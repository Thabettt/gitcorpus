from __future__ import annotations

import json

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from serve.app import create_app
from serve.detect import (
    DETECTION_REPO_EVIDENCE_CAP,
    DETECTION_REPOS_PAGE_SIZE,
    latest_detect_for_run,
)


@pytest.fixture(scope="module", autouse=True)
def schema(alembic_config):
    command.upgrade(alembic_config, "head")


@pytest.fixture()
def clean(clean_db):
    return clean_db(
        owners=[{"id": 1, "login": "octo", "type": "User"}],
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


def seed_find_run(engine, status="done") -> int:
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, finished_at)"
                " VALUES ('find-hash', '{\"q\": \"rust\"}'::jsonb, '2022-11-28', :status, now())"
                " RETURNING id"
            ),
            {"status": status},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                " VALUES (:run, 1, 'octo/one', 10)"
            ),
            {"run": run_id},
        )
    return int(run_id)


def seed_pack(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('test-pack',"
                ' \'[{"pattern": "noreply@anthropic\\\\.com", "agent": "Claude Code"}]\'::jsonb,'
                ' \'[{"pattern": "CLAUDE\\\\.md", "agent": "Claude Code"}]\'::jsonb,'
                ' \'[{"pattern": "codex/", "agent": "Codex"}]\'::jsonb,'
                " '[]'::jsonb)"
            )
        )


def make_client(engine):
    def runner_factory(_engine):
        def runner(_run_id, _spec):
            raise AssertionError("find runner must not run in detect page tests")

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


def seed_detect_run(engine, source_id: int, spec_override: dict | None = None) -> int:
    return seed_detect_run_scaled(
        engine, source_id, repo_count=1, hits_per_repo=1, spec_override=spec_override
    )


def seed_detect_run_scaled(
    engine,
    source_id: int,
    *,
    repo_count: int,
    hits_per_repo: int,
    spec_override: dict | None = None,
) -> int:
    spec = {
        "version": 1,
        "kind": "detect",
        "source_run_id": source_id,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file", "pr_metadata"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    if spec_override:
        spec.update(spec_override)
    summary = {
        "repos_scanned": repo_count,
        "repos_with_signal": repo_count,
        "repos_unavailable": 0,
        "agents": {"Claude Code": repo_count},
        "channels": {"file": repo_count},
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
    evidence = {"path": "CLAUDE.md"}
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, kind,"
                " source_run_id, result_summary, finished_at)"
                " VALUES ('detect-hash', CAST(:spec AS jsonb), '2022-11-28', 'done', 'detect',"
                " :src, CAST(:summary AS jsonb), now()) RETURNING id"
            ),
            {"src": source_id, "spec": json.dumps(spec), "summary": json.dumps(summary)},
        ).scalar_one()
        for repo_id in range(1, repo_count + 1):
            if repo_id > 1:
                connection.execute(
                    text(
                        "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility)"
                        " VALUES (:id, :node, :full_name, 1, :name, 'public')"
                    ),
                    {
                        "id": repo_id,
                        "node": f"n{repo_id}",
                        "full_name": f"octo/r{repo_id}",
                        "name": f"r{repo_id}",
                    },
                )
            connection.execute(
                text(
                    "INSERT INTO run_items (run_id, repo_id, full_name, stargazers, detection)"
                    " VALUES (:run, :repo, :full_name, :stargazers, CAST(:detection AS jsonb))"
                ),
                {
                    "run": run_id,
                    "repo": repo_id,
                    "full_name": "octo/one" if repo_id == 1 else f"octo/r{repo_id}",
                    "stargazers": 1000 - repo_id,
                    "detection": json.dumps(detection),
                },
            )
        hits = [
            {
                "run": run_id,
                "repo": repo_id,
                "evidence": json.dumps({**evidence, "row": n}),
            }
            for repo_id in range(1, repo_count + 1)
            for n in range(1, hits_per_repo + 1)
        ]
        if hits:
            connection.execute(
                text(
                    "INSERT INTO detection_evidence (run_id, repo_id, agent, channel, evidence,"
                    " pack_version) VALUES (:run, :repo, 'Claude Code', 'file',"
                    " CAST(:evidence AS jsonb), 'test-pack')"
                ),
                hits,
            )
    return int(run_id)


