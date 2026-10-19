from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

import detect.repo_walk as repo_walk
from detect.gitio import GitRepo, read_commits
from detect.repo_walk import (
    CatFileBatch,
    RepoWalkSession,
    WalkAnomaly,
    reset_verification,
    verification_summary,
    walk_windows,
    walk_windows_with_records,
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

        def git(self, *args, timeout=None, stdin=None, env_extra=None):
            assert args[:2] == ("rev-list", "-n")
            return "s1\ns2\n"

    result = walk_windows(FakeRepo(), {9: "aaa"}, depth=100)
    assert result == {9: ("s1", "s2")}


def test_fallback_walks_each_unique_tip_once(tmp_path):
    calls: list[tuple[str, ...]] = []

    class FakeRepo(GitRepo):
        def __init__(self):
            super().__init__(tmp_path / "not-a-repo")

        def git(self, *args, timeout=None, stdin=None, env_extra=None):
            assert args[:2] == ("rev-list", "-n")
            calls.append(args)
            return "s1\ns2\n" if args[-1] == "aaa" else "s3\n"

    result = walk_windows(FakeRepo(), {1: "aaa", 2: "aaa", 3: "bbb"}, depth=100)
    assert len(calls) == 2
    assert result == {1: ("s1", "s2"), 2: ("s1", "s2"), 3: ("s3",)}


def test_fallback_rev_list_disables_lazy_fetch_without_excluding_promisor_objects(tmp_path):
    captured: list[tuple[tuple[str, ...], dict[str, str] | None]] = []

    class FakeRepo(GitRepo):
        def __init__(self):
            super().__init__(tmp_path / "not-a-repo")

        def git(self, *args, timeout=None, stdin=None, env_extra=None):
            captured.append((args, env_extra))
            return "s1\ns2\n"

    result = walk_windows(FakeRepo(), {1: "aaa"}, depth=100)
    assert result == {1: ("s1", "s2")}
    args, env_extra = captured[0]
    assert "--exclude-promisor-objects" not in args
    assert args[-1] == "aaa"
    assert env_extra == {"GIT_NO_LAZY_FETCH": "1"}


@needs_git
def test_in_process_duplicate_tips_share_one_walk_and_identical_windows(tmp_path, monkeypatch):
    monkeypatch.delenv("GITCORPUS_WALK_VERIFY_PCT", raising=False)
    reset_verification()
    dest = _repo(tmp_path, 25)
    repo, calls = _tracking_repo(dest)
    head = _rev_parse(dest, "HEAD")
    walked: list[str] = []
    real_walk_one = repo_walk._walk_one

    def counting(cat, cache, tip, depth, shallow):
        walked.append(tip)
        return real_walk_one(cat, cache, tip, depth, shallow)

    monkeypatch.setattr(repo_walk, "_walk_one", counting)
    result = walk_windows(repo, {1: head, 2: head, 3: head}, depth=10)
    assert walked == [head]
    assert calls == []
    assert result[1] == result[2] == result[3]
    assert result[1] == _rev_list(dest, head, 10)


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


def _sleeping_popen(monkeypatch):
    real_popen = subprocess.Popen

    def sleeping_popen(argv, **kwargs):
        return real_popen([sys.executable, "-c", "import time; time.sleep(30.0)"], **kwargs)

    monkeypatch.setattr(repo_walk.subprocess, "Popen", sleeping_popen)


@needs_git
@needs_git
def test_cat_file_batch_child_environment_disables_lazy_fetch(tmp_path, monkeypatch):
    captured: dict[str, object] = {}
    real_popen = subprocess.Popen

    def recording_popen(argv, **kwargs):
        captured.update(kwargs)
        return real_popen(argv, **kwargs)

    monkeypatch.setattr(repo_walk.subprocess, "Popen", recording_popen)
    cat = CatFileBatch(tmp_path)
    try:
        env = captured["env"]
        assert env["GIT_NO_LAZY_FETCH"] == "1"
    finally:
        cat.close()


def test_cat_file_batch_spawns_the_resolved_git_binary(tmp_path, monkeypatch):
    spawned: list[list[str]] = []
    real_popen = subprocess.Popen

    def recording_popen(argv, **kwargs):
        spawned.append([str(part) for part in argv])
        return real_popen([sys.executable, "-c", "pass"], **kwargs)

    monkeypatch.setattr(repo_walk, "git_binary", lambda: "C:/resolved/mingw64/git.exe")
    monkeypatch.setattr(repo_walk.subprocess, "Popen", recording_popen)
    cat = CatFileBatch(tmp_path)
    try:
        assert spawned == [["C:/resolved/mingw64/git.exe", "cat-file", "--batch"]]
    finally:
        cat.close()


@needs_git
def test_cat_file_batch_timeout_defaults_come_from_the_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_CATFILE_OP_TIMEOUT_SECONDS", "1.5")
    monkeypatch.setenv("GITCORPUS_CATFILE_REPO_TIMEOUT_SECONDS", "7")
    cat = CatFileBatch(tmp_path)
    try:
        assert cat._op_timeout == 1.5
        assert cat._repo_timeout == 7.0
    finally:
        cat.close()


@needs_git
def test_cat_file_batch_timeout_defaults_are_60_and_180_seconds(tmp_path, monkeypatch):
    monkeypatch.delenv("GITCORPUS_CATFILE_OP_TIMEOUT_SECONDS", raising=False)
    monkeypatch.delenv("GITCORPUS_CATFILE_REPO_TIMEOUT_SECONDS", raising=False)
    cat = CatFileBatch(tmp_path)
    try:
        assert cat._op_timeout == 60.0
        assert cat._repo_timeout == 180.0
    finally:
        cat.close()


@needs_git
def test_cat_file_batch_op_timeout_kills_a_silent_child(tmp_path, monkeypatch):
    _sleeping_popen(monkeypatch)
    cat = CatFileBatch(tmp_path, op_timeout=0.2, repo_timeout=30.0)
    started = time.monotonic()
    with pytest.raises(WalkAnomaly, match="cat-file timed out"):
        cat.commit("f" * 40)
    assert time.monotonic() - started < 10.0
    with pytest.raises(WalkAnomaly, match="cat-file timed out"):
        cat.commit("f" * 40)
    assert cat._process.poll() is not None
    try:
        cat.close()
        assert not cat._watchdog.is_alive()
    finally:
        if cat._process.poll() is None:
            cat._process.kill()


@needs_git
def test_cat_file_batch_repo_timeout_kills_an_idle_child(tmp_path, monkeypatch):
    _sleeping_popen(monkeypatch)
    cat = CatFileBatch(tmp_path, op_timeout=30.0, repo_timeout=0.2)
    deadline = time.monotonic() + 10.0
    while cat._process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    assert cat._process.poll() is not None
    with pytest.raises(WalkAnomaly, match="cat-file timed out"):
        cat.commit("f" * 40)
    cat.close()


@needs_git
def test_cat_file_batch_fast_commits_are_unaffected_by_the_watchdog(tmp_path):
    dest = _init_repo(tmp_path)
    sha = _commit_message(dest, "feat: base\n", date="2026-01-01T00:00:00+00:00")
    cat = CatFileBatch(dest, op_timeout=10.0, repo_timeout=30.0)
    try:
        parsed = cat.commit(sha)
    finally:
        cat.close()
    assert parsed is not None
    assert parsed[2].sha == sha


@needs_git
def test_cat_file_batch_close_is_idempotent_and_leaves_no_thread(tmp_path):
    cat = CatFileBatch(tmp_path)
    thread = cat._watchdog
    cat.close()
    assert cat._process.poll() is not None
    cat.close()
    assert not thread.is_alive()


@needs_git
def test_cat_file_batch_read_serves_commit_oids_and_head_paths(tmp_path):
    dest = _repo(tmp_path, 2)
    head = _rev_parse(dest, "HEAD")
    blob_oid = _rev_parse(dest, "HEAD:f.txt")
    cat = CatFileBatch(dest)
    try:
        parsed = cat.read(head)
        assert parsed is not None
        header, body = parsed
        assert header == f"{head} commit {len(body)}"
        assert body.startswith(b"tree ")
        assert b"author Jane <jane@example.com>" in body
        assert cat.read("HEAD:f.txt") == (f"{blob_oid} blob 2", b"1\n")
        assert cat.read("HEAD:missing.txt") is None
        assert cat.read("f" * 40) is None
    finally:
        cat.close()


@needs_git
def test_repo_walk_session_window_matches_the_walker_on_a_linear_repo(tmp_path):
    reset_verification()
    dest = _repo(tmp_path, 30)
    head = _rev_parse(dest, "HEAD")
    repo = GitRepo(dest)
    with RepoWalkSession.open(repo) as session:
        shas, records = session.window(head, 10)
    assert shas == walk_windows(repo, {1: head}, depth=10)[1]
    assert set(shas) == set(_rev_list(dest, head, 10))
    assert records == read_commits(repo, shas)


@needs_git
def test_repo_walk_session_window_matches_the_walker_with_merge_commits(tmp_path):
    reset_verification()
    dest = _repo(tmp_path, 5)
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=dest, check=True, env=ENV)
    (dest / "s.txt").write_text("s\n", encoding="utf-8")
    _commit(dest, "feat: side")
    subprocess.run(["git", "checkout", "-q", "-"], cwd=dest, check=True, env=ENV)
    (dest / "m.txt").write_text("m\n", encoding="utf-8")
    _commit(dest, "feat: main")
    subprocess.run(
        ["git", "merge", "--no-ff", "-q", "-m", "Merge branch 'side'", "side"],
        cwd=dest,
        check=True,
        env=ENV,
    )
    head = _rev_parse(dest, "HEAD")
    repo = GitRepo(dest)
    with RepoWalkSession.open(repo) as session:
        shas, records = session.window(head, 100)
    assert shas == walk_windows(repo, {1: head}, depth=100)[1]
    assert set(shas) == set(_rev_list(dest, head, 100))
    assert records == read_commits(repo, shas)


