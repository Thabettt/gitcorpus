from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import BinaryIO

import httpx
import pytest

from detect import gitio
from detect.gitio import (
    GitError,
    GitRepo,
    RemoteRefs,
    RemoteRefsUnavailable,
    clone_lean,
    fetch_blobs,
    fetch_pr_refs,
    git_error_tail,
    list_tree,
    list_tree_entries,
    parse_log,
    parse_merge_branches,
    read_blob,
    read_commits,
    read_log,
    read_pr_refs_snapshot,
    remote_pr_refs,
    remote_refs_for,
    resolve_head,
    retry_call,
    run_git,
    run_git_bytes,
    walk_pr_shas,
)
from lib import cancellation
from lib.cancellation import RunCancelled

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


class FakeRepo(GitRepo):
    """GitRepo whose git() answers from a canned handler."""

    def __init__(self, handler, dest: Path | None = None):
        super().__init__(dest or Path())
        self._handler = handler
        self.calls: list[tuple[str, ...]] = []
        self.timeouts: list[float | None] = []
        self.stdins: list[bytes | None] = []
        self.env_extras: list[dict[str, str] | None] = []

    def git(
        self,
        *args: str,
        timeout: float | None = None,
        stdin: BinaryIO | None = None,
        env_extra: dict[str, str] | None = None,
    ) -> str:
        self.calls.append(args)
        self.timeouts.append(timeout)
        self.stdins.append(stdin.read() if stdin is not None else None)
        self.env_extras.append(env_extra)
        result = self._handler(args)
        if result is None:
            raise GitError(list(args), 128, "fake: unknown command")
        return result


class FakeGate:
    """Records acquire/release, timeout polling, and the hold depth seen mid-fetch."""

    def __init__(self, grants: bool = True) -> None:
        self.acquires = 0
        self.releases = 0
        self.held = 0
        self.grants = grants
        self.held_at_fetch: list[int] = []

    def acquire(self, *, timeout: float | None = None) -> bool:
        self.acquires += 1
        if not self.grants:
            return False
        self.held += 1
        return True

    def release(self) -> None:
        self.releases += 1
        self.held -= 1


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
    assert fake.env_extras == [None]


def test_read_blobs_batch_disables_lazy_fetch(monkeypatch, tmp_path):
    captured: dict[str, object] = {}

    def fake_run_git_bytes(argv, **kwargs):
        captured["argv"] = argv
        captured["env_extra"] = kwargs.get("env_extra")
        return b"abc123 blob 6\nhello\n"

    monkeypatch.setattr(gitio, "run_git_bytes", fake_run_git_bytes)
    assert GitRepo(tmp_path).read_blobs(["README"]) == {"README": "hello\n"}
    assert captured["argv"] == ["cat-file", "--batch"]
    assert captured["env_extra"] == {"GIT_NO_LAZY_FETCH": "1"}


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


def _basic_auth_header(token: str) -> str:
    payload = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    return f"Authorization: Basic {payload}"


