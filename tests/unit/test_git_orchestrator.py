from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import stat
import subprocess
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

import pytest
from sqlalchemy import text

import detect.phase_metrics as phase_metrics
import detect.repo_walk as repo_walk
from detect.breaker import local_values
from detect.channels import ChannelResult
from detect.git_orchestrator import (
    Admission,
    GitScanConfig,
    _admit,
    _failure_message,
    _kill_tree,
    _offline_refs,
    _remove_tree,
    _run_git_detection_processes,
    _scan_one,
    _scan_worker_main,
    pr_gate_permits_from_env,
    run_git_detection,
)
from detect.gitio import GitError, GitRepo, RemoteRefs, RemoteRefsUnavailable
from detect.orchestrator import DetectOptions, _failed_scan
from detect.packs import Pack, Pattern, freeze_pack
from enrich.cloner import MARKER_NAME
from lib import cancellation
from lib.cancellation import RunCancelled
from serve.executor import create_run

FAKE_DEST = Path(tempfile.gettempdir(), f"gitcorpus-fake-repo-{os.getpid()}")


class FakeRepo(GitRepo):
    """GitRepo whose git() answers from a canned handler.

    The dest is an absolute placeholder with no git directory: HEAD resolution
    and walk sessions must degrade to the canned handler instead of the test's
    cwd, with no dependence on the cwd the suite runs from.
    """

    def __init__(self, handler):
        super().__init__(FAKE_DEST)
        self._handler = handler
        self.calls: list[tuple[str, ...]] = []

    def git(self, *args: str, timeout: float | None = None, stdin=None, env_extra=None) -> str:
        self.calls.append(args)
        result = self._handler(args)
        if result is None:
            raise GitError(list(args), 128, "fake")
        return result

    def read_blobs(self, paths):
        self.calls.append(("read_blobs", *paths))
        return {path: self._handler(("show", f"HEAD:{path}")) for path in paths}


def happy_handler(args):
    if args[0] == "ls-tree":
        return f"100644 blob {'a' * 40}\tCLAUDE.md\n"
    if args[0] == "show":
        return "# guidance\n"
    if args[0] == "log":
        return _LOG
    if args[0] == "fetch":
        return ""
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
    "\x1f2026-01-02T00:00:00+00:00\x1ffeat: claude work\n\n"
    "Co-authored-by: Claude <noreply@anthropic.com>\x1e"
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


def test_run_git_detection_records_evidence_and_summary(clean_db, tmp_path, monkeypatch):
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

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    config = GitScanConfig(depth=100, keep=False, scan_root=str(tmp_path / "clones"), workers=1)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file", "commit_trailer", "branch", "label"})),
        PACK,
        config=config,
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
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
                "SELECT channel, agent FROM detection_evidence WHERE run_id = :run ORDER BY channel"
            ),
            {"run": detect_run},
        ).all()
    assert ("file", "Claude Code") in rows
    assert ("commit_trailer", "Claude Code") in rows
    assert not (tmp_path / "clones" / f"detect-{detect_run}").exists()


def test_run_git_detection_passes_full_name_into_the_repo_factory(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    made: list[tuple[str, str | None]] = []

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    def factory(dest: Path, full_name: str | None = None):
        made.append((dest.name, full_name))
        return FakeRepo(happy_handler)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(depth=100, keep=False, scan_root=str(tmp_path / "clones"), workers=1),
        clone_fn=clone,
        repo_factory=factory,
    )
    assert sorted(made) == [("octo__one", "octo/one"), ("octo__two", "octo/two")]


def test_run_git_detection_keep_retains_scan_dir(clean_db, tmp_path, monkeypatch):
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

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    config = GitScanConfig(depth=100, keep=True, scan_root=str(tmp_path / "clones"), workers=1)
    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=config,
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert (tmp_path / "clones" / f"detect-{detect_run}").exists()


def test_run_git_detection_keep_reuses_marked_clones_on_rerun(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    clones: list[str] = []

    def clone(full_name: str, dest: Path) -> None:
        clones.append(full_name)
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    config = GitScanConfig(depth=100, keep=True, scan_root=str(tmp_path / "clones"), workers=1)
    spec = make_spec(source_id, frozenset({"file"}))
    run_git_detection(
        engine,
        detect_run,
        spec,
        PACK,
        config=config,
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    run_dir = tmp_path / "clones" / f"detect-{detect_run}"
    assert sorted(clones) == ["octo/one", "octo/two"]
    assert (run_dir / "octo__one" / MARKER_NAME).exists()
    assert (run_dir / "octo__two" / MARKER_NAME).exists()

    clones.clear()
    run_git_detection(
        engine,
        detect_run,
        spec,
        PACK,
        config=config,
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert clones == []


def test_run_git_detection_resolves_the_default_relative_scan_root(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    dests: list[Path] = []

    def clone(full_name: str, dest: Path) -> None:
        dests.append(dest)
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    monkeypatch.chdir(tmp_path)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(workers=1),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert dests
    assert all(dest.is_absolute() for dest in dests)
    assert dests[0] == tmp_path / "clones" / f"detect-{detect_run}" / "octo__one"
    assert payload.result_summary["repos_scanned"] == 2
    assert not (tmp_path / "clones" / f"detect-{detect_run}").exists()


def test_run_git_detection_retries_a_failed_clone(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    attempts: list[str] = []

    def clone(full_name: str, dest: Path) -> None:
        attempts.append(full_name)
        if full_name == "octo/two" and attempts.count("octo/two") == 1:
            raise GitError(["git", "clone"], 128, "fatal: connection reset")
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1, retry_delay=0.0),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert attempts.count("octo/two") == 2
    assert payload.result_summary["repos_unavailable"] == 0
    assert payload.incomplete is False


def test_run_git_detection_stops_before_scanning_when_the_disk_reserve_is_hit(
    clean_db, tmp_path, monkeypatch
):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    clones: list[str] = []

    def clone(full_name: str, dest: Path) -> None:
        clones.append(full_name)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10.0)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert clones == []
    assert payload.items == []
    assert payload.incomplete is True
    assert payload.result_summary["repos_scanned"] == 0
    assert any("low disk" in warning for warning in payload.warnings)


def test_run_git_detection_stops_scheduling_when_disk_drops_mid_run(
    clean_db, tmp_path, monkeypatch
):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    readings: list[int] = []

    def free(path) -> float:
        readings.append(1)
        return 10_000.0 if len(readings) == 1 else 10.0

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", free)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert payload.result_summary["repos_scanned"] == 1
    assert payload.incomplete is True
    assert any("low disk" in warning for warning in payload.warnings)
    assert len(readings) >= 2


def test_run_git_detection_checkpoints_run_items_per_repo(clean_db, tmp_path, monkeypatch):
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

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file", "commit_trailer"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT repo_id, full_name, detection FROM run_items"
                    " WHERE run_id = :run ORDER BY repo_id"
                ),
                {"run": detect_run},
            )
            .mappings()
            .all()
        )
    assert [row["repo_id"] for row in rows] == [1, 2]
    assert rows[0]["detection"]["agents"] == ["Claude Code"]