@needs_git
def test_repo_walk_session_record_and_blob_share_the_commit_cache(tmp_path):
    reset_verification()
    dest = _repo(tmp_path, 3)
    head = _rev_parse(dest, "HEAD")
    repo = GitRepo(dest)
    with RepoWalkSession.open(repo) as session:
        record = session.record(head)
        assert record == read_commits(repo, [head])[head]
        assert session.record(head) is record
        assert session.record("f" * 40) is None
        assert session.blob("HEAD:f.txt") == b"2\n"
        assert session.blob("HEAD:missing.txt") is None


@needs_git
def test_repo_walk_session_close_is_idempotent_and_the_context_manager_closes(tmp_path):
    dest = _repo(tmp_path, 3)
    session = RepoWalkSession.open(GitRepo(dest))
    process = session._cat._process
    with session:
        session.window(_rev_parse(dest, "HEAD"), 1)
    assert process.poll() is not None
    session.close()
    assert not session._cat._watchdog.is_alive()


@pytest.mark.parametrize(
    "error",
    [OSError("unreadable shallow file"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad byte")],
)
def test_repo_walk_session_open_fails_before_spawning_when_shallow_is_unreadable(
    tmp_path, monkeypatch, error
):
    constructed: list[int] = []

    class RecordingBatch:
        def __init__(self, dest):
            constructed.append(1)

        def close(self):
            constructed.append(-1)

    def broken(git_dir):
        raise error

    monkeypatch.setattr(repo_walk, "_load_shallow", broken)
    monkeypatch.setattr(repo_walk, "CatFileBatch", RecordingBatch)

    with pytest.raises(type(error)):
        RepoWalkSession.open(GitRepo(tmp_path))

    assert constructed == []


def _init_repo(tmp_path: Path) -> Path:
    dest = tmp_path / "r"
    dest.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True, env=ENV)
    return dest


def _commit_message(
    dest: Path,
    message: str | bytes,
    *,
    date: str | None = None,
    flags: tuple[str, ...] = (),
    config: tuple[str, ...] = (),
    env_extra: dict[str, str] | None = None,
) -> str:
    payload = message if isinstance(message, bytes) else message.encode("utf-8")
    (dest / ".git" / "test-message").write_bytes(payload)
    env = {**ENV, **(env_extra or {})}
    if date is not None:
        env["GIT_AUTHOR_DATE"] = date
        env["GIT_COMMITTER_DATE"] = date
    command = ["git"]
    for setting in config:
        command.extend(["-c", setting])
    command.extend(["commit", "-q", "--allow-empty", "-F", ".git/test-message", *flags])
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True, env=ENV)
    subprocess.run(command, cwd=dest, check=True, env=env)
    return _rev_parse(dest, "HEAD")


