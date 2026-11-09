from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import bindparam, text, update
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from serve.countries import (
    UNKNOWN_COUNTRY,
    country_name,
    country_wealth,
    gdp_per_capita,
    income_group,
    wealth_source,
)
from serve.pages import _stamp, validate_csrf
from serve.pages import _templates as templates

ANALYSIS_PAGE_SIZE = 400
FINGERPRINT_LIMIT = 5
WEALTH_MIN_REPOS = 10

_INCOME_ORDER = {
    "High income": 0,
    "Upper middle income": 1,
    "Lower middle income": 2,
    "Low income": 3,
    "Unknown": 4,
}

_SIZE_BUCKETS = (
    (100, "<100 KB", 0),
    (500, "100–500 KB", 1),
    (2_000, "0.5–2 MB", 2),
    (10_000, "2–10 MB", 3),
    (50_000, "10–50 MB", 4),
    (200_000, "50–200 MB", 5),
    (None, "≥200 MB", 6),
)


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    description: str


ANALYSIS_METRICS: tuple[Metric, ...] = (
    Metric(
        "agent_share",
        "Agent share",
        "Repos with each agent, as a share of every scanned repo and of readable repos.",
    ),
    Metric(
        "agents_by_country",
        "Agents by country",
        "Repo counts per country and agent. Unknown country is its own bucket.",
    ),
    Metric(
        "adoption",
        "Agent use",
        "Share of repos with at least one agent, plus the adoption-level mix.",
    ),
    Metric(
        "adoption_by_country",
        "Agent use by country",
        "Adoption rate per country, repo-weighted. Unknown country is its own bucket.",
    ),
    Metric(
        "size_vs_adoption",
        "Repo size vs agent use",
        "Adoption rate by repository size bucket, with per-agent rates.",
    ),
    Metric(
        "agent_debut",
        "Agent debuts",
        "Earliest observed signal per agent, plus the earliest repo that carries it.",
    ),
    Metric(
        "fingerprint_debut",
        "Fingerprint debuts",
        "Earliest observed signal for the top file, branch, trailer, author, label, and issue "
        "fingerprints per agent.",
    ),
    Metric(
        "country_wealth",
        "Country wealth vs agent use",
        "GDP per capita and income group against adoption rate.",
    ),
)

_METRIC_BY_KEY = {metric.key: metric for metric in ANALYSIS_METRICS}
_ALL_METRIC_KEYS = tuple(metric.key for metric in ANALYSIS_METRICS)


def _pct(part: int | float | None, whole: int | float | None) -> float | None:
    if part is None or not whole:
        return None
    return round(float(part) / float(whole) * 100, 1)


def _moment(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return moment.astimezone(UTC).strftime("%Y-%m-%d")
    return str(value)[:10] or None


def _scalar(engine: Engine, statement: str, params: dict[str, Any]) -> Any:
    with engine.connect() as connection:
        return connection.execute(text(statement), params).scalar()


def _mappings(engine: Engine, statement: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(text(statement), params).mappings()]


def _run_row(engine: Engine, run_id: int) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT id, kind, status, source_run_id, created_at, started_at, finished_at,"
                    " filter_hash, filter_spec, result_summary"
                    " FROM runs WHERE id = :run"
                ),
                {"run": run_id},
            )
            .mappings()
            .one_or_none()
        )
    return dict(row) if row is not None else None


def detection_number(engine: Engine, run_id: int) -> int:
    return int(
        _scalar(
            engine,
            "SELECT count(*) FROM runs WHERE kind = 'detect' AND id <= :run",
            {"run": run_id},
        )
        or 0
    )


def _finished_detections(engine: Engine, limit: int = ANALYSIS_PAGE_SIZE) -> list[dict[str, Any]]:
    rows = _mappings(
        engine,
        "SELECT r.id, r.status, r.source_run_id, r.created_at, r.finished_at,"
        " (SELECT count(*) FROM run_items i WHERE i.run_id = r.id) AS repos"
        " FROM runs r"
        " WHERE r.kind = 'detect' AND r.status IN ('done', 'partial')"
        " ORDER BY r.id DESC LIMIT :limit",
        {"limit": limit},
    )
    numbers = {
        int(row["id"]): int(row["number"])
        for row in _mappings(
            engine,
            "SELECT id, row_number() OVER (ORDER BY id) AS number FROM runs WHERE kind = 'detect'",
            {},
        )
    }
    return [
        {
            "id": int(row["id"]),
            "number": numbers.get(int(row["id"]), int(row["id"])),
            "status": row["status"],
            "source_run_id": row["source_run_id"],
            "started": _stamp(row["created_at"]),
            "duration": _duration(row["created_at"], row["finished_at"]),
            "repos": int(row["repos"] or 0),
        }
        for row in rows
    ]


def _duration(started: object, finished: object) -> str:
    if not isinstance(started, datetime) or not isinstance(finished, datetime):
        return "—"
    seconds = max(0, int((finished - started).total_seconds()))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _selected_metrics(request: Request) -> tuple[str, ...]:
    raw = request.query_params.getlist("metric")
    if not raw:
        joined = request.query_params.get("metrics")
        if joined is not None:
            raw = [part for part in joined.split(",") if part]
    if not raw and "metrics_present" not in request.query_params:
        return _ALL_METRIC_KEYS
    return tuple(key for key in dict.fromkeys(raw) if key in _METRIC_BY_KEY)


