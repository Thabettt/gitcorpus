from __future__ import annotations

import argparse
import random
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from detect.gitio import GitError, GitRepo, clone_lean, fetch_pr_refs, git_error_tail  # noqa: E402
from detect.repo_walk import walk_windows  # noqa: E402


def _repo_is_empty(repo: GitRepo) -> bool:
    try:
        return repo.git("rev-list", "--all", "--count").strip() == "0"
    except (GitError, subprocess.TimeoutExpired):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="+", help="owner/repo entries to verify")
    parser.add_argument("--depth", type=int, default=100)
    parser.add_argument(
        "--max-tips-per-repo",
        type=int,
        default=250,
        help="0 verifies every PR tip (slow on monster repos)",
    )
    parser.add_argument(
        "--root", default=str(Path(__file__).resolve().parents[1] / "clones" / "verify")
    )
    args = parser.parse_args()

    root = Path(args.root)
    checked = mismatch = errors = 0
    started_all = time.monotonic()
    for full_name in args.repos:
        dest = root / full_name.replace("/", "__")
        dest.mkdir(parents=True, exist_ok=True)
        t0 = time.monotonic()
        if not (dest / ".git").exists():
            clone_lean(full_name, dest, depth=args.depth, timeout=1800)
        t_clone = time.monotonic() - t0
        repo = GitRepo(dest)
        t0 = time.monotonic()
        refs = fetch_pr_refs(repo, depth=args.depth)
        t_fetch = time.monotonic() - t0
        t0 = time.monotonic()
        walked = walk_windows(repo, refs, depth=args.depth)
        t_walk = time.monotonic() - t0
        tips = sorted(refs)
        sampled = tips
        if args.max_tips_per_repo and len(tips) > args.max_tips_per_repo:
            sampled = sorted(random.sample(tips, args.max_tips_per_repo))
        local_mismatch = 0
        t0 = time.monotonic()
        for number in sampled:
            truth = tuple(repo.git("rev-list", "-n", str(args.depth), refs[number]).split())
            checked += 1
            if set(walked[number]) != set(truth):
                mismatch += 1
                local_mismatch += 1
                print(
                    f"MISMATCH {full_name} PR #{number}:"
                    f" walked={len(walked[number])} truth={len(truth)}"
                )
        t_verify = time.monotonic() - t0
        try:
            head = repo.git("rev-parse", "HEAD").strip()
        except (GitError, subprocess.TimeoutExpired) as exc:
            reason = git_error_tail(exc)
            if _repo_is_empty(repo):
                head_label = f"skipped (empty repository: {reason})"
            else:
                # An unreadable HEAD in a repo that has commits is a gate
                # failure, not a pass we may wave through as "skipped".
                errors += 1
                head_label = f"error ({reason})"
        else:
            try:
                head_walk = walk_windows(repo, {0: head}, depth=args.depth)[0]
                head_truth = tuple(repo.git("rev-list", "-n", str(args.depth), head).split())
            except (GitError, subprocess.TimeoutExpired) as exc:
                errors += 1
                head_label = f"error ({git_error_tail(exc)})"
            else:
                checked += 1
                head_mismatch = set(head_walk) != set(head_truth)
                if head_mismatch:
                    mismatch += 1
                    local_mismatch += 1
                    print(
                        f"MISMATCH {full_name} HEAD:"
                        f" walked={len(head_walk)} truth={len(head_truth)}"
                    )
                head_label = "MISMATCH" if head_mismatch else "ok"
        print(
            f"{full_name}: tips={len(tips)} verified={len(sampled)} mismatches={local_mismatch}"
            f" head={head_label}"
            f" clone={t_clone:.1f}s fetch={t_fetch:.1f}s walk={t_walk:.2f}s verify={t_verify:.1f}s",
            flush=True,
        )
    total = time.monotonic() - started_all
    print(f"\nchecked={checked} mismatches={mismatch} errors={errors} total={total:.1f}s")
    return 1 if mismatch or errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
