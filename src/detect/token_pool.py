from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

from discover.pipeline import Deps
from lib import audit, cancellation
from lib.gh_client import API_BASE, request_with_retry, resource_for_url

FIXED_API_TOKEN_COUNT = 4
TOKEN_MODE_SINGLE = "single"
TOKEN_MODE_POOL4 = "pool4"
TOKEN_MODES = frozenset({TOKEN_MODE_SINGLE, TOKEN_MODE_POOL4})
TOKEN_RESERVE = 400
INITIAL_PER_TOKEN_CONCURRENCY = 2
MAX_PER_TOKEN_CONCURRENCY = 3
_SUCCESS_RAMP_RESPONSES = 40
_SECONDARY_DEFAULT_WAIT = 60.0
_LEASE_POLL_SECONDS = 0.25

_HISTORY_CHANNELS = frozenset({"author", "commit_trailer", "bot"})
_PR_CHANNELS = frozenset({"branch", "label", "pr_metadata"})

_PREFLIGHT_QUERY = """
query {
  viewer { login }
  rateLimit { cost limit used remaining resetAt }
}
"""


class TokenPoolConfigurationError(ValueError):
    pass


class TokenPoolExhausted(RuntimeError):
    """No configured identity can safely serve another detection request."""


class TokenPoolRetryExhausted(RuntimeError):
    """A repository has already tried every currently usable identity."""


def token_mode_error(mode: str, configured_tokens: int) -> str | None:
    if mode == TOKEN_MODE_SINGLE:
        if configured_tokens < 1:
            return "Single-token API detection needs at least one configured GitHub token"
        return None
    if mode == TOKEN_MODE_POOL4:
        if configured_tokens != FIXED_API_TOKEN_COUNT:
            return (
                "Four-account API detection needs exactly four configured GitHub tokens; "
                f"found {configured_tokens}"
            )
        return None
    return f"Unknown API detection token mode {mode!r}"


@dataclass(frozen=True)
class DetectionCostProfile:
    core: float
    graphql: float


def cost_profile(channels: Sequence[str], *, file_core_calls: float = 3.0) -> DetectionCostProfile:
    """Per-repo budget cost used for pacing; `file_core_calls` comes from the
    pack schema and scan mode (see ``detect.estimate.file_rest_calls``)."""
    selected = frozenset(channels)
    core = file_core_calls if "file" in selected else 0.0
    graphql = 0.0
    if selected & _HISTORY_CHANNELS:
        graphql += 1.0
    if selected & _PR_CHANNELS:
        graphql += 3.0
    if "issue" in selected:
        graphql += 2.0
    return DetectionCostProfile(core=core, graphql=graphql)


@dataclass
class _Budget:
    remaining: int | None = None
    reset_at: float | None = None


@dataclass
class _Slot:
    index: int
    deps: Deps
    max_concurrency: int
    active: int = 0
    active_limit: int = INITIAL_PER_TOKEN_CONCURRENCY
    next_dispatch_at: float = 0.0
    cooldown_until: float = 0.0
    success_streak: int = 0
    responses: int = 0
    secondary_hits: int = 0
    transient_hits: int = 0
    dispatches: int = 0
    disabled: bool = False
    core: _Budget = field(default_factory=_Budget)
    graphql: _Budget = field(default_factory=_Budget)

    def __post_init__(self) -> None:
        self.active_limit = min(self.active_limit, self.max_concurrency)


class TokenLease(AbstractContextManager[Deps]):
    def __init__(self, owner: DetectionTokenPool, slot: _Slot) -> None:
        self._owner = owner
        self._slot = slot
        self._released = False

    @property
    def deps(self) -> Deps:
        return self._slot.deps

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._owner._release(self._slot)

    def __enter__(self) -> Deps:
        return self.deps

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()


