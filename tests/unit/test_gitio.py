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
        "\x1f2026-01-02T03:04:05+00:00"
        "\x1ffeat: add\n\nCo-authored-by: Claude <noreply@anthropic.com>\x1e"
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
