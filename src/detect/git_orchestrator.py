from __future__ import annotations

import contextlib
import contextvars
import dataclasses
import itertools
import multiprocessing
import os
import queue
import shutil
import stat
import subprocess
import threading
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from sqlalchemy import delete, insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from detect import phase_metrics, repo_walk
from detect.attribution import dedupe_hits
from detect.breaker import CircuitBreaker, local_values
from detect.channels import ChannelResult, detect_pr_metadata
from detect.gitio import (
    _MONSTER_PR_THRESHOLD,
    GitError,
    GitRepo,
    RemoteRefs,
    RemoteRefsUnavailable,
    _acquire_gate,
    classify_git_failure,
    clone_lean,
    newest_pr_refs,
    remote_refs_for,
    retry_call,
)
from detect.local_channels import (
    detect_branch_local,
    detect_files_local,
    detect_hidden_refs_local,
    detect_history_local,
    detect_pr_commits_local,
)
from detect.orchestrator import (
    DetectOptions,
    _audit_hook,
    _candidates,
    _facets,
    _failed_scan,
    _fold_summary,
    _repo_document,
    _RepoScan,  # same-package helper reuse, intentional
    _scan_contribution,
    _SummaryContribution,
    stream_detections,
)
from detect.packs import Pack
from detect.pr_sidecar import (
    PR_API_KEY,
    SIDECAR_CHANNELS,
    PrFetch,
    PrSidecar,
    merge_pr_metadata,
)
from discover.pipeline import Deps
from enrich.cloner import LOW_DISK_THRESHOLD_MB, MARKER_NAME, free_disk_mb
from lib import audit, cancellation, progress
from lib.cancellation import RunCancelled
from lib.procguard import contain_process_tree
from serve.executor import RunPayload, RunPayloadItem
from store.models import DetectionCheckpoint, DetectionEvidence, DetectionRepoFilter, RunItem

LOCAL_CHANNELS = (
    "file",
    "author",
    "branch",
    "hidden_ref",
    "bot",
    "commit_trailer",
    "pr_metadata",
)
API_ONLY_CHANNELS = ("label", "issue")
HYBRID_SOURCE = "hybrid"
_PR_WORKERS_PER_TOKEN = 3
_PR_MAX_WORKERS = 12
_HISTORY_KEYS = ("author", "commit_trailer", "bot")
_CANCEL_POLL_SECONDS = 0.25
_LOW_DISK_MARKER = "low_disk"
_DEFAULT_PR_GATE_PERMITS = 32
_PR_GATE_ENV = "GITCORPUS_PR_GATE"


@dataclass(frozen=True)
class GitScanConfig:
    depth: int = 100
    keep: bool = False
    scan_root: str = "clones"
    timeout: float | None = None
    workers: int = 16
    attempts: int = 4
    retry_delay: float = 1.0
    processes: int = 0
    pr_gate_permits: int = _DEFAULT_PR_GATE_PERMITS


def pr_gate_permits_from_env() -> int:
    """The serve layer's fleet-gate size; invalid or non-positive means 32."""
    raw = os.environ.get(_PR_GATE_ENV)
    if raw is None or not raw.strip():
        return _DEFAULT_PR_GATE_PERMITS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_PR_GATE_PERMITS
    return value if value > 0 else _DEFAULT_PR_GATE_PERMITS


def _clear_read_only(func, path, _exc) -> None:
    # Git for Windows marks pack files read-only; without clearing the
    # attribute rmtree's unlink fails and the whole sweep survives.
    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IWRITE)
        func(path)


def _remove_tree(path: Path) -> None:
    for delay in (0.0, 0.2, 1.0, 0.0, 0.5):
        if delay:
            time.sleep(delay)
        shutil.rmtree(path, onexc=_clear_read_only)
        if not path.exists():
            return


def _kill_tree(process: multiprocessing.Process) -> None:
    # terminate() signals only the scan worker; its git children (notably
    # `cat-file --batch`) keep running until the app-exit job object closes,
    # leaking handles and a slot of bandwidth per dead worker. taskkill /T
    # walks the spawned tree; failures are suppressed because the target is
    # often already gone and a kill is best-effort.
    if os.name == "nt":
        with contextlib.suppress(OSError, subprocess.TimeoutExpired):
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=30,
                check=False,
            )
        return
    process.terminate()