def _hash_commit(dest: Path, raw: bytes) -> str:
    return (
        subprocess.run(
            ["git", "hash-object", "-t", "commit", "-w", "--stdin"],
            cwd=dest,
            check=True,
            env=ENV,
            input=raw,
            capture_output=True,
        )
        .stdout.decode()
        .strip()
    )


@needs_git
def test_missing_parent_is_a_shallow_boundary_without_a_rev_list_fallback(tmp_path):
    reset_verification()
    dest = _init_repo(tmp_path)
    (dest / "f.txt").write_text("0\n", encoding="utf-8")
    _commit_message(dest, "feat: base\n", date="2026-01-01T00:00:00+00:00")
    tree = _rev_parse(dest, "HEAD^{tree}")
    raw = (
        f"tree {tree}\n"
        f"parent {'0' * 40}\n"
        "author Jane <jane@example.com> 1770000000 +0000\n"
        "committer Jane <jane@example.com> 1770000000 +0000\n"
        "\n"
        "feat: orphaned parent\n"
    ).encode()
    tip = _hash_commit(dest, raw)
    repo, calls = _tracking_repo(dest)
    result = walk_windows(repo, {1: tip}, depth=10)
    assert result[1] == (tip,)
    assert calls == []


@needs_git
def test_missing_tip_still_raises_walk_anomaly(tmp_path):
    dest = _init_repo(tmp_path)
    _commit_message(dest, "feat: base\n", date="2026-01-01T00:00:00+00:00")
    cat = CatFileBatch(dest)
    try:
        with pytest.raises(WalkAnomaly, match="missing"):
            repo_walk._walk_one(cat, {}, "f" * 40, 5, frozenset())
    finally:
        cat.close()


