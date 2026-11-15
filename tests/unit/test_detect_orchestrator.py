from __future__ import annotations

import csv
import json
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import text

from detect import orchestrator as orchestrator_module
from detect.channels import ChannelResult, FailureKind
from detect.orchestrator import CHANNELS, DetectConfig, DetectOptions, run_detection
from detect.packs import Pack, Pattern, freeze_pack
from detect.token_pool import DetectionTokenPool, TokenPoolExhausted
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
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers,"
                " repo_created_at, commit_count, language, country_iso, geo_confidence)"
                " VALUES (:run, 1, 'octo/one', 10, '2024-01-01T00:00:00Z', 1,"
                " 'Python', 'DE', 'name'),"
                " (:run, 2, 'octo/two', 5, '2025-02-01T00:00:00Z', 0,"
                " 'Rust', NULL, NULL)"
            ),
            {"run": source_id},
        )
    freeze_pack(engine, PACK)
    return source_id


def test_candidates_snapshot_repo_metadata_missing_from_imported_run(clean_db):
    engine = clean_db(
        owners=[{"id": 1, "login": "octo", "type": "User"}],
        repos=[
            {
                "id": 1,
                "node_id": "n1",
                "full_name": "octo/one",
                "owner_id": 1,
                "name": "one",
                "visibility": "public",
                "language": "Rust",
                "license_spdx": "MIT",
                "stargazers": 42,
                "default_branch": "main",
                "created_at": "2024-01-01T00:00:00Z",
            }
        ],
    )
    source_id = create_run(engine, {"q": "import: repos.csv"}, api_version="2022-11-28")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name)" " VALUES (:run, 1, 'octo/one')"
            ),
            {"run": source_id},
        )
    candidate = orchestrator_module._candidates(engine, source_id, None)[0]
    assert candidate["language"] == "Rust"
    assert candidate["license_spdx"] == "MIT"
    assert candidate["stargazers"] == 42
    assert candidate["repo_created_at"] is not None


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
                                        "totalCount": 1,
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
                                        ],
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


def test_candidates_top_n_is_deterministic(clean_db):
    engine = clean_db()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO owners (id, login, type) VALUES (1, 'octo', 'User')"))
        connection.execute(
            text(
                "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility)"
                " VALUES (1, 'n1', 'octo/one', 1, 'one', 'public'),"
                " (2, 'n2', 'octo/two', 1, 'two', 'public'),"
                " (3, 'n3', 'octo/three', 1, 'three', 'public'),"
                " (4, 'n4', 'octo/four', 1, 'four', 'public'),"
                " (5, 'n5', 'octo/five', 1, 'five', 'public')"
            )
        )
    source_id = create_run(engine, {"q": "language:rust"}, api_version="2022-11-28")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                " VALUES (:run, 1, 'octo/one', 100), (:run, 2, 'octo/two', 50),"
                " (:run, 3, 'octo/three', 50), (:run, 4, 'octo/four', NULL),"
                " (:run, 5, 'octo/five', 10)"
            ),
            {"run": source_id},
        )
    order = [row["repo_id"] for row in orchestrator_module._candidates(engine, source_id, None)]
    assert order == [1, 2, 3, 5, 4]  # stargazers DESC, repo_id ASC tie-break, NULLS LAST
    top_three = [row["repo_id"] for row in orchestrator_module._candidates(engine, source_id, 3)]
    assert top_three == [1, 2, 3]
    top_four = [row["repo_id"] for row in orchestrator_module._candidates(engine, source_id, 4)]
    assert top_four == [1, 2, 3, 5]


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
    assert item_one.commit_count == 1
    assert item_one.language == "Python"
    assert item_one.country_iso == "DE"
    assert datetime.fromisoformat(item_one.repo_created_at).astimezone(UTC) == datetime(
        2024, 1, 1, tzinfo=UTC
    )
    assert payload.detections == []
    assert len(list(payload.detections_source())) == len(rows)
    assert all("/search" not in path for path in seen)
    assert all("search(" not in query for query in queries)


