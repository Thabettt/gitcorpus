from __future__ import annotations

import contextvars
import time
from collections.abc import Callable, Mapping
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx
from sqlalchemy import insert, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

from detect.attribution import Hit, adoption_level, dedupe_hits
from detect.channels import (
    ChannelResult,
    FailureKind,
    detect_files,
    detect_history,
    detect_issues,
    detect_prs,
)
from detect.content_attribution import CONTENT_CHANNEL
from detect.packs import GENERIC_AGENT, Pack
from detect.token_pool import (
    FIXED_API_TOKEN_COUNT,
    DetectionTokenPool,
    TokenPoolExhausted,
    TokenPoolRetryExhausted,
)
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

ResponseObserver = Callable[[str, httpx.Response, str], None]
PoolStatsReporter = Callable[[dict[str, object]], None]


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
    pool_stats_reporter: PoolStatsReporter | None = None
    pool_stats_interval: float = 5.0


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
    repo_created_at: datetime | None = None
    commit_count: int | None = None
    pushed_at: datetime | None = None
    archived: bool | None = None
    language: str | None = None
    license_spdx: str | None = None
    country_iso: str | None = None
    geo_confidence: str | None = None
    virtuals: Mapping[str, object] = field(default_factory=dict)


def _audit_hook(
    deps: Deps,
    run_id: int,
    ledger: audit.PointsLedger,
    phase: str,
    observer: ResponseObserver | None = None,
):
    def hook(response: httpx.Response, latency_ms: float) -> None:
        record = audit.record_from_response(
            {}, response, token_fp=deps.token_fp, latency_ms=latency_ms, run_id=run_id, phase=phase
        )
        ledger.add(phase, audit.cached_json(response))
        if observer is not None:
            observer(deps.token_fp, response, phase)
        if deps.audit_buffer is not None:
            deps.audit_buffer.add(record)
        else:
            audit.record_audit(deps.engine, record)

    return hook


def _candidates(engine: Engine, source_run_id: int, limit: int | None) -> list[Mapping]:
    statement = (
        select(
            RunItem.repo_id,
            RunItem.full_name,
            RunItem.stargazers,
            RunItem.repo_created_at,
            RunItem.commit_count,
            RunItem.pushed_at,
            RunItem.archived,
            RunItem.language,
            RunItem.license_spdx,
            RunItem.country_iso,
            RunItem.geo_confidence,
            RunItem.virtuals,
            Repo.default_branch,
        )
        .join(Repo, Repo.id == RunItem.repo_id, isouter=True)
        .where(RunItem.run_id == source_run_id)
        # The corpus is public. A search run with an account's own token can match
        # that account's private repos; keep them out of detection. Rows without a
        # stored repo record are kept and rely on the cross-identity 404 retry.
        .where(or_(Repo.visibility.is_(None), Repo.visibility == "public"))
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
    observer: ResponseObserver | None = None,
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
            on_response=_audit_hook(deps, run_id, ledger, "detect:file", observer),
        )
    if set(_HISTORY_KEYS) & channels:
        history = detect_history(
            deps,
            full_name,
            pack,
            limit=options.windows.get("commits", 100),
            agents=options.agents,
            on_response=_audit_hook(deps, run_id, ledger, "detect:history", observer),
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
            on_response=_audit_hook(deps, run_id, ledger, "detect:prs", observer),
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
            on_response=_audit_hook(deps, run_id, ledger, "detect:issues", observer),
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
        repo_created_at=candidate["repo_created_at"],
        commit_count=candidate["commit_count"],
        pushed_at=candidate["pushed_at"],
        archived=candidate["archived"],
        language=candidate["language"],
        license_spdx=candidate["license_spdx"],
        country_iso=candidate["country_iso"],
        geo_confidence=candidate["geo_confidence"],
        virtuals=candidate["virtuals"] or {},
    )


def _scan_repo_from_pool(
    token_pool: DetectionTokenPool,
    pack: Pack,
    options: DetectOptions,
    run_id: int,
    ledger: audit.PointsLedger,
    candidate: Mapping,
) -> _RepoScan:
    excluded: set[str] = set()
    last_scan: _RepoScan | None = None
    while len(excluded) < FIXED_API_TOKEN_COUNT:
        try:
            lease = token_pool.lease(exclude=frozenset(excluded))
        except TokenPoolRetryExhausted:
            break
        with lease as deps:
            last_scan = _scan_repo(
                deps,
                pack,
                options,
                run_id,
                ledger,
                candidate,
                token_pool.observe,
            )
            if not _retry_on_another_identity(last_scan):
                return last_scan
            excluded.add(deps.token_fp)
            token_pool.raise_if_exhausted()
    if last_scan is None:  # pragma: no cover - the fixed pool always has an initial token
        raise RuntimeError("detection token pool produced no repository scan")
    return last_scan


