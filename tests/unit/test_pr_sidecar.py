from __future__ import annotations

import json
import threading

import httpx

from detect.attribution import CODEX_PR_BODY_MARKER, Hit
from detect.channels import ChannelResult, FailureKind, detect_pr_metadata
from detect.orchestrator import _repo_document, _RepoScan
from detect.packs import Pack, Pattern
from detect.pr_sidecar import PR_API_KEY, PrSidecar, merge_pr_metadata
from discover.pipeline import Deps

PACK = Pack(
    version="v1",
    agents={"Claude Code": "https://claude.com", "Codex": "https://openai.com"},
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"),),
    files=(Pattern(r"CLAUDE\.md", "Claude Code"),),
    branches=(Pattern("claude/", "Claude Code"),),
    labels=(Pattern("^codex$", "Codex"),),
    bots=(),
    generic_weights={},
    exclusions=frozenset(),
)

ALL = frozenset({"file", "branch", "label", "pr_metadata"})


def make_deps(handler) -> Deps:
    return Deps(
        client=httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
        engine=None,
    )


def pr_payload(*nodes: dict) -> dict:
    return {"data": {"repository": {"pullRequests": {"nodes": list(nodes)}}}}


def test_detect_pr_metadata_matches_body_label_and_head_without_commits():
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json=pr_payload(
                {
                    "number": 7,
                    "createdAt": "2026-03-01T00:00:00Z",
                    "headRefName": "claude/fix-it",
                    "bodyText": f"Did a thing. {CODEX_PR_BODY_MARKER}",
                    "author": {"login": "jane"},
                    "labels": {"nodes": [{"name": "codex"}]},
                }
            ),
        )

    result = detect_pr_metadata(make_deps(handler), "octo/repo", PACK, limit=100)

    assert result.status == "ok"
    found = {(hit.channel, hit.agent) for hit in result.hits}
    assert ("branch", "Claude Code") in found
    assert ("label", "Codex") in found
    assert ("pr_metadata", "Codex") in found
    assert result.stats["created_at"] == {7: "2026-03-01T00:00:00Z"}
    query = bodies[0]["query"]
    assert "commits" not in query and "comments" not in query and "reviews" not in query


def test_detect_pr_metadata_reports_unavailable_repo():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"repository": None}})

    result = detect_pr_metadata(make_deps(handler), "octo/gone", PACK)
    assert result.status == "unavailable"


def make_scan(results: dict[str, ChannelResult]) -> _RepoScan:
    hits = [hit for result in results.values() for hit in result.hits]
    scan = _RepoScan(
        repo_id=1,
        full_name="octo/repo",
        stargazers=1,
        hits=hits,
        results=results,
        pr_result=results.get("pr_metadata"),
        history_stats={},
    )
    scan.document = _repo_document(scan)
    return scan


def test_merge_adds_api_hits_label_channel_and_dates_pr_evidence():
    local_pr = ChannelResult(
        hits=(Hit("Claude Code", "pr_metadata", {"pr": 7, "commit": "a1", "propagated": True}),),
        stats={"propagated_oids": ("a1",), "created_at": {}},
    )
    scan = make_scan(
        {
            "file": ChannelResult(),
            "branch": ChannelResult(),
            "pr_metadata": local_pr,
        }
    )
    assert scan.document["first_signal_at"] is None
    api = ChannelResult(
        hits=(
            Hit("Codex", "label", {"pr": 9, "label": "codex", "match": "codex"}),
            Hit("Codex", "pr_metadata", {"pr": 9, "snippet": CODEX_PR_BODY_MARKER}),
            Hit("Claude Code", "branch", {"pr": 7, "head": "claude/x", "match": "claude/"}),
        ),
        stats={"created_at": {7: "2026-02-01T00:00:00Z", 9: "2026-03-01T00:00:00Z"}},
    )

    merge_pr_metadata(scan, api, ALL)

    assert scan.results["label"].status == "ok"
    assert [hit.agent for hit in scan.results["label"].hits] == ["Codex"]
    assert {hit.agent for hit in scan.results["pr_metadata"].hits} == {"Claude Code", "Codex"}
    assert scan.results["pr_metadata"].stats["propagated_oids"] == ("a1",)
    assert len(scan.results["branch"].hits) == 1
    assert scan.document["agents"] == ["Claude Code", "Codex"]
    assert scan.document["first_signal_at"] == "2026-02-01T00:00:00Z"
    assert scan.document["channels"]["label"] == "ok"
    assert scan.document[PR_API_KEY] == "ok"


