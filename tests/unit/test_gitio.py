from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import BinaryIO

import pytest

from detect import gitio
from detect.gitio import (
    GitError,
    GitRepo,
    clone_lean,
    fetch_blobs,
    fetch_pr_refs,
    git_error_tail,
    list_pr_refs,
    list_tree,
    list_tree_entries,
    parse_log,
    parse_merge_branches,
    read_blob,
    read_commits,
    read_log,
    remote_pr_refs,
    retry_call,
    run_git,
    walk_pr_shas,
)
from lib import cancellation
from lib.cancellation import RunCancelled

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


class FakeRepo(GitRepo):
    """GitRepo whose git() answers from a canned handler."""

    def __init__(self, handler):
        super().__init__(Path())
        self._handler = handler
        self.calls: list[tuple[str, ...]] = []
        self.timeouts: list[float | None] = []
        self.stdins: list[bytes | None] = []

    def git(self, *args: str, timeout: float | None = None, stdin: BinaryIO | None = None) -> str:
        self.calls.append(args)
        self.timeouts.append(timeout)
        self.stdins.append(stdin.read() if stdin is not None else None)
        result = self._handler(args)
        if result is None:
            raise GitError(list(args), 128, "fake: unknown command")
        return result


class FakeProcess:
    """Narrow Popen double that records kill/reap for the cancellation test."""

    def __init__(self):
        self.returncode = None
        self.killed = False
        self.reaped = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def communicate(self, timeout=None):
        self.reaped = True
        return "", ""


def test_parse_log_splits_records_and_keeps_multiline_messages():
    output = (
        "abc123\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-01-02T03:04:05+00:00"
        "\x1ffeat: add\n\nCo-authored-by: Claude <noreply@anthropic.com>\x1e"
        "\ndef456\x1fBot\x1fbot@example.com\x1fBot\x1fbot@example.com"
        "\x1f2026-01-03T00:00:00+00:00\x1fchore: bump\x1e"
    )
    records = parse_log(output)
    assert [r.sha for r in records] == ["abc123", "def456"]
    assert records[0].author_email == "jane@example.com"
    assert "Co-authored-by: Claude" in records[0].message


_LS_TREE_OUTPUT = (
    "100644 blob aaa111\tCLAUDE.md\n"
    "100644 blob bbb222\tsrc/main.rs\n"
    "160000 commit ccc333\tvendor/lib\n"
)


def test_list_tree_returns_paths():
    fake = FakeRepo(lambda args: _LS_TREE_OUTPUT if args[0] == "ls-tree" else None)
    assert list_tree(fake) == ("CLAUDE.md", "src/main.rs", "vendor/lib")


def test_list_tree_entries_parses_paths_and_oids():
    fake = FakeRepo(lambda args: _LS_TREE_OUTPUT if args[0] == "ls-tree" else None)
    assert list_tree_entries(fake) == (
        ("CLAUDE.md", "aaa111"),
        ("src/main.rs", "bbb222"),
        ("vendor/lib", "ccc333"),
    )


def test_read_blob_returns_none_when_git_fails():
    fake = FakeRepo(lambda args: None)
    assert read_blob(fake, ".gitignore") is None


def test_read_log_uses_limit_and_parses():
    line = (
        "a1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-01-01T00:00:00+00:00\x1ffeat\x1e"
    )
    fake = FakeRepo(lambda args: line if args[0] == "log" else None)
    records = read_log(fake, limit=100)
    assert fake.calls[0] == (
        "log",
        "-n",
        "100",
        "--format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%cI%x1f%B%x1e",
        "HEAD",
    )
    assert records[0].sha == "a1"


def test_git_env_disables_maintenance_and_optional_locks():
    env = gitio.git_env()
    assert env["GIT_OPTIONAL_LOCKS"] == "0"
    assert env["GIT_CONFIG_COUNT"] == "2"
    assert env["GIT_CONFIG_KEY_0"] == "gc.auto"
    assert env["GIT_CONFIG_VALUE_0"] == "0"
    assert env["GIT_CONFIG_KEY_1"] == "maintenance.auto"
    assert env["GIT_CONFIG_VALUE_1"] == "false"