class DetectionTokenPool:
    """Four-account API pool with per-identity pacing and a shared safety brake."""

    def __init__(
        self,
        dependencies: Sequence[Deps],
        channels: Sequence[str],
        *,
        max_concurrency: int = MAX_PER_TOKEN_CONCURRENCY,
        clock: Callable[[], float] = time.monotonic,
        wall_clock: Callable[[], float] = time.time,
        file_core_calls: float = 3.0,
    ) -> None:
        if len(dependencies) != FIXED_API_TOKEN_COUNT:
            raise TokenPoolConfigurationError(
                f"API detection requires exactly {FIXED_API_TOKEN_COUNT} GitHub tokens"
            )
        fingerprints = [deps.token_fp for deps in dependencies]
        if len(set(fingerprints)) != FIXED_API_TOKEN_COUNT:
            raise TokenPoolConfigurationError("API detection tokens must be distinct")
        per_token = max(1, min(int(max_concurrency), MAX_PER_TOKEN_CONCURRENCY))
        self._slots = [
            _Slot(index=index, deps=deps, max_concurrency=per_token)
            for index, deps in enumerate(dependencies)
        ]
        self._by_fingerprint = {slot.deps.token_fp: slot for slot in self._slots}
        self._profile = cost_profile(channels, file_core_calls=file_core_calls)
        self._clock = clock
        self._wall_clock = wall_clock
        self._condition = threading.Condition()
        self._global_cooldown_until = 0.0
        self._closed = False

    @property
    def primary(self) -> Deps:
        return self._slots[0].deps

    @property
    def worker_limit(self) -> int:
        return sum(slot.max_concurrency for slot in self._slots)

    def preflight(self) -> None:
        identities: list[str] = []
        for slot in self._slots:
            identity_response = request_with_retry(
                slot.deps.client,
                "GET",
                f"{API_BASE}/user",
                limiter=slot.deps.limiter,
                token_id=slot.deps.token_fp,
                max_attempts=3,
                on_response=lambda response, _latency, fp=slot.deps.token_fp: self.observe(
                    fp, response, "preflight"
                ),
            )
            if identity_response.status_code != 200:
                raise TokenPoolConfigurationError(
                    f"GitHub token {slot.deps.token_fp} failed identity preflight "
                    f"(HTTP {identity_response.status_code})"
                )
            identity_payload = _json_object(identity_response)
            login = identity_payload.get("login")
            if not isinstance(login, str) or not login:
                raise TokenPoolConfigurationError(
                    f"GitHub token {slot.deps.token_fp} returned no account identity"
                )
            identities.append(login.casefold())
            graphql_response = request_with_retry(
                slot.deps.client,
                "POST",
                f"{API_BASE}/graphql",
                json_body={"query": _PREFLIGHT_QUERY},
                limiter=slot.deps.limiter,
                token_id=slot.deps.token_fp,
                max_attempts=3,
                on_response=lambda response, _latency, fp=slot.deps.token_fp: self.observe(
                    fp, response, "preflight"
                ),
            )
            if graphql_response.status_code != 200:
                raise TokenPoolConfigurationError(
                    f"GitHub token {slot.deps.token_fp} failed GraphQL preflight "
                    f"(HTTP {graphql_response.status_code})"
                )
            payload = _json_object(graphql_response)
            errors = payload.get("errors")
            if errors:
                raise TokenPoolConfigurationError(
                    f"GitHub token {slot.deps.token_fp} returned GraphQL preflight errors"
                )
            self._observe_graphql_payload(slot, payload)

        if len(set(identities)) != FIXED_API_TOKEN_COUNT:
            raise TokenPoolConfigurationError(
                "the four GitHub tokens must belong to four distinct accounts"
            )

    def lease(self, *, exclude: frozenset[str] | None = None) -> TokenLease:
        excluded = exclude or frozenset()
        while True:
            cancellation.check()
            with self._condition:
                if self._closed:
                    raise RuntimeError("detection token pool is closed")
                now = self._clock()
                wall_now = self._wall_clock()
                ready: list[_Slot] = []
                next_ready: list[float] = []
                for slot in self._slots:
                    if slot.disabled or slot.deps.token_fp in excluded:
                        continue
                    available_at = self._available_at(slot, now, wall_now)
                    next_ready.append(available_at)
                    if slot.active < slot.active_limit and available_at <= now:
                        ready.append(slot)
                if ready:
                    slot = min(
                        ready,
                        key=lambda candidate: (
                            candidate.active / max(1, candidate.active_limit),
                            candidate.dispatches,
                            candidate.index,
                        ),
                    )
                    slot.active += 1
                    slot.dispatches += 1
                    interval = self._dispatch_interval(slot, wall_now)
                    slot.next_dispatch_at = max(now, slot.next_dispatch_at) + interval
                    return TokenLease(self, slot)
                if not next_ready:
                    if any(not slot.disabled for slot in self._slots):
                        raise TokenPoolRetryExhausted(
                            "no untried GitHub identity remains for this repository"
                        )
                    raise TokenPoolExhausted(
                        "all GitHub identities in the detection pool are disabled"
                    )
                future = min(next_ready) if next_ready else now + _LEASE_POLL_SECONDS
                timeout = max(0.01, min(_LEASE_POLL_SECONDS, future - now))
                self._condition.wait(timeout=timeout)

    def observe(self, token_fp: str, response: httpx.Response, phase: str) -> None:
        slot = self._by_fingerprint.get(token_fp)
        if slot is None:
            return
        now = self._clock()
        with self._condition:
            slot.responses += 1
            resource = response.headers.get("x-ratelimit-resource")
            if not resource and response.request is not None:
                resource = resource_for_url(str(response.request.url))
            budget = slot.graphql if resource == "graphql" else slot.core
            remaining = _integer(response.headers.get("x-ratelimit-remaining"))
            reset_at = _number(response.headers.get("x-ratelimit-reset"))
            if remaining is not None:
                budget.remaining = remaining
            if reset_at is not None:
                budget.reset_at = reset_at
            payload = audit.cached_json(response)
            if payload is None:
                try:
                    payload = response.json()
                except ValueError:
                    payload = None
            graphql_errors = False
            if resource == "graphql" and isinstance(payload, Mapping):
                self._observe_graphql_payload(slot, payload)
                graphql_errors = bool(payload.get("errors"))

            if response.status_code == 401:
                slot.disabled = True
                slot.success_streak = 0
                slot.active_limit = 1
            elif response.status_code in (403, 429):
                wait = _number(response.headers.get("retry-after")) or _SECONDARY_DEFAULT_WAIT
                slot.secondary_hits += 1
                slot.success_streak = 0
                slot.active_limit = 1
                slot.cooldown_until = max(slot.cooldown_until, now + wait + slot.index)
                self._global_cooldown_until = max(self._global_cooldown_until, now + wait)
            elif response.status_code in (500, 502, 503, 504):
                slot.transient_hits += 1
                slot.success_streak = 0
                slot.active_limit = max(1, slot.active_limit - 1)
            elif 200 <= response.status_code < 300 and phase != "preflight" and not graphql_errors:
                slot.success_streak += 1
                if (
                    slot.success_streak >= _SUCCESS_RAMP_RESPONSES
                    and slot.active_limit < slot.max_concurrency
                ):
                    slot.active_limit += 1
                    slot.success_streak = 0
            self._condition.notify_all()

    def raise_if_exhausted(self) -> None:
        with self._condition:
            if all(slot.disabled for slot in self._slots):
                raise TokenPoolExhausted("all GitHub identities in the detection pool are disabled")

    def stats(self) -> dict[str, object]:
        with self._condition:
            now = self._clock()
            return {
                "tokens": FIXED_API_TOKEN_COUNT,
                "reserve": TOKEN_RESERVE,
                "global_cooldown_seconds": round(max(0.0, self._global_cooldown_until - now), 1),
                "profile": {"core": self._profile.core, "graphql": self._profile.graphql},
                "accounts": [
                    {
                        "fingerprint": slot.deps.token_fp,
                        "dispatches": slot.dispatches,
                        "responses": slot.responses,
                        "secondary_hits": slot.secondary_hits,
                        "transient_hits": slot.transient_hits,
                        "active": slot.active,
                        "active_limit": slot.active_limit,
                        "disabled": slot.disabled,
                        "cooldown_seconds": round(max(0.0, slot.cooldown_until - now), 1),
                        "core_remaining": slot.core.remaining,
                        "graphql_remaining": slot.graphql.remaining,
                    }
                    for slot in self._slots
                ],
            }

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._condition.notify_all()
        seen: set[int] = set()
        for slot in self._slots:
            marker = id(slot.deps.client)
            if marker in seen:
                continue
            seen.add(marker)
            slot.deps.client.close()

    def _release(self, slot: _Slot) -> None:
        with self._condition:
            slot.active = max(0, slot.active - 1)
            self._condition.notify_all()

    def _available_at(self, slot: _Slot, now: float, wall_now: float) -> float:
        available = max(
            now,
            slot.next_dispatch_at,
            slot.cooldown_until,
            self._global_cooldown_until,
        )
        for cost, budget in (
            (self._profile.core, slot.core),
            (self._profile.graphql, slot.graphql),
        ):
            if cost <= 0 or budget.remaining is None or budget.remaining > TOKEN_RESERVE + cost:
                continue
            if budget.reset_at is None:
                return max(available, now + _SECONDARY_DEFAULT_WAIT)
            available = max(available, now + max(0.0, budget.reset_at - wall_now))
        return available

    def _dispatch_interval(self, slot: _Slot, wall_now: float) -> float:
        intervals = [
            self._resource_interval(self._profile.core, slot.core, wall_now),
            self._resource_interval(self._profile.graphql, slot.graphql, wall_now),
        ]
        return max(intervals)

    @staticmethod
    def _resource_interval(cost: float, budget: _Budget, wall_now: float) -> float:
        if cost <= 0:
            return 0.0
        remaining = budget.remaining
        reset_at = budget.reset_at
        if remaining is not None and reset_at is not None and reset_at > wall_now:
            usable = max(1.0, float(remaining - TOKEN_RESERVE))
            rate = usable / max(1.0, reset_at - wall_now)
        else:
            rate = (5000.0 - TOKEN_RESERVE) / 3600.0
        return cost / max(rate, 0.001)

    def _observe_graphql_payload(self, slot: _Slot, payload: Mapping[str, Any]) -> None:
        data = payload.get("data")
        if not isinstance(data, Mapping):
            return
        node = data.get("rateLimit")
        if not isinstance(node, Mapping):
            return
        remaining = _integer(node.get("remaining"))
        if remaining is not None:
            slot.graphql.remaining = remaining
        reset = node.get("resetAt")
        if isinstance(reset, str):
            parsed = _instant(reset)
            if parsed is not None:
                slot.graphql.reset_at = parsed.timestamp()


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _number(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _instant(value: str) -> datetime | None:
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _json_object(response: httpx.Response) -> Mapping[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise TokenPoolConfigurationError("GitHub preflight returned malformed JSON") from exc
    if not isinstance(payload, Mapping):
        raise TokenPoolConfigurationError("GitHub preflight returned a non-object payload")
    return payload
