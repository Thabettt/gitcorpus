from __future__ import annotations

import pytest

from detect.estimate import estimate


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