def test_git_env_disables_maintenance_and_optional_locks(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKENS", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    env = gitio.git_env()
    assert env["GIT_OPTIONAL_LOCKS"] == "0"
    assert env["GIT_CONFIG_COUNT"] == "2"
    assert env["GIT_CONFIG_KEY_0"] == "gc.auto"
    assert env["GIT_CONFIG_VALUE_0"] == "0"
    assert env["GIT_CONFIG_KEY_1"] == "maintenance.auto"
    assert env["GIT_CONFIG_VALUE_1"] == "false"
    assert env["GIT_ASKPASS"] == ""
    assert env["SSH_ASKPASS"] == ""
    assert env["GIT_TERMINAL_PROMPT"] == "0"


def test_git_env_adds_the_first_github_tokens_authorization_header(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKENS", "tok-one, tok-two")
    monkeypatch.setenv("GITHUB_TOKEN", "tok-fallback")
    env = gitio.git_env()
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_2"] == "http.https://github.com/.extraHeader"
    assert env["GIT_CONFIG_VALUE_2"] == _basic_auth_header("tok-one")


def test_git_env_falls_back_to_the_single_github_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKENS", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "tok-single")
    env = gitio.git_env()
    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_2"] == "http.https://github.com/.extraHeader"
    assert env["GIT_CONFIG_VALUE_2"] == _basic_auth_header("tok-single")


def test_git_env_keeps_two_config_entries_and_no_header_without_a_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKENS", raising=False)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    env = gitio.git_env()
    assert env["GIT_CONFIG_COUNT"] == "2"
    assert "GIT_CONFIG_KEY_2" not in env
    assert "GIT_CONFIG_VALUE_2" not in env
    assert not any(
        value.startswith("Authorization: Basic") for key, value in env.items() if "CONFIG" in key
    )


@pytest.fixture
def reset_git_binary(monkeypatch):
    monkeypatch.setattr(gitio, "_GIT_BINARY", None)


def test_git_binary_prefers_an_existing_env_override(tmp_path, monkeypatch, reset_git_binary):
    override = tmp_path / "git.exe"
    override.write_text("", encoding="utf-8")
    monkeypatch.setenv("GITCORPUS_GIT_BIN", str(override))
    monkeypatch.setattr(gitio.shutil, "which", lambda name: "/usr/bin/git")
    assert gitio.git_binary() == str(override)


def test_git_binary_ignores_a_missing_env_override(tmp_path, monkeypatch, reset_git_binary):
    monkeypatch.setenv("GITCORPUS_GIT_BIN", str(tmp_path / "gone" / "git.exe"))
    monkeypatch.setattr(gitio.shutil, "which", lambda name: None)
    assert gitio.git_binary() == "git"


def test_git_binary_prefers_the_mingw64_sibling_over_the_cmd_shim(
    tmp_path, monkeypatch, reset_git_binary
):
    shim = tmp_path / "Git" / "cmd" / "git.exe"
    real = tmp_path / "Git" / "mingw64" / "bin" / "git.exe"
    for path in (shim, real):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    monkeypatch.delenv("GITCORPUS_GIT_BIN", raising=False)
    monkeypatch.setattr(gitio.shutil, "which", lambda name: str(shim))
    assert gitio.git_binary() == str(real)


def test_git_binary_keeps_the_cmd_shim_when_the_sibling_is_missing(
    tmp_path, monkeypatch, reset_git_binary
):
    shim = tmp_path / "Git" / "cmd" / "git.exe"
    shim.parent.mkdir(parents=True)
    shim.write_text("", encoding="utf-8")
    monkeypatch.delenv("GITCORPUS_GIT_BIN", raising=False)
    monkeypatch.setattr(gitio.shutil, "which", lambda name: str(shim))
    assert gitio.git_binary() == str(shim)


def test_git_binary_keeps_a_non_cmd_which_result(monkeypatch, reset_git_binary):
    monkeypatch.delenv("GITCORPUS_GIT_BIN", raising=False)
    monkeypatch.setattr(gitio.shutil, "which", lambda name: "/usr/bin/git")
    assert gitio.git_binary() == "/usr/bin/git"


def test_git_binary_falls_back_to_bare_git(monkeypatch, reset_git_binary):
    monkeypatch.delenv("GITCORPUS_GIT_BIN", raising=False)
    monkeypatch.setattr(gitio.shutil, "which", lambda name: None)
    assert gitio.git_binary() == "git"


def test_git_binary_is_resolved_once_per_process(monkeypatch, reset_git_binary):
    calls: list[str] = []
    monkeypatch.delenv("GITCORPUS_GIT_BIN", raising=False)
    monkeypatch.setattr(gitio.shutil, "which", lambda name: calls.append(name) or None)
    assert gitio.git_binary() == "git"
    assert gitio.git_binary() == "git"
    assert calls == ["git"]


def test_run_git_process_spawns_the_resolved_binary(tmp_path, monkeypatch):
    spawned: list[list[str]] = []

    class RecordingProcess:
        def __init__(self, argv, **kwargs):
            spawned.append([str(part) for part in argv])
            self.returncode = 0

        def poll(self):
            return self.returncode

        def kill(self):
            pass

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr(gitio, "git_binary", lambda: "C:/resolved/mingw64/git.exe")
    monkeypatch.setattr(gitio.subprocess, "Popen", RecordingProcess)
    run_git(["status"], cwd=tmp_path)
    assert spawned == [["C:/resolved/mingw64/git.exe", "status"]]


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


def test_git_error_scrubs_every_configured_token_and_its_base64_payload(monkeypatch):
    token = "ghs_secret_value_123"
    payload = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    monkeypatch.setenv("GITHUB_TOKENS", f"{token}, other-token")
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    exc = GitError(["git", "fetch"], 128, f"fatal: bad credentials {token}\nheader {payload}\n")
    assert token not in str(exc)
    assert token not in exc.stderr
    assert payload not in str(exc)
    assert payload not in exc.stderr
    assert str(exc).count("<redacted>") == 2


def test_git_error_scrubs_the_single_github_token(monkeypatch):
    token = "ghp_single_secret_456"
    payload = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    monkeypatch.delenv("GITHUB_TOKENS", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", token)
    exc = GitError(["git", "fetch"], 128, f"error: rejected {token} via {payload}")
    assert token not in str(exc)
    assert payload not in str(exc)
    assert "<redacted>" in str(exc)


def test_git_error_tail_scrubs_git_error_output(monkeypatch):
    token = "ghs_tail_secret_789"
    payload = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    monkeypatch.setenv("GITHUB_TOKENS", token)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    exc = GitError(["git", "fetch"], 128, f"line one\n\nfatal: auth {token} {payload}\n")
    tail = git_error_tail(exc)
    assert token not in tail
    assert payload not in tail
    assert "<redacted>" in tail


def test_git_error_tail_scrubs_non_git_error_output(monkeypatch):
    token = "ghp_tail_fallback_987"
    monkeypatch.setenv("GITHUB_TOKEN", token)
    monkeypatch.delenv("GITHUB_TOKENS", raising=False)

    class Coded(Exception):
        stderr = f"fatal: {token} rejected"

    assert token not in git_error_tail(Coded())
    assert token not in git_error_tail(RuntimeError(f"failed with {token}"))


def test_scrub_secrets_leaves_clean_text_untouched(monkeypatch):
    text = "fatal: could not read from remote repository\nplumbing e0110bad\n"
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_clean_text_000")
    monkeypatch.delenv("GITHUB_TOKENS", raising=False)
    assert gitio._scrub_secrets(text) == text
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    assert gitio._scrub_secrets(text) == text


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


def test_env_extra_reaches_every_git_entry_point_without_leaking(tmp_path, monkeypatch):
    created: list[dict] = []

    class RecordingProcess:
        def __init__(self, argv, **kwargs):
            created.append(kwargs)
            self.returncode = 0

        def poll(self):
            return self.returncode

        def kill(self):
            pass

        def communicate(self, timeout=None):
            return "", ""

    monkeypatch.setattr(gitio.subprocess, "Popen", RecordingProcess)
    monkeypatch.delenv("GIT_NO_LAZY_FETCH", raising=False)
    run_git(["status"], cwd=tmp_path, env_extra={"GIT_NO_LAZY_FETCH": "1"})
    run_git_bytes(["status"], cwd=tmp_path, env_extra={"GIT_NO_LAZY_FETCH": "1"})
    GitRepo(tmp_path).git("status", env_extra={"GIT_NO_LAZY_FETCH": "1"})
    assert [call["env"]["GIT_NO_LAZY_FETCH"] for call in created] == ["1", "1", "1"]
    run_git(["status"], cwd=tmp_path)
    assert "GIT_NO_LAZY_FETCH" not in created[-1]["env"]
    assert "GIT_NO_LAZY_FETCH" not in gitio.git_env()
    assert "GIT_NO_LAZY_FETCH" not in os.environ


_LS_REMOTE_OUTPUT = "sha1\trefs/pull/7/head\nsha2\trefs/pull/9/head\nsha3\trefs/tags/v1\n"


def _repo_dir(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_remote_pr_refs_lists_pr_tips():
    fake = FakeRepo(lambda args: _LS_REMOTE_OUTPUT if args[0] == "ls-remote" else None)
    assert remote_pr_refs(fake) == {7: "sha1", 9: "sha2"}
    assert fake.calls[0] == ("remote", "get-url", "origin")
    assert fake.calls[1] == (
        "ls-remote",
        "--refs",
        "origin",
        "refs/pull/*/head",
        "refs/heads/*",
    )
    assert fake.timeouts[1] == gitio._LS_REMOTE_TIMEOUT


def test_fetch_pr_refs_sends_destinationless_refspecs_over_stdin(tmp_path):
    def handler(args):
        if args[0] == "ls-remote":
            return _LS_REMOTE_OUTPUT
        return "" if args[0] == "fetch" else None

    fake = FakeRepo(handler, dest=_repo_dir(tmp_path))
    assert fetch_pr_refs(fake, depth=100) == {7: "sha1", 9: "sha2"}
    assert fake.calls[-1] == (
        "fetch",
        "--quiet",
        "--depth",
        "100",
        "--filter=tree:0",
        "--no-tags",
        "--no-write-fetch-head",
        "--recurse-submodules=no",
        "origin",
        "--stdin",
    )
    assert not any("refs/pull" in part for part in fake.calls[-1])
    assert fake.stdins[-1] == b"refs/pull/7/head\nrefs/pull/9/head\n"
    assert fake.env_extras[-1] == {"GIT_NO_LAZY_FETCH": "1"}
    assert fake.timeouts[-1] == gitio._PR_CHUNK_TIMEOUT


def test_fetch_pr_refs_returns_the_remote_map_and_persists_a_sorted_snapshot(tmp_path):
    fake = FakeRepo(
        lambda args: (
            "s10\trefs/pull/10/head\ns2\trefs/pull/2/head\n" if args[0] == "ls-remote" else ""
        ),
        dest=_repo_dir(tmp_path),
    )
    assert fetch_pr_refs(fake, depth=100) == {2: "s2", 10: "s10"}
    payload = json.loads((tmp_path / ".git" / ".gitcorpus-pr-refs.json").read_text("utf-8"))
    assert payload == {"version": 1, "refs": {"2": "s2", "10": "s10"}}
    assert list(payload["refs"]) == ["2", "10"]
    assert read_pr_refs_snapshot(fake) == {2: "s2", 10: "s10"}


def test_fetch_pr_refs_skips_fetch_and_snapshot_when_no_pr_refs(tmp_path):
    fake = FakeRepo(lambda args: "" if args[0] == "ls-remote" else None, dest=_repo_dir(tmp_path))
    assert fetch_pr_refs(fake, depth=100) == {}
    assert [call[0] for call in fake.calls] == ["remote", "ls-remote"]
    assert not (tmp_path / ".git" / ".gitcorpus-pr-refs.json").exists()


def test_fetch_pr_refs_deletes_the_snapshot_when_the_fresh_listing_is_empty(tmp_path):
    dest = _repo_dir(tmp_path)
    snapshot = tmp_path / ".git" / ".gitcorpus-pr-refs.json"
    seeded = FakeRepo(
        lambda args: "s7\trefs/pull/7/head\n" if args[0] == "ls-remote" else "",
        dest=dest,
    )
    assert fetch_pr_refs(seeded, depth=100) == {7: "s7"}
    assert snapshot.exists()

    emptied = FakeRepo(lambda args: "" if args[0] == "ls-remote" else None, dest=dest)
    assert fetch_pr_refs(emptied, depth=100) == {}
    assert not snapshot.exists()
    assert read_pr_refs_snapshot(emptied) is None


def test_fetch_pr_refs_survives_a_snapshot_write_failure(monkeypatch, tmp_path):
    def handler(args):
        if args[0] == "ls-remote":
            return _LS_REMOTE_OUTPUT
        return "" if args[0] == "fetch" else None

    def failing_write(repo, refs):
        raise OSError("no space left on device")

    monkeypatch.setattr(gitio, "write_pr_refs_snapshot", failing_write)
    fake = FakeRepo(handler, dest=_repo_dir(tmp_path))
    assert fetch_pr_refs(fake, depth=100) == {7: "sha1", 9: "sha2"}
    assert [call[0] for call in fake.calls] == ["remote", "ls-remote", "fetch"]


def test_fetch_pr_refs_chunks_large_ref_sets_over_stdin(monkeypatch, tmp_path):
    assert gitio._PR_FETCH_CHUNK_REFS == 2000
    monkeypatch.setattr(gitio, "_PR_FETCH_CHUNK_REFS", 2)
    lines = "".join(f"sha{n}\trefs/pull/{n}/head\n" for n in (1, 2, 3, 4, 5))
    fake = FakeRepo(
        lambda args: lines if args[0] == "ls-remote" else ("" if args[0] == "fetch" else None),
        dest=_repo_dir(tmp_path),
    )
    fetch_pr_refs(fake, depth=100)
    fetches = [call for call in fake.calls if call[0] == "fetch"]
    assert len(fetches) == 3
    assert fake.stdins[-3:] == [
        b"refs/pull/1/head\nrefs/pull/2/head\n",
        b"refs/pull/3/head\nrefs/pull/4/head\n",
        b"refs/pull/5/head\n",
    ]
    assert all("--filter=tree:0" in call and "--stdin" in call for call in fetches)


def _ls_remote_lines(count: int) -> str:
    return "".join(f"sha{n}\trefs/pull/{n}/head\n" for n in range(1, count + 1))


def test_fetch_pr_refs_leaves_the_gate_alone_at_the_threshold(tmp_path):
    assert gitio._MONSTER_PR_THRESHOLD == 500
    gate = FakeGate()
    fake = FakeRepo(
        lambda args: _ls_remote_lines(500) if args[0] == "ls-remote" else "",
        dest=_repo_dir(tmp_path),
    )
    assert len(fetch_pr_refs(fake, depth=100, gate=gate)) == 500
    assert (gate.acquires, gate.releases) == (0, 0)


def test_fetch_pr_refs_leaves_the_gate_alone_for_ordinary_repos(tmp_path):
    gate = FakeGate()
    fake = FakeRepo(
        lambda args: _LS_REMOTE_OUTPUT if args[0] == "ls-remote" else "",
        dest=_repo_dir(tmp_path),
    )
    fetch_pr_refs(fake, depth=100, gate=gate)
    assert (gate.acquires, gate.releases) == (0, 0)


def test_fetch_pr_refs_gates_monster_ref_sets_across_every_chunk(monkeypatch, tmp_path):
    monkeypatch.setattr(gitio, "_PR_FETCH_CHUNK_REFS", 200)
    gate = FakeGate()

    def handler(args):
        if args[0] == "ls-remote":
            return _ls_remote_lines(501)
        if args[0] == "fetch":
            gate.held_at_fetch.append(gate.held)
            return ""
        return None

    fake = FakeRepo(handler, dest=_repo_dir(tmp_path))
    assert len(fetch_pr_refs(fake, depth=100, gate=gate)) == 501
    assert gate.held_at_fetch == [1, 1, 1]
    assert (gate.acquires, gate.releases) == (3, 3)
    assert gate.held == 0


def test_fetch_pr_refs_releases_the_gate_when_a_chunk_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(gitio, "_PR_FETCH_CHUNK_REFS", 200)
    gate = FakeGate()
    fetches: list[int] = []

    def handler(args):
        if args[0] == "ls-remote":
            return _ls_remote_lines(501)
        if args[0] == "fetch":
            fetches.append(1)
            if len(fetches) == 3:
                raise GitError(list(args), 128, "fatal: connection reset")
            return ""
        return None

    fake = FakeRepo(handler, dest=_repo_dir(tmp_path))
    with pytest.raises(GitError):
        fetch_pr_refs(fake, depth=100, gate=gate)
    assert len(fetches) == 3
    assert (gate.acquires, gate.releases) == (3, 3)
    assert gate.held == 0


def test_fetch_pr_refs_cancellation_while_waiting_for_the_gate_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(gitio, "_PR_FETCH_CHUNK_REFS", 200)
    gate = FakeGate(grants=False)
    fake = FakeRepo(
        lambda args: _ls_remote_lines(501) if args[0] == "ls-remote" else "",
        dest=_repo_dir(tmp_path),
    )
    token = cancellation.bind(lambda: True)
    try:
        with pytest.raises(RunCancelled):
            fetch_pr_refs(fake, depth=100, gate=gate)
    finally:
        cancellation.reset(token)
    assert [call[0] for call in fake.calls] == ["remote", "ls-remote"]
    assert gate.acquires == 1
    assert gate.releases == 0


def test_acquire_gate_polls_the_gate_and_checks_cancellation_between_polls():
    gate = FakeGate(grants=False)
    token = cancellation.bind(lambda: True)
    try:
        with pytest.raises(RunCancelled):
            gitio._acquire_gate(gate)
    finally:
        cancellation.reset(token)
    assert gate.acquires == 1


def test_acquire_gate_non_blocking_makes_one_immediate_attempt():
    gate = FakeGate(grants=False)
    assert gitio._acquire_gate(gate, blocking=False) is False
    assert gate.acquires == 1


def test_fetch_pr_refs_ignores_the_gate_without_pr_refs(tmp_path):
    gate = FakeGate()
    fake = FakeRepo(lambda args: "" if args[0] == "ls-remote" else None, dest=_repo_dir(tmp_path))
    assert fetch_pr_refs(fake, depth=100, gate=gate) == {}
    assert (gate.acquires, gate.releases) == (0, 0)


def test_fetch_pr_refs_fetches_monsters_ungated_without_a_gate(monkeypatch, tmp_path):
    monkeypatch.setattr(gitio, "_PR_FETCH_CHUNK_REFS", 200)
    fake = FakeRepo(
        lambda args: _ls_remote_lines(501) if args[0] == "ls-remote" else "",
        dest=_repo_dir(tmp_path),
    )
    assert len(fetch_pr_refs(fake, depth=100, gate=None)) == 501


def test_read_pr_refs_snapshot_none_when_missing_corrupt_or_unknown(tmp_path):
    fake = FakeRepo(lambda args: None, dest=_repo_dir(tmp_path))
    path = tmp_path / ".git" / ".gitcorpus-pr-refs.json"
    assert read_pr_refs_snapshot(fake) is None
    path.write_text("not json", encoding="utf-8")
    assert read_pr_refs_snapshot(fake) is None
    path.write_text('{"version": 99, "refs": {"7": "abc"}}', encoding="utf-8")
    assert read_pr_refs_snapshot(fake) is None
    path.write_text('{"version": 1, "refs": "nope"}', encoding="utf-8")
    assert read_pr_refs_snapshot(fake) is None
    path.write_text('{"version": 1, "refs": {"7": "abc", "notes": "abc"}}', encoding="utf-8")
    assert read_pr_refs_snapshot(fake) is None
    path.write_text('{"version": 1, "refs": {"7": "abc"}}', encoding="utf-8")
    assert read_pr_refs_snapshot(fake) == {7: "abc"}


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
    assert fake.env_extras == [None]


def test_fetch_blobs_is_a_noop_without_objects():
    fake = FakeRepo(lambda args: None)
    fetch_blobs(fake, [])
    assert fake.calls == []


def test_walk_pr_shas_delegates_to_the_batched_walker(monkeypatch):
    calls: list[tuple] = []

    def fake_walk(repo, refs, *, depth):
        calls.append((repo, dict(refs), depth))
        return {7: ("s1",)}

    monkeypatch.setattr("detect.repo_walk.walk_windows", fake_walk)
    result = walk_pr_shas(FakeRepo(lambda args: None), {7: "aaa"}, depth=5)
    assert result == {7: ("s1",)}
    assert calls and calls[0][2] == 5


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


def _head_git_dir(tmp_path: Path) -> Path:
    git_dir = tmp_path / ".git"
    git_dir.mkdir(parents=True)
    return git_dir


def test_resolve_head_reads_a_detached_head(tmp_path):
    git_dir = _head_git_dir(tmp_path)
    (git_dir / "HEAD").write_text(f"{_SHA_A}\n", encoding="utf-8")
    fake = FakeRepo(lambda args: None, dest=tmp_path)
    assert resolve_head(fake) == _SHA_A
    assert fake.calls == []


def test_resolve_head_reads_a_loose_symbolic_ref(tmp_path):
    git_dir = _head_git_dir(tmp_path)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    loose = git_dir / "refs" / "heads" / "main"
    loose.parent.mkdir(parents=True)
    loose.write_text(f"{_SHA_A}\n", encoding="utf-8")
    fake = FakeRepo(lambda args: None, dest=tmp_path)
    assert resolve_head(fake) == _SHA_A
    assert fake.calls == []


def test_resolve_head_reads_a_packed_ref(tmp_path):
    git_dir = _head_git_dir(tmp_path)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    (git_dir / "packed-refs").write_text(
        "# pack-refs with: peeled fully-peeled sorted\n"
        f"{_SHA_B} refs/heads/other\n"
        f"{_SHA_A} refs/heads/main\n"
        f"^{_SHA_C}\n",
        encoding="utf-8",
    )
    fake = FakeRepo(lambda args: None, dest=tmp_path)
    assert resolve_head(fake) == _SHA_A
    assert fake.calls == []


def test_resolve_head_falls_back_to_rev_parse_on_unparseable_head(tmp_path):
    git_dir = _head_git_dir(tmp_path)
    (git_dir / "HEAD").write_text("garbage\n", encoding="utf-8")
    fake = FakeRepo(lambda args: f"{_SHA_A}\n" if args[0] == "rev-parse" else None, dest=tmp_path)
    assert resolve_head(fake) == _SHA_A
    assert fake.calls == [("rev-parse", "HEAD")]


def test_resolve_head_falls_back_when_the_symbolic_ref_is_unresolvable(tmp_path):
    git_dir = _head_git_dir(tmp_path)
    (git_dir / "HEAD").write_text("ref: refs/heads/gone\n", encoding="utf-8")
    fake = FakeRepo(lambda args: f"{_SHA_B}\n" if args[0] == "rev-parse" else None, dest=tmp_path)
    assert resolve_head(fake) == _SHA_B


def test_resolve_head_refuses_a_backslash_ref_that_escapes_the_git_dir(tmp_path):
    git_dir = _head_git_dir(tmp_path)
    (git_dir / "HEAD").write_text("ref: refs/x\\..\\..\\..\\secret\n", encoding="utf-8")
    decoy = tmp_path / "secret"
    decoy.write_text(f"{_SHA_C}\n", encoding="utf-8")
    fake = FakeRepo(lambda args: f"{_SHA_A}\n" if args[0] == "rev-parse" else None, dest=tmp_path)
    assert resolve_head(fake) == _SHA_A
    assert fake.calls == [("rev-parse", "HEAD")]


@needs_git
def test_resolve_head_matches_rev_parse_for_loose_and_packed_refs(tmp_path):
    repo_dir = tmp_path / "r"
    repo_dir.mkdir()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Jane",
        "GIT_AUTHOR_EMAIL": "jane@example.com",
        "GIT_COMMITTER_NAME": "Jane",
        "GIT_COMMITTER_EMAIL": "jane@example.com",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo_dir, check=True, env=env)
    (repo_dir / "README.md").write_text("hi\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=repo_dir, check=True, env=env)
    sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_dir,
        check=True,
        env=env,
        capture_output=True,
        text=True,
    ).stdout.strip()

    repo = GitRepo(repo_dir)
    assert resolve_head(repo) == sha
    assert (repo_dir / ".git" / "refs" / "heads" / "main").exists()

    subprocess.run(["git", "pack-refs", "--all"], cwd=repo_dir, check=True, env=env)
    assert not (repo_dir / ".git" / "refs" / "heads" / "main").exists()
    assert resolve_head(repo) == sha


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
    assert fake.env_extras == [{"GIT_NO_LAZY_FETCH": "1"}]


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


@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("fatal: repository 'https://github.com/o/r/' not found", "dead"),
        ("fatal: could not read Username for 'https://github.com'", "dead"),
        ("fatal: Authentication failed for 'https://github.com/o/r.git/'", "dead"),
        (
            "fatal: unable to access 'https://github.com/o/r.git/': Could not resolve host",
            "transient",
        ),
        (
            "fatal: unable to access 'https://github.com/o/r.git/': Failed to connect",
            "transient",
        ),
        ("error: RPC failed; curl 56 Recv failure: Connection was reset", "transient"),
        ("fatal: unable to access 'https://github.com/o/r.git/': Operation timed out", "transient"),
        (
            "fatal: unable to access 'https://github.com/': returned error: 502",
            "transient",
        ),
        (
            "fatal: unable to access 'x': The requested URL returned error: 403",
            "transient",
        ),
        ("remote: You have exceeded a secondary rate limit", "transient"),
        ("fatal: Unable to create '.../.git/index.lock': File exists", "local"),
        ("fatal: destination path 'x' already exists and is not an empty directory", "local"),
        ("something unexpected happened", "fatal"),
    ],
)
def test_classify_git_failure_table(stderr, expected):
    assert gitio.classify_git_failure(GitError(["git", "clone"], 128, stderr)) == expected


def test_classify_git_failure_reads_timeouts_as_transient():
    assert (
        gitio.classify_git_failure(subprocess.TimeoutExpired(["git", "fetch"], 600)) == "transient"
    )


def test_retry_call_skips_retries_when_the_failure_is_not_retryable():
    calls: list[int] = []
    sleeps: list[float] = []

    def failing() -> str:
        calls.append(1)
        raise GitError(["git", "clone"], 128, "fatal: repository not found")

    with pytest.raises(GitError):
        retry_call(
            failing,
            attempts=4,
            base_delay=1.0,
            sleep=sleeps.append,
            jitter=lambda: 0.0,
            retryable=lambda exc: gitio.classify_git_failure(exc) != "dead",
        )
    assert len(calls) == 1
    assert sleeps == []


_SHA_A = "a" * 40
_SHA_B = "b" * 40
_SHA_C = "c" * 40
_LS_REFS_URL = "https://github.com/octo/repo.git/git-upload-pack"
_FALLBACK_LS_REMOTE = (
    f"{_SHA_A}\trefs/pull/7/head\n{_SHA_B}\trefs/heads/claude/fix-tests\nsha3\trefs/tags/v1\n"
)


def _pkt_line(payload: bytes) -> bytes:
    return f"{len(payload) + 4:04x}".encode("ascii") + payload


def _ls_refs_stream() -> bytes:
    return (
        _pkt_line(b"version 2\n")
        + b"0001"
        + _pkt_line(f"{_SHA_A} refs/pull/7/head\n".encode())
        + _pkt_line(f"{_SHA_B} refs/heads/claude/fix-tests\n".encode())
        + _pkt_line(f"{_SHA_C} refs/heads/claude/other peeled:{_SHA_A}\n".encode())
        + b"0000"
    )


def _mount_http(monkeypatch, handler) -> httpx.Client:
    client = httpx.Client(transport=httpx.MockTransport(handler), trust_env=False)
    monkeypatch.setattr(gitio, "_http_client", lambda: client)
    return client


def _ok_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=_ls_refs_stream(), request=request)


