from __future__ import annotations

import contextlib
import contextvars
import json
import multiprocessing
import os
import queue
import shutil
import subprocess
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from detect.attribution import dedupe_hits
from detect.breaker import CircuitBreaker, local_values
from detect.channels import ChannelResult
from detect.gitio import GitRepo, classify_git_failure, clone_lean, retry_call
from detect.local_channels import (
    detect_branch_local,
    detect_files_local,
    detect_history_local,
    detect_pr_commits_local,
)
from detect.orchestrator import (
    DetectOptions,
    _candidates,
    _failed_scan,
    _repo_document,
    _RepoScan,  # same-package helper reuse, intentional
    _summary,
)
from detect.packs import Pack
from enrich.cloner import LOW_DISK_THRESHOLD_MB, MARKER_NAME, free_disk_mb
from lib import cancellation, progress
from lib.cancellation import RunCancelled
from serve.executor import RunPayload, RunPayloadItem
from store.models import DetectionEvidence, RunItem

LOCAL_CHANNELS = (
    "file",
    "author",
    "branch",
    "bot",
    "commit_trailer",
    "pr_metadata",
)
API_ONLY_CHANNELS = ("label", "issue")
_HISTORY_KEYS = ("author", "commit_trailer", "bot")
_CANCEL_POLL_SECONDS = 0.25
_LOW_DISK_MARKER = "low_disk"


@dataclass(frozen=True)
class GitScanConfig:
    depth: int = 100
    keep: bool = False
    scan_root: str = "clones"
    timeout: float | None = None
    workers: int = 16
    attempts: int = 4
    retry_delay: float = 1.0
    walk_workers: int = 8
    processes: int = 0


def _spawn_rmdir(path: Path) -> None:
    # Deletion walks thousands of files; pushing that work into a child
    # process keeps the CPU off the caller's thread (and off its GIL).
    if os.name != "nt":
        shutil.rmtree(path, ignore_errors=True)
        return
    with contextlib.suppress(OSError, subprocess.TimeoutExpired):
        subprocess.run(
            ["cmd", "/c", "rmdir", "/s", "/q", str(path)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=300,
            check=False,
        )


def _remove_tree(path: Path) -> None:
    for delay in (0.0, 0.2, 1.0):
        if delay:
            time.sleep(delay)
        _spawn_rmdir(path)
        if not path.exists():
            return
    for delay in (0.0, 0.5):
        if delay:
            time.sleep(delay)
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            return


def _scan_one(
    run_dir: Path,
    cfg: GitScanConfig,
    spec: DetectOptions,
    pack: Pack,
    active: frozenset[str],
    candidate: Mapping,
    *,
    clone_one: Callable[[str, Path], None],
    make_repo: Callable[[Path], GitRepo],
    walk_pool: ThreadPoolExecutor | None,
) -> _RepoScan:
    full_name = str(candidate["full_name"])
    dest = run_dir / full_name.replace("/", "__")
    if not (cfg.keep and (dest / MARKER_NAME).exists()):

        def clone_attempt() -> None:
            shutil.rmtree(dest, ignore_errors=True)
            clone_one(full_name, dest)
            (dest / MARKER_NAME).write_text("", encoding="utf-8")

        retry_call(
            clone_attempt,
            attempts=cfg.attempts,
            base_delay=cfg.retry_delay,
            retryable=lambda exc: classify_git_failure(exc) != "dead",
        )
    repo = make_repo(dest)
    results: dict[str, ChannelResult] = {}
    history_stats: Mapping[str, object] = {}
    if "file" in active:
        results["file"] = detect_files_local(repo, pack, spec.agents)
    if set(_HISTORY_KEYS) & active:
        history = detect_history_local(repo, pack, spec.agents, limit=cfg.depth)
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
            walk_workers=cfg.walk_workers,
            walk_pool=walk_pool,
        )
        results["pr_metadata"] = pr_result
    if "branch" in active:
        results["branch"] = detect_branch_local(repo, pack, spec.agents, limit=cfg.depth)
    hits = dedupe_hits([hit for result in results.values() for hit in result.hits])
    scan = _RepoScan(
        repo_id=int(candidate["repo_id"]),
        full_name=full_name,
        stargazers=candidate["stargazers"],
        hits=hits,
        results=results,
        pr_result=pr_result,
        history_stats=history_stats,
    )
    scan.document = _repo_document(scan)
    return scan