@needs_git
def test_walked_records_match_read_commits_for_varied_commit_shapes(tmp_path):
    reset_verification()
    dest = _init_repo(tmp_path)
    (dest / "f.txt").write_text("0\n", encoding="utf-8")
    plain = _commit_message(dest, "feat: plain\n", date="2026-01-01T00:00:00+00:00")
    (dest / "f.txt").write_text("1\n", encoding="utf-8")
    multiline = _commit_message(
        dest,
        "feat: multi-line\n\nbody paragraph\n\nSigned-off-by: Jane <jane@example.com>\n",
        date="2026-01-02T00:00:00+00:00",
    )
    (dest / "f.txt").write_text("2\n", encoding="utf-8")
    rollover = _commit_message(dest, "feat: rollover\n", date="2026-01-03T23:30:00-05:00")
    empty = _commit_message(
        dest,
        b"",
        date="2026-01-04T00:00:00+00:00",
        flags=("--allow-empty", "--allow-empty-message"),
    )
    repo = GitRepo(dest)
    windows, walked = walk_windows_with_records(repo, {1: empty}, depth=100)
    shas = sorted(windows[1])
    assert set(windows[1]) == set(_rev_list(dest, empty, 100))
    assert set(walked) == set(windows[1])
    assert {sha: walked[sha] for sha in shas} == read_commits(repo, shas)
    assert walked[plain].committed_at == "2026-01-01T00:00:00Z"
    assert walked[rollover].committed_at == "2026-01-03T23:30:00-05:00"
    assert walked[multiline].message == (
        "feat: multi-line\n\nbody paragraph\n\nSigned-off-by: Jane <jane@example.com>"
    )
    assert walked[empty].message == ""