def test_parse_ls_refs_handles_capabilities_delimiters_and_peel_attrs():
    refs = gitio._parse_ls_refs(_ls_refs_stream())
    assert refs == RemoteRefs(
        pr_refs={7: _SHA_A},
        head_refs={"refs/heads/claude/fix-tests": _SHA_B, "refs/heads/claude/other": _SHA_C},
    )


def test_parse_ls_refs_trims_payloads_and_ignores_err_and_empty_streams():
    trimmed = _pkt_line(f"  {_SHA_A} refs/pull/9/head  ".encode())
    assert gitio._parse_ls_refs(trimmed).pr_refs == {9: _SHA_A}
    assert gitio._parse_ls_refs(_pkt_line(b"ERR repository not found\n") + b"0000") == RemoteRefs(
        pr_refs={}, head_refs={}
    )
    assert gitio._parse_ls_refs(b"") == RemoteRefs(pr_refs={}, head_refs={})
    assert gitio._parse_ls_refs(b"0000") == RemoteRefs(pr_refs={}, head_refs={})
    with pytest.raises(ValueError):
        gitio._parse_ls_refs(b"00ff")


def test_remote_refs_posts_both_prefixes_with_the_v2_headers(monkeypatch):
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content
        captured["headers"] = request.headers
        return _ok_handler(request)

    _mount_http(monkeypatch, handler)
    refs = gitio.remote_refs(GitRepo(Path(), full_name="octo/repo"))
    assert refs.pr_refs == {7: _SHA_A}
    assert refs.head_refs["refs/heads/claude/fix-tests"] == _SHA_B
    assert captured["url"] == _LS_REFS_URL
    assert captured["body"] == (
        b"0014command=ls-refs\n"
        b"0001"
        b"0009peel\n"
        b"001aref-prefix refs/pull/\n"
        b"001bref-prefix refs/heads/\n"
        b"0000"
    )
    headers = captured["headers"]
    assert headers["Git-Protocol"] == "version=2"
    assert headers["Content-Type"] == "application/x-git-upload-pack-request"
    assert headers["Accept"] == "application/x-git-upload-pack-result"
    assert headers["User-Agent"] == "git/2.47.1"