def test_clone_lean_uses_depth_and_blob_filter(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    monkeypatch.setattr(gitio, "run_git", lambda argv, **kw: calls.append(list(argv)) or "")
    clone_lean("octo/repo", tmp_path / "r", depth=150, timeout=5)
    argv = calls[0]
    assert "--depth=150" in argv
    assert "--filter=blob:none" in argv
    assert "--no-checkout" in argv
    assert "--no-tags" in argv
    assert argv[-2:] == ["https://github.com/octo/repo.git", str(tmp_path / "r")]


def test_clone_lean_resolves_a_relative_destination_before_running_git(tmp_path, monkeypatch):
    calls: list[tuple[list[str], dict]] = []
    monkeypatch.setattr(gitio, "run_git", lambda argv, **kw: calls.append((list(argv), kw)) or "")
    monkeypatch.chdir(tmp_path)
    relative = "clones/detect-1/octo__repo"
    clone_lean("octo/repo", Path(relative), depth=1)
    argv, kwargs = calls[0]
    resolved = str(tmp_path / "clones" / "detect-1" / "octo__repo")
    assert argv[-1] == resolved
    assert Path(kwargs["cwd"]) == tmp_path / "clones" / "detect-1"


@needs_git
def test_clone_lean_clones_into_the_requested_relative_destination(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", str(origin)], check=True)
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    relative = "clones/detect-1/octo__repo"
    dest = Path(relative)
    clone_lean("octo/repo", dest, depth=1, url=origin.as_uri())
    assert (work / dest / ".git").is_dir()
    assert not (work / "clones" / "detect-1" / "clones").exists()


def test_retry_call_retries_with_exponential_jittered_delays():
    attempts: list[int] = []
    sleeps: list[float] = []

    def flaky() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise GitError(["git", "clone"], 128, "boom")
        return "ok"

    result = retry_call(flaky, attempts=3, base_delay=2.0, sleep=sleeps.append, jitter=lambda: 0.0)
    assert result == "ok"
    assert len(attempts) == 3
    assert sleeps == [2.0, 4.0]


def test_retry_call_retries_timeouts():
    calls: list[int] = []
    sleeps: list[float] = []

    def stalling() -> str:
        calls.append(1)
        if len(calls) < 3:
            raise subprocess.TimeoutExpired(["git", "fetch"], timeout=600)
        return "ok"

    result = retry_call(
        stalling, attempts=3, base_delay=1.0, sleep=sleeps.append, jitter=lambda: 0.0
    )
    assert result == "ok"
    assert len(calls) == 3
    assert sleeps == [1.0, 2.0]


def test_retry_call_backoff_is_interruptible_by_cancellation():
    cancelled = threading.Event()
    calls: list[int] = []

    def failing() -> str:
        calls.append(1)
        raise GitError(["git", "fetch"], 128, "down")

    token = cancellation.bind(cancelled.is_set)
    timer = threading.Timer(0.1, cancelled.set)
    timer.start()
    started = time.monotonic()
    try:
        with pytest.raises(RunCancelled):
            retry_call(failing, attempts=2, base_delay=5.0)
    finally:
        timer.cancel()
        cancellation.reset(token)
    assert time.monotonic() - started < 4.0


def test_retry_call_raises_the_last_error_after_exhausting_attempts():
    calls: list[int] = []

    def failing() -> str:
        calls.append(1)
        raise GitError(["git", "fetch"], 128, "still down")

    with pytest.raises(GitError, match="still down"):
        retry_call(failing, attempts=2, base_delay=0.0, sleep=lambda _: None, jitter=lambda: 0.0)
    assert len(calls) == 2


def test_retry_call_with_one_attempt_never_sleeps():
    sleeps: list[float] = []

    with pytest.raises(GitError):
        retry_call(
            lambda: (_ for _ in ()).throw(GitError(["git"], 128, "x")),
            attempts=1,
            base_delay=5.0,
            sleep=sleeps.append,
            jitter=lambda: 0.0,
        )
    assert sleeps == []


def test_git_error_tail_prefers_the_last_non_empty_stderr_line():
    exc = GitError(["git", "fetch"], 128, "line one\n\nfatal: could not read from remote\n")
    assert git_error_tail(exc) == "fatal: could not read from remote"


def test_git_error_tail_falls_back_to_str():
    assert git_error_tail(TimeoutError("timed out")) == "timed out"


@needs_git
def test_read_blobs_reads_paths_in_one_batch_with_binary_content(tmp_path):
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
    (repo_dir / "README").write_bytes(b"hello\n")
    (repo_dir / "bin").write_bytes(b"\xff\xfe\x00binary\n")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=repo_dir, check=True, env=env)

    blobs = GitRepo(repo_dir).read_blobs(["README", "bin", "missing.txt"])
    assert blobs["README"] == "hello\n"
    assert "\ufffd" in blobs["bin"]
    assert "binary" in blobs["bin"]
    assert blobs["missing.txt"] is None


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


@needs_git
def test_real_git_round_trips_non_ascii_messages(tmp_path):
    repo_dir = tmp_path / "r"
    repo_dir.mkdir()
    message = "feat: поддержка локали"
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Jane",
        "GIT_AUTHOR_EMAIL": "jane@example.com",
        "GIT_COMMITTER_NAME": "Jane",
        "GIT_COMMITTER_EMAIL": "jane@example.com",
    }
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True, env=env)
    (repo_dir / "README.md").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo_dir, check=True, env=env)

    records = read_log(GitRepo(repo_dir), limit=10)
    assert records[0].message.strip() == message