def test_run_detection_leases_distinct_dependencies_from_a_token_pool(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        return httpx.Response(
            200,
            json={"data": {"repository": {"object": {"history": {"totalCount": 0, "nodes": []}}}}},
        )

    first = make_deps(engine, handler)
    second = make_deps(engine, handler)
    first = Deps(client=first.client, engine=engine, token_fp="first")
    second = Deps(client=second.client, engine=engine, token_fp="second")
    leased: list[str] = []

    class Lease:
        def __init__(self, deps):
            self.deps = deps

        def __enter__(self):
            leased.append(self.deps.token_fp)
            return self.deps

        def __exit__(self, exc_type, exc, traceback):
            return None

    class Pool:
        def __init__(self):
            self.dependencies = iter((first, second))

        def lease(self, *, exclude=None):
            return Lease(next(self.dependencies))

        def observe(self, token_fp, response, phase):
            return None

        def stats(self):
            return {"tokens": 4}

    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    live_stats: list[dict[str, object]] = []
    payload = run_detection(
        first,
        run_id,
        make_options(source_id, agents=["Claude Code", "Codex"], channels=("author",)),
        PACK,
        config=DetectConfig(
            concurrency=2,
            pool_stats_reporter=live_stats.append,
            pool_stats_interval=0,
        ),
        token_pool=Pool(),
    )
    assert set(leased) == {"first", "second"}
    assert payload.field_stats["token_pool"] == {"tokens": 4}
    assert payload.result_summary["token_pool"] == {"tokens": 4}
    assert live_stats and live_stats[-1] == {"tokens": 4}


def _scan_with(result: ChannelResult, *, full_name: str = "octo/one"):
    return orchestrator_module._RepoScan(
        repo_id=1,
        full_name=full_name,
        stargazers=1,
        hits=[],
        results={"file": result},
        pr_result=None,
        history_stats={},
    )


def test_permanent_failure_does_not_retry_another_identity():
    scan = _scan_with(
        ChannelResult(status="partial", note="graphql errors", failure_kind=FailureKind.PERMANENT)
    )

    assert orchestrator_module._retry_on_another_identity(scan) is False


def test_not_found_scan_retries_another_identity():
    scan = _scan_with(
        ChannelResult(
            status="unavailable", note="repo not found", failure_kind=FailureKind.NOT_FOUND
        ),
        full_name="octo/private",
    )

    assert orchestrator_module._retry_on_another_identity(scan) is True


def test_pool_scan_tries_every_identity_before_reporting_not_found(monkeypatch):
    from detect.token_pool import TokenPoolRetryExhausted

    accounts = ("first", "second", "third", "fourth")
    exclusions: list[frozenset[str]] = []
    not_found = _scan_with(
        ChannelResult(
            status="unavailable", note="repo not found", failure_kind=FailureKind.NOT_FOUND
        ),
        full_name="octo/gone",
    )

    class Lease:
        def __init__(self, deps):
            self.deps = deps

        def __enter__(self):
            return self.deps

        def __exit__(self, exc_type, exc, traceback):
            return None

    class Pool:
        def lease(self, *, exclude=None):
            excluded = exclude or frozenset()
            exclusions.append(excluded)
            remaining = [fp for fp in accounts if fp not in excluded]
            if not remaining:
                raise TokenPoolRetryExhausted("no untried identity")
            return Lease(SimpleNamespace(token_fp=remaining[0]))

        def observe(self, token_fp, response, phase):
            return None

        def raise_if_exhausted(self):
            return None

    monkeypatch.setattr(orchestrator_module, "_scan_repo", lambda *args, **kwargs: not_found)

    result = orchestrator_module._scan_repo_from_pool(Pool(), PACK, make_options(1), 1, None, {})

    assert result is not_found
    assert exclusions == [
        frozenset(),
        frozenset({"first"}),
        frozenset({"first", "second"}),
        frozenset({"first", "second", "third"}),
    ]


def test_transient_scan_retries_another_identity_without_note_matching():
    scan = orchestrator_module._RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[],
        results={
            "author": ChannelResult(
                status="partial",
                note="opaque upstream failure",
                failure_kind=FailureKind.RETRYABLE,
            )
        },
        pr_result=None,
        history_stats={},
    )

    assert orchestrator_module._retry_on_another_identity(scan) is True