def test_remote_refs_for_returns_refs_without_a_repo(monkeypatch):
    _mount_http(monkeypatch, _ok_handler)
    refs = remote_refs_for("octo/repo")
    assert refs.head_refs == {
        "refs/heads/claude/fix-tests": _SHA_B,
        "refs/heads/claude/other": _SHA_C,
    }


def test_remote_refs_for_404_raises_a_dead_git_error(monkeypatch):
    _mount_http(monkeypatch, lambda request: httpx.Response(404, request=request))
    with pytest.raises(GitError) as excinfo:
        remote_refs_for("octo/gone")
    assert "Repository not found" in excinfo.value.stderr
    assert gitio.classify_git_failure(excinfo.value) == "dead"


def test_remote_refs_401_raises_a_dead_git_error_instead_of_falling_back(monkeypatch):
    _mount_http(monkeypatch, lambda request: httpx.Response(401, request=request))
    repo = FakeRepo(lambda args: _FALLBACK_LS_REMOTE if args[0] == "ls-remote" else None)
    repo.full_name = "octo/private"
    with pytest.raises(GitError) as excinfo:
        gitio.remote_refs(repo)
    assert gitio.classify_git_failure(excinfo.value) == "dead"
    assert repo.calls == []


def test_remote_refs_for_wraps_transient_failures(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    _mount_http(monkeypatch, handler)
    with pytest.raises(RemoteRefsUnavailable):
        remote_refs_for("octo/repo")


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: (_ for _ in ()).throw(httpx.ConnectError("down", request=request)),
        lambda request: httpx.Response(502, request=request),
    ],
)
def test_remote_refs_falls_back_to_git_on_transport_and_server_errors(monkeypatch, handler):
    _mount_http(monkeypatch, handler)
    repo = FakeRepo(lambda args: _FALLBACK_LS_REMOTE if args[0] == "ls-remote" else None)
    repo.full_name = "octo/repo"
    refs = gitio.remote_refs(repo)
    assert refs.pr_refs == {7: _SHA_A}
    assert refs.head_refs == {"refs/heads/claude/fix-tests": _SHA_B}
    assert repo.calls == [("ls-remote", "--refs", "origin", "refs/pull/*/head", "refs/heads/*")]


