"""Validity, robustness, clustering, distribution, and wealth diagnostics.

All functions operate on the single frozen-run view from
``serve.analysis_dataset``.  The pure statistical helpers are dependency-free
and deterministic so their behavior can be tested at edge cases and replayed.
"""

from __future__ import annotations

import bisect
import hashlib
import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

from serve.adoption_metrics import (
    STUDY_CUTOFF,
    _rate,
    cohort_bucket,
    commit_bucket,
    quantile,
    star_bucket,
)
from serve.analysis_dataset import AnalysisDataset, AnalysisRepo
from serve.countries import UNKNOWN_COUNTRY, country_name

PERVASIVE_RATIO = 0.20
OWNER_BOOTSTRAP_REPLICATES = 1_000
WEALTH_BOOTSTRAP_REPLICATES = 2_000
MIN_OWNER_BOOTSTRAP_CLUSTERS = 10
MIN_WEALTH_COEFFICIENT_COUNTRIES = 3
MIN_WEALTH_ROBUSTNESS_COUNTRIES = 5

REPOSITORY_AGENT_BANDS = (
    ("1", 1, 1),
    ("2–5", 2, 5),
    ("6–9", 6, 9),
    ("10+", 10, None),
)
OWNER_AGENT_BANDS = (
    ("1", 1, 1),
    ("2", 2, 2),
    ("3", 3, 3),
    ("4–6", 4, 6),
    ("7–9", 7, 9),
    ("10+", 10, None),
)


class AnalysisInvariantError(RuntimeError):
    """Raised when an aggregate fails an exact reconciliation rule."""