def test_cancelled_git_detection_leaves_checkpointed_items(clean_db, tmp_path, monkeypatch):
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

    def repo_factory(dest: Path, full_name: str | None = None):
        if dest.name == "octo__two":
            raise RunCancelled()
        return FakeRepo(happy_handler)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    with pytest.raises(RunCancelled):
        run_git_detection(
            engine,
            detect_run,
            make_spec(source_id, frozenset({"file"})),
            PACK,
            config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
            clone_fn=clone,
            repo_factory=repo_factory,
        )
    with engine.connect() as connection:
        names = (
            connection.execute(
                text("SELECT full_name FROM run_items WHERE run_id = :run ORDER BY repo_id"),
                {"run": detect_run},
            )
            .scalars()
            .all()
        )
    assert names == ["octo/one"]
    # Cancellation skips the final sweep so the stop lands immediately; the
    # leftovers are reclaimed by the console's flush action.
    assert (tmp_path / "clones" / f"detect-{detect_run}").exists()


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")


def _make_local_repo(dest: Path) -> None:
    dest.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True)
    (dest / "CLAUDE.md").write_text("# guidance\n", encoding="utf-8")
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Jane",
        "GIT_AUTHOR_EMAIL": "jane@example.com",
        "GIT_COMMITTER_NAME": "Jane",
        "GIT_COMMITTER_EMAIL": "jane@example.com",
    }
    subprocess.run(["git", "add", "."], cwd=dest, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "feat: x"], cwd=dest, check=True, env=env)
    (dest / MARKER_NAME).write_text("", encoding="utf-8")


@needs_git
def test_run_git_detection_spreads_workers_over_processes(clean_db, tmp_path):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    run_dir = tmp_path / "clones" / f"detect-{detect_run}"
    _make_local_repo(run_dir / "octo__one")
    _make_local_repo(run_dir / "octo__two")
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file", "commit_trailer"})),
        PACK,
        config=GitScanConfig(
            scan_root=str(tmp_path / "clones"),
            keep=True,
            workers=4,
            processes=2,
        ),
        admission_probe=_offline_refs,
    )
    assert payload.result_summary["repos_scanned"] == 2
    assert payload.result_summary["repos_unavailable"] == 0
    assert all(item.detection["agents"] == ["Claude Code"] for item in payload.items)
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT count(*) FROM detection_evidence WHERE run_id = :run"),
            {"run": detect_run},
        ).scalar()
    assert rows == 2
    assert (run_dir / "octo__one" / MARKER_NAME).exists()


def test_run_git_detection_reads_the_commit_window_once_per_repo(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    log_calls: list[int] = []

    def handler(args):
        if args[0] == "log":
            log_calls.append(1)
        return happy_handler(args)

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"author", "branch"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(handler),
    )
    assert len(log_calls) == 2  # one per repo, shared by history and branch


def test_run_git_detection_passes_scan_knobs_to_the_pr_channel(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    captured: dict[str, object] = {}

    def fake_pr(
        repo, pack, agents, *, depth, attempts, retry_delay, gate, refs, gate_reserved, session=None
    ):
        captured.update(
            depth=depth,
            attempts=attempts,
            retry_delay=retry_delay,
            gate=gate,
        )
        return ChannelResult(status="ok")

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    monkeypatch.setattr("detect.git_orchestrator.detect_pr_commits_local", fake_pr)
    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"pr_metadata"})),
        PACK,
        config=GitScanConfig(
            scan_root=str(tmp_path / "clones"),
            workers=1,
            attempts=2,
            retry_delay=0.5,
        ),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert captured == {"depth": 100, "attempts": 2, "retry_delay": 0.5, "gate": None}


