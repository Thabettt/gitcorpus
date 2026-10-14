from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from detect import orchestrator as orchestrator_module
from detect.orchestrator import CHANNELS, DetectConfig, DetectOptions, run_detection
from detect.packs import Pack, Pattern, freeze_pack
from discover.pipeline import Deps
from lib import cancellation
from lib.cancellation import RunCancelled
from serve.executor import create_run, execute_run

PACK = Pack(
    version="v1",
    agents={
        "Claude Code": "https://claude.com",
        "Codex": "https://openai.com/codex",
        "Generic": "https://agents.md",
    },
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"),),
    files=(Pattern(r"CLAUDE\.md", "Claude Code"),),
    branches=(Pattern("codex/", "Codex"),),
    labels=(Pattern("codex", "Codex"),),
    bots=(Pattern(r"dependabot\[bot\]", "dependabot"),),
    generic_weights={"AGENTS.md": 0.3},
    exclusions=frozenset({"CONVENTIONS.md"}),
)

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def seed_source_run(engine) -> int:
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO owners (id, login, type) VALUES (1, 'octo', 'User')"))
        connection.execute(
            text(
                "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility,"
                " default_branch)"
                " VALUES (1, 'n1', 'octo/one', 1, 'one', 'public', 'main'),"
                " (2, 'n2', 'octo/two', 1, 'two', 'public', 'main')"
            )
        )
    source_id = create_run(engine, {"q": "language:rust"}, api_version="2022-11-28")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                " VALUES (:run, 1, 'octo/one', 10), (:run, 2, 'octo/two', 5)"
            ),
            {"run": source_id},
        )
    freeze_pack(engine, PACK)
    return source_id


def make_handler(seen: list[str], queries: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/repos/octo/one/git/trees/main":
            return httpx.Response(
                200, json={"truncated": False, "tree": [{"path": "CLAUDE.md", "type": "blob"}]}
            )
        if request.url.path == "/repos/octo/one/contents/CLAUDE.md":
            return httpx.Response(200, text="# guidance\n")
        if request.url.path == "/repos/octo/one/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/repos/octo/two/git/trees/main":
            return httpx.Response(404, json={"message": "Not Found"})
        if request.url.path == "/repos/octo/two/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/graphql":
            body = json.loads(request.content)
            queries.append(body["query"])
            if body["variables"].get("name") == "two":
                return httpx.Response(200, json={"data": {"repository": None}})
            if "history(" in body["query"]:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "repository": {
                                "object": {
                                    "history": {
                                        "nodes": [
                                            {
                                                "oid": "a1",
                                                "committedDate": "2026-01-02T00:00:00Z",
                                                "message": "feat: x",
                                                "author": {
                                                    "name": "Jane",
                                                    "email": "jane@example.com",
                                                    "user": {"login": "jane"},
                                                },
                                                "committer": {
                                                    "name": "Jane",
                                                    "email": "jane@example.com",
                                                    "user": {"login": "jane"},
                                                },
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    },
                )
            if "pullRequests(" in body["query"]:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "repository": {
                                "pullRequests": {
                                    "nodes": [
                                        {
                                            "number": 7,
                                            "createdAt": "2026-01-03T00:00:00Z",
                                            "headRefName": "codex/fix",
                                            "bodyText": "",
                                            "author": {"login": "jane"},
                                            "labels": {"nodes": []},
                                            "comments": {"nodes": []},
                                            "commits": {
                                                "nodes": [
                                                    {
                                                        "commit": {
                                                            "oid": "a1",
                                                            "author": {"user": {"login": "jane"}},
                                                        }
                                                    }
                                                ]
                                            },
                                        }
                                    ]
                                }
                            }
                        }
                    },
                )
            if "issues(" in body["query"]:
                return httpx.Response(200, json={"data": {"repository": {"issues": {"nodes": []}}}})
        raise AssertionError(request.url)

    return handler


def make_deps(engine, handler) -> Deps:
    return Deps(
        client=httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
        engine=engine,
    )


def make_options(source_id: int, *, agents=None, channels=CHANNELS) -> DetectOptions:
    return DetectOptions(
        source_run_id=source_id,
        pack_version="v1",
        agents=frozenset(agents) if agents is not None else None,
        channels=frozenset(channels),
    )


def test_run_detection_writes_evidence_and_never_searches(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    queries: list[str] = []
    deps = make_deps(engine, make_handler(seen, queries))
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    options = make_options(source_id, agents=["Claude Code", "Codex"])
    payload = run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))

    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT repo_id, agent, channel, evidence FROM detection_evidence"
                    " WHERE run_id = :run ORDER BY agent, channel, repo_id"
                ),
                {"run": run_id},
            )
            .mappings()
            .all()
        )
    pairs = {(row["agent"], row["channel"], row["repo_id"]) for row in rows}
    assert ("Claude Code", "file", 1) in pairs
    assert ("Codex", "pr_metadata", 1) in pairs  # branch match propagated to the PR author's commit
    assert ("Claude Code", "file", 2) not in pairs  # repo two is unavailable
    assert payload.result_summary["agents"] == {
        "Claude Code": 1,
        "Codex": 2,
    }  # branch + propagated commit
    assert payload.result_summary["repos_scanned"] == 2
    assert payload.result_summary["repos_unavailable"] == 1
    item_one = next(item for item in payload.items if item.repo_id == 1)
    assert item_one.detection["agents"] == ["Claude Code", "Codex"]
    assert item_one.detection["adoption_level"] == "pervasive"  # 1 AI of 1 windowed commit -> 100%
    assert item_one.detection["first_signal_at"] == "2026-01-02T00:00:00Z"
    assert len(payload.detections) == len(rows)
    assert all("/search" not in path for path in seen)
    assert all("search(" not in query for query in queries)


