from __future__ import annotations

from collections.abc import Sequence

CHANNELS = ("file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata", "issue")

_REST_CALLS_PER_REPO = {"file": 3.0}  # tree + .gitignore + bounded content probes
_GRAPHQL_GROUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("author", "commit_trailer", "bot"), "author"),
    (("branch", "label", "pr_metadata"), "pr_metadata"),
    (("issue",), "issue"),
)
_POINTS_PER_HOUR = 5000.0


def estimate(
    candidates: int,
    channels: Sequence[str],
    *,
    tokens: int,
    concurrency: int = 10,
    deadline_seconds: float | None = None,
) -> dict:
    """Calls/time estimate. `concurrency` is display-only: the steady-state rate cap
    (points per hour per token) does not change with it."""
    if tokens <= 0:
        raise ValueError("tokens must be >= 1")
    unknown = [channel for channel in channels if channel not in CHANNELS]
    if unknown:
        raise ValueError(f"unknown channels: {unknown}")
    selected = set(channels)
    per_channel = {channel: 0.0 for channel in channels}
    rest_calls = 0.0
    if "file" in selected:
        rest_calls = candidates * _REST_CALLS_PER_REPO["file"]
        per_channel["file"] = _REST_CALLS_PER_REPO["file"]
    graphql_calls = 0.0
    for members, _owner in _GRAPHQL_GROUPS:
        picked = [channel for channel in members if channel in selected]
        if picked:
            graphql_calls += candidates
            per_channel[picked[0]] = per_channel.get(picked[0], 0.0) + 1.0
    hours = round((rest_calls + graphql_calls) / (_POINTS_PER_HOUR * tokens), 2)
    return {
        "repos": candidates,
        "rest_calls": int(rest_calls),
        "graphql_calls": int(graphql_calls),
        "hours": hours,
        "per_channel": per_channel,
        "concurrency": concurrency,
        "deadline_exceeded": deadline_seconds is not None and hours * 3600.0 > deadline_seconds,
    }
