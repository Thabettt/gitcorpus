"""Env-gated per-repo phase metrics for git detection scans.

When ``GITCORPUS_PHASE_METRICS`` names a directory, every scanned repo
appends one JSON line to a per-process ``phase-metrics-<pid>.jsonl`` file in
that directory. Per-process files keep concurrent spawn workers from
interleaving partial lines; aggregators glob the directory. The machinery is
inert when the variable is unset, and any failure while writing a line is
swallowed so metrics can never affect a scan.
"""

from __future__ import annotations

import contextvars
import json
import os
import threading
import time
from dataclasses import dataclass, fields
from pathlib import Path

PHASE_METRICS_ENV = "GITCORPUS_PHASE_METRICS"

_current: contextvars.ContextVar[RepoPhaseMetrics | None] = contextvars.ContextVar(
    "gitcorpus_phase_metrics", default=None
)
_write_lock = threading.Lock()


@dataclass
class RepoPhaseMetrics:
    """One repo's phase timings; ``None`` marks a phase that did not happen."""

    full_name: str
    probe_ms: float | None = None
    clone_ms: float | None = None
    files_ms: float | None = None
    history_ms: float | None = None
    pr_listing_ms: float | None = None
    pr_fetch_ms: float | None = None
    walk_ms: float | None = None
    total_ms: float | None = None
    refs_count: int | None = None
    gated: bool | None = None
    gate_wait_ms: float | None = None
    cat_file_spawns: int | None = None

    def as_dict(self) -> dict[str, object]:
        return {field.name: getattr(self, field.name) for field in fields(self)}


def elapsed_ms(started: float) -> float:
    return (time.monotonic() - started) * 1000.0


def collecting(record: RepoPhaseMetrics) -> contextvars.Token:
    """Make ``record`` the current repo's metrics within this context."""
    return _current.set(record)


def reset(token: contextvars.Token) -> None:
    _current.reset(token)


def current() -> RepoPhaseMetrics | None:
    """The metrics record collecting for the current scan context, if any."""
    return _current.get()


def metrics_directory() -> str | None:
    return os.environ.get(PHASE_METRICS_ENV, "").strip() or None


def write_phase_metrics(record: RepoPhaseMetrics) -> None:
    """Append ``record`` as one JSON line; a silent no-op when disabled."""
    directory = metrics_directory()
    if directory is None:
        return
    try:
        line = json.dumps(record.as_dict(), separators=(",", ":"))
        target = Path(directory)
        target.mkdir(parents=True, exist_ok=True)
        with _write_lock:
            with (target / f"phase-metrics-{os.getpid()}.jsonl").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(line + "\n")
    except Exception:
        # Diagnostics must never take a scan down with them.
        pass
