from __future__ import annotations

import csv
import io
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
from serve.executor import EVIDENCE_CSV_HEADER


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
            connection.execute(
                text(
                    "INSERT INTO detection_repo_filters (run_id, repo_id, agent, channel)"
                    " VALUES (:run, :repo, 'Claude Code', 'file')"
                ),
                [{"run": run_id, "repo": repo_id} for repo_id in range(1, repo_count + 1)],
            )
    return int(run_id)


def seed_detect_run_with_evidence(engine, source_id, rows) -> int:
    """Seed a detect run whose evidence rows are given explicitly.

    rows: dicts with `repo` (1-based index), `agent`, `channel`, and `evidence` (dict).
    Each repo's detection rollup is derived from its rows.
    """
    repo_count = max(row["repo"] for row in rows)
    spec = {
        "version": 1,
        "kind": "detect",
        "source_run_id": source_id,
        "pack_version": "test-pack",
        "agents": None,
        "channels": sorted({row["channel"] for row in rows}),
        "limit": None,
        "windows": {"commits": 100, "prs": 100, "issues": 100},
    }
    summary = {
        "repos_scanned": repo_count,
        "repos_with_signal": repo_count,
        "repos_unavailable": 0,
        "agents": {},
        "channels": {},
        "pack_version": "test-pack",
        "agents_selected": "all",
        "windows": {"commits": 100, "prs": 100, "issues": 100},
        "commit_ratio": 1.0,
        "adoption_level": "pervasive",
        "first_signal_at": "2026-01-02T00:00:00Z",
        "partial_channels": {},
    }
    with engine.begin() as connection:
        run_id = int(
            connection.execute(
                text(
                    "INSERT INTO runs (filter_hash, filter_spec, api_version, status, kind,"
                    " source_run_id, result_summary, finished_at)"
                    " VALUES ('detect-hash', CAST(:spec AS jsonb), '2022-11-28', 'done', 'detect',"
                    " :src, CAST(:summary AS jsonb), now()) RETURNING id"
                ),
                {"src": source_id, "spec": json.dumps(spec), "summary": json.dumps(summary)},
            ).scalar_one()
        )
        for repo_index in range(1, repo_count + 1):
            if repo_index > 1:
                connection.execute(
                    text(
                        "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility)"
                        " VALUES (:id, :node, :full_name, 1, :name, 'public')"
                    ),
                    {
                        "id": repo_index,
                        "node": f"n{repo_index}",
                        "full_name": f"octo/r{repo_index}",
                        "name": f"r{repo_index}",
                    },
                )
            repo_rows = [row for row in rows if row["repo"] == repo_index]
            agents = sorted({row["agent"] for row in repo_rows if row["channel"] != "bot"})
            detection = {
                "agents": agents,
                "channels": {
                    channel: "ok" for channel in sorted({r["channel"] for r in repo_rows})
                },
                "unavailable": False,
                "commit_ratio": 1.0 if agents else None,
                "adoption_level": "pervasive" if agents else "none",
                "first_signal_at": "2026-01-02T00:00:00Z" if agents else None,
                "notes": [],
            }
            connection.execute(
                text(
                    "INSERT INTO run_items (run_id, repo_id, full_name, stargazers, detection)"
                    " VALUES (:run, :repo, :full_name, :stargazers, CAST(:detection AS jsonb))"
                ),
                {
                    "run": run_id,
                    "repo": repo_index,
                    "full_name": "octo/one" if repo_index == 1 else f"octo/r{repo_index}",
                    "stargazers": 1000 - repo_index,
                    "detection": json.dumps(detection),
                },
            )
        connection.execute(
            text(
                "INSERT INTO detection_evidence (run_id, repo_id, agent, channel, evidence,"
                " pack_version) VALUES (:run, :repo, :agent, :channel, CAST(:evidence AS jsonb),"
                " 'test-pack')"
            ),
            [
                {
                    "run": run_id,
                    "repo": row["repo"],
                    "agent": row["agent"],
                    "channel": row["channel"],
                    "evidence": json.dumps(row["evidence"]),
                }
                for row in rows
            ],
        )
        connection.execute(
            text(
                "INSERT INTO detection_repo_filters (run_id, repo_id, agent, channel)"
                " VALUES (:run, :repo, :agent, :channel) ON CONFLICT DO NOTHING"
            ),
            [
                {
                    "run": run_id,
                    "repo": row["repo"],
                    "agent": row["agent"],
                    "channel": row["channel"],
                }
                for row in rows
            ],
        )
    return run_id


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


