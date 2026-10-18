from __future__ import annotations

import csv
import hashlib
import json

import pytest

from serve import executor
from serve.executor import RunPayload, RunPayloadItem


def test_run_payload_item_defaults_are_independent():
    first = RunPayloadItem(repo_id=1, full_name="octo/hello")
    second = RunPayloadItem(repo_id=2, full_name="octo/world")
    first.virtuals["has_dockerfile"] = True
    assert second.virtuals == {}
    assert first.stargazers is None
    assert first.pushed_at is None
    assert first.archived is None
    assert first.language is None
    assert first.license_spdx is None
    assert first.country_iso is None
    assert first.geo_confidence is None
    assert first.raw is None


def test_run_payload_defaults():
    payload = RunPayload(total_count=None, items=[])
    assert payload.incomplete is False
    assert payload.fetched is None
    assert payload.field_stats == {}


def test_run_payload_field_stats_defaults_are_independent():
    first = RunPayload(total_count=None, items=[])
    second = RunPayload(total_count=None, items=[])
    first.field_stats["requeues"] = 1
    assert second.field_stats == {}


def test_filter_hash_is_canonical_across_key_order():
    left = executor._filter_hash({"q": "stars:>10", "sort": "stars", "order": "desc"})
    right = executor._filter_hash({"order": "desc", "sort": "stars", "q": "stars:>10"})
    expected = hashlib.sha256(
        json.dumps(
            {"q": "stars:>10", "sort": "stars", "order": "desc"},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    assert left == right == expected


def test_default_runner_raises_runtime_error():
    with pytest.raises(RuntimeError, match="no runner configured"):
        executor._default_runner(1, {})


def test_error_message_is_class_prefixed_and_truncated():
    message = executor._error_message(ValueError("x" * 1000))
    assert message == ("ValueError: " + "x" * 1000)[:300]
    assert len(message) == 300
    assert message.startswith("ValueError: ")


def test_error_message_strips_upstream_body():
    from serve.executor import _error_message

    message = _error_message(
        ValueError("422: Validation Failed: {'message': 'upstream body secret'}")
    )
    assert "upstream body secret" not in message
    assert message.startswith("ValueError")


def test_bundle_item_prefers_raw_and_falls_back_to_snapshot():
    raw = {"id": 1, "full_name": "octo/hello", "extra": True}
    assert executor._bundle_item(RunPayloadItem(repo_id=1, full_name="octo/hello", raw=raw)) == raw
    snapshot = executor._bundle_item(
        RunPayloadItem(
            repo_id=2,
            full_name="octo/world",
            stargazers=5,
            pushed_at="2026-09-30T12:00:00+00:00",
            archived=True,
            language="Go",
            license_spdx="Apache-2.0",
            country_iso="US",
            geo_confidence="gazetteer-city",
            virtuals={"team_topic": True},
        )
    )
    assert snapshot == {
        "repo_id": 2,
        "full_name": "octo/world",
        "stargazers": 5,
        "pushed_at": "2026-09-30T12:00:00+00:00",
        "archived": True,
        "language": "Go",
        "license_spdx": "Apache-2.0",
        "country_iso": "US",
        "geo_confidence": "gazetteer-city",
        "virtuals": {"team_topic": True},
        "detection": None,
    }


def _evidence_row(**overrides):
    row = {
        "run_id": 99,
        "repo_id": 1,
        "full_name": "octo/one",
        "agent": "Claude Code",
        "channel": "file",
        "pack_version": "v1",
        "detected_at": None,
        "evidence": {"path": "CLAUDE.md"},
    }
    row.update(overrides)
    return row


def _cells(row):
    return dict(zip(executor.EVIDENCE_CSV_HEADER, executor.evidence_csv_row(row), strict=True))


def test_evidence_header_is_the_flat_schema():
    assert executor.EVIDENCE_CSV_HEADER == [
        "run_id",
        "repo_id",
        "full_name",
        "agent",
        "channel",
        "pack_version",
        "detected_at",
        "commit_sha",
        "path",
        "path_source",
        "file_size",
        "file_empty",
        "file_generic",
        "file_weight",
        "pr_number",
        "branch_head",
        "branch_match",
        "label",
        "issue_number",
        "issue_role",
        "login",
        "identity_field",
        "snippet",
        "propagated",
        "evidence_json",
    ]


def test_evidence_row_flattens_file_channel():
    cells = _cells(
        _evidence_row(
            evidence={
                "path": ".claude/settings.json",
                "size": 27,
                "empty": False,
                "generic": True,
                "weight": 0.5,
                "source": "tree",
            }
        )
    )
    assert cells["path"] == ".claude/settings.json"
    assert cells["path_source"] == "tree"
    assert cells["file_size"] == "27"
    assert cells["file_empty"] == "false"
    assert cells["file_generic"] == "true"
    assert cells["file_weight"] == "0.5"
    assert cells["commit_sha"] == ""
    assert cells["evidence_json"] == (
        '{"empty": false, "generic": true, "path": ".claude/settings.json",'
        ' "size": 27, "source": "tree", "weight": 0.5}'
    )


def test_evidence_row_flattens_identity_channels():
    author = _cells(
        _evidence_row(
            channel="author",
            evidence={"login": "Copilot", "field": "login", "commit": "abc123"},
        )
    )
    assert author["login"] == "Copilot"
    assert author["identity_field"] == "login"
    assert author["commit_sha"] == "abc123"
    bot = _cells(
        _evidence_row(channel="bot", evidence={"login": "renovate[bot]", "field": "email"})
    )
    assert bot["login"] == "renovate[bot]"
    assert bot["identity_field"] == "email"


def test_evidence_row_flattens_branch_and_label_channels():
    branch = _cells(
        _evidence_row(
            channel="branch", evidence={"pr": 206, "head": "codex/readme", "match": "codex/"}
        )
    )
    assert branch["pr_number"] == "206"
    assert branch["branch_head"] == "codex/readme"
    assert branch["branch_match"] == "codex/"
    label = _cells(
        _evidence_row(channel="label", evidence={"pr": 7, "label": "cursor", "match": "cursor"})
    )
    assert label["pr_number"] == "7"
    assert label["label"] == "cursor"
    assert label["branch_match"] == "cursor"


def test_evidence_row_flattens_trailer_and_propagation():
    trailer = _cells(
        _evidence_row(channel="commit_trailer", evidence={"commit": "a1b2", "snippet": "Claude"})
    )
    assert trailer["commit_sha"] == "a1b2"
    assert trailer["snippet"] == "Claude"
    propagated = _cells(
        _evidence_row(
            channel="pr_metadata",
            evidence={"pr": 3, "commit": "cafe", "propagated": True},
        )
    )
    assert propagated["pr_number"] == "3"
    assert propagated["commit_sha"] == "cafe"
    assert propagated["propagated"] == "true"


def test_evidence_row_flattens_pr_author_and_issue_channels():
    pr_author = _cells(
        _evidence_row(channel="pr_metadata", evidence={"pr": 11, "author": "devin-ai"})
    )
    assert pr_author["login"] == "devin-ai"
    assert pr_author["pr_number"] == "11"
    issue = _cells(
        _evidence_row(
            channel="issue", evidence={"role": "assignee", "login": "Claude", "number": 67}
        )
    )
    assert issue["issue_number"] == "67"
    assert issue["issue_role"] == "assignee"
    assert issue["login"] == "Claude"


def test_evidence_row_keeps_unknown_shapes_in_raw_json_only():
    cells = _cells(_evidence_row(channel="mystery", evidence={"custom": [1, 2]}))
    assert cells["commit_sha"] == ""
    assert cells["path"] == ""
    assert cells["evidence_json"] == '{"custom": [1, 2]}'


def test_evidence_row_formats_detected_at_as_utc_iso():
    from datetime import UTC, datetime

    moment = datetime(2026, 10, 18, 4, 15, 22, tzinfo=UTC)
    cells = _cells(_evidence_row(detected_at=moment))
    assert cells["detected_at"] == "2026-10-18T04:15:22Z"
    text_moment = _cells(_evidence_row(detected_at="2026-10-18T04:15:22+00:00"))
    assert text_moment["detected_at"] == "2026-10-18T04:15:22+00:00"


def test_csv_cell_flattens_newlines_to_literal_escapes():
    assert executor._csv_cell("a\r\nb\nc") == "a\\nb\\nc"
    assert executor._csv_cell("a\rb") == "a\\nb"
    assert executor._csv_cell("plain text") == "plain text"


def test_evidence_row_flattens_snippet_and_keeps_evidence_json_newline_free():
    evidence = {"commit": "a1", "snippet": "first\n\nsecond", "propagated": True}
    cells = _cells(_evidence_row(channel="commit_trailer", evidence=evidence))
    assert cells["snippet"] == "first\\n\\nsecond"
    assert cells["evidence_json"] == json.dumps(evidence, sort_keys=True)
    assert "\n" not in cells["evidence_json"]


def test_write_bundle_streams_detections_from_source(tmp_path):
    rows = [
        _evidence_row(evidence={"path": "CLAUDE.md"}),
        _evidence_row(evidence={"snippet": "first\n\nsecond"}),
    ]
    payload = RunPayload(total_count=1, items=[], detections_source=lambda: iter(rows))
    run = {"filter_hash": "hash-a", "id": 9, "filter_spec": {}, "api_version": "2022-11-28"}
    bundle_dir = executor._write_bundle(run, payload, str(tmp_path))
    assert bundle_dir.endswith("/hash-a/9/")
    detections_csv = tmp_path / "hash-a" / "9" / "detections.csv"
    assert detections_csv.exists()
    raw = detections_csv.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf"
    assert raw.count(b"\n") == len(rows) + 1
    with detections_csv.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        first = next(reader)
        second = next(reader)
    assert header == executor.EVIDENCE_CSV_HEADER
    assert first[executor.EVIDENCE_CSV_HEADER.index("full_name")] == "octo/one"
    assert first[executor.EVIDENCE_CSV_HEADER.index("path")] == "CLAUDE.md"
    assert first[executor.EVIDENCE_CSV_HEADER.index("channel")] == "file"
    assert second[executor.EVIDENCE_CSV_HEADER.index("snippet")] == "first\\n\\nsecond"


def test_write_bundle_omits_detections_without_source(tmp_path):
    payload = RunPayload(total_count=0, items=[])
    run = {"filter_hash": "hash-b", "id": 10, "filter_spec": {}, "api_version": "2022-11-28"}
    executor._write_bundle(run, payload, str(tmp_path))
    assert not (tmp_path / "hash-b" / "10" / "detections.csv").exists()
