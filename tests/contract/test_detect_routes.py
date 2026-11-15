from __future__ import annotations

import json
import time

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text

from serve.app import create_app
from serve.detect_spec import DetectSpecError, detect_spec_to_dict, parse_detect_spec
from store.settings import update_run_settings


@pytest.fixture(scope="module", autouse=True)
def schema(alembic_config):
    command.upgrade(alembic_config, "head")


@pytest.fixture(autouse=True)
def _reset_flush_state():
    from serve import detect as detect_module

    detect_module._FLUSH_STATE.clear()
    detect_module._FLUSH_STATE["phase"] = "idle"
    yield
    detect_module._FLUSH_STATE.clear()
    detect_module._FLUSH_STATE["phase"] = "idle"


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


def make_client(engine, *, detect_runner=None, clone_root="clones"):
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
            clone_root=clone_root,
            redis_ping=lambda: True,
            token_present=lambda: True,
        )
    )


def seed_detect_run(engine, status="running") -> int:
    with engine.begin() as connection:
        return int(
            connection.execute(
                text(
                    "INSERT INTO runs (filter_hash, filter_spec, api_version, kind, status)"
                    " VALUES ('detect-hash', '{\"kind\": \"detect\"}'::jsonb,"
                    " '2022-11-28', 'detect', :status) RETURNING id"
                ),
                {"status": status},
            ).scalar_one()
        )