def _scan_one(
    run_dir: Path,
    cfg: GitScanConfig,
    spec: DetectOptions,
    pack: Pack,
    active: frozenset[str],
    candidate: Mapping,
    *,
    clone_one: Callable[[str, Path], None],
    make_repo: Callable[[Path, str], GitRepo],
    pr_gate: object | None = None,
    prefetched: RemoteRefs | None = None,
    gate_reserved: bool = False,
    probe_ms: float | None = None,
) -> _RepoScan:
    session: repo_walk.RepoWalkSession | None = None
    session_failed = False
    started = time.monotonic()
    spawns_before = repo_walk.cat_file_spawns()
    metrics = phase_metrics.RepoPhaseMetrics(full_name="", probe_ms=probe_ms)

    def walk_session(repo: GitRepo) -> repo_walk.RepoWalkSession | None:
        nonlocal session, session_failed
        if session is None and not session_failed:
            try:
                session = repo_walk.RepoWalkSession.open(repo)
            except RunCancelled:
                raise
            except Exception:
                session_failed = True
        return session

    token = phase_metrics.collecting(metrics)
    try:
        full_name = str(candidate["full_name"])
        metrics.full_name = full_name
        dest = run_dir / full_name.replace("/", "__")
        if not (cfg.keep and (dest / MARKER_NAME).exists()):

            def clone_attempt() -> None:
                shutil.rmtree(dest, ignore_errors=True)
                clone_one(full_name, dest)
                (dest / MARKER_NAME).write_text("", encoding="utf-8")

            clone_started = time.monotonic()
            try:
                retry_call(
                    clone_attempt,
                    attempts=cfg.attempts,
                    base_delay=cfg.retry_delay,
                    retryable=lambda exc: classify_git_failure(exc) != "dead",
                )
            finally:
                metrics.clone_ms = phase_metrics.elapsed_ms(clone_started)
        repo = make_repo(dest, full_name)
        results: dict[str, ChannelResult] = {}
        history_stats: Mapping[str, object] = {}
        if "file" in active:
            files_started = time.monotonic()
            try:
                results["file"] = detect_files_local(
                    repo, pack, spec.agents, session=walk_session(repo)
                )
            finally:
                metrics.files_ms = phase_metrics.elapsed_ms(files_started)
        if set(_HISTORY_KEYS) & active:
            history_started = time.monotonic()
            try:
                history = detect_history_local(
                    repo, pack, spec.agents, limit=cfg.depth, session=walk_session(repo)
                )
            finally:
                metrics.history_ms = phase_metrics.elapsed_ms(history_started)
            for key in _HISTORY_KEYS:
                if key in active:
                    results[key] = history[key]
            history_stats = history["author"].stats
        pr_result: ChannelResult | None = None
        if "pr_metadata" in active:
            pr_result = detect_pr_commits_local(
                repo,
                pack,
                spec.agents,
                depth=cfg.depth,
                attempts=cfg.attempts,
                retry_delay=cfg.retry_delay,
                gate=pr_gate,
                refs=prefetched.pr_refs if prefetched is not None else None,
                gate_reserved=gate_reserved,
                session=walk_session(repo),
                pr_limit=_pr_window(spec),
            )
            results["pr_metadata"] = pr_result
        if "branch" in active:
            results["branch"] = detect_branch_local(repo, pack, spec.agents, limit=cfg.depth)
        if "hidden_ref" in active:
            results["hidden_ref"] = detect_hidden_refs_local(repo, pack, spec.agents)
        hits = dedupe_hits([hit for result in results.values() for hit in result.hits])
        scan = _RepoScan(
            repo_id=int(candidate["repo_id"]),
            full_name=full_name,
            stargazers=candidate["stargazers"],
            hits=hits,
            results=results,
            pr_result=pr_result,
            history_stats=history_stats,
            repo_created_at=candidate.get("repo_created_at"),
            commit_count=candidate.get("commit_count"),
            pushed_at=candidate.get("pushed_at"),
            archived=candidate.get("archived"),
            language=candidate.get("language"),
            license_spdx=candidate.get("license_spdx"),
            country_iso=candidate.get("country_iso"),
            geo_confidence=candidate.get("geo_confidence"),
            virtuals=candidate.get("virtuals") or {},
        )
        scan.document = _repo_document(scan)
        return scan
    finally:
        phase_metrics.reset(token)
        metrics.total_ms = phase_metrics.elapsed_ms(started)
        metrics.cat_file_spawns = repo_walk.cat_file_spawns() - spawns_before
        phase_metrics.write_phase_metrics(metrics)
        if session is not None:
            with contextlib.suppress(Exception):
                session.close()
        # A scheduler-reserved fleet permit is released exactly here, whatever
        # the outcome; the acquire happened in the scheduler's thread, and a
        # BoundedSemaphore has no thread ownership, so this is legal.
        if gate_reserved and pr_gate is not None:
            pr_gate.release()  # type: ignore