def test_run_git_kills_child_when_cancelled(tmp_path, monkeypatch):
    process = FakeProcess()
    monkeypatch.setattr(gitio.subprocess, "Popen", lambda *args, **kwargs: process)
    token = cancellation.bind(lambda: True)
    try:
        with pytest.raises(RunCancelled):
            run_git(["fetch", "origin"], cwd=tmp_path)
    finally:
        cancellation.reset(token)
    assert process.killed
    assert process.reaped
    assert process.returncode == -9


_GOOD_REF_FORMAT = "refs/gc/pr/12 aaa\n" "refs/gc/pr/7 bbb\n" "refs/gc/pr/notes ccc\n"


def test_list_pr_refs_parses_numbers_and_skips_non_numeric():
    fake = FakeRepo(lambda args: _GOOD_REF_FORMAT if args[0] == "for-each-ref" else None)
    assert list_pr_refs(fake) == {12: "aaa", 7: "bbb"}


_LS_REMOTE_OUTPUT = "sha1\trefs/pull/7/head\nsha2\trefs/pull/9/head\nsha3\trefs/tags/v1\n"


def test_remote_pr_refs_lists_pr_tips():
    fake = FakeRepo(lambda args: _LS_REMOTE_OUTPUT if args[0] == "ls-remote" else None)
    assert remote_pr_refs(fake) == {7: "sha1", 9: "sha2"}
    assert fake.calls[0] == ("ls-remote", "--refs", "origin", "refs/pull/*/head")
    assert fake.timeouts[0] == gitio._LS_REMOTE_TIMEOUT


def test_fetch_pr_refs_requests_the_ls_remote_snapshot_explicitly():
    def handler(args):
        if args[0] == "ls-remote":
            return _LS_REMOTE_OUTPUT
        return "" if args[0] == "fetch" else None

    fake = FakeRepo(handler)
    fetch_pr_refs(fake, depth=100)
    assert fake.calls[-1] == (
        "fetch",
        "--quiet",
        "--depth",
        "100",
        "--filter=blob:none",
        "--no-tags",
        "origin",
        "+refs/pull/7/head:refs/gc/pr/7",
        "+refs/pull/9/head:refs/gc/pr/9",
    )
    assert fake.timeouts[-1] == gitio._PR_CHUNK_TIMEOUT


def test_fetch_pr_refs_skips_fetch_when_no_pr_refs():
    fake = FakeRepo(lambda args: "" if args[0] == "ls-remote" else None)
    fetch_pr_refs(fake, depth=100)
    assert [call[0] for call in fake.calls] == ["ls-remote"]


