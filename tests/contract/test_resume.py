from __future__ import annotations

import json
import time

import fakeredis
import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from lib.gh_client import API_VERSION
from serve.app import create_app
from serve.executor import RunPayload, RunPayloadItem, create_run, execute_run
from serve.pages import CSRF_COOKIE


@pytest.fixture(scope="module", autouse=True)
def schema(alembic_config):
    command.upgrade(alembic_config, "head")


@pytest.fixture()
def clean(clean_db):
    return clean_db(
        owners=[
            {
                "id": 1,
                "login": "octo",
                "type": "User",
                "location_raw": "Berlin, Germany",
                "country_iso": "DE",
                "geo_confidence": "name",
            }
        ],
        repos=[
            {
                "id": 1296269,
                "node_id": "R_1296269",
                "full_name": "octo/hello",
                "owner_id": 1,
                "name": "hello",
                "visibility": "public",
                "description": "My first repo",
                "language": "Ruby",
                "license_spdx": "MIT",
                "topics": ["octocat"],
                "stargazers": 80,
                "forks_count": 9,
                "open_issues": 0,
                "pushed_at": "2011-01-26T19:06:43Z",
            }
        ],
    )


def payload_item(**overrides) -> RunPayloadItem:
    values: dict[str, object] = {
        "repo_id": 1296269,
        "full_name": "octo/hello",
        "stargazers": 80,
        "pushed_at": "2011-01-26T19:06:43Z",
        "archived": False,
        "language": "Ruby",
        "license_spdx": "MIT",
        "country_iso": "DE",
        "geo_confidence": "name",
        "virtuals": {"has_dockerfile": True},
    }
    values.update(overrides)
    return RunPayloadItem(**values)


def make_client(
    engine,
    runs_root="runs",
    *,
    redis_ping=None,
    token_present=None,
    runner_factory=None,
    detect_runner_factory=None,
) -> TestClient:
    application = create_app(
        engine=engine,
        runs_root=str(runs_root),
        redis_ping=redis_ping,
        token_present=token_present,
        runner_factory=runner_factory,
        detect_runner_factory=detect_runner_factory,
    )
    return TestClient(application, raise_server_exceptions=False)


def healthy_client(engine: Engine, tmp_path, monkeypatch, **overrides) -> TestClient:
    monkeypatch.setenv("GITHUB_TOKEN", "super-secret-token-value")
    monkeypatch.delenv("GITHUB_TOKENS", raising=False)
    options = {
        "redis_ping": fakeredis.FakeRedis().ping,
        "token_present": lambda: True,
        "runs_root": tmp_path,
    }
    options.update(overrides)
    return make_client(engine, **options)


def seed_run(engine: Engine, tmp_path) -> tuple[int, str]:
    filter_spec = {"gitcorpus_filter": 1, "q": "language:rust"}
    run_id = create_run(engine, filter_spec, api_version=API_VERSION)
    payload = RunPayload(total_count=1, fetched=1, items=[payload_item()])
    execute_run(engine, run_id, runner=lambda _rid, _spec: payload, runs_root=str(tmp_path))
    with engine.connect() as connection:
        filter_hash = connection.scalar(
            text("SELECT filter_hash FROM runs WHERE id = :id"), {"id": run_id}
        )
    return run_id, str(filter_hash)


def csrf_token(client) -> str:
    client.get("/")
    return client.cookies.get(CSRF_COOKIE)


def fake_runner_factory(engine):
    def runner(run_id: int, spec: dict):
        return RunPayload(
            total_count=1,
            fetched=1,
            items=[
                RunPayloadItem(repo_id=1296269, full_name="octo/hello", stargazers=10, virtuals={})
            ],
        )

    return runner


