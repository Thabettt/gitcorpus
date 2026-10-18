from __future__ import annotations

import contextvars
from collections.abc import Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field

import httpx
from sqlalchemy import insert, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from detect.attribution import Hit, adoption_level, dedupe_hits
from detect.channels import ChannelResult, detect_files, detect_history, detect_issues, detect_prs
from detect.packs import Pack
from discover.pipeline import Deps
from lib import audit, cancellation, progress
from lib.cancellation import RunCancelled
from lib.deadlines import Deadline, request_deadline_seconds
from serve.executor import RunPayload, RunPayloadItem
from store.models import DetectionEvidence, DetectionRepoFilter, Repo, RunItem

CHANNELS = ("file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata", "issue")
_HISTORY_KEYS = ("author", "commit_trailer", "bot")
_PR_KEYS = ("branch", "label", "pr_metadata")
_BOT_CHANNEL = "bot"
_FAILURE_NOTE_LIMIT = 300
_CANCEL_POLL_SECONDS = 0.25


@dataclass(frozen=True)
class DetectOptions:
    source_run_id: int
    pack_version: str
    agents: frozenset[str] | None
    channels: frozenset[str]
    limit: int | None = None
    windows: Mapping[str, int] = field(
        default_factory=lambda: {"commits": 100, "prs": 100, "issues": 100}
    )
    source: str = "api"
    clone_depth: int = 100
    clone_keep: bool = False


@dataclass(frozen=True)
class DetectConfig:
    deadline_seconds: float | None = None
    concurrency: int = 10


@dataclass
class _RepoScan:
    repo_id: int
    full_name: str
    stargazers: int | None
    hits: list[Hit]
    results: dict[str, ChannelResult]
    pr_result: ChannelResult | None
    history_stats: Mapping[str, object]
    document: dict = field(default_factory=dict)


def _audit_hook(deps: Deps, run_id: int, ledger: audit.PointsLedger, phase: str):
    def hook(response: httpx.Response, latency_ms: float) -> None:
        record = audit.record_from_response(
            {}, response, token_fp=deps.token_fp, latency_ms=latency_ms, run_id=run_id, phase=phase
        )
        ledger.add(phase, audit.cached_json(response))
        if deps.audit_buffer is not None:
            deps.audit_buffer.add(record)
        else:
            audit.record_audit(deps.engine, record)

    return hook


def _candidates(engine: Engine, source_run_id: int, limit: int | None) -> list[Mapping]:
    statement = (
        select(RunItem.repo_id, RunItem.full_name, RunItem.stargazers, Repo.default_branch)
        .join(Repo, Repo.id == RunItem.repo_id, isouter=True)
        .where(RunItem.run_id == source_run_id)
        .order_by(RunItem.stargazers.desc().nullslast(), RunItem.repo_id)
    )
    if limit is not None:
        statement = statement.limit(limit)
    with engine.connect() as connection:
        return list(connection.execute(statement).mappings())


def _scan_repo(
    deps: Deps,
    pack: Pack,
    options: DetectOptions,
    run_id: int,
    ledger: audit.PointsLedger,
    candidate: Mapping,
) -> _RepoScan:
    full_name = str(candidate["full_name"])
    ref = candidate["default_branch"]
    channels = options.channels
    results: dict[str, ChannelResult] = {}
    history_stats: Mapping[str, object] = {}
    if "file" in channels:
        results["file"] = detect_files(
            deps,
            full_name,
            pack,
            ref=ref,
            agents=options.agents,
            on_response=_audit_hook(deps, run_id, ledger, "detect:file"),
        )
    if set(_HISTORY_KEYS) & channels:
        history = detect_history(
            deps,
            full_name,
            pack,
            limit=options.windows.get("commits", 100),
            agents=options.agents,
            on_response=_audit_hook(deps, run_id, ledger, "detect:history"),
        )
        for key in _HISTORY_KEYS:
            if key in channels:
                results[key] = history[key]
        history_stats = history["author"].stats
    pr_result: ChannelResult | None = None
    if set(_PR_KEYS) & channels:
        pr_result = detect_prs(
            deps,
            full_name,
            pack,
            limit=options.windows.get("prs", 100),
            agents=options.agents,
            channels=channels,
            on_response=_audit_hook(deps, run_id, ledger, "detect:prs"),
        )
        for key in _PR_KEYS:
            if key in channels:
                results[key] = pr_result
    if "issue" in channels:
        extra = tuple(pr_result.stats.get("commenter_entries", ())) if pr_result is not None else ()
        results["issue"] = detect_issues(
            deps,
            full_name,
            pack,
            limit=options.windows.get("issues", 100),
            agents=options.agents,
            extra_entries=extra,
            on_response=_audit_hook(deps, run_id, ledger, "detect:issues"),
        )
    hits: list[Hit] = []
    for result in results.values():
        hits.extend(result.hits)
    return _RepoScan(
        repo_id=int(candidate["repo_id"]),
        full_name=full_name,
        stargazers=candidate["stargazers"],
        hits=dedupe_hits(hits),
        results=results,
        pr_result=pr_result,
        history_stats=history_stats,
    )