def _totals(engine: Engine, run_id: int) -> dict[str, Any]:
    row = _mappings(
        engine,
        "SELECT count(*) AS scanned,"
        " count(*) FILTER (WHERE COALESCE((detection->>'unavailable')::boolean, false))"
        "   AS unavailable,"
        " count(*) FILTER"
        "   (WHERE jsonb_array_length(COALESCE(detection->'agents', '[]'::jsonb)) > 0)"
        "   AS with_agent,"
        " count(*) FILTER (WHERE detection->>'failure_class' IS NOT NULL) AS failed,"
        " count(*) FILTER (WHERE detection IS NULL) AS missing_document"
        " FROM run_items WHERE run_id = :run",
        {"run": run_id},
    )[0]
    scanned = int(row["scanned"] or 0)
    unavailable = int(row["unavailable"] or 0)
    with_agent = int(row["with_agent"] or 0)
    readable = max(0, scanned - unavailable)
    return {
        "scanned": scanned,
        "unavailable": unavailable,
        "readable": readable,
        "with_agent": with_agent,
        "failed": int(row["failed"] or 0),
        "missing_document": int(row["missing_document"] or 0),
        "adoption_scanned": _pct(with_agent, scanned),
        "adoption_readable": _pct(with_agent, readable),
    }


def _country_totals(engine: Engine, run_id: int) -> dict[str, Any]:
    row = _mappings(
        engine,
        "SELECT count(*) AS repos,"
        " count(*) FILTER (WHERE COALESCE(i.country_iso, o.country_iso) IS NOT NULL) AS known"
        " FROM run_items i"
        " LEFT JOIN repos r ON r.id = i.repo_id"
        " LEFT JOIN owners o ON o.id = r.owner_id"
        " WHERE i.run_id = :run",
        {"run": run_id},
    )[0]
    owners = _mappings(
        engine,
        "SELECT count(DISTINCT r.owner_id) AS owners,"
        " count(DISTINCT r.owner_id) FILTER (WHERE o.country_iso IS NULL) AS missing"
        " FROM run_items i"
        " JOIN repos r ON r.id = i.repo_id"
        " JOIN owners o ON o.id = r.owner_id"
        " WHERE i.run_id = :run",
        {"run": run_id},
    )[0]
    repos = int(row["repos"] or 0)
    known = int(row["known"] or 0)
    return {
        "repos": repos,
        "known": known,
        "unknown": max(0, repos - known),
        "coverage": _pct(known, repos),
        "owners": int(owners["owners"] or 0),
        "missing_owners": int(owners["missing"] or 0),
        "pending_owners": _pending_owner_count(engine, run_id),
    }