def _persist_scan(engine: Engine, run_id: int, scan: _RepoScan, pack: Pack) -> None:
    rows = [
        {
            "run_id": run_id,
            "repo_id": scan.repo_id,
            "agent": hit.agent,
            "channel": hit.channel,
            "evidence": hit.evidence,
            "pack_version": pack.version,
        }
        for hit in scan.hits
    ]
    with engine.begin() as connection:
        if rows:
            connection.execute(insert(DetectionEvidence), rows)
        connection.execute(
            pg_insert(RunItem)
            .values(
                run_id=run_id,
                repo_id=scan.repo_id,
                full_name=scan.full_name,
                stargazers=scan.stargazers,
                detection=scan.document,
            )
            .on_conflict_do_update(
                index_elements=["run_id", "repo_id"],
                set_={
                    "full_name": scan.full_name,
                    "stargazers": scan.stargazers,
                    "detection": scan.document,
                },
            )
        )


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
) -> None:
    cancellation.bind(cancel_event.is_set)
    run_dir = Path(run_dir_str)
    active = frozenset(channel for channel in spec.channels if channel in LOCAL_CHANNELS)
    clone_one = lambda full_name, dest: clone_lean(  # noqa: E731
        full_name, dest, depth=cfg.depth, timeout=cfg.timeout
    )
    make_repo = lambda dest: GitRepo(dest, timeout=cfg.timeout)  # noqa: E731
    breaker = CircuitBreaker(*breaker_values)
    walk_pool = ThreadPoolExecutor(max_workers=max(1, cfg.walk_workers))
    pool = ThreadPoolExecutor(max_workers=max(1, threads))
    try:
        pending = iter(slice_candidates)
        retry_candidates: list[Mapping] = []
        wave = 1
        in_flight: dict[Future, Mapping] = {}
        exhausted = False
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
                future = pool.submit(
                    context.run,
                    _scan_one,
                    run_dir,
                    cfg,
                    spec,
                    pack,
                    active,
                    candidate,
                    clone_one=clone_one,
                    make_repo=make_repo,
                    walk_pool=walk_pool,
                )
                in_flight[future] = candidate
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
                    failure = f"{scan.full_name}: {scan.document['notes'][0]}"
            else:
                breaker.record_success()
            if not cfg.keep:
                _remove_tree(run_dir / scan.full_name.replace("/", "__"))
            out_queue.put(("scan", scan, failure))
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        walk_pool.shutdown(wait=False, cancel_futures=True)


def _drain_message(
    message,
    scans: list[_RepoScan],
    failures: list[str],
    warnings: list[str],
    *,
    scan_root: Path,
    total: int,
) -> bool:
    """Handle one worker message; returns True when it was a low-disk notice."""
    if isinstance(message, tuple) and message and message[0] == _LOW_DISK_MARKER:
        free = float(message[1])
        warnings.append(
            f"low disk: only {free:.0f} MB free under {str(scan_root)!r}"
            f" (reserve {LOW_DISK_THRESHOLD_MB:.0f} MB); stopped scheduling"
            f" after {len(scans)} of {total} repos"
        )
        return True
    _tag, scan, failure = message
    scans.append(scan)
    if failure is not None:
        failures.append(failure)
    return False


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
) -> tuple[list[_RepoScan], list[str], bool, bool]:
    processes = max(2, cfg.processes)
    threads = max(1, cfg.workers // processes)
    mp_context = multiprocessing.get_context("spawn")
    out_queue = mp_context.Queue()
    cancel_event = mp_context.Event()
    breaker_values = (
        mp_context.Value("d", 0.0),
        mp_context.Value("d", 0.0),
        mp_context.Value("d", 0.0),
    )
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
                ),
                daemon=True,
            )
            process.start()
            workers.append(process)
    except BaseException:
        for process in workers:
            if process.is_alive():
                process.terminate()
        out_queue.close()
        raise
    scans: list[_RepoScan] = []
    failures: list[str] = []
    stopped_for_disk = False
    cancelled = False
    try:
        while True:
            cancellation.check()
            try:
                message = out_queue.get(timeout=_CANCEL_POLL_SECONDS)
            except queue.Empty:
                if len(scans) >= total:
                    break
                if all(process.exitcode is not None for process in workers):
                    break
                continue
            if _drain_message(message, scans, failures, warnings, scan_root=scan_root, total=total):
                stopped_for_disk = True
                continue
            scan = scans[-1]
            _persist_scan(engine, run_id, scan, pack)
            progress.report("detecting", len(scans), total)
        while True:
            try:
                message = out_queue.get_nowait()
            except queue.Empty:
                break
            if _drain_message(message, scans, failures, warnings, scan_root=scan_root, total=total):
                stopped_for_disk = True
    except RunCancelled:
        cancelled = True
        cancel_event.set()
        deadline = time.monotonic() + 10.0
        for process in workers:
            process.join(timeout=max(0.1, deadline - time.monotonic()))
        for process in workers:
            if process.is_alive():
                process.terminate()
        raise
    finally:
        if not cancelled:
            for process in workers:
                process.join(timeout=5)
                if process.is_alive():
                    process.terminate()
        out_queue.close()
    lost = (not cancelled) and len(scans) < total and not stopped_for_disk
    if lost:
        warnings.append(f"scan workers stopped early: {len(scans)} of {total} repos scanned")
    return scans, failures, stopped_for_disk, lost