@needs_git
def test_walked_records_match_git_reencoding_for_iso_8859_1_message(tmp_path):
    reset_verification()
    dest = _init_repo(tmp_path)
    sha = _commit_message(
        dest,
        "sujet: café à la crème\n".encode("iso-8859-1"),
        date="2026-02-01T00:00:00+00:00",
        config=("i18n.commitEncoding=ISO-8859-1",),
    )
    repo = GitRepo(dest)
    windows, walked = walk_windows_with_records(repo, {1: sha}, depth=10)
    assert windows[1] == (sha,)
    assert walked[sha] == read_commits(repo, [sha])[sha]
    assert walked[sha].message == "sujet: café à la crème"


@needs_git
def test_walked_records_keep_non_ascii_trailing_whitespace_in_names(tmp_path):
    reset_verification()
    dest = _init_repo(tmp_path)
    nbsp = "Jane\u00a0"
    nbsp_sha = _commit_message(
        dest,
        "feat: nbsp name\n",
        date="2026-01-01T00:00:00+00:00",
        env_extra={"GIT_AUTHOR_NAME": nbsp, "GIT_COMMITTER_NAME": nbsp},
    )
    spaced_sha = _commit_message(
        dest,
        "feat: ascii trailing space\n",
        date="2026-01-02T00:00:00+00:00",
        env_extra={"GIT_AUTHOR_NAME": "Jane ", "GIT_COMMITTER_NAME": "Jane "},
    )
    repo = GitRepo(dest)
    _windows, walked = walk_windows_with_records(repo, {1: spaced_sha}, depth=100)
    oracle = read_commits(repo, [nbsp_sha, spaced_sha])
    assert {sha: walked[sha] for sha in oracle} == oracle
    assert walked[nbsp_sha].author_name == nbsp
    assert walked[nbsp_sha].committer_name == nbsp
    assert walked[spaced_sha].author_name == "Jane"


@needs_git
def test_walked_gpg_signed_commit_matches_read_commits(tmp_path):
    reset_verification()
    dest = _init_repo(tmp_path)
    parent = _commit_message(dest, "feat: base\n", date="2026-01-01T00:00:00+00:00")
    tree = _rev_parse(dest, "HEAD^{tree}")
    bogus = "f" * 40
    raw = (
        f"tree {tree}\n"
        f"parent {parent}\n"
        "author Jane <jane@example.com> 1770000000 +0000\n"
        "committer Jane <jane@example.com> 1770000000 +0000\n"
        "gpgsig -----BEGIN PGP SIGNATURE-----\n"
        " \n"
        f" parent {bogus}\n"
        " iQIzBAABCgAdFiEEtesttesttest\n"
        " =abcd\n"
        " -----END PGP SIGNATURE-----\n"
        "\n"
        "feat: signed work\n\nwith a body\n"
    ).encode()
    sha = _hash_commit(dest, raw)
    repo = GitRepo(dest)
    windows, walked = walk_windows_with_records(repo, {1: sha}, depth=10)
    assert windows[1] == (sha, parent)
    assert walked[sha] == read_commits(repo, [sha])[sha]
    assert walked[parent] == read_commits(repo, [parent])[parent]
    cat = CatFileBatch(dest)
    try:
        parsed = cat.commit(sha)
    finally:
        cat.close()
    assert parsed is not None
    parents, epoch, record = parsed
    assert parents == (parent,)
    assert epoch == 1770000000
    assert record == read_commits(repo, [sha])[sha]