def test_pool_scan_releases_a_transient_failure_to_another_identity(monkeypatch):
    dependencies = iter(
        (
            SimpleNamespace(token_fp="first"),
            SimpleNamespace(token_fp="second"),
        )
    )
    exclusions: list[frozenset[str]] = []
    transient = orchestrator_module._RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[],
        results={
            "file": ChannelResult(
                status="partial",
                note="HTTP 502",
                failure_kind=FailureKind.RETRYABLE,
            )
        },
        pr_result=None,
        history_stats={},
    )
    recovered = orchestrator_module._RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[],
        results={"file": ChannelResult(status="ok")},
        pr_result=None,
        history_stats={},
    )
    scans = iter((transient, recovered))

    class Lease:
        def __init__(self, deps):
            self.deps = deps

        def __enter__(self):
            return self.deps

        def __exit__(self, exc_type, exc, traceback):
            return None

    class Pool:
        def lease(self, *, exclude=None):
            exclusions.append(exclude or frozenset())
            return Lease(next(dependencies))

        def observe(self, token_fp, response, phase):
            return None

        def raise_if_exhausted(self):
            return None

    monkeypatch.setattr(
        orchestrator_module,
        "_scan_repo",
        lambda *args, **kwargs: next(scans),
    )

    result = orchestrator_module._scan_repo_from_pool(Pool(), PACK, make_options(1), 1, None, {})

    assert result is recovered
    assert exclusions == [frozenset(), frozenset({"first"})]


def test_pool_exhaustion_aborts_detection_instead_of_writing_failed_repos(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    deps = make_deps(engine, make_handler([], []))

    class ExhaustedPool:
        def lease(self, *, exclude=None):
            raise TokenPoolExhausted("all GitHub identities are disabled")

        def stats(self):
            return {"tokens": 4}

    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )

    with pytest.raises(TokenPoolExhausted, match="all GitHub identities"):
        run_detection(
            deps,
            run_id,
            make_options(source_id, channels=("file",)),
            PACK,
            config=DetectConfig(concurrency=2),
            token_pool=ExhaustedPool(),
        )

    with engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT count(*) FROM run_items WHERE run_id = :run"),
                {"run": run_id},
            )
            == 0
        )


_GRAPHQL_HEADERS = {
    "x-ratelimit-resource": "graphql",
    "x-ratelimit-remaining": "4998",
    "x-ratelimit-reset": "4102444800",
}
_RATE_LIMIT = {
    "cost": 1,
    "limit": 5000,
    "used": 2,
    "remaining": 4998,
    "resetAt": "2100-01-01T00:00:00Z",
}


def _pool_account_deps(engine, account: int, can_see=lambda name: True) -> Deps:
    """One pooled GitHub account; ``can_see(repo_name)`` decides 200 versus NOT_FOUND."""

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(
                200,
                json={"login": f"account-{account}"},
                headers={
                    "x-ratelimit-resource": "core",
                    "x-ratelimit-remaining": "4999",
                    "x-ratelimit-reset": "4102444800",
                },
            )
        body = json.loads(request.content)
        if "viewer" in body["query"]:
            return httpx.Response(
                200,
                json={
                    "data": {"viewer": {"login": f"account-{account}"}, "rateLimit": _RATE_LIMIT}
                },
                headers=_GRAPHQL_HEADERS,
            )
        name = body["variables"]["name"]
        if not can_see(name):
            return httpx.Response(
                200,
                json={
                    "data": {"repository": None, "rateLimit": _RATE_LIMIT},
                    "errors": [
                        {
                            "type": "NOT_FOUND",
                            "message": f"Could not resolve to a Repository with the name '{name}'.",
                        }
                    ],
                },
                headers=_GRAPHQL_HEADERS,
            )
        return httpx.Response(
            200,
            json={
                "data": {
                    "repository": {"object": {"history": {"totalCount": 0, "nodes": []}}},
                    "rateLimit": _RATE_LIMIT,
                }
            },
            headers=_GRAPHQL_HEADERS,
        )

    return Deps(
        client=httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
        engine=engine,
        token_fp=f"pool-{account}",
    )


def _detect_with_pool(engine, source_id: int, dependencies: list[Deps]) -> tuple[int, object]:
    token_pool = DetectionTokenPool(dependencies, ("author",))
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    try:
        token_pool.preflight()
        payload = run_detection(
            token_pool.primary,
            run_id,
            make_options(source_id, channels=("author",)),
            PACK,
            config=DetectConfig(concurrency=4),
            token_pool=token_pool,
        )
    finally:
        token_pool.close()
    return run_id, payload