def test_fetch_pr_refs_chunks_large_ref_sets(monkeypatch):
    monkeypatch.setattr(gitio, "_PR_FETCH_CHUNK_REFS", 2)
    lines = "".join(f"sha{n}\trefs/pull/{n}/head\n" for n in (1, 2, 3, 4, 5))
    fake = FakeRepo(
        lambda args: lines if args[0] == "ls-remote" else ("" if args[0] == "fetch" else None)
    )
    fetch_pr_refs(fake, depth=100)
    fetches = [call for call in fake.calls if call[0] == "fetch"]
    assert len(fetches) == 3
    assert fetches[0][-2:] == (
        "+refs/pull/1/head:refs/gc/pr/1",
        "+refs/pull/2/head:refs/gc/pr/2",
    )
    assert fetches[1][-2:] == (
        "+refs/pull/3/head:refs/gc/pr/3",
        "+refs/pull/4/head:refs/gc/pr/4",
    )
    assert fetches[2][-1:] == ("+refs/pull/5/head:refs/gc/pr/5",)
    assert all("--depth" in call and "--filter=blob:none" in call for call in fetches)


def test_fetch_blobs_batches_objects_into_one_stdin_fetch():
    fake = FakeRepo(lambda args: "")
    fetch_blobs(fake, ["blob1", "blob2"])
    assert fake.calls == [
        (
            "-c",
            "fetch.negotiationAlgorithm=noop",
            "fetch",
            "origin",
            "--no-tags",
            "--no-write-fetch-head",
            "--recurse-submodules=no",
            "--filter=blob:none",
            "--stdin",
        )
    ]
    assert fake.stdins == [b"blob1\nblob2\n"]
    assert fake.timeouts == [gitio._PR_CHUNK_TIMEOUT]


def test_fetch_blobs_is_a_noop_without_objects():
    fake = FakeRepo(lambda args: None)
    fetch_blobs(fake, [])
    assert fake.calls == []


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


def test_walk_pr_shas_parallel_matches_sequential():
    def handler(args):
        if args[0] == "rev-list":
            return {"a1": "s1\ns2\n", "a2": "s2\n", "a3": "s3\n", "a4": ""}[args[3]]
        return None

    refs = {4: "a4", 1: "a1", 3: "a3", 2: "a2"}
    parallel = FakeRepo(handler)
    sequential = FakeRepo(handler)
    assert walk_pr_shas(parallel, refs, depth=100, workers=4) == walk_pr_shas(
        sequential, refs, depth=100, workers=1
    )
    assert len([call for call in parallel.calls if call[0] == "rev-list"]) == 4


def test_read_log_caches_the_parsed_window_per_repo():
    calls: list[tuple] = []
    line = (
        "a1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-01-01T00:00:00+00:00\x1ffeat\x1e"
    )

    def handler(args):
        calls.append(args)
        return line if args[0] == "log" else None

    fake = FakeRepo(handler)
    first = read_log(fake, limit=100)
    second = read_log(fake, limit=100)
    assert first == second
    assert [call[0] for call in calls] == ["log"]


def test_read_commits_parses_log_no_walk_output():
    def handler(args):
        if args[0] != "log":
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


def test_read_commits_never_uses_show_so_trees_are_not_demanded():
    def handler(args):
        if args[0] == "show":
            raise GitError(list(args), 128, "unexpected show")
        return "".join(
            f"{sha}\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
            f"\x1f2026-01-01T00:00:00+00:00\x1ffeat {sha}\x1e\n"
            for sha in args[3:]
        )

    fake = FakeRepo(handler)
    records = read_commits(fake, ["a"])
    assert set(records) == {"a"}
    assert fake.calls[0][:2] == ("log", "--no-walk")


def test_read_commits_batches_six_hundred_shas_per_log_call():
    batches: list[int] = []

    def handler(args):
        if args[0] != "log":
            return None
        shas = args[3:]
        batches.append(len(shas))
        return "".join(
            f"{sha}\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
            f"\x1f2026-01-01T00:00:00+00:00\x1ffeat {sha}\x1e\n"
            for sha in shas
        )

    fake = FakeRepo(handler)
    shas = [f"{i:040x}" for i in range(601)]
    records = read_commits(fake, shas)
    assert len(records) == 601
    assert batches == [600, 1]


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
