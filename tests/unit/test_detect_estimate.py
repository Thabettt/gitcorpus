from __future__ import annotations

import pytest

from detect.estimate import estimate, file_rest_calls


def test_estimate_all_channels():
    result = estimate(
        1000,
        ["file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata", "issue"],
        tokens=2,
    )
    assert result["repos"] == 1000
    assert result["rest_calls"] == 3000  # file: tree + gitignore + content probes
    assert result["graphql_calls"] == 3000  # history + PRs + issues
    assert result["graphql_points"] == 6000  # history 1 + PRs 3 + issues 2
    assert result["hours"] == 0.6  # REST and GraphQL have independent hourly budgets
    assert result["per_channel"]["commit_trailer"] == 0.0
    assert result["per_channel"]["issue"] == 1.0
    assert result["deadline_exceeded"] is False


def test_estimate_file_only():
    result = estimate(200, ["file"], tokens=1)
    assert result["rest_calls"] == 600
    assert result["graphql_calls"] == 0


def test_estimate_hidden_refs_accounts_for_targeted_namespaces_and_tip_enrichment():
    result = estimate(200, ["hidden_ref"], tokens=1)
    assert result["rest_calls"] == 1200
    assert result["per_channel"]["hidden_ref"] == 6.0


def test_estimate_pr_group_attributed_to_branch():
    result = estimate(200, ["branch"], tokens=1)
    assert result["rest_calls"] == 0
    assert result["graphql_calls"] == 200
    assert result["per_channel"]["branch"] == 1.0


def test_estimate_rejects_zero_tokens():
    with pytest.raises(ValueError, match="tokens"):
        estimate(10, ["file"], tokens=0)


def test_estimate_flags_deadline_overrun():
    result = estimate(100000, ["file"], tokens=1, deadline_seconds=3600)
    assert result["deadline_exceeded"] is True


def test_four_token_estimate_keeps_a_reserve_and_uses_measured_graphql_costs():
    result = estimate(
        17757,
        ["file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata", "issue"],
        tokens=4,
    )
    assert result["graphql_points"] == 106542
    assert result["rest_calls"] == 53271
    assert result["hours"] == 5.79


ALL = ["file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata", "issue"]


def test_schema_v2_full_scan_prices_broad_content_reads_and_fast_mode_drops_them():
    full = estimate(17757, ALL, tokens=4, structured_content=True)
    fast = estimate(17757, ALL, tokens=4, structured_content=True, scan_mode="fast")
    assert full["per_channel"]["file"] == 8.5
    assert fast["per_channel"]["file"] == 3.0
    assert full["hours"] == 8.2
    assert full["bound"] == "quota"
    assert fast["rest_calls"] == 53271


def test_latency_floor_applies_when_quota_is_not_the_bottleneck():
    # Run 155 measured ~15 s per repo per worker at 12 workers: ~6.2 h for 17,757.
    result = estimate(
        17757,
        ALL,
        tokens=4,
        concurrency=12,
        structured_content=True,
        scan_mode="fast",
        seconds_per_repo=15.0,
    )
    assert result["bound"] == "latency"
    assert result["hours"] == 6.17
    assert result["quota_hours"] == 5.79


def test_file_rest_calls_by_schema_and_mode():
    assert file_rest_calls(structured_content=False) == 3.0
    assert file_rest_calls(structured_content=True) == 8.5
    assert file_rest_calls(structured_content=True, scan_mode="fast") == 3.0