def test_cancel_detect_run_redirects_to_its_detection_page(clean):
    client = make_client(clean)
    client.get("/detections")
    run_id = seed_detect_run(clean, status="running")
    response = client.post(
        f"/runs/{run_id}/cancel",
        data={"csrf": csrf_token(client)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/detections/{run_id}"


def test_cancel_find_run_still_redirects_to_the_run_page(clean):
    client = make_client(clean)
    client.get("/detections")
    source = seed_find_run(clean, status="running")
    response = client.post(
        f"/runs/{source}/cancel",
        data={"csrf": csrf_token(client)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/runs/{source}"


def test_detect_status_partial_shows_stopping_after_cancel_request(clean):
    client = make_client(clean)
    client.get("/detections")
    run_id = seed_detect_run(clean, status="running")
    before = client.get(f"/partials/detections/{run_id}/status")
    assert "Stop detection" in before.text
    assert "Stopping" not in before.text
    client.post(f"/runs/{run_id}/cancel", data={"csrf": csrf_token(client)})
    after = client.get(f"/partials/detections/{run_id}/status")
    assert "Stopping" in after.text
    assert "Stop detection" not in after.text


def test_detect_status_partial_shows_live_token_pool_health(clean):
    client = make_client(clean)
    run_id = seed_detect_run(clean, status="running")
    pool = {
        "tokens": 4,
        "accounts": [
            {
                "fingerprint": f"private-fingerprint-{index}",
                "core_remaining": 4900 - index,
                "graphql_remaining": 4800 - index,
                "active": 1,
                "active_limit": 3,
                "disabled": index == 3,
                "cooldown_seconds": 0,
            }
            for index in range(4)
        ],
    }
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET result_summary = CAST(:summary AS jsonb) WHERE id = :run"),
            {"run": run_id, "summary": json.dumps({"token_pool": pool})},
        )

    body = client.get(f"/partials/detections/{run_id}/status").text

    assert 'class="pool-table"' in body
    rows = body.split("<tbody>", 1)[1].split("</tbody>", 1)[0].split("<tr>")[1:]
    assert len(rows) == 4
    assert '<span class="pool-num">4900</span>' in rows[0]
    assert '<span class="pool-num">4800</span>' in rows[0]
    assert ">1/3<" in rows[0]
    assert "disabled" in rows[3] and "disabled" not in rows[0]
    assert "private-fingerprint" not in body


def test_detections_list_has_a_flush_repos_button(clean):
    client = make_client(clean)
    body = client.get("/detections").text
    assert 'action="/detections/flush"' in body
    assert "Flush repos" in body


def test_flush_repos_removes_leftover_detect_clones_but_keeps_active_ones(clean, tmp_path):
    clone_root = tmp_path / "clones"
    (clone_root / "detect-41" / "octo__one").mkdir(parents=True)
    (clone_root / "detect-41" / "octo__one" / ".git").mkdir()
    (clone_root / "detect-41" / "detect-41").mkdir()
    active = seed_detect_run(clean, status="running")
    (clone_root / f"detect-{active}").mkdir()
    (clone_root / "find-hash").mkdir()
    client = make_client(clean, clone_root=str(clone_root))
    client.get("/detections")
    response = client.post(
        "/detections/flush",
        data={"csrf": csrf_token(client)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/detections"
    status_text = _wait_for_flush(client)
    assert "deleted 1 leftover" in status_text
    assert "kept 1 (active scans)" in status_text
    assert not (clone_root / "detect-41").exists()
    assert (clone_root / f"detect-{active}").exists()
    assert (clone_root / "find-hash").exists()


def test_flush_status_shows_live_progress_while_running(clean, tmp_path, monkeypatch):
    from serve import detect as detect_module

    clone_root = tmp_path / "clones"
    (clone_root / "detect-7").mkdir(parents=True)
    (clone_root / "detect-8").mkdir(parents=True)
    real_remove = detect_module._remove_tree

    def slow_remove(path):
        time.sleep(0.4)
        real_remove(path)

    monkeypatch.setattr(detect_module, "_remove_tree", slow_remove)
    client = make_client(clean, clone_root=str(clone_root))
    client.get("/detections")
    response = client.post(
        "/detections/flush",
        data={"csrf": csrf_token(client)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    live = client.get("/partials/detections/flush/status").text
    assert "Flushing repos:" in live
    assert 'hx-get="/partials/detections/flush/status"' in live
    finished = _wait_for_flush(client)
    assert "deleted 2 leftover" in finished
    assert not (clone_root / "detect-7").exists()
    assert not (clone_root / "detect-8").exists()


def test_flush_follows_the_environment_clones_root(clean, tmp_path, monkeypatch):
    env_root = tmp_path / "env-clones"
    (env_root / "detect-51").mkdir(parents=True)
    monkeypatch.setenv("GITCORPUS_CLONES_ROOT", str(env_root))
    client = make_client(clean, clone_root=None)
    client.get("/detections")
    response = client.post(
        "/detections/flush",
        data={"csrf": csrf_token(client)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    status_text = _wait_for_flush(client)
    assert "deleted 1 leftover" in status_text
    assert not (env_root / "detect-51").exists()


def _wait_for_flush(client: TestClient, timeout: float = 15.0) -> str:
    deadline = time.monotonic() + timeout
    text = ""
    while time.monotonic() < deadline:
        text = client.get("/partials/detections/flush/status").text
        if "Flush repos: deleted" in text or "Flush repos failed" in text:
            return text
        time.sleep(0.1)
    pytest.fail(f"flush never finished; last status: {text!r}")


def test_detections_list_is_ordered_newest_id_first_even_with_older_timestamps(clean):
    client = make_client(clean)
    older_id = seed_detect_run(clean, status="done")
    newer_id = seed_detect_run(clean, status="done")
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET created_at = now() - interval '1 day' WHERE id = :id"),
            {"id": newer_id},
        )
    body = client.get("/detections").text
    assert body.index(f"detection-{newer_id}") < body.index(f"detection-{older_id}")


def test_detections_list_paginates_older_runs(clean):
    client = make_client(clean)
    run_ids = [seed_detect_run(clean, status="done") for _ in range(17)]
    first_page = client.get("/detections").text
    assert first_page.count('<tr id="detection-') == 15
    assert f'id="detection-{run_ids[-1]}"' in first_page
    assert f'id="detection-{run_ids[0]}"' not in first_page
    assert "Page 1 of 2 · 17 detections" in first_page
    assert 'href="/detections?page=2"' in first_page
    second_page = client.get("/detections?page=2").text
    assert second_page.count('<tr id="detection-') == 2
    assert f'id="detection-{run_ids[0]}"' in second_page
    assert f'id="detection-{run_ids[-1]}"' not in second_page
    assert "Page 2 of 2 · 17 detections" in second_page
    assert 'href="/detections?page=1"' in second_page


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
    assert client.get(f"/detections/from/{running}").status_code == 400
    done = seed_find_run(clean, status="done")
    seed_pack(clean)
    response = client.get(f"/detections/from/{done}")
    assert response.status_code == 200
    assert "Claude Code" in response.text
    assert "test-pack" in response.text
    assert "shares the history call" in response.text
    assert 'id="detect-channels-all"' in response.text


def test_start_detection_creates_run_and_submits_runner(clean):
    calls: list[tuple[int, dict]] = []

    def detect_runner(run_id, spec):
        calls.append((run_id, spec))

    client = make_client(clean, detect_runner=detect_runner)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/detections/from/{source}")  # sets the CSRF cookie
    response = client.post(
        f"/detections/from/{source}",
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


def test_start_detection_records_fast_mode_and_shows_it(clean):
    client = make_client(clean, detect_runner=lambda run_id, spec: None)
    source = seed_find_run(clean)
    seed_pack(clean)
    options = client.get(f"/detections/from/{source}")
    assert 'name="scan_mode" value="fast"' in options.text
    response = client.post(
        f"/detections/from/{source}",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "channels": ["file"],
            "scan_mode": "fast",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_id = int(response.headers["location"].rsplit("/", 1)[-1])
    with clean.connect() as connection:
        spec = connection.scalar(
            text("SELECT filter_spec FROM runs WHERE id = :id"), {"id": new_id}
        )
    assert spec["scan_mode"] == "fast"
    assert 'id="run-scan-mode"' in client.get(f"/detections/{new_id}").text


def test_start_pool4_detection_rejects_two_or_three_configured_tokens(clean, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKENS", "token-one,token-two")
    monkeypatch.setenv("GITHUB_TOKEN", "single-token-is-ignored")
    update_run_settings(clean, {"detect_token_mode": "pool4"})
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "channels": ["file"],
            "source": "api",
        },
    )
    assert response.status_code == 400
    assert "exactly four" in response.text.lower()
    assert "found 2" in response.text
    with clean.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM runs WHERE kind = 'detect'")) == 0


def test_start_detection_rejects_empty_source_run(clean):
    client = make_client(clean)
    source = seed_find_run(clean, with_items=False)
    seed_pack(clean)
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
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
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
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
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
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
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
        data={"csrf": csrf_token(client), "pack_version": "test-pack", "channels": []},
    )
    assert response.status_code == 400
    assert "channels must be a non-empty list" in response.text


def test_estimate_partial_renders(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(
        f"/partials/detections/{source}/estimate?channels=file&channels=issue&limit=10"
    )
    assert response.status_code == 200
    assert "REST" in response.text


def test_estimate_partial_404s_for_missing_run(clean):
    client = make_client(clean)
    response = client.get("/partials/detections/9999/estimate")
    assert response.status_code == 404


def test_detect_status_partial(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(f"/partials/detections/{source}/status")
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


def test_new_detection_page_renders_sources_and_upload(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get("/detections/new")
    assert response.status_code == 200
    assert "New detection" in response.text
    assert "From a finished search" in response.text
    assert "From a CSV or JSON file" in response.text
    assert f'value="{source}"' in response.text


def test_new_detection_from_search_redirects_to_options(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get("/detections/new")
    response = client.post(
        "/detections/new",
        data={"csrf": csrf_token(client), "source": str(source)},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/detections/from/{source}"


def test_new_detection_from_csv_imports_and_redirects(clean):
    client = make_client(clean)
    seed_pack(clean)
    client.get("/detections/new")
    response = client.post(
        "/detections/new",
        data={"csrf": csrf_token(client)},
        files={
            "import_file": (
                "repos.csv",
                "repo,stars\nocto/one,42\nocto/two,7\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_id = int(response.headers["location"].split("/")[3])
    with clean.connect() as connection:
        run = (
            connection.execute(text("SELECT kind, status FROM runs WHERE id = :id"), {"id": new_id})
            .mappings()
            .one()
        )
        items = connection.scalar(
            text("SELECT count(*) FROM run_items WHERE run_id = :id"), {"id": new_id}
        )
    assert run["kind"] == "find"
    assert run["status"] == "done"
    assert items == 2


def test_new_detection_rejects_bad_csv_and_unfinished_search(clean):
    client = make_client(clean)
    client.get("/detections/new")
    bad = client.post(
        "/detections/new",
        data={"csrf": csrf_token(client)},
        files={"import_file": ("bad.csv", "stars,url\n5,https://github.com/x\n", "text/csv")},
    )
    assert bad.status_code == 400
    assert "full_name or repo" in bad.text
    running = seed_find_run(clean, status="running")
    not_finished = client.post(
        "/detections/new",
        data={"csrf": csrf_token(client), "source": str(running)},
    )
    assert not_finished.status_code == 400
    assert "not a finished search" in not_finished.text


def test_options_page_blocks_enter_submit_and_search_hides_labels(clean, repo_root):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    response = client.get(f"/detections/from/{source}")
    assert 'event.key === "Enter"' in response.text
    css = (repo_root / "src/serve/static/app.css").read_text(encoding="utf-8")
    assert ".checklist .checkbox[hidden]" in css
    assert ".field-grid[hidden]" in css


def test_new_detection_from_json_export_imports(clean):
    client = make_client(clean)
    seed_pack(clean)
    client.get("/detections/new")
    payload = json.dumps(
        {
            "filter": {"gitcorpus_filter": 1, "q": "language:rust"},
            "items": [
                {"repo_id": 5, "full_name": "octo/one", "stargazers": 9, "virtuals": {}},
                {"repo_id": 6, "full_name": "octo/two", "stargazers": 2},
            ],
            "field_stats": {},
        }
    )
    response = client.post(
        "/detections/new",
        data={"csrf": csrf_token(client)},
        files={"import_file": ("bundle.json", payload, "application/json")},
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_id = int(response.headers["location"].split("/")[3])
    with clean.connect() as connection:
        items = (
            connection.execute(
                text(
                    "SELECT repo_id, full_name, stargazers FROM run_items"
                    " WHERE run_id = :id ORDER BY full_name"
                ),
                {"id": new_id},
            )
            .mappings()
            .all()
        )
    # octo/one already exists in the seeded fixture (id 1) and is reused;
    # octo/two keeps the id carried by the export.
    assert [(int(item["repo_id"]), item["full_name"], item["stargazers"]) for item in items] == [
        (1, "octo/one", 9),
        (6, "octo/two", 2),
    ]


def test_detect_spec_parses_git_source_and_clone_options():
    doc = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file", "label"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
        "source": "git",
        "clone": {"depth": 250, "keep": True},
    }
    spec = parse_detect_spec(doc)
    assert spec.source == "git"
    assert spec.clone_depth == 250
    assert spec.clone_keep is True
    round_tripped = detect_spec_to_dict(spec)
    assert round_tripped["source"] == "git"
    assert round_tripped["clone"] == {"depth": 250, "keep": True}


def test_detect_spec_defaults_to_api_source():
    doc = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    spec = parse_detect_spec(doc)
    assert spec.source == "api"
    assert spec.clone_depth == 100
    assert spec.clone_keep is False
    assert detect_spec_to_dict(spec)["source"] == "api"


def test_detect_spec_rejects_unknown_source_and_bad_clone():
    base = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    with pytest.raises(DetectSpecError) as bad_source:
        parse_detect_spec({**base, "source": "ftp"})
    assert any("source must be" in error for error in bad_source.value.errors)
    with pytest.raises(DetectSpecError) as bad_depth:
        parse_detect_spec({**base, "clone": {"depth": 0}})
    assert any("clone.depth must be" in error for error in bad_depth.value.errors)
    with pytest.raises(DetectSpecError) as bad_keep:
        parse_detect_spec({**base, "clone": {"keep": "yes"}})
    assert any("clone.keep must be" in error for error in bad_keep.value.errors)


def test_detect_spec_scan_mode_defaults_full_and_round_trips_fast():
    base = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    full = parse_detect_spec(base)
    assert full.scan_mode == "full"
    # Full mode is omitted so pre-existing specs and filter hashes are unchanged.
    assert "scan_mode" not in detect_spec_to_dict(full)
    fast = parse_detect_spec({**base, "scan_mode": "fast"})
    assert fast.scan_mode == "fast"
    assert detect_spec_to_dict(fast)["scan_mode"] == "fast"
    assert parse_detect_spec(detect_spec_to_dict(fast)) == fast


def test_detect_spec_rejects_unknown_scan_mode_and_fast_git():
    base = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    with pytest.raises(DetectSpecError) as unknown:
        parse_detect_spec({**base, "scan_mode": "turbo"})
    assert any("scan_mode must be" in error for error in unknown.value.errors)
    with pytest.raises(DetectSpecError) as git_fast:
        parse_detect_spec({**base, "source": "git", "scan_mode": "fast"})
    assert any("only to API" in error for error in git_fast.value.errors)


def test_detect_spec_parses_hybrid_source_and_rejects_fast_hybrid():
    base = {
        "version": 1,
        "kind": "detect",
        "source_run_id": 7,
        "pack_version": "test-pack",
        "agents": None,
        "channels": ["file", "label", "pr_metadata"],
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
        "source": "hybrid",
    }
    spec = parse_detect_spec(base)
    assert spec.source == "hybrid"
    assert parse_detect_spec(detect_spec_to_dict(spec)) == spec
    with pytest.raises(DetectSpecError) as hybrid_fast:
        parse_detect_spec({**base, "scan_mode": "fast"})
    assert any("only to API" in error for error in hybrid_fast.value.errors)


def test_options_page_and_estimate_offer_hybrid(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    page = client.get(f"/detections/from/{source}")
    assert 'id="detect-source-hybrid"' in page.text
    assert "Hybrid (git + PR metadata)" in page.text
    estimate = client.get(f"/partials/detections/{source}/estimate?source=hybrid&limit=10")
    assert "Hybrid (git + PR metadata)</strong> — selected" in estimate.text
    assert "Local clone (git)</strong> — selected" not in estimate.text


def test_options_page_presents_both_detection_methods(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    response = client.get(f"/detections/from/{source}")
    assert response.status_code == 200
    assert "GitHub API" in response.text
    assert "Local clone (git)" in response.text
    assert "5,000 REST requests + 5,000 GraphQL points per hour" in response.text
    assert "No API quota" in response.text
    assert "99.5% of detected repos" in response.text


def test_estimate_partial_shows_both_methods(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(
        f"/partials/detections/{source}/estimate?source=git&channels=file&limit=10"
    )
    assert response.status_code == 200
    assert "REST" in response.text
    assert "Local clone (git)" in response.text
    assert "MB of lean clones" in response.text


def test_estimate_partial_highlights_the_selected_method(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(f"/partials/detections/{source}/estimate?source=git&limit=10")
    assert "Local clone (git)</strong> — selected" in response.text
    assert "GitHub API</strong> — selected" not in response.text
    # The swapped-in partial must keep polling so method changes re-estimate.
    assert f'hx-get="/partials/detections/{source}/estimate"' in response.text
    assert 'hx-include="#detect-form"' in response.text


def test_estimate_partial_reflects_keep_and_depth(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(
        f"/partials/detections/{source}/estimate"
        "?source=git&limit=10&clone_keep=true&clone_depth=250"
    )
    assert "MB kept on disk" in response.text
    assert "depth 250 commits" in response.text
    assert "clones kept on disk" in response.text
    no_keep = client.get(f"/partials/detections/{source}/estimate?source=git&limit=10")
    assert "deleted after each scan" in no_keep.text
    assert "MB kept on disk" not in no_keep.text


V1_CHANNELS = (
    "file",
    "author",
    "branch",
    "label",
    "bot",
    "commit_trailer",
    "pr_metadata",
    "issue",
)


def seed_older_pack(engine) -> None:
    from json import dumps

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels,"
                " frozen_at) VALUES ('older-pack', CAST(:authors AS jsonb),"
                " '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, now() - interval '1 day')"
            ),
            {"authors": dumps([{"pattern": "cursor", "agent": "Cursor"}])},
        )


def seed_lifecycle_pack(engine) -> None:
    from pathlib import Path

    from detect.packs import freeze_pack, load_pack_file

    root = Path(__file__).resolve().parents[2]
    freeze_pack(engine, load_pack_file(root / "packs" / "2026-11-14.json"))


def test_options_page_moves_clone_fields_into_scope_and_disables_api_only_channels(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    body = client.get(f"/detections/from/{source}").text
    assert body.index('id="detect-scope-section"') < body.index("data-git-field>")
    assert body.count("data-git-field>") == 2
    assert body.index("data-git-field>") < body.index('id="detect-estimate"')
    assert "unavailable with this detection method" in body
    assert "apiOnlyValues" in body


def test_schema_v1_pack_offers_its_eight_channels(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    body = client.get(f"/detections/from/{source}").text
    # The flat v1 matcher feeds all eight channels (author patterns also match
    # PR authors and issue participants), and none of them is opt-in.
    for channel in V1_CHANNELS:
        assert f'name="channels" value="{channel}" checked>' in body
    assert 'data-channel="hidden_ref"' not in body
    assert 'Channels (<span id="detect-channels-count">8</span>)' in body


def test_lifecycle_pack_offers_only_channels_its_rules_feed(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_lifecycle_pack(clean)
    body = client.get(f"/detections/from/{source}").text
    for channel in ("file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata"):
        assert f'name="channels" value="{channel}" checked>' in body
    # hidden_ref is supported but opt-in; issue has no rules in this pack.
    assert 'name="channels" value="hidden_ref">' in body
    assert 'data-channel="issue"' not in body
    # Legacy-only families stay selectable and are labelled.
    assert 'value="Brokk" checked> <span>Brokk</span> <span class="muted">(legacy)</span>' in body


def test_options_page_renders_only_the_selected_packs_agents(clean):
    seed_older_pack(clean)
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    body = client.get(f"/detections/from/{source}").text
    # test-pack is the newest frozen pack, so it is selected and only its
    # roster is in the form; the other pack lives only in the JSON map.
    assert '<option value="test-pack" selected>' in body
    assert '<option value="older-pack">' in body
    assert 'data-agent="Claude Code">' in body
    assert 'data-agent="Cursor"' not in body
    assert '"older-pack": {"agents": [{"category": "active", "name": "Cursor"}' in body


def test_options_error_page_keeps_the_submitted_pack_and_selection(clean):
    seed_older_pack(clean)
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
        data={
            "csrf": csrf_token(client),
            "pack_version": "older-pack",
            "agents": ["Ghost"],
            "channels": ["author"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "unknown agents for pack" in response.text
    assert "Ghost" in response.text
    assert '<option value="older-pack" selected>' in response.text
    assert 'data-agent="Cursor">' in response.text
    assert 'data-agent="Claude Code"' not in response.text
    assert 'value="author" checked>' in response.text
    assert 'name="channels" value="file">' in response.text


def test_start_rejects_a_channel_the_pack_cannot_feed(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "channels": ["file", "hidden_ref"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "channels not supported by pack" in response.text
    assert "hidden_ref" in response.text


def test_start_stores_the_whole_roster_as_an_unfiltered_scan(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "agents": ["Claude Code", "Codex", "Generic"],
            "channels": ["file"],
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with clean.connect() as connection:
        spec = connection.execute(
            text("SELECT filter_spec FROM runs WHERE kind = 'detect' ORDER BY id DESC LIMIT 1")
        ).scalar_one()
    assert spec["agents"] is None


def test_estimate_prices_only_the_selected_packs_channels(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    seed_lifecycle_pack(clean)
    older = client.get(
        f"/partials/detections/{source}/estimate?pack_version=test-pack&channels=hidden_ref"
    ).text
    newer = client.get(
        f"/partials/detections/{source}/estimate?pack_version=2026-11-14&channels=hidden_ref"
    ).text
    assert "hidden_ref" not in older
    assert older != newer


def test_start_detection_records_git_source_and_clone(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/detections/from/{source}")
    response = client.post(
        f"/detections/from/{source}",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "channels": ["file", "commit_trailer"],
            "source": "git",
            "clone_depth": "250",
            "clone_keep": "true",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    with clean.connect() as connection:
        spec = connection.execute(
            text("SELECT filter_spec FROM runs WHERE kind = 'detect' ORDER BY id DESC LIMIT 1")
        ).scalar_one()
    assert spec["source"] == "git"
    assert spec["clone"] == {"depth": 250, "keep": True}
