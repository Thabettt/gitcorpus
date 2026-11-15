from __future__ import annotations

import csv
import io
import json

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import insert, text

from serve.adoption_metrics import commit_depth, creation_cohorts, language_adoption, star_tiers
from serve.analysis import (
    ANALYSIS_METRICS,
    analysis_context,
    backfill_countries,
    backfill_countries_exhaustive,
)
from serve.app import create_app
from serve.countries import country_name
from serve.executor import EVIDENCE_CSV_HEADER, create_run
from store.models import DetectionEvidence, RunItem


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
            detect_runner_factory=lambda _engine: lambda run_id, spec: None,
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
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers,"
                " repo_created_at, commit_count, language, country_iso, geo_confidence)"
                " VALUES (:run, 1, 'octo/one', 10, '2024-01-01T00:00:00Z', 42,"
                " 'Rust', 'DE', 'name')"
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
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers,"
                " repo_created_at, commit_count, language, detection)"
                " VALUES (:run, 1, 'octo/one', 10, '2024-01-01T00:00:00Z', 42,"
                " 'Rust', CAST(:detection AS jsonb))"
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
    assert analysis_context(engine, detect_id, ("adoption",)) is not None

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
        snapshots = connection.execute(
            text("SELECT count(*) FROM analysis_snapshots WHERE run_id = :run"),
            {"run": detect_id},
        ).scalar_one()
    assert tuple(row) == ("DE", "name")
    assert snapshots == 0


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


def test_dashboard_from_existing_data_renders_new_metrics(clean):
    assert [metric.key for metric in ANALYSIS_METRICS] == [
        "agent_share",
        "generic_markers",
        "agents_by_country",
        "adoption",
        "adoption_by_country",
        "size_vs_adoption",
        "agent_debut",
        "fingerprint_debut",
        "country_wealth",
        "birth_cohort",
        "star_tiers",
        "commit_depth",
        "language_adoption",
    ]
    source = seed_source_run(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)

    response = client.get(
        f"/analysis/{detect_id}",
        params=[
            ("metric", "birth_cohort"),
            ("metric", "star_tiers"),
            ("metric", "commit_depth"),
            ("metric", "language_adoption"),
            ("metrics_present", "1"),
        ],
    )

    assert response.status_code == 200
    for section in (
        "analysis-birth-cohort",
        "analysis-star-tiers",
        "analysis-commit-depth",
        "analysis-language-adoption",
    ):
        assert f'id="{section}"' in response.text
    assert "10–99" in response.text
    assert "Unknown" in response.text


def test_visual_dashboard_renders_all_twelve_authoritative_metrics(clean):
    source = seed_source_run(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)

    response = client.get(f"/analysis/{detect_id}/dashboard")

    assert response.status_code == 200
    assert 'id="analysis-visual-dashboard"' in response.text
    assert 'id="analysis-dashboard-data"' in response.text
    assert 'src="/static/analysis-dashboard.js"' in response.text
    for key in (
        "agent-share",
        "agents-country",
        "adoption",
        "country-adoption",
        "size-adoption",
        "agent-debuts",
        "fingerprints",
        "country-wealth",
        "creation-cohorts",
        "star-tiers",
        "commit-depth",
        "language-adoption",
        "diagnostic-evidence-robustness",
        "diagnostic-observation-coverage",
        "diagnostic-owner-cluster",
        "diagnostic-robust-debut",
        "diagnostic-adoption-intensity",
        "diagnostic-multi-agent-co-use",
    ):
        assert f'data-chart-key="{key}"' in response.text
        assert f'data-open="viz-info-{key}"' in response.text
        assert f'id="viz-info-{key}"' in response.text

    assert "How to read" in response.text
    assert "What you are looking at" in response.text
    assert "Key terms in this figure" in response.text
    assert "For example." in response.text
    assert "Keep in mind." in response.text


def test_analysis_report_exposes_all_six_authoritative_diagnostics(clean):
    source = seed_source_run(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)

    response = client.get(f"/analysis/{detect_id}")

    assert response.status_code == 200
    for section in (
        "analysis-diagnostic-evidence",
        "analysis-diagnostic-coverage",
        "analysis-diagnostic-owner",
        "analysis-diagnostic-debut",
        "analysis-diagnostic-intensity",
        "analysis-diagnostic-co-use",
    ):
        assert f'id="{section}"' in response.text
    assert "Broad–strict gap" in response.text
    assert "Users and Organizations are separate" in response.text


