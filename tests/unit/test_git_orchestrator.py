from __future__ import annotations

import os
import shutil
import subprocess
import threading
import time
from pathlib import Path

import pytest
from sqlalchemy import text

from detect.channels import ChannelResult
from detect.git_orchestrator import GitScanConfig, _remove_tree, run_git_detection
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
        self.calls: list[tuple[str, ...]] = []

    def git(self, *args: str, timeout: float | None = None, stdin=None) -> str:
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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

    def repo_factory(dest: Path):
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
        repo_factory=lambda dest: FakeRepo(handler),
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
    captured: dict[str, int] = {}

    def fake_pr(repo, pack, agents, *, depth, attempts, retry_delay, walk_workers, walk_pool=None):
        captured.update(
            depth=depth,
            attempts=attempts,
            retry_delay=retry_delay,
            walk_workers=walk_workers,
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
            walk_workers=3,
        ),
        clone_fn=clone,
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )
    assert captured == {"depth": 100, "attempts": 2, "retry_delay": 0.5, "walk_workers": 3}


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

    monkeypatch.setattr("detect.git_orchestrator._spawn_rmdir", lambda path: None)
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
        def git(self, *args: str, timeout: float | None = None, stdin=None) -> str:
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
        def git(self, *args: str, timeout: float | None = None, stdin=None) -> str:
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
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
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )
    assert payload.result_summary["unavailable_repos"] == [
        {"full_name": "octo/two", "reason": "fatal"}
    ]
    assert payload.result_summary["unavailable_reasons"] == {"fatal": 1}