def test_run_detection_never_persists_emails(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/graphql":
            body = json.loads(request.content)
            if "history(" in body["query"]:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "repository": {
                                "object": {
                                    "history": {
                                        "nodes": [
                                            {
                                                "oid": "a1",
                                                "committedDate": "2026-01-02T00:00:00Z",
                                                "message": (
                                                    "fix: x\n\nCo-authored-by: Claude"
                                                    " <noreply@anthropic.com>"
                                                ),
                                                "author": {
                                                    "name": "Jane",
                                                    "email": "jane@example.com",
                                                    "user": {"login": "jane"},
                                                },
                                                "committer": {
                                                    "name": "Jane",
                                                    "email": "jane@example.com",
                                                    "user": {"login": "jane"},
                                                },
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    },
                )
            if "pullRequests(" in body["query"]:
                return httpx.Response(
                    200, json={"data": {"repository": {"pullRequests": {"nodes": []}}}}
                )
            if "issues(" in body["query"]:
                return httpx.Response(200, json={"data": {"repository": {"issues": {"nodes": []}}}})
        if request.url.path.endswith("/contents/.gitignore"):
            return httpx.Response(404)
        return httpx.Response(404, json={"message": "Not Found"})

    deps = make_deps(engine, handler)
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    options = make_options(source_id)
    payload = run_detection(deps, run_id, options, PACK)
    with engine.connect() as connection:
        evidence_text = "\n".join(
            str(row[0])
            for row in connection.execute(
                text("SELECT evidence::text FROM detection_evidence WHERE run_id = :run"),
                {"run": run_id},
            )
        )
        audit_text = "\n".join(
            str(row[0])
            for row in connection.execute(
                text("SELECT params::text FROM audit_log WHERE run_id = :run"), {"run": run_id}
            )
        )
    assert not EMAIL.search(evidence_text), evidence_text
    assert not EMAIL.search(audit_text), audit_text
    assert not EMAIL.search(json.dumps(payload.detections))
    assert "<email>" in evidence_text


def test_run_detection_isolates_one_repo_failure(clean_db, monkeypatch):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    queries: list[str] = []
    deps = make_deps(engine, make_handler(seen, queries))
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )

    def boom(*args, **kwargs):
        raise RuntimeError("boom in file channel")

    monkeypatch.setattr(orchestrator_module, "detect_files", boom)
    options = make_options(source_id, channels=["file"])
    payload = run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))

    assert payload.incomplete is True
    assert payload.result_summary["repos_scanned"] == 2
    assert payload.result_summary["repos_unavailable"] == 2
    assert payload.result_summary["agents"] == {}
    failed = next(item for item in payload.items if item.repo_id == 1)
    assert failed.detection["unavailable"] is True
    assert failed.detection["agents"] == []
    assert failed.detection["adoption_level"] == "none"
    assert failed.detection["notes"] == ["RuntimeError: boom in file channel"]
    assert sorted(payload.warnings) == [
        "octo/one: RuntimeError: boom in file channel",
        "octo/two: RuntimeError: boom in file channel",
    ]
    assert payload.detections == []


def test_run_detection_cancelled_before_start_writes_nothing(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    queries: list[str] = []
    deps = make_deps(engine, make_handler(seen, queries))
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    options = make_options(source_id, agents=["Claude Code", "Codex"])
    token = cancellation.bind(lambda: True)
    try:
        with pytest.raises(RunCancelled):
            run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))
    finally:
        cancellation.reset(token)
    with engine.connect() as connection:
        count = connection.scalar(
            text("SELECT count(*) FROM detection_evidence WHERE run_id = :run"), {"run": run_id}
        )
    assert count == 0
    assert seen == []
    assert queries == []


def test_execute_run_writes_result_summary_and_detections_csv(clean_db, tmp_path):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    queries: list[str] = []
    deps = make_deps(engine, make_handler(seen, queries))
    options = make_options(source_id, agents=["Claude Code", "Codex"])
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    execute_run(
        engine,
        run_id,
        runner=lambda rid, _doc: run_detection(
            deps, rid, options, PACK, config=DetectConfig(concurrency=2)
        ),
        runs_root=str(tmp_path),
    )
    with engine.connect() as connection:
        row = (
            connection.execute(
                text("SELECT status, result_summary FROM runs WHERE id = :run"), {"run": run_id}
            )
            .mappings()
            .one()
        )
        detections = connection.execute(
            text("SELECT detection FROM run_items WHERE run_id = :run AND repo_id = 1"),
            {"run": run_id},
        ).scalar_one()
    assert row["status"] in ("done", "partial")
    assert row["result_summary"]["agents"] == {"Claude Code": 1, "Codex": 2}
    assert detections["agents"] == ["Claude Code", "Codex"]
    evidence_csv = list(Path(tmp_path).glob(f"*/{run_id}/detections.csv"))
    assert len(evidence_csv) == 1
    with evidence_csv[0].open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header == ["full_name", "repo_id", "agent", "channel", "evidence", "pack_version"]