def _failed_scan(
    candidate: Mapping, exc: Exception, *, failure_class: str | None = None
) -> _RepoScan:
    note = f"{type(exc).__name__}: {exc}"
    if len(note) > _FAILURE_NOTE_LIMIT:
        note = note[:_FAILURE_NOTE_LIMIT]
    return _RepoScan(
        repo_id=int(candidate["repo_id"]),
        full_name=str(candidate["full_name"]),
        stargazers=candidate["stargazers"],
        hits=[],
        results={},
        pr_result=None,
        history_stats={},
        document={
            "agents": [],
            "channels": {},
            "unavailable": True,
            "failure_class": failure_class,
            "first_signal_at": None,
            "commit_ratio": None,
            "adoption_level": "none",
            "notes": [note],
        },
    )


def _ratio_sets(scan: _RepoScan) -> tuple[set[str], set[str]]:
    ai = {str(oid) for oid in scan.history_stats.get("ai_oids", ())}
    human = {str(oid) for oid in scan.history_stats.get("human_oids", ())}
    if scan.pr_result is not None:
        propagated = {str(oid) for oid in scan.pr_result.stats.get("propagated_oids", ())}
        propagated_in_window = propagated & human
        ai |= propagated_in_window
        human -= propagated_in_window
    return ai, human


def _first_signal_at(scan: _RepoScan) -> str | None:
    dates: list[str] = []
    committed = scan.history_stats.get("committed_at") or {}
    for hit in scan.hits:
        oid = hit.evidence.get("commit")
        if oid is not None and oid in committed:
            dates.append(str(committed[oid]))
    if scan.pr_result is not None:
        created = scan.pr_result.stats.get("created_at") or {}
        for hit in scan.hits:
            number = hit.evidence.get("pr")
            if number is not None and number in created:
                dates.append(str(created[number]))
    return min(dates) if dates else None


def _repo_document(scan: _RepoScan) -> dict:
    ai, human = _ratio_sets(scan)
    ratio = len(ai) / (len(ai) + len(human)) if (ai or human) else None
    notes = [
        f"{key}: {result.note}"
        for key, result in scan.results.items()
        if result.note and result.status != "ok"
    ]
    return {
        "agents": sorted({hit.agent for hit in scan.hits if hit.channel != _BOT_CHANNEL}),
        "channels": {key: result.status for key, result in scan.results.items()},
        "unavailable": any(result.status == "unavailable" for result in scan.results.values()),
        "first_signal_at": _first_signal_at(scan),
        "commit_ratio": round(ratio, 4) if ratio is not None else None,
        "adoption_level": adoption_level(ratio),
        "notes": notes,
    }


@dataclass(frozen=True)
class _SummaryContribution:
    unavailable: bool
    has_signal: bool
    agent_counts: Mapping[str, int]
    channel_counts: Mapping[str, int]
    partials: Mapping[str, str]
    ai_count: int
    human_count: int
    first_signal_at: str | None


def _scan_contribution(scan: _RepoScan) -> _SummaryContribution:
    agent_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    for hit in scan.hits:
        if hit.channel == _BOT_CHANNEL:
            continue
        agent_counts[hit.agent] = agent_counts.get(hit.agent, 0) + 1
        channel_counts[hit.channel] = channel_counts.get(hit.channel, 0) + 1
    partials: dict[str, str] = {}
    for key, result in scan.results.items():
        if result.status == "partial" and result.note:
            partials.setdefault(key, result.note)
    ai, human = _ratio_sets(scan)
    document = scan.document
    return _SummaryContribution(
        unavailable=bool(document["unavailable"]),
        has_signal=bool(document["agents"]),
        agent_counts=agent_counts,
        channel_counts=channel_counts,
        partials=partials,
        ai_count=len(ai),
        human_count=len(human),
        first_signal_at=document["first_signal_at"],
    )