def test_merge_drops_hits_for_unselected_channels():
    scan = make_scan({"file": ChannelResult(), "pr_metadata": ChannelResult()})
    api = ChannelResult(
        hits=(Hit("Codex", "label", {"pr": 9, "label": "codex", "match": "codex"}),),
    )
    merge_pr_metadata(scan, api, frozenset({"file", "pr_metadata"}))
    assert "label" not in scan.results
    assert scan.hits == []


def test_failed_api_fetch_never_downgrades_git_channels():
    scan = make_scan({"file": ChannelResult(), "pr_metadata": ChannelResult()})
    api = ChannelResult(status="unavailable", note="repo not found")

    merge_pr_metadata(scan, api, ALL)

    assert scan.results["file"].status == "ok"
    assert scan.results["pr_metadata"].status == "ok"
    assert scan.results["label"].status == "partial"
    assert scan.document["unavailable"] is False
    assert scan.document[PR_API_KEY] == "partial"


def test_merge_leaves_failed_scans_alone():
    scan = make_scan({})
    scan.document = {"unavailable": True, "notes": ["clone failed"], "agents": []}
    merge_pr_metadata(scan, ChannelResult(hits=(Hit("Codex", "label", {}),)), ALL)
    assert scan.results == {}
    assert PR_API_KEY not in scan.document


def test_sidecar_prefetches_and_serves_on_demand():
    seen: list[str] = []
    lock = threading.Lock()

    def fetch(full_name: str) -> ChannelResult:
        with lock:
            seen.append(full_name)
        return ChannelResult(note=full_name)

    sidecar = PrSidecar(fetch, workers=2, lookahead=2)
    try:
        sidecar.prefetch(["a/1", "a/2", "a/3"])
        assert sidecar.result("a/2").note == "a/2"
        assert sidecar.result("z/9").note == "z/9"
        sidecar.discard("a/1")
        assert sidecar.result("a/3").note == "a/3"
    finally:
        sidecar.close()
    assert "z/9" in seen
    assert sidecar.stats()["statuses"] == {"ok": 3}


def test_sidecar_turns_fetch_exceptions_into_partial_results():
    def fetch(full_name: str) -> ChannelResult:
        raise RuntimeError("boom")

    sidecar = PrSidecar(fetch, workers=1)
    try:
        result = sidecar.result("a/1")
    finally:
        sidecar.close()
    assert result.status == "partial"
    assert "boom" in (result.note or "")


def test_sidecar_breaker_trips_after_consecutive_retryable_failures():
    calls: list[str] = []

    def fetch(full_name: str) -> ChannelResult:
        calls.append(full_name)
        return ChannelResult(status="partial", note="HTTP 502", failure_kind=FailureKind.RETRYABLE)

    sidecar = PrSidecar(fetch, workers=1, failure_limit=3)
    try:
        for index in range(3):
            assert sidecar.result(f"a/{index}").status == "partial"
        assert sidecar.tripped_note is not None
        skipped = sidecar.result("a/9")
    finally:
        sidecar.close()
    assert skipped.status == "skipped"
    assert calls == ["a/0", "a/1", "a/2"]
    assert sidecar.stats()["tripped"] is True


def test_sidecar_permanent_failures_do_not_trip_the_breaker():
    def fetch(full_name: str) -> ChannelResult:
        return ChannelResult(
            status="unavailable", note="repo not found", failure_kind=FailureKind.PERMANENT
        )

    sidecar = PrSidecar(fetch, workers=1, failure_limit=2)
    try:
        for index in range(4):
            sidecar.result(f"a/{index}")
    finally:
        sidecar.close()
    assert sidecar.tripped_note is None
