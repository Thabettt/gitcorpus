from __future__ import annotations

import csv
import io
import json

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from serve.analysis import (
    ANALYSIS_METRICS,
    backfill_countries,
    backfill_countries_exhaustive,
)
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


def test_country_backfill_syncs_saved_rows_even_with_no_pending_owners(clean_db):
    from enrich.geo_resolver import GEO_RESOLVER_VERSION

    engine = clean_db(
        owners=[
            {
                "id": 1,
                "login": "octo",
                "type": "User",
                "country_iso": "DE",
                "geo_confidence": "name",
                "geo_version": GEO_RESOLVER_VERSION,
            }
        ],
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
    source = seed_source_run(engine)
    detect_id = seed_detect_run(engine, source)

    result = backfill_countries(engine, detect_id, fetch=False)

    assert result["owners"] == 0
    assert result["updated"] == 1
    assert result["remaining"] == 0
    with engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT country_iso, geo_confidence FROM run_items"
                " WHERE run_id = :run AND repo_id = 1"
            ),
            {"run": detect_id},
        ).one()
    assert tuple(row) == ("DE", "name")


def test_country_backfill_resolves_stored_locations_into_saved_rows(clean_db):
    engine = clean_db(
        owners=[
            {
                "id": 1,
                "login": "octo",
                "type": "User",
                "location_raw": "Germany",
            }
        ],
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
    source = seed_source_run(engine)
    detect_id = seed_detect_run(engine, source)

    result = backfill_countries(engine, detect_id, fetch=False)

    assert result["resolved"] == 1
    assert result["updated"] >= 1
    assert result["remaining"] == 0
    with engine.connect() as connection:
        owner = connection.execute(
            text("SELECT country_iso, geo_confidence FROM owners WHERE id = 1")
        ).one()
        detect_items = connection.execute(
            text("SELECT country_iso FROM run_items WHERE run_id = :run"),
            {"run": detect_id},
        ).all()
        source_items = connection.execute(
            text("SELECT country_iso FROM run_items WHERE run_id = :run"),
            {"run": source},
        ).all()
    assert tuple(owner) == ("DE", "name")
    assert detect_items == [("DE",)]
    assert source_items == [("DE",)]


def test_country_backfill_resolves_all_stored_locations_beyond_the_limit(clean_db):
    """The API limit must never cap owners that resolve locally for free."""
    owners = [
        {"id": owner_id, "login": f"octo{owner_id}", "type": "User", "location_raw": "Germany"}
        for owner_id in (1, 2, 3)
    ]
    repos = [
        {
            "id": repo_id,
            "node_id": f"n{repo_id}",
            "full_name": f"octo{repo_id}/one",
            "owner_id": repo_id,
            "name": "one",
            "visibility": "public",
        }
        for repo_id in (1, 2, 3)
    ]
    engine = clean_db(owners=owners, repos=repos)
    source = seed_source_run(engine)
    detect_id = seed_detect_run(engine, source)
    with engine.begin() as connection:
        for repo_id in (2, 3):
            for run_id in (source, detect_id):
                connection.execute(
                    text(
                        "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                        " VALUES (:run, :repo, :name, 10)"
                    ),
                    {"run": run_id, "repo": repo_id, "name": f"octo{repo_id}/one"},
                )

    result = backfill_countries(engine, detect_id, fetch=False, limit=1)

    assert result["owners"] == 3
    assert result["resolved"] == 3
    assert result["remaining"] == 0
    with engine.connect() as connection:
        countries = connection.execute(
            text("SELECT country_iso FROM run_items WHERE run_id = :run ORDER BY repo_id"),
            {"run": detect_id},
        ).all()
    assert countries == [("DE",), ("DE",), ("DE",)]


def test_country_backfill_keeps_owners_without_signal_pending(clean_db):
    engine = clean_db(
        owners=[
            {"id": 1, "login": "octo", "type": "User", "location_raw": "Germany"},
            {"id": 2, "login": "blank", "type": "User", "location_raw": None},
        ],
        repos=[
            {
                "id": repo_id,
                "node_id": f"n{repo_id}",
                "full_name": f"owner{repo_id}/one",
                "owner_id": repo_id,
                "name": "one",
                "visibility": "public",
            }
            for repo_id in (1, 2)
        ],
    )
    source = seed_source_run(engine)
    detect_id = seed_detect_run(engine, source)
    with engine.begin() as connection:
        for run_id in (source, detect_id):
            connection.execute(
                text(
                    "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                    " VALUES (:run, 2, 'owner2/one', 10)"
                ),
                {"run": run_id},
            )

    result = backfill_countries(engine, detect_id, fetch=False, limit=500)

    assert result["owners"] == 1
    assert result["resolved"] == 1
    assert result["remaining"] == 1
    with engine.connect() as connection:
        blank = connection.execute(
            text("SELECT country_iso, geo_confidence, geo_version FROM owners WHERE id = 2")
        ).one()
    assert tuple(blank) == (None, None, None)


def test_country_backfill_exhaustive_drains_every_batch(monkeypatch):
    from serve import analysis

    passes = iter(
        [
            {
                "owners": 2,
                "fetched": 2,
                "resolved": 1,
                "unmatched": 1,
                "updated": 2,
                "remaining": 3,
            },
            {
                "owners": 1,
                "fetched": 1,
                "resolved": 1,
                "unmatched": 0,
                "updated": 1,
                "remaining": 0,
            },
        ]
    )
    monkeypatch.setattr(analysis, "backfill_countries", lambda *args, **kwargs: next(passes))

    result = backfill_countries_exhaustive(object(), 1)

    assert result == {
        "owners": 3,
        "fetched": 3,
        "resolved": 2,
        "unmatched": 1,
        "updated": 3,
        "remaining": 0,
    }


def test_country_backfill_exhaustive_stops_when_no_progress(monkeypatch):
    from serve import analysis

    monkeypatch.setattr(
        analysis,
        "backfill_countries",
        lambda *args, **kwargs: {
            "owners": 1,
            "fetched": 0,
            "resolved": 0,
            "unmatched": 0,
            "updated": 0,
            "remaining": 5,
        },
    )

    result = backfill_countries_exhaustive(object(), 1)

    assert result["remaining"] == 5
    assert result["owners"] == 1


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
