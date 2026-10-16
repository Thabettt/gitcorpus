from __future__ import annotations

import contextvars
import json
import shutil
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import insert
from sqlalchemy.engine import Engine

from detect.attribution import dedupe_hits
from detect.channels import ChannelResult
from detect.gitio import GitRepo, clone_lean
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
from enrich.cloner import LOW_DISK_THRESHOLD_MB, free_disk_mb
from lib import cancellation, progress
from lib.cancellation import RunCancelled
from serve.executor import RunPayload, RunPayloadItem
from store.models import DetectionEvidence

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
_CANCEL_POLL_SECONDS = 1.0


@dataclass(frozen=True)
class GitScanConfig:
    depth: int = 100
    keep: bool = False
    scan_root: str = "clones"
    timeout: float | None = None
    workers: int = 16


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
    free = free_disk_mb(cfg.scan_root)
    if free < LOW_DISK_THRESHOLD_MB:
        raise RuntimeError(
            f"low disk: {free:.0f} MB free under {cfg.scan_root!r};"
            f" reserve {LOW_DISK_THRESHOLD_MB:.0f} MB before a local scan"
        )
    clone_one = clone_fn or (
        lambda full_name, dest: clone_lean(full_name, dest, depth=cfg.depth, timeout=cfg.timeout)
    )
    make_repo = repo_factory or (lambda dest: GitRepo(dest, timeout=cfg.timeout))
    active = frozenset(channel for channel in spec.channels if channel in LOCAL_CHANNELS)
    skipped = sorted(channel for channel in spec.channels if channel not in LOCAL_CHANNELS)
    candidates = _candidates(engine, spec.source_run_id, spec.limit)
    total = len(candidates)
    run_dir = Path(cfg.scan_root) / f"detect-{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    scans: list[_RepoScan] = []
    failures: list[str] = []

    def scan_repo(candidate: Mapping) -> _RepoScan:
        full_name = str(candidate["full_name"])
        dest = run_dir / full_name.replace("/", "__")
        shutil.rmtree(dest, ignore_errors=True)
        clone_one(full_name, dest)
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
            pr_result = detect_pr_commits_local(repo, pack, spec.agents, depth=cfg.depth)
            results["pr_metadata"] = pr_result
        if "branch" in active:
            results["branch"] = detect_branch_local(repo, pack, spec.agents, limit=cfg.depth)
        hits = dedupe_hits([hit for result in results.values() for hit in result.hits])
        return _RepoScan(
            repo_id=int(candidate["repo_id"]),
            full_name=full_name,
            stargazers=candidate["stargazers"],
            hits=hits,
            results=results,
            pr_result=pr_result,
            history_stats=history_stats,
        )

    try:
        max_workers = max(1, cfg.workers)
        pool = ThreadPoolExecutor(max_workers=max_workers)
        cancelled = False
        try:
            pending = iter(candidates)
            in_flight: dict[Future, Mapping] = {}
            exhausted = False
            done = 0
            while True:
                while not exhausted and len(in_flight) < max_workers:
                    cancellation.check()
                    candidate = next(pending, None)
                    if candidate is None:
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
                    scan.document = _repo_document(scan)
                except RunCancelled:
                    raise
                except Exception as exc:
                    scan = _failed_scan(candidate, exc)
                    failures.append(f"{scan.full_name}: {scan.document['notes'][0]}")
                scans.append(scan)
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
                if rows:
                    with engine.begin() as connection:
                        connection.execute(insert(DetectionEvidence), rows)
                if not cfg.keep:
                    shutil.rmtree(run_dir / scan.full_name.replace("/", "__"), ignore_errors=True)
                done += 1
                progress.report("detecting", done, total)
        except RunCancelled:
            cancelled = True
            raise
        finally:
            pool.shutdown(wait=not cancelled, cancel_futures=True)
    finally:
        if not cfg.keep:
            shutil.rmtree(run_dir, ignore_errors=True)

    partial = bool(failures) or any(
        result.status in ("partial", "unavailable")
        for scan in scans
        for result in scan.results.values()
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
    warnings = list(failures)
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
