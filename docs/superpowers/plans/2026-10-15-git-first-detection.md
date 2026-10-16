# Git-First (Local Clone) Detection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add **a second, user-selectable detection method — local clone ("git")** — alongside the existing GitHub API method, which stays the default and is never replaced. Git mode downloads each repository with lean git clones and matches entirely locally: zero API calls, ~1 h and ~4 GB for the 17.7k-repo corpus, measured at 99.5% repo coverage against the API run. Both methods produce identical evidence/rollup/summary schemas and pass through the same executor seams.

**Architecture:** The detection options page presents both methods as selectable cards with pros/cons, and the estimate partial shows a size-based estimate for each (candidate count × stored `size_kb` for git; calls/hours for API), so the choice is informed per corpus. Git mode runs in two phases per repo: **Fetch** (plain git only — `clone --depth=N --filter=blob:none`, then one `refs/pull/*/head` fetch for PR commits) and **Detect** (pure local matching over `git ls-tree` / `git log` / `git show` output against the frozen pack). A new `src/detect/gitio.py` wraps git; `src/detect/local_channels.py` mirrors the four API channel functions plus local `pr_metadata`/`branch` detectors, reusing `attribution.py` untouched; `src/detect/git_orchestrator.py` walks candidates exactly like `run_detection` and returns the same `RunPayload`; the existing detect runner branches on the spec's new `source` field (default `"api"`).

**Tech Stack:** Python 3.12, git ≥ 2.20 (subprocess; dev machine has 2.47), SQLAlchemy 2 + Postgres, FastAPI + Jinja2 + htmx, pytest, ruff + black.

**Spec:** `design/detection-pipeline.md` (stage-by-stage spec). Companion rationale and measurements: `design/detection-options.md`; tier boundaries: `docs/detection-tiers.md`.

## Global Constraints

