from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import text

from detect.orchestrator import DetectOptions
from detect.packs import Pack, Pattern, freeze_pack
from serve.detect import _persist_detection_pool_stats, build_detect_runner
from serve.detect_spec import detect_spec_to_dict
from serve.executor import RunPayload, RunPayloadItem, create_run
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
    monkeypatch.setattr("serve.detect.load_tokens", lambda: ["one", "two", "three", "four"])

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


def test_api_runner_uses_a_fixed_four_token_pool_with_twelve_workers(clean_db, monkeypatch):
    engine = clean_db()
    freeze_pack(engine, PACK)
    update_run_settings(
        engine,
        {
            "detect_concurrency": 64,
            "limiter_max_concurrent": 18,
            "detect_token_mode": "pool4",
        },
    )
    sentinel = RunPayload(total_count=0, items=[])
    captured: dict[str, object] = {}
    primary = SimpleNamespace()

    class FakePool:
        worker_limit = 12

        def __init__(self):
            self.primary = primary

        def preflight(self):
            captured["preflight"] = True

        def close(self):
            captured["closed"] = True

    fake_pool = FakePool()

    def fake_build_pool(engine_, tokens, channels, *, max_concurrent, file_core_calls):
        captured["tokens"] = list(tokens)
        captured["channels"] = channels
        captured["max_concurrent"] = max_concurrent
        captured["file_core_calls"] = file_core_calls
        return fake_pool

    def fake_run_detection(deps, run_id, spec, pack, *, config=None, token_pool=None):
        captured["deps"] = deps
        captured["concurrency"] = config.concurrency
        captured["pool_stats_reporter"] = config.pool_stats_reporter
        captured["pool"] = token_pool
        return sentinel

    monkeypatch.setattr("serve.detect.load_tokens", lambda: ["one", "two", "three", "four"])
    monkeypatch.setattr("serve.detect._build_detection_token_pool", fake_build_pool)
    monkeypatch.setattr("serve.detect.run_detection", fake_run_detection)

    spec = DetectOptions(
        source_run_id=1,
        pack_version="v1",
        agents=None,
        channels=frozenset({"file", "author"}),
    )
    runner = build_detect_runner(engine)
    assert runner(1, detect_spec_to_dict(spec)) is sentinel
    assert captured["tokens"] == ["one", "two", "three", "four"]
    assert captured["preflight"] is True
    assert captured["concurrency"] == 12
    assert captured["deps"] is primary
    assert captured["pool"] is fake_pool
    assert callable(captured["pool_stats_reporter"])
    assert captured["closed"] is True


def test_api_runner_rejects_an_incomplete_token_pool(clean_db, monkeypatch):
    engine = clean_db()
    freeze_pack(engine, PACK)
    update_run_settings(engine, {"detect_token_mode": "pool4"})
    monkeypatch.setattr("serve.detect.load_tokens", lambda: ["one", "two"])
    spec = DetectOptions(
        source_run_id=1,
        pack_version="v1",
        agents=None,
        channels=frozenset({"file"}),
    )
    runner = build_detect_runner(engine)
    try:
        runner(1, detect_spec_to_dict(spec))
    except ValueError as exc:
        assert "exactly four" in str(exc)
    else:
        raise AssertionError("two-token production pool should be rejected")


def test_live_pool_stats_are_persisted_only_while_a_run_is_running(clean_db):
    engine = clean_db()
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": 1},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=None,
    )
    first = {"tokens": 4, "accounts": [{"core_remaining": 4900}]}
    second = {"tokens": 4, "accounts": [{"core_remaining": 1}]}
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE runs SET status = 'running' WHERE id = :run"), {"run": run_id}
        )

    _persist_detection_pool_stats(engine, run_id, first)
    with engine.begin() as connection:
        connection.execute(text("UPDATE runs SET status = 'done' WHERE id = :run"), {"run": run_id})
    _persist_detection_pool_stats(engine, run_id, second)

    with engine.connect() as connection:
        summary = connection.scalar(
            text("SELECT result_summary FROM runs WHERE id = :run"), {"run": run_id}
        )
    assert summary == {"token_pool": first}


def test_runner_annotates_detected_repos_with_stored_owner_countries(clean_db, monkeypatch):
    engine = clean_db(
        owners=[{"id": 1, "login": "octo", "type": "User", "location_raw": "Germany"}],
        repos=[
            {
                "id": 1,
                "node_id": "n1",
                "full_name": "octo/one",
                "owner_id": 1,
                "name": "one",
                "visibility": "public",
            }
        ],
    )
    freeze_pack(engine, PACK)
    sentinel = RunPayload(
        total_count=1,
        items=[RunPayloadItem(repo_id=1, full_name="octo/one")],
    )

    monkeypatch.setattr("serve.detect.run_git_detection", lambda *args, **kwargs: sentinel)

    spec = DetectOptions(
        source_run_id=1,
        pack_version="v1",
        agents=None,
        channels=frozenset({"file"}),
        source="git",
    )
    runner = build_detect_runner(engine)
    result = runner(1, detect_spec_to_dict(spec))

    assert result.items[0].country_iso == "DE"
    assert result.items[0].geo_confidence == "name"
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT country_iso, geo_confidence FROM owners WHERE id = 1")
        ).one()
    assert tuple(row) == ("DE", "name")


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
