from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from detect.gitio import GitRepo
from detect.repo_walk import reset_verification, verification_summary, walk_windows

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Jane",
    "GIT_AUTHOR_EMAIL": "jane@example.com",
    "GIT_COMMITTER_NAME": "Jane",
    "GIT_COMMITTER_EMAIL": "jane@example.com",
}


def _commit(dest: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True, env=ENV)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=dest, check=True, env=ENV)


def _repo(tmp_path: Path, commits: int) -> Path:
    dest = tmp_path / "r"
    dest.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True, env=ENV)
    for index in range(commits):
        (dest / "f.txt").write_text(f"{index}\n", encoding="utf-8")
        _commit(dest, f"feat: c{index}")
    return dest


@needs_git
def test_walk_windows_matches_rev_list_exactly(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 30)
    heads = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest, check=True, env=ENV, capture_output=True, text=True
    ).stdout.strip()
    result = walk_windows(GitRepo(dest), {7: heads}, depth=100)
    truth = subprocess.run(
        ["git", "rev-list", "-n", "100", heads],
        cwd=dest,
        check=True,
        env=ENV,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert set(result[7]) == set(truth)
    assert verification_summary()["mismatches"] == 0


@needs_git
def test_walk_windows_selects_the_same_deep_prefix_as_rev_list(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 25)
    heads = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest, check=True, env=ENV, capture_output=True, text=True
    ).stdout.strip()
    result = walk_windows(GitRepo(dest), {1: heads}, depth=10)
    truth = subprocess.run(
        ["git", "rev-list", "-n", "10", heads],
        cwd=dest,
        check=True,
        env=ENV,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert result[1] == tuple(truth)


@needs_git
def test_walk_windows_respects_shallow_grafts(tmp_path):
    origin = _repo(tmp_path / "origin", 20)
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "5", origin.as_uri(), str(clone)], check=True, env=ENV
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=clone,
        check=True,
        env=ENV,
        capture_output=True,
        text=True,
    ).stdout.strip()
    result = walk_windows(GitRepo(clone), {3: head}, depth=100)
    truth = subprocess.run(
        ["git", "rev-list", "-n", "100", head],
        cwd=clone,
        check=True,
        env=ENV,
        capture_output=True,
        text=True,
    ).stdout.split()
    assert result[3] == tuple(truth)
    assert len(result[3]) == 5  # the graft caps it


def test_walk_windows_falls_back_to_rev_list_without_a_repo(tmp_path):
    class FakeRepo(GitRepo):
        def __init__(self):
            super().__init__(tmp_path / "not-a-repo")

        def git(self, *args, timeout=None, stdin=None):
            assert args[:2] == ("rev-list", "-n")
            return "s1\ns2\n"

    result = walk_windows(FakeRepo(), {9: "aaa"}, depth=100)
    assert result == {9: ("s1", "s2")}


def test_walk_windows_returns_empty_for_no_refs(tmp_path):
    assert walk_windows(GitRepo(tmp_path), {}, depth=100) == {}