def _persist_scan(
    engine: Engine,
    run_id: int,
    scan: _RepoScan,
    pack: Pack,
    checkpoint: tuple[bool, _SummaryContribution] | None = None,
) -> None:
    rows = [
        {
            "run_id": run_id,
            "repo_id": scan.repo_id,
            "pack_version": pack.version,
            **hit.storage_fields(),
        }
        for hit in scan.hits
    ]
    facets = _facets(scan.hits)
    with engine.begin() as connection:
        if rows:
            connection.execute(insert(DetectionEvidence), rows)
        if facets:
            connection.execute(
                pg_insert(DetectionRepoFilter)
                .values(
                    [
                        {
                            "run_id": run_id,
                            "repo_id": scan.repo_id,
                            "agent": agent,
                            "channel": channel,
                        }
                        for agent, channel in facets
                    ]
                )
                .on_conflict_do_nothing()
            )
        connection.execute(
            pg_insert(RunItem)
            .values(
                run_id=run_id,
                repo_id=scan.repo_id,
                full_name=scan.full_name,
                stargazers=scan.stargazers,
                repo_created_at=scan.repo_created_at,
                commit_count=scan.commit_count,
                pushed_at=scan.pushed_at,
                archived=scan.archived,
                language=scan.language,
                license_spdx=scan.license_spdx,
                country_iso=scan.country_iso,
                geo_confidence=scan.geo_confidence,
                virtuals=dict(scan.virtuals),
                detection=scan.document,
            )
            .on_conflict_do_update(
                index_elements=["run_id", "repo_id"],
                set_={
                    "full_name": scan.full_name,
                    "stargazers": scan.stargazers,
                    "repo_created_at": scan.repo_created_at,
                    "commit_count": scan.commit_count,
                    "pushed_at": scan.pushed_at,
                    "archived": scan.archived,
                    "language": scan.language,
                    "license_spdx": scan.license_spdx,
                    "country_iso": scan.country_iso,
                    "geo_confidence": scan.geo_confidence,
                    "virtuals": dict(scan.virtuals),
                    "detection": scan.document,
                },
            )
        )
        if checkpoint is not None:
            # Same transaction as the run item: a resume never sees a
            # checkpoint whose evidence is missing, or the reverse.
            clean, contribution = checkpoint
            values = {"clean": clean, "contribution": dataclasses.asdict(contribution)}
            connection.execute(
                pg_insert(DetectionCheckpoint)
                .values(run_id=run_id, repo_id=scan.repo_id, **values)
                .on_conflict_do_update(index_elements=["run_id", "repo_id"], set_=values)
            )


@dataclass(frozen=True)
class _RetainedScan:
    repo_id: int
    full_name: str
    stargazers: int | None
    repo_created_at: datetime | None
    commit_count: int | None
    pushed_at: datetime | None
    archived: bool | None
    language: str | None
    license_spdx: str | None
    country_iso: str | None
    geo_confidence: str | None
    virtuals: dict
    document: dict
    contribution: _SummaryContribution
    partial: bool


def _retain(scan: _RepoScan) -> _RetainedScan:
    partial = any(result.status in ("partial", "unavailable") for result in scan.results.values())
    return _RetainedScan(
        repo_id=scan.repo_id,
        full_name=scan.full_name,
        stargazers=scan.stargazers,
        repo_created_at=scan.repo_created_at,
        commit_count=scan.commit_count,
        pushed_at=scan.pushed_at,
        archived=scan.archived,
        language=scan.language,
        license_spdx=scan.license_spdx,
        country_iso=scan.country_iso,
        geo_confidence=scan.geo_confidence,
        virtuals=dict(scan.virtuals),
        document=scan.document,
        contribution=_scan_contribution(scan),
        partial=partial,
    )


class Admission(NamedTuple):
    """Scheduler decision for one admitted candidate."""

    candidate: Mapping
    prefetched: RemoteRefs | None
    gate_reserved: bool


class _Pending(NamedTuple):
    """A queued candidate; refs already probed are carried across requeues."""

    candidate: Mapping
    refs: RemoteRefs | None = None


_PERSIST_ATTEMPTS = 3


def _settle_scan(
    engine: Engine,
    run_id: int,
    scan: _RepoScan,
    pack: Pack,
    finalize: Callable[[_RepoScan], None] | None,
    failures: list[str],
) -> _RetainedScan:
    """Finalize, retain and persist one scan; never let one repo sink the run.

    The scan itself already isolates git failures. This guards what happens
    after: an enrichment merge that throws keeps the plain git scan, and a
    persist that keeps failing is recorded as a run warning while the scan
    still rides the payload (the executor snapshots every payload item), so
    a single bad repository costs at most its own evidence rows.
    """
    clean = True
    if finalize is not None:
        try:
            finalize(scan)
        except RunCancelled:
            raise
        except Exception as exc:
            clean = False
            failures.append(f"{scan.full_name}: enrichment skipped: {type(exc).__name__}: {exc}")
    try:
        retained = _retain(scan)
    except RunCancelled:
        raise
    except Exception as exc:
        clean = False
        scan = _failed_scan(_candidate_of(scan), exc, failure_class="fatal")
        failures.append(_failure_message(scan))
        retained = _retain(scan)
    # Only a scan with nothing missing may be skipped by a resume: no partial
    # or unavailable channel, and (hybrid) PR metadata actually fetched.
    clean = (
        clean
        and not retained.partial
        and not scan.document.get("unavailable")
        and scan.document.get(PR_API_KEY, "ok") == "ok"
    )
    for attempt in range(1, _PERSIST_ATTEMPTS + 1):
        try:
            _persist_scan(engine, run_id, scan, pack, (clean, retained.contribution))
            break
        except RunCancelled:
            raise
        except Exception as exc:
            if attempt >= _PERSIST_ATTEMPTS:
                failures.append(
                    f"{scan.full_name}: evidence not saved: {type(exc).__name__}: {exc}"[:300]
                )
                break
            cancellation.check()
            time.sleep(0.5 * attempt)
    return retained