def test_remote_refs_falls_back_to_git_on_malformed_responses(monkeypatch):
    _mount_http(monkeypatch, lambda request: httpx.Response(200, content=b"zzzz", request=request))
    repo = FakeRepo(lambda args: _FALLBACK_LS_REMOTE if args[0] == "ls-remote" else None)
    repo.full_name = "octo/repo"
    assert gitio.remote_refs(repo).pr_refs == {7: _SHA_A}


def test_remote_refs_caches_the_result_and_lists_once(monkeypatch):
    requests: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(1)
        return _ok_handler(request)

    _mount_http(monkeypatch, handler)
    repo = GitRepo(Path(), full_name="octo/repo")
    first = gitio.remote_refs(repo)
    assert gitio.remote_refs(repo) is first
    assert len(requests) == 1


def test_remote_refs_resolves_and_caches_the_origin_url(monkeypatch):
    calls: list[tuple[str, ...]] = []
    _mount_http(monkeypatch, _ok_handler)

    def git_handler(args):
        calls.append(args)
        return "https://github.com/octo/repo.git" if args[0] == "remote" else None

    repo = FakeRepo(git_handler)
    assert gitio.remote_refs(repo).pr_refs == {7: _SHA_A}
    repo._remote_refs_cache = None
    assert gitio.remote_refs(repo).pr_refs == {7: _SHA_A}
    assert [call[0] for call in calls] == ["remote"]


