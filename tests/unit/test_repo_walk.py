from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

import detect.repo_walk as repo_walk
from detect.gitio import GitRepo
from detect.repo_walk import (
    CatFileBatch,
    reset_verification,
    verification_summary,
    walk_windows,
)

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


def _rev_parse(dest: Path, rev: str) -> str:
    return subprocess.run(
        ["git", "rev-parse", rev], cwd=dest, check=True, env=ENV, capture_output=True, text=True
    ).stdout.strip()


def _rev_list(dest: Path, rev: str, depth: int) -> tuple[str, ...]:
    output = subprocess.run(
        ["git", "rev-list", "-n", str(depth), rev],
        cwd=dest,
        check=True,
        env=ENV,
        capture_output=True,
        text=True,
    ).stdout
    return tuple(output.split())


def _tracking_repo(dest: Path) -> tuple[GitRepo, list[tuple[str, ...]]]:
    repo = GitRepo(dest)
    calls: list[tuple[str, ...]] = []
    git = repo.git

    def tracked(*args, **kwargs):
        if args and args[0] == "rev-list":
            calls.append(args)
        return git(*args, **kwargs)

    repo.git = tracked
    return repo, calls


@needs_git
def test_walk_windows_matches_rev_list_exactly(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 30)
    repo, calls = _tracking_repo(dest)
    heads = _rev_parse(dest, "HEAD")
    result = walk_windows(repo, {7: heads}, depth=10)
    assert set(result[7]) == set(_rev_list(dest, heads, 10))
    assert len(calls) == 1
    assert verification_summary()["checked"] == 1
    assert verification_summary()["mismatches"] == 0


@needs_git
def test_walk_windows_selects_the_same_deep_prefix_as_rev_list(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 25)
    heads = _rev_parse(dest, "HEAD")
    result = walk_windows(GitRepo(dest), {1: heads}, depth=10)
    assert result[1] == _rev_list(dest, heads, 10)
    assert verification_summary()["checked"] == 1


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


@needs_git
def test_exhausted_walk_is_never_verified_even_at_pct_100(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 5)
    repo, calls = _tracking_repo(dest)
    result = walk_windows(repo, {1: _rev_parse(dest, "HEAD")}, depth=100)
    assert len(result[1]) == 5
    assert calls == []
    assert verification_summary() == {"checked": 0, "mismatches": 0, "disabled": False}


@needs_git
def test_default_verify_pct_is_zero_so_order_dependent_walks_spawn_nothing(tmp_path, monkeypatch):
    monkeypatch.delenv("GITCORPUS_WALK_VERIFY_PCT", raising=False)
    monkeypatch.setattr(repo_walk.random, "randint", lambda low, high: low)
    reset_verification()
    dest = _repo(tmp_path, 25)
    repo, calls = _tracking_repo(dest)
    result = walk_windows(repo, {1: _rev_parse(dest, "HEAD")}, depth=10)
    assert len(result[1]) == 10
    assert calls == []
    assert verification_summary()["checked"] == 0


@needs_git
def test_verify_budget_caps_spawns_at_two_per_walk_windows_call(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 40)
    repo, calls = _tracking_repo(dest)
    tips = {
        1: _rev_parse(dest, "HEAD"),
        2: _rev_parse(dest, "HEAD~5"),
        3: _rev_parse(dest, "HEAD~10"),
    }
    first = walk_windows(repo, tips, depth=10)
    assert len(calls) == 2
    assert verification_summary()["checked"] == 2
    second = walk_windows(repo, tips, depth=10)
    assert len(calls) == 4
    assert verification_summary()["checked"] == 4
    for number, tip in tips.items():
        truth = _rev_list(dest, tip, 10)
        assert first[number] == truth
        assert second[number] == truth


@needs_git
def test_mismatch_substitutes_truth_and_disables_after_three(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 20)
    repo, _calls = _tracking_repo(dest)
    head = _rev_parse(dest, "HEAD")
    truth = _rev_list(dest, head, 5)
    real_walk_one = repo_walk._walk_one
    walked_tips: list[str] = []

    def corrupted(cat, cache, tip, depth, shallow):
        walked_tips.append(tip)
        walked = real_walk_one(cat, cache, tip, depth, shallow)
        return ("f" * 40, *walked[1:])

    monkeypatch.setattr(repo_walk, "_walk_one", corrupted)

    for expected_mismatches in (1, 2, 3):
        result = walk_windows(repo, {1: head}, depth=5)
        assert result[1] == truth
        summary = verification_summary()
        assert summary["mismatches"] == expected_mismatches
        assert summary["disabled"] == (expected_mismatches == 3)

    assert len(walked_tips) == 3
    healed = walk_windows(repo, {1: head}, depth=5)
    assert healed[1] == truth
    assert verification_summary()["disabled"] is True
    assert len(walked_tips) == 3


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


@needs_git
def test_cat_file_batch_close_survives_posix_communicate_semantics(tmp_path, monkeypatch):
    cat = CatFileBatch(tmp_path)
    original = subprocess.Popen.communicate

    def posix_communicate(process, input=None, timeout=None):
        if process.stdin is not None and process.stdin.closed:
            raise ValueError("flush of closed file")
        return original(process, input, timeout)

    monkeypatch.setattr(subprocess.Popen, "communicate", posix_communicate)

    cat.close()

    assert cat._process.poll() is not None