@needs_git
def test_walked_merge_commit_preserves_parent_order(tmp_path):
    reset_verification()
    dest = _init_repo(tmp_path)
    (dest / "f.txt").write_text("0\n", encoding="utf-8")
    base = _commit_message(dest, "feat: base\n", date="2026-01-01T00:00:00+00:00")
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=dest, check=True, env=ENV)
    (dest / "s.txt").write_text("s\n", encoding="utf-8")
    side = _commit_message(dest, "feat: side\n", date="2026-01-02T00:00:00+00:00")
    subprocess.run(["git", "checkout", "-q", "-"], cwd=dest, check=True, env=ENV)
    (dest / "m.txt").write_text("m\n", encoding="utf-8")
    main = _commit_message(dest, "feat: main\n", date="2026-01-03T00:00:00+00:00")
    merge_env = {
        **ENV,
        "GIT_AUTHOR_DATE": "2026-01-04T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-01-04T00:00:00+00:00",
    }
    subprocess.run(
        ["git", "merge", "--no-ff", "-q", "-m", "Merge branch 'side'", "side"],
        cwd=dest,
        check=True,
        env=merge_env,
    )
    merge = _rev_parse(dest, "HEAD")
    assert (_rev_parse(dest, f"{merge}^1"), _rev_parse(dest, f"{merge}^2")) == (main, side)
    cat = CatFileBatch(dest)
    try:
        parsed = cat.commit(merge)
    finally:
        cat.close()
    assert parsed is not None
    parents, _epoch, _record = parsed
    assert parents == (main, side)
    repo = GitRepo(dest)
    _windows, walked = walk_windows_with_records(repo, {1: merge}, depth=100)
    oracle = read_commits(repo, [merge, main, side, base])
    assert {sha: walked[sha] for sha in oracle} == oracle


@needs_git
def test_message_line_looking_like_parent_is_not_parsed_as_parent(tmp_path):
    reset_verification()
    dest = _init_repo(tmp_path)
    (dest / "f.txt").write_text("0\n", encoding="utf-8")
    base = _commit_message(dest, "feat: base\n", date="2026-01-01T00:00:00+00:00")
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=dest, check=True, env=ENV)
    (dest / "s.txt").write_text("s\n", encoding="utf-8")
    side = _commit_message(dest, "feat: side\n", date="2026-01-02T00:00:00+00:00")
    subprocess.run(["git", "checkout", "-q", "-"], cwd=dest, check=True, env=ENV)
    (dest / "m.txt").write_text("m\n", encoding="utf-8")
    head = _commit_message(
        dest,
        "feat: body mentions a parent\n\n"
        f"parent {side}\n"
        "committer Jane <jane@example.com> 1 +0000\n",
        date="2026-01-03T00:00:00+00:00",
    )
    repo = GitRepo(dest)
    windows, walked = walk_windows_with_records(repo, {1: head}, depth=100)
    assert windows[1] == _rev_list(dest, head, 100)
    assert side not in windows[1]
    oracle = read_commits(repo, [head, base])
    assert {sha: walked[sha] for sha in oracle} == oracle
    cat = CatFileBatch(dest)
    try:
        parsed = cat.commit(head)
    finally:
        cat.close()
    assert parsed is not None
    assert parsed[0] == (base,)


@needs_git
def test_literal_record_separator_byte_survives_the_walk_but_truncates_in_parse_log(tmp_path):
    reset_verification()
    dest = _init_repo(tmp_path)
    sha = _commit_message(
        dest,
        b"feat: before\x1e after\n",
        date="2026-01-01T00:00:00+00:00",
    )
    repo = GitRepo(dest)
    _windows, walked = walk_windows_with_records(repo, {1: sha}, depth=10)
    assert walked[sha].message == "feat: before\x1e after"
    assert read_commits(repo, [sha])[sha].message == "feat: before"


@needs_git
def test_walked_records_parity_for_batched_shas(tmp_path):
    reset_verification()
    dest = _repo(tmp_path, 12)
    repo = GitRepo(dest)
    head = _rev_parse(dest, "HEAD")
    older = _rev_parse(dest, "HEAD~5")
    windows, walked = walk_windows_with_records(repo, {1: head, 2: older}, depth=4)
    shas = sorted({sha for shas in windows.values() for sha in shas})
    assert set(walked) == set(shas)
    assert {sha: walked[sha] for sha in shas} == read_commits(repo, shas)


def test_walk_windows_with_records_falls_back_without_records(tmp_path):
    class FakeRepo(GitRepo):
        def __init__(self):
            super().__init__(tmp_path / "not-a-repo")

        def git(self, *args, timeout=None, stdin=None, env_extra=None):
            assert args[:2] == ("rev-list", "-n")
            return "s1\ns2\n"

    windows, records = walk_windows_with_records(FakeRepo(), {9: "aaa"}, depth=100)
    assert windows == {9: ("s1", "s2")}
    assert records == {}