def test_real_four_token_pool_preflights_and_audits_each_leased_identity(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    dependencies = [_pool_account_deps(engine, index) for index in range(4)]

    run_id, payload = _detect_with_pool(engine, source_id, dependencies)

    assert payload.result_summary["repos_scanned"] == 2
    with engine.connect() as connection:
        fingerprints = set(
            connection.scalars(
                text("SELECT DISTINCT token_fp FROM audit_log WHERE run_id = :run"),
                {"run": run_id},
            )
        )
    assert fingerprints == {"pool-0", "pool-1"}


def _author_channel(engine, run_id: int, repo_id: int) -> dict:
    with engine.connect() as connection:
        detection = connection.scalar(
            text("SELECT detection FROM run_items WHERE run_id = :run AND repo_id = :repo"),
            {"run": run_id, "repo": repo_id},
        )
    return {"unavailable": detection["unavailable"], "status": detection["channels"]["author"]}


def test_pool_reads_a_repo_only_one_account_can_see_on_every_run(clean_db):
    """404 from the leased account, 200 from another: availability is lease-independent."""
    engine = clean_db()
    source_id = seed_source_run(engine)
    owner = 3  # the only pooled account that can see octo/one

    outcomes = []
    for _ in range(3):
        dependencies = [
            _pool_account_deps(
                engine,
                index,
                can_see=lambda name, account=index: name != "one" or account == owner,
            )
            for index in range(4)
        ]
        run_id, payload = _detect_with_pool(engine, source_id, dependencies)
        assert payload.result_summary["repos_unavailable"] == 0
        outcomes.append(_author_channel(engine, run_id, 1))

    assert all(outcome["unavailable"] is False for outcome in outcomes)
    assert all(outcome["status"] == "ok" for outcome in outcomes)


def test_pool_marks_a_repo_unavailable_only_after_every_account_misses(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    dependencies = [
        _pool_account_deps(engine, index, can_see=lambda name: name != "one") for index in range(4)
    ]

    run_id, payload = _detect_with_pool(engine, source_id, dependencies)

    assert payload.result_summary["repos_unavailable"] == 1
    outcome = _author_channel(engine, run_id, 1)
    assert outcome["unavailable"] is True
    assert outcome["status"] == "unavailable"
    with engine.connect() as connection:
        tried = set(
            connection.scalars(
                text("SELECT DISTINCT token_fp FROM audit_log WHERE run_id = :run"),
                {"run": run_id},
            )
        )
    assert tried == {"pool-0", "pool-1", "pool-2", "pool-3"}


def test_candidates_exclude_private_and_internal_repos(clean_db):
    engine = clean_db()
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO owners (id, login, type) VALUES (1, 'octo', 'User')"))
        connection.execute(
            text(
                "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility)"
                " VALUES (1, 'n1', 'octo/open', 1, 'open', 'public'),"
                " (2, 'n2', 'octo/mine', 1, 'mine', 'private'),"
                " (3, 'n3', 'octo/corp', 1, 'corp', 'internal')"
            )
        )
    source_id = create_run(engine, {"q": "language:rust"}, api_version="2022-11-28")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                " VALUES (:run, 1, 'octo/open', 1), (:run, 2, 'octo/mine', 100),"
                " (:run, 3, 'octo/corp', 50)"
            ),
            {"run": source_id},
        )

    candidates = orchestrator_module._candidates(engine, source_id, None)

    assert [row["full_name"] for row in candidates] == ["octo/open"]


def test_first_signal_at_uses_the_earliest_parsed_instant_for_mixed_offsets():
    from detect.attribution import Hit
    from detect.orchestrator import _RepoScan

    scan = _RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[
            Hit("Claude Code", "commit_trailer", {"commit": "a1"}),
            Hit("Claude Code", "commit_trailer", {"commit": "a2"}),
        ],
        results={},
        pr_result=None,
        history_stats={
            "committed_at": {
                "a1": "2025-01-01T00:30:00+03:00",
                "a2": "2024-12-31T23:00:00Z",
            }
        },
    )
    assert orchestrator_module._first_signal_at(scan) == "2025-01-01T00:30:00+03:00"