def test_detection_detail_lives_under_detections(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    redirect = client.get(f"/runs/{detect_id}", follow_redirects=False)
    assert redirect.status_code == 307
    assert redirect.headers["location"] == f"/detections/{detect_id}"
    response = client.get(f"/detections/{detect_id}")
    assert response.status_code == 200
    assert "Detection" in response.text
    assert "CLAUDE.md" in response.text
    assert "Export evidence CSV" in response.text
    assert "Windowed commit ratio" in response.text


def test_find_run_page_wires_detect_button_and_badge(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(f"/runs/{source}")
    assert f'href="/detections/from/{source}"' in response.text
    assert f"/detections/{detect_id}" in response.text
    assert "Coming soon" not in response.text


def test_nav_has_detections_link(clean):
    client = make_client(clean)
    response = client.get("/")
    assert 'href="/detections"' in response.text


def test_corpora_pages_wire_detect_and_last_detection(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    with clean.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO corpora (id, name, source_run_id, note, repo_count)"
                " VALUES (1, 'corpus one', :src, NULL, 1)"
            ),
            {"src": source},
        )
    client = make_client(clean)
    listing = client.get("/corpora")
    assert f'href="/detections/from/{source}"' in listing.text
    assert f"/detections/{detect_id}" in listing.text
    assert "Coming soon" not in listing.text
    detail = client.get("/corpora/1")
    assert f'href="/detections/from/{source}"' in detail.text


def test_detections_export_renders_evidence_csv(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(f"/runs/{detect_id}/export?format=detections")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "full_name,repo_id,agent,channel,evidence,pack_version" in response.text
    assert "Claude Code" in response.text


def test_options_page_has_search_and_select_all_controls(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    client = make_client(clean)
    response = client.get(f"/detections/from/{source}")
    assert response.status_code == 200
    assert 'id="detect-agent-search"' in response.text
    assert 'id="detect-agents-all"' in response.text
    assert 'id="detect-agents-none"' in response.text
    assert "Select all" in response.text
    assert "Select none" in response.text


def test_detection_detail_has_filters_and_repo_data_attributes(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(f"/detections/{detect_id}")
    assert response.status_code == 200
    assert 'id="detection-filter-signal"' in response.text
    assert 'id="detection-filter-agent"' in response.text
    assert 'id="detection-filter-channel"' in response.text
    assert 'data-agents="Claude Code"' in response.text
    assert 'data-channels="file"' in response.text
    assert 'class="evidence-channel" data-channel="file"' in response.text
    assert 'data-agent="Claude Code"' in response.text


def test_latest_detect_for_run_finds_the_detection(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    assert latest_detect_for_run(clean, source)["id"] == detect_id


def test_detect_status_poll_refreshes_page_when_run_finishes(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET status = 'running', finished_at = NULL WHERE id = :id"),
            {"id": detect_id},
        )
    running = client.get(f"/partials/detections/{detect_id}/status", headers={"HX-Request": "true"})
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET status = 'done', finished_at = now() WHERE id = :id"),
            {"id": detect_id},
        )
    done_poll = client.get(
        f"/partials/detections/{detect_id}/status", headers={"HX-Request": "true"}
    )
    done_render = client.get(f"/partials/detections/{detect_id}/status")
    assert running.status_code == done_poll.status_code == done_render.status_code == 200
    assert "HX-Refresh" not in running.headers
    assert done_poll.headers.get("HX-Refresh") == "true"
    assert "HX-Refresh" not in done_render.headers


def test_detection_summary_cards_are_readable(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(f"/detections/{detect_id}")
    assert response.status_code == 200
    assert "2026-01-02 00:00 UTC" in response.text
    assert "100.0%" in response.text
    assert "<h3>Pack</h3>" not in response.text
    assert 'class="info-pop"' in response.text
    assert "What the windowed commit ratio means" in response.text
    assert "conservative lower bound" in response.text
    assert "source api" in response.text


def test_git_detection_detail_reports_clone_depth(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(
        clean,
        source,
        spec_override={"source": "git", "clone": {"depth": 250, "keep": False}},
    )
    client = make_client(clean)
    response = client.get(f"/detections/{detect_id}")
    assert response.status_code == 200
    assert "250 commits" in response.text
    assert "last 250 commits on the default branch" in response.text
    assert "every PR ref walked 250 commits deep" in response.text
    assert "labels and issues are API-only" in response.text


def test_detections_use_their_own_numbering(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    first = seed_detect_run(clean, source)
    second = seed_detect_run(clean, source)
    client = make_client(clean)
    listing = client.get("/detections").text
    assert f'href="/detections/{first}">#1</a>' in listing
    assert f'href="/detections/{second}">#2</a>' in listing
    detail = client.get(f"/detections/{second}").text
    assert "Detection #2" in detail
    assert f"search #{source}" in detail
    assert f'data-field="run">run {second}</span>' in detail


def test_detection_detail_paginates_repos(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    repo_count = DETECTION_REPOS_PAGE_SIZE + 5
    detect_id = seed_detect_run_scaled(clean, source, repo_count=repo_count, hits_per_repo=1)
    client = make_client(clean)
    page1 = client.get(f"/detections/{detect_id}")
    assert page1.status_code == 200
    assert 'id="detection-repo-1"' in page1.text
    assert f'id="detection-repo-{DETECTION_REPOS_PAGE_SIZE}"' in page1.text
    assert f'id="detection-repo-{DETECTION_REPOS_PAGE_SIZE + 1}"' not in page1.text
    assert f"repos 1–{DETECTION_REPOS_PAGE_SIZE} of {repo_count}" in page1.text
    assert 'href="?page=2"' in page1.text
    page2 = client.get(f"/detections/{detect_id}?page=2")
    assert f'id="detection-repo-{repo_count}"' in page2.text
    assert 'id="detection-repo-1"' not in page2.text
    assert 'href="?page=1"' in page2.text
    assert f"repos {DETECTION_REPOS_PAGE_SIZE + 1}–{repo_count} of {repo_count}" in page2.text
    clamped = client.get(f"/detections/{detect_id}?page=99")
    assert f'id="detection-repo-{repo_count}"' in clamped.text


def test_detection_detail_caps_repo_evidence(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    total_hits = DETECTION_REPO_EVIDENCE_CAP + 10
    detect_id = seed_detect_run_scaled(clean, source, repo_count=1, hits_per_repo=total_hits)
    client = make_client(clean)
    response = client.get(f"/detections/{detect_id}")
    assert response.status_code == 200
    assert response.text.count('<li data-agent="Claude Code">') == DETECTION_REPO_EVIDENCE_CAP
    truncated_note = f"Showing first {DETECTION_REPO_EVIDENCE_CAP} of {total_hits} evidence rows"
    assert truncated_note in response.text