def test_run_git_detection_single_process_path_forwards_no_pr_gate(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine,
        {"kind": "detect"},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    gates: list[object] = []

    def fake_pr(
        repo, pack, agents, *, depth, attempts, retry_delay, gate, refs, gate_reserved, session=None
    ):
        gates.append(gate)
        return ChannelResult(status="ok")

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    monkeypatch.setattr("detect.git_orchestrator.detect_pr_commits_local", fake_pr)
    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"pr_metadata"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert gates == [None, None]


def test_remove_tree_retries_after_a_transient_failure(tmp_path, monkeypatch):
    target = tmp_path / "run"
    target.mkdir()
    (target / "pack").write_text("x", encoding="utf-8")
    real = shutil.rmtree
    calls: list[Path] = []

    def flaky(path, *args, **kwargs):
        calls.append(Path(path))
        if len(calls) == 1:
            return
        real(path, *args, **kwargs)

    monkeypatch.setattr("detect.git_orchestrator.shutil.rmtree", flaky)
    monkeypatch.setattr("detect.git_orchestrator.time.sleep", lambda _: None)
    _remove_tree(target)
    assert len(calls) == 2
    assert not target.exists()


def test_remove_tree_deletes_a_real_directory(tmp_path):
    target = tmp_path / "run"
    (target / "a" / "b").mkdir(parents=True)
    (target / "a" / "b" / "file").write_text("x", encoding="utf-8")
    _remove_tree(target)
    assert not target.exists()


def test_remove_tree_deletes_read_only_files(tmp_path):
    # Git for Windows marks pack files read-only, which turned the previous
    # ignore_errors=True sweep into a silent no-op.
    target = tmp_path / "run"
    pack_dir = target / ".git" / "objects" / "pack"
    pack_dir.mkdir(parents=True)
    pack = pack_dir / "x.pack"
    pack.write_text("pack", encoding="utf-8")
    os.chmod(pack, stat.S_IREAD)
    (target / "nested").mkdir()
    (target / "nested" / "keep.txt").write_text("x", encoding="utf-8")
    _remove_tree(target)
    assert not target.exists()


def test_remove_tree_returns_immediately_for_a_missing_path(tmp_path, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("detect.git_orchestrator.time.sleep", sleeps.append)
    _remove_tree(tmp_path / "missing")
    assert sleeps == []


class FakeWorker:
    """Worker double exposing the pid/terminate surface _kill_tree touches."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.terminated = False

    def terminate(self) -> None:
        self.terminated = True


def test_kill_tree_uses_taskkill_on_windows(monkeypatch):
    calls: list[tuple[tuple[str, ...], dict]] = []

    def fake_run(argv, **kwargs):
        calls.append((tuple(argv), kwargs))

    monkeypatch.setattr("detect.git_orchestrator.subprocess.run", fake_run)
    monkeypatch.setattr("detect.git_orchestrator.os.name", "nt")
    worker = FakeWorker(4321)
    _kill_tree(worker)
    assert [argv for argv, _kwargs in calls] == [("taskkill", "/F", "/T", "/PID", "4321")]
    assert not worker.terminated


def test_kill_tree_swallows_taskkill_errors(monkeypatch):
    def failing_run(argv, **kwargs):
        raise OSError("taskkill vanished")

    monkeypatch.setattr("detect.git_orchestrator.subprocess.run", failing_run)
    monkeypatch.setattr("detect.git_orchestrator.os.name", "nt")
    _kill_tree(FakeWorker(4321))


def test_kill_tree_terminates_the_process_off_windows(monkeypatch):
    def forbidden_run(argv, **kwargs):
        raise AssertionError("taskkill must not run off Windows")

    monkeypatch.setattr("detect.git_orchestrator.subprocess.run", forbidden_run)
    monkeypatch.setattr("detect.git_orchestrator.os.name", "posix")
    worker = FakeWorker(4321)
    _kill_tree(worker)
    assert worker.terminated


def test_run_git_detection_cancel_reaches_scan_workers(clean_db, tmp_path, monkeypatch):
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

    seen_cancel = threading.Event()

    class CancellableRepo(FakeRepo):
        def git(self, *args: str, timeout: float | None = None, stdin=None, env_extra=None) -> str:
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                try:
                    cancellation.check()
                except RunCancelled:
                    seen_cancel.set()
                    raise
                time.sleep(0.01)
            raise AssertionError("scan worker never observed the cancellation binding")

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    cancel = threading.Event()
    token = cancellation.bind(cancel.is_set)
    timer = threading.Timer(0.2, cancel.set)
    timer.start()
    try:
        with pytest.raises(RunCancelled):
            run_git_detection(
                engine,
                detect_run,
                make_spec(source_id, frozenset({"file"})),
                PACK,
                config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
                clone_fn=clone,
                repo_factory=lambda dest, full_name=None: CancellableRepo(happy_handler),
            )
    finally:
        timer.cancel()
        cancellation.reset(token)
    assert seen_cancel.is_set()


def test_run_git_detection_cancel_returns_promptly_with_wedged_scans(
    clean_db, tmp_path, monkeypatch
):
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

    release = threading.Event()
    started = threading.Event()

    class WedgedRepo(FakeRepo):
        def git(self, *args: str, timeout: float | None = None, stdin=None, env_extra=None) -> str:
            started.set()
            release.wait()
            return happy_handler(args)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    cancel = threading.Event()
    outcome: list[object] = []

    def drive() -> None:
        token = cancellation.bind(cancel.is_set)
        try:
            run_git_detection(
                engine,
                detect_run,
                make_spec(source_id, frozenset({"file"})),
                PACK,
                config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
                clone_fn=clone,
                repo_factory=lambda dest, full_name=None: WedgedRepo(happy_handler),
            )
            outcome.append(None)
        except BaseException as exc:
            outcome.append(exc)
        finally:
            cancellation.reset(token)

    thread = threading.Thread(target=drive)
    thread.start()
    try:
        assert started.wait(timeout=5)
        time.sleep(0.1)
        cancel.set()
        thread.join(timeout=3)
        assert not thread.is_alive()
        assert outcome and isinstance(outcome[0], RunCancelled)
    finally:
        release.set()
        thread.join(timeout=5)


def test_dead_repo_fails_fast_without_retries(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )
    attempts: list[str] = []

    def clone(full_name: str, dest: Path) -> None:
        attempts.append(full_name)
        if full_name == "octo/two":
            raise GitError(
                ["git", "clone"],
                128,
                "fatal: repository 'https://github.com/octo/two/' not found",
            )
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1, retry_delay=0.0),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert attempts.count("octo/two") == 1  # dead class: no inline retries
    failed = [item for item in payload.items if item.full_name == "octo/two"]
    assert failed and failed[0].detection["failure_class"] == "dead"
    assert payload.result_summary["repos_unavailable"] == 1


def test_transient_failure_gets_one_post_sweep_retry(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )
    attempts: list[str] = []

    def clone(full_name: str, dest: Path) -> None:
        attempts.append(full_name)
        if full_name == "octo/two" and attempts.count("octo/two") == 1:
            raise GitError(
                ["git", "clone"],
                128,
                "fatal: unable to access 'x': Could not resolve host: github.com",
            )
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(
            scan_root=str(tmp_path / "clones"), workers=1, attempts=1, retry_delay=0.0
        ),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert attempts.count("octo/two") == 2  # first try + retry wave
    assert payload.result_summary["repos_unavailable"] == 0


def test_unavailable_repos_listed_with_reasons(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )

    def clone(full_name: str, dest: Path) -> None:
        if full_name == "octo/two":
            raise RuntimeError("clone failed")
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(
            scan_root=str(tmp_path / "clones"), workers=1, attempts=1, retry_delay=0.0
        ),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert payload.result_summary["unavailable_repos"] == [
        {"full_name": "octo/two", "reason": "fatal"}
    ]
    assert payload.result_summary["unavailable_reasons"] == {"fatal": 1}


def test_per_repo_deletion_does_not_block_the_parent(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )
    removed: list[str] = []

    def tracking_remove(path):
        removed.append(str(path))
        _remove_tree(path)

    monkeypatch.setattr("detect.git_orchestrator._remove_tree", tracking_remove)
    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    assert len(removed) >= 3  # two per-repo dirs plus the final run-dir sweep


def test_run_git_detection_records_compact_repo_filter_facets(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    config = GitScanConfig(depth=100, keep=False, scan_root=str(tmp_path / "clones"), workers=1)
    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file", "commit_trailer", "branch"})),
        PACK,
        config=config,
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )
    with engine.connect() as connection:
        facets = set(
            connection.execute(
                text(
                    "SELECT repo_id, agent, channel FROM detection_repo_filters WHERE run_id = :run"
                ),
                {"run": detect_run},
            ).all()
        )
        expected = set(
            connection.execute(
                text(
                    "SELECT DISTINCT repo_id, agent, channel FROM detection_evidence"
                    " WHERE run_id = :run"
                ),
                {"run": detect_run},
            ).all()
        )
    assert facets == expected
    assert facets


def test_run_git_detection_streams_detections_from_the_database(clean_db, tmp_path, monkeypatch):
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

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    config = GitScanConfig(depth=100, keep=False, scan_root=str(tmp_path / "clones"), workers=1)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file", "commit_trailer", "branch"})),
        PACK,
        config=config,
        clone_fn=clone,
        repo_factory=lambda dest, full_name=None: FakeRepo(happy_handler),
    )

    assert payload.detections == []
    assert payload.detections_source is not None
    streamed = list(payload.detections_source())
    with engine.connect() as connection:
        expected = connection.execute(
            text("SELECT count(*) FROM detection_evidence WHERE run_id = :run"),
            {"run": detect_run},
        ).scalar_one()
    assert len(streamed) == expected > 0
    assert {row["full_name"] for row in streamed} == {"octo/one", "octo/two"}
    sample = streamed[0]
    assert set(sample) == {
        "full_name",
        "repo_id",
        "agent",
        "channel",
        "evidence",
        "pack_version",
        "run_id",
        "detected_at",
    }
    assert isinstance(sample["evidence"], dict)
    assert sample["run_id"] == detect_run
    assert sample["detected_at"] is not None
    assert payload.items[0].detection["agents"] == ["Claude Code"]


class AdmissionGate:
    """Gate double recording non-blocking probes and permits held."""

    def __init__(self, grants: bool = True) -> None:
        self.grants = grants
        self.acquires = 0
        self.releases = 0
        self.held = 0

    def acquire(self, *, timeout: float | None = None) -> bool:
        self.acquires += 1
        if not self.grants:
            return False
        self.held += 1
        return True

    def release(self) -> None:
        self.releases += 1
        self.held -= 1


def _candidate(name: str, repo_id: int = 1) -> dict:
    return {"full_name": name, "repo_id": repo_id, "stargazers": 10}


def _refs(count: int) -> RemoteRefs:
    return RemoteRefs(pr_refs={number: f"sha{number}" for number in range(count)}, head_refs={})


def _probe(mapping):
    def probe(full_name: str) -> RemoteRefs:
        outcome = mapping[full_name]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    return probe


def test_admit_skips_a_dead_repo_without_an_admission():
    pending = deque([_candidate("octo/gone")])
    dead_error = GitError(["ls-refs"], 128, "remote: Repository not found.")
    emitted: list = []

    admission = _admit(pending, _probe({"octo/gone": dead_error}), AdmissionGate(), emitted.append)

    assert admission is None
    assert len(emitted) == 1
    dead = emitted[0]
    assert dead.repo_id == 1
    assert dead.full_name == "octo/gone"
    assert dead.document["failure_class"] == "dead"
    assert dead.document["unavailable"] is True
    assert _failure_message(dead).startswith("octo/gone: GitError:")
    assert not pending


def test_admit_passes_a_transient_probe_failure_through_without_refs():
    probe = _probe({"octo/one": RemoteRefsUnavailable("ls-refs failed")})
    gate = AdmissionGate()

    admission = _admit(deque([_candidate("octo/one")]), probe, gate)

    assert admission == Admission(_candidate("octo/one"), None, False)
    assert (gate.acquires, gate.releases) == (0, 0)


def test_admit_passes_a_retryable_git_error_through_without_refs():
    probe = _probe({"octo/one": GitError(["ls-refs"], 128, "fatal: connection reset")})
    gate = AdmissionGate()

    admission = _admit(deque([_candidate("octo/one")]), probe, gate)

    assert admission == Admission(_candidate("octo/one"), None, False)
    assert (gate.acquires, gate.releases) == (0, 0)


def test_admit_requeues_a_monster_and_pops_the_tail():
    monster = _candidate("octo/monster")
    tail = _candidate("octo/tail", repo_id=2)
    pending = deque([monster, tail])
    gate = AdmissionGate(grants=False)

    admission = _admit(pending, _probe({"octo/monster": _refs(501)}), gate)

    assert admission == Admission(tail, None, False)
    requeued = list(pending)
    assert [entry.candidate for entry in requeued] == [monster]
    assert requeued[0].refs == _refs(501)  # carried for the next admission
    assert (gate.acquires, gate.releases) == (1, 0)  # failed attempt holds nothing


def test_admit_requeued_monster_is_not_re_probed(tmp_path, monkeypatch):
    monster = _candidate("octo/monster")
    pending = deque([monster, _candidate("octo/tail", repo_id=2)])
    refs = _refs(501)
    probed: list[str] = []

    def probe(full_name: str) -> RemoteRefs:
        probed.append(full_name)
        return refs

    _admit(pending, probe, AdmissionGate(grants=False))

    assert probed == ["octo/monster"]  # the tail is never probed here
    requeued = list(pending)
    assert [entry.candidate for entry in requeued] == [monster]
    assert requeued[0].refs is refs

    # A second admission of the requeued entry must not probe again, and the
    # carried refs must reach the submitted scan.
    seen: list[dict] = []

    def fake_pr(
        repo, pack, agents, *, depth, attempts, retry_delay, gate, refs, gate_reserved, session=None
    ):
        seen.append({"refs": refs, "gate_reserved": gate_reserved})
        return ChannelResult(status="ok")

    monkeypatch.setattr("detect.git_orchestrator.detect_pr_commits_local", fake_pr)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    second_gate = AdmissionGate(grants=False)
    admission = _admit(pending, probe, second_gate, None)
    assert admission is not None and admission.candidate is monster
    assert probed == ["octo/monster"]  # no re-probe of the requeued entry
    _scan_one(
        run_dir,
        GitScanConfig(attempts=1, retry_delay=0.0),
        make_spec(1, frozenset({"pr_metadata"})),
        PACK,
        frozenset({"pr_metadata"}),
        admission.candidate,
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
        pr_gate=second_gate,
        prefetched=admission.prefetched,
        gate_reserved=admission.gate_reserved,
    )
    assert seen == [{"refs": refs.pr_refs, "gate_reserved": False}]
    assert (second_gate.acquires, second_gate.releases) == (1, 0)  # no permit was taken


def test_admit_falls_back_to_the_sole_monster_when_the_gate_is_busy():
    monster = _candidate("octo/monster")
    pending = deque([monster])
    gate = AdmissionGate(grants=False)
    refs = _refs(501)

    admission = _admit(pending, _probe({"octo/monster": refs}), gate)

    assert admission == Admission(monster, refs, False)  # fetch path blocks on the gate
    assert list(pending) == []
    assert (gate.acquires, gate.releases) == (1, 0)


def test_admit_reserves_a_permit_for_a_monster_when_the_gate_grants():
    monster = _candidate("octo/monster")
    gate = AdmissionGate()

    admission = _admit(deque([monster]), _probe({"octo/monster": _refs(501)}), gate)

    assert admission == Admission(monster, _refs(501), True)
    assert (gate.acquires, gate.held) == (1, 1)


def test_admit_never_touches_the_gate_for_ordinary_repos():
    gate = AdmissionGate(grants=False)
    refs = _refs(500)

    admission = _admit(deque([_candidate("octo/one")]), _probe({"octo/one": refs}), gate)

    assert admission == Admission(_candidate("octo/one"), refs, False)
    assert (gate.acquires, gate.releases) == (0, 0)


def test_admit_drains_an_empty_queue():
    assert _admit(deque(), _probe({}), AdmissionGate()) is None


def test_admit_keeps_scanning_after_a_dead_repo_is_skipped():
    pending = deque([_candidate("octo/gone"), _candidate("octo/one", repo_id=2)])
    probe = _probe(
        {
            "octo/gone": GitError(["ls-refs"], 128, "remote: Repository not found."),
            "octo/one": _refs(3),
        }
    )
    emitted: list = []

    admission = _admit(pending, probe, AdmissionGate(), emitted.append)

    assert [scan.full_name for scan in emitted] == ["octo/gone"]
    assert admission == Admission(_candidate("octo/one", repo_id=2), _refs(3), False)
    assert not pending


def test_scan_one_releases_a_reserved_permit_in_finally(tmp_path, monkeypatch):
    gate = AdmissionGate()
    calls: list[dict] = []

    def fake_pr(
        repo, pack, agents, *, depth, attempts, retry_delay, gate, refs, gate_reserved, session=None
    ):
        calls.append({"refs": refs, "gate_reserved": gate_reserved})
        return ChannelResult(status="ok")

    monkeypatch.setattr("detect.git_orchestrator.detect_pr_commits_local", fake_pr)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    prefetched = _refs(501)
    scan = _scan_one(
        run_dir,
        GitScanConfig(),
        make_spec(1, frozenset({"pr_metadata"})),
        PACK,
        frozenset({"pr_metadata"}),
        _candidate("octo/one"),
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
        pr_gate=gate,
        prefetched=prefetched,
        gate_reserved=True,
    )

    assert scan.repo_id == 1
    assert calls == [{"refs": prefetched.pr_refs, "gate_reserved": True}]
    assert (gate.acquires, gate.releases, gate.held) == (0, 1, -1)


def test_scan_one_releases_a_reserved_permit_when_the_scan_raises(tmp_path):
    gate = AdmissionGate()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    def exploding_clone(full_name, dest):
        raise RuntimeError("clone exploded")

    with pytest.raises(RuntimeError, match="clone exploded"):
        _scan_one(
            run_dir,
            GitScanConfig(attempts=1, retry_delay=0.0),
            make_spec(1, frozenset({"file"})),
            PACK,
            frozenset({"file"}),
            _candidate("octo/one"),
            clone_one=exploding_clone,
            make_repo=lambda dest, full_name: FakeRepo(happy_handler),
            pr_gate=gate,
            gate_reserved=True,
        )

    assert (gate.acquires, gate.releases, gate.held) == (0, 1, -1)


def test_scan_one_leaves_the_gate_alone_without_a_reservation(tmp_path):
    gate = AdmissionGate()
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    _scan_one(
        run_dir,
        GitScanConfig(),
        make_spec(1, frozenset({"file"})),
        PACK,
        frozenset({"file"}),
        _candidate("octo/one"),
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
        pr_gate=gate,
    )

    assert (gate.acquires, gate.releases) == (0, 0)


def _recording_session(monkeypatch):
    opened: list = []
    closed: list = []

    class RecordingSession:
        @classmethod
        def open(cls, repo):
            instance = cls()
            opened.append(instance)
            return instance

        def close(self):
            closed.append(self)

    monkeypatch.setattr(repo_walk, "RepoWalkSession", RecordingSession)
    return opened, closed


def test_scan_one_shares_one_walk_session_across_file_history_and_pr(tmp_path, monkeypatch):
    opened, closed = _recording_session(monkeypatch)
    seen: list[tuple[str, object]] = []

    def fake_files(repo, pack, agents=None, *, session=None):
        seen.append(("file", session))
        return ChannelResult(status="ok")

    def fake_history(repo, pack, agents=None, *, limit=100, session=None):
        seen.append(("history", session))
        return {key: ChannelResult(status="ok") for key in ("author", "commit_trailer", "bot")}

    def fake_pr(
        repo, pack, agents, *, depth, attempts, retry_delay, gate, refs, gate_reserved, session=None
    ):
        seen.append(("pr", session))
        return ChannelResult(status="ok")

    monkeypatch.setattr("detect.git_orchestrator.detect_files_local", fake_files)
    monkeypatch.setattr("detect.git_orchestrator.detect_history_local", fake_history)
    monkeypatch.setattr("detect.git_orchestrator.detect_pr_commits_local", fake_pr)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    active = frozenset({"file", "author", "pr_metadata"})

    scan = _scan_one(
        run_dir,
        GitScanConfig(),
        make_spec(1, active),
        PACK,
        active,
        _candidate("octo/one"),
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
    )

    assert scan.repo_id == 1
    assert len(opened) == 1
    assert [name for name, _session in seen] == ["file", "history", "pr"]
    assert all(session is opened[0] for _name, session in seen)
    assert closed == opened


def test_scan_one_closes_the_walk_session_when_a_channel_fails(tmp_path, monkeypatch):
    opened, closed = _recording_session(monkeypatch)

    def exploding_files(repo, pack, agents=None, *, session=None):
        raise RuntimeError("file channel exploded")

    monkeypatch.setattr("detect.git_orchestrator.detect_files_local", exploding_files)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    with pytest.raises(RuntimeError, match="file channel exploded"):
        _scan_one(
            run_dir,
            GitScanConfig(),
            make_spec(1, frozenset({"file"})),
            PACK,
            frozenset({"file"}),
            _candidate("octo/one"),
            clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
            make_repo=lambda dest, full_name: FakeRepo(happy_handler),
        )

    assert len(opened) == 1
    assert closed == opened


def test_scan_one_suppresses_walk_session_close_failures(tmp_path, monkeypatch):
    class ExplodingCloseSession:
        @classmethod
        def open(cls, repo):
            return cls()

        def close(self):
            raise RuntimeError("close exploded")

    monkeypatch.setattr(repo_walk, "RepoWalkSession", ExplodingCloseSession)

    def fake_files(repo, pack, agents=None, *, session=None):
        assert session is not None
        return ChannelResult(status="ok")

    monkeypatch.setattr("detect.git_orchestrator.detect_files_local", fake_files)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    scan = _scan_one(
        run_dir,
        GitScanConfig(),
        make_spec(1, frozenset({"file"})),
        PACK,
        frozenset({"file"}),
        _candidate("octo/one"),
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
    )

    assert scan.repo_id == 1


def test_scan_one_degrades_when_the_walk_session_cannot_open(tmp_path, monkeypatch):
    attempts: list[int] = []
    sessions: list[object] = []

    class BrokenSession:
        @classmethod
        def open(cls, repo):
            attempts.append(1)
            raise repo_walk.WalkAnomaly("cat-file failed to start")

    monkeypatch.setattr(repo_walk, "RepoWalkSession", BrokenSession)

    def fake_files(repo, pack, agents=None, *, session=None):
        sessions.append(session)
        return ChannelResult(status="ok")

    def fake_history(repo, pack, agents=None, *, limit=100, session=None):
        sessions.append(session)
        return {key: ChannelResult(status="ok") for key in ("author", "commit_trailer", "bot")}

    monkeypatch.setattr("detect.git_orchestrator.detect_files_local", fake_files)
    monkeypatch.setattr("detect.git_orchestrator.detect_history_local", fake_history)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    active = frozenset({"file", "author"})

    scan = _scan_one(
        run_dir,
        GitScanConfig(),
        make_spec(1, active),
        PACK,
        active,
        _candidate("octo/one"),
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
    )

    assert scan.repo_id == 1
    assert sessions == [None, None]
    assert attempts == [1]


def test_scan_one_never_opens_a_walk_session_for_branch_only_scans(tmp_path, monkeypatch):
    class ExplodingSession:
        @classmethod
        def open(cls, repo):
            raise AssertionError("branch-only scans must not open a walk session")

    monkeypatch.setattr(repo_walk, "RepoWalkSession", ExplodingSession)
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    active = frozenset({"branch"})

    scan = _scan_one(
        run_dir,
        GitScanConfig(),
        make_spec(1, active),
        PACK,
        active,
        _candidate("octo/one"),
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
    )

    assert scan.repo_id == 1


class FakeOutQueue:
    """in-process stand-in for multiprocessing.Queue."""

    def __init__(self) -> None:
        self.messages: list = []

    def put(self, message) -> None:
        self.messages.append(message)


class FakeCancelEvent:
    def is_set(self) -> bool:
        return False


def _scan_main_isolated(slice_candidates, out_queue, cancel_event, *args):
    """_scan_worker_main binds the cancellation contextvar; never leak it.

    ``out_queue`` occupies positional slot 2 and ``cancel_event`` slot 3; the
    remaining positional args pass through unchanged.
    """
    token = cancellation.bind(cancel_event.is_set)
    try:
        _scan_worker_main(slice_candidates, out_queue, cancel_event, *args)
    finally:
        cancellation.reset(token)


def test_scan_worker_main_emits_a_failed_scan_for_a_dead_repo(tmp_path):
    dead_error = GitError(["ls-refs"], 128, "remote: Repository not found.")

    def probe(full_name: str) -> RemoteRefs:
        raise dead_error

    out_queue = FakeOutQueue()
    _scan_main_isolated(
        [_candidate("octo/gone")],
        out_queue,
        FakeCancelEvent(),
        GitScanConfig(keep=True, scan_root=str(tmp_path)),
        make_spec(1, frozenset({"file"})),
        PACK,
        str(tmp_path),
        1,
        local_values(),
        AdmissionGate(),
        probe,
    )

    assert len(out_queue.messages) == 1
    tag, scan, failure = out_queue.messages[0]
    assert tag == "scan"
    assert scan.full_name == "octo/gone"
    assert scan.document["failure_class"] == "dead"
    assert failure is not None and failure.startswith("octo/gone: GitError:")
    assert not (tmp_path / "octo__gone").exists()


def test_scan_worker_main_submits_with_prefetched_refs_and_reserved_permit(tmp_path, monkeypatch):
    seen: list[dict] = []

    def fake_scan_one(run_dir, cfg, spec, pack, active, candidate, **kwargs):
        seen.append({"candidate": candidate, **kwargs})
        return _failed_scan(candidate, GitError(["git"], 128, "synthetic"), failure_class="fatal")

    monkeypatch.setattr("detect.git_orchestrator._scan_one", fake_scan_one)
    gate = AdmissionGate()
    out_queue = FakeOutQueue()
    _scan_main_isolated(
        [_candidate("octo/monster")],
        out_queue,
        FakeCancelEvent(),
        GitScanConfig(keep=True, scan_root=str(tmp_path)),
        make_spec(1, frozenset({"pr_metadata"})),
        PACK,
        str(tmp_path),
        1,
        local_values(),
        gate,
        lambda full_name: _refs(501),
    )

    assert len(seen) == 1
    assert seen[0]["candidate"]["full_name"] == "octo/monster"
    assert seen[0]["prefetched"] == _refs(501)
    assert seen[0]["gate_reserved"] is True
    # The fake _scan_one never releases; the real release path is covered by
    # test_scan_one_releases_a_reserved_permit_in_finally.
    assert gate.acquires == 1 and gate.held == 1
    assert out_queue.messages and out_queue.messages[0][0] == "scan"


def test_git_scan_config_defaults_pr_gate_permits_to_32():
    assert GitScanConfig().pr_gate_permits == 32


def test_pr_gate_permits_from_env_reads_a_positive_override(monkeypatch):
    monkeypatch.setenv("GITCORPUS_PR_GATE", "64")
    assert pr_gate_permits_from_env() == 64


@pytest.mark.parametrize("raw", ["", " ", "abc", "0", "-5", "3.5"])
def test_pr_gate_permits_from_env_falls_back_to_32(monkeypatch, raw):
    monkeypatch.setenv("GITCORPUS_PR_GATE", raw)
    assert pr_gate_permits_from_env() == 32


def test_pr_gate_permits_from_env_defaults_to_32_when_unset(monkeypatch):
    monkeypatch.delenv("GITCORPUS_PR_GATE", raising=False)
    assert pr_gate_permits_from_env() == 32


class _GateRecorded(RuntimeError):
    """Stops the spawn path the moment the fleet gate is built."""


class _RecordingGateContext:
    def __init__(self) -> None:
        self.permits: list[int] = []

    def Queue(self):
        return object()

    def Event(self):
        return object()

    def Value(self, *_args):
        return object()

    def BoundedSemaphore(self, value):
        self.permits.append(value)
        raise _GateRecorded()


@pytest.mark.parametrize(("configured", "expected"), [(128, 128), (0, 1), (-4, 1)])
def test_run_git_detection_processes_builds_the_gate_with_the_configured_permits(
    tmp_path, monkeypatch, configured, expected
):
    context = _RecordingGateContext()
    monkeypatch.setattr(multiprocessing, "get_context", lambda name: context)
    with pytest.raises(_GateRecorded):
        _run_git_detection_processes(
            None,
            1,
            make_spec(1, frozenset()),
            PACK,
            GitScanConfig(pr_gate_permits=configured),
            tmp_path,
            tmp_path,
            [],
            0,
            [],
            _offline_refs,
        )
    assert context.permits == [expected]


def _phase_metrics_lines(directory: Path) -> list[dict]:
    rows: list[dict] = []
    for path in sorted(directory.glob("phase-metrics-*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            rows.append(json.loads(line))
    return rows


def test_phase_metrics_writer_appends_json_lines(monkeypatch, tmp_path):
    monkeypatch.setenv(phase_metrics.PHASE_METRICS_ENV, str(tmp_path / "metrics"))
    phase_metrics.write_phase_metrics(
        phase_metrics.RepoPhaseMetrics(full_name="octo/one", probe_ms=1.5)
    )
    phase_metrics.write_phase_metrics(phase_metrics.RepoPhaseMetrics(full_name="octo/two"))

    rows = _phase_metrics_lines(tmp_path / "metrics")
    assert [row["full_name"] for row in rows] == ["octo/one", "octo/two"]
    assert set(rows[0]) == {
        "full_name",
        "probe_ms",
        "clone_ms",
        "files_ms",
        "history_ms",
        "pr_listing_ms",
        "pr_fetch_ms",
        "walk_ms",
        "total_ms",
        "refs_count",
        "gated",
        "gate_wait_ms",
        "cat_file_spawns",
    }
    assert rows[0]["probe_ms"] == 1.5
    assert rows[0]["clone_ms"] is None


def test_phase_metrics_writer_is_silent_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv(phase_metrics.PHASE_METRICS_ENV, raising=False)
    phase_metrics.write_phase_metrics(phase_metrics.RepoPhaseMetrics(full_name="octo/one"))
    assert list(tmp_path.iterdir()) == []


def test_phase_metrics_writer_survives_a_write_failure(monkeypatch, tmp_path):
    target = tmp_path / "not-a-directory"
    target.write_text("filed", encoding="utf-8")
    monkeypatch.setenv(phase_metrics.PHASE_METRICS_ENV, str(target))
    phase_metrics.write_phase_metrics(phase_metrics.RepoPhaseMetrics(full_name="octo/one"))


def test_scan_one_appends_a_phase_metrics_line_when_enabled(tmp_path, monkeypatch):
    metrics_dir = tmp_path / "metrics"
    monkeypatch.setenv(phase_metrics.PHASE_METRICS_ENV, str(metrics_dir))
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    scan = _scan_one(
        run_dir,
        GitScanConfig(),
        make_spec(1, frozenset({"file"})),
        PACK,
        frozenset({"file"}),
        _candidate("octo/one"),
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
        probe_ms=12.5,
    )

    assert scan.repo_id == 1
    rows = _phase_metrics_lines(metrics_dir)
    assert len(rows) == 1
    row = rows[0]
    assert row["full_name"] == "octo/one"
    assert row["probe_ms"] == 12.5
    assert isinstance(row["clone_ms"], float)
    assert isinstance(row["files_ms"], float)
    assert isinstance(row["total_ms"], float)
    assert isinstance(row["cat_file_spawns"], int)
    assert row["history_ms"] is None
    assert row["pr_listing_ms"] is None
    assert row["pr_fetch_ms"] is None
    assert row["walk_ms"] is None
    assert row["refs_count"] is None
    assert row["gated"] is None
    assert row["gate_wait_ms"] is None


def test_scan_one_writes_no_metrics_when_the_env_is_unset(tmp_path, monkeypatch):
    monkeypatch.delenv(phase_metrics.PHASE_METRICS_ENV, raising=False)
    run_dir = tmp_path / "run"
    run_dir.mkdir()

    _scan_one(
        run_dir,
        GitScanConfig(),
        make_spec(1, frozenset({"file"})),
        PACK,
        frozenset({"file"}),
        _candidate("octo/one"),
        clone_one=lambda full_name, dest: dest.mkdir(parents=True, exist_ok=True),
        make_repo=lambda dest, full_name: FakeRepo(happy_handler),
    )

    assert not [path for path in tmp_path.rglob("phase-metrics-*.jsonl")]


def test_scan_worker_main_measures_and_forwards_probe_ms(tmp_path, monkeypatch):
    seen: list[dict] = []

    def fake_scan_one(run_dir, cfg, spec, pack, active, candidate, **kwargs):
        seen.append(kwargs)
        return _failed_scan(candidate, GitError(["git"], 128, "synthetic"), failure_class="fatal")

    def slow_probe(full_name: str) -> RemoteRefs:
        # 60ms clears Windows' 15.6ms monotonic tick so the elapsed reading
        # can never round to zero.
        time.sleep(0.06)
        return _offline_refs(full_name)

    monkeypatch.setattr("detect.git_orchestrator._scan_one", fake_scan_one)
    out_queue = FakeOutQueue()
    _scan_main_isolated(
        [_candidate("octo/one")],
        out_queue,
        FakeCancelEvent(),
        GitScanConfig(keep=True, scan_root=str(tmp_path)),
        make_spec(1, frozenset({"file"})),
        PACK,
        str(tmp_path),
        1,
        local_values(),
        AdmissionGate(),
        slow_probe,
    )

    assert len(seen) == 1
    assert seen[0]["probe_ms"] >= 20.0


def test_scan_worker_main_records_probe_metrics_for_dead_repos(tmp_path, monkeypatch):
    metrics_dir = tmp_path / "metrics"
    monkeypatch.setenv(phase_metrics.PHASE_METRICS_ENV, str(metrics_dir))
    dead_error = GitError(["ls-refs"], 128, "remote: Repository not found.")

    def probe(full_name: str) -> RemoteRefs:
        raise dead_error

    out_queue = FakeOutQueue()
    _scan_main_isolated(
        [_candidate("octo/gone")],
        out_queue,
        FakeCancelEvent(),
        GitScanConfig(keep=True, scan_root=str(tmp_path)),
        make_spec(1, frozenset({"file"})),
        PACK,
        str(tmp_path),
        1,
        local_values(),
        AdmissionGate(),
        probe,
    )

    rows = _phase_metrics_lines(metrics_dir)
    assert len(rows) == 1
    assert rows[0]["full_name"] == "octo/gone"
    assert rows[0]["probe_ms"] is not None
    assert rows[0]["clone_ms"] is None