def run_git_detection(
    engine: Engine,
    run_id: int,
    spec: DetectOptions,
    pack: Pack,
    *,
    config: GitScanConfig | None = None,
    clone_fn: Callable[[str, Path], None] | None = None,
    repo_factory: Callable[[Path], GitRepo] | None = None,
) -> RunPayload:
    cfg = config or GitScanConfig()
    scan_root = Path(os.path.abspath(cfg.scan_root))
    clone_one = clone_fn or (
        lambda full_name, dest: clone_lean(full_name, dest, depth=cfg.depth, timeout=cfg.timeout)
    )
    make_repo = repo_factory or (lambda dest: GitRepo(dest, timeout=cfg.timeout))
    active = frozenset(channel for channel in spec.channels if channel in LOCAL_CHANNELS)
    skipped = sorted(channel for channel in spec.channels if channel not in LOCAL_CHANNELS)
    candidates = [dict(row) for row in _candidates(engine, spec.source_run_id, spec.limit)]
    total = len(candidates)
    run_dir = scan_root / f"detect-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    failures: list[str] = []
    stopped_for_disk = False
    worker_lost = False

    use_processes = (
        cfg.processes > 1 and clone_fn is None and repo_factory is None and os.name == "nt"
    )
    if use_processes:
        scans, failures, stopped_for_disk, worker_lost = _run_git_detection_processes(
            engine, run_id, spec, pack, cfg, scan_root, run_dir, candidates, total, warnings
        )
        cancelled = False
    else:
        breaker = CircuitBreaker(*local_values())
        walk_pool = ThreadPoolExecutor(max_workers=max(1, cfg.walk_workers))
        scans = []
        cancelled = False

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
                walk_pool=walk_pool,
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
                    scans.append(scan)
                    _persist_scan(engine, run_id, scan, pack)
                    if not cfg.keep:
                        _remove_tree(run_dir / scan.full_name.replace("/", "__"))
                    done += 1
                    progress.report("detecting", done, total)
            except RunCancelled:
                cancelled = True
                raise
            finally:
                pool.shutdown(wait=not cancelled, cancel_futures=True)
        finally:
            walk_pool.shutdown(wait=False, cancel_futures=True)
            # On a stop, skip the sweep so the status flips immediately; the
            # leftovers are reclaimed by the console's flush action or the resume.
            if not cfg.keep and not cancelled:
                _remove_tree(run_dir)

    by_repo: dict[int, _RepoScan] = {}
    for scan in scans:
        by_repo[scan.repo_id] = scan
    scans = [by_repo[key] for key in sorted(by_repo)]
    partial = (
        stopped_for_disk
        or worker_lost
        or bool(failures)
        or any(
            result.status in ("partial", "unavailable")
            for scan in scans
            for result in scan.results.values()
        )
    )
    items = [
        RunPayloadItem(
            repo_id=scan.repo_id,
            full_name=scan.full_name,
            stargazers=scan.stargazers,
            detection=scan.document,
        )
        for scan in scans
    ]
    detections = [
        {
            "full_name": scan.full_name,
            "repo_id": scan.repo_id,
            "agent": hit.agent,
            "channel": hit.channel,
            "evidence": json.dumps(hit.evidence, sort_keys=True),
            "pack_version": pack.version,
        }
        for scan in scans
        for hit in scan.hits
    ]
    summary = _summary(scans, spec, pack)
    summary["source"] = "git"
    summary["skipped_channels"] = skipped
    unavailable = sorted(
        (
            {
                "full_name": scan.full_name,
                "reason": scan.document.get("failure_class") or "channel_unavailable",
            }
            for scan in scans
            if scan.document.get("unavailable")
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
    return RunPayload(
        total_count=total,
        items=items,
        incomplete=partial,
        fetched=total,
        warnings=warnings,
        result_summary=summary,
        detections=detections,
        field_stats={
            "clone": {
                "depth": cfg.depth,
                "keep": cfg.keep,
                "scanned": len(scans),
                "failures": len(failures),
            }
        },
    )
