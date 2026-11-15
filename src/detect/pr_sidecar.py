"""Hybrid detection: a PR-metadata API sidecar running beside the git scan.

A local clone sees every commit but nothing GitHub stores outside git: PR
descriptions ("Generated with Claude Code"), PR authors, head branch names of
squash-merged PRs, labels, and PR creation dates. The sidecar fetches exactly
those — one lean GraphQL query per repository — in the parent process while
the clone workers scan, and merges them into each scan before it is persisted.

It never fails or delays a repository's git evidence: a failed fetch leaves
the git channels untouched and records the API status on the scan, and a run
of consecutive failures (quota exhausted, outage) trips a breaker that turns
the rest of the run into a plain git scan with a run-level warning.
"""

from __future__ import annotations

import threading
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import Future, ThreadPoolExecutor, wait
from dataclasses import replace

from detect.attribution import dedupe_hits
from detect.channels import ChannelResult, FailureKind
from detect.orchestrator import _repo_document, _RepoScan  # same-package helper reuse
from lib import cancellation
from lib.cancellation import RunCancelled

# Channels the sidecar can feed; ``issue`` stays API-only (it added 1 repo in
# 9,510 against run 101, and would cost a second query per repository).
SIDECAR_CHANNELS = frozenset({"branch", "label", "pr_metadata"})
PR_API_KEY = "pr_api"

_DEFAULT_WORKERS = 4
_DEFAULT_LOOKAHEAD = 256
_DEFAULT_FAILURE_LIMIT = 25
_POLL_SECONDS = 0.25
_NOTE_LIMIT = 200

PrFetch = Callable[[str], ChannelResult]


class PrSidecar:
    """Fetch PR metadata ahead of the git scan, bounded and breaker-protected.

    ``prefetch`` primes a lookahead window in candidate order; ``result``
    returns (fetching on demand if needed) one repository's result and tops
    the window back up, so at most ``lookahead`` results are held at once.
    """

    def __init__(
        self,
        fetch: PrFetch,
        *,
        workers: int = _DEFAULT_WORKERS,
        lookahead: int = _DEFAULT_LOOKAHEAD,
        failure_limit: int = _DEFAULT_FAILURE_LIMIT,
    ) -> None:
        self._fetch = fetch
        self._pool = ThreadPoolExecutor(
            max_workers=max(1, workers), thread_name_prefix="detect-pr-api"
        )
        self._lookahead = max(1, lookahead)
        self._failure_limit = max(1, failure_limit)
        self._lock = threading.Lock()
        self._futures: dict[str, Future[ChannelResult]] = {}
        self._queue: list[str] = []
        self._next = 0
        self._consecutive_failures = 0
        self._tripped_note: str | None = None
        self._statuses: Counter[str] = Counter()

    # -- scheduling -----------------------------------------------------
    def prefetch(self, full_names: Iterable[str]) -> None:
        with self._lock:
            self._queue = list(full_names)
            self._next = 0
            self._top_up_locked()

    def _top_up_locked(self) -> None:
        while len(self._futures) < self._lookahead and self._next < len(self._queue):
            name = self._queue[self._next]
            self._next += 1
            if name not in self._futures:
                self._futures[name] = self._pool.submit(self._run, name)

    def _run(self, full_name: str) -> ChannelResult:
        tripped = self._tripped_note
        if tripped is not None:
            return ChannelResult(status="skipped", note=tripped)
        try:
            result = self._fetch(full_name)
        except RunCancelled:
            raise
        except Exception as exc:  # the sidecar must never fail a repository
            result = ChannelResult(
                status="partial",
                note=f"{type(exc).__name__}: {exc}"[:_NOTE_LIMIT],
                failure_kind=FailureKind.RETRYABLE,
            )
        self._record(result)
        return result

    def _record(self, result: ChannelResult) -> None:
        with self._lock:
            # Only retryable faults (quota, outage, timeouts) count toward the
            # breaker; a permanent per-repo answer says nothing about the API.
            if result.status == "partial" and result.failure_kind is FailureKind.RETRYABLE:
                self._consecutive_failures += 1
                if self._consecutive_failures >= self._failure_limit and self._tripped_note is None:
                    self._tripped_note = (
                        f"PR metadata API disabled after {self._consecutive_failures}"
                        f" consecutive failures (last: {result.note}); git evidence unaffected"
                    )[: _NOTE_LIMIT * 2]
            else:
                self._consecutive_failures = 0

    def result(self, full_name: str) -> ChannelResult:
        with self._lock:
            future = self._futures.pop(full_name, None)
            if future is None:
                future = self._pool.submit(self._run, full_name)
            self._top_up_locked()
        while True:
            cancellation.check()
            done, _ = wait([future], timeout=_POLL_SECONDS)
            if done:
                break
        result = future.result()
        with self._lock:
            self._statuses[result.status] += 1
        return result

    def discard(self, full_name: str) -> None:
        """Drop a prefetched result whose repository produced no git scan."""
        with self._lock:
            future = self._futures.pop(full_name, None)
            if future is not None:
                future.cancel()
            self._top_up_locked()

    # -- reporting / lifecycle -------------------------------------------
    @property
    def tripped_note(self) -> str | None:
        return self._tripped_note

    def stats(self) -> dict[str, object]:
        with self._lock:
            return {
                "statuses": dict(sorted(self._statuses.items())),
                "tripped": self._tripped_note is not None,
            }

    def close(self, *, cancelled: bool = False) -> None:
        self._pool.shutdown(wait=not cancelled, cancel_futures=True)