def _candidate_of(scan: _RepoScan) -> dict:
    return {
        "repo_id": scan.repo_id,
        "full_name": scan.full_name,
        "stargazers": scan.stargazers,
        "repo_created_at": scan.repo_created_at,
        "commit_count": scan.commit_count,
        "pushed_at": scan.pushed_at,
        "archived": scan.archived,
        "language": scan.language,
        "license_spdx": scan.license_spdx,
        "country_iso": scan.country_iso,
        "geo_confidence": scan.geo_confidence,
        "virtuals": scan.virtuals,
    }


def _load_finished(engine: Engine, run_id: int, wanted: set[int]) -> dict[int, _RetainedScan]:
    """Repositories a resumed run already finished cleanly, ready to fold in.

    A checkpoint that no longer parses (summary fields changed since it was
    written) is dropped with its evidence so the repository is rescanned
    from a clean slate rather than double-counted.
    """
    with engine.connect() as connection:
        if connection.scalar(text("SELECT to_regclass('detection_checkpoints')")) is None:
            return {}
        rows = (
            connection.execute(
                select(RunItem.__table__, DetectionCheckpoint.contribution)
                .join(
                    DetectionCheckpoint,
                    (DetectionCheckpoint.run_id == RunItem.run_id)
                    & (DetectionCheckpoint.repo_id == RunItem.repo_id),
                )
                .where(RunItem.run_id == run_id, DetectionCheckpoint.clean.is_(True))
            )
            .mappings()
            .all()
        )
    finished: dict[int, _RetainedScan] = {}
    stale: list[int] = []
    for row in rows:
        repo_id = row["repo_id"]
        if repo_id not in wanted:
            continue
        try:
            summary = _SummaryContribution(**row["contribution"])
            if not isinstance(row["detection"], dict):
                raise TypeError("run item has no detection document")
        except (TypeError, ValueError):
            stale.append(repo_id)
            continue
        finished[repo_id] = _RetainedScan(
            repo_id=repo_id,
            full_name=row["full_name"],
            stargazers=row["stargazers"],
            repo_created_at=row["repo_created_at"],
            commit_count=row["commit_count"],
            pushed_at=row["pushed_at"],
            archived=row["archived"],
            language=row["language"],
            license_spdx=row["license_spdx"],
            country_iso=row["country_iso"],
            geo_confidence=row["geo_confidence"],
            virtuals=dict(row["virtuals"] or {}),
            document=row["detection"],
            contribution=summary,
            partial=False,
        )
    if stale:
        with engine.begin() as connection:
            for model in (DetectionEvidence, DetectionRepoFilter, DetectionCheckpoint, RunItem):
                connection.execute(
                    delete(model).where(model.run_id == run_id, model.repo_id.in_(stale))
                )
    return finished


def _failure_message(scan: _RepoScan) -> str:
    return f"{scan.full_name}: {scan.document['notes'][0]}"


def _pr_window(spec: DetectOptions) -> int:
    """The "last N pull requests" window, shared with the API channels."""
    return max(1, int(spec.windows.get("prs", 100)))


def _is_monster(refs: RemoteRefs) -> bool:
    return len(refs.pr_refs) > _MONSTER_PR_THRESHOLD


def _offline_refs(full_name: str) -> RemoteRefs:
    """Empty probe result; lets process-path tests stay offline."""
    return RemoteRefs(pr_refs={}, head_refs={})


def _entry(item) -> _Pending:
    """Accept a pending deque item as either a _Pending or a bare mapping."""
    return item if isinstance(item, _Pending) else _Pending(item)


def _admit(
    pending: deque,
    probe,
    gate: object | None,
    emit_failure: Callable[[_RepoScan], None] | None = None,
) -> Admission | None:
    """Decide the next candidate to submit, driving the pure admission rules.

    Dead repositories are emitted as failed scans without cloning (one at a
    time, then the loop keeps scanning) and never admitted; a ``None`` return
    means the queue drained. A monster whose fleet permit cannot be taken
    immediately is appended back with its prefetched refs and the candidate at
    the tail is admitted instead, so a wave of giants cannot starve the
    ordinary lane; the refs ride on the requeued entry, so it is never
    re-probed while the gate stays saturated; when the monster is the only
    candidate left it is admitted anyway and its fetch path blocks on the
    gate as before.
    """
    while pending:
        entry = _entry(pending.popleft())
        candidate = entry.candidate
        full_name = str(candidate["full_name"])
        refs = entry.refs
        if refs is None:
            try:
                refs = probe(full_name)
            except GitError as exc:
                failure_class = classify_git_failure(exc)
                if failure_class == "dead":
                    dead = _failed_scan(candidate, exc, failure_class=failure_class)
                    if emit_failure is not None:
                        emit_failure(dead)
                    continue
                refs = None
            except RemoteRefsUnavailable:
                refs = None
            except RunCancelled:
                raise
            except Exception:
                # The probe is an optimisation; any other surprise (timeout,
                # OS error) just submits the repo unprobed instead of killing
                # the worker process and its whole slice of the run.
                refs = None
        if refs is not None and gate is not None and _is_monster(refs):
            if _acquire_gate(gate, blocking=False):
                return Admission(candidate, refs, True)
            if pending:
                # Two lanes: requeue the monster with its prefetched refs and
                # admit the candidate at the tail instead. The permit attempt
                # failed, so no permit is held while the monster waits.
                pending.appendleft(_Pending(candidate, refs))
                tail = _entry(pending.pop())
                return Admission(tail.candidate, None, False)
            # It is the only candidate left; admit it anyway and let the
            # fetch path block on the gate as today.
        return Admission(candidate, refs, False)
    return None