def test_first_signal_at_ignores_bot_channel_hits():
    from detect.attribution import Hit
    from detect.orchestrator import _RepoScan

    scan = _RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[
            Hit("dependabot", "bot", {"commit": "a1", "pr": 7}),
            Hit("Claude Code", "commit_trailer", {"commit": "a2"}),
        ],
        results={},
        pr_result=ChannelResult(stats={"created_at": {7: "2025-01-01T00:00:00Z"}}),
        history_stats={
            "committed_at": {
                "a1": "2025-01-01T00:00:00Z",
                "a2": "2026-01-02T00:00:00Z",
            }
        },
    )
    assert orchestrator_module._first_signal_at(scan) == "2026-01-02T00:00:00Z"


def test_repo_document_records_commit_window_coverage():
    from detect.attribution import Hit
    from detect.channels import ChannelResult

    scan = orchestrator_module._RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[
            Hit("Claude Code", "file", {"path": ".claude/x.json", "source": "tree"}),
            Hit(
                "Codex",
                "file",
                {"path": "CLAUDE.md", "source": "gitignore"},
            ),
            Hit("Claude Code", "commit_trailer", {"commit": "a1"}),
        ],
        results={
            "file": ChannelResult(status="ok"),
            "commit_trailer": ChannelResult(status="ok"),
        },
        pr_result=None,
        history_stats={
            "total_commits": 250,
            "window_commits": 100,
            "commits": 4,
            "ai_oids": ("a1",),
            "human_oids": ("h1", "h2", "h3"),
            "committed_at": {
                "h1": "2025-01-01T00:00:00Z",
                "a1": "2025-01-03T00:00:00Z",
                "h2": "2025-01-04T00:00:00Z",
                "h3": "2025-01-05T00:00:00Z",
            },
        },
    )

    document = orchestrator_module._repo_document(scan)

    assert document["oldest_scanned_commit_at"] == "2025-01-01T00:00:00Z"
    assert document["total_commits"] == 250
    assert document["history_window_commits"] == 100
    assert document["history_eligible_commits"] == 4
    assert document["history_coverage"] == 0.4
    assert document["history_complete"] is False
    assert scan.commit_count == 250


def test_commit_ratio_uses_only_selected_attribution_channels():
    scan = orchestrator_module._RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[],
        results={"author": ChannelResult(status="ok")},
        pr_result=None,
        history_stats={
            "commit_oids": ("author", "trailer", "human"),
            "author_oids": ("author",),
            "trailer_oids": ("trailer",),
            "window_commits": 3,
            "commits": 3,
            "total_commits": 3,
        },
    )

    document = orchestrator_module._repo_document(scan)

    assert document["commit_ratio"] == 0.3333
    assert document["history_complete"] is True


def test_partial_history_never_becomes_a_zero_or_partial_ratio():
    scan = orchestrator_module._RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[],
        results={"author": ChannelResult(status="partial")},
        pr_result=None,
        history_stats={
            "commit_oids": ("a", "h"),
            "author_oids": ("a",),
            "window_commits": 2,
            "commits": 2,
            "total_commits": 2,
        },
    )

    document = orchestrator_module._repo_document(scan)

    assert document["commit_ratio"] is None
    assert document["history_coverage"] is None
    assert document["history_complete"] is None


def test_stale_total_never_reports_impossible_history_coverage():
    scan = orchestrator_module._RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[],
        results={"author": ChannelResult(status="ok")},
        pr_result=None,
        history_stats={
            "commit_oids": ("a", "h", "new"),
            "author_oids": ("a",),
            "window_commits": 3,
            "commits": 3,
            "total_commits": 2,
        },
    )

    document = orchestrator_module._repo_document(scan)

    assert document["history_coverage"] is None
    assert document["history_complete"] is None
    assert any("coverage unknown" in note for note in document["notes"])


def test_fold_summary_uses_the_earliest_parsed_instant_for_mixed_offsets():
    from detect.orchestrator import _fold_summary, _SummaryContribution

    def contribution(first_signal_at: str | None) -> _SummaryContribution:
        return _SummaryContribution(
            unavailable=False,
            has_signal=True,
            agent_counts={},
            channel_counts={},
            partials={},
            ai_count=0,
            human_count=0,
            first_signal_at=first_signal_at,
        )

    contributions = [
        contribution("2026-01-01T00:30:00+03:00"),
        contribution("2025-12-31T23:00:00Z"),
    ]
    summary = _fold_summary(contributions, make_options(1), PACK, len(contributions))
    assert summary["first_signal_at"] == "2026-01-01T00:30:00+03:00"