def _merge_created_at(
    base: Mapping[str, object], created_at: Mapping[object, object]
) -> dict[str, object]:
    merged = dict(base)
    existing = merged.get("created_at")
    combined = dict(existing) if isinstance(existing, Mapping) else {}
    combined.update(created_at)
    merged["created_at"] = combined
    return merged


def merge_pr_metadata(scan: _RepoScan, api: ChannelResult, channels: frozenset[str]) -> None:
    """Fold one sidecar result into a finished git scan, in place.

    API hits join the selected git channels; ``label`` becomes a real channel
    carrying the API status; PR creation dates attach to the PR result so
    ``first_signal_at`` can date PR evidence. A failed fetch never downgrades a
    git channel: its status is recorded separately under ``pr_api``.
    """
    if scan.document.get("unavailable") and not scan.results:
        return  # a failed clone has no git evidence to enrich
    status = "partial" if api.status == "unavailable" else api.status
    selected = channels & SIDECAR_CHANNELS
    api_hits = [hit for hit in api.hits if hit.channel in selected]
    created_at = api.stats.get("created_at")
    created = created_at if isinstance(created_at, Mapping) else {}
    if "label" in selected:
        scan.results["label"] = ChannelResult(
            hits=tuple(hit for hit in api_hits if hit.channel == "label"),
            status=status,
            note=api.note,
            failure_kind=api.failure_kind,
        )
    for key in ("branch", "pr_metadata"):
        local = scan.results.get(key)
        if local is None:
            continue
        extra = [hit for hit in api_hits if hit.channel == key]
        stats = _merge_created_at(local.stats, created) if key == "pr_metadata" else local.stats
        scan.results[key] = replace(
            local, hits=tuple(dedupe_hits([*local.hits, *extra])), stats=stats
        )
    if "pr_metadata" in scan.results:
        scan.pr_result = scan.results["pr_metadata"]
    elif scan.pr_result is not None:
        scan.pr_result = replace(
            scan.pr_result, stats=_merge_created_at(scan.pr_result.stats, created)
        )
    elif created:
        scan.pr_result = ChannelResult(stats={"created_at": dict(created)})
    scan.hits = dedupe_hits([*scan.hits, *api_hits])
    scan.document = _repo_document(scan)
    scan.document[PR_API_KEY] = status
    if status != "ok" and api.note and "label" not in selected:
        scan.document.setdefault("notes", []).append(f"{PR_API_KEY}: {api.note}")