def _scan_worker_main(
    slice_candidates: Sequence[Mapping],
    out_queue: multiprocessing.Queue,
    cancel_event: multiprocessing.Event,
    cfg: GitScanConfig,
    spec: DetectOptions,
    pack: Pack,
    run_dir_str: str,
    threads: int,
    breaker_values: tuple,
    pr_gate: multiprocessing.BoundedSemaphore,
    admission_probe: Callable[[str], RemoteRefs] = remote_refs_for,
) -> None:
    cancellation.bind(cancel_event.is_set)
    run_dir = Path(run_dir_str)
    active = frozenset(channel for channel in spec.channels if channel in LOCAL_CHANNELS)
    clone_one = lambda full_name, dest: clone_lean(  # noqa: E731
        full_name, dest, depth=cfg.depth, timeout=cfg.timeout
    )
    make_repo = lambda dest, full_name: GitRepo(  # noqa: E731
        dest, timeout=cfg.timeout, full_name=full_name
    )
    breaker = CircuitBreaker(*breaker_values)
    pool = ThreadPoolExecutor(max_workers=max(1, threads))
    probe_times: dict[str, float] = {}

    pr_window = _pr_window(spec)

    def timed_probe(full_name: str) -> RemoteRefs:
        started = time.monotonic()
        try:
            refs = admission_probe(full_name)
            # Admission sees the capped window, so a repo whose newest PRs fit
            # under the monster threshold never reserves a fleet permit.
            return replace(refs, pr_refs=newest_pr_refs(refs.pr_refs, pr_window))
        finally:
            probe_times[full_name] = phase_metrics.elapsed_ms(started)

    try:
        pending = deque(_Pending(candidate) for candidate in slice_candidates)
        retry_candidates: list[Mapping] = []
        wave = 1
        in_flight: dict[Future, Mapping] = {}
        exhausted = False

        def emit_dead(scan: _RepoScan) -> None:
            # Dead repos never reach _scan_one; record their probe cost here so
            # the metrics stream still has one line per scheduled repo.
            phase_metrics.write_phase_metrics(
                phase_metrics.RepoPhaseMetrics(
                    full_name=scan.full_name,
                    probe_ms=probe_times.pop(scan.full_name, None),
                )
            )
            out_queue.put(("scan", scan, _failure_message(scan)))

        while True:
            if cancel_event.is_set():
                raise RunCancelled()
            while not exhausted and len(in_flight) < threads:
                breaker.wait_if_open()
                free = free_disk_mb(cfg.scan_root)
                if free < LOW_DISK_THRESHOLD_MB:
                    exhausted = True
                    out_queue.put((_LOW_DISK_MARKER, float(free)))
                    break
                admission = _admit(pending, timed_probe, pr_gate, emit_dead)
                if admission is None:
                    if wave == 1 and retry_candidates:
                        wave = 2
                        pending = deque(_Pending(candidate) for candidate in retry_candidates)
                        retry_candidates = []
                        continue
                    exhausted = True
                    break
                context = contextvars.copy_context()
                try:
                    future = pool.submit(
                        context.run,
                        _scan_one,
                        run_dir,
                        cfg,
                        spec,
                        pack,
                        active,
                        admission.candidate,
                        clone_one=clone_one,
                        make_repo=make_repo,
                        pr_gate=pr_gate,
                        prefetched=admission.prefetched,
                        gate_reserved=admission.gate_reserved,
                        probe_ms=probe_times.pop(str(admission.candidate["full_name"]), None),
                    )
                except BaseException:
                    # A reserved permit must never outlive its admission, even
                    # when the submission itself fails.
                    if admission.gate_reserved and pr_gate is not None:
                        pr_gate.release()
                    raise
                in_flight[future] = admission.candidate
            if not in_flight:
                break
            ready, _ = wait(in_flight, timeout=_CANCEL_POLL_SECONDS, return_when=FIRST_COMPLETED)
            if not ready:
                continue
            future = next(iter(ready))
            cancellation.check()
            candidate = in_flight.pop(future)
            failure: str | None = None
            try:
                scan = future.result()
            except RunCancelled:
                raise
            except Exception as exc:
                failure_class = classify_git_failure(exc)
                deferred = False
                if failure_class == "transient":
                    breaker.record_failure()
                    if wave == 1:
                        retry_candidates.append(candidate)
                        deferred = True
                scan = _failed_scan(candidate, exc, failure_class=failure_class)
                if not deferred:
                    failure = _failure_message(scan)
            else:
                breaker.record_success()
            out_queue.put(("scan", scan, failure))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _drain_message(
    message,
    failures: list[str],
    warnings: list[str],
    *,
    scan_root: Path,
    total: int,
    delivered: int,
) -> tuple[bool, _RepoScan | None]:
    """Handle one worker message; returns (stopped_for_disk, scan)."""
    if isinstance(message, tuple) and message and message[0] == _LOW_DISK_MARKER:
        free = float(message[1])
        warnings.append(
            f"low disk: only {free:.0f} MB free under {str(scan_root)!r}"
            f" (reserve {LOW_DISK_THRESHOLD_MB:.0f} MB); stopped scheduling"
            f" after {delivered} of {total} repos"
        )
        return True, None
    _tag, scan, failure = message
    if failure is not None:
        failures.append(failure)
    return False, scan


