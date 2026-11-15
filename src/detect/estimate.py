from __future__ import annotations

from collections.abc import Sequence

from detect.packs import DETECTION_CHANNELS

CHANNELS = DETECTION_CHANNELS

_REST_CALLS_PER_REPO = {
    "file": 3.0,  # tree + .gitignore + bounded declared content predicates
    "hidden_ref": 6.0,  # five declared namespaces + bounded tip identity enrichment
}
_GRAPHQL_GROUPS: tuple[tuple[tuple[str, ...], str, float], ...] = (
    (("author", "commit_trailer", "bot"), "author", 1.0),
    (("branch", "label", "pr_metadata"), "pr_metadata", 3.0),
    (("issue",), "issue", 2.0),
)
# Schema-v2 packs read the content of every file a content rule's path could
# match. Measured on run 165 (pack 2026-11-15): 8.5 file REST calls per repo
# versus 3.4 on schema-v1 run 155 -- the extra ~5.5 are broad-pattern reads
# (every workflow / compose file) that fast mode skips.
_BROAD_CONTENT_REST_CALLS = 5.5
# Measured wall time per repo per worker when quota is not the bottleneck
# (run 155: 7,245 repos in 151 min at 12 workers).
MEASURED_SECONDS_PER_REPO = 15.0
_POINTS_PER_HOUR = 5000.0
_FOUR_TOKEN_RESERVE = 400.0


def file_rest_calls(*, structured_content: bool, scan_mode: str = "full") -> float:
    """REST calls the file channel makes per repo for a pack schema and scan mode."""
    calls = _REST_CALLS_PER_REPO["file"]
    if structured_content and scan_mode != "fast":
        calls += _BROAD_CONTENT_REST_CALLS
    return calls


def estimate(
    candidates: int,
    channels: Sequence[str],
    *,
    tokens: int,
    concurrency: int = 10,
    deadline_seconds: float | None = None,
    structured_content: bool = False,
    scan_mode: str = "full",
    seconds_per_repo: float | None = None,
) -> dict:
    """Calls/time estimate.

    The quota bound (points per hour per token) does not change with
    `concurrency`. When `seconds_per_repo` is given, a latency bound
    (repos x seconds / concurrency) is also applied and the slower one wins.
    `structured_content` marks a schema-v2 pack, whose full scan reads every
    broad-pattern content candidate; `scan_mode="fast"` skips those reads.
    """
    if tokens <= 0:
        raise ValueError("tokens must be >= 1")
    unknown = [channel for channel in channels if channel not in CHANNELS]
    if unknown:
        raise ValueError(f"unknown channels: {unknown}")
    selected = set(channels)
    per_channel = {channel: 0.0 for channel in channels}
    rest_calls = 0.0
    for channel, calls in _REST_CALLS_PER_REPO.items():
        if channel in selected:
            if channel == "file":
                calls = file_rest_calls(structured_content=structured_content, scan_mode=scan_mode)
            rest_calls += candidates * calls
            per_channel[channel] = calls
    graphql_calls = 0.0
    graphql_points = 0.0
    for members, _owner, point_cost in _GRAPHQL_GROUPS:
        picked = [channel for channel in members if channel in selected]
        if picked:
            graphql_calls += candidates
            graphql_points += candidates * point_cost
            per_channel[picked[0]] = per_channel.get(picked[0], 0.0) + 1.0
    hourly_per_token = _POINTS_PER_HOUR - (_FOUR_TOKEN_RESERVE if tokens == 4 else 0.0)
    quota_hours = max(rest_calls, graphql_points) / (hourly_per_token * tokens)
    latency_hours = (
        candidates * seconds_per_repo / max(1, concurrency) / 3600.0
        if seconds_per_repo is not None
        else 0.0
    )
    hours = round(max(quota_hours, latency_hours), 2)
    return {
        "repos": candidates,
        "tokens": tokens,
        "rest_calls": int(rest_calls),
        "graphql_calls": int(graphql_calls),
        "graphql_points": int(graphql_points),
        "hours": hours,
        "per_channel": per_channel,
        "concurrency": concurrency,
        "scan_mode": scan_mode,
        "seconds_per_repo": seconds_per_repo,
        "quota_hours": round(quota_hours, 2),
        "latency_hours": round(latency_hours, 2),
        "bound": "quota" if quota_hours >= latency_hours else "latency",
        "deadline_exceeded": deadline_seconds is not None and hours * 3600.0 > deadline_seconds,
    }
