from __future__ import annotations

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from serve.app import create_app
from serve.detect_spec import detect_spec_to_dict, parse_detect_spec


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


def seed_find_run(engine, status="done", *, with_items=True) -> int:
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, finished_at)"
                " VALUES ('find-hash', '{\"q\": \"rust\"}'::jsonb, '2022-11-28', :status, now())"
                " RETURNING id"
            ),
            {"status": status},
        ).scalar_one()
        if with_items:
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


def make_client(engine, *, detect_runner=None):
    def runner_factory(_engine):
        def runner(_run_id, _spec):
            raise AssertionError("find runner must not run in detect tests")

        return runner

    def detect_factory(_engine):
        return detect_runner or (lambda run_id, spec: None)

    return TestClient(
        create_app(
            engine=engine,
            runner_factory=runner_factory,
            detect_runner_factory=detect_factory,
            runs_root="runs",
            clone_root="clones",
            redis_ping=lambda: True,
            token_present=lambda: True,
        )
    )


def csrf_token(client: TestClient) -> str:
    return client.cookies.get("gc_csrf")


def test_detections_list_renders_empty_and_filled(clean):
    client = make_client(clean)
    assert "No detections yet" in client.get("/detections").text
    seed_find_run(clean)
    client = make_client(clean)
    response = client.get("/detections")
    assert response.status_code == 200


def test_options_page_requires_finished_find_run(clean):
    client = make_client(clean)
    running = seed_find_run(clean, status="running")
    assert client.get(f"/runs/{running}/detect").status_code == 400
    done = seed_find_run(clean, status="done")
    seed_pack(clean)
    response = client.get(f"/runs/{done}/detect")
    assert response.status_code == 200
    assert "Claude Code" in response.text
    assert "test-pack" in response.text


def test_start_detection_creates_run_and_submits_runner(clean):
    calls: list[tuple[int, dict]] = []

    def detect_runner(run_id, spec):
        calls.append((run_id, spec))

    client = make_client(clean, detect_runner=detect_runner)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/runs/{source}/detect")  # sets the CSRF cookie
    response = client.post(
        f"/runs/{source}/detect",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "agents": ["Claude Code", "Codex"],
            "channels": ["file", "pr_metadata"],
            "limit": "50",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_id = int(response.headers["location"].rsplit("/", 1)[-1])
    with clean.connect() as connection:
        row = (
            connection.execute(
                text("SELECT kind, source_run_id, filter_spec FROM runs WHERE id = :id"),
                {"id": new_id},
            )
            .mappings()
            .one()
        )
    assert row["kind"] == "detect"
    assert row["source_run_id"] == source
    assert row["filter_spec"]["agents"] == ["Claude Code", "Codex"]
    assert row["filter_spec"]["channels"] == ["file", "pr_metadata"]
    assert row["filter_spec"]["limit"] == 50


def test_start_detection_rejects_empty_source_run(clean):
    client = make_client(clean)
    source = seed_find_run(clean, with_items=False)
    seed_pack(clean)
    client.get(f"/runs/{source}/detect")
    response = client.post(
        f"/runs/{source}/detect",
        data={"csrf": csrf_token(client), "pack_version": "test-pack", "channels": ["file"]},
    )
    assert response.status_code == 400
    assert "no saved results" in response.text
    assert "finished search with saved results" in response.text
    with clean.connect() as connection:
        count = connection.scalar(text("SELECT count(*) FROM runs WHERE kind = 'detect'"))
    assert count == 0


def test_start_detection_rejects_unknown_agents(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/runs/{source}/detect")
    response = client.post(
        f"/runs/{source}/detect",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "agents": ["Not An Agent"],
            "channels": ["file"],
        },
    )
    assert response.status_code == 400
    assert "unknown agents" in response.text
    assert "Not An Agent" in response.text
    assert "roster" in response.text
    with clean.connect() as connection:
        count = connection.scalar(text("SELECT count(*) FROM runs WHERE kind = 'detect'"))
    assert count == 0


def test_start_detection_validates_agents_against_the_submitted_pack(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    with clean.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('older-pack', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)"
            )
        )
    client.get(f"/runs/{source}/detect")
    response = client.post(
        f"/runs/{source}/detect",
        data={
            "csrf": csrf_token(client),
            "pack_version": "older-pack",
            "agents": ["Codex"],
            "channels": ["file"],
        },
    )
    assert response.status_code == 400
    assert "unknown agents" in response.text
    assert "Codex" in response.text
    with clean.connect() as connection:
        count = connection.scalar(text("SELECT count(*) FROM runs WHERE kind = 'detect'"))
    assert count == 0


def test_start_detection_rejects_empty_selection(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/runs/{source}/detect")
    response = client.post(
        f"/runs/{source}/detect",
        data={"csrf": csrf_token(client), "pack_version": "test-pack", "channels": []},
    )
    assert response.status_code == 400
    assert "channels must be a non-empty list" in response.text


def test_estimate_partial_renders(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(f"/runs/{source}/detect-estimate?channels=file&channels=issue&limit=10")
    assert response.status_code == 200
    assert "REST calls" in response.text


def test_detect_status_partial(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(f"/partials/runs/{source}/detect-status")
    assert response.status_code == 200


def test_detect_spec_round_trip_canonicalizes_channels():
    doc = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": ["Codex", "Claude Code"],
        "channels": ["pr_metadata", "file"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    spec = parse_detect_spec(doc)
    assert spec.channels == frozenset({"file", "pr_metadata"})
    round_tripped = detect_spec_to_dict(spec)
    assert round_tripped["channels"] == ["file", "pr_metadata"]
    assert round_tripped["agents"] == ["Claude Code", "Codex"]
    assert round_tripped["source_run_id"] == 7