def _run_git_detection_processes(
    engine: Engine,
    run_id: int,
    spec: DetectOptions,
    pack: Pack,
    cfg: GitScanConfig,
    scan_root: Path,
    run_dir: Path,
    candidates: list[dict],
    total: int,
    warnings: list[str],
    admission_probe: Callable[[str], RemoteRefs] = remote_refs_for,
    finalize: Callable[[_RepoScan], None] | None = None,
    progress_offset: int = 0,
) -> tuple[list[_RetainedScan], list[str], bool, bool]:
    processes = max(2, cfg.processes)
    threads = max(1, cfg.workers // processes)
    contain_process_tree()
    mp_context = multiprocessing.get_context("spawn")
    out_queue = mp_context.Queue()
    cancel_event = mp_context.Event()
    breaker_values = (
        mp_context.Value("d", 0.0),
        mp_context.Value("d", 0.0),
        mp_context.Value("d", 0.0),
    )
    pr_gate = mp_context.BoundedSemaphore(max(1, cfg.pr_gate_permits))
    slices = [candidates[index::processes] for index in range(processes)]
    workers = []
    try:
        for slice_candidates in slices:
            process = mp_context.Process(
                target=_scan_worker_main,
                args=(
                    slice_candidates,
                    out_queue,
                    cancel_event,
                    cfg,
                    spec,
                    pack,
                    str(run_dir),
                    threads,
                    breaker_values,
                    pr_gate,
                    admission_probe,
                ),
                daemon=True,
            )
            process.start()
            workers.append(process)
    except BaseException:
        for process in workers:
            if process.is_alive():
                _kill_tree(process)
        out_queue.close()
        raise
    retained: dict[int, _RetainedScan] = {}
    delivered = 0
    failures: list[str] = []
    stopped_for_disk = False
    cancelled = False
    deletion_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="detect-rm")
    try:
        while True:
            cancellation.check()
            try:
                message = out_queue.get(timeout=_CANCEL_POLL_SECONDS)
            except queue.Empty:
                if delivered >= total:
                    break
                if all(process.exitcode is not None for process in workers):
                    break
                continue
            stopped, scan = _drain_message(
                message, failures, warnings, scan_root=scan_root, total=total, delivered=delivered
            )
            if stopped:
                stopped_for_disk = True
                continue
            assert scan is not None
            retained[scan.repo_id] = _settle_scan(engine, run_id, scan, pack, finalize, failures)
            delivered += 1
            deferred_transient = (
                message[2] is None and scan.document.get("failure_class") == "transient"
            )
            if not cfg.keep and not deferred_transient:
                deletion_pool.submit(_remove_tree, run_dir / scan.full_name.replace("/", "__"))
            progress.report("detecting", progress_offset + delivered, progress_offset + total)
        while True:
            try:
                message = out_queue.get_nowait()
            except queue.Empty:
                break
            stopped, scan = _drain_message(
                message, failures, warnings, scan_root=scan_root, total=total, delivered=delivered
            )
            if stopped:
                stopped_for_disk = True
                continue
            if scan is not None:
                retained[scan.repo_id] = _settle_scan(
                    engine, run_id, scan, pack, finalize, failures
                )
                delivered += 1
    except RunCancelled:
        cancelled = True
        cancel_event.set()
        deadline = time.monotonic() + 10.0
        for process in workers:
            process.join(timeout=max(0.1, deadline - time.monotonic()))
        for process in workers:
            if process.is_alive():
                _kill_tree(process)
        raise
    finally:
        if not cancelled:
            deletion_pool.shutdown(wait=True)
            for process in workers:
                process.join(timeout=5)
                if process.is_alive():
                    _kill_tree(process)
            if not cfg.keep:
                _remove_tree(run_dir)
        else:
            deletion_pool.shutdown(wait=False, cancel_futures=True)
        out_queue.close()
    lost = (not cancelled) and delivered < total and not stopped_for_disk
    if lost:
        warnings.append(f"scan workers stopped early: {delivered} of {total} repos scanned")
    records = [retained[key] for key in sorted(retained)]
    return records, failures, stopped_for_disk, lost