def test_run_detection_checkpoints_run_items_per_repo(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    deps = make_deps(engine, make_handler(seen, []))
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    options = make_options(source_id, agents=["Claude Code", "Codex"])
    run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))

    with engine.connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT repo_id, full_name, repo_created_at, commit_count, language,"
                    " country_iso, detection FROM run_items"
                    " WHERE run_id = :run ORDER BY repo_id"
                ),
                {"run": run_id},
            )
            .mappings()
            .all()
        )
    assert [row["repo_id"] for row in rows] == [1, 2]
    assert rows[0]["full_name"] == "octo/one"
    assert rows[0]["commit_count"] == 1
    assert rows[0]["language"] == "Python"
    assert rows[0]["country_iso"] == "DE"
    assert rows[0]["repo_created_at"] is not None
    assert rows[0]["detection"]["agents"] == ["Claude Code", "Codex"]


def test_run_detection_records_compact_repo_filter_facets(clean_db):
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
    run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))

    with engine.connect() as connection:
        facets = set(
            connection.execute(
                text(
                    "SELECT repo_id, agent, channel FROM detection_repo_filters WHERE run_id = :run"
                ),
                {"run": run_id},
            ).all()
        )
        expected = set(
            connection.execute(
                text(
                    "SELECT DISTINCT repo_id, agent, channel FROM detection_evidence"
                    " WHERE run_id = :run"
                ),
                {"run": run_id},
            ).all()
        )
    assert facets == expected
    assert ("Claude Code", "file") in {(agent, channel) for _, agent, channel in facets}


def test_reset_run_artifacts_clears_evidence_and_facets(clean_db):
    from serve.executor import reset_run_artifacts

    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    deps = make_deps(engine, make_handler(seen, []))
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    options = make_options(source_id, agents=["Claude Code"])
    run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO analysis_snapshots"
                " (run_id, schema_version, build_seconds, payload)"
                " VALUES (:run, 'test', 0, '{}'::jsonb)"
            ),
            {"run": run_id},
        )
    with engine.connect() as connection:
        assert connection.execute(
            text("SELECT count(*) FROM detection_evidence WHERE run_id = :run"), {"run": run_id}
        ).scalar_one()
        assert connection.execute(
            text("SELECT count(*) FROM detection_repo_filters WHERE run_id = :run"),
            {"run": run_id},
        ).scalar_one()
        assert connection.execute(
            text("SELECT count(*) FROM analysis_snapshots WHERE run_id = :run"),
            {"run": run_id},
        ).scalar_one()
    reset_run_artifacts(engine, run_id)
    with engine.connect() as connection:
        assert (
            connection.execute(
                text("SELECT count(*) FROM detection_evidence WHERE run_id = :run"),
                {"run": run_id},
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM analysis_snapshots WHERE run_id = :run"),
                {"run": run_id},
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(
                text("SELECT count(*) FROM detection_repo_filters WHERE run_id = :run"),
                {"run": run_id},
            ).scalar_one()
            == 0
        )


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
    assert not EMAIL.search(json.dumps(list(payload.detections_source()), default=str))
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
    assert list(payload.detections_source()) == []


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


def test_run_detection_cancel_reaches_scan_workers(clean_db, monkeypatch):
    engine = clean_db()
    source_id = seed_source_run(engine)
    deps = make_deps(engine, make_handler([], []))
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    options = make_options(source_id, channels=["file"])
    seen_cancel = threading.Event()

    def slow_files(deps_, full_name, pack, **kwargs):
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            try:
                cancellation.check()
            except RunCancelled:
                seen_cancel.set()
                raise
            time.sleep(0.01)
        raise AssertionError("scan worker never observed the cancellation binding")

    monkeypatch.setattr(orchestrator_module, "detect_files", slow_files)
    cancel = threading.Event()
    token = cancellation.bind(cancel.is_set)
    timer = threading.Timer(0.2, cancel.set)
    timer.start()
    try:
        with pytest.raises(RunCancelled):
            run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))
    finally:
        timer.cancel()
        cancellation.reset(token)
    assert seen_cancel.is_set()


