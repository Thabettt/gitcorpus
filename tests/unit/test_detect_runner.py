from __future__ import annotations

from types import SimpleNamespace

from detect.orchestrator import DetectOptions
from detect.packs import Pack, Pattern, freeze_pack
from serve.detect import build_detect_runner
from serve.detect_spec import detect_spec_to_dict
from serve.executor import RunPayload
from store.settings import update_run_settings

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


def test_git_runner_uses_detect_concurrency(clean_db, monkeypatch):
    engine = clean_db()
    freeze_pack(engine, PACK)
    update_run_settings(engine, {"detect_concurrency": 64, "limiter_max_concurrent": 18})
    sentinel = RunPayload(total_count=0, items=[])
    captured: dict[str, int] = {}

    def fake_git(*args, config=None, **kwargs):
        captured["workers"] = config.workers
        return sentinel

    monkeypatch.setattr("serve.detect.run_git_detection", fake_git)

    spec = DetectOptions(
        source_run_id=1,
        pack_version="v1",
        agents=None,
        channels=frozenset({"file"}),
        source="git",
    )
    runner = build_detect_runner(engine)
    assert runner(1, detect_spec_to_dict(spec)) is sentinel
    assert captured["workers"] == 64


def test_api_runner_bounds_detect_concurrency_by_the_request_limit(clean_db, monkeypatch):
    engine = clean_db()
    freeze_pack(engine, PACK)
    update_run_settings(engine, {"detect_concurrency": 64, "limiter_max_concurrent": 18})
    sentinel = RunPayload(total_count=0, items=[])
    captured: dict[str, int] = {}

    def fake_build_deps(engine_, *, max_concurrent):
        captured["max_concurrent"] = max_concurrent
        return SimpleNamespace(client=SimpleNamespace(close=lambda: None))

    def fake_run_detection(deps, run_id, spec, pack, *, config=None):
        captured["concurrency"] = config.concurrency
        return sentinel

    monkeypatch.setattr("serve.runner.build_deps", fake_build_deps)
    monkeypatch.setattr("serve.detect.run_detection", fake_run_detection)

    spec = DetectOptions(
        source_run_id=1,
        pack_version="v1",
        agents=None,
        channels=frozenset({"file"}),
    )
    runner = build_detect_runner(engine)
    assert runner(1, detect_spec_to_dict(spec)) is sentinel
    assert captured["max_concurrent"] == 18
    assert captured["concurrency"] == 18


def test_detect_clone_root_env_override(monkeypatch):
    from serve.detect import detect_clone_root

    monkeypatch.delenv("GITCORPUS_CLONES_ROOT", raising=False)
    assert detect_clone_root() == "clones"
    monkeypatch.setenv("GITCORPUS_CLONES_ROOT", r"D:\gitcrawl-clones")
    assert detect_clone_root() == r"D:\gitcrawl-clones"


def test_git_runner_passes_the_clone_root_to_the_scan_config(clean_db, monkeypatch):
    engine = clean_db()
    freeze_pack(engine, PACK)
    sentinel = RunPayload(total_count=0, items=[])
    captured: dict[str, str] = {}

    def fake_git(*args, config=None, **kwargs):
        captured["scan_root"] = config.scan_root
        return sentinel

    monkeypatch.setattr("serve.detect.run_git_detection", fake_git)
    monkeypatch.setenv("GITCORPUS_CLONES_ROOT", r"D:\gitcrawl-clones")

    spec = DetectOptions(
        source_run_id=1,
        pack_version="v1",
        agents=None,
        channels=frozenset({"file"}),
        source="git",
    )
    runner = build_detect_runner(engine)
    assert runner(1, detect_spec_to_dict(spec)) is sentinel
    assert captured["scan_root"] == r"D:\gitcrawl-clones"