def run_git_detection(
    engine: Engine,
    run_id: int,
    spec: DetectOptions,
    pack: Pack,
    *,
    config: GitScanConfig | None = None,
    clone_fn: Callable[[str, Path], None] | None = None,
    repo_factory: Callable[[Path, str], GitRepo] | None = None,
    admission_probe: Callable[[str], RemoteRefs] | None = None,
    pr_deps: Sequence[Deps] = (),
    pr_fetch: PrFetch | None = None,
) -> RunPayload:
    """Scan lean clones; with ``spec.source == "hybrid"`` also fetch PR metadata.

    Hybrid mode runs :class:`PrSidecar` in this (parent) process beside the
    clone workers, using ``pr_deps`` (or the injected ``pr_fetch``), and merges
    each repository's PR descriptions, authors, head branches, labels and
    dates into its scan before it is persisted.

    Each fetch costs one GraphQL point, so one token covers ~5,000 repos/hour;
    requests rotate over every supplied token so the sidecar keeps pace with
    the clone fleet instead of becoming the bottleneck.
    """
    cfg = config or GitScanConfig()
    hybrid = spec.source == HYBRID_SOURCE
    ledger = audit.PointsLedger()
    sidecar: PrSidecar | None = None
    if hybrid:
        fetch = pr_fetch
        workers = _PR_WORKERS_PER_TOKEN
        if fetch is None:
            if not pr_deps:
                raise ValueError("hybrid detection needs API credentials for PR metadata")
            identities = [
                (deps, _audit_hook(deps, run_id, ledger, "detect:pr-metadata")) for deps in pr_deps
            ]
            rotation = itertools.cycle(identities)
            rotation_lock = threading.Lock()
            pr_limit = _pr_window(spec)
            workers = min(_PR_MAX_WORKERS, _PR_WORKERS_PER_TOKEN * len(identities))

            def fetch(full_name: str) -> ChannelResult:
                with rotation_lock:
                    api_deps, on_response = next(rotation)
                return detect_pr_metadata(
                    api_deps,
                    full_name,
                    pack,
                    limit=pr_limit,
                    agents=spec.agents,
                    on_response=on_response,
                )

        sidecar = PrSidecar(fetch, workers=workers)

    def finalize(scan: _RepoScan) -> None:
        if sidecar is None:
            return
        if scan.document.get("unavailable") and not scan.results:
            sidecar.discard(scan.full_name)
            return
        merge_pr_metadata(scan, sidecar.result(scan.full_name), spec.channels)

    scan_root = Path(os.path.abspath(cfg.scan_root))
    clone_one = clone_fn or (
        lambda full_name, dest: clone_lean(full_name, dest, depth=cfg.depth, timeout=cfg.timeout)
    )
    make_repo = repo_factory or (
        lambda dest, full_name: GitRepo(dest, timeout=cfg.timeout, full_name=full_name)
    )
    active = frozenset(channel for channel in spec.channels if channel in LOCAL_CHANNELS)
    served = set(LOCAL_CHANNELS) | (set(SIDECAR_CHANNELS) if hybrid else set())
    skipped = sorted(channel for channel in spec.channels if channel not in served)
    selected = [dict(row) for row in _candidates(engine, spec.source_run_id, spec.limit)]
    # A resumed run keeps every repository it already finished cleanly and
    # scans only the rest; a fresh run has no checkpoints, so this is a no-op.
    finished = _load_finished(engine, run_id, {int(row["repo_id"]) for row in selected})
    candidates = [row for row in selected if int(row["repo_id"]) not in finished]
    resumed = len(finished)
    total = len(candidates)
    if resumed:
        progress.report("detecting", resumed, resumed + total)
    if sidecar is not None:
        sidecar.prefetch(str(candidate["full_name"]) for candidate in candidates)
    run_dir = scan_root / f"detect-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    failures: list[str] = []
    stopped_for_disk = False
    worker_lost = False

    sidecar_cancelled = False
    try:
        use_processes = (
            cfg.processes > 1 and clone_fn is None and repo_factory is None and os.name == "nt"
        )
        if use_processes:
            records, failures, stopped_for_disk, worker_lost = _run_git_detection_processes(
                engine,
                run_id,
                spec,
                pack,
                cfg,
                scan_root,
                run_dir,
                candidates,
                total,
                warnings,
                remote_refs_for if admission_probe is None else admission_probe,
                finalize,
                resumed,
            )
            cancelled = False
        else:
            breaker = CircuitBreaker(*local_values())
            records_by_repo: dict[int, _RetainedScan] = {}
            cancelled = False
            deletion_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="detect-rm")

            def scan_repo(candidate: Mapping) -> _RepoScan:
                return _scan_one(
                    run_dir,
                    cfg,
                    spec,
                    pack,
                    active,
                    candidate,
                    clone_one=clone_one,
                    make_repo=make_repo,
                    pr_gate=None,
                )

            try:
                max_workers = max(1, cfg.workers)
                pool = ThreadPoolExecutor(max_workers=max_workers)
                try:
                    pending = iter(candidates)
                    retry_candidates: list[Mapping] = []
                    wave = 1
                    in_flight: dict[Future, Mapping] = {}
                    exhausted = False
                    done = 0
                    while True:
                        while not exhausted and len(in_flight) < max_workers:
                            cancellation.check()
                            breaker.wait_if_open()
                            free = free_disk_mb(scan_root)
                            if free < LOW_DISK_THRESHOLD_MB:
                                stopped_for_disk = True
                                exhausted = True
                                warnings.append(
                                    f"low disk: only {free:.0f} MB free under"
                                    f" {str(scan_root)!r} (reserve {LOW_DISK_THRESHOLD_MB:.0f} MB);"
                                    f" stopped scheduling after {done} of {total} repos"
                                )
                                break
                            candidate = next(pending, None)
                            if candidate is None:
                                if wave == 1 and retry_candidates:
                                    wave = 2
                                    pending = iter(retry_candidates)
                                    retry_candidates = []
                                    continue
                                exhausted = True
                                break
                            context = contextvars.copy_context()
                            future = pool.submit(context.run, scan_repo, candidate)
                            in_flight[future] = candidate
                        if not in_flight:
                            break
                        ready, _ = wait(
                            in_flight, timeout=_CANCEL_POLL_SECONDS, return_when=FIRST_COMPLETED
                        )
                        if not ready:
                            cancellation.check()
                            continue
                        future = next(iter(ready))
                        cancellation.check()
                        candidate = in_flight.pop(future)
                        deferred = False
                        try:
                            scan = future.result()
                        except RunCancelled:
                            raise
                        except Exception as exc:
                            failure_class = classify_git_failure(exc)
                            deferred = False
                            if failure_class == "transient":
                                breaker.record_failure()
                                if wave == 1:
                                    retry_candidates.append(candidate)
                                    deferred = True
                            scan = _failed_scan(candidate, exc, failure_class=failure_class)
                            if not deferred:
                                failures.append(f"{scan.full_name}: {scan.document['notes'][0]}")
                        else:
                            breaker.record_success()
                        records_by_repo[scan.repo_id] = _settle_scan(
                            engine, run_id, scan, pack, finalize, failures
                        )
                        if not cfg.keep and not deferred:
                            deletion_pool.submit(
                                _remove_tree, run_dir / scan.full_name.replace("/", "__")
                            )
                        done += 1
                        progress.report("detecting", resumed + done, resumed + total)
                except RunCancelled:
                    cancelled = True
                    raise
                finally:
                    pool.shutdown(wait=not cancelled, cancel_futures=True)
            finally:
                deletion_pool.shutdown(wait=not cancelled, cancel_futures=True)
                # On a stop, skip the sweep so the status flips immediately; the
                # leftovers are reclaimed by the console's flush action or the resume.
                if not cfg.keep and not cancelled:
                    _remove_tree(run_dir)
            records = [records_by_repo[key] for key in sorted(records_by_repo)]
    except RunCancelled:
        sidecar_cancelled = True
        raise
    finally:
        if sidecar is not None:
            sidecar.close(cancelled=sidecar_cancelled)

    records = sorted([*finished.values(), *records], key=lambda record: record.repo_id)
    partial = (
        stopped_for_disk
        or worker_lost
        or bool(failures)
        or any(record.partial for record in records)
    )
    items = [
        RunPayloadItem(
            repo_id=record.repo_id,
            full_name=record.full_name,
            stargazers=record.stargazers,
            repo_created_at=(
                record.repo_created_at.isoformat() if record.repo_created_at is not None else None
            ),
            commit_count=record.commit_count,
            pushed_at=record.pushed_at.isoformat() if record.pushed_at is not None else None,
            archived=record.archived,
            language=record.language,
            license_spdx=record.license_spdx,
            country_iso=record.country_iso,
            geo_confidence=record.geo_confidence,
            virtuals=record.virtuals,
            detection=record.document,
        )
        for record in records
    ]
    summary = _fold_summary([record.contribution for record in records], spec, pack, len(records))
    summary["source"] = HYBRID_SOURCE if hybrid else "git"
    summary["skipped_channels"] = skipped
    unavailable = sorted(
        (
            {
                "full_name": record.full_name,
                "reason": record.document.get("failure_class") or "channel_unavailable",
            }
            for record in records
            if record.document.get("unavailable")
        ),
        key=lambda row: row["full_name"],
    )
    reasons: dict[str, int] = {}
    for entry in unavailable:
        reasons[entry["reason"]] = reasons.get(entry["reason"], 0) + 1
    summary["unavailable_repos"] = unavailable
    summary["unavailable_reasons"] = dict(sorted(reasons.items()))
    warnings.extend(failures)
    if skipped:
        warnings.append(f"local scan skipped API-only channels: {', '.join(skipped)}")
    field_stats: dict[str, object] = {
        "clone": {
            "depth": cfg.depth,
            "keep": cfg.keep,
            "scanned": len(records),
            "resumed": resumed,
            "failures": len(failures),
        },
        "walk": repo_walk.verification_summary(),
    }
    if sidecar is not None:
        pr_api = sidecar.stats()
        summary["pr_api"] = pr_api
        field_stats["pr_api"] = {**pr_api, "points": ledger.as_dict()}
        if sidecar.tripped_note is not None:
            warnings.append(sidecar.tripped_note)
            partial = True
    return RunPayload(
        total_count=resumed + total,
        items=items,
        incomplete=partial,
        fetched=resumed + total,
        warnings=warnings,
        result_summary=summary,
        detections_source=lambda: stream_detections(engine, run_id),
        field_stats=field_stats,
    )
