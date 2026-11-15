from __future__ import annotations

import httpx
import pytest

from detect.token_pool import (
    DetectionTokenPool,
    TokenPoolConfigurationError,
    TokenPoolExhausted,
    _Budget,
    cost_profile,
)
from discover.pipeline import Deps


def _deps(index: int, *, login: str | None = None) -> Deps:
    account = login or f"account-{index}"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/user":
            return httpx.Response(
                200,
                json={"login": account},
                headers={
                    "x-ratelimit-resource": "core",
                    "x-ratelimit-limit": "5000",
                    "x-ratelimit-remaining": "4999",
                    "x-ratelimit-reset": "4102444800",
                },
            )
        if request.url.path == "/graphql":
            return httpx.Response(
                200,
                json={
                    "data": {
                        "viewer": {"login": account},
                        "rateLimit": {
                            "cost": 1,
                            "limit": 5000,
                            "used": 1,
                            "remaining": 4999,
                            "resetAt": "2100-01-01T00:00:00Z",
                        },
                    }
                },
                headers={
                    "x-ratelimit-resource": "graphql",
                    "x-ratelimit-limit": "5000",
                    "x-ratelimit-remaining": "4999",
                    "x-ratelimit-reset": "4102444800",
                },
            )
        raise AssertionError(request.url)

    return Deps(
        client=httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
        engine=None,
        token_fp=f"fingerprint-{index}",
    )


def _pool(*, duplicate_identity: bool = False, channels=()) -> DetectionTokenPool:
    dependencies = [
        _deps(index, login="same-account" if duplicate_identity else None) for index in range(4)
    ]
    return DetectionTokenPool(dependencies, channels)


def test_cost_profile_prices_shared_channel_groups_once():
    profile = cost_profile(
        ("file", "author", "commit_trailer", "bot", "branch", "label", "pr_metadata", "issue")
    )
    assert profile.core == 3.0
    assert profile.graphql == 6.0


def test_cost_profile_uses_the_measured_file_cost_for_the_scan_mode():
    channels = ("file", "author", "pr_metadata", "issue")
    assert cost_profile(channels, file_core_calls=8.5).core == 8.5
    assert cost_profile(("author",), file_core_calls=8.5).core == 0.0


def test_graphql_dispatch_interval_preserves_the_four_hundred_point_reserve():
    interval = DetectionTokenPool._resource_interval(
        6.0,
        _Budget(remaining=5000, reset_at=3600.0),
        wall_now=0.0,
    )
    assert interval == pytest.approx(6.0 / (4600.0 / 3600.0))


def test_pool_requires_exactly_four_distinct_tokens():
    dependencies = [_deps(index) for index in range(2)]
    with pytest.raises(TokenPoolConfigurationError, match="exactly 4"):
        DetectionTokenPool(dependencies, ())
    for deps in dependencies:
        deps.client.close()


def test_preflight_accepts_four_distinct_account_identities():
    pool = _pool(channels=("file", "author"))
    try:
        pool.preflight()
        stats = pool.stats()
        assert stats["tokens"] == 4
        assert len({account["fingerprint"] for account in stats["accounts"]}) == 4
        assert {account["graphql_remaining"] for account in stats["accounts"]} == {4999}
    finally:
        pool.close()


def test_preflight_rejects_tokens_from_the_same_account():
    pool = _pool(duplicate_identity=True)
    try:
        with pytest.raises(TokenPoolConfigurationError, match="four distinct accounts"):
            pool.preflight()
    finally:
        pool.close()


def test_initial_leases_are_balanced_across_all_four_tokens():
    pool = _pool()
    leases = [pool.lease() for _ in range(4)]
    try:
        assert {lease.deps.token_fp for lease in leases} == {
            "fingerprint-0",
            "fingerprint-1",
            "fingerprint-2",
            "fingerprint-3",
        }
    finally:
        for lease in leases:
            lease.release()
        pool.close()


def test_secondary_response_reduces_only_the_offending_token_window():
    pool = _pool()
    response = httpx.Response(
        403,
        headers={"retry-after": "60"},
        request=httpx.Request("POST", "https://api.github.com/graphql"),
    )
    try:
        pool.observe("fingerprint-2", response, "detect:prs")
        accounts = pool.stats()["accounts"]
        assert accounts[2]["secondary_hits"] == 1
        assert accounts[2]["active_limit"] == 1
        assert all(account["secondary_hits"] == 0 for account in accounts[:2] + accounts[3:])
    finally:
        pool.close()


def test_clean_responses_ramp_a_token_from_two_to_three_workers():
    pool = _pool()
    response = httpx.Response(
        200,
        headers={"x-ratelimit-resource": "graphql", "x-ratelimit-remaining": "4900"},
        request=httpx.Request("POST", "https://api.github.com/graphql"),
    )
    try:
        for _ in range(40):
            pool.observe("fingerprint-0", response, "detect:history")
        assert pool.stats()["accounts"][0]["active_limit"] == 3
    finally:
        pool.close()


def test_graphql_error_responses_do_not_ramp_concurrency():
    pool = _pool()
    response = httpx.Response(
        200,
        json={"data": None, "errors": [{"message": "RATE_LIMITED"}]},
        headers={"x-ratelimit-resource": "graphql", "x-ratelimit-remaining": "4900"},
        request=httpx.Request("POST", "https://api.github.com/graphql"),
    )
    try:
        for _ in range(80):
            pool.observe("fingerprint-0", response, "detect:history")
        assert pool.stats()["accounts"][0]["active_limit"] == 2
    finally:
        pool.close()


def test_pool_raises_a_fatal_error_when_every_identity_is_disabled():
    pool = _pool()
    response = httpx.Response(
        401,
        request=httpx.Request("GET", "https://api.github.com/user"),
    )
    try:
        for index in range(4):
            pool.observe(f"fingerprint-{index}", response, "detect:file")
        with pytest.raises(TokenPoolExhausted, match="all GitHub identities"):
            pool.raise_if_exhausted()
        with pytest.raises(TokenPoolExhausted, match="all GitHub identities"):
            pool.lease()
    finally:
        pool.close()