def test_detections_export_renders_flat_evidence_csv(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    rows = [
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": "CLAUDE.md", "source": "tree", "size": 12, "empty": False},
        },
        {
            "repo": 1,
            "agent": "Codex",
            "channel": "pr_metadata",
            "evidence": {"pr": 7, "commit": "a1", "propagated": True},
        },
        {
            "repo": 2,
            "agent": "Claude Code",
            "channel": "commit_trailer",
            "evidence": {"commit": "b2", "snippet": "Co-authored-by: Claude"},
        },
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    response = client.get(f"/runs/{detect_id}/export?format=detections")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers.get("x-gitcorpus-regenerated") == "true"
    assert (
        f'filename="gitcorpus-detect-{detect_id}-evidence.csv"'
        in response.headers["content-disposition"]
    )
    assert response.content[:3] == b"\xef\xbb\xbf"
    body = response.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(body))
    assert reader.fieldnames == EVIDENCE_CSV_HEADER
    exported = list(reader)
    with clean.connect() as connection:
        stored = connection.execute(
            text("SELECT count(*) FROM detection_evidence WHERE run_id = :run"),
            {"run": detect_id},
        ).scalar_one()
    assert len(exported) == stored == len(rows)
    file_row = next(row for row in exported if row["channel"] == "file")
    assert file_row["full_name"] == "octo/one"
    assert file_row["run_id"] == str(detect_id)
    assert file_row["agent"] == "Claude Code"
    assert file_row["pack_version"] == "test-pack"
    assert file_row["path"] == "CLAUDE.md"
    assert file_row["path_source"] == "tree"
    assert file_row["file_size"] == "12"
    assert file_row["file_empty"] == "false"
    assert file_row["detected_at"]
    assert json.loads(file_row["evidence_json"]) == {
        "path": "CLAUDE.md",
        "source": "tree",
        "size": 12,
        "empty": False,
    }
    propagated = next(row for row in exported if row["channel"] == "pr_metadata")
    assert propagated["pr_number"] == "7"
    assert propagated["commit_sha"] == "a1"
    assert propagated["propagated"] == "true"
    trailer = next(row for row in exported if row["channel"] == "commit_trailer")
    assert trailer["snippet"] == "Co-authored-by: Claude"
    assert trailer["commit_sha"] == "b2"


def test_detections_export_is_single_line_and_reads_back(clean):
    from serve.runs import DETECT_REPO_CSV_HEADER

    source = seed_find_run(clean)
    seed_pack(clean)
    rows = [
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "commit_trailer",
            "evidence": {"commit": "b1", "snippet": "first\n\nsecond"},
        },
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "commit_trailer",
            "evidence": {"commit": "b2", "snippet": "single line"},
        },
        {
            "repo": 1,
            "agent": "Codex",
            "channel": "pr_metadata",
            "evidence": {"pr": 7, "commit": "a1", "propagated": True},
        },
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    response = client.get(f"/runs/{detect_id}/export?format=detections")
    assert response.status_code == 200
    assert response.content[:3] == b"\xef\xbb\xbf"
    body = response.content.decode("utf-8-sig")
    with clean.connect() as connection:
        stored = connection.execute(
            text("SELECT count(*) FROM detection_evidence WHERE run_id = :run"),
            {"run": detect_id},
        ).scalar_one()
    raw_records = list(csv.reader(io.StringIO(body)))
    assert len(raw_records) == stored + 1
    assert all(len(record) == len(EVIDENCE_CSV_HEADER) for record in raw_records)
    assert body.count("\n") == stored + 1
    exported = list(csv.DictReader(io.StringIO(body)))
    assert len(exported) == stored == len(rows)
    by_commit = {row["commit_sha"]: row for row in exported}
    assert by_commit["b1"]["snippet"] == "first\\n\\nsecond"
    assert by_commit["b2"]["snippet"] == "single line"
    assert all(
        "\n" not in value and "\r" not in value for row in exported for value in row.values()
    )
    repo_response = client.get(f"/runs/{detect_id}/export?format=csv")
    assert repo_response.status_code == 200
    assert repo_response.content[:3] == b"\xef\xbb\xbf"
    repo_body = repo_response.content.decode("utf-8-sig")
    repo_records = list(csv.reader(io.StringIO(repo_body)))
    assert repo_records[0] == DETECT_REPO_CSV_HEADER
    assert repo_body.count("\n") == len(repo_records)