_IDENTITY_RETRY_KINDS = frozenset({FailureKind.RETRYABLE, FailureKind.NOT_FOUND})


def _retry_on_another_identity(scan: _RepoScan) -> bool:
    # A not-found answer is identity-scoped: a repository one pooled account cannot
    # see may be readable by another, so availability must not depend on the lease.
    return any(result.failure_kind in _IDENTITY_RETRY_KINDS for result in scan.results.values())


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
        repo_created_at=candidate.get("repo_created_at"),
        commit_count=candidate.get("commit_count"),
        pushed_at=candidate.get("pushed_at"),
        archived=candidate.get("archived"),
        language=candidate.get("language"),
        license_spdx=candidate.get("license_spdx"),
        country_iso=candidate.get("country_iso"),
        geo_confidence=candidate.get("geo_confidence"),
        virtuals=candidate.get("virtuals") or {},
        document={
            "agents": [],
            "channels": {},
            "unavailable": True,
            "failure_class": failure_class,
            "first_signal_at": None,
            "oldest_scanned_commit_at": None,
            "total_commits": candidate.get("commit_count"),
            "history_window_commits": None,
            "history_eligible_commits": None,
            "history_coverage": None,
            "history_complete": None,
            "commit_ratio": None,
            "adoption_level": "none",
            "notes": [note],
        },
    )


def _oid_set(value: object) -> set[str]:
    if not isinstance(value, (tuple, list, set, frozenset)):
        return set()
    return {str(oid) for oid in value}


def _object_mapping(value: object) -> Mapping[object, object]:
    return value if isinstance(value, Mapping) else {}


def _ratio_sets(scan: _RepoScan) -> tuple[set[str], set[str]]:
    direct_channels = {"author", "commit_trailer"} & set(scan.results)
    if not direct_channels or any(scan.results[key].status != "ok" for key in direct_channels):
        return set(), set()
    commit_oids = _oid_set(scan.history_stats.get("commit_oids"))
    if commit_oids:
        ai: set[str] = set()
        if "author" in direct_channels:
            ai.update(_oid_set(scan.history_stats.get("author_oids")))
        if "commit_trailer" in direct_channels:
            ai.update(_oid_set(scan.history_stats.get("trailer_oids")))
        human = commit_oids - ai
    elif direct_channels:
        # Compatibility for scans produced by pre-field test doubles.
        ai = _oid_set(scan.history_stats.get("ai_oids"))
        human = _oid_set(scan.history_stats.get("human_oids"))
    else:
        ai, human = set(), set()
    if scan.pr_result is not None:
        propagated = _oid_set(scan.pr_result.stats.get("propagated_oids"))
        propagated_in_window = propagated & human
        ai |= propagated_in_window
        human -= propagated_in_window
    return ai, human


def _instant(value: str) -> datetime:
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _first_signal_at(scan: _RepoScan) -> str | None:
    signal_hits = [hit for hit in scan.hits if hit.channel != _BOT_CHANNEL]
    dates: list[str] = []
    committed = _object_mapping(scan.history_stats.get("committed_at"))
    for hit in signal_hits:
        oid = hit.evidence.get("commit")
        if oid is not None and oid in committed:
            dates.append(str(committed[oid]))
    if scan.pr_result is not None:
        created = _object_mapping(scan.pr_result.stats.get("created_at"))
        for hit in signal_hits:
            number = hit.evidence.get("pr")
            if number is not None and number in created:
                dates.append(str(created[number]))
    return min(dates, key=_instant) if dates else None


def _oldest_scanned_commit_at(scan: _RepoScan) -> str | None:
    committed = _object_mapping(scan.history_stats.get("committed_at"))
    dates = [str(value) for value in committed.values() if value]
    return min(dates, key=_instant) if dates else None