def test_run_detection_cancel_returns_promptly_with_wedged_scans(clean_db, monkeypatch):
    engine = clean_db()
    source_id = seed_source_run(engine)
    deps = make_deps(engine, make_handler([], []))
    run_id = create_run(
        engine,
        {"kind": "detect", "source_run_id": source_id},
        api_version="2022-11-28",
        kind="detect",
        source_run_id=source_id,
    )
    options = make_options(source_id, channels=["file"])
    release = threading.Event()
    started = threading.Event()

    def wedged_files(*args, **kwargs):
        started.set()
        release.wait()
        return ChannelResult(status="partial", note="released")

    monkeypatch.setattr(orchestrator_module, "detect_files", wedged_files)
    cancel = threading.Event()
    outcome: list[object] = []

    def drive() -> None:
        token = cancellation.bind(cancel.is_set)
        try:
            run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))
            outcome.append(None)
        except BaseException as exc:
            outcome.append(exc)
        finally:
            cancellation.reset(token)

    thread = threading.Thread(target=drive)
    thread.start()
    try:
        assert started.wait(timeout=5)
        time.sleep(0.1)
        cancel.set()
        thread.join(timeout=3)
        assert not thread.is_alive()
        assert outcome and isinstance(outcome[0], RunCancelled)
    finally:
        release.set()
        thread.join(timeout=5)


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
        analysis_snapshots = connection.execute(
            text("SELECT count(*) FROM analysis_snapshots WHERE run_id = :run"),
            {"run": run_id},
        ).scalar_one()
    assert row["status"] in ("done", "partial")
    assert row["result_summary"]["agents"] == {"Claude Code": 1, "Codex": 2}
    assert detections["agents"] == ["Claude Code", "Codex"]
    assert analysis_snapshots == 1
    evidence_csv = list(Path(tmp_path).glob(f"*/{run_id}/detections.csv"))
    assert len(evidence_csv) == 1
    with evidence_csv[0].open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = list(reader)
    from serve.executor import EVIDENCE_CSV_HEADER

    assert header == EVIDENCE_CSV_HEADER
    assert "run_id" not in header
    assert "pack_version" not in header
    path_cell = rows[0][EVIDENCE_CSV_HEADER.index("path")]
    assert path_cell == "CLAUDE.md"
    assert rows[0][EVIDENCE_CSV_HEADER.index("repo_id")] == "1"
    assert rows[0][EVIDENCE_CSV_HEADER.index("detected_at")]


def test_summary_contributions_reproduce_batch_summary():
    from detect.attribution import Hit
    from detect.orchestrator import (
        _fold_summary,
        _RepoScan,
        _scan_contribution,
        _summary,
    )

    pack = Pack(
        version="acc-pack",
        agents={},
        authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"),),
        files=(Pattern(r"CLAUDE\.md", "Claude Code"),),
        branches=(),
        labels=(),
        bots=(),
        generic_weights={},
        exclusions=frozenset(),
    )
    spec = DetectOptions(
        source_run_id=1,
        pack_version="acc-pack",
        agents=None,
        channels=frozenset({"file", "bot"}),
        source="git",
    )
    scans = [
        _RepoScan(
            repo_id=1,
            full_name="octo/one",
            stargazers=10,
            hits=[
                Hit("Claude Code", "file", {"path": "CLAUDE.md"}),
                Hit("Generic", "file", {"path": "AGENTS.md"}),
                Hit("dependabot", "bot", {"login": "dependabot"}),
            ],
            results={"file": ChannelResult(status="ok")},
            pr_result=None,
            history_stats={"ai_oids": ("a1", "a2"), "human_oids": ("h1", "h2", "a2")},
            document={
                "agents": ["Claude Code"],
                "generic_markers": ["AGENTS.md"],
                "channels": {"file": "ok"},
                "unavailable": False,
                "first_signal_at": "2026-01-02T00:00:00Z",
                "notes": [],
            },
        ),
        _RepoScan(
            repo_id=2,
            full_name="octo/two",
            stargazers=5,
            hits=[Hit("Claude Code", "commit_trailer", {"commit": "b1"})],
            results={"file": ChannelResult(status="partial", note="pull refs fetch failed")},
            pr_result=None,
            history_stats={},
            document={
                "agents": ["Claude Code"],
                "channels": {"file": "partial"},
                "unavailable": True,
                "failure_class": "transient",
                "first_signal_at": None,
                "notes": ["boom"],
            },
        ),
    ]

    contributions = [_scan_contribution(scan) for scan in scans]
    assert _fold_summary(contributions, spec, pack, len(scans)) == _summary(scans, spec, pack)