def test_detect_repo_export_has_detection_rollup_columns(clean):
    from serve.runs import DETECT_REPO_CSV_HEADER

    source = seed_find_run(clean)
    seed_pack(clean)
    rows = [
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": "CLAUDE.md"},
        },
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "pr_metadata",
            "evidence": {"pr": 7, "commit": "a1", "propagated": True},
        },
        {
            "repo": 1,
            "agent": "github actions",
            "channel": "bot",
            "evidence": {"login": "github-actions[bot]", "field": "login", "commit": "c3"},
        },
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    response = client.get(f"/runs/{detect_id}/export?format=csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        f'filename="gitcorpus-detect-{detect_id}-repos.csv"'
        in response.headers["content-disposition"]
    )
    assert response.content[:3] == b"\xef\xbb\xbf"
    body = response.content.decode("utf-8-sig")
    assert body.count("\n") == 2
    reader = csv.DictReader(io.StringIO(body))
    assert reader.fieldnames == DETECT_REPO_CSV_HEADER
    by_id = {row["repo_id"]: row for row in reader}
    assert set(by_id) == {"1"}
    row = by_id["1"]
    assert row["full_name"] == "octo/one"
    assert row["has_signal"] == "true"
    assert row["agents"] == "Claude Code"
    assert row["evidence_rows"] == "3"
    assert row["signal_rows"] == "2"
    assert row["bot_rows"] == "1"
    assert row["file_rows"] == "1"
    assert row["pr_metadata_rows"] == "1"
    assert row["commit_trailer_rows"] == "0"
    assert row["unavailable"] == "false"
    assert row["adoption_level"] == "pervasive"