def _nonnegative_int(value: object) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _generic_markers(hits: list[Hit]) -> list[str]:
    """Shared, vendor-neutral evidence that must not count as an agent.

    ``Generic`` is a pseudo-agent: ``AGENTS.md``, ``AI Assistant`` and
    ``ai-generated`` describe a convention, an identity alias, or a PR label,
    not a product.  Keep the evidence visible, but never score it.
    """

    markers: set[str] = set()
    for hit in hits:
        if hit.agent != GENERIC_AGENT:
            continue
        if hit.channel == "file":
            path = str(hit.evidence.get("path") or GENERIC_AGENT)
            markers.add(path.rsplit("/", 1)[-1] or GENERIC_AGENT)
        elif hit.channel in {"author", "commit_trailer", "pr_metadata"}:
            value = hit.evidence.get("login") or hit.evidence.get("email") or "AI Assistant"
            markers.add(f"author:{value}")
        elif hit.channel == "label":
            value = hit.evidence.get("label") or "ai-generated"
            markers.add(f"label:{value}")
        else:
            markers.add(f"{hit.channel}:{GENERIC_AGENT}")
    return sorted(markers)


def _agent_projection(scan: _RepoScan) -> tuple[list[str], list[dict], list[str]]:
    """Split scored agents from shared markers and content-only fallbacks.

    Content evidence from a shared file is a *fallback*: it is used only when no
    product-owned file, identity, branch or PR names an agent.  This prevents a
    shared ``AGENTS.md`` from adding agents on top of stronger evidence.
    """

    named = [hit for hit in scan.hits if hit.channel != _BOT_CHANNEL and hit.agent != GENERIC_AGENT]
    direct = [hit for hit in named if hit.channel != CONTENT_CHANNEL]
    content = [hit for hit in named if hit.channel == CONTENT_CHANNEL]
    direct_agents = sorted({hit.agent for hit in direct})
    if direct_agents:
        return direct_agents, [], _generic_markers(scan.hits)
    content_agents = sorted({hit.agent for hit in content})
    details = [
        {
            "agent": hit.agent,
            "path": hit.evidence.get("path"),
            "cue": hit.evidence.get("cue"),
            "confidence": hit.evidence.get("confidence"),
            "classifier": hit.evidence.get("classifier"),
        }
        for hit in content
        if hit.agent in content_agents
    ]
    return content_agents, details, _generic_markers(scan.hits)