def _fold_summary(
    contributions: list[_SummaryContribution], spec: DetectOptions, pack: Pack, scanned: int
) -> dict:
    agent_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    partials: dict[str, str] = {}
    firsts: list[str] = []
    repos_with_signal = 0
    unavailable = 0
    ai_total = 0
    human_total = 0
    for contribution in contributions:
        if contribution.unavailable:
            unavailable += 1
        if contribution.has_signal:
            repos_with_signal += 1
        for agent, count in contribution.agent_counts.items():
            agent_counts[agent] = agent_counts.get(agent, 0) + count
        for channel, count in contribution.channel_counts.items():
            channel_counts[channel] = channel_counts.get(channel, 0) + count
        for key, note in contribution.partials.items():
            partials.setdefault(key, note)
        ai_total += contribution.ai_count
        human_total += contribution.human_count
        if contribution.first_signal_at:
            firsts.append(contribution.first_signal_at)
    ratio = ai_total / (ai_total + human_total) if (ai_total + human_total) else None
    return {
        "repos_scanned": scanned,
        "repos_with_signal": repos_with_signal,
        "repos_unavailable": unavailable,
        "agents": dict(sorted(agent_counts.items())),
        "channels": dict(sorted(channel_counts.items())),
        "pack_version": pack.version,
        "agents_selected": sorted(spec.agents) if spec.agents is not None else "all",
        "windows": dict(spec.windows),
        "commit_ratio": round(ratio, 4) if ratio is not None else None,
        "adoption_level": adoption_level(ratio),
        "first_signal_at": min(firsts) if firsts else None,
        "partial_channels": partials,
    }


def _summary(scans: list[_RepoScan], spec: DetectOptions, pack: Pack) -> dict:
    contributions = [_scan_contribution(scan) for scan in scans]
    return _fold_summary(contributions, spec, pack, len(scans))


def stream_detections(engine: Engine, run_id: int):
    statement = text(
        "SELECT i.full_name, e.repo_id, e.agent, e.channel, e.evidence, e.pack_version,"
        " e.run_id, e.detected_at"
        " FROM detection_evidence e JOIN run_items i"
        " ON i.run_id = e.run_id AND i.repo_id = e.repo_id"
        " WHERE e.run_id = :run ORDER BY e.repo_id, e.agent, e.channel, e.id"
    )
    with engine.connect() as connection:
        rows = connection.execution_options(stream_results=True).execute(statement, {"run": run_id})
        for row in rows:
            yield {
                "full_name": row[0],
                "repo_id": row[1],
                "agent": row[2],
                "channel": row[3],
                "evidence": row[4],
                "pack_version": row[5],
                "run_id": row[6],
                "detected_at": row[7],
            }


def run_detection(
    deps: Deps,
    run_id: int,
    spec: DetectOptions,
    pack: Pack,
    *,
    config: DetectConfig | None = None,
) -> RunPayload:
    cfg = config or DetectConfig()
    if deps.limiter is not None:
        seconds = (
            cfg.deadline_seconds if cfg.deadline_seconds is not None else request_deadline_seconds()
        )
        deps.limiter.bind_deadline(Deadline(seconds))
    ledger = audit.PointsLedger()
    candidates = _candidates(deps.engine, spec.source_run_id, spec.limit)
    total = len(candidates)
    scans: list[_RepoScan] = []
    failures: list[str] = []
    try:
        max_workers = max(1, cfg.concurrency)
        pool = ThreadPoolExecutor(max_workers=max_workers)
        cancelled = False
        try:
            pending = iter(candidates)
            in_flight: dict[Future, Mapping] = {}
            exhausted = False
            done = 0
            progress.report("detecting", 0, total)
            while True:
                while not exhausted and len(in_flight) < max_workers:
                    cancellation.check()
                    candidate = next(pending, None)
                    if candidate is None:
                        exhausted = True
                        break
                    context = contextvars.copy_context()
                    future = pool.submit(
                        context.run, _scan_repo, deps, pack, spec, run_id, ledger, candidate
                    )
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
                synthetic: _RepoScan | None = None
                try:
                    scan = future.result()
                    scan.document = _repo_document(scan)
                except RunCancelled:
                    raise
                except Exception as exc:
                    scan = _failed_scan(candidate, exc)
                    synthetic = scan
                scans.append(scan)
                if synthetic is not None:
                    failures.append(f"{scan.full_name}: {scan.document['notes'][0]}")
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
                facets = sorted({(hit.agent, hit.channel) for hit in scan.hits})
                with deps.engine.begin() as connection:
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
                done += 1
                progress.report("detecting", done, total)
        except RunCancelled:
            cancelled = True
            raise
        finally:
            pool.shutdown(wait=not cancelled, cancel_futures=True)
    finally:
        if deps.limiter is not None:
            deps.limiter.bind_deadline(None)
        if deps.audit_buffer is not None:
            deps.audit_buffer.flush()
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
    return RunPayload(
        total_count=total,
        items=items,
        incomplete=partial,
        fetched=total,
        warnings=failures,
        result_summary=_summary(scans, spec, pack),
        detections_source=lambda: stream_detections(deps.engine, run_id),
        field_stats={"points": ledger.as_dict()},
    )
