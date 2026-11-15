from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic import command
from sqlalchemy import text

from serve import analysis


@pytest.fixture(scope="module", autouse=True)
def schema(alembic_config):
    command.upgrade(alembic_config, "head")


@pytest.fixture()
def detect_run(clean_db):
    engine = clean_db()
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, kind,"
                " finished_at) VALUES ('analysis-cache',"
                ' \'{"kind":"detect","channels":["file"]}\'::jsonb,'
                " '2022-11-28', 'done', 'detect', now()) RETURNING id"
            )
        ).scalar_one()
    return engine, int(run_id)


def test_snapshot_builds_once_and_warm_reads_do_not_scan_sources(detect_run, monkeypatch):
    engine, run_id = detect_run
    calls = 0

    def build(_engine, requested):
        nonlocal calls
        calls += 1
        assert requested == run_id
        return {"totals": {"scanned": 1}, "country": {}, "results": {}, "diagnostics": {}}

    monkeypatch.setattr(analysis, "_analysis_payload", build)
    run = analysis._run_row(engine, run_id)

    first, first_metadata = analysis.analysis_payload(engine, run)
    second, second_metadata = analysis.analysis_payload(engine, run)

    assert first == second
    assert first_metadata["status"] == "built"
    assert second_metadata["status"] == "hit"
    assert calls == 1
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM analysis_snapshots WHERE run_id = :run"),
                {"run": run_id},
            ).scalar_one()
            == 1
        )


def test_snapshot_version_and_finished_time_are_part_of_validity(detect_run, monkeypatch):
    engine, run_id = detect_run
    calls = 0

    def build(_engine, _requested):
        nonlocal calls
        calls += 1
        return {
            "totals": {"scanned": calls},
            "country": {},
            "results": {},
            "diagnostics": {},
        }

    monkeypatch.setattr(analysis, "_analysis_payload", build)
    run = analysis._run_row(engine, run_id)
    analysis.analysis_payload(engine, run)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE analysis_snapshots SET schema_version = 'stale' WHERE run_id = :run"),
            {"run": run_id},
        )
    version_rebuild, _metadata = analysis.analysis_payload(engine, run)
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE runs SET finished_at = finished_at + interval '1 second' WHERE id = :run"),
            {"run": run_id},
        )
    finished_rebuild, _metadata = analysis.analysis_payload(
        engine, analysis._run_row(engine, run_id)
    )

    assert version_rebuild["totals"]["scanned"] == 2
    assert finished_rebuild["totals"]["scanned"] == 3
    assert calls == 3


def test_explicit_invalidation_removes_snapshot(detect_run, monkeypatch):
    engine, run_id = detect_run
    monkeypatch.setattr(
        analysis,
        "_analysis_payload",
        lambda _engine, _run: {
            "totals": {},
            "country": {},
            "results": {},
            "diagnostics": {},
        },
    )
    analysis.analysis_payload(engine, analysis._run_row(engine, run_id))

    assert analysis.invalidate_analysis_snapshot(engine, run_id) == 1
    assert analysis.invalidate_analysis_snapshot(engine, run_id) == 0


def test_concurrent_cold_requests_share_one_build(detect_run, monkeypatch):
    engine, run_id = detect_run
    calls = 0
    calls_lock = threading.Lock()

    def build(_engine, _requested):
        nonlocal calls
        with calls_lock:
            calls += 1
        time.sleep(0.1)
        return {"totals": {}, "country": {}, "results": {}, "diagnostics": {}}

    monkeypatch.setattr(analysis, "_analysis_payload", build)
    run = analysis._run_row(engine, run_id)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _index: analysis.analysis_payload(engine, run), range(2)))

    assert calls == 1
    assert sorted(metadata["status"] for _payload, metadata in outcomes) == ["built", "hit"]