def test_detect_json_export_includes_detection_rollup(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    rows = [
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": "CLAUDE.md"},
        },
        {
            "repo": 2,
            "agent": "Codex",
            "channel": "file",
            "evidence": {"path": "AGENTS.md"},
        },
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    response = client.get(f"/runs/{detect_id}/export?format=json")
    assert response.status_code == 200
    assert response.headers.get("x-gitcorpus-regenerated") == "true"
    payload = response.json()
    items = {item["full_name"]: item for item in payload["items"]}
    assert items["octo/one"]["detection"]["agents"] == ["Claude Code"]
    assert items["octo/r2"]["detection"]["agents"] == ["Codex"]
    assert payload["run_id"] == detect_id


def test_detect_export_refuses_while_run_is_unfinished(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET status = 'running', finished_at = NULL WHERE id = :id"),
            {"id": detect_id},
        )
    client = make_client(clean)
    for fmt in ("detections", "csv", "json"):
        response = client.get(f"/runs/{detect_id}/export?format={fmt}")
        assert response.status_code == 409
        assert response.json()["error"] == "run_not_ready"


def test_detections_export_streams_bounded_batches(clean):
    from serve.runs import _detections_chunks

    source = seed_find_run(clean)
    seed_pack(clean)
    rows = [
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": f"file-{index}.md"},
        }
        for index in range(5)
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    chunks = list(_detections_chunks(clean, detect_id, batch_rows=2))
    assert chunks[0].startswith(b"\xef\xbb\xbf")
    assert chunks[0].decode("utf-8-sig").startswith("run_id,")
    sizes = [
        len([line for line in chunk.decode("utf-8").splitlines() if line]) for chunk in chunks[1:]
    ]
    assert sizes
    assert all(size <= 2 for size in sizes)
    assert sum(sizes) == 5


def test_detection_export_buttons_hide_until_the_run_finishes(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET status = 'running', finished_at = NULL WHERE id = :id"),
            {"id": detect_id},
        )
    running = client.get(f"/detections/{detect_id}")
    assert "Export evidence CSV" not in running.text
    assert "Export CSV" not in running.text
    assert "Exports unlock when the run finishes." in running.text
    with clean.begin() as connection:
        connection.execute(
            text("UPDATE runs SET status = 'done', finished_at = now() WHERE id = :id"),
            {"id": detect_id},
        )
    done = client.get(f"/detections/{detect_id}")
    assert "Export evidence CSV" in done.text


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


def test_detection_detail_has_server_side_filter_form(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(f"/detections/{detect_id}")
    assert response.status_code == 200
    assert 'id="detection-filters"' in response.text
    assert 'method="get"' in response.text
    assert 'name="signal"' in response.text
    assert 'name="agent"' in response.text
    assert 'name="channel"' in response.text
    assert '<option value="Claude Code">Claude Code</option>' in response.text
    assert '<option value="file">file</option>' in response.text
    assert "data-agents=" not in response.text


def test_detection_filter_form_reflects_current_filters(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(
        f"/detections/{detect_id}",
        params={"signal": "1", "agent": "Claude Code", "channel": "file"},
    )
    assert response.status_code == 200
    assert 'name="signal" value="1" checked' in response.text
    assert '<option value="Claude Code" selected>' in response.text
    assert '<option value="file" selected>' in response.text


def test_detection_evidence_filters_search_the_whole_run(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    repo_count = DETECTION_REPOS_PAGE_SIZE + 5
    rows = [
        {
            "repo": index,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": f"file-{index}.md"},
        }
        for index in range(1, repo_count + 1)
    ]
    rows.append(
        {
            "repo": repo_count,
            "agent": "Codex",
            "channel": "pr_metadata",
            "evidence": {"pr": 9, "commit": "aa", "propagated": True},
        }
    )
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    page1 = client.get(f"/detections/{detect_id}")
    assert f'id="detection-repo-{repo_count}"' not in page1.text
    filtered = client.get(f"/detections/{detect_id}", params={"agent": "Codex"})
    assert f'id="detection-repo-{repo_count}"' in filtered.text
    assert 'id="detection-repo-1"' not in filtered.text
    assert "repos 1–1 of 1 (filtered)" in filtered.text


def test_detection_filter_options_cover_the_whole_run(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    repo_count = DETECTION_REPOS_PAGE_SIZE + 5
    rows = [
        {
            "repo": index,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": f"file-{index}.md"},
        }
        for index in range(1, repo_count + 1)
    ]
    rows.append(
        {
            "repo": repo_count,
            "agent": "Codex",
            "channel": "pr_metadata",
            "evidence": {"pr": 9, "commit": "aa", "propagated": True},
        }
    )
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    page1 = client.get(f"/detections/{detect_id}")
    assert '<option value="Codex">Codex</option>' in page1.text
    assert '<option value="pr_metadata">pr_metadata</option>' in page1.text


def test_detection_filters_compose_agent_and_channel(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    rows = [
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": "CLAUDE.md"},
        },
        {
            "repo": 1,
            "agent": "Codex",
            "channel": "pr_metadata",
            "evidence": {"pr": 7, "commit": "a1", "propagated": True},
        },
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    combined = client.get(
        f"/detections/{detect_id}", params={"agent": "Claude Code", "channel": "pr_metadata"}
    )
    assert "No repos match these filters." in combined.text
    match = client.get(
        f"/detections/{detect_id}", params={"agent": "Claude Code", "channel": "file"}
    )
    assert 'id="detection-repo-1"' in match.text


def test_detection_filters_show_only_matching_evidence_rows(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    rows = [
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": "CLAUDE.md"},
        },
        {
            "repo": 1,
            "agent": "Codex",
            "channel": "pr_metadata",
            "evidence": {"pr": 7, "commit": "a1", "propagated": True},
        },
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    filtered = client.get(f"/detections/{detect_id}", params={"channel": "pr_metadata"})
    assert "PR #7" in filtered.text
    assert "CLAUDE.md" not in filtered.text
    unfiltered = client.get(f"/detections/{detect_id}")
    assert "CLAUDE.md" in unfiltered.text


def test_detection_signal_filter_excludes_bot_only_repos(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    rows = [
        {
            "repo": 1,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": "CLAUDE.md"},
        },
        {
            "repo": 1,
            "agent": "github actions",
            "channel": "bot",
            "evidence": {"login": "github-actions[bot]", "field": "login", "commit": "c1"},
        },
        {
            "repo": 2,
            "agent": "dependabot",
            "channel": "bot",
            "evidence": {"login": "dependabot", "field": "login", "commit": "c2"},
        },
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    response = client.get(f"/detections/{detect_id}", params={"signal": "1"})
    assert 'id="detection-repo-1"' in response.text
    assert 'id="detection-repo-2"' not in response.text
    assert "repos 1–1 of 1 (filtered)" in response.text
    unfiltered = client.get(f"/detections/{detect_id}")
    assert 'id="detection-repo-2"' in unfiltered.text


def test_detection_pagination_preserves_filters(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    repo_count = DETECTION_REPOS_PAGE_SIZE + 5
    rows = [
        {
            "repo": index,
            "agent": "Claude Code",
            "channel": "file",
            "evidence": {"path": f"file-{index}.md"},
        }
        for index in range(1, repo_count + 1)
    ]
    detect_id = seed_detect_run_with_evidence(clean, source, rows)
    client = make_client(clean)
    page1 = client.get(f"/detections/{detect_id}", params={"agent": "Claude Code"})
    assert f"repos 1–{DETECTION_REPOS_PAGE_SIZE} of {repo_count} (filtered)" in page1.text
    assert "page=2&amp;agent=Claude+Code" in page1.text
    page2 = client.get(f"/detections/{detect_id}", params={"agent": "Claude Code", "page": "2"})
    assert f'id="detection-repo-{repo_count}"' in page2.text
    assert f"repos {DETECTION_REPOS_PAGE_SIZE + 1}–{repo_count} of {repo_count} (filtered)" in (
        page2.text
    )
    assert "page=1&amp;agent=Claude+Code" in page2.text


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
