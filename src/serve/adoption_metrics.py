"""Statistically explicit stratified adoption metrics.

Every rate returned here carries its numerator, denominator, percentage, and
95% Wilson interval. Missing metadata and unobserved channels are never
silently converted to zero.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from serve.analysis_dataset import AnalysisDataset, AnalysisRepo, load_analysis_dataset

SMALL_STRATUM_N = 10
STUDY_CUTOFF = date(2025, 1, 1)


def _mappings(engine: Engine, statement: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(text(statement), params).mappings()]


def _pct(part: int, whole: int) -> float | None:
    if whole <= 0:
        return None
    return round(part / whole * 100, 1)


def _wilson(part: int, whole: int) -> tuple[float | None, float | None]:
    if whole <= 0:
        return None, None
    z = 1.959963984540054
    proportion = part / whole
    denominator = 1 + (z * z / whole)
    centre = (proportion + z * z / (2 * whole)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / whole + z * z / (4 * whole * whole))
        / denominator
    )
    return round(max(0.0, centre - margin) * 100, 1), round(min(1.0, centre + margin) * 100, 1)


def _rate(part: int, whole: int) -> dict[str, Any]:
    low, high = _wilson(part, whole)
    return {
        "count": part,
        "eligible": whole,
        "percent": _pct(part, whole),
        "ci_low": low,
        "ci_high": high,
    }


def _unavailable(alias: str = "i") -> str:
    return (
        f"CASE WHEN jsonb_typeof({alias}.detection->'unavailable') = 'boolean' "
        f"THEN ({alias}.detection->>'unavailable')::boolean ELSE false END"
    )


def _with_agent(alias: str = "i") -> str:
    # ``Generic`` is a shared marker (AGENTS.md, "AI Assistant", "ai-generated"),
    # not a product, so it must never make a repository count as adopted.
    return (
        f"CASE WHEN jsonb_typeof({alias}.detection->'agents') = 'array' THEN EXISTS ("
        f"SELECT 1 FROM jsonb_array_elements_text({alias}.detection->'agents') AS a(agent)"
        f" WHERE a.agent <> 'Generic') ELSE false END"
    )


def _readable(alias: str = "i") -> str:
    channels = f"{alias}.detection->'channels'"
    return (
        f"{alias}.detection IS NOT NULL AND NOT ({_unavailable(alias)}) "
        f"AND CASE WHEN jsonb_typeof({channels}) = 'object' THEN "
        f"EXISTS (SELECT 1 FROM jsonb_each_text({channels})) "
        "AND NOT EXISTS (SELECT 1 FROM jsonb_each_text("
        f"{channels}) channel_status WHERE channel_status.value <> 'ok') "
        "ELSE false END"
    )


def _commit_ratio(alias: str = "i") -> str:
    value = f"({alias}.detection->>'commit_ratio')::double precision"
    return (
        f"CASE WHEN jsonb_typeof({alias}.detection->'commit_ratio') = 'number' "
        f"AND {value} BETWEEN 0 AND 1 THEN {value} ELSE NULL END"
    )


def _history_coverage(alias: str = "i") -> str:
    value = f"({alias}.detection->>'history_coverage')::double precision"
    return (
        f"CASE WHEN jsonb_typeof({alias}.detection->'history_coverage') = 'number' "
        f"AND {value} BETWEEN 0 AND 1 THEN {value} ELSE NULL END"
    )


def _history_complete(alias: str = "i") -> str:
    return (
        f"CASE WHEN jsonb_typeof({alias}.detection->'history_complete') = 'boolean' "
        f"THEN ({alias}.detection->>'history_complete')::boolean ELSE NULL END"
    )


def _file_observed(alias: str = "i") -> str:
    return (
        f"CASE WHEN jsonb_typeof({alias}.detection->'channels') = 'object' "
        f"AND {alias}.detection->'channels'->>'file' = 'ok' THEN true ELSE false END"
    )


def _structural_signal(alias: str = "i") -> str:
    return (
        "EXISTS (SELECT 1 FROM detection_evidence e "
        f"WHERE e.run_id = {alias}.run_id AND e.repo_id = {alias}.repo_id "
        "AND e.channel = 'file' "
        "AND COALESCE(e.evidence->>'source', 'tree') <> 'gitignore')"
    )


def _commit_count() -> str:
    legacy = (
        "CASE WHEN jsonb_typeof(s.virtuals->'commit_count') = 'number' "
        "AND (s.virtuals->>'commit_count') ~ '^[0-9]+$' "
        "AND (s.virtuals->>'commit_count')::numeric <= 2147483647 "
        "THEN (s.virtuals->>'commit_count')::integer ELSE NULL END"
    )
    return f"COALESCE(i.commit_count, s.commit_count, {legacy})"


def _common_select() -> str:
    return (
        f"{_readable()} AS readable, "
        f"{_with_agent()} AS with_agent, "
        f"{_file_observed()} AS file_observed, "
        f"{_structural_signal()} AS structural_signal, "
        f"{_commit_ratio()} AS ratio"
    )


def _snapshot_join() -> str:
    return (
        " FROM run_items i JOIN runs dr ON dr.id = i.run_id"
        " LEFT JOIN run_items s"
        " ON s.run_id = dr.source_run_id AND s.repo_id = i.repo_id"
    )


def _finalize(row: dict[str, Any]) -> dict[str, Any]:
    repos = int(row.get("repos") or 0)
    readable = int(row.get("readable") or 0)
    with_agent = int(row.get("with_agent") or 0)
    file_observed = int(row.get("file_observed") or 0)
    structural = int(row.get("structural") or 0)
    history_observed = int(row.get("history_observed") or 0)
    recent_adopters = int(row.get("recent_adopters") or 0)
    median = row.get("median_ratio")
    return {
        **row,
        "repos": repos,
        "readable": readable,
        "with_agent": with_agent,
        "file_observed": file_observed,
        "structural": structural,
        "history_observed": history_observed,
        "recent_adopters": recent_adopters,
        "adoption": _rate(with_agent, readable),
        "file_adoption": _rate(structural, file_observed),
        "recent_adoption": _rate(recent_adopters, history_observed),
        "median_ratio": round(float(median) * 100, 1) if median is not None else None,
        "small_sample": (
            readable < SMALL_STRATUM_N
            or 0 < file_observed < SMALL_STRATUM_N
            or 0 < history_observed < SMALL_STRATUM_N
        ),
    }


_AGGREGATES = (
    "count(*) AS repos,"
    " count(*) FILTER (WHERE readable) AS readable,"
    " count(*) FILTER (WHERE readable AND with_agent) AS with_agent,"
    " count(*) FILTER (WHERE readable AND file_observed) AS file_observed,"
    " count(*) FILTER (WHERE readable AND file_observed AND structural_signal) AS structural,"
    " count(*) FILTER (WHERE readable AND ratio IS NOT NULL) AS history_observed,"
    " count(*) FILTER (WHERE readable AND ratio > 0) AS recent_adopters,"
    " percentile_cont(0.5) WITHIN GROUP (ORDER BY ratio)"
    " FILTER (WHERE readable AND ratio > 0) AS median_ratio"
)


def star_tiers(engine: Engine, run_id: int) -> list[dict[str, Any]]:
    stars = "COALESCE(i.stargazers, s.stargazers)"
    rows = _mappings(
        engine,
        "WITH base AS (SELECT"
        f" CASE WHEN {stars} IS NULL OR {stars} < 0 THEN 'Unknown'"
        f"      WHEN {stars} = 0 THEN '0'"
        f"      WHEN {stars} < 10 THEN '1–9'"
        f"      WHEN {stars} < 100 THEN '10–99'"
        f"      WHEN {stars} < 1000 THEN '100–999'"
        f"      WHEN {stars} < 10000 THEN '1,000–9,999'"
        "      ELSE '≥10,000' END AS bucket,"
        f" CASE WHEN {stars} IS NULL OR {stars} < 0 THEN 99"
        f"      WHEN {stars} = 0 THEN 0"
        f"      WHEN {stars} < 10 THEN 1"
        f"      WHEN {stars} < 100 THEN 2"
        f"      WHEN {stars} < 1000 THEN 3"
        f"      WHEN {stars} < 10000 THEN 4 ELSE 5 END AS bucket_order, "
        + _common_select()
        + _snapshot_join()
        + " WHERE i.run_id = :run)"
        " SELECT bucket, min(bucket_order) AS bucket_order, "
        + _AGGREGATES
        + " FROM base GROUP BY bucket ORDER BY bucket_order",
        {"run": run_id},
    )
    return [_finalize(row) for row in rows]


def commit_depth(engine: Engine, run_id: int) -> list[dict[str, Any]]:
    count_sql = _commit_count()
    rows = _mappings(
        engine,
        "WITH base AS (SELECT"
        f" CASE WHEN {count_sql} IS NULL THEN 'Unknown'"
        f"      WHEN {count_sql} = 0 THEN '0'"
        f"      WHEN {count_sql} < 20 THEN '1–19'"
        f"      WHEN {count_sql} < 100 THEN '20–99'"
        f"      WHEN {count_sql} < 500 THEN '100–499'"
        f"      WHEN {count_sql} < 2500 THEN '500–2,499'"
        f"      WHEN {count_sql} < 10000 THEN '2,500–9,999'"
        "      ELSE '≥10,000' END AS bucket,"
        f" CASE WHEN {count_sql} IS NULL THEN 99"
        f"      WHEN {count_sql} = 0 THEN 0"
        f"      WHEN {count_sql} < 20 THEN 1"
        f"      WHEN {count_sql} < 100 THEN 2"
        f"      WHEN {count_sql} < 500 THEN 3"
        f"      WHEN {count_sql} < 2500 THEN 4"
        f"      WHEN {count_sql} < 10000 THEN 5 ELSE 6 END AS bucket_order, "
        + _common_select()
        + ", "
        + _history_coverage()
        + " AS coverage, "
        + _history_complete()
        + " AS complete"
        + _snapshot_join()
        + " WHERE i.run_id = :run)"
        " SELECT bucket, min(bucket_order) AS bucket_order, "
        + _AGGREGATES
        + ", count(*) FILTER (WHERE readable AND coverage IS NOT NULL) AS coverage_observed"
        " , count(*) FILTER (WHERE readable AND coverage IS NOT NULL AND complete) AS full_history"
        " , percentile_cont(0.5) WITHIN GROUP (ORDER BY coverage)"
        " FILTER (WHERE readable AND coverage IS NOT NULL) AS median_coverage"
        " FROM base GROUP BY bucket ORDER BY bucket_order",
        {"run": run_id},
    )
    result = []
    for raw in rows:
        row = _finalize(raw)
        coverage_observed = int(raw.get("coverage_observed") or 0)
        full_history = int(raw.get("full_history") or 0)
        median = raw.get("median_coverage")
        row.update(
            {
                "coverage_observed": coverage_observed,
                "full_history": full_history,
                "full_coverage": _rate(full_history, coverage_observed),
                "median_coverage": round(float(median) * 100, 1) if median is not None else None,
            }
        )
        result.append(row)
    return result


def creation_cohorts(engine: Engine, run_id: int, *, cutoff: date = STUDY_CUTOFF) -> dict[str, Any]:
    rows = _mappings(
        engine,
        "WITH base AS (SELECT"
        " CASE WHEN COALESCE(i.repo_created_at, s.repo_created_at) IS NULL THEN 'Unknown'"
        "      WHEN COALESCE(i.repo_created_at, s.repo_created_at) < :cutoff"
        "        THEN 'Existing before cutoff'"
        "      ELSE to_char(date_trunc('quarter',"
        "        COALESCE(i.repo_created_at, s.repo_created_at)), 'YYYY-\"Q\"Q') END AS cohort,"
        " CASE WHEN COALESCE(i.repo_created_at, s.repo_created_at) IS NULL THEN 'unknown'"
        "      WHEN COALESCE(i.repo_created_at, s.repo_created_at) < :cutoff"
        "        THEN 'installed_base' ELSE 'new' END AS cohort_kind,"
        " CASE WHEN COALESCE(i.repo_created_at, s.repo_created_at) IS NULL THEN 999999"
        "      WHEN COALESCE(i.repo_created_at, s.repo_created_at) < :cutoff THEN 0"
        "      ELSE extract(year FROM COALESCE(i.repo_created_at, s.repo_created_at))::int * 4"
        "        + extract(quarter FROM COALESCE(i.repo_created_at, s.repo_created_at))::int"
        "      END AS cohort_order, "
        + _common_select()
        + _snapshot_join()
        + " WHERE i.run_id = :run)"
        " SELECT cohort, cohort_kind, min(cohort_order) AS cohort_order, "
        + _AGGREGATES
        + " FROM base GROUP BY cohort, cohort_kind ORDER BY cohort_order",
        {"run": run_id, "cutoff": cutoff},
    )
    return {"cutoff": cutoff.isoformat(), "rows": [_finalize(row) for row in rows]}


def language_adoption(engine: Engine, run_id: int) -> list[dict[str, Any]]:
    language_sql = (
        "COALESCE(NULLIF(btrim(i.language), ''), NULLIF(btrim(s.language), ''), 'Unknown')"
    )
    rows = _mappings(
        engine,
        "WITH base AS (SELECT "
        + language_sql
        + " AS language_name, "
        + _common_select()
        + _snapshot_join()
        + " WHERE i.run_id = :run)"
        " SELECT language_name, " + _AGGREGATES + " FROM base GROUP BY language_name"
        " ORDER BY language_name = 'Unknown', readable DESC, language_name",
        {"run": run_id},
    )
    agent_rows = _mappings(
        engine,
        "SELECT "
        + language_sql
        + " AS language_name, a.agent, count(*) AS repos"
        + _snapshot_join()
        + " CROSS JOIN LATERAL jsonb_array_elements_text("
        " CASE WHEN jsonb_typeof(i.detection->'agents') = 'array'"
        " THEN i.detection->'agents' ELSE '[]'::jsonb END) AS a(agent)"
        " WHERE i.run_id = :run AND a.agent <> 'Generic' AND "
        + _readable()
        + " GROUP BY language_name, a.agent ORDER BY language_name, repos DESC, a.agent",
        {"run": run_id},
    )
    top: dict[str, tuple[int, str]] = {}
    for raw in agent_rows:
        language = str(raw["language_name"])
        candidate = (int(raw["repos"] or 0), str(raw["agent"]))
        current = top.get(language)
        if current is None or (-candidate[0], candidate[1]) < (-current[0], current[1]):
            top[language] = candidate
    result = []
    for raw in rows:
        row = _finalize(raw)
        leader = top.get(str(raw["language_name"]))
        row["language"] = str(raw["language_name"])
        row["top_agent"] = leader[1] if leader else None
        row["top_agent_share"] = (
            _rate(leader[0], row["readable"]) if leader else _rate(0, row["readable"])
        )
        result.append(row)
    return result


def quantile(values: Iterable[float], probability: float) -> float | None:
    """Return the R-7/NumPy-linear sample quantile, deterministically.

    The function intentionally has no optional statistics dependency. Values
    must already be valid finite measurements; callers define eligibility.
    """

    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between 0 and 1")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _percent(value: float | None) -> float | None:
    return round(value * 100, 1) if value is not None else None


def _summarize_repos(rows: list[AnalysisRepo], dataset: AnalysisDataset) -> dict[str, Any]:
    complete = [row for row in rows if row.complete_channels]
    file_observed = [row for row in rows if row.file_observed]
    history_observed = (
        [row for row in rows if row.readable and row.commit_ratio is not None]
        if dataset.history_applicable
        else []
    )
    recent = [row for row in history_observed if (row.commit_ratio or 0.0) > 0.0]
    positive = [float(row.commit_ratio) for row in recent if row.commit_ratio is not None]
    with_agent = sum(bool(row.agents) for row in complete)
    structural = sum(row.structural_signal for row in file_observed)
    zero_recent = sum(row.commit_ratio == 0.0 for row in history_observed)
    pervasive = sum(row.commit_ratio is not None and row.commit_ratio >= 0.20 for row in recent)
    median = quantile(positive, 0.50)
    return {
        "repos": len(rows),
        "frame_readable": sum(row.readable for row in rows),
        # Compatibility: existing templates call the complete-channel
        # denominator "readable". The explicit frame count above removes the
        # ambiguity for diagnostics and future copy.
        "readable": len(complete),
        "with_agent": with_agent,
        "file_observed": len(file_observed),
        "structural": structural,
        "history_observed": len(history_observed),
        "recent_adopters": len(recent),
        "zero_recent": zero_recent,
        "pervasive": pervasive,
        "adoption": _rate(with_agent, len(complete)),
        "file_adoption": _rate(structural, len(file_observed)),
        "recent_adoption": _rate(len(recent), len(history_observed)),
        "zero_recent_rate": _rate(zero_recent, len(history_observed)),
        "pervasive_rate": _rate(pervasive, len(recent)),
        "median_ratio": _percent(median),
        "ratio_p25": _percent(quantile(positive, 0.25)),
        "ratio_p50": _percent(median),
        "ratio_p75": _percent(quantile(positive, 0.75)),
        "ratio_p90": _percent(quantile(positive, 0.90)),
        "small_sample": (
            len(complete) < SMALL_STRATUM_N
            or 0 < len(file_observed) < SMALL_STRATUM_N
            or 0 < len(history_observed) < SMALL_STRATUM_N
        ),
    }


def star_bucket(value: int | None) -> tuple[str, int]:
    if value is None:
        return "Unknown", 99
    if value == 0:
        return "0", 0
    if value < 10:
        return "1–9", 1
    if value < 100:
        return "10–99", 2
    if value < 1_000:
        return "100–999", 3
    if value < 10_000:
        return "1,000–9,999", 4
    return "≥10,000", 5


def commit_bucket(value: int | None) -> tuple[str, int]:
    if value is None:
        return "Unknown", 99
    if value == 0:
        return "0", 0
    if value < 20:
        return "1–19", 1
    if value < 100:
        return "20–99", 2
    if value < 500:
        return "100–499", 3
    if value < 2_500:
        return "500–2,499", 4
    if value < 10_000:
        return "2,500–9,999", 5
    return "≥10,000", 6


def cohort_bucket(value: datetime | None, cutoff: date = STUDY_CUTOFF) -> tuple[str, str, int]:
    if value is None:
        return "Unknown", "unknown", 999_999
    naive_date = value.date()
    if naive_date < cutoff:
        return "Existing before cutoff", "installed_base", 0
    quarter = (value.month - 1) // 3 + 1
    return f"{value.year}-Q{quarter}", "new", value.year * 4 + quarter


def _grouped(
    rows: tuple[AnalysisRepo, ...],
    key,
) -> list[tuple[tuple, list[AnalysisRepo]]]:
    groups: defaultdict[tuple, list[AnalysisRepo]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return sorted(groups.items(), key=lambda item: item[0][-1])


def _star_rows(dataset: AnalysisDataset) -> list[dict[str, Any]]:
    result = []
    for (label, order), rows in _grouped(dataset.rows, lambda row: star_bucket(row.stars)):
        result.append({"bucket": label, "bucket_order": order, **_summarize_repos(rows, dataset)})
    return result


def _commit_rows(dataset: AnalysisDataset) -> list[dict[str, Any]]:
    result = []
    for (label, order), rows in _grouped(dataset.rows, lambda row: commit_bucket(row.commit_count)):
        summary = _summarize_repos(rows, dataset)
        observed = (
            [
                row.history_coverage
                for row in rows
                if row.readable and row.history_coverage is not None
            ]
            if dataset.history_applicable
            else []
        )
        full = (
            sum(
                row.readable and row.history_coverage is not None and row.history_complete is True
                for row in rows
            )
            if dataset.history_applicable
            else 0
        )
        summary.update(
            {
                "coverage_observed": len(observed),
                "full_history": full,
                "full_coverage": _rate(full, len(observed)),
                "median_coverage": _percent(quantile(observed, 0.50)),
            }
        )
        result.append({"bucket": label, "bucket_order": order, **summary})
    return result


def _cohort_rows(dataset: AnalysisDataset, cutoff: date) -> dict[str, Any]:
    result = []
    # TODO: repositories without a creation date are CSV-import placeholders
    # (synthetic negative ids). Hydrate them from GitHub so they can rejoin
    # the cohorts instead of being excluded here.
    excluded_unknown = sum(row.repo_created_at is None for row in dataset.rows)
    for (label, kind, order), rows in _grouped(
        dataset.rows, lambda row: cohort_bucket(row.repo_created_at, cutoff)
    ):
        if kind == "unknown":
            continue
        result.append(
            {
                "cohort": label,
                "cohort_kind": kind,
                "cohort_order": order,
                **_summarize_repos(rows, dataset),
            }
        )
    return {
        "cutoff": cutoff.isoformat(),
        "rows": result,
        "excluded_unknown": excluded_unknown,
    }


def _language_rows(dataset: AnalysisDataset) -> list[dict[str, Any]]:
    groups: defaultdict[str, list[AnalysisRepo]] = defaultdict(list)
    for row in dataset.rows:
        groups[row.language].append(row)
    result = []
    for language, rows in groups.items():
        summary = _summarize_repos(rows, dataset)
        agents: Counter[str] = Counter(
            agent for row in rows if row.complete_channels for agent in row.agents
        )
        leader = min(agents, key=lambda agent: (-agents[agent], agent)) if agents else None
        result.append(
            {
                "language_name": language,
                "language": language,
                **summary,
                "top_agent": leader,
                "top_agent_share": (
                    _rate(agents[leader], summary["readable"])
                    if leader
                    else _rate(0, summary["readable"])
                ),
            }
        )
    return sorted(
        result,
        key=lambda row: (
            row["language"] == "Unknown",
            -row["readable"],
            row["language"],
        ),
    )


def all_stratified_metrics(
    engine: Engine,
    run_id: int,
    *,
    dataset: AnalysisDataset | None = None,
    cutoff: date = STUDY_CUTOFF,
) -> tuple[AnalysisDataset, dict[str, Any]]:
    """Compute all four stratified measures from one repository/evidence load."""

    resolved = dataset or load_analysis_dataset(engine, run_id)
    return resolved, {
        "birth_cohort": _cohort_rows(resolved, cutoff),
        "star_tiers": _star_rows(resolved),
        "commit_depth": _commit_rows(resolved),
        "language_adoption": _language_rows(resolved),
    }