def _seed(*parts: object) -> int:
    digest = hashlib.sha256(":".join(str(part) for part in parts).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _rounded(value: float | None, digits: int = 3) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(value, digits)


def _percent(value: float | None) -> float | None:
    return round(value * 100, 1) if value is not None else None


def _not_applicable(reason: str | None = None) -> dict[str, Any]:
    return {
        "applicable": False,
        "count": None,
        "eligible": None,
        "percent": None,
        "ci_low": None,
        "ci_high": None,
        "reason": reason,
    }


def _applicable_rate(count: int, total: int) -> dict[str, Any]:
    return {"applicable": True, **_rate(count, total)}


def band_for(count: int, bands: Sequence[tuple[str, int, int | None]]) -> str:
    if count < 1:
        raise ValueError("agent multiplicity bands require a positive count")
    for label, low, high in bands:
        if count >= low and (high is None or count <= high):
            return label
    raise AnalysisInvariantError(f"no multiplicity band contains {count}")


def nearest_rank(values: Sequence[datetime], probability: float) -> datetime | None:
    """Return the nearest-rank empirical quantile (ceil(p*n), minimum rank 1)."""

    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be between 0 and 1")
    if not values:
        return None
    ordered = sorted(values)
    rank = max(1, math.ceil(probability * len(ordered)))
    return ordered[rank - 1]


def _parse_moment(value: str | None) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if candidate.endswith(("Z", "z")):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _date(value: datetime | None) -> str | None:
    return value.date().isoformat() if value is not None else None


def evidence_robustness(dataset: AnalysisDataset) -> dict[str, Any]:
    eligible = [row for row in dataset.rows if row.complete_channels]
    broad = sum(row.broad_signal for row in eligible)
    behavioral = sum(row.behavioral_signal for row in eligible)
    corroborated = sum(row.corroborated_signal for row in eligible)
    structural_only = sum(row.structural_only for row in eligible)
    strict = sum(row.strict_signal for row in eligible)
    documented = sum(bool(row.agents) for row in eligible)
    broad_without_document = sum(row.broad_signal and not row.agents for row in eligible)
    document_without_broad = sum(bool(row.agents) and not row.broad_signal for row in eligible)
    definitions = {
        "broad": _applicable_rate(broad, len(eligible)),
        "behavioral": (
            _applicable_rate(behavioral, len(eligible))
            if dataset.strict_applicable
            else _not_applicable()
        ),
        "corroborated": (
            _applicable_rate(corroborated, len(eligible))
            if dataset.strict_applicable
            else _not_applicable()
        ),
        "strict": (
            _applicable_rate(strict, len(eligible))
            if dataset.strict_applicable
            else _not_applicable()
        ),
        "structural_only": (
            _applicable_rate(structural_only, len(eligible))
            if dataset.file_applicable
            else _not_applicable()
        ),
    }
    sensitivity_gap = None
    if definitions["broad"]["percent"] is not None and definitions["strict"]["percent"] is not None:
        sensitivity_gap = round(
            definitions["broad"]["percent"] - definitions["strict"]["percent"], 1
        )
    return {
        "eligible": len(eligible),
        "selected_channels": list(dataset.selected_channels),
        "channel_selection_source": dataset.channel_selection_source,
        "definitions": definitions,
        "corroboration_among_broad": _applicable_rate(corroborated, broad),
        "sensitivity_gap_pp": sensitivity_gap,
        "documented_detected": documented,
        "broad_without_document": broad_without_document,
        "document_without_broad": document_without_broad,
    }


def _coverage_summary(
    rows: list[AnalysisRepo], dataset: AnalysisDataset, *, history_recorded: bool
) -> dict[str, Any]:
    total = len(rows)
    history_reason = None
    if not dataset.history_applicable:
        history_reason = "History channel was not selected in this run."
    elif not history_recorded:
        history_reason = "History coverage was not recorded by this detection run."
    return {
        "readable": _applicable_rate(sum(row.readable for row in rows), total),
        "complete_channels": _applicable_rate(sum(row.complete_channels for row in rows), total),
        "file_scan": (
            _applicable_rate(sum(row.file_observed for row in rows), total)
            if dataset.file_applicable
            else _not_applicable("File channel was not selected in this run.")
        ),
        "commit_denominator": (
            _applicable_rate(
                sum(row.readable and row.commit_ratio is not None for row in rows), total
            )
            if dataset.history_applicable
            else _not_applicable("History channel was not selected in this run.")
        ),
        "history_observed": (
            _applicable_rate(
                sum(row.readable and row.history_coverage is not None for row in rows),
                total,
            )
            if history_reason is None
            else _not_applicable(history_reason)
        ),
        "full_history": (
            _applicable_rate(
                sum(
                    row.readable
                    and row.history_coverage is not None
                    and row.history_complete is True
                    for row in rows
                ),
                total,
            )
            if history_reason is None
            else _not_applicable(history_reason)
        ),
    }


def _dimension_rows(
    dataset: AnalysisDataset,
    key,
    *,
    order,
    history_recorded: bool,
) -> list[dict[str, Any]]:
    groups: defaultdict[tuple[str, str, int], list[AnalysisRepo]] = defaultdict(list)
    for row in dataset.rows:
        groups[key(row)].append(row)
    result = [
        {
            "key": group_key,
            "label": label,
            "order": numeric_order,
            "repos": len(rows),
            "coverage": _coverage_summary(rows, dataset, history_recorded=history_recorded),
        }
        for (group_key, label, numeric_order), rows in groups.items()
    ]
    return sorted(result, key=order)


def observation_coverage(dataset: AnalysisDataset) -> dict[str, Any]:
    history_recorded = dataset.history_recorded
    country_rows = _dimension_rows(
        dataset,
        lambda row: (
            row.country_iso,
            (
                "Unknown"
                if row.country_iso == UNKNOWN_COUNTRY
                else (country_name(row.country_iso) or row.country_iso)
            ),
            0,
        ),
        order=lambda row: (
            row["key"] == UNKNOWN_COUNTRY,
            -row["repos"],
            row["label"],
        ),
        history_recorded=history_recorded,
    )
    language_rows = _dimension_rows(
        dataset,
        lambda row: (row.language, row.language, 0),
        order=lambda row: (
            row["key"] == "Unknown",
            -row["repos"],
            row["label"],
        ),
        history_recorded=history_recorded,
    )
    star_rows = _dimension_rows(
        dataset,
        lambda row: (
            star_bucket(row.stars)[0],
            star_bucket(row.stars)[0],
            star_bucket(row.stars)[1],
        ),
        order=lambda row: (row["order"], row["label"]),
        history_recorded=history_recorded,
    )
    commit_rows = _dimension_rows(
        dataset,
        lambda row: (
            commit_bucket(row.commit_count)[0],
            commit_bucket(row.commit_count)[0],
            commit_bucket(row.commit_count)[1],
        ),
        order=lambda row: (row["order"], row["label"]),
        history_recorded=history_recorded,
    )
    return {
        "measures": [
            {"key": "readable", "label": "Readable"},
            {"key": "complete_channels", "label": "Complete channels"},
            {"key": "file_scan", "label": "Successful file scan"},
            {"key": "commit_denominator", "label": "Valid commit denominator"},
            {"key": "history_observed", "label": "History coverage observed"},
            {"key": "full_history", "label": "Full default-branch history"},
        ],
        "dimensions": [
            {"key": "country", "label": "Country", "rows": country_rows},
            {"key": "language", "label": "Language", "rows": language_rows},
            {"key": "stars", "label": "Star tier", "rows": star_rows},
            {"key": "commits", "label": "Commit tier", "rows": commit_rows},
        ],
    }


def _bootstrap_interval(values: list[float]) -> dict[str, float | None]:
    return {
        "low": _rounded(quantile(values, 0.025), 1),
        "high": _rounded(quantile(values, 0.975), 1),
    }


def cluster_bootstrap(
    clusters: Sequence[tuple[int, int]],
    *,
    seed: int,
    replicates: int = OWNER_BOOTSTRAP_REPLICATES,
) -> dict[str, Any] | None:
    """Resample owner clusters and return repo- and owner-weighted intervals.

    Each tuple is ``(eligible repositories, adopted repositories)``. Owners are
    sampled with replacement; every repository in a sampled owner cluster moves
    together, preserving within-owner dependence.
    """

    if len(clusters) < MIN_OWNER_BOOTSTRAP_CLUSTERS or replicates < 1:
        return None
    rng = random.Random(seed)
    repo_estimates: list[float] = []
    owner_estimates: list[float] = []
    count = len(clusters)
    for _ in range(replicates):
        eligible = 0
        adopted = 0
        adopted_owners = 0
        for _draw in range(count):
            cluster = clusters[rng.randrange(count)]
            eligible += cluster[0]
            adopted += cluster[1]
            adopted_owners += cluster[1] > 0
        if eligible:
            repo_estimates.append(adopted / eligible * 100)
        owner_estimates.append(adopted_owners / count * 100)
    return {
        "method": "owner clusters sampled with replacement",
        "replicates": replicates,
        "repo_weighted": _bootstrap_interval(repo_estimates),
        "owner_weighted": _bootstrap_interval(owner_estimates),
    }


def _concentration(counts: Iterable[int]) -> dict[str, float | None]:
    ordered = sorted((int(value) for value in counts if value > 0), reverse=True)
    total = sum(ordered)
    return {
        "top_1_percent": round(ordered[0] / total * 100, 1) if ordered and total else None,
        "top_5_percent": round(sum(ordered[:5]) / total * 100, 1) if total else None,
    }


def owner_cluster_robustness(dataset: AnalysisDataset) -> dict[str, Any]:
    output = []
    for account_type in ("User", "Organization"):
        represented = {
            row.owner_id
            for row in dataset.rows
            if row.owner_type == account_type and row.owner_id is not None
        }
        clusters: defaultdict[int, list[int]] = defaultdict(lambda: [0, 0])
        missing_owner_repos = 0
        for row in dataset.rows:
            if not row.complete_channels:
                continue
            if row.owner_id is None:
                missing_owner_repos += 1
                continue
            if row.owner_type != account_type:
                continue
            clusters[row.owner_id][0] += 1
            clusters[row.owner_id][1] += int(row.broad_signal)
        values = [(value[0], value[1]) for value in clusters.values()]
        eligible_repos = sum(value[0] for value in values)
        adopted_repos = sum(value[1] for value in values)
        adopted_owners = sum(value[1] > 0 for value in values)
        repo_counts = [value[0] for value in values]
        adopted_counts = [value[1] for value in values]
        bootstrap = cluster_bootstrap(
            values,
            seed=_seed(dataset.run_id, "owner-cluster", account_type),
        )
        output.append(
            {
                "account_type": account_type,
                "represented_owners": len(represented),
                "eligible_owners": len(values),
                "adopted_owners": adopted_owners,
                "eligible_repos": eligible_repos,
                "adopted_repos": adopted_repos,
                "missing_owner_repos": missing_owner_repos,
                "repo_weighted_adoption": _applicable_rate(adopted_repos, eligible_repos),
                "owner_weighted_adoption": _applicable_rate(adopted_owners, len(values)),
                "repos_per_owner": {
                    "mean": round(eligible_repos / len(values), 2) if values else None,
                    "median": _rounded(quantile(repo_counts, 0.50), 1),
                    "maximum": max(repo_counts) if repo_counts else None,
                },
                "eligible_repo_concentration": _concentration(repo_counts),
                "adopted_repo_concentration": _concentration(adopted_counts),
                "cluster_bootstrap": bootstrap,
            }
        )
    return {"account_types": output, "minimum_bootstrap_owners": MIN_OWNER_BOOTSTRAP_CLUSTERS}


def robust_debuts(dataset: AnalysisDataset) -> dict[str, Any]:
    repos_by_agent: defaultdict[str, list[AnalysisRepo]] = defaultdict(list)
    for row in dataset.rows:
        for agent in row.agents:
            repos_by_agent[agent].append(row)
    result = []
    for agent, rows in repos_by_agent.items():
        moments = [moment for row in rows if (moment := _parse_moment(row.first_signal_at))]
        created = [row.repo_created_at for row in rows if row.repo_created_at is not None]
        result.append(
            {
                "agent": agent,
                "earliest_signal": _date(nearest_rank(moments, 0.0)),
                "signal_p0": _date(nearest_rank(moments, 0.0)),
                "signal_p10": _date(nearest_rank(moments, 0.10)),
                "signal_p50": _date(nearest_rank(moments, 0.50)),
                "earliest_repo_created": _date(min(created)) if created else None,
                "repos": len(rows),
                "dated_repos": len(moments),
                "dated_coverage": _applicable_rate(len(moments), len(rows)),
            }
        )
    return {
        "quantile_method": "nearest-rank empirical date quantiles",
        "rows": sorted(
            result,
            key=lambda row: (
                row["signal_p10"] is None,
                row["signal_p10"] or "",
                -row["repos"],
                row["agent"],
            ),
        ),
    }


def _intensity_summary(rows: Sequence[AnalysisRepo]) -> dict[str, Any]:
    observed = [
        float(row.commit_ratio) for row in rows if row.readable and row.commit_ratio is not None
    ]
    positive = [value for value in observed if value > 0.0]
    zero = len(observed) - len(positive)
    pervasive = sum(value >= PERVASIVE_RATIO for value in positive)
    return {
        "repos": len(rows),
        "history_observed": len(observed),
        "recent_adopters": len(positive),
        "zero_recent": _applicable_rate(zero, len(observed)),
        "pervasive": _applicable_rate(pervasive, len(positive)),
        "p25": _percent(quantile(positive, 0.25)),
        "p50": _percent(quantile(positive, 0.50)),
        "p75": _percent(quantile(positive, 0.75)),
        "p90": _percent(quantile(positive, 0.90)),
    }


def _cdf(rows: Sequence[AnalysisRepo]) -> list[dict[str, float]]:
    positive = sorted(
        float(row.commit_ratio) * 100
        for row in rows
        if row.readable and row.commit_ratio is not None and row.commit_ratio > 0
    )
    if not positive:
        return []
    return [
        {
            "intensity": round(step / 2, 1),
            "cumulative": round(bisect.bisect_right(positive, step / 2) / len(positive) * 100, 1),
        }
        for step in range(0, 201)
    ]


def _intensity_group_members(
    dataset: AnalysisDataset, dimension: str
) -> list[tuple[str, int, list[AnalysisRepo]]]:
    groups: defaultdict[tuple[str, int], list[AnalysisRepo]] = defaultdict(list)
    for row in dataset.rows:
        if dimension == "country":
            label = (
                "Unknown"
                if row.country_iso == UNKNOWN_COUNTRY
                else (country_name(row.country_iso) or row.country_iso)
            )
            key = (label, 0)
        elif dimension == "language":
            key = (row.language, 0)
        elif dimension == "stars":
            key = star_bucket(row.stars)
        elif dimension == "commits":
            key = commit_bucket(row.commit_count)
        elif dimension == "cohort":
            label, _kind, order = cohort_bucket(row.repo_created_at, STUDY_CUTOFF)
            key = (label, order)
        else:
            raise ValueError(f"unknown intensity dimension: {dimension}")
        groups[key].append(row)
    result = [(label, order, rows) for (label, order), rows in groups.items()]
    if dimension in {"stars", "commits", "cohort"}:
        return sorted(result, key=lambda row: (row[1], row[0]))
    return sorted(
        result,
        key=lambda row: (
            row[0] == "Unknown",
            -sum(item.readable and item.commit_ratio is not None for item in row[2]),
            row[0],
        ),
    )


def _intensity_groups(dataset: AnalysisDataset, dimension: str) -> list[dict[str, Any]]:
    return [
        {"label": label, "order": order, **_intensity_summary(rows)}
        for label, order, rows in _intensity_group_members(dataset, dimension)
    ]


def _intensity_cdf_series(dataset: AnalysisDataset) -> list[dict[str, Any]]:
    labels = {
        "country": "Country",
        "language": "Language",
        "stars": "Star tier",
        "commits": "Commit tier",
        "cohort": "Creation cohort",
    }
    result = [
        {
            "key": "overall",
            "label": "All recent adopters",
            "dimension": "Overall",
            "points": _cdf(dataset.rows),
        }
    ]
    for dimension in ("stars", "commits", "cohort", "language", "country"):
        members = _intensity_group_members(dataset, dimension)
        if dimension in {"language", "country"}:
            members = sorted(
                members,
                key=lambda item: (
                    -sum(
                        row.readable and row.commit_ratio is not None and row.commit_ratio > 0
                        for row in item[2]
                    ),
                    item[0],
                ),
            )[:20]
        for label, _order, rows in members:
            points = _cdf(rows)
            if not points:
                continue
            result.append(
                {
                    "key": f"{dimension}:{label}",
                    "label": f"{labels[dimension]} · {label}",
                    "dimension": labels[dimension],
                    "points": points,
                }
            )
    return result


def adoption_intensity(dataset: AnalysisDataset) -> dict[str, Any]:
    if not dataset.history_applicable:
        return {
            "applicable": False,
            "pervasive_threshold_percent": PERVASIVE_RATIO * 100,
            "overall": {
                "repos": len(dataset.rows),
                "history_observed": 0,
                "recent_adopters": 0,
                "zero_recent": _not_applicable(),
                "pervasive": _not_applicable(),
                "p25": None,
                "p50": None,
                "p75": None,
                "p90": None,
            },
            "cdf": [],
            "cdf_series": [],
            "dimensions": [],
        }
    return {
        "applicable": True,
        "pervasive_threshold_percent": PERVASIVE_RATIO * 100,
        "overall": _intensity_summary(dataset.rows),
        "cdf": _cdf(dataset.rows),
        "cdf_series": _intensity_cdf_series(dataset),
        "dimensions": [
            {"key": dimension, "rows": _intensity_groups(dataset, dimension)}
            for dimension in ("country", "language", "stars", "commits", "cohort")
        ],
    }


def _exact_set_rows(
    counts: Counter[tuple[str, ...]], band_total: int, owner_total: int
) -> list[dict[str, Any]]:
    return [
        {
            "agents": list(agent_set),
            "set_key": " + ".join(agent_set),
            "count": count,
            "share_in_band": round(count / band_total * 100, 1) if band_total else None,
            "share_of_agent_owners": round(count / owner_total * 100, 1) if owner_total else None,
        }
        for agent_set, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def multi_agent_co_use(dataset: AnalysisDataset) -> dict[str, Any]:
    detected_rows = [row for row in dataset.rows if row.agents]
    repo_counts = Counter(
        band_for(len(row.agents), REPOSITORY_AGENT_BANDS) for row in detected_rows
    )
    complete_repo_counts = Counter(
        band_for(len(row.agents), REPOSITORY_AGENT_BANDS)
        for row in detected_rows
        if row.complete_channels
    )
    complete_frame = sum(row.complete_channels for row in dataset.rows)
    repository_bands = [
        {
            "band": label,
            "repos": repo_counts[label],
            "share_detected": _applicable_rate(repo_counts[label], len(detected_rows)),
            "share_complete_frame": _applicable_rate(complete_repo_counts[label], complete_frame),
        }
        for label, _low, _high in REPOSITORY_AGENT_BANDS
    ]
    if sum(row["repos"] for row in repository_bands) != len(detected_rows):
        raise AnalysisInvariantError("repository multiplicity bands do not reconcile")

    owner_results = []
    for account_type in ("User", "Organization"):
        owner_sets: defaultdict[int, set[str]] = defaultdict(set)
        represented: set[int] = set()
        for row in dataset.rows:
            if row.owner_type != account_type or row.owner_id is None:
                continue
            represented.add(row.owner_id)
            owner_sets[row.owner_id].update(row.agents)
        with_agents = {
            owner_id: tuple(sorted(agent_set))
            for owner_id, agent_set in owner_sets.items()
            if agent_set
        }
        band_counts: Counter[str] = Counter()
        exact: defaultdict[str, Counter[tuple[str, ...]]] = defaultdict(Counter)
        for agent_set in with_agents.values():
            band = band_for(len(agent_set), OWNER_AGENT_BANDS)
            band_counts[band] += 1
            exact[band][agent_set] += 1
        bands = []
        for label, _low, _high in OWNER_AGENT_BANDS:
            total = band_counts[label]
            rankings = _exact_set_rows(exact[label], total, len(with_agents))
            if sum(row["count"] for row in rankings) != total:
                raise AnalysisInvariantError(
                    f"{account_type} exact agent sets do not reconcile in band {label}"
                )
            bands.append(
                {
                    "band": label,
                    "owners": total,
                    "share": _applicable_rate(total, len(with_agents)),
                    "rankings": rankings,
                }
            )
        if sum(row["owners"] for row in bands) != len(with_agents):
            raise AnalysisInvariantError(f"{account_type} owner bands do not reconcile")
        owner_results.append(
            {
                "account_type": account_type,
                "represented_owners": len(represented),
                "owners_with_agents": len(with_agents),
                "owners_without_agents": len(represented) - len(with_agents),
                "bands": bands,
            }
        )
    return {
        "repositories": {
            "frame_repos": len(dataset.rows),
            "complete_frame_repos": sum(row.complete_channels for row in dataset.rows),
            "detected_repos": len(detected_rows),
            "bands": repository_bands,
        },
        "owners": owner_results,
    }


def pearson(points: Sequence[tuple[float, float]]) -> float | None:
    if len(points) < 3:
        return None
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    covariance = sum((x - mean_x) * (y - mean_y) for x, y in points)
    variance_x = sum((x - mean_x) ** 2 for x, _ in points)
    variance_y = sum((y - mean_y) ** 2 for _, y in points)
    if variance_x <= 0 or variance_y <= 0:
        return None
    return covariance / math.sqrt(variance_x * variance_y)


def _average_ranks(values: Sequence[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=lambda index: (values[index], index))
    ranks = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        average = ((start + 1) + end) / 2
        for index in ordered[start:end]:
            ranks[index] = average
        start = end
    return ranks


def spearman(points: Sequence[tuple[float, float]]) -> float | None:
    if len(points) < 3:
        return None
    x_ranks = _average_ranks([x for x, _ in points])
    y_ranks = _average_ranks([y for _, y in points])
    return pearson(list(zip(x_ranks, y_ranks, strict=True)))


def linear_regression(points: Sequence[tuple[float, float]]) -> dict[str, float] | None:
    if len(points) < 2:
        return None
    mean_x = sum(x for x, _ in points) / len(points)
    mean_y = sum(y for _, y in points) / len(points)
    variance_x = sum((x - mean_x) ** 2 for x, _ in points)
    if variance_x <= 0:
        return None
    slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / variance_x
    intercept = mean_y - slope * mean_x
    total = sum((y - mean_y) ** 2 for _, y in points)
    residual = sum((y - (intercept + slope * x)) ** 2 for x, y in points)
    r_squared = 1 - residual / total if total > 0 else 1.0
    return {"slope": slope, "intercept": intercept, "r_squared": r_squared}


def _association_sample(
    records: Sequence[dict[str, Any]], indexes: Sequence[int]
) -> dict[str, Any]:
    points = [(float(records[index]["x"]), float(records[index]["y"])) for index in indexes]
    fit = linear_regression(points)
    return {
        "pearson": pearson(points),
        "spearman": spearman(points),
        "slope": fit["slope"] if fit else None,
    }


def wealth_association(
    records: Sequence[dict[str, Any]],
    *,
    seed: int,
    replicates: int = WEALTH_BOOTSTRAP_REPLICATES,
) -> dict[str, Any]:
    """Compute robust unweighted country-level association diagnostics.

    ``x`` is log2 GDP per capita and ``y`` is adoption in percentage points.
    Each qualifying country receives equal weight.
    """

    n = len(records)
    base = (
        _association_sample(records, list(range(n)))
        if n >= MIN_WEALTH_COEFFICIENT_COUNTRIES
        else {
            "pearson": None,
            "spearman": None,
            "slope": None,
        }
    )
    fit = (
        linear_regression([(float(row["x"]), float(row["y"])) for row in records])
        if n >= MIN_WEALTH_COEFFICIENT_COUNTRIES
        else None
    )
    bootstrap: dict[str, Any] | None = None
    if n >= MIN_WEALTH_ROBUSTNESS_COUNTRIES and replicates > 0:
        rng = random.Random(seed)
        samples: dict[str, list[float]] = {"pearson": [], "spearman": [], "slope": []}
        for _ in range(replicates):
            estimate = _association_sample(records, [rng.randrange(n) for _draw in range(n)])
            for key in samples:
                value = estimate[key]
                if value is not None and math.isfinite(value):
                    samples[key].append(value)
        bootstrap = {
            "method": "countries sampled with replacement",
            "replicates": replicates,
            "statistics": {
                key: {
                    "valid_replicates": len(values),
                    "low": _rounded(quantile(values, 0.025), 3),
                    "high": _rounded(quantile(values, 0.975), 3),
                }
                for key, values in samples.items()
            },
        }

    leave_one_out = []
    if n >= MIN_WEALTH_ROBUSTNESS_COUNTRIES:
        for omitted in range(n):
            estimate = _association_sample(
                records, [index for index in range(n) if index != omitted]
            )
            leave_one_out.append(
                {
                    "country": records[omitted]["label"],
                    "country_iso": records[omitted].get("country_iso"),
                    **estimate,
                    "delta_pearson": (
                        estimate["pearson"] - base["pearson"]
                        if estimate["pearson"] is not None and base["pearson"] is not None
                        else None
                    ),
                    "delta_slope": (
                        estimate["slope"] - base["slope"]
                        if estimate["slope"] is not None and base["slope"] is not None
                        else None
                    ),
                }
            )

    cooks: list[dict[str, Any]] = []
    if fit is not None and n >= MIN_WEALTH_ROBUSTNESS_COUNTRIES:
        xs = [float(row["x"]) for row in records]
        ys = [float(row["y"]) for row in records]
        mean_x = sum(xs) / n
        spread = sum((value - mean_x) ** 2 for value in xs)
        residuals = [
            ys[index] - (fit["intercept"] + fit["slope"] * xs[index]) for index in range(n)
        ]
        mse = sum(value * value for value in residuals) / (n - 2)
        loo_by_iso = {row.get("country_iso"): row for row in leave_one_out}
        if spread > 0 and mse > 0:
            for index, record in enumerate(records):
                leverage = 1 / n + (xs[index] - mean_x) ** 2 / spread
                denominator = max((1 - leverage) ** 2, 1e-15)
                distance = (residuals[index] ** 2 / (2 * mse)) * leverage / denominator
                omitted = loo_by_iso.get(record.get("country_iso"), {})
                cooks.append(
                    {
                        "country": record["label"],
                        "country_iso": record.get("country_iso"),
                        "cooks_distance": distance,
                        "threshold": 4 / n,
                        "influential": distance > 4 / n,
                        "delta_pearson": omitted.get("delta_pearson"),
                        "delta_slope": omitted.get("delta_slope"),
                    }
                )
            cooks.sort(key=lambda row: (-row["cooks_distance"], row["country"]))

    def range_for(key: str) -> dict[str, float | None]:
        values = [row[key] for row in leave_one_out if row[key] is not None]
        return {
            "low": _rounded(min(values), 3) if values else None,
            "high": _rounded(max(values), 3) if values else None,
        }

    return {
        "countries": n,
        "pearson": _rounded(base["pearson"], 3),
        "spearman": _rounded(base["spearman"], 3),
        "slope_pp_per_doubling": _rounded(base["slope"], 3),
        "intercept": _rounded(fit["intercept"], 3) if fit else None,
        "r_squared": _rounded(fit["r_squared"], 3) if fit else None,
        "bootstrap": bootstrap,
        "leave_one_out": {
            "pearson": range_for("pearson"),
            "spearman": range_for("spearman"),
            "slope_pp_per_doubling": range_for("slope"),
        },
        "influential_countries": [
            {
                **row,
                "cooks_distance": _rounded(row["cooks_distance"], 4),
                "threshold": _rounded(row["threshold"], 4),
                "delta_pearson": _rounded(row["delta_pearson"], 3),
                "delta_slope": _rounded(row["delta_slope"], 3),
            }
            for row in cooks[:5]
        ],
        "minimum_coefficient_countries": MIN_WEALTH_COEFFICIENT_COUNTRIES,
        "minimum_robustness_countries": MIN_WEALTH_ROBUSTNESS_COUNTRIES,
    }


def build_diagnostics(dataset: AnalysisDataset) -> dict[str, Any]:
    """Build all six diagnostics from one frozen-run dataset."""

    return {
        "evidence_robustness": evidence_robustness(dataset),
        "observation_coverage": observation_coverage(dataset),
        "owner_cluster": owner_cluster_robustness(dataset),
        "robust_debut": robust_debuts(dataset),
        "adoption_intensity": adoption_intensity(dataset),
        "multi_agent_co_use": multi_agent_co_use(dataset),
    }
