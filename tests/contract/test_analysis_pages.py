from __future__ import annotations

import csv
import io
import json

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from serve.analysis import ANALYSIS_METRICS
from serve.app import create_app
from serve.countries import country_name
from serve.executor import EVIDENCE_CSV_HEADER


@pytest.fixture(scope="module", autouse=True)
def schema(alembic_config):
    command.upgrade(alembic_config, "head")


@pytest.fixture()
def clean(clean_db):
    return clean_db(
        owners=[{"id": 1, "login": "octo", "type": "User", "country_iso": "DE"}],
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


def make_client(engine):
    def runner_factory(_engine):
        def runner(_run_id, _spec):
            raise AssertionError("the find runner must not run in analysis tests")

        return runner

    return TestClient(
        create_app(
            engine=engine,
            runner_factory=runner_factory,
            detect_runner_factory=lambda _engine: (lambda run_id, spec: None),
            runs_root="runs",
            clone_root="clones",
            redis_ping=lambda: True,
            token_present=lambda: True,
        )
    )


def seed_source_run(engine) -> int:
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, finished_at)"
                " VALUES ('find-analysis', '{\"q\": \"rust\"}'::jsonb, '2022-11-28', 'done', now())"
                " RETURNING id"
            )
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers, country_iso,"
                " geo_confidence) VALUES (:run, 1, 'octo/one', 10, 'DE', 'name')"
            ),
            {"run": run_id},
        )
    return int(run_id)


def seed_detect_run(engine, source_id: int) -> int:
    spec = {
        "version": 1,
        "kind": "detect",
        "source_run_id": source_id,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    summary = {
        "repos_scanned": 1,
        "repos_with_signal": 1,
        "repos_unavailable": 0,
        "agents": {"Claude Code": 1},
        "channels": {"file": 1},
        "pack_version": "test-pack",
        "agents_selected": "all",
        "windows": {"commits": 100, "prs": 100, "issues": 100},
        "commit_ratio": 1.0,
        "adoption_level": "pervasive",
        "first_signal_at": "2026-01-02T00:00:00Z",
        "partial_channels": {},
    }
    detection = {
        "agents": ["Claude Code"],
        "channels": {"file": "ok"},
        "unavailable": False,
        "first_signal_at": "2026-01-02T00:00:00Z",
        "commit_ratio": 1.0,
        "adoption_level": "pervasive",
        "notes": [],
    }
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('test-pack',"
                ' \'[{"pattern": "noreply@anthropic\\\\.com", "agent": "Claude Code"}]\'::jsonb,'
                ' \'[{"pattern": "CLAUDE\\\\.md", "agent": "Claude Code"}]\'::jsonb,'
                ' \'[{"pattern": "codex/", "agent": "Codex"}]\'::jsonb,'
                " '[]'::jsonb) ON CONFLICT (version) DO NOTHING"
            )
        )
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, kind,"
                " source_run_id, result_summary, finished_at)"
                " VALUES ('detect-analysis', CAST(:spec AS jsonb), '2022-11-28', 'done',"
                " 'detect', :src, CAST(:summary AS jsonb), now()) RETURNING id"
            ),
            {"src": source_id, "spec": json.dumps(spec), "summary": json.dumps(summary)},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers, detection)"
                " VALUES (:run, 1, 'octo/one', 10, CAST(:detection AS jsonb))"
            ),
            {"run": run_id, "detection": json.dumps(detection)},
        )
        connection.execute(
            text(
                "INSERT INTO detection_evidence (run_id, repo_id, agent, channel, evidence,"
                " pack_version) VALUES (:run, 1, 'Claude Code', 'file',"
                " '{\"path\": \"CLAUDE.md\"}'::jsonb, 'test-pack')"
            ),
            {"run": run_id},
        )
        connection.execute(
            text(
                "INSERT INTO detection_repo_filters (run_id, repo_id, agent, channel)"
                " VALUES (:run, 1, 'Claude Code', 'file')"
            ),
            {"run": run_id},
        )
    return int(run_id)


def test_analysis_page_lists_finished_detections(clean):
    source = seed_source_run(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)

    response = client.get("/analysis")

    assert response.status_code == 200
    assert f'href="/analysis/{detect_id}"' in response.text
    assert "What to analyze" in response.text


def test_analysis_report_renders_metrics_and_countries(clean):
    source = seed_source_run(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)

    response = client.get(f"/analysis/{detect_id}")

    assert response.status_code == 200
    assert "Agent share" in response.text
    assert "Agent use by country" in response.text
    assert "Germany" in response.text
    assert "100.0%" in response.text
    assert f"/runs/{source}" in response.text


def test_analysis_metric_selection_narrows_the_report(clean):
    source = seed_source_run(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)

    response = client.get(
        f"/analysis/{detect_id}", params={"metric": "adoption", "metrics_present": "1"}
    )

    assert response.status_code == 200
    assert 'id="analysis-adoption"' in response.text
    assert 'id="analysis-agent-share"' not in response.text


def test_analysis_rejects_a_find_run(clean):
    source = seed_source_run(clean)
    client = make_client(clean)

    response = client.get(f"/analysis/{source}")

    assert response.status_code == 404


def test_exports_include_country_names(clean):
    source = seed_source_run(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)

    search_csv = client.get(f"/runs/{source}/export?format=csv").content.decode("utf-8-sig")
    search_rows = list(csv.DictReader(io.StringIO(search_csv)))
    assert search_rows[0]["country_iso"] == "DE"
    assert search_rows[0]["country"] == "Germany"

    search_json = client.get(f"/runs/{source}/export?format=json").json()
    assert search_json["items"][0]["country"] == "Germany"

    repo_csv = client.get(f"/runs/{detect_id}/export?format=csv").content.decode("utf-8-sig")
    repo_rows = list(csv.DictReader(io.StringIO(repo_csv)))
    assert repo_rows[0]["country_iso"] == "DE"
    assert repo_rows[0]["country"] == "Germany"

    evidence_csv = client.get(f"/runs/{detect_id}/export?format=detections").content.decode(
        "utf-8-sig"
    )
    assert next(csv.reader(io.StringIO(evidence_csv))) == EVIDENCE_CSV_HEADER
    evidence_rows = list(csv.DictReader(io.StringIO(evidence_csv)))
    assert evidence_rows[0]["country_iso"] == "DE"
    assert evidence_rows[0]["country"] == "Germany"

    evidence_json = client.get(f"/runs/{detect_id}/export?format=detections-json").json()
    assert evidence_json[0]["country_iso"] == "DE"
    assert evidence_json[0]["country"] == "Germany"

    assert country_name("DE") == "Germany"
    assert "country_wealth" in {metric.key for metric in ANALYSIS_METRICS}