def _repo_document(scan: _RepoScan) -> dict:
    agents, content_attribution, generic_markers = _agent_projection(scan)
    ai, human = _ratio_sets(scan)
    ratio = len(ai) / (len(ai) + len(human)) if (ai or human) else None
    notes = [
        f"{key}: {result.note}"
        for key, result in scan.results.items()
        if result.note and result.status != "ok"
    ]
    total_commits = _nonnegative_int(scan.history_stats.get("total_commits"))
    if total_commits is None:
        total_commits = _nonnegative_int(scan.commit_count)
    scan.commit_count = total_commits
    window_commits = _nonnegative_int(scan.history_stats.get("window_commits"))
    eligible_commits = _nonnegative_int(scan.history_stats.get("commits"))
    history_results = [
        scan.results[key] for key in ("author", "commit_trailer") if key in scan.results
    ]
    history_ok = bool(history_results) and all(result.status == "ok" for result in history_results)
    coverage: float | None = None
    complete: bool | None = None
    if history_ok and total_commits is not None and window_commits is not None:
        if total_commits == 0:
            if window_commits == 0:
                coverage = 1.0
                complete = True
        elif window_commits <= total_commits:
            coverage = window_commits / total_commits
            complete = window_commits == total_commits
        else:
            notes.append("history: inspected window exceeds frozen total; coverage unknown")
    return {
        "agents": agents,
        "generic_markers": generic_markers,
        "content_attribution": content_attribution,
        "channels": {key: result.status for key, result in scan.results.items()},
        "unavailable": any(result.status == "unavailable" for result in scan.results.values()),
        "first_signal_at": _first_signal_at(scan),
        "oldest_scanned_commit_at": _oldest_scanned_commit_at(scan),
        "total_commits": total_commits,
        "history_window_commits": window_commits,
        "history_eligible_commits": eligible_commits,
        "history_coverage": round(coverage, 4) if coverage is not None else None,
        "history_complete": complete,
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


def _facets(hits: list[Hit]) -> list[tuple[str, str]]:
    """Distinct (agent, channel) pairs, excluding the shared ``Generic`` marker."""

    return sorted({(hit.agent, hit.channel) for hit in hits if hit.agent != GENERIC_AGENT})


def _scan_contribution(scan: _RepoScan) -> _SummaryContribution:
    # Count only agents in the projected document.  That set already excludes
    # the ``Generic`` marker and content fallbacks that were not used.
    scored = set(scan.document.get("agents") or ())
    agent_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    for hit in scan.hits:
        if hit.channel == _BOT_CHANNEL or hit.agent == GENERIC_AGENT or hit.agent not in scored:
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
        has_signal=bool(set(document["agents"]) - {GENERIC_AGENT}),
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
        "first_signal_at": min(firsts, key=_instant) if firsts else None,
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
    token_pool: DetectionTokenPool | None = None,
) -> RunPayload:
    cfg = config or DetectConfig()
    last_pool_stats_report = 0.0

    def report_pool_stats(*, force: bool = False) -> None:
        nonlocal last_pool_stats_report
        if token_pool is None or cfg.pool_stats_reporter is None:
            return
        now = time.monotonic()
        if not force and now - last_pool_stats_report < max(0.0, cfg.pool_stats_interval):
            return
        cfg.pool_stats_reporter(token_pool.stats())
        last_pool_stats_report = now

    if deps.limiter is not None:
        seconds = (
            cfg.deadline_seconds if cfg.deadline_seconds is not None else request_deadline_seconds()
        )
        deps.limiter.bind_deadline(Deadline(seconds))
    ledger = audit.PointsLedger()
    candidates = _candidates(deps.engine, spec.source_run_id, spec.limit)
    total = len(candidates)
    scans: list[_RepoScan] = []
    contributions: list[_SummaryContribution] = []
    failures: list[str] = []
    had_partial_channels = False
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
            report_pool_stats(force=True)
            while True:
                while not exhausted and len(in_flight) < max_workers:
                    cancellation.check()
                    candidate = next(pending, None)
                    if candidate is None:
                        exhausted = True
                        break
                    context = contextvars.copy_context()
                    if token_pool is None:
                        future = pool.submit(
                            context.run, _scan_repo, deps, pack, spec, run_id, ledger, candidate
                        )
                    else:
                        future = pool.submit(
                            context.run,
                            _scan_repo_from_pool,
                            token_pool,
                            pack,
                            spec,
                            run_id,
                            ledger,
                            candidate,
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
                except TokenPoolExhausted:
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
                facets = _facets(scan.hits)
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
                contributions.append(_scan_contribution(scan))
                had_partial_channels = had_partial_channels or any(
                    result.status in ("partial", "unavailable") for result in scan.results.values()
                )
                # Evidence is durable in PostgreSQL and streams from there into the
                # export. Keep only the compact item projection for the final bundle;
                # retaining every hit and 100-entry history/PR map does not scale to
                # a 60k-repository corpus.
                scan.hits.clear()
                scan.results.clear()
                scan.pr_result = None
                scan.history_stats = {}
                done += 1
                progress.report("detecting", done, total)
                report_pool_stats()
        except RunCancelled:
            cancelled = True
            raise
        finally:
            pool.shutdown(wait=not cancelled, cancel_futures=True)
    finally:
        report_pool_stats(force=True)
        if deps.limiter is not None:
            deps.limiter.bind_deadline(None)
        if deps.audit_buffer is not None:
            deps.audit_buffer.flush()
    partial = bool(failures) or had_partial_channels
    items = [
        RunPayloadItem(
            repo_id=scan.repo_id,
            full_name=scan.full_name,
            stargazers=scan.stargazers,
            repo_created_at=(
                scan.repo_created_at.isoformat() if scan.repo_created_at is not None else None
            ),
            commit_count=scan.commit_count,
            pushed_at=scan.pushed_at.isoformat() if scan.pushed_at is not None else None,
            archived=scan.archived,
            language=scan.language,
            license_spdx=scan.license_spdx,
            country_iso=scan.country_iso,
            geo_confidence=scan.geo_confidence,
            virtuals=dict(scan.virtuals),
            detection=scan.document,
        )
        for scan in scans
    ]
    result_summary = _fold_summary(contributions, spec, pack, len(scans))
    field_stats: dict[str, object] = {"points": ledger.as_dict()}
    if token_pool is not None:
        pool_stats = token_pool.stats()
        field_stats["token_pool"] = pool_stats
        result_summary["token_pool"] = pool_stats
    return RunPayload(
        total_count=total,
        items=items,
        incomplete=partial,
        fetched=total,
        warnings=failures,
        result_summary=result_summary,
        detections_source=lambda: stream_detections(deps.engine, run_id),
        field_stats=field_stats,
    )
