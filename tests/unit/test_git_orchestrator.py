from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import text

from detect.git_orchestrator import GitScanConfig, run_git_detection
from detect.gitio import GitError, GitRepo
from detect.orchestrator import DetectOptions
from detect.packs import Pack, Pattern, freeze_pack
from enrich.cloner import MARKER_NAME
from lib import cancellation
from lib.cancellation import RunCancelled
from serve.executor import create_run


class FakeRepo(GitRepo):
    """GitRepo whose git() answers from a canned handler."""

    def __init__(self, handler):
        super().__init__(Path())
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )
    assert clones == []


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
        def git(self, *args: str) -> str:
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
                repo_factory=lambda dest: CancellableRepo(happy_handler),
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
        def git(self, *args: str) -> str:
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
                repo_factory=lambda dest: WedgedRepo(happy_handler),
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