def test_remote_refs_skips_http_for_non_github_origins(monkeypatch):
    requests: list[int] = []
    _mount_http(monkeypatch, lambda request: requests.append(1) or _ok_handler(request))

    def git_handler(args):
        if args[0] == "remote":
            return "/tmp/local-origin"
        if args[0] == "ls-remote":
            return _FALLBACK_LS_REMOTE
        return None

    assert gitio.remote_refs(FakeRepo(git_handler)).pr_refs == {7: _SHA_A}
    assert requests == []


def test_http_client_is_one_keep_alive_client_per_thread(monkeypatch):
    built: list[int] = []

    def builder() -> httpx.Client:
        built.append(1)
        return httpx.Client(transport=httpx.MockTransport(_ok_handler), trust_env=False)

    monkeypatch.setattr(gitio, "_build_http_client", builder)
    monkeypatch.setattr(gitio, "_client_local", threading.local())
    first = gitio._http_client()
    assert gitio._http_client() is first
    seen: list[object] = []
    worker = threading.Thread(target=lambda: seen.append(gitio._http_client()))
    worker.start()
    worker.join()
    assert len(built) == 2
    assert seen[0] is not first


def test_build_http_client_adds_token_auth(monkeypatch):
    token = "ghp_remote_refs_000"
    monkeypatch.setenv("GITHUB_TOKENS", token)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    client = gitio._build_http_client()
    try:
        payload = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
        assert client.headers["Authorization"] == f"Basic {payload}"
    finally:
        client.close()