def _agent_share(engine: Engine, run_id: int, totals: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _mappings(
        engine,
        "SELECT a.agent, count(*) AS repos,"
        " count(*) FILTER (WHERE NOT COALESCE((i.detection->>'unavailable')::boolean, false))"
        "   AS readable_repos"
        " FROM run_items i"
        " CROSS JOIN LATERAL jsonb_array_elements_text("
        "   COALESCE(i.detection->'agents', '[]'::jsonb)"
        " ) AS a(agent)"
        " WHERE i.run_id = :run"
        " GROUP BY a.agent"
        " ORDER BY repos DESC, a.agent",
        {"run": run_id},
    )
    return [
        {
            "agent": row["agent"],
            "repos": int(row["repos"] or 0),
            "readable_repos": int(row["readable_repos"] or 0),
            "share_scanned": _pct(row["repos"], totals["scanned"]),
            "share_readable": _pct(row["readable_repos"], totals["readable"]),
        }
        for row in rows
    ]


def _country_rows(engine: Engine, run_id: int) -> list[dict[str, Any]]:
    rows = _mappings(
        engine,
        "WITH base AS ("
        " SELECT COALESCE(i.country_iso, o.country_iso, '??') AS country_iso,"
        "   i.repo_id,"
        "   COALESCE((i.detection->>'unavailable')::boolean, false) AS unavailable,"
        "   jsonb_array_length(COALESCE(i.detection->'agents', '[]'::jsonb)) > 0 AS with_agent"
        " FROM run_items i"
        " LEFT JOIN repos r ON r.id = i.repo_id"
        " LEFT JOIN owners o ON o.id = r.owner_id"
        " WHERE i.run_id = :run"
        ") SELECT country_iso, count(*) AS repos,"
        " count(*) FILTER (WHERE with_agent) AS with_agent,"
        " count(*) FILTER (WHERE unavailable) AS unavailable"
        " FROM base GROUP BY country_iso",
        {"run": run_id},
    )
    result = []
    for row in rows:
        repos = int(row["repos"] or 0)
        unavailable = int(row["unavailable"] or 0)
        readable = max(0, repos - unavailable)
        with_agent = int(row["with_agent"] or 0)
        iso = str(row["country_iso"])
        result.append(
            {
                "country_iso": iso,
                "country": "Unknown" if iso == UNKNOWN_COUNTRY else country_name(iso),
                "repos": repos,
                "readable": readable,
                "with_agent": with_agent,
                "unavailable": unavailable,
                "adoption_scanned": _pct(with_agent, repos),
                "adoption_readable": _pct(with_agent, readable),
            }
        )
    return sorted(
        result,
        key=lambda row: (
            row["country_iso"] == UNKNOWN_COUNTRY,
            -row["repos"],
            row["country"] or "",
        ),
    )


def _agents_by_country(
    engine: Engine, run_id: int, countries: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows = _mappings(
        engine,
        "SELECT COALESCE(i.country_iso, o.country_iso, '??') AS country_iso,"
        " a.agent, count(*) AS repos"
        " FROM run_items i"
        " LEFT JOIN repos r ON r.id = i.repo_id"
        " LEFT JOIN owners o ON o.id = r.owner_id"
        " CROSS JOIN LATERAL jsonb_array_elements_text("
        "   COALESCE(i.detection->'agents', '[]'::jsonb)"
        " ) AS a(agent)"
        " WHERE i.run_id = :run"
        " GROUP BY 1, 2",
        {"run": run_id},
    )
    by_country: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_country[str(row["country_iso"])].append(
            {"agent": row["agent"], "repos": int(row["repos"] or 0)}
        )
    for country in countries:
        agents = sorted(
            by_country.get(country["country_iso"], []),
            key=lambda item: (-item["repos"], item["agent"]),
        )
        for agent in agents:
            agent["share_readable"] = _pct(agent["repos"], country["readable"])
        country["agents"] = agents
    return [country for country in countries if country["agents"]]


def _adoption_levels(engine: Engine, run_id: int) -> list[dict[str, Any]]:
    rows = _mappings(
        engine,
        "SELECT COALESCE(NULLIF(detection->>'adoption_level', ''), 'unknown') AS level,"
        " count(*) AS repos"
        " FROM run_items WHERE run_id = :run GROUP BY 1",
        {"run": run_id},
    )
    order = {"none": 0, "experimental": 1, "limited": 2, "consistent": 3, "pervasive": 4}
    return sorted(
        [
            {
                "level": str(row["level"]),
                "repos": int(row["repos"] or 0),
                "share": _pct(row["repos"], sum(int(item["repos"] or 0) for item in rows)),
            }
            for row in rows
        ],
        key=lambda row: (order.get(row["level"], 99), row["level"]),
    )


def _size_expression(alias: str = "r") -> str:
    parts = []
    for threshold, label, _order in _SIZE_BUCKETS[:-1]:
        parts.append(f"WHEN {alias}.size_kb < {threshold} THEN '{label}'")
    parts.append(f"ELSE '{_SIZE_BUCKETS[-1][1]}'")
    return "CASE WHEN " + alias + ".size_kb IS NULL THEN 'Unknown' " + " ".join(parts) + " END"


def _size_order_expression(alias: str = "r") -> str:
    parts = []
    for threshold, _label, order in _SIZE_BUCKETS[:-1]:
        parts.append(f"WHEN {alias}.size_kb < {threshold} THEN {order}")
    parts.append(f"ELSE {_SIZE_BUCKETS[-1][2]}")
    return "CASE WHEN " + alias + ".size_kb IS NULL THEN 99 " + " ".join(parts) + " END"


def _size_vs_adoption(
    engine: Engine, run_id: int, agent_share: list[dict[str, Any]]
) -> dict[str, Any]:
    bucket_sql = _size_expression()
    order_sql = _size_order_expression()
    rows = _mappings(
        engine,
        f"WITH base AS ("
        f" SELECT i.repo_id, {bucket_sql} AS bucket, {order_sql} AS bucket_order,"
        "   jsonb_array_length(COALESCE(i.detection->'agents', '[]'::jsonb)) > 0 AS with_agent,"
        "   COALESCE((i.detection->>'unavailable')::boolean, false) AS unavailable"
        " FROM run_items i"
        " LEFT JOIN repos r ON r.id = i.repo_id"
        " WHERE i.run_id = :run"
        f") SELECT bucket, min(bucket_order) AS bucket_order, count(*) AS repos,"
        " count(*) FILTER (WHERE with_agent) AS with_agent,"
        " count(*) FILTER (WHERE unavailable) AS unavailable"
        " FROM base GROUP BY bucket ORDER BY bucket_order",
        {"run": run_id},
    )
    agent_rows = _mappings(
        engine,
        f"WITH base AS ("
        f" SELECT i.repo_id, {bucket_sql} AS bucket, {order_sql} AS bucket_order, a.agent"
        " FROM run_items i"
        " LEFT JOIN repos r ON r.id = i.repo_id"
        " CROSS JOIN LATERAL jsonb_array_elements_text("
        "   COALESCE(i.detection->'agents', '[]'::jsonb)"
        " ) AS a(agent)"
        " WHERE i.run_id = :run"
        f") SELECT bucket, min(bucket_order) AS bucket_order, agent, count(*) AS repos"
        " FROM base GROUP BY bucket, agent",
        {"run": run_id},
    )
    by_bucket: dict[str, dict[str, int]] = defaultdict(dict)
    for row in agent_rows:
        by_bucket[str(row["bucket"])][str(row["agent"])] = int(row["repos"] or 0)
    top_agents = [row["agent"] for row in agent_share[:8]]
    buckets = []
    for row in rows:
        bucket = str(row["bucket"])
        repos = int(row["repos"] or 0)
        unavailable = int(row["unavailable"] or 0)
        readable = max(0, repos - unavailable)
        with_agent = int(row["with_agent"] or 0)
        agents = [
            {
                "agent": agent,
                "repos": by_bucket.get(bucket, {}).get(agent, 0),
                "share": _pct(by_bucket.get(bucket, {}).get(agent, 0), readable),
            }
            for agent in top_agents
        ]
        buckets.append(
            {
                "bucket": bucket,
                "repos": repos,
                "readable": readable,
                "with_agent": with_agent,
                "unavailable": unavailable,
                "adoption_readable": _pct(with_agent, readable),
                "agents": agents,
            }
        )
    return {"buckets": buckets, "agents": top_agents}


def _agent_debut(engine: Engine, run_id: int) -> list[dict[str, Any]]:
    rows = _mappings(
        engine,
        "SELECT a.agent,"
        " min(NULLIF(i.detection->>'first_signal_at', '')::timestamptz) AS earliest_signal,"
        " min(r.created_at) AS earliest_repo_created,"
        " count(*) AS repos,"
        " count(*) FILTER (WHERE NULLIF(i.detection->>'first_signal_at', '') IS NOT NULL)"
        "   AS dated_repos"
        " FROM run_items i"
        " LEFT JOIN repos r ON r.id = i.repo_id"
        " CROSS JOIN LATERAL jsonb_array_elements_text("
        "   COALESCE(i.detection->'agents', '[]'::jsonb)"
        " ) AS a(agent)"
        " WHERE i.run_id = :run"
        " GROUP BY a.agent"
        " ORDER BY earliest_signal NULLS LAST, repos DESC, a.agent",
        {"run": run_id},
    )
    return [
        {
            "agent": row["agent"],
            "earliest_signal": _moment(row["earliest_signal"]),
            "earliest_repo_created": _moment(row["earliest_repo_created"]),
            "repos": int(row["repos"] or 0),
            "dated_repos": int(row["dated_repos"] or 0),
        }
        for row in rows
    ]


_FINGERPRINT_CHANNELS = (
    ("file", "e.evidence->>'path'"),
    ("branch", "COALESCE(e.evidence->>'match', e.evidence->>'head')"),
    ("commit_trailer", "LEFT(COALESCE(e.evidence->>'snippet', ''), 140)"),
    ("author", "COALESCE(NULLIF(e.evidence->>'login', ''), e.evidence->>'field')"),
    ("label", "e.evidence->>'label'"),
    ("issue", "e.evidence->>'role'"),
)


def _fingerprint_debut(engine: Engine, run_id: int, limit: int = FINGERPRINT_LIMIT) -> list[dict]:
    # Query channel by channel so each scan can use de_run_channel_idx. A single
    # CASE over every evidence row is roughly 5x slower on large runs.
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for channel, expression in _FINGERPRINT_CHANNELS:
        rows = _mappings(
            engine,
            f"WITH fp AS ("
            f" SELECT e.agent, e.repo_id, {expression} AS fingerprint"
            " FROM detection_evidence e"
            " WHERE e.run_id = :run AND e.channel = :channel"
            ") SELECT fp.agent, fp.fingerprint, count(DISTINCT fp.repo_id) AS repos,"
            " min(r.created_at) AS earliest_repo_created,"
            " min(NULLIF(i.detection->>'first_signal_at', '')::timestamptz) AS earliest_signal"
            " FROM fp"
            " LEFT JOIN repos r ON r.id = fp.repo_id"
            " LEFT JOIN run_items i ON i.run_id = :run AND i.repo_id = fp.repo_id"
            " WHERE fp.fingerprint IS NOT NULL AND fp.fingerprint <> ''"
            " GROUP BY fp.agent, fp.fingerprint",
            {"run": run_id, "channel": channel},
        )
        for row in rows:
            grouped[str(row["agent"])].append(
                {
                    "channel": channel,
                    "fingerprint": row["fingerprint"],
                    "repos": int(row["repos"] or 0),
                    "earliest_signal": _moment(row["earliest_signal"]),
                    "earliest_repo_created": _moment(row["earliest_repo_created"]),
                }
            )
    return [
        {
            "agent": agent,
            "fingerprints": sorted(
                fingerprints, key=lambda item: (-item["repos"], item["fingerprint"])
            )[:limit],
        }
        for agent, fingerprints in sorted(grouped.items())
    ]


def _income_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        group = row["income_group"] or "Unknown"
        bucket = groups.setdefault(
            group, {"income_group": group, "repos": 0, "with_agent": 0, "countries": 0}
        )
        bucket["repos"] += row["readable"]
        bucket["with_agent"] += row["with_agent"]
        bucket["countries"] += 1
    result = []
    for group in groups.values():
        result.append(
            {
                **group,
                "adoption": _pct(group["with_agent"], group["repos"]),
            }
        )
    return sorted(
        result,
        key=lambda row: (
            _INCOME_ORDER.get(row["income_group"], 99),
            -row["repos"],
        ),
    )


def _pearson(points: list[tuple[float, float]]) -> float | None:
    if len(points) < 3:
        return None
    n = len(points)
    mean_x = sum(x for x, _ in points) / n
    mean_y = sum(y for _, y in points) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in points)
    var_x = sum((x - mean_x) ** 2 for x, _ in points)
    var_y = sum((y - mean_y) ** 2 for _, y in points)
    if var_x <= 0 or var_y <= 0:
        return None
    return cov / math.sqrt(var_x * var_y)


def _country_wealth(engine: Engine, run_id: int, countries: list[dict[str, Any]]) -> dict:
    rows = []
    for country in countries:
        iso = country["country_iso"]
        if iso == UNKNOWN_COUNTRY:
            continue
        wealth = country_wealth(iso) or {}
        rows.append(
            {
                **country,
                "gdp_pc": gdp_per_capita(iso),
                "gdp_year": wealth.get("gdp_year"),
                "income_group": income_group(iso) or "Unknown",
            }
        )
    points = [
        (math.log10(row["gdp_pc"]), row["adoption_readable"] / 100)
        for row in rows
        if row["gdp_pc"]
        and row["gdp_pc"] > 0
        and row["adoption_readable"] is not None
        and row["readable"] >= WEALTH_MIN_REPOS
    ]
    correlation = _pearson(points)
    return {
        "rows": sorted(
            rows,
            key=lambda row: (
                row["gdp_pc"] is None,
                -(row["gdp_pc"] or 0),
            ),
        ),
        "income_groups": _income_groups(rows),
        "correlation": round(correlation, 3) if correlation is not None else None,
        "points": len(points),
        "min_repos": WEALTH_MIN_REPOS,
        "source": wealth_source(),
    }


def analysis_context(
    engine: Engine, run_id: int, selected: tuple[str, ...]
) -> dict[str, Any] | None:
    run = _run_row(engine, run_id)
    if run is None or run["kind"] != "detect":
        return None
    totals = _totals(engine, run_id)
    countries = _country_rows(engine, run_id)
    agent_share = _agent_share(engine, run_id, totals)
    results: dict[str, Any] = {}
    if "agent_share" in selected:
        results["agent_share"] = agent_share
    if "agents_by_country" in selected:
        results["agents_by_country"] = _agents_by_country(engine, run_id, countries)
    if "adoption" in selected:
        results["adoption"] = {
            **totals,
            "levels": _adoption_levels(engine, run_id),
        }
    if "adoption_by_country" in selected:
        results["adoption_by_country"] = countries
    if "size_vs_adoption" in selected:
        results["size_vs_adoption"] = _size_vs_adoption(engine, run_id, agent_share)
    if "agent_debut" in selected:
        results["agent_debut"] = _agent_debut(engine, run_id)
    if "fingerprint_debut" in selected:
        results["fingerprint_debut"] = _fingerprint_debut(engine, run_id)
    if "country_wealth" in selected:
        results["country_wealth"] = _country_wealth(engine, run_id, countries)
    spec = run.get("filter_spec") or {}
    return {
        "run": {
            "id": int(run["id"]),
            "number": detection_number(engine, run_id),
            "status": run["status"],
            "source_run_id": run["source_run_id"],
            "created_at": _stamp(run["created_at"]),
            "finished_at": _stamp(run["finished_at"]),
            "api_source": spec.get("source") or "api",
            "hash_short": str(run["filter_hash"])[:8],
        },
        "selected": selected,
        "metrics": [metric for metric in ANALYSIS_METRICS if metric.key in selected],
        "all_metrics": ANALYSIS_METRICS,
        "totals": totals,
        "country": _country_totals(engine, run_id),
        "results": results,
    }


def _pending_owner_count(engine: Engine, run_id: int, *, retry_unmatched: bool = False) -> int:
    """Owners a backfill can still act on (excludes final ``unmatched`` rows)."""
    from enrich.geo_resolver import GEO_RESOLVER_VERSION

    retry_filter = (
        ""
        if retry_unmatched
        else " AND (o.geo_confidence IS DISTINCT FROM 'unmatched'"
        " OR o.geo_version IS DISTINCT FROM :geo_version)"
    )
    return int(
        _scalar(
            engine,
            "SELECT count(DISTINCT r.owner_id) FROM run_items i"
            " JOIN repos r ON r.id = i.repo_id JOIN owners o ON o.id = r.owner_id"
            " WHERE i.run_id = :run"
            " AND (o.country_iso IS NULL OR o.geo_version IS DISTINCT FROM :geo_version)"
            + retry_filter,
            {"run": run_id, "geo_version": GEO_RESOLVER_VERSION},
        )
        or 0
    )


def _sync_run_item_countries(engine: Engine, *run_ids: int) -> int:
    """Copy resolved owner countries onto frozen run rows, always."""
    total = 0
    with engine.begin() as connection:
        for run_id in dict.fromkeys(run_ids):
            updated = connection.execute(
                text(
                    "UPDATE run_items i"
                    " SET country_iso = o.country_iso, geo_confidence = o.geo_confidence"
                    " FROM repos r JOIN owners o ON o.id = r.owner_id"
                    " WHERE i.run_id = :run AND i.repo_id = r.id"
                    "   AND (i.country_iso IS DISTINCT FROM o.country_iso"
                    "        OR i.geo_confidence IS DISTINCT FROM o.geo_confidence)"
                ),
                {"run": run_id},
            ).rowcount
            total += int(updated or 0)
    return total


def _needs_geo_resolution(owner: dict[str, Any], *, retry_unmatched: bool = False) -> bool:
    """Whether an owner still needs a resolver pass at the current version."""
    from enrich.geo_resolver import GEO_RESOLVER_VERSION

    if owner.get("country_iso") is not None and owner.get("geo_version") == GEO_RESOLVER_VERSION:
        return False
    if (
        not retry_unmatched
        and owner.get("geo_confidence") == "unmatched"
        and owner.get("geo_version") == GEO_RESOLVER_VERSION
    ):
        return False
    return True


def _resolve_owner_rows_local(
    engine: Engine,
    owners: dict[int, dict[str, Any]],
    *,
    retry_unmatched: bool = False,
) -> tuple[list[dict[str, Any]], int, int]:
    """Resolve stored location/blog signals and mutate the owner dicts in place.

    No GitHub requests are made: this only replays signals already captured
    during discovery/hydration. Returns ``(updates, resolved, unmatched)``.
    """
    from enrich.geo_resolver import (
        GEO_RESOLVER_VERSION,
        GeoCache,
        _owner_cache_key,
        resolve_many,
    )

    targets = [
        (owner_id, owner)
        for owner_id, owner in owners.items()
        if _needs_geo_resolution(owner, retry_unmatched=retry_unmatched)
        and (owner.get("location_raw") is not None or owner.get("blog") is not None)
    ]
    if not targets:
        return [], 0, 0
    resolved = resolve_many(
        engine,
        [owner["location_raw"] for _, owner in targets],
        blogs=[owner["blog"] for _, owner in targets],
        cache=GeoCache(engine),
    )
    updates: list[dict[str, Any]] = []
    matched = 0
    unmatched = 0
    for owner_id, owner in targets:
        raw = owner.get("location_raw")
        blog = owner.get("blog")
        result = resolved.get(_owner_cache_key(raw, blog, None))
        country_iso = result.country_iso if result is not None else None
        confidence = result.confidence if result is not None else "unmatched"
        owner["country_iso"] = country_iso
        owner["geo_confidence"] = confidence
        owner["geo_version"] = GEO_RESOLVER_VERSION
        updates.append(
            {
                "owner_id": owner_id,
                "location_raw": raw,
                "blog": blog,
                "country_iso": country_iso,
                "geo_confidence": confidence,
                "geo_version": GEO_RESOLVER_VERSION,
            }
        )
        if country_iso is not None:
            matched += 1
        else:
            unmatched += 1
    return updates, matched, unmatched


def _write_owner_geo_updates(engine: Engine, updates: Sequence[dict[str, Any]]) -> None:
    from store.models import Owner

    if not updates:
        return
    statement = (
        update(Owner)
        .where(Owner.id == bindparam("owner_id"))
        .values(
            location_raw=bindparam("location_raw"),
            blog=bindparam("blog"),
            country_iso=bindparam("country_iso"),
            geo_confidence=bindparam("geo_confidence"),
            geo_version=bindparam("geo_version"),
        )
    )
    with engine.begin() as connection:
        connection.execute(statement, list(updates))


def resolve_repo_countries(
    engine: Engine, repo_ids: Sequence[int]
) -> dict[int, tuple[str | None, str | None]]:
    """Resolve owner countries for repositories using stored signals only.

    Returns ``repo_id -> (country_iso, geo_confidence)``. Detection runs call
    this before their payload is snapshotted so new runs carry countries
    without a manual backfill. Owners with no stored location or blog stay
    unresolved; nothing is guessed and no GitHub request is made.
    """
    ids = list(dict.fromkeys(int(repo_id) for repo_id in repo_ids))
    if not ids:
        return {}
    rows = _mappings(
        engine,
        "SELECT r.id AS repo_id, o.id, o.login, o.type, o.location_raw, o.blog,"
        " o.country_iso, o.geo_confidence, o.geo_version"
        " FROM repos r JOIN owners o ON o.id = r.owner_id"
        " WHERE r.id = ANY(:ids)",
        {"ids": ids},
    )
    owners: dict[int, dict[str, Any]] = {}
    repo_owner: dict[int, int] = {}
    for row in rows:
        owner_id = int(row["id"])
        repo_owner[int(row["repo_id"])] = owner_id
        owners.setdefault(owner_id, dict(row))
    updates, _resolved, _unmatched = _resolve_owner_rows_local(engine, owners)
    _write_owner_geo_updates(engine, updates)
    return {
        repo_id: (owners[owner_id]["country_iso"], owners[owner_id]["geo_confidence"])
        for repo_id, owner_id in repo_owner.items()
    }


def backfill_countries(
    engine: Engine,
    run_id: int,
    *,
    limit: int = 500,
    retry_unmatched: bool = False,
    fetch: bool = True,
    force_rest: bool = False,
) -> dict[str, int]:
    """Resolve owner countries for a run and freeze them into run_items.

    Owners with a stored ``location_raw``/``blog`` are always resolved in one
    local pass: they cost no API request, so ``limit`` must never hide them.
    ``limit`` only caps how many owners *without* any stored signal are fetched
    from GitHub in a single call; ``limit <= 0`` fetches every one of them.
    ``fetch=False`` skips GitHub entirely.
    """
    from enrich.geo_resolver import GEO_RESOLVER_VERSION
    from enrich.graphql_owner_location import OwnerGeoProfile, OwnerGeoProfileAdapter
    from lib.graphql_batch import fetch_batch, is_transient_error
    from serve.runner import _audit_hook, _fetch_owner_profile, build_deps
    from store.settings import load_run_settings

    retry_filter = (
        ""
        if retry_unmatched
        else " AND (o.geo_confidence IS DISTINCT FROM 'unmatched'"
        " OR o.geo_version IS DISTINCT FROM :geo_version)"
    )
    base_query = (
        "SELECT DISTINCT o.id, o.login, o.type, o.location_raw, o.country_iso,"
        " o.geo_confidence, o.geo_version, o.blog"
        " FROM run_items i"
        " JOIN repos r ON r.id = i.repo_id"
        " JOIN owners o ON o.id = r.owner_id"
        " WHERE i.run_id = :run"
        " AND (o.country_iso IS NULL OR o.geo_version IS DISTINCT FROM :geo_version)" + retry_filter
    )
    params = {"run": run_id, "geo_version": GEO_RESOLVER_VERSION}
    local_pending = _mappings(
        engine,
        base_query + " AND (o.location_raw IS NOT NULL OR o.blog IS NOT NULL) ORDER BY o.id",
        params,
    )
    missing_query = base_query + " AND o.location_raw IS NULL AND o.blog IS NULL ORDER BY o.id"
    missing_params = dict(params)
    if limit > 0:
        missing_query += " LIMIT :limit"
        missing_params["limit"] = limit
    missing_pending = _mappings(engine, missing_query, missing_params) if fetch else []

    run = _run_row(engine, run_id)
    target_ids = [run_id]
    if run is not None and run.get("source_run_id") is not None:
        target_ids.append(int(run["source_run_id"]))
    if not local_pending and not missing_pending:
        # Even when every owner is already classified, the saved rows may still
        # carry an older (or empty) country; always apply what we know.
        updated = _sync_run_item_countries(engine, *target_ids)
        return {
            "owners": 0,
            "fetched": 0,
            "resolved": 0,
            "unmatched": 0,
            "updated": updated,
            "remaining": _pending_owner_count(engine, run_id, retry_unmatched=retry_unmatched),
        }

    owners: dict[int, dict[str, Any]] = {
        int(row["id"]): dict(row) for row in [*local_pending, *missing_pending]
    }
    handled: set[int] = set()
    fetched = 0
    if missing_pending:
        settings = load_run_settings(engine)
        deps = build_deps(engine, max_concurrent=min(8, settings.limiter_max_concurrent))
        try:
            hook = _audit_hook(deps, run_id=run_id, phase="analysis:geo")
            by_login = {str(row["login"]): str(row["type"]) for row in missing_pending}
            owner_id_by_login = {str(row["login"]): int(row["id"]) for row in missing_pending}
            adapter = OwnerGeoProfileAdapter(by_login, batch_size=settings.graphql_batch_size)

            attempted: set[str] = set()

            def fallback(login: str) -> object | None:
                ok, profile = _fetch_owner_profile(deps, login, hook)
                # A definitive answer (even a 404 with no profile) means this
                # owner was checked; record it so a drain does not stall on it.
                attempted.add(login)
                if not ok:
                    return None
                return profile

            outcome = fetch_batch(
                adapter,
                list(by_login),
                client=deps.client,
                limiter=deps.limiter,
                token_id=deps.token_fp,
                fallback=fallback,
                on_response=hook,
                allow_requests=settings.graphql_batch and not force_rest,
                concurrency=min(8, settings.detect_concurrency),
            )
            for login in by_login:
                owner_id = owner_id_by_login[login]
                if login in outcome.values:
                    handled.add(owner_id)
                    fetched += 1
                    profile = outcome.values[login]
                    if isinstance(profile, OwnerGeoProfile):
                        owners[owner_id]["location_raw"] = profile.location
                        owners[owner_id]["blog"] = profile.blog
                    continue
                if login in attempted:
                    # REST fallback answered but produced no profile (for
                    # example a deleted account); record the miss as final.
                    handled.add(owner_id)
                    continue
                reason = outcome.unresolved.get(login, "")
                lowered = reason.lower()
                if (
                    reason
                    and not is_transient_error(reason)
                    and "deadline" not in lowered
                    and "deferred" not in lowered
                ):
                    handled.add(owner_id)
        finally:
            deps.client.close()

    updates, resolved, unmatched = _resolve_owner_rows_local(
        engine, owners, retry_unmatched=retry_unmatched
    )
    # Owners we asked GitHub about but who returned no usable signal are final:
    # record the miss so they are not retried on every pass.
    for owner_id in handled:
        owner = owners[owner_id]
        if owner.get("location_raw") is not None or owner.get("blog") is not None:
            continue
        if owner.get("country_iso") is not None:
            continue
        owner["country_iso"] = None
        owner["geo_confidence"] = "unmatched"
        owner["geo_version"] = GEO_RESOLVER_VERSION
        updates.append(
            {
                "owner_id": owner_id,
                "location_raw": None,
                "blog": owner.get("blog"),
                "country_iso": None,
                "geo_confidence": "unmatched",
                "geo_version": GEO_RESOLVER_VERSION,
            }
        )
        unmatched += 1

    _write_owner_geo_updates(engine, updates)
    updated = _sync_run_item_countries(engine, *target_ids)
    remaining = _pending_owner_count(engine, run_id, retry_unmatched=retry_unmatched)
    return {
        "owners": len(owners),
        "fetched": fetched,
        "resolved": resolved,
        "unmatched": unmatched,
        "updated": updated,
        "remaining": remaining,
    }


def backfill_countries_exhaustive(
    engine: Engine,
    run_id: int,
    *,
    limit: int = 500,
    retry_unmatched: bool = False,
    fetch: bool = True,
    force_rest: bool = False,
) -> dict[str, int]:
    """Drain every actionable owner for a run, not just one 500-owner batch.

    Each pass persists its owners and run rows, so a long API drain never loses
    completed work. Pass ``limit=0`` to fetch every missing profile in a single
    pass instead of looping in batches.
    """
    totals = {"owners": 0, "fetched": 0, "resolved": 0, "unmatched": 0, "updated": 0}
    result: dict[str, int] = {**totals, "remaining": 0}
    while True:
        result = backfill_countries(
            engine,
            run_id,
            limit=limit,
            retry_unmatched=retry_unmatched,
            fetch=fetch,
            force_rest=force_rest,
        )
        for key in totals:
            totals[key] += result[key]
        if result["remaining"] == 0 or result["owners"] == 0:
            break
        if result["fetched"] == 0 and result["updated"] == 0:
            break
    return {**totals, "remaining": result["remaining"]}


def _backfill_notice(request: Request) -> dict[str, Any] | None:
    status = request.query_params.get("country_backfill")
    if status not in ("ok", "error"):
        return None
    return {
        "status": status,
        "message": request.query_params.get("message"),
        "owners": request.query_params.get("owners"),
        "fetched": request.query_params.get("fetched"),
        "resolved": request.query_params.get("resolved"),
        "unmatched": request.query_params.get("unmatched"),
        "updated": request.query_params.get("updated"),
        "remaining": request.query_params.get("remaining"),
    }


def _analysis_redirect(run_id: int, selected: tuple[str, ...]) -> RedirectResponse:
    query = {"metrics": ",".join(selected), "metrics_present": "1"}
    return RedirectResponse(f"/analysis/{run_id}?{urlencode(query)}", status_code=303)


def register_analysis(application: FastAPI, *, engine_factory) -> None:
    @application.get("/analysis", response_class=HTMLResponse)
    def analysis_page(request: Request):
        engine = engine_factory()
        raw_run = request.query_params.get("run", "").strip()
        selected = _selected_metrics(request)
        if raw_run.isdigit():
            return _analysis_redirect(int(raw_run), selected)
        return templates.TemplateResponse(
            request,
            "analysis.html",
            {
                "detections": _finished_detections(engine),
                "metrics": ANALYSIS_METRICS,
                "selected": selected,
                "csrf_token": request.state.csrf_token,
            },
        )

    @application.get("/analysis/{run_id}", response_class=HTMLResponse)
    def analysis_report(request: Request, run_id: int):
        engine = engine_factory()
        selected = _selected_metrics(request)
        context = analysis_context(engine, run_id, selected)
        if context is None:
            return templates.TemplateResponse(
                request,
                "analysis_report.html",
                {"run": None, "selected": selected, "all_metrics": ANALYSIS_METRICS},
                status_code=404,
            )
        return templates.TemplateResponse(
            request,
            "analysis_report.html",
            {
                **context,
                "backfill": _backfill_notice(request),
                "csrf_token": request.state.csrf_token,
            },
        )

    @application.post("/analysis/{run_id}/country-backfill")
    async def analysis_country_backfill(request: Request, run_id: int):
        if not await validate_csrf(request):
            from serve import errors

            return errors.csrf_error_page(request)
        engine = engine_factory()
        form = await request.form()
        chosen = [key for key in form.getlist("metric") if key in _METRIC_BY_KEY]
        keep_metrics: dict[str, str] = {"metrics_present": "1"}
        if chosen:
            keep_metrics["metrics"] = ",".join(chosen)
        try:
            result = await run_in_threadpool(backfill_countries_exhaustive, engine, run_id)
        except Exception as exc:  # a token/API failure must surface, not vanish
            query = urlencode(
                {
                    **keep_metrics,
                    "country_backfill": "error",
                    "message": f"{type(exc).__name__}: {exc}"[:240],
                }
            )
            return RedirectResponse(f"/analysis/{run_id}?{query}", status_code=303)
        query = urlencode(
            {
                **keep_metrics,
                "country_backfill": "ok",
                **{key: str(value) for key, value in result.items()},
            }
        )
        return RedirectResponse(f"/analysis/{run_id}?{query}", status_code=303)
