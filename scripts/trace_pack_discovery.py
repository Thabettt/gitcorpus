"""Mine candidate fingerprints that the current trace pack does not match.

Documentation lags the products, so each pack release should also look at the
data (docs/findings/2026-11-15-trace-pack-audit.md §5 step 6). This script
makes light clones (``--filter=blob:none --no-checkout``) of a sample of repos
and lists what the pack leaves unmatched:

* ``co_author``  — Co-authored-by trailers no rule matched (name + email domain);
* ``bot_identity`` — ``[bot]`` commit authors/committers no rule matched;
* ``dot_path``   — dot-directories and dot-files no file rule matched;
* ``instruction_file`` — upper-case ``*.md`` files no file rule matched;
* ``branch_prefix`` — remote branch prefixes no branch rule matched.

Candidates are ranked by how many repositories show them. They are leads for
research, not rules: each needs documentation or observed evidence and a
validation sample before it enters a pack.

Personal data is minimised: co-author emails are reduced to their domain, and
GitHub noreply addresses keep the login only for ``[bot]`` accounts.

Usage::

    PYTHONPATH=<checkout>/src python scripts/trace_pack_discovery.py \
        --pack packs/2026-11-15.json --run 101 --limit 200 \
        --out packs/discovery/2026-11-15-run101.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import tempfile
from collections import defaultdict
from pathlib import Path

# Tooling directories that are never coding-agent evidence on their own.
COMMON_DOT = {
    ".git",
    ".github",
    ".gitlab",
    ".vscode",
    ".idea",
    ".husky",
    ".devcontainer",
    ".circleci",
    ".config",
    ".cargo",
    ".changeset",
    ".storybook",
    ".yarn",
    ".venv",
    ".vs",
    ".mvn",
    ".gradle",
    ".next",
    ".nuxt",
    ".docker",
    ".pnpm-store",
    ".turbo",
    ".gitignore",
    ".gitattributes",
    ".gitmodules",
    ".editorconfig",
    ".npmrc",
    ".nvmrc",
    ".prettierrc",
    ".prettierignore",
    ".eslintrc",
    ".eslintignore",
    ".dockerignore",
    ".env",
    ".env.example",
    ".python-version",
    ".pre-commit-config.yaml",
    ".travis.yml",
    ".gitkeep",
    ".keep",
    ".DS_Store",
    ".clang-format",
    ".clang-tidy",
    ".flake8",
    ".markdownlint.json",
    ".yamllint",
    ".stylelintrc",
    ".babelrc",
    ".browserslistrc",
    ".tool-versions",
    ".rustfmt.toml",
    ".golangci.yml",
    ".mailmap",
    ".coveragerc",
}
COMMON_MD = {
    "README.md",
    "CHANGELOG.md",
    "LICENSE.md",
    "CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    "SECURITY.md",
    "SUPPORT.md",
    "AUTHORS.md",
    "HISTORY.md",
    "TODO.md",
    "NOTICE.md",
    "GOVERNANCE.md",
    "MAINTAINERS.md",
    "ROADMAP.md",
    "RELEASE.md",
    "RELEASING.md",
    "CONTRIBUTORS.md",
    "INSTALL.md",
    "UPGRADING.md",
    "MIGRATION.md",
    "FAQ.md",
}
# Human branch-naming conventions (conventional commits, git-flow, dependency bots).
CONVENTIONAL_PREFIXES = {
    "fix/",
    "feat/",
    "feature/",
    "features/",
    "chore/",
    "docs/",
    "doc/",
    "ci/",
    "test/",
    "tests/",
    "refactor/",
    "perf/",
    "release/",
    "releases/",
    "hotfix/",
    "bugfix/",
    "bug/",
    "build/",
    "style/",
    "dev/",
    "develop/",
    "wip/",
    "revert/",
    "deps/",
    "dependabot/",
    "renovate/",
    "backport/",
    "backup/",
    "archive/",
    "experiment/",
    "experimental/",
    "security/",
    "debug/",
    "bench/",
    "integration/",
    "update/",
    "upgrade/",
    "gh-pages/",
    "user/",
    "users/",
    "pr/",
    "review/",
    "automation/",
    "temp/",
    "tmp/",
    "poc/",
}
UPPER_MD = re.compile(r"^[A-Z][A-Z0-9_-]+\.md$")
NOREPLY = re.compile(r"^(?:\d+\+)?(?P<login>[^@]+)@users\.noreply\.github\.com$", re.I)


def git(*args: str, cwd: Path | None = None, timeout: int = 300) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip()[:200])
    return result.stdout


def clone(repo: str, root: Path, depth: int) -> Path | None:
    target = root / repo.replace("/", "__")
    if (target / ".git").exists() or (target / "HEAD").exists():
        return target
    try:
        git(
            "clone",
            "--quiet",
            "--filter=blob:none",
            "--no-checkout",
            f"--depth={depth}",
            f"https://github.com/{repo}.git",
            str(target),
        )
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f"skip {repo}: {exc}")
        return None
    return target


def coauthor_key(name: str | None, email: str | None) -> str:
    email = email or ""
    name = (name or "").strip()
    login = NOREPLY.match(email)
    if login and login.group("login").endswith("[bot]"):
        return f"{name} <{login.group('login')}@users.noreply.github.com>"
    if login:
        return f"{name} <*@users.noreply.github.com>"
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else "?"
    return f"{name} <*@{domain}>"


def mine(pack, repo: str, path: Path, candidates) -> None:
    from detect.structured import path_matches

    from detect import attribution
    from detect.attribution import parse_structured_trailers

    file_specs = [
        rule.match["path"]
        for rule in pack.rules_for("file", "workflow", include_rejections=True)
        if isinstance(rule.match.get("path"), dict)
    ]
    sep, end = "\x1f", "\x1e"
    log = git("log", f"--format=%H{sep}%an{sep}%ae{sep}%cn{sep}%ce{sep}%B{end}", cwd=path)
    messages, identities = [], []
    for record in log.split(end):
        parts = record.strip("\n").split(sep)
        if len(parts) < 6:
            continue
        sha, an, ae, cn, ce, body = parts[:6]
        messages.append((sha, body))
        identities.append({"login": "", "name": an, "email": ae, "role": "author", "commit": sha})
        identities.append(
            {"login": "", "name": cn, "email": ce, "role": "committer", "commit": sha}
        )
    noise = [
        re.compile(str(rule.match.get("regex") or rule.pattern), re.IGNORECASE)
        for rule in pack.rules_for("bot", include_rejections=True)
        if rule.match.get("regex") or rule.pattern
    ]
    matched_values = {
        str(hit.evidence.get("trailer_value"))
        for hit in attribution.match_commit_messages(pack, messages)
    }
    for _sha, body in messages:
        for trailer in parse_structured_trailers(body):
            if trailer.token.lower() != "co-authored-by" or trailer.value in matched_values:
                continue
            if not (trailer.name or "").strip():
                continue
            if any(rx.search(trailer.value) for rx in noise):
                continue  # CI/release bots already in the noise ledger
            candidates["co_author"][coauthor_key(trailer.name, trailer.email)].add(repo)
    matched_commits = {
        (hit.evidence.get("commit"), hit.role)
        for hit in attribution.match_author_identities(pack, identities)
    }
    for entry in identities:
        name, email = entry["name"], entry["email"]
        if "[bot]" not in name.lower() and "[bot]" not in email.lower():
            continue
        if (entry["commit"], f"commit_{entry['role']}") in matched_commits:
            continue
        if any(rx.search(name) or rx.search(email) for rx in noise):
            continue  # already in the CI/release noise ledger
        candidates["bot_identity"][name].add(repo)
    try:
        paths = git("ls-tree", "-r", "--name-only", "HEAD", cwd=path).splitlines()
    except RuntimeError:
        paths = []
    # Test every path against the file rules: match evidence keeps one example
    # path per rule, so it cannot tell which other paths a rule also covers.
    seen_dot: set[str] = set()
    for file_path in paths:
        if any(path_matches(file_path, spec) for spec in file_specs):
            continue
        segments = file_path.split("/")
        for index, segment in enumerate(segments):
            if segment.startswith(".") and segment not in COMMON_DOT:
                marker = segment + ("/" if index < len(segments) - 1 else "")
                if marker not in seen_dot:
                    seen_dot.add(marker)
                    candidates["dot_path"][marker].add(repo)
                break
        leaf = segments[-1]
        if UPPER_MD.match(leaf) and leaf not in COMMON_MD:
            candidates["instruction_file"][leaf].add(repo)
    try:
        heads = [
            line.split("refs/heads/", 1)[1]
            for line in git("ls-remote", "--heads", "origin", cwd=path).splitlines()
            if "refs/heads/" in line
        ]
    except RuntimeError:
        heads = []
    matched_heads = {
        str(hit.evidence.get("branch")) for hit in attribution.match_branches(pack, heads)
    }
    for head in heads:
        if "/" not in head or head in matched_heads:
            continue
        prefix = head.split("/", 1)[0] + "/"
        if prefix.lower() not in CONVENTIONAL_PREFIXES:
            candidates["branch_prefix"][prefix].add(repo)


def repos_from_run(run_id: int, limit: int | None) -> list[str]:
    import sqlalchemy as sa

    engine = sa.create_engine(os.environ["DATABASE_URL"])
    query = (
        "SELECT i.full_name FROM run_items i LEFT JOIN repos r ON r.id = i.repo_id "
        "WHERE i.run_id = :run AND coalesce(r.visibility, 'public') = 'public' "
        "ORDER BY i.stargazers DESC NULLS LAST, i.repo_id"
    )
    if limit:
        query += " LIMIT :limit"
    with engine.connect() as connection:
        return [
            row[0] for row in connection.execute(sa.text(query), {"run": run_id, "limit": limit})
        ]


def main() -> int:
    from detect.packs import load_pack_file

    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", type=int, help="search or detect run whose repos to sample")
    source.add_argument("--repos", nargs="+", help="explicit owner/name list")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--depth", type=int, default=200)
    parser.add_argument("--clone-dir", type=Path)
    parser.add_argument("--min-repos", type=int, default=2)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    pack = load_pack_file(args.pack)
    repos = args.repos or repos_from_run(args.run, args.limit)
    candidates: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    with tempfile.TemporaryDirectory() as temporary:
        root = args.clone_dir or Path(temporary)
        root.mkdir(parents=True, exist_ok=True)
        for number, repo in enumerate(repos, start=1):
            path = clone(repo, root, args.depth)
            if path is None:
                continue
            try:
                mine(pack, repo, path, candidates)
            except (RuntimeError, subprocess.TimeoutExpired) as exc:
                print(f"skip {repo}: {exc}")
            if number % 25 == 0:
                print(f"{number}/{len(repos)} repos mined")
    rows = [
        {
            "kind": kind,
            "candidate": candidate,
            "repos": len(found),
            "examples": " ".join(sorted(found)[:3]),
        }
        for kind, values in candidates.items()
        for candidate, found in values.items()
        if len(found) >= args.min_repos
    ]
    rows.sort(key=lambda row: (-row["repos"], row["kind"], row["candidate"]))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["kind", "candidate", "repos", "examples"])
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"{len(repos)} repos sampled; {len(rows)} candidates seen in >= {args.min_repos} "
        f"repos written to {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