def test_fetch_pr_refs_with_refs_skips_the_remote_listing(tmp_path):
    fake = FakeRepo(lambda args: "" if args[0] == "fetch" else None, dest=_repo_dir(tmp_path))
    assert fetch_pr_refs(fake, depth=100, refs={7: _SHA_A}) == {7: _SHA_A}
    assert [call[0] for call in fake.calls] == ["fetch"]
    assert fake.stdins == [b"refs/pull/7/head\n"]


def test_fetch_pr_refs_with_refs_prefers_them_over_the_remote_listing(tmp_path):
    fake = FakeRepo(
        lambda args: f"{_SHA_B}\trefs/pull/9/head\n" if args[0] == "ls-remote" else "",
        dest=_repo_dir(tmp_path),
    )
    assert fetch_pr_refs(fake, depth=100, refs={7: _SHA_A}) == {7: _SHA_A}
    assert [call[0] for call in fake.calls] == ["fetch"]
    assert fake.stdins == [b"refs/pull/7/head\n"]
    assert read_pr_refs_snapshot(fake) == {7: _SHA_A}


def test_fetch_pr_refs_with_reserved_gate_leaves_the_gate_alone_per_chunk(monkeypatch, tmp_path):
    monkeypatch.setattr(gitio, "_PR_FETCH_CHUNK_REFS", 200)
    gate = FakeGate()
    fake = FakeRepo(
        lambda args: _ls_remote_lines(501) if args[0] == "ls-remote" else "",
        dest=_repo_dir(tmp_path),
    )
    refs = fetch_pr_refs(fake, depth=100, gate=gate, gate_reserved=True)
    assert len(refs) == 501
    assert len([call for call in fake.calls if call[0] == "fetch"]) == 3
    assert (gate.acquires, gate.releases, gate.held) == (0, 0, 0)


def test_fetch_pr_refs_with_reserved_gate_still_honours_prefetched_refs(tmp_path):
    gate = FakeGate()
    prefetched = {7: _SHA_A, 9: _SHA_B}
    fake = FakeRepo(lambda args: "" if args[0] == "fetch" else None, dest=_repo_dir(tmp_path))
    assert fetch_pr_refs(fake, depth=100, gate=gate, refs=prefetched, gate_reserved=True) == (
        prefetched
    )
    assert [call[0] for call in fake.calls] == ["fetch"]
    assert (gate.acquires, gate.releases) == (0, 0)