- Python `>=3.12`; line length 100; ruff (`E,F,I,UP,B`) + black clean; coverage floor `fail_under = 93` (`pyproject.toml`).
- DB tests require `TEST_DATABASE_URL` ending in `_test` (or `GITCORPUS_REQUIRE_TEST_DB=1`); use the central `clean_db` fixture from `tests/conftest.py` — **never** add a local `TRUNCATE` fixture.
- **Git mode MUST NOT make any GitHub API call**: no `httpx` client, no limiter, no `build_deps`. The runner branch for `source == "git"` must not construct API dependencies; enforced by test.
- **The API method stays the default and is never replaced.** `source` defaults to `"api"` everywhere; every existing spec, page, test and run replays unchanged. The options page presents **both methods** (API = default, already implemented; local clone = new) with pros/cons and a size-based estimate for each, so the user sees what goes where before choosing.
- All git subprocesses go through `src/detect/gitio.py` only; always with `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=os.devnull`; argv as a list, never shell strings.
- Local channels are exactly `file, author, branch, bot, commit_trailer, pr_metadata`. `label` and `issue` are API-only: in git mode they are recorded as skipped (`result_summary["skipped_channels"]`, options-page note, run warning) — never silently dropped.
- Evidence schema, rollup schema (`run_items.detection`), `result_summary` shape, `runs.kind='detect'`, `source_run_id` semantics and the bundle format are unchanged. No migration is needed.
- Windows + POSIX: `pathlib` paths, `subprocess` list argv; tests that need a real git binary skip when `shutil.which("git") is None`.
- Delete-after-scan is the default (`clone.keep=false`); `keep=true` is opt-in for offline re-scans. Low-disk guard (2 GB reserve, `enrich.cloner.LOW_DISK_THRESHOLD_MB`) runs before the scan starts.
- Superseding rule for channels is the executor/cancellation contract: per-repo work checks `lib.cancellation.check()`; a cancelled scan run must end as `cancelled`, never `failed`.
- Golden pages: regenerate with `UPDATE_GOLDEN=1` after template edits; review the snapshot diff — only the touched pages may change. No new routes → the OpenAPI pin must NOT change.
- Conventional commit prefixes matching repo style (`feat:`, `test:`, `docs:`, `fix:`).
- Run tests with: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest <path> -q` (Windows PowerShell).

**Preflight (once, before Task 1):** `git status --porcelain` must be clean. `git --version` must be ≥ 2.20 (partial clone filter support). `TEST_DATABASE_URL` must point at a `_test` database for the DB-backed tasks (7, 8, 9).

## Source references (for revision)

- **Spec:** `design/detection-pipeline.md` — stages 0–8, the two commands, the measured channel table, failure list.
- **Route comparison + all measurements:** `design/detection-options.md`.
- **Tier rules:** `docs/detection-tiers.md` (clone tier vs API tier).
- **Ground truth run:** detection run #3 (`runs.id = 42`) — 41,189 evidence rows across 882 repos; every recovery figure in the spec traces back to it.
- **Existing API-mode code to mirror, not rewrite:** `src/detect/orchestrator.py` (`run_detection`, `_RepoScan`, `_repo_document`, `_summary`, `_failed_scan`, `_candidates`), `src/detect/channels.py` (return shapes and probe limits), `src/detect/attribution.py` (all matchers — do not touch), `src/enrich/cloner.py` (process/cancel/timeout/marker patterns).

## File Structure

**Create**

- `src/detect/gitio.py` — git subprocess wrapper (`run_git`, `GitRepo`, `clone_lean`), tree/blob reads, log parsing (`CommitRecord`, `parse_log`, `read_log`), PR-refs primitives (`fetch_pr_refs`, `list_pr_refs`, `walk_pr_shas`, `read_commits`) and the merge-message parser (`parse_merge_branches`).
- `src/detect/local_channels.py` — `detect_files_local`, `detect_history_local`, `detect_pr_commits_local`, `detect_branch_local` (return `ChannelResult`s identical in shape to `channels.py`).
- `src/detect/git_orchestrator.py` — `GitScanConfig`, `LOCAL_CHANNELS`, `run_git_detection(...) -> RunPayload`.
- `tests/unit/test_gitio.py`
- `tests/unit/test_detect_local_channels.py`
- `tests/unit/test_git_orchestrator.py`
- `tests/unit/test_detect_runner.py`

**Modify**

- `src/detect/orchestrator.py` — `DetectOptions` gains `source`, `clone_depth`, `clone_keep` (defaults keep old specs valid).
- `src/serve/detect_spec.py` — parse/validate `source` + `clone`; `detect_spec_to_dict` emits them.
- `src/enrich/cloner.py` — `CloneMode.DETECT` + factor `0.006` + flags (for the estimate only).
- `src/serve/detect.py` — runner branches to `run_git_detection` when `spec.source == "git"`; form reads `source`/`clone_depth`/`clone_keep`; estimate partial renders the clone estimate in git mode.
- `src/serve/templates/detect_options.html` — Scan-source section (radio + depth + keep) and a note that `label`/`issue` are skipped in local mode.
- `src/serve/templates/partials/detect_estimate.html` — branch for git estimates.
- `src/serve/templates/detect_detail.html` — show scan source; warn when channels were skipped.
- `tests/unit/test_cloner.py` — detect-mode factor/flags tests.
- `tests/contract/test_detect_routes.py` — spec round-trip extensions; git-source POST; git estimate partial.
- `tests/golden/snapshots/*` — regenerate detect options/detail pages (and estimate partial if changed).
- `docs/development-log.md`, `README.md` — status notes.
- `design/detection-pipeline.md` — append the build-plan pointer under "Where to go next".

---

## Task 1: Git I/O core — run_git, clone_lean, tree, blob, log

**Files:**
- Create: `src/detect/gitio.py`
- Test: `tests/unit/test_gitio.py`

**Interfaces:**
- Consumes: `lib.cancellation.check` (polled in the wait loop, same pattern as `enrich/cloner.py:190-224`).
- Produces: `GitError(argv, returncode, stderr)`; `git_env() -> dict[str,str]`; `run_git(argv, *, cwd, timeout=None) -> str`; `GitRepo(dest: Path, timeout: float | None = None)` with `.git(*args) -> str`; `clone_lean(full_name, dest, *, depth, timeout=None) -> None`; `list_tree(repo) -> tuple[str, ...]`; `read_blob(repo, path) -> str | None`; `CommitRecord(sha, author_name, author_email, committer_name, committer_email, committed_at, message)`; `parse_log(output) -> tuple[CommitRecord, ...]`; `read_log(repo, *, limit) -> tuple[CommitRecord, ...]`. Tasks 2–4 build on all of these.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_gitio.py`:

```python
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from detect import gitio
from detect.gitio import (
    GitError,
    GitRepo,
    clone_lean,
    list_tree,
    parse_log,
    read_blob,
    read_log,
)

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


class FakeRepo(GitRepo):
    """GitRepo whose git() answers from a canned handler."""

    def __init__(self, handler):
        super().__init__(Path("."))
        self._handler = handler
        self.calls: list[tuple[str, ...]] = []

    def git(self, *args: str) -> str:
        self.calls.append(args)
        result = self._handler(args)
        if result is None:
            raise GitError(list(args), 128, "fake: unknown command")
        return result


def test_parse_log_splits_records_and_keeps_multiline_messages():
    output = (
        "abc123\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-01-02T03:04:05+00:00\x1ffeat: add\n\nCo-authored-by: Claude <noreply@anthropic.com>\x1e"
        "\ndef456\x1fBot\x1fbot@example.com\x1fBot\x1fbot@example.com"
        "\x1f2026-01-03T00:00:00+00:00\x1fchore: bump\x1e"
    )
    records = parse_log(output)
    assert [r.sha for r in records] == ["abc123", "def456"]
    assert records[0].author_email == "jane@example.com"
    assert "Co-authored-by: Claude" in records[0].message


def test_list_tree_returns_paths():
    fake = FakeRepo(lambda args: "CLAUDE.md\nsrc/main.rs\n" if args[0] == "ls-tree" else None)
    assert list_tree(fake) == ("CLAUDE.md", "src/main.rs")


def test_read_blob_returns_none_when_git_fails():
    fake = FakeRepo(lambda args: None)
    assert read_blob(fake, ".gitignore") is None


def test_read_log_uses_limit_and_parses():
    line = "a1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com\x1f2026-01-01T00:00:00+00:00\x1ffeat\x1e"
    fake = FakeRepo(lambda args: line if args[0] == "log" else None)
    records = read_log(fake, limit=100)
    assert fake.calls[0] == ("log", "-n", "100", "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%cI%x1f%B%x1e", "HEAD")
    assert records[0].sha == "a1"


def test_clone_lean_uses_depth_and_blob_filter(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(gitio, "run_git", lambda argv, **kw: calls.append(list(argv)) or "")
    clone_lean("octo/repo", tmp_path / "r", depth=150, timeout=5)
    argv = calls[0]
    assert "--depth=150" in argv
    assert "--filter=blob:none" in argv
    assert "--no-checkout" in argv
    assert argv[-2:] == ["https://github.com/octo/repo.git", str(tmp_path / "r")]


@needs_git
def test_real_git_tree_blob_and_log(tmp_path):
    repo_dir = tmp_path / "r"
    repo_dir.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Jane",
        "GIT_AUTHOR_EMAIL": "jane@example.com",
        "GIT_COMMITTER_NAME": "Jane",
        "GIT_COMMITTER_EMAIL": "jane@example.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True, env=env)
    (repo_dir / ".gitignore").write_text("target/\n", encoding="utf-8")
    (repo_dir / "CLAUDE.md").write_text("# guidance\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "feat: x"], cwd=repo_dir, check=True, env=env)

    repo = GitRepo(repo_dir)
    assert "CLAUDE.md" in list_tree(repo)
    assert read_blob(repo, ".gitignore") == "target/\n"
    records = read_log(repo, limit=10)
    assert len(records) == 1
    assert records[0].author_email == "jane@example.com"


@needs_git
def test_run_git_raises_on_missing_head(tmp_path):
    repo_dir = tmp_path / "empty"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    fake = GitRepo(repo_dir)
    with pytest.raises(GitError):
        fake.git("log", "-n", "1", "HEAD")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_gitio.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'detect.gitio'`

- [ ] **Step 3: Write the implementation**

Create `src/detect/gitio.py`:

```python
from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from lib import cancellation

_CANCEL_POLL = 0.1
_STDERR_LIMIT = 200
LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%cI%x1f%B%x1e"
_UNIT = "\x1f"
_RECORD = "\x1e"


class GitError(RuntimeError):
    def __init__(self, argv: Sequence[str], returncode: int, stderr: str) -> None:
        message = f"{' '.join(str(part) for part in argv)} -> exit {returncode}: {stderr[:_STDERR_LIMIT]}"
        super().__init__(message)
        self.argv = tuple(str(part) for part in argv)
        self.returncode = returncode
        self.stderr = stderr


def git_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    return env


def run_git(argv: Sequence[str], *, cwd: Path | str, timeout: float | None = None) -> str:
    process = subprocess.Popen(
        ["git", *argv],
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_env(),
        text=True,
    )
    deadline = None if timeout is None else time.monotonic() + timeout
    while True:
        cancellation.check()
        step = _CANCEL_POLL
        if deadline is not None:
            step = min(step, max(0.01, deadline - time.monotonic()))
        try:
            stdout, stderr = process.communicate(timeout=step)
            break
        except subprocess.TimeoutExpired:
            if deadline is not None and time.monotonic() >= deadline:
                process.kill()
                process.communicate()
                raise subprocess.TimeoutExpired(["git", *argv], timeout) from None
    if process.returncode != 0:
        raise GitError(["git", *argv], process.returncode, stderr or "")
    return stdout or ""


@dataclass
class GitRepo:
    dest: Path
    timeout: float | None = None

    def git(self, *args: str) -> str:
        return run_git(args, cwd=self.dest, timeout=self.timeout)


def clone_lean(
    full_name: str, dest: Path, *, depth: int, timeout: float | None = None
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_git(
        [
            "clone",
            "--quiet",
            "--single-branch",
            "--no-checkout",
            f"--depth={depth}",
            "--filter=blob:none",
            f"https://github.com/{full_name}.git",
            str(dest),
        ],
        cwd=dest.parent,
        timeout=timeout,
    )


def list_tree(repo: GitRepo) -> tuple[str, ...]:
    output = repo.git("ls-tree", "-r", "--name-only", "HEAD")
    return tuple(line for line in output.splitlines() if line)


def read_blob(repo: GitRepo, path: str) -> str | None:
    try:
        return repo.git("show", f"HEAD:{path}")
    except GitError:
        return None


@dataclass(frozen=True)
class CommitRecord:
    sha: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    committed_at: str
    message: str


def parse_log(output: str) -> tuple[CommitRecord, ...]:
    records: list[CommitRecord] = []
    for chunk in output.split(_RECORD):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        parts = chunk.split(_UNIT, 6)
        if len(parts) != 7:
            continue
        records.append(CommitRecord(*parts))
    return tuple(records)


def read_log(repo: GitRepo, *, limit: int) -> tuple[CommitRecord, ...]:
    output = repo.git("log", "-n", str(limit), f"--format={LOG_FORMAT}", "HEAD")
    return parse_log(output)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_gitio.py -q`
Expected: PASS (real-git tests included; they skip only when git is missing)

- [ ] **Step 5: Commit**

```bash
git add src/detect/gitio.py tests/unit/test_gitio.py
git commit -m "feat(detect): add git I/O core for local scans"
```

---

## Task 2: PR-refs primitives and merge-message parsing

**Files:**
- Modify: `src/detect/gitio.py`
- Test: `tests/unit/test_gitio.py`

**Interfaces:**
- Consumes: Task 1 (`GitRepo`, `GitError`, `LOG_FORMAT`, `parse_log`), `lib.batching.chunked`.
- Produces: `fetch_pr_refs(repo, *, depth) -> None`; `list_pr_refs(repo) -> dict[int, str]` (PR number → head sha); `walk_pr_shas(repo, refs, *, depth) -> dict[int, tuple[str, ...]]`; `read_commits(repo, shas) -> dict[str, CommitRecord]` (chunked `git show`); `parse_merge_branches(messages) -> list[tuple[int | None, str]]`. Tasks 4 and 7 use all of these.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_gitio.py`:

```python
from detect.gitio import (
    fetch_pr_refs,
    list_pr_refs,
    parse_merge_branches,
    read_commits,
    walk_pr_shas,
)

_GOOD_REF_FORMAT = (
    "refs/gc/pr/12 aaa\n"
    "refs/gc/pr/7 bbb\n"
    "refs/gc/pr/notes ccc\n"
)


def test_list_pr_refs_parses_numbers_and_skips_non_numeric():
    fake = FakeRepo(
        lambda args: _GOOD_REF_FORMAT if args[0] == "for-each-ref" else None
    )
    assert list_pr_refs(fake) == {12: "aaa", 7: "bbb"}


def test_fetch_pr_refs_uses_commit_only_filter():
    fake = FakeRepo(lambda args: "" if args[0] == "fetch" else None)
    fetch_pr_refs(fake, depth=100)
    assert fake.calls[0] == (
        "fetch",
        "--quiet",
        "--depth",
        "100",
        "--filter=tree:0",
        "--no-tags",
        "origin",
        "+refs/pull/*/head:refs/gc/pr/*",
    )


def test_walk_pr_shas_reads_each_ref():
    def handler(args):
        if args[0] == "rev-list":
            return {"aaa": "s1\ns2\n", "bbb": "s2\ns3\n"}[args[3]]
        return None

    fake = FakeRepo(handler)
    assert walk_pr_shas(fake, {12: "aaa", 7: "bbb"}, depth=2) == {
        12: ("s1", "s2"),
        7: ("s2", "s3"),
    }


def test_read_commits_parses_show_output():
    def handler(args):
        if args[0] != "show":
            return None
        return "".join(
            f"{sha}\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
            f"\x1f2026-01-01T00:00:00+00:00\x1ffeat {sha}\x1e\n"
            for sha in args[3:]
        )

    fake = FakeRepo(handler)
    records = read_commits(fake, ["a", "b"])
    assert set(records) == {"a", "b"}
    assert records["a"].message == "feat a"


def test_parse_merge_branches_handles_pr_local_and_fork_forms():
    messages = [
        ("s1", "Merge pull request #123 from octo/claude/fix-login\n\nbody text"),
        ("s2", "Merge branch 'codex/thing' into main"),
        ("s3", "Merge pull request #7 from forkowner/devin/rewrite"),
        ("s4", "feat: normal commit"),
        ("s5", "chore: mention Merge pull request #999 from octo/x in body"),
    ]
    assert parse_merge_branches(messages) == [
        (123, "claude/fix-login"),
        (None, "codex/thing"),
        (7, "devin/rewrite"),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_gitio.py -q`
Expected: FAIL — `ImportError: cannot import name 'fetch_pr_refs'`

- [ ] **Step 3: Write the implementation**

Append to `src/detect/gitio.py`:

```python
import re
from collections.abc import Iterable, Mapping

from lib.batching import chunked

_MERGE_PR = re.compile(
    r"Merge pull request #(?P<pr>\d+) from (?P<owner>[^/\s]+)/(?P<head>\S+)"
)
_MERGE_LOCAL = re.compile(r"Merge branch '(?P<head>[^']+)'")
_SHOW_BATCH = 200


def fetch_pr_refs(repo: GitRepo, *, depth: int) -> None:
    repo.git(
        "fetch",
        "--quiet",
        "--depth",
        str(depth),
        "--filter=tree:0",
        "--no-tags",
        "origin",
        "+refs/pull/*/head:refs/gc/pr/*",
    )


def list_pr_refs(repo: GitRepo) -> dict[int, str]:
    output = repo.git("for-each-ref", "--format=%(refname) %(objectname)", "refs/gc/pr")
    refs: dict[int, str] = {}
    for line in output.splitlines():
        name, _, sha = line.partition(" ")
        number = name.rpartition("/")[2]
        if number.isdigit() and sha:
            refs[int(number)] = sha
    return refs


def walk_pr_shas(
    repo: GitRepo, refs: Mapping[int, str], *, depth: int
) -> dict[int, tuple[str, ...]]:
    walks: dict[int, tuple[str, ...]] = {}
    for number, sha in sorted(refs.items()):
        output = repo.git("rev-list", "-n", str(depth), sha)
        walks[number] = tuple(line for line in output.splitlines() if line)
    return walks


def read_commits(repo: GitRepo, shas: Sequence[str]) -> dict[str, CommitRecord]:
    records: dict[str, CommitRecord] = {}
    for batch in chunked(list(shas), _SHOW_BATCH):
        output = repo.git("show", "-s", f"--format={LOG_FORMAT}", *batch)
        for record in parse_log(output):
            records[record.sha] = record
    return records


def parse_merge_branches(
    messages: Iterable[tuple[str | None, str]]
) -> list[tuple[int | None, str]]:
    found: list[tuple[int | None, str]] = []
    for _sha, message in messages:
        first = (message or "").split("\n", 1)[0].strip()
        match = _MERGE_PR.match(first)
        if match:
            found.append((int(match.group("pr")), match.group("head")))
            continue
        match = _MERGE_LOCAL.match(first)
        if match:
            found.append((None, match.group("head")))
    return found
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_gitio.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/detect/gitio.py tests/unit/test_gitio.py
git commit -m "feat(detect): add PR-ref fetch and merge-message primitives"
```

---

## Task 3: Local file + history channels

**Files:**
- Create: `src/detect/local_channels.py`
- Test: `tests/unit/test_detect_local_channels.py`

**Interfaces:**
- Consumes: `detect.gitio` (`GitRepo`, `GitError`, `list_tree`, `read_blob`, `read_log`, `CommitRecord`); `detect.attribution` (`match_files`, `match_author_identities`, `match_commit_messages`, `match_bots`, `is_noise_commit`, `dedupe_hits`, `Hit`); `enrich.trees_first.FilePresence`; `detect.channels.ChannelResult`; `detect.packs.Pack`.
- Produces: `detect_files_local(repo, pack, agents=None) -> ChannelResult` (statuses `ok|unavailable`); `detect_history_local(repo, pack, agents=None, *, limit=100) -> dict[str, ChannelResult]` keyed `author|commit_trailer|bot` with the same `stats` keys as `channels.detect_history` (`commits`, `ai_oids`, `human_oids`, `committed_at`). Tasks 4 and 7 consume both.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_detect_local_channels.py` (reuse the `PACK` definition shape from `tests/unit/test_detect_channels.py:11-29`):

```python
from __future__ import annotations

from pathlib import Path

from detect.gitio import GitError, GitRepo
from detect.local_channels import detect_files_local, detect_history_local
from detect.packs import Pack, Pattern

PACK = Pack(
    version="v1",
    agents={
        "Claude Code": "https://claude.com",
        "Cursor": "https://cursor.com",
        "Generic": "https://agents.md",
    },
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"), Pattern("cursoragent", "Cursor")),
    files=(
        Pattern(r"CLAUDE\.md", "Claude Code"),
        Pattern(r"\.cursor/", "Cursor"),
        Pattern(r"AGENTS\.md", "Generic"),
    ),
    branches=(Pattern("claude/", "Claude Code"), Pattern("cursor/", "Cursor")),
    labels=(Pattern("ai-generated", "Claude Code"),),
    bots=(Pattern(r"dependabot\[bot\]", "dependabot"),),
    generic_weights={"AGENTS.md": 0.3},
    exclusions=frozenset({"CONVENTIONS.md"}),
)


class FakeRepo(GitRepo):
    def __init__(self, handler):
        super().__init__(Path("."))
        self._handler = handler

    def git(self, *args: str) -> str:
        result = self._handler(args)
        if result is None:
            raise GitError(list(args), 128, "fake")
        return result


def _tree(handler_args_value: str):
    def handler(args):
        if args[0] == "ls-tree":
            return handler_args_value
        return None

    return handler


def test_detect_files_local_matches_tree_gitignore_and_probes_content():
    files = ["CLAUDE.md", ".cursor/rules/x.md", "AGENTS.md", "CONVENTIONS.md"]
    blobs = {".gitignore": ".cursor/\n# comment\n", "CLAUDE.md": "# guidance\n"}

    def handler(args):
        if args[0] == "ls-tree":
            return "".join(f"{path}\n" for path in files)
        if args[0] == "show":
            return blobs.get(args[1][5:])
        return None

    result = detect_files_local(FakeRepo(handler), PACK)
    assert result.status == "ok"
    by_key = {(h.agent, h.evidence["path"]): h for h in result.hits}
    assert ("Claude Code", "CLAUDE.md") in by_key
    assert ("Cursor", ".cursor/rules/x.md") in by_key
    assert ("Generic", "AGENTS.md") in by_key
    assert ("Claude Code", "CONVENTIONS.md") not in by_key
    assert ("Cursor", ".cursor/") in by_key
    assert by_key[("Cursor", ".cursor/")].evidence["source"] == "gitignore"
    assert by_key[("Claude Code", "CLAUDE.md")].evidence["size"] == len("# guidance\n")
    assert by_key[("Claude Code", "CLAUDE.md")].evidence["empty"] is False


def test_detect_files_local_reports_empty_repository():
    result = detect_files_local(FakeRepo(lambda args: None if args[0] == "ls-tree" else ""), PACK)
    assert result.status == "unavailable"


_LOGGED = (
    "a1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
    "\x1f2026-01-02T03:04:05+00:00\x1ffeat: work\n\nCo-authored-by: Claude <noreply@anthropic.com>\x1e"
    "\na2\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
    "\x1f2026-01-03T00:00:00+00:00\x1ffeat: claude commit\x1e"
    "\na3\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
    "\x1f2026-01-04T00:00:00+00:00\x1fMerge pull request #5 from octo/claude/x\x1e"
    "\na4\x1fdependabot[bot]\x1f49699333+dependabot[bot]@users.noreply.github.com"
    "\x1fdependabot[bot]\x1f49699333+dependabot[bot]@users.noreply.github.com"
    "\x1f2026-01-05T00:00:00+00:00\x1fchore(deps): bump serde\x1e"
)


def test_detect_history_local_author_trailer_bot_and_stats():
    repo = FakeRepo(lambda args: _LOGGED if args[0] == "log" else None)
    results = detect_history_local(repo, PACK, limit=100)
    author, trailer, bot = results["author"], results["commit_trailer"], results["bot"]
    assert {h.evidence["commit"] for h in author.hits} == {"a1", "a2"}
    assert trailer.hits and trailer.hits[0].evidence["commit"] == "a1"
    assert {h.agent for h in bot.hits} == {"dependabot"}
    stats = author.stats
    assert stats["commits"] == 2  # a1, a2 — a3 is noise, a4 is a bot
    assert set(stats["ai_oids"]) == {"a1", "a2"}
    assert stats["human_oids"] == ()
    assert stats["committed_at"]["a2"] == "2026-01-03T00:00:00+00:00"


def test_detect_history_local_empty_repository():
    repo = FakeRepo(lambda args: None if args[0] == "log" else "")
    results = detect_history_local(repo, PACK)
    assert all(result.status == "unavailable" for result in results.values())
```

Check against `attribution.py` semantics while implementing: `match_author_identities` matches `login`/`name`/`email`; `stats["commits"]` in `channels.detect_history` counts non-noise, non-bot commits; the noise filter runs on the message subject.

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_local_channels.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'detect.local_channels'`

- [ ] **Step 3: Write the implementation**

Create `src/detect/local_channels.py`:

```python
from __future__ import annotations

import re

from detect.attribution import (
    Hit,
    dedupe_hits,
    is_noise_commit,
    match_author_identities,
    match_bots,
    match_commit_messages,
    match_files,
)
from detect.channels import ChannelResult
from detect.gitio import CommitRecord, GitError, GitRepo, list_tree, read_blob, read_log
from detect.packs import Pack
from enrich.trees_first import FilePresence

CONTENT_PROBE_LIMIT = 5
_NOREPLY = re.compile(r"^(?:\d+\+)?(?P<login>[^@+]+)@users\.noreply\.github\.com$")


def _login_from_email(email: str) -> str:
    match = _NOREPLY.match(email or "")
    return match.group("login") if match else ""


def _person(record: CommitRecord, name: str, email: str) -> dict[str, str]:
    return {"login": _login_from_email(email), "name": name, "email": email, "commit": record.sha}


def _entries(record: CommitRecord) -> tuple[dict[str, str], dict[str, str]]:
    return (
        _person(record, record.author_name, record.author_email),
        _person(record, record.committer_name, record.committer_email),
    )


def detect_files_local(
    repo: GitRepo, pack: Pack, agents: frozenset[str] | None = None
) -> ChannelResult:
    try:
        paths = list_tree(repo)
    except GitError:
        return ChannelResult(status="unavailable", note="empty repository")
    presence = FilePresence(
        repo_full_name="", paths=frozenset(paths), truncated=False, source="tree"
    )
    hits = list(match_files(pack, presence, agents))
    ignore_text = read_blob(repo, ".gitignore")
    if ignore_text:
        ignored = tuple(
            line.strip()
            for line in ignore_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        if ignored:
            hits.extend(
                match_files(
                    pack,
                    FilePresence("", frozenset(ignored), False, "gitignore"),
                    agents,
                )
            )
    hits = dedupe_hits(hits)
    probe_paths = sorted(
        {hit.evidence["path"] for hit in hits if hit.evidence.get("source") == "tree"}
    )[:CONTENT_PROBE_LIMIT]
    for path in probe_paths:
        text = read_blob(repo, path)
        if text is None:
            continue
        for hit in hits:
            if hit.evidence.get("path") == path:
                hit.evidence.update({"size": len(text), "empty": not text.strip()})
    return ChannelResult(hits=tuple(hits), status="ok", note="local clone; tree + .gitignore")


def detect_history_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    limit: int = 100,
) -> dict[str, ChannelResult]:
    keys = ("author", "commit_trailer", "bot")
    try:
        records = read_log(repo, limit=limit)
    except GitError:
        return {key: ChannelResult(status="unavailable", note="empty repository") for key in keys}
    identities: list[dict[str, str]] = []
    bot_candidates: list[dict[str, str]] = []
    messages: list[tuple[str, str]] = []
    committed_at: dict[str, str] = {}
    for record in records:
        author_entry, committer_entry = _entries(record)
        bot_candidates.extend((author_entry, committer_entry))
        if record.committed_at:
            committed_at[record.sha] = record.committed_at
        if is_noise_commit(record.message):
            continue
        messages.append((record.sha, record.message))
        identities.extend((author_entry, committer_entry))
    author_hits = match_author_identities(pack, identities, agents)
    trailer_hits = match_commit_messages(pack, messages, agents)
    bot_hits = match_bots(pack, bot_candidates, agents)
    ai_oids = {hit.evidence.get("commit") for hit in (*author_hits, *trailer_hits)}
    bot_oids = {hit.evidence.get("commit") for hit in bot_hits}
    commit_oids = {sha for sha, _ in messages} - bot_oids
    human_oids = commit_oids - ai_oids
    stats: dict[str, object] = {
        "commits": len(commit_oids),
        "ai_oids": tuple(sorted(str(oid) for oid in ai_oids if oid)),
        "human_oids": tuple(sorted(str(oid) for oid in human_oids if oid)),
        "committed_at": committed_at,
    }
    note = f"window: last {limit} commits"
    return {
        "author": ChannelResult(hits=tuple(author_hits), status="ok", note=note, stats=stats),
        "commit_trailer": ChannelResult(
            hits=tuple(trailer_hits), status="ok", note=note, stats=stats
        ),
        "bot": ChannelResult(
            hits=tuple(bot_hits),
            status="ok",
            note="generic bot evidence only (QA; never counted as adoption)",
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_local_channels.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/detect/local_channels.py tests/unit/test_detect_local_channels.py
git commit -m "feat(detect): add local file and history channels"
```

---

## Task 4: Local PR-commit and branch channels

**Files:**
- Modify: `src/detect/local_channels.py`
- Test: `tests/unit/test_detect_local_channels.py`

**Interfaces:**
- Consumes: Task 2 (`fetch_pr_refs`, `list_pr_refs`, `walk_pr_shas`, `read_commits`, `parse_merge_branches`), Task 3 (`_entries`), `detect.attribution.match_branches`.
- Produces: `detect_pr_commits_local(repo, pack, agents=None, *, depth=100) -> ChannelResult` (channel `pr_metadata`, hits `{"pr": n, "commit": sha, "propagated": True}`, stats `{"propagated_oids", "commenter_entries": (), "created_at": {}}` — shaped so `orchestrator._ratio_sets` and `_first_signal_at` work unmodified); `detect_branch_local(repo, pack, agents=None, *, limit=100) -> ChannelResult` (channel `branch`, hits `{"pr": n | null, "head": name, "match": pattern}`). Tasks 7 consumes both.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_detect_local_channels.py`:

```python
from detect.local_channels import detect_branch_local, detect_pr_commits_local

_PR_LOG = (
    "s1\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
    "\x1f2026-02-01T00:00:00+00:00\x1ffeat: pr work\x1e"
    "\ns2\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
    "\x1f2026-02-02T00:00:00+00:00\x1fhuman work\x1e"
)


def test_detect_pr_commits_local_maps_commits_to_prs_and_dedupes():
    def handler(args):
        if args[0] == "fetch":
            return ""
        if args[0] == "for-each-ref":
            return "refs/gc/pr/7 aaa\nrefs/gc/pr/9 bbb\n"
        if args[0] == "rev-list":
            return {"aaa": "s1\ns2\n", "bbb": "s2\n"}[args[3]]
        if args[0] == "show":
            return _PR_LOG
        return None

    result = detect_pr_commits_local(FakeRepo(handler), PACK, depth=100)
    assert result.status == "ok"
    assert {(h.evidence["pr"], h.evidence["commit"]) for h in result.hits} == {(7, "s1")}
    assert all(h.evidence["propagated"] is True for h in result.hits)
    assert result.stats["propagated_oids"] == ("s1",)
    assert result.stats["created_at"] == {}


def test_detect_pr_commits_local_without_refs_is_ok():
    repo = FakeRepo(lambda args: "" if args[0] == "fetch" else "")
    result = detect_pr_commits_local(repo, PACK)
    assert result.status == "ok"
    assert result.hits == ()
    assert result.stats["propagated_oids"] == ()


def test_detect_branch_local_parses_merge_messages():
    log = (
        "m1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-03-01T00:00:00+00:00\x1fMerge pull request #123 from octo/claude/fix\x1e"
        "\nm2\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-03-02T00:00:00+00:00\x1fMerge pull request #9 from fork/cursor/tool\x1e"
        "\nm3\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-03-03T00:00:00+00:00\x1ffeat: normal\x1e"
    )
    repo = FakeRepo(lambda args: log if args[0] == "log" else None)
    result = detect_branch_local(repo, PACK, limit=100)
    assert {(h.evidence["pr"], h.evidence["head"]) for h in result.hits} == {
        (123, "claude/fix"),
        (9, "cursor/tool"),
    }
    assert {h.agent for h in result.hits} == {"Claude Code", "Cursor"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_local_channels.py -q`
Expected: FAIL — `ImportError: cannot import name 'detect_pr_commits_local'`

- [ ] **Step 3: Write the implementation**

Append to `src/detect/local_channels.py` (add `match_branches` to the attribution import block):

```python
def detect_pr_commits_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    depth: int = 100,
) -> ChannelResult:
    empty_stats = {"propagated_oids": (), "commenter_entries": (), "created_at": {}}
    try:
        fetch_pr_refs(repo, depth=depth)
        refs = list_pr_refs(repo)
    except GitError:
        return ChannelResult(status="partial", note="pull refs fetch failed", stats=empty_stats)
    if not refs:
        return ChannelResult(status="ok", note="no pull requests found", stats=empty_stats)
    walks = walk_pr_shas(repo, refs, depth=depth)
    sha_to_pr: dict[str, int] = {}
    for number in sorted(walks):
        for sha in walks[number]:
            sha_to_pr.setdefault(sha, number)
    try:
        records = read_commits(repo, sorted(sha_to_pr))
    except GitError:
        records = {}
    hits: list[Hit] = []
    for sha, number in sorted(sha_to_pr.items(), key=lambda item: (item[1], item[0])):
        record = records.get(sha)
        if record is None:
            continue
        matches = match_author_identities(pack, list(_entries(record)), agents)
        matches += match_commit_messages(pack, [(sha, record.message)], agents)
        for hit in dedupe_hits(matches):
            hits.append(
                Hit(hit.agent, "pr_metadata", {"pr": number, "commit": sha, "propagated": True})
            )
    hits = dedupe_hits(hits)
    propagated = tuple(sorted({hit.evidence["commit"] for hit in hits}))
    return ChannelResult(
        hits=tuple(hits),
        status="ok",
        note=f"local PR refs; depth {depth}",
        stats={**empty_stats, "propagated_oids": propagated},
    )


def detect_branch_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    limit: int = 100,
) -> ChannelResult:
    try:
        records = read_log(repo, limit=limit)
    except GitError:
        return ChannelResult(status="unavailable", note="empty repository")
    pairs = parse_merge_branches((record.sha, record.message) for record in records)
    hits: list[Hit] = []
    for number, head in pairs:
        for hit in match_branches(pack, [head], agents):
            hits.append(
                Hit(
                    hit.agent,
                    "branch",
                    {"pr": number, "head": head, "match": hit.evidence["match"]},
                )
            )
    return ChannelResult(
        hits=tuple(dedupe_hits(hits)),
        status="ok",
        note=f"window: last {limit} commits; merge messages only",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_local_channels.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/detect/local_channels.py tests/unit/test_detect_local_channels.py
git commit -m "feat(detect): add local PR-commit and branch channels"
```

---

## Task 5: Detect spec — `source` and `clone` options

**Files:**
- Modify: `src/detect/orchestrator.py` (`DetectOptions`, ~:29-38)
- Modify: `src/serve/detect_spec.py`
- Test: `tests/contract/test_detect_routes.py` (spec round-trip block at ~:257)

**Interfaces:**
- Consumes: nothing new.
- Produces: `DetectOptions` gains `source: str = "api"`, `clone_depth: int = 100`, `clone_keep: bool = False` (positional defaults keep every existing call valid). `parse_detect_spec` accepts optional `"source"` (`"api"|"git"`, default `"api"`) and optional `"clone": {"depth": int 1..5000 = 100, "keep": bool = false}`; invalid values raise `DetectSpecError` with the messages below. `detect_spec_to_dict` emits both keys. Task 7, 8, 9 consume the fields.

- [ ] **Step 1: Write the failing tests**

Append to `tests/contract/test_detect_routes.py`:

```python
def test_detect_spec_parses_git_source_and_clone_options():
    doc = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file", "label"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
        "source": "git",
        "clone": {"depth": 250, "keep": True},
    }
    spec = parse_detect_spec(doc)
    assert spec.source == "git"
    assert spec.clone_depth == 250
    assert spec.clone_keep is True
    round_tripped = detect_spec_to_dict(spec)
    assert round_tripped["source"] == "git"
    assert round_tripped["clone"] == {"depth": 250, "keep": True}


def test_detect_spec_defaults_to_api_source():
    doc = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    spec = parse_detect_spec(doc)
    assert spec.source == "api"
    assert spec.clone_depth == 100
    assert spec.clone_keep is False
    assert detect_spec_to_dict(spec)["source"] == "api"


def test_detect_spec_rejects_unknown_source_and_bad_clone():
    base = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    with pytest.raises(DetectSpecError) as bad_source:
        parse_detect_spec({**base, "source": "ftp"})
    assert any("source must be" in error for error in bad_source.value.errors)
    with pytest.raises(DetectSpecError) as bad_depth:
        parse_detect_spec({**base, "clone": {"depth": 0}})
    assert any("clone.depth must be" in error for error in bad_depth.value.errors)
    with pytest.raises(DetectSpecError) as bad_keep:
        parse_detect_spec({**base, "clone": {"keep": "yes"}})
    assert any("clone.keep must be" in error for error in bad_keep.value.errors)
```

Ensure `pytest` and `DetectSpecError` are imported at the top of the file (extend the existing import from `serve.detect_spec`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_routes.py -q -k "spec_parses_git or spec_defaults or spec_rejects"`
Expected: FAIL — `AttributeError: 'DetectOptions' object has no attribute 'source'`

- [ ] **Step 3: Write the implementation**

In `src/detect/orchestrator.py`, extend `DetectOptions`:

```python
@dataclass(frozen=True)
class DetectOptions:
    source_run_id: int
    pack_version: str
    agents: frozenset[str] | None
    channels: frozenset[str]
    limit: int | None = None
    windows: Mapping[str, int] = field(
        default_factory=lambda: {"commits": 100, "prs": 100, "issues": 100}
    )
    source: str = "api"
    clone_depth: int = 100
    clone_keep: bool = False
```

In `src/serve/detect_spec.py`, add after the windows block (before `if errors:`):

```python
    source = doc.get("source", "api")
    if source not in ("api", "git"):
        errors.append("source must be 'api' or 'git'")
        source = "api"
    clone_depth = 100
    clone_keep = False
    raw_clone = doc.get("clone")
    if raw_clone is not None:
        if not isinstance(raw_clone, Mapping):
            errors.append("clone must be an object")
        else:
            depth = raw_clone.get("depth", 100)
            if isinstance(depth, int) and not isinstance(depth, bool) and 1 <= depth <= 5000:
                clone_depth = depth
            else:
                errors.append("clone.depth must be an integer between 1 and 5000")
            keep = raw_clone.get("keep", False)
            if isinstance(keep, bool):
                clone_keep = keep
            else:
                errors.append("clone.keep must be true or false")
```

and extend the returned `DetectOptions(...)` with `source=str(source), clone_depth=clone_depth, clone_keep=clone_keep`. In `detect_spec_to_dict`, add:

```python
        "source": spec.source,
        "clone": {"depth": spec.clone_depth, "keep": spec.clone_keep},
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_routes.py tests/unit/test_detect_orchestrator.py -q`
Expected: PASS (the existing round-trip test at ~:257 may need its expected dict updated only if it asserts full equality — it asserts individual keys, so it should pass; fix if it fails)

- [ ] **Step 5: Commit**

```bash
git add src/detect/orchestrator.py src/serve/detect_spec.py tests/contract/test_detect_routes.py
git commit -m "feat(detect): add git source and clone options to the detect spec"
```

---

## Task 6: Cloner detect mode (estimate support)

**Files:**
- Modify: `src/enrich/cloner.py` (`CloneMode`, `MODE_FACTORS`, `MODE_FLAGS` at ~:32-48)
- Test: `tests/unit/test_cloner.py`

**Interfaces:**
- Consumes: `estimate_clone` / `estimate_clone_from_totals` (already in cloner).
- Produces: `CloneMode.DETECT = "detect"`, `MODE_FACTORS[CloneMode.DETECT] = 0.006`, `MODE_FLAGS[CloneMode.DETECT] = ("--depth", "100", "--filter=blob:none", "--no-checkout")` — used by the options-page estimate in Task 9. Factor source: the 30-repo stratified measurement (~4.07 GiB projected against ~693 GiB of full sizes).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_cloner.py` (match its existing import style):

```python
def test_estimate_detect_mode_uses_lean_factor():
    estimate = estimate_clone_from_totals(10, 1_000_000, mode=CloneMode.DETECT)
    assert estimate.estimated_mb == pytest.approx(1_000_000 * 0.006 / 1024)


def test_detect_mode_flags_are_lean():
    assert MODE_FLAGS[CloneMode.DETECT] == (
        "--depth",
        "100",
        "--filter=blob:none",
        "--no-checkout",
    )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_cloner.py -q -k detect`
Expected: FAIL — `AttributeError: DETECT` / `KeyError: <CloneMode.SHALLOW...>`

- [ ] **Step 3: Write the implementation**

In `src/enrich/cloner.py`:

```python
class CloneMode(StrEnum):
    SHALLOW = "shallow"
    FILE_ONLY = "file_only"
    WINDOWED = "windowed"
    DETECT = "detect"


MODE_FACTORS: dict[CloneMode, float] = {
    CloneMode.SHALLOW: 1.0,
    CloneMode.FILE_ONLY: 0.25,
    CloneMode.WINDOWED: 0.5,
    CloneMode.DETECT: 0.006,  # measured on the 2026-10 corpus sample
}

MODE_FLAGS: dict[CloneMode, tuple[str, ...]] = {
    CloneMode.SHALLOW: ("--depth", "1"),
    CloneMode.FILE_ONLY: ("--depth", "1", "--no-checkout"),
    CloneMode.WINDOWED: ("--filter=blob:none", "--no-checkout"),
    CloneMode.DETECT: ("--depth", "100", "--filter=blob:none", "--no-checkout"),
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_cloner.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/enrich/cloner.py tests/unit/test_cloner.py
git commit -m "feat(enrich): add detection clone mode and measured size factor"
```

---

## Task 7: Git orchestrator — `run_git_detection`

**Files:**
- Create: `src/detect/git_orchestrator.py`
- Test: `tests/unit/test_git_orchestrator.py`

**Interfaces:**
- Consumes: Tasks 1–6; `detect.orchestrator` helpers (`_RepoScan`, `_candidates`, `_failed_scan`, `_repo_document`, `_summary`) — same-package imports of these private helpers are intentional and must stay; `enrich.cloner` (`free_disk_mb`, `LOW_DISK_THRESHOLD_MB`); `lib.progress`, `lib.cancellation`; `serve.executor` (`RunPayload`, `RunPayloadItem`); `store.models.DetectionEvidence`.
- Produces: `LOCAL_CHANNELS = ("file", "author", "branch", "bot", "commit_trailer", "pr_metadata")`; `GitScanConfig(depth=100, keep=False, scan_root="clones", timeout=None, workers=16)`; `run_git_detection(engine, run_id, spec, pack, *, config=None, clone_fn=None, repo_factory=None) -> RunPayload` — the runner branch (Task 8) calls this. `result_summary["source"] == "git"` and `result_summary["skipped_channels"]` are part of the contract (Task 10 renders them).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_git_orchestrator.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import text

from detect.gitio import GitError, GitRepo
from detect.git_orchestrator import GitScanConfig, run_git_detection
from detect.orchestrator import DetectOptions
from detect.packs import Pack, Pattern, freeze_pack
from serve.executor import create_run


class FakeRepo(GitRepo):
    """GitRepo whose git() answers from a canned handler."""

    def __init__(self, handler):
        super().__init__(Path("."))
        self._handler = handler

    def git(self, *args: str) -> str:
        result = self._handler(args)
        if result is None:
            raise GitError(list(args), 128, "fake")
        return result


def happy_handler(args):
    if args[0] == "ls-tree":
        return "CLAUDE.md\n"
    if args[0] == "show":
        return "# guidance\n"
    if args[0] == "log":
        return _LOG
    return None

PACK = Pack(
    version="v1",
    agents={"Claude Code": "https://claude.com"},
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"),),
    files=(Pattern(r"CLAUDE\.md", "Claude Code"),),
    branches=(Pattern("claude/", "Claude Code"),),
    labels=(),
    bots=(),
    generic_weights={},
    exclusions=frozenset(),
)

_LOG = (
    "a1\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
    "\x1f2026-01-02T00:00:00+00:00\x1ffeat: claude work\x1e"
)


def seed_source(engine) -> int:
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO owners (id, login, type) VALUES (1, 'octo', 'User')"))
        connection.execute(
            text(
                "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility)"
                " VALUES (1, 'n1', 'octo/one', 1, 'one', 'public'),"
                " (2, 'n2', 'octo/two', 1, 'two', 'public')"
            )
        )
    source_id = create_run(engine, {"q": "language:rust"}, api_version="2022-11-28")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                " VALUES (:run, 1, 'octo/one', 10), (:run, 2, 'octo/two', 5)"
            ),
            {"run": source_id},
        )
    freeze_pack(engine, PACK)
    return source_id


def make_spec(source_id: int, channels: frozenset[str], **overrides) -> DetectOptions:
    return DetectOptions(
        source_run_id=source_id,
        pack_version="v1",
        agents=None,
        channels=channels,
        source="git",
        **overrides,
    )


def test_run_git_detection_records_evidence_and_summary(clean_db, tmp_path):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )

    def clone(full_name: str, dest: Path) -> None:
        if full_name == "octo/two":
            raise RuntimeError("clone failed")
        dest.mkdir(parents=True, exist_ok=True)

    config = GitScanConfig(depth=100, keep=False, scan_root=str(tmp_path / "clones"), workers=1)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file", "commit_trailer", "branch", "label"})),
        PACK,
        config=config,
        clone_fn=clone,
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )

    assert payload.result_summary["repos_scanned"] == 2
    assert payload.result_summary["repos_unavailable"] == 1
    assert payload.result_summary["source"] == "git"
    assert payload.result_summary["skipped_channels"] == ["label"]
    assert payload.incomplete is True
    assert payload.items[0].detection["agents"] == ["Claude Code"]
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT channel, agent FROM detection_evidence"
                " WHERE run_id = :run ORDER BY channel"
            ),
            {"run": detect_run},
        ).all()
    assert ("file", "Claude Code") in rows
    assert ("commit_trailer", "Claude Code") in rows
    assert not (tmp_path / "clones" / f"detect-{detect_run}").exists()


def test_run_git_detection_keep_retains_scan_dir(clean_db, tmp_path):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    config = GitScanConfig(depth=100, keep=True, scan_root=str(tmp_path / "clones"), workers=1)
    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=config,
        clone_fn=clone,
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )
    assert (tmp_path / "clones" / f"detect-{detect_run}").exists()


def test_run_git_detection_refuses_on_low_disk(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10.0)
    with pytest.raises(RuntimeError, match="low disk"):
        run_git_detection(
            engine,
            detect_run,
            make_spec(source_id, frozenset({"file"})),
            PACK,
            config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_git_orchestrator.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'detect.git_orchestrator'`

- [ ] **Step 3: Write the implementation**

Create `src/detect/git_orchestrator.py`:

```python
from __future__ import annotations

import json
import shutil
from collections.abc import Callable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from detect.attribution import dedupe_hits
from detect.channels import ChannelResult
from detect.gitio import GitRepo, clone_lean
from detect.local_channels import (
    detect_branch_local,
    detect_files_local,
    detect_history_local,
    detect_pr_commits_local,
)
from detect.orchestrator import (
    DetectOptions,
    _RepoScan,  # same-package helper reuse, intentional
    _candidates,
    _failed_scan,
    _repo_document,
    _summary,
)
from detect.packs import Pack
from enrich.cloner import LOW_DISK_THRESHOLD_MB, free_disk_mb
from lib import cancellation, progress
from lib.cancellation import RunCancelled
from serve.executor import RunPayload, RunPayloadItem
from store.models import DetectionEvidence

LOCAL_CHANNELS = (
    "file",
    "author",
    "branch",
    "bot",
    "commit_trailer",
    "pr_metadata",
)
API_ONLY_CHANNELS = ("label", "issue")
_HISTORY_KEYS = ("author", "commit_trailer", "bot")


@dataclass(frozen=True)
class GitScanConfig:
    depth: int = 100
    keep: bool = False
    scan_root: str = "clones"
    timeout: float | None = None
    workers: int = 16


def run_git_detection(
    engine: Engine,
    run_id: int,
    spec: DetectOptions,
    pack: Pack,
    *,
    config: GitScanConfig | None = None,
    clone_fn: Callable[[str, Path], None] | None = None,
    repo_factory: Callable[[Path], GitRepo] | None = None,
) -> RunPayload:
    cfg = config or GitScanConfig()
    free = free_disk_mb(cfg.scan_root)
    if free < LOW_DISK_THRESHOLD_MB:
        raise RuntimeError(
            f"low disk: {free:.0f} MB free under {cfg.scan_root!r};"
            f" reserve {LOW_DISK_THRESHOLD_MB:.0f} MB before a local scan"
        )
    clone_one = clone_fn or (
        lambda full_name, dest: clone_lean(
            full_name, dest, depth=cfg.depth, timeout=cfg.timeout
        )
    )
    make_repo = repo_factory or (lambda dest: GitRepo(dest, timeout=cfg.timeout))
    active = frozenset(channel for channel in spec.channels if channel in LOCAL_CHANNELS)
    skipped = sorted(channel for channel in spec.channels if channel not in LOCAL_CHANNELS)
    candidates = _candidates(engine, spec.source_run_id, spec.limit)
    total = len(candidates)
    run_dir = Path(cfg.scan_root) / f"detect-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    scans: list[_RepoScan] = []
    failures: list[str] = []

    def scan_repo(candidate: Mapping) -> _RepoScan:
        full_name = str(candidate["full_name"])
        dest = run_dir / full_name.replace("/", "__")
        shutil.rmtree(dest, ignore_errors=True)
        clone_one(full_name, dest)
        repo = make_repo(dest)
        results: dict[str, ChannelResult] = {}
        history_stats: Mapping[str, object] = {}
        if "file" in active:
            results["file"] = detect_files_local(repo, pack, spec.agents)
        if set(_HISTORY_KEYS) & active:
            history = detect_history_local(repo, pack, spec.agents, limit=cfg.depth)
            for key in _HISTORY_KEYS:
                if key in active:
                    results[key] = history[key]
            history_stats = history["author"].stats
        pr_result: ChannelResult | None = None
        if "pr_metadata" in active:
            pr_result = detect_pr_commits_local(repo, pack, spec.agents, depth=cfg.depth)
            results["pr_metadata"] = pr_result
        if "branch" in active:
            results["branch"] = detect_branch_local(repo, pack, spec.agents, limit=cfg.depth)
        hits = dedupe_hits([hit for result in results.values() for hit in result.hits])
        return _RepoScan(
            repo_id=int(candidate["repo_id"]),
            full_name=full_name,
            stargazers=candidate["stargazers"],
            hits=hits,
            results=results,
            pr_result=pr_result,
            history_stats=history_stats,
        )

    try:
        with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as pool:
            pending = iter(candidates)
            in_flight: dict[Future, Mapping] = {}
            exhausted = False
            done = 0
            while True:
                while not exhausted and len(in_flight) < max(1, cfg.workers):
                    cancellation.check()
                    candidate = next(pending, None)
                    if candidate is None:
                        exhausted = True
                        break
                    in_flight[pool.submit(scan_repo, candidate)] = candidate
                if not in_flight:
                    break
                future = next(as_completed(in_flight))
                cancellation.check()
                candidate = in_flight.pop(future)
                try:
                    scan = future.result()
                    scan.document = _repo_document(scan)
                except RunCancelled:
                    raise
                except Exception as exc:
                    scan = _failed_scan(candidate, exc)
                    failures.append(f"{scan.full_name}: {scan.document['notes'][0]}")
                scans.append(scan)
                rows = [
                    {
                        "run_id": run_id,
                        "repo_id": scan.repo_id,
                        "agent": hit.agent,
                        "channel": hit.channel,
                        "evidence": hit.evidence,
                        "pack_version": pack.version,
                    }
                    for hit in scan.hits
                ]
                if rows:
                    with engine.begin() as connection:
                        connection.execute(insert(DetectionEvidence), rows)
                if not cfg.keep:
                    shutil.rmtree(run_dir / scan.full_name.replace("/", "__"), ignore_errors=True)
                done += 1
                progress.report("detecting", done, total)
    finally:
        if not cfg.keep:
            shutil.rmtree(run_dir, ignore_errors=True)

    partial = bool(failures) or any(
        result.status in ("partial", "unavailable")
        for scan in scans
        for result in scan.results.values()
    )
    items = [
        RunPayloadItem(
            repo_id=scan.repo_id,
            full_name=scan.full_name,
            stargazers=scan.stargazers,
            detection=scan.document,
        )
        for scan in scans
    ]
    detections = [
        {
            "full_name": scan.full_name,
            "repo_id": scan.repo_id,
            "agent": hit.agent,
            "channel": hit.channel,
            "evidence": json.dumps(hit.evidence, sort_keys=True),
            "pack_version": pack.version,
        }
        for scan in scans
        for hit in scan.hits
    ]
    summary = _summary(scans, spec, pack)
    summary["source"] = "git"
    summary["skipped_channels"] = skipped
    warnings = list(failures)
    if skipped:
        warnings.append(
            f"local scan skipped API-only channels: {', '.join(skipped)}"
        )
    return RunPayload(
        total_count=total,
        items=items,
        incomplete=partial,
        fetched=total,
        warnings=warnings,
        result_summary=summary,
        detections=detections,
        field_stats={
            "clone": {
                "depth": cfg.depth,
                "keep": cfg.keep,
                "scanned": len(scans),
                "failures": len(failures),
            }
        },
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_git_orchestrator.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/detect/git_orchestrator.py tests/unit/test_git_orchestrator.py
git commit -m "feat(detect): add git-first detection orchestrator"
```

---

## Task 8: Runner branch — `source == "git"` skips API deps

**Files:**
- Modify: `src/serve/detect.py` (`build_detect_runner` at ~:38-60)
- Test: `tests/unit/test_detect_runner.py`

**Interfaces:**
- Consumes: Task 7 (`run_git_detection`, `GitScanConfig`), `lib.deadlines.clone_timeout_seconds`, existing `parse_detect_spec` / `load_frozen` / `load_run_settings`.
- Produces: the same `Runner` factory contract (`runner(run_id, spec_doc) -> RunPayload`); git specs are handled without `build_deps`, and resume (which re-submits the stored spec through this same factory) works unchanged.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_detect_runner.py`:

```python
from __future__ import annotations

from detect.packs import Pack, Pattern, freeze_pack
from serve.detect import build_detect_runner
from serve.detect_spec import detect_spec_to_dict
from detect.orchestrator import DetectOptions
from serve.executor import RunPayload

PACK = Pack(
    version="v1",
    agents={"Claude Code": "https://claude.com"},
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"),),
    files=(Pattern(r"CLAUDE\.md", "Claude Code"),),
    branches=(),
    labels=(),
    bots=(),
    generic_weights={},
    exclusions=frozenset(),
)


def test_git_source_runner_never_builds_api_deps(clean_db, monkeypatch):
    engine = clean_db()
    freeze_pack(engine, PACK)
    sentinel = RunPayload(total_count=0, items=[])
    calls: dict[str, bool] = {}

    def fake_git(*args, **kwargs):
        calls["git"] = True
        return sentinel

    def fail_build_deps(*args, **kwargs):
        raise AssertionError("build_deps must not run for git scans")

    monkeypatch.setattr("serve.detect.run_git_detection", fake_git)
    monkeypatch.setattr("serve.runner.build_deps", fail_build_deps)

    spec = DetectOptions(
        source_run_id=1,
        pack_version="v1",
        agents=None,
        channels=frozenset({"file"}),
        source="git",
    )
    runner = build_detect_runner(engine)
    result = runner(1, detect_spec_to_dict(spec))
    assert result is sentinel
    assert calls.get("git") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_runner.py -q`
Expected: FAIL — assertion error: `build_deps` was called (API path taken)

- [ ] **Step 3: Write the implementation**

In `src/serve/detect.py`, first add the imports:

```python
from detect.git_orchestrator import GitScanConfig, run_git_detection
from lib.deadlines import clone_timeout_seconds
```

Then restructure `build_detect_runner` (API path must stay byte-equivalent in behavior):

```python
def build_detect_runner(engine: Engine) -> Runner:
    def runner(run_id: int, spec_doc: dict) -> RunPayload:
        spec = parse_detect_spec(spec_doc)
        settings = load_run_settings(engine)
        pack = load_frozen(engine, spec.pack_version)
        if spec.source == "git":
            return run_git_detection(
                engine,
                run_id,
                spec,
                pack,
                config=GitScanConfig(
                    depth=spec.clone_depth,
                    keep=spec.clone_keep,
                    timeout=clone_timeout_seconds(),
                    workers=min(settings.limiter_max_concurrent, 32),
                ),
            )
        from serve.runner import build_deps

        deps = build_deps(engine, max_concurrent=settings.limiter_max_concurrent)
        try:
            return run_detection(
                deps,
                run_id,
                spec,
                pack,
                config=DetectConfig(
                    deadline_seconds=float(settings.request_deadline_seconds),
                    concurrency=min(settings.limiter_max_concurrent, 32),
                ),
            )
        finally:
            deps.client.close()

    return runner
```

- [ ] **Step 4: Run the test and the existing orchestrator suite**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_runner.py tests/unit/test_detect_orchestrator.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/serve/detect.py tests/unit/test_detect_runner.py
git commit -m "feat(serve): route git-source detections to the local scan"
```

---

## Task 9: Detection-method chooser (API vs local clone), form fields, and size-based estimates

**Files:**
- Modify: `src/serve/detect.py` (`detect_start` form handling at ~:407-429; `detect_estimate_partial` at ~:528-549)
- Modify: `src/serve/templates/detect_options.html` (new chooser section after the `panel-head` block; method-sync JS inside the existing IIFE at the bottom)
- Modify: `src/serve/templates/detect_new.html` (two-method note in the panel head at ~:7)
- Modify: `src/serve/templates/partials/detect_estimate.html`
- Modify: `src/serve/static/app.css` (method cards, estimate table, API-only channel marker)
- Test: `tests/contract/test_detect_routes.py`
- Golden: regenerate `tests/golden/snapshots/runs_run_id_detect.json`, `runs_run_id_detect-estimate.json`, and `detections_new.json`

**Interfaces:**
- Consumes: Task 6 (`CloneMode.DETECT`, `estimate_clone`, `free_disk_mb`), Task 5 (spec fields).
- Produces: the options page renders **both methods** as selectable cards with pros/cons (API default, git new — neither replaces the other); the form posts `source`, `clone_depth`, `clone_keep`; the estimate partial returns **both** estimates (`{"selected", "repos", "api", "git"}`) and renders them side by side with the selected one highlighted, using the corpus's stored repo sizes for the git numbers.

- [ ] **Step 1: Write the failing contract tests**

Append to `tests/contract/test_detect_routes.py`:

```python
def test_options_page_presents_both_detection_methods(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    response = client.get(f"/runs/{source}/detect")
    assert response.status_code == 200
    assert "GitHub API" in response.text
    assert "Local clone (git)" in response.text
    assert "5,000 REST requests + 5,000 GraphQL points per hour" in response.text
    assert "No API quota" in response.text
    assert "99.5% of detected repos" in response.text


def test_estimate_partial_shows_both_methods(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(f"/runs/{source}/detect-estimate?source=git&channels=file&limit=10")
    assert response.status_code == 200
    assert "REST" in response.text
    assert "Local clone (git)" in response.text
    assert "MB of lean clones" in response.text


def test_start_detection_records_git_source_and_clone(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/runs/{source}/detect")
    response = client.post(
        f"/runs/{source}/detect",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "channels": ["file", "commit_trailer"],
            "source": "git",
            "clone_depth": "250",
            "clone_keep": "true",
        },
    )
    assert response.status_code == 303
    with clean.connect() as connection:
        spec = connection.execute(
            text("SELECT filter_spec FROM runs WHERE kind = 'detect' ORDER BY id DESC LIMIT 1")
        ).scalar_one()
    assert spec["source"] == "git"
    assert spec["clone"] == {"depth": 250, "keep": True}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_routes.py -q -k "both_detection_methods or both_methods or git_source_and_clone"`
Expected: FAIL — the chooser copy is not rendered; the estimate shows only the API numbers; the recorded spec lacks `source`/`clone`.

- [ ] **Step 3: Write the implementation**

(a) `src/serve/detect.py` — in `detect_start`, extend the doc built from the form:

```python
        raw_depth = str(form.get("clone_depth") or "").strip()
        clone_depth: int | None = None
        if raw_depth:
            try:
                clone_depth = int(raw_depth)
            except ValueError:
                clone_depth = 0
        doc = {
            "version": 1,
            "kind": "detect",
            "source_run_id": run_id,
            "pack_version": str(form.get("pack_version") or "").strip(),
            "agents": [str(value) for value in form.getlist("agents") if str(value).strip()]
            or None,
            "channels": [str(value) for value in form.getlist("channels") if str(value).strip()],
            "limit": limit,
            "windows": {"commits": 100, "prs": 100, "issues": 100},
            "source": str(form.get("source") or "api").strip(),
            "clone": {
                "depth": clone_depth if clone_depth is not None else 100,
                "keep": form.get("clone_keep") is not None,
            },
        }
```

(b) `detect_estimate_partial` — compute **both** estimates and let the template compare them. Replace the block from `raw_limit = ...` through the final `return templates.TemplateResponse(...)` with:

```python
        raw_limit = request.query_params.get("limit", "").strip()
        candidates = _candidate_count(engine, run_id)
        limit_value = int(raw_limit) if raw_limit.isdigit() and int(raw_limit) > 0 else None
        repos = min(candidates, limit_value) if limit_value is not None else candidates
        settings = load_run_settings(engine)
        api_estimate = estimate(
            repos,
            channels,
            tokens=max(1, len(load_tokens())),
            concurrency=settings.limiter_max_concurrent,
            deadline_seconds=float(settings.request_deadline_seconds),
        )
        clone_estimate = estimate_clone(
            engine,
            run_id,
            limit=repos,
            mode=CloneMode.DETECT,
            disk_free_mb=free_disk_mb("clones"),
        )
        workers = max(1, min(settings.limiter_max_concurrent, 32))
        git_estimate = {
            "repos": clone_estimate.repos,
            "estimated_mb": round(clone_estimate.estimated_mb, 1),
            "free_mb": round(free_disk_mb("clones"), 1),
            "workers": workers,
            "minutes_low": round(clone_estimate.repos * 1.0 / workers / 60, 1),
            "minutes_high": round(clone_estimate.repos * 4.0 / workers / 60, 1),
            "warnings": list(clone_estimate.warnings),
        }
        return templates.TemplateResponse(
            request,
            "partials/detect_estimate.html",
            {
                "selected": (request.query_params.get("source") or "api").strip(),
                "repos": repos,
                "api": api_estimate,
                "git": git_estimate,
            },
        )
```

Add the import `from enrich.cloner import CloneMode, estimate_clone, free_disk_mb`. The git time band uses the measured 1–4 s per repo (clone + reads) from the 2026-10 field tests; the git size comes from the run's stored `size_kb` values, so it scales with the actual corpus size.

(c) `src/serve/templates/detect_options.html` — insert the chooser after the `panel-head` block (~:21) and before the trace-pack section:

```html
    <section class="filter-section" id="detect-method-section">
      <h2>Detection method</h2>
      <p class="muted">Two methods are available per run and produce the same evidence tables — they differ in where the data comes from and what they cost. The API method stays the default; local clone is additive, not a replacement.</p>
      <div class="method-grid">
        <label class="method-card" for="detect-source-api">
          <input type="radio" id="detect-source-api" name="source" value="api" checked>
          <span class="method-title">GitHub API — default</span>
          <ul class="method-pros">
            <li>No downloads and no disk; starts instantly — small corpora finish in seconds.</li>
            <li>The only method that can read the <code>label</code> and <code>issue</code> channels.</li>
          </ul>
          <ul class="method-cons">
            <li>Rate-limited: 5,000 REST requests + 5,000 GraphQL points per hour per account.</li>
            <li>Large corpora are slow (≈13 h for 17.7k repos) and stall when the quota is spent; long runs are fragile to interruptions.</li>
          </ul>
        </label>
        <label class="method-card" for="detect-source-git">
          <input type="radio" id="detect-source-git" name="source" value="git">
          <span class="method-title">Local clone (git) — new</span>
          <ul class="method-pros">
            <li>No API quota and no tokens required — 17.7k repos scan in ≈1 h (measured).</li>
            <li>Same evidence for 6 of 8 channels — 99.5% of detected repos recovered in validation against the API run.</li>
            <li>Clones can be kept for offline re-scans with future packs.</li>
          </ul>
          <ul class="method-cons">
            <li>Downloads ≈4 GB of lean clones for 17.7k repos; peak disk stays under 1 GB because each clone is deleted after its scan (keeping is opt-in).</li>
            <li><code>label</code> and <code>issue</code> are API-only and are recorded as skipped.</li>
            <li>Branch names are recovered only for projects that merge with merge commits (23% measured).</li>
            <li>Needs git installed.</li>
          </ul>
        </label>
      </div>
      <div class="field-grid" id="detect-git-fields">
        <label class="field" for="detect-clone-depth">
          <span class="field-label">Clone depth (last N commits)</span>
          <input class="field-input" id="detect-clone-depth" name="clone_depth" type="number" min="1" max="5000" value="100">
        </label>
        <label class="checkbox"><input type="checkbox" name="clone_keep" value="true"> <span>Keep clones on disk after scanning (off = delete each repo after its scan)</span></label>
      </div>
    </section>
```

(d) `src/serve/templates/detect_options.html` — inside the existing IIFE (before its closing `})();`, ~:160), wire the method sync:

```javascript
  var gitFields = document.getElementById("detect-git-fields");
  var gitRadio = document.getElementById("detect-source-git");
  var apiOnlyValues = { label: true, issue: true };
  function syncMethod() {
    var gitSelected = !!(gitRadio && gitRadio.checked);
    if (gitFields) {
      gitFields.hidden = !gitSelected;
    }
    Array.prototype.forEach.call(
      document.querySelectorAll("#detect-channels input[type=checkbox]"),
      function (input) {
        if (apiOnlyValues[input.value]) {
          input.closest("label").classList.toggle("channel-api-only", gitSelected);
        }
      }
    );
  }
  Array.prototype.forEach.call(
    form ? form.querySelectorAll('input[name="source"]') : [],
    function (radio) {
      radio.addEventListener("change", syncMethod);
    }
  );
  syncMethod();
```

Notes: `label`/`issue` stay checked and submittable in git mode — the server records them as skipped (Task 7); the class only marks them. Toggling `gitFields.hidden` plus the existing `hx-trigger="load, change from:#detect-form"` refreshes the estimate whenever the method changes.

(e) `src/serve/static/app.css` — append (the file uses `--gc-*` tokens):

```css
.method-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 12px 0; }
.method-card {
  border: 1px solid var(--gc-border);
  border-radius: var(--gc-radius);
  padding: 12px 14px;
  cursor: pointer;
  background: var(--gc-surface);
}
.method-card:has(input:checked) { border-color: var(--gc-accent); background: var(--gc-accent-soft); }
.method-title { display: block; font-weight: 600; margin-bottom: 6px; }
.method-pros, .method-cons { margin: 6px 0; padding-left: 18px; font-size: 0.9rem; }
.method-pros li::marker { color: var(--gc-ok); }
.method-cons li::marker { color: var(--gc-down); }
.channel-api-only { opacity: 0.55; }
.estimate-table { width: 100%; border-collapse: collapse; margin: 8px 0; }
.estimate-table th, .estimate-table td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--gc-border); }
.estimate-table tr.estimate-selected { background: var(--gc-accent-soft); }
```

(f) `src/serve/templates/detect_new.html` — replace the panel intro paragraph (~:7) so both methods are visible before the chooser:

```html
    <p class="muted">Two detection methods are available: <strong>GitHub API</strong> (default — no downloads, rate-limited) and <strong>local clone via git</strong> (no API quota; downloads each repo and records the API-only <code>label</code>/<code>issue</code> channels as skipped). Pick one on the next screen. Detection scans a frozen repo list and stores per-repo agent evidence.</p>
```

(g) `src/serve/templates/partials/detect_estimate.html` — replace the whole file:

```html
<div id="detect-estimate">
  <p class="muted">For {{ repos }} repos — the selected method is highlighted; the other stays fully available for any run.</p>
  <table class="estimate-table">
    <thead>
      <tr><th>Method</th><th>Cost</th><th>Time</th><th>Disk</th></tr>
    </thead>
    <tbody>
      <tr class="{% if selected == 'api' %}estimate-selected{% endif %}">
        <td><strong>GitHub API</strong>{% if selected == 'api' %} — selected{% endif %}</td>
        <td>{{ api.rest_calls }} REST + {{ api.graphql_calls }} GraphQL calls</td>
        <td>≈{{ api.hours }} h (quota-bound)</td>
        <td>none</td>
      </tr>
      <tr class="{% if selected == 'git' %}estimate-selected{% endif %}">
        <td><strong>Local clone (git)</strong>{% if selected == 'git' %} — selected{% endif %}</td>
        <td>≈{{ git.estimated_mb }} MB of lean clones ({{ git.free_mb }} MB free)</td>
        <td>≈{{ git.minutes_low }}–{{ git.minutes_high }} min at {{ git.workers }} workers</td>
        <td>&lt;1 GB peak, or ≈{{ git.estimated_mb }} MB kept</td>
      </tr>
    </tbody>
  </table>
  {% if api.deadline_exceeded %}
  <p class="flag warn">The API estimate exceeds the request deadline; an API run would stop partial. Local clone has no deadline constraint.</p>
  {% endif %}
  {% if git.warnings %}
  <p class="flag warn">Local clone: {{ git.warnings | join("; ") }}</p>
  {% endif %}
  <p class="muted">Git time uses the measured 1–4 s per repo (clone + reads); sizes come from the corpus's stored repo sizes.</p>
</div>
```

- [ ] **Step 4: Run the contract tests and regenerate goldens**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_routes.py -q`
Expected: PASS

Run: `$env:PYTHONPATH='src'; $env:UPDATE_GOLDEN='1'; .\.venv\Scripts\python.exe -m pytest tests/golden -q; Remove-Item Env:\UPDATE_GOLDEN`
Then: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/golden -q`
Expected: PASS; `git diff tests/golden/snapshots` shows only the detect options, estimate, and `detections_new` snapshots changed; the OpenAPI pin is unchanged (no new routes).

- [ ] **Step 5: Commit**

```bash
git add src/serve/detect.py src/serve/templates/detect_options.html src/serve/templates/partials/detect_estimate.html tests/contract/test_detect_routes.py tests/golden/snapshots
git commit -m "feat(serve): add local-clone source option and clone estimate"
```

---

## Task 10: Detail page — show the scan source and skipped channels

**Files:**
- Modify: `src/serve/templates/detect_detail.html` (header at ~:11-27)
- Golden: regenerate detect detail snapshot

**Interfaces:**
- Consumes: `result_summary["source"]` / `["skipped_channels"]` (Task 7).
- Produces: rendered provenance — an API-mode run renders `source api`, so existing golden output stays meaningful after regeneration.

- [ ] **Step 1: Extend the existing detail-page test**

In `tests/contract/test_detect_pages.py`, find the existing detect-detail test (the one that seeds a detect run whose `result_summary` is set and asserts the summary cards render). Add one assertion to that existing test — no new test function is needed:

```python
    assert "source api" in response.text
```

- [ ] **Step 2: Run it to verify it fails**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_pages.py -q`
Expected: FAIL — `assert "source api" in response.text` (the placeholder text is not rendered yet)

- [ ] **Step 3: Implement the template change**

In `detect_detail.html`, inside the `run-meta` block (after the `run-id` span, ~:21):

```html
      <span id="run-source" data-field="source">source {{ "git (local clone)" if detection.summary.source == "git" else "api" }}</span>
```

And directly under `{% include "partials/detect_status.html" %}` (~:16):

```html
  {% if detection.summary.skipped_channels %}
  <p class="flag warn">Local-clone scan skipped API-only channels: {{ detection.summary.skipped_channels | join(", ") }}.</p>
  {% endif %}
```

- [ ] **Step 4: Run tests and regenerate goldens**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_pages.py -q`
Then: `$env:PYTHONPATH='src'; $env:UPDATE_GOLDEN='1'; .\.venv\Scripts\python.exe -m pytest tests/golden -q; Remove-Item Env:\UPDATE_GOLDEN`
Then: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/golden -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/serve/templates/detect_detail.html tests/contract/test_detect_pages.py tests/golden/snapshots
git commit -m "feat(serve): show scan source and skipped channels on detection pages"
```

---

## Task 11: Docs, full verification, and handoff

**Files:**
- Modify: `README.md`, `docs/development-log.md`, `design/detection-pipeline.md`

**Interfaces:**
- Consumes: everything above.
- Produces: documented, verified feature.

- [ ] **Step 1: Documentation updates**

- `README.md`: in the detection section, add a short paragraph: **two selectable methods per run** — GitHub API (default, unchanged; rate-limited) and local clone (`source: "git"`: lean clone `--depth=N --filter=blob:none`, one PR-refs fetch, local matching). The options page presents both with pros/cons and a size-based estimate for each (API calls/hours; clone MB/minutes for the selected top-N). Git mode uses zero API calls, deletes clones after scanning by default, and records `label`/`issue` as skipped (~1 h / ~4 GB for the 17.7k corpus).
- `docs/development-log.md`: append a dated entry (2026-10-15) listing tasks T1–T11, the measured numbers (98.6% rows / 99.5% repos / 100% PR commits / 23% branch), and the tests added.
- `design/detection-pipeline.md` — under "Where to go next", append:
  `- Build it: \`docs/superpowers/plans/2026-10-15-git-first-detection.md\` (T1–T11; tests-first, each task independently reviewable).`

- [ ] **Step 2: Full verification run**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (with `TEST_DATABASE_URL` set), coverage ≥ 93.

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m ruff check src tests; .\.venv\Scripts\python.exe -m black --check src tests`
Expected: clean.

- [ ] **Step 3: Optional live smoke (manual, one repo)**

```powershell
$env:PYTHONPATH='src'
.\.venv\Scripts\python.exe -c "from detect.gitio import clone_lean, GitRepo, list_tree, read_log; import tempfile, pathlib, shutil
root = pathlib.Path(tempfile.mkdtemp()); dest = root / 'r'
clone_lean('serde-rs/serde', dest, depth=100, timeout=300)
print(len(list_tree(GitRepo(dest))), 'paths')
print(len(read_log(GitRepo(dest), limit=100)), 'commits')
shutil.rmtree(root, ignore_errors=True)"
```

Expected: prints path and commit counts; verifies the two git commands against a real repo (no token needed).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/development-log.md design/detection-pipeline.md
git commit -m "docs: document git-first detection scan"
```

---

## Self-review notes (already applied)

- **Spec coverage:** spec stages 0–8 map to T5 (inputs/spec), T1 (clone), T3 (tree/history), T2+T4 (PR refs, branch recovery), T3/T4 (shared matchers — attribution untouched), T7 (rollup/store/delete), T8 (runner/executor seams), T9/T10 (UI), T11 (docs). Failure list (gone repos, empty repos, giant repos, long PRs, squash branch names, labels/comments) is implemented in T7/T3 and surfaced in T9/T10.
- **Type consistency:** `GitRepo.git`, `CommitRecord` field order, `ChannelResult` shapes, `GitScanConfig` field names, `run_git_detection` signature, `result_summary["source"]/["skipped_channels"]`, spec keys `source`/`clone.depth`/`clone.keep` are used consistently across tasks.
- **Known follow-ups (out of scope):** deeper PR-ref depths per straggler; classic "download" flow for the options page; BQ-tier history.