def test_stratified_metrics_use_explicit_eligible_denominators(clean_db):
    engine = clean_db(
        owners=[{"id": 1, "login": "octo", "type": "User"}],
        repos=[
            {
                "id": repo_id,
                "node_id": f"n{repo_id}",
                "full_name": f"octo/r{repo_id}",
                "owner_id": 1,
                "name": f"r{repo_id}",
                "visibility": "public",
            }
            for repo_id in range(1, 8)
        ],
    )
    source = create_run(engine, {"q": "test"}, api_version="2022-11-28")
    detect = create_run(
        engine,
        {"kind": "detect", "source_run_id": source},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source,
    )
    source_rows = [
        (1, 0, "2024-01-01T00:00:00Z", 10, "Python"),
        (2, 5, "2025-02-01T00:00:00Z", 50, "Python"),
        (3, 20, "2025-05-01T00:00:00Z", 200, "Rust"),
        (4, 20, "2025-05-01T00:00:00Z", 200, "Rust"),
        (5, None, None, None, None),
        (6, 20, "2025-05-01T00:00:00Z", 200, "Rust"),
        (7, 20, "2025-05-01T00:00:00Z", 200, "Rust"),
    ]
    documents = {
        1: {
            "agents": ["Claude Code"],
            "channels": {"file": "ok", "commit_trailer": "ok"},
            "unavailable": False,
            "commit_ratio": 0.2,
            "history_coverage": 1.0,
            "history_complete": True,
        },
        2: {
            "agents": [],
            "channels": {"file": "ok", "commit_trailer": "ok"},
            "unavailable": False,
            "commit_ratio": 0.0,
            "history_coverage": 1.0,
            "history_complete": True,
        },
        3: {
            "agents": ["Codex"],
            "channels": {"commit_trailer": "ok"},
            "unavailable": False,
            "commit_ratio": 0.05,
            "history_coverage": 0.5,
            "history_complete": False,
        },
        4: {
            "agents": ["Claude Code"],
            "channels": {"file": "ok", "commit_trailer": "ok"},
            "unavailable": True,
            "commit_ratio": 0.5,
            "history_coverage": 0.5,
            "history_complete": False,
        },
        5: {
            "agents": ["Aider"],
            "channels": {"file": "ok"},
            "unavailable": False,
            "commit_ratio": None,
            "history_coverage": None,
            "history_complete": None,
        },
        6: {
            "agents": [],
            "channels": {"file": "ok", "commit_trailer": "ok"},
            "unavailable": False,
            "commit_ratio": 0.0,
            "history_coverage": 1.0,
            "history_complete": True,
        },
        7: {
            "agents": [],
            "channels": {"file": "partial", "commit_trailer": "ok"},
            "unavailable": False,
            "commit_ratio": 0.0,
            "history_coverage": 1.0,
            "history_complete": True,
        },
    }
    with engine.begin() as connection:
        connection.execute(
            insert(RunItem),
            [
                {
                    "run_id": source,
                    "repo_id": repo_id,
                    "full_name": f"octo/r{repo_id}",
                    "stargazers": stars,
                    "repo_created_at": created,
                    "commit_count": commits,
                    "language": language,
                }
                for repo_id, stars, created, commits, language in source_rows
            ],
        )
        connection.execute(
            insert(RunItem),
            [
                {
                    "run_id": detect,
                    "repo_id": repo_id,
                    "full_name": f"octo/r{repo_id}",
                    # Leave metadata empty to verify frozen source fallback.
                    "detection": documents[repo_id],
                }
                for repo_id, *_rest in source_rows
            ],
        )
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('metrics-pack', '[]', '[]', '[]', '[]')"
            )
        )
        connection.execute(
            insert(DetectionEvidence),
            [
                {
                    "run_id": detect,
                    "repo_id": repo_id,
                    "agent": agent,
                    "channel": "file",
                    "evidence": {"path": path, "source": "tree"},
                    "pack_version": "metrics-pack",
                }
                for repo_id, agent, path in (
                    (1, "Claude Code", "CLAUDE.md"),
                    (5, "Aider", ".aider.conf.yml"),
                )
            ],
        )

    stars = {row["bucket"]: row for row in star_tiers(engine, detect)}
    assert stars["10–99"]["repos"] == 4
    assert stars["10–99"]["readable"] == 2
    assert stars["10–99"]["adoption"] == {
        "count": 1,
        "eligible": 2,
        "percent": 50.0,
        "ci_low": 9.5,
        "ci_high": 90.5,
    }
    assert stars["Unknown"]["adoption"]["count"] == 1

    commits = {row["bucket"]: row for row in commit_depth(engine, detect)}
    assert commits["100–499"]["recent_adoption"]["count"] == 1
    assert commits["100–499"]["recent_adoption"]["eligible"] == 2
    assert commits["100–499"]["median_coverage"] == 75.0
    assert commits["100–499"]["full_history"] == 1
    assert commits["Unknown"]["repos"] == 1

    cohorts = {row["cohort"]: row for row in creation_cohorts(engine, detect)["rows"]}
    assert cohorts["Existing before cutoff"]["adoption"]["percent"] == 100.0
    assert cohorts["2025-Q2"]["adoption"]["percent"] == 50.0

    languages = {row["language"]: row for row in language_adoption(engine, detect)}
    assert languages["Rust"]["adoption"]["eligible"] == 2
    assert languages["Rust"]["adoption"]["percent"] == 50.0
    assert languages["Python"]["top_agent"] == "Claude Code"
    assert languages["Unknown"]["file_adoption"]["percent"] == 100.0


def test_analysis_rejects_a_find_run(clean):
    source = seed_source_run(clean)
    client = make_client(clean)

    response = client.get(f"/analysis/{source}")

    assert response.status_code == 404


def test_exports_include_country_names(clean):
    source = seed_source_run(clean)
    detect_id = seed_detect_run(clean, source)
    backfill_countries(clean, detect_id, fetch=False)
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
