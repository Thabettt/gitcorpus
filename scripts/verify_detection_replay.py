from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine, text  # noqa: E402

from detect.git_orchestrator import LOCAL_CHANNELS, GitScanConfig, _scan_one  # noqa: E402
from detect.gitio import GitRepo, clone_lean  # noqa: E402
from detect.orchestrator import DetectOptions  # noqa: E402
from detect.packs import load_frozen  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True, help="detect run to replay against")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument(
        "--sample",
        choices=("random", "first"),
        default="random",
        help="random draws across the whole run; first replays the earliest scans (heaviest)",
    )
    parser.add_argument(
        "--root", default=str(Path(__file__).resolve().parents[1] / "clones" / "replay")
    )
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        run = connection.execute(
            text("SELECT filter_spec, source_run_id FROM runs WHERE id=:id"), {"id": args.run_id}
        ).one()
        spec_row = run[0]
        rows = connection.execute(
            text(
                "SELECT i.full_name, i.detection, i.repo_id FROM run_items i"
                " WHERE i.run_id=:id AND i.detection IS NOT NULL"
                f" ORDER BY {'random()' if args.sample == 'random' else 'i.id'} LIMIT :limit"
            ),
            {"id": args.run_id, "limit": args.limit},
        ).all()
    channels = frozenset(ch for ch in spec_row["channels"] if ch in LOCAL_CHANNELS)
    spec = DetectOptions(
        source_run_id=run[1],
        pack_version=spec_row["pack_version"],
        agents=frozenset(spec_row["agents"]) if spec_row.get("agents") else None,
        channels=frozenset(spec_row["channels"]),
        source="git",
        clone_depth=spec_row.get("clone", {}).get("depth", 100),
        clone_keep=False,
        windows=spec_row.get("windows") or {"commits": 100, "prs": 100, "issues": 100},
    )
    pack = load_frozen(engine, spec.pack_version)
    cfg = GitScanConfig(depth=spec.clone_depth, keep=False, scan_root=args.root, timeout=1800)
    run_dir = Path(args.root) / f"detect-{args.run_id}"

    mismatches = skipped_unavailable = 0
    for index, (full_name, stored, repo_id) in enumerate(rows, start=1):
        dest = run_dir / str(full_name).replace("/", "__")
        if stored.get("unavailable"):
            skipped_unavailable += 1
            continue
        candidate = {"full_name": full_name, "repo_id": repo_id, "stargazers": None}
        try:
            scan = _scan_one(
                run_dir,
                cfg,
                spec,
                pack,
                channels,
                candidate,
                clone_one=lambda name, path: clone_lean(
                    name, path, depth=cfg.depth, timeout=cfg.timeout
                ),
                make_repo=lambda path: GitRepo(path, timeout=cfg.timeout),
            )
            fresh = scan.document
            if fresh != stored:
                mismatches += 1
                print(f"DIFF {full_name}")
                for key in sorted(set(fresh) | set(stored)):
                    if fresh.get(key) != stored.get(key):
                        print(f"  {key}: fresh={fresh.get(key)!r} stored={stored.get(key)!r}")
        finally:
            shutil.rmtree(dest, ignore_errors=True)
        if index % 25 == 0:
            print(f"replayed {index}/{len(rows)} mismatches={mismatches}", flush=True)
    print(
        f"\nreplayed={len(rows)} compared={len(rows) - skipped_unavailable}"
        f" skipped_unavailable={skipped_unavailable} mismatches={mismatches}"
    )
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