def test_resume_failed_run_requeues_and_clears_items(clean, tmp_path, monkeypatch):
    run_id, _ = seed_run(clean, tmp_path)
    with clean.begin() as connection:
        connection.execute(text("UPDATE runs SET status='failed' WHERE id=:id"), {"id": run_id})
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name) "
                "VALUES (:id, NULL, 'octo/world')"
            ),
            {"id": run_id},
        )
    observed: list[int] = []
    stamps: list[tuple] = []

    def recording_factory(engine):
        def runner(run_id: int, spec: dict) -> RunPayload:
            with engine.connect() as connection:
                count = connection.scalar(
                    text("SELECT count(*) FROM run_items WHERE run_id = :id"), {"id": run_id}
                )
                stamp = connection.execute(
                    text("SELECT started_at, finished_at FROM runs WHERE id = :id"),
                    {"id": run_id},
                ).one()
            observed.append(int(count))
            stamps.append((stamp[0], stamp[1]))
            return RunPayload(
                total_count=1,
                fetched=1,
                items=[
                    RunPayloadItem(
                        repo_id=1296269, full_name="octo/hello", stargazers=10, virtuals={}
                    )
                ],
            )

        return runner

    client = make_client(clean, tmp_path, runner_factory=recording_factory)
    token = csrf_token(client)
    response = client.post(
        f"/runs/{run_id}/resume", headers={"x-csrf-token": token}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/runs/{run_id}"
    deadline = time.monotonic() + 5
    while True:
        with clean.connect() as connection:
            status = connection.scalar(text("SELECT status FROM runs WHERE id=:id"), {"id": run_id})
        if status in {"done", "failed", "partial"} or time.monotonic() > deadline:
            break
        time.sleep(0.05)
    assert observed == [0], f"runner saw {observed} run_items; resume did not reset first"
    assert stamps and stamps[0][1] is None, f"resume kept a stale finish time: {stamps}"
    with clean.connect() as connection:
        stale = connection.scalar(
            text("SELECT count(*) FROM run_items WHERE run_id=:id AND full_name='octo/world'"),
            {"id": run_id},
        )
    assert stale == 0
    assert status in {"queued", "running", "done"}


def test_resume_partial_run_requeues(clean, tmp_path, monkeypatch):
    run_id, _ = seed_run(clean, tmp_path)
    with clean.begin() as connection:
        connection.execute(text("UPDATE runs SET status='partial' WHERE id=:id"), {"id": run_id})
    client = make_client(clean, tmp_path, runner_factory=fake_runner_factory)
    token = csrf_token(client)
    response = client.post(
        f"/runs/{run_id}/resume", headers={"x-csrf-token": token}, follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/runs/{run_id}"


def test_resume_done_run_is_400(clean, tmp_path, monkeypatch):
    run_id, _ = seed_run(clean, tmp_path)
    client = make_client(clean, tmp_path, runner_factory=fake_runner_factory)
    token = csrf_token(client)
    response = client.post(f"/runs/{run_id}/resume", headers={"x-csrf-token": token})
    assert response.status_code == 400
    assert "failed" in response.text


def test_resume_unknown_run_is_404(clean, tmp_path, monkeypatch):
    client = make_client(clean, tmp_path, runner_factory=fake_runner_factory)
    token = csrf_token(client)
    assert client.post("/runs/4242/resume", headers={"x-csrf-token": token}).status_code == 404


def test_resume_requires_csrf(clean, tmp_path, monkeypatch):
    run_id, _ = seed_run(clean, tmp_path)
    client = make_client(clean, tmp_path, runner_factory=fake_runner_factory)
    assert client.post(f"/runs/{run_id}/resume").status_code == 403


def test_run_detail_shows_resume_for_failed_and_partial(clean, tmp_path, monkeypatch):
    run_id, _ = seed_run(clean, tmp_path)
    client = make_client(clean, tmp_path, runner_factory=fake_runner_factory)
    assert "Resume" not in client.get(f"/runs/{run_id}").text
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET status='failed', error='boom' WHERE id=:id"), {"id": run_id}
        )
    assert "Resume" in client.get(f"/runs/{run_id}").text
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET status='partial', error=NULL WHERE id=:id"), {"id": run_id}
        )
    assert "Resume" in client.get(f"/runs/{run_id}").text


def test_resume_detect_run_uses_detect_runner_and_clears_evidence(clean):
    engine = clean
    with engine.begin() as connection:
        source = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status)"
                " VALUES ('s', '{}'::jsonb, '2022-11-28', 'done') RETURNING id"
            )
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('p1', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO owners (id, login, type) VALUES (1, 'octo', 'User')"
                " ON CONFLICT (id) DO NOTHING"
            )
        )
        connection.execute(
            text(
                "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility)"
                " VALUES (1, 'n1', 'octo/one', 1, 'one', 'public')"
            )
        )
        detect_id = connection.execute(
            text(
                "INSERT INTO runs"
                " (filter_hash, filter_spec, api_version, status, kind, source_run_id)"
                " VALUES ('d', :spec, '2022-11-28', 'failed', 'detect', :src) RETURNING id"
            ),
            {
                "spec": json.dumps(
                    {
                        "version": 1,
                        "kind": "detect",
                        "source_run_id": int(source),
                        "pack_version": "p1",
                        "agents": None,
                        "channels": ["file"],
                        "limit": None,
                        "windows": {"commits": 100, "prs": 100, "issues": 100},
                    }
                ),
                "src": source,
            },
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO detection_evidence"
                " (run_id, repo_id, agent, channel, evidence, pack_version)"
                " VALUES (:run, 1, 'claude', 'file', '{}'::jsonb, 'p1')"
            ),
            {"run": detect_id},
        )
    seen: list[int] = []

    def detect_factory(_engine):
        def runner(run_id, _spec):
            seen.append(run_id)
            from serve.executor import RunPayload

            return RunPayload(total_count=0, items=[], fetched=0)

        return runner

    client = make_client(engine, detect_runner_factory=detect_factory)
    client.get(f"/runs/{detect_id}")  # CSRF cookie
    response = client.post(
        f"/runs/{detect_id}/resume", data={"csrf": csrf_token(client)}, follow_redirects=False
    )
    assert response.status_code == 303
    with engine.connect() as connection:
        status = connection.execute(
            text("SELECT status FROM runs WHERE id = :id"), {"id": detect_id}
        ).scalar_one()
        evidence = connection.execute(
            text("SELECT count(*) FROM detection_evidence WHERE run_id = :id"), {"id": detect_id}
        ).scalar_one()
    assert status in ("queued", "running", "done")
    assert evidence == 0
