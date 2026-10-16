from __future__ import annotations

from detect.orchestrator import DetectOptions
from detect.packs import Pack, Pattern, freeze_pack
from serve.detect import build_detect_runner
from serve.detect_spec import detect_spec_to_dict
from serve.executor import RunPayload

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
