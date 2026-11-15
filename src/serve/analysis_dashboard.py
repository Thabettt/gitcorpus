"""Statistically appropriate visual projections of the analysis results.

The analysis tables remain authoritative.  This module only reshapes those
values for figures; it never invents a denominator or silently turns missing
data into zero.
"""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from serve.analysis_explanations import explanation_for


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    return None


def _wilson(part: int, whole: int) -> tuple[float | None, float | None]:
    """Return a two-sided 95% Wilson score interval in percentage points."""
    if whole <= 0:
        return None, None
    z = 1.959963984540054
    proportion = part / whole
    denominator = 1 + z * z / whole
    centre = (proportion + z * z / (2 * whole)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / whole + z * z / (4 * whole * whole))
        / denominator
    )
    return round(max(0.0, centre - margin) * 100, 1), round(min(1.0, centre + margin) * 100, 1)


def _item(
    label: object,
    value: object,
    detail: object = "",
    *,
    low: object = None,
    high: object = None,
    count: object = None,
    n: object = None,
    **extra: object,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "label": str(label),
        "value": _number(value),
        "detail": str(detail or ""),
        "low": _number(low),
        "high": _number(high),
        "count": int(count) if isinstance(count, int) and not isinstance(count, bool) else None,
        "n": int(n) if isinstance(n, int) and not isinstance(n, bool) else None,
    }
    item.update(extra)
    return item


def _prevalence_item(
    label: object,
    count: object,
    n: object,
    detail: object = "",
    **extra: object,
) -> dict[str, Any]:
    numerator = int(count) if isinstance(count, int) and not isinstance(count, bool) else 0
    denominator = int(n) if isinstance(n, int) and not isinstance(n, bool) else 0
    value = round(numerator / denominator * 100, 1) if denominator > 0 else None
    low, high = _wilson(numerator, denominator)
    return _item(
        label,
        value,
        detail,
        low=low,
        high=high,
        count=numerator,
        n=denominator,
        small=0 < denominator < 10,
        **extra,
    )


def _rate_item(label: object, rate: object, detail: object = "", **extra: object) -> dict[str, Any]:
    value = rate if isinstance(rate, dict) else {}
    count = value.get("count")
    eligible = value.get("eligible")
    return _item(
        label,
        value.get("percent"),
        detail,
        low=value.get("ci_low"),
        high=value.get("ci_high"),
        count=count,
        n=eligible,
        small=isinstance(eligible, int) and 0 < eligible < 10,
        **extra,
    )


def _dataset(label: str, items: list[dict[str, Any]], *, key: str = "") -> dict[str, Any]:
    return {"label": label, "key": key, "items": items}


def _rates_datasets(rows: list[dict[str, Any]], label_key: str) -> list[dict[str, Any]]:
    definitions = (
        ("Any signal", "adoption"),
        ("Committed config", "file_adoption"),
        ("Recent commit use", "recent_adoption"),
    )
    datasets = [
        _dataset(
            label,
            [
                _rate_item(
                    row.get(label_key, "Unknown"),
                    row.get(key),
                    (
                        f"{(row.get(key) or {}).get('count', 0)}/"
                        f"{(row.get(key) or {}).get('eligible', 0)}"
                    ),
                )
                for row in rows
            ],
            key=key,
        )
        for label, key in definitions
    ]
    datasets.append(
        _dataset(
            "Median commit intensity",
            [
                _item(
                    row.get(label_key, "Unknown"),
                    row.get("median_ratio"),
                    f"n={row.get('recent_adopters', 0)} adopters",
                    n=row.get("recent_adopters"),
                    small=0 < int(row.get("recent_adopters") or 0) < 10,
                )
                for row in rows
            ],
            key="median_ratio",
        )
    )
    return datasets


def _chart(
    key: str,
    chart_type: str,
    title: str,
    description: str,
    method: str,
    *,
    span: str = "wide",
    **data: object,
) -> dict[str, Any]:
    return {
        "key": key,
        "type": chart_type,
        "title": title,
        "description": description,
        "method": method,
        "span": span,
        "explanation": explanation_for(key),
        **data,
    }


def build_dashboard(context: dict[str, Any]) -> dict[str, Any]:
    results = context["results"]
    totals = context["totals"]
    diagnostics = context.get("diagnostics", {})
    charts: list[dict[str, Any]] = []

    agent_share = results.get("agent_share", [])
    charts.append(
        _chart(
            "agent-share",
            "paired_dot",
            "Agent share",
            (
                "Per-agent prevalence under both valid denominators. "
                "Repositories can carry more than one agent."
            ),
            "Paired prevalence plot · point estimate with 95% Wilson interval",
            datasets=[
                _dataset(
                    "All scanned repositories",
                    [
                        _prevalence_item(
                            row["agent"],
                            row.get("repos"),
                            totals.get("scanned"),
                            f"{row.get('repos', 0)}/{totals.get('scanned', 0)}",
                        )
                        for row in agent_share
                    ],
                    key="scanned",
                ),
                _dataset(
                    "Readable repositories",
                    [
                        _prevalence_item(
                            row["agent"],
                            row.get("readable_repos"),
                            totals.get("readable"),
                            f"{row.get('readable_repos', 0)}/{totals.get('readable', 0)}",
                        )
                        for row in agent_share
                    ],
                    key="readable",
                ),
            ],
            unit="%",
        )
    )

    marker_summary = results.get("generic_markers", {})
    marker_sets = [
        _dataset(
            "Shared markers",
            [
                _item(
                    row["marker"],
                    row.get("repos"),
                    f"{row['kind']} marker · never counted as an agent",
                    channel=row["kind"],
                )
                for row in marker_summary.get("markers", [])
            ],
            key="markers",
        )
    ]
    content_rows = marker_summary.get("content_attribution", [])
    if content_rows:
        marker_sets.append(
            _dataset(
                "Content-only fallback",
                [
                    _item(
                        row["agent"],
                        row.get("repos"),
                        "attributed from an AGENTS.md address cue",
                        channel="content",
                    )
                    for row in content_rows
                ],
                key="content",
            )
        )
    charts.append(
        _chart(
            "generic-markers",
            "lollipop",
            "Shared markers and content fallbacks",
            (
                "AGENTS.md and similar shared conventions stay visible but are "
                "excluded from every agent count."
            ),
            (
                "Lollipop frequency plot · shared markers are not products; "
                "content fallbacks are used only when no named agent exists"
            ),
            datasets=marker_sets,
            stats=[
                {
                    "label": "Repositories with shared markers",
                    "value": marker_summary.get("repos_with_markers"),
                    "unit": "",
                },
                {
                    "label": "Content-only attributions",
                    "value": sum(int(row.get("repos") or 0) for row in content_rows),
                    "unit": "",
                },
            ],
            unit=" repos",
        )
    )

    country_agents = results.get("agents_by_country", [])
    agent_totals: defaultdict[str, int] = defaultdict(int)
    for row in country_agents:
        for agent in row.get("agents", []):
            agent_totals[str(agent["agent"])] += int(agent.get("repos") or 0)
    heatmap_columns = [
        agent
        for agent, _count in sorted(agent_totals.items(), key=lambda item: (-item[1], item[0]))
    ]
    charts.append(
        _chart(
            "agents-country",
            "heatmap",
            "Agents by country",
            "Country–agent structure, normalized by readable repositories within each country.",
            "Prevalence matrix · cell color encodes share; text gives exact percent and count",
            span="full",
            columns=heatmap_columns,
            rows=[
                {
                    "label": row["country"],
                    "code": row.get("country_iso"),
                    "n": row.get("readable"),
                    "cells": {
                        agent["agent"]: {
                            "value": _number(agent.get("share_readable")),
                            "count": agent.get("repos"),
                        }
                        for agent in row.get("agents", [])
                    },
                }
                for row in country_agents
            ],
            unit="%",
        )
    )

    adoption = results.get("adoption", {})
    charts.append(
        _chart(
            "adoption",
            "composition",
            "Agent use",
            "Observed repositories partitioned by ordered commit-intensity tier.",
            "Normalized composition strip · mutually exclusive tiers sum to 100%",
            segments=[
                {
                    "label": row["level"].replace("_", " ").title(),
                    "value": _number(row.get("share")),
                    "count": row.get("repos"),
                }
                for row in adoption.get("levels", [])
            ],
            stats=[
                {
                    "label": "Eligible prevalence",
                    "value": adoption.get("adoption_readable"),
                    "unit": "%",
                },
                {
                    "label": "Scanned prevalence",
                    "value": adoption.get("adoption_scanned"),
                    "unit": "%",
                },
                {"label": "Unavailable", "value": adoption.get("unavailable"), "unit": ""},
            ],
        )
    )

    country_rows = results.get("adoption_by_country", [])
    charts.append(
        _chart(
            "country-adoption",
            "forest",
            "Agent use by country",
            "Repo-weighted prevalence; unresolved owners remain visible as Unknown.",
            "Caterpillar forest plot · point estimate with 95% Wilson interval",
            datasets=[
                _dataset(
                    "Eligible-repository adoption",
                    [
                        _prevalence_item(
                            row["country"],
                            row.get("with_agent"),
                            row.get("readable"),
                            (
                                f"{row.get('with_agent', 0)}/{row.get('readable', 0)} "
                                f"eligible · {row.get('repos', 0)} scanned"
                            ),
                            code=row.get("country_iso"),
                        )
                        for row in country_rows
                    ],
                    key="adoption",
                )
            ],
            filter_by_n=True,
            unit="%",
        )
    )

    size = results.get("size_vs_adoption", {})
    buckets = size.get("buckets", [])
    size_sets = [
        _dataset(
            "Any signal",
            [
                _prevalence_item(
                    row["bucket"],
                    row.get("with_agent"),
                    row.get("readable"),
                    f"{row.get('with_agent', 0)}/{row.get('readable', 0)} eligible",
                )
                for row in buckets
            ],
            key="adoption",
        )
    ]
    for agent_name in size.get("agents", []):
        size_sets.append(
            _dataset(
                agent_name,
                [
                    _prevalence_item(
                        row["bucket"],
                        next(
                            (
                                agent.get("repos")
                                for agent in row.get("agents", [])
                                if agent.get("agent") == agent_name
                            ),
                            0,
                        ),
                        row.get("readable"),
                        f"n={row.get('readable', 0)} eligible",
                    )
                    for row in buckets
                ],
                key=agent_name,
            )
        )
    charts.append(
        _chart(
            "size-adoption",
            "ordinal_profile",
            "Repository size",
            "Prevalence across frozen disk-size bands; choose an agent to inspect its profile.",
            "Ordered stratum profile · point estimate with 95% Wilson interval",
            datasets=size_sets,
            unit="%",
        )
    )

    debuts = results.get("agent_debut", [])
    charts.append(
        _chart(
            "agent-debuts",
            "range_timeline",
            "Agent debuts",
            (
                "Earliest repository creation and earliest observed signal inside "
                "this run's bounded window."
            ),
            "Paired event timeline · endpoints are bounded earliest observations, not true debuts",
            rows=[
                {
                    "label": row["agent"],
                    "repository_date": row.get("earliest_repo_created"),
                    "signal_date": row.get("earliest_signal"),
                    "repos": row.get("repos"),
                    "dated": row.get("dated_repos"),
                }
                for row in debuts
            ],
        )
    )

    fingerprint_groups = results.get("fingerprint_debut", [])
    charts.append(
        _chart(
            "fingerprints",
            "lollipop",
            "Fingerprint prevalence",
            "Choose an agent to compare its strongest repository-visible fingerprints.",
            "Lollipop frequency plot · top five fingerprints per agent by repository count",
            datasets=[
                _dataset(
                    group["agent"],
                    [
                        _item(
                            row["fingerprint"],
                            row.get("repos"),
                            (
                                f"{row['channel'].replace('_', ' ')} · first "
                                f"{row.get('earliest_signal') or 'undated'}"
                            ),
                            channel=row["channel"],
                            signal_date=row.get("earliest_signal"),
                        )
                        for row in group.get("fingerprints", [])
                    ],
                )
                for group in fingerprint_groups
            ],
            unit=" repos",
        )
    )

    wealth = results.get("country_wealth", {})
    minimum = int(wealth.get("min_repos") or 0)
    wealth_points = []
    for row in wealth.get("rows", []):
        if row.get("gdp_pc") is None or row.get("adoption_readable") is None:
            continue
        low, high = _wilson(int(row.get("with_agent") or 0), int(row.get("readable") or 0))
        wealth_points.append(
            {
                "label": row["country"],
                "x": _number(row.get("gdp_pc")),
                "y": _number(row.get("adoption_readable")),
                "low": low,
                "high": high,
                "group": row.get("income_group") or "Unknown",
                "n": row.get("readable"),
                "count": row.get("with_agent"),
                "in_fit": int(row.get("readable") or 0) >= minimum,
                "year": row.get("gdp_year"),
                "influential": bool((row.get("influence") or {}).get("influential")),
            }
        )
    wealth_statistics = wealth.get("statistics") or {}
    wealth_bootstrap = (wealth_statistics.get("bootstrap") or {}).get("statistics") or {}
    pearson_bootstrap = wealth_bootstrap.get("pearson") or {}
    pearson_loo = (wealth_statistics.get("leave_one_out") or {}).get("pearson") or {}
    charts.append(
        _chart(
            "country-wealth",
            "scatter_regression",
            "Country wealth vs agent use",
            "Log GDP per capita against repo-weighted adoption. Descriptive, never causal.",
            (
                "Bubble scatterplot · unweighted OLS fit on eligible countries; "
                "area encodes readable n"
            ),
            span="full",
            points=wealth_points,
            min_n=minimum,
            stats=[
                {"label": "Pearson r", "value": wealth.get("correlation"), "unit": ""},
                {"label": "Spearman ρ", "value": wealth.get("spearman"), "unit": ""},
                {
                    "label": "pp per GDP doubling",
                    "value": wealth.get("slope_pp_per_doubling"),
                    "unit": "",
                },
                {
                    "label": "Pearson bootstrap 95%",
                    "value": (
                        f"{pearson_bootstrap.get('low')}–{pearson_bootstrap.get('high')}"
                        if pearson_bootstrap.get("low") is not None
                        else None
                    ),
                    "unit": "",
                },
                {
                    "label": "Pearson leave-one-out",
                    "value": (
                        f"{pearson_loo.get('low')}–{pearson_loo.get('high')}"
                        if pearson_loo.get("low") is not None
                        else None
                    ),
                    "unit": "",
                },
                {"label": "Countries in fit", "value": wealth.get("points"), "unit": ""},
                {"label": "Minimum n", "value": minimum, "unit": ""},
            ],
        )
    )

    cohort = results.get("birth_cohort", {})
    excluded_unknown = cohort.get("excluded_unknown") or 0
    cohort_note = (
        f" {excluded_unknown} repositories with no recorded creation date are excluded."
        if excluded_unknown
        else ""
    )
    charts.append(
        _chart(
            "creation-cohorts",
            "ordinal_profile",
            "Creation cohorts",
            (
                "Cross-sectional prevalence by repository creation cohort; "
                f"cutoff {cohort.get('cutoff', '—')}."
                f"{cohort_note}"
            ),
            "Ordered cohort profile · 95% Wilson intervals for binomial outcomes",
            datasets=_rates_datasets(cohort.get("rows", []), "cohort"),
            break_labels=["Existing before cutoff", "Unknown"],
            unit="%",
        )
    )

    stars = results.get("star_tiers", [])
    charts.append(
        _chart(
            "star-tiers",
            "ordinal_profile",
            "Stars vs agent use",
            "Popularity strata are descriptive and not exposure denominators.",
            "Log-binned stratum profile · 95% Wilson intervals for binomial outcomes",
            datasets=_rates_datasets(stars, "bucket"),
            break_labels=["Unknown"],
            unit="%",
        )
    )

    commits = results.get("commit_depth", [])
    commit_sets = _rates_datasets(commits, "bucket")
    commit_sets.extend(
        [
            _dataset(
                "Median history coverage",
                [
                    _item(
                        row["bucket"],
                        row.get("median_coverage"),
                        f"n={row.get('coverage_observed', 0)} observed",
                        n=row.get("coverage_observed"),
                        small=0 < int(row.get("coverage_observed") or 0) < 10,
                    )
                    for row in commits
                ],
                key="median_coverage",
            ),
            _dataset(
                "Full-history coverage",
                [
                    _rate_item(
                        row["bucket"],
                        row.get("full_coverage"),
                        f"{row.get('full_history', 0)}/{row.get('coverage_observed', 0)} observed",
                    )
                    for row in commits
                ],
                key="full_coverage",
            ),
        ]
    )
    charts.append(
        _chart(
            "commit-depth",
            "ordinal_profile",
            "Commits vs agent use",
            (
                "Lifetime depth defines the stratum; recent ratios use only "
                "inspected eligible commits."
            ),
            "Ordered stratum profile · uncertainty shown for binomial estimates",
            datasets=commit_sets,
            break_labels=["Unknown"],
            unit="%",
        )
    )

    languages = results.get("language_adoption", [])
    language_sets = _rates_datasets(languages, "language")
    language_sets.append(
        _dataset(
            "Top-agent share",
            [
                _rate_item(
                    row["language"],
                    row.get("top_agent_share"),
                    row.get("top_agent") or "No observed agent",
                    annotation=row.get("top_agent"),
                )
                for row in languages
            ],
            key="top_agent_share",
        )
    )
    charts.append(
        _chart(
            "language-adoption",
            "forest",
            "Language vs agent use",
            "Primary-language strata from the frozen source snapshot.",
            "Caterpillar forest plot · point estimate with 95% Wilson interval where defined",
            span="full",
            datasets=language_sets,
            filter_by_n=True,
            unit="%",
        )
    )

    robustness = diagnostics.get("evidence_robustness", {})
    definitions = robustness.get("definitions", {})
    charts.append(
        _chart(
            "diagnostic-evidence-robustness",
            "paired_dot",
            "Evidence robustness",
            "How much estimated adoption changes under a predeclared stricter evidence rule.",
            "Sensitivity envelope · the broad–strict gap is not a confidence interval",
            datasets=[
                _dataset(
                    "Broad evidence",
                    [_rate_item("Complete eligible frame", definitions.get("broad"))],
                    key="broad",
                ),
                _dataset(
                    "Strict evidence",
                    [_rate_item("Complete eligible frame", definitions.get("strict"))],
                    key="strict",
                ),
            ],
            stats=[
                {
                    "label": "Behavioral",
                    "value": (definitions.get("behavioral") or {}).get("percent"),
                    "unit": "%",
                },
                {
                    "label": "Corroborated",
                    "value": (definitions.get("corroborated") or {}).get("percent"),
                    "unit": "%",
                },
                {
                    "label": "Structural only",
                    "value": (definitions.get("structural_only") or {}).get("percent"),
                    "unit": "%",
                },
                {
                    "label": "Sensitivity gap",
                    "value": robustness.get("sensitivity_gap_pp"),
                    "unit": " pp",
                },
            ],
            unit="%",
        )
    )

    coverage = diagnostics.get("observation_coverage", {})
    charts.append(
        _chart(
            "diagnostic-observation-coverage",
            "coverage_heatmap",
            "Observation and eligibility coverage",
            "The share of every stratum on which each outcome could actually be observed.",
            "Coverage matrix · missing or unselected outcomes are not rendered as zero",
            span="full",
            measures=coverage.get("measures", []),
            dimensions=coverage.get("dimensions", []),
            unit="%",
        )
    )

    owner_cluster = diagnostics.get("owner_cluster", {})
    account_types = owner_cluster.get("account_types", [])

    def owner_item(row: dict[str, Any], key: str, bootstrap_key: str) -> dict[str, Any]:
        rate = row.get(key) or {}
        interval = (row.get("cluster_bootstrap") or {}).get(bootstrap_key) or {}
        return _item(
            row.get("account_type", "Unknown"),
            rate.get("percent"),
            f"{rate.get('count', 0)}/{rate.get('eligible', 0)} eligible",
            low=interval.get("low", rate.get("ci_low")),
            high=interval.get("high", rate.get("ci_high")),
            count=rate.get("count"),
            n=rate.get("eligible"),
        )

    charts.append(
        _chart(
            "diagnostic-owner-cluster",
            "paired_dot",
            "Owner-cluster robustness",
            "Repository and owner weighting compared separately for people and organizations.",
            "Paired estimates · intervals resample whole owner clusters when n ≥ 10 owners",
            datasets=[
                _dataset(
                    "Repository weighted",
                    [
                        owner_item(row, "repo_weighted_adoption", "repo_weighted")
                        for row in account_types
                    ],
                    key="repo_weighted",
                ),
                _dataset(
                    "Owner weighted",
                    [
                        owner_item(row, "owner_weighted_adoption", "owner_weighted")
                        for row in account_types
                    ],
                    key="owner_weighted",
                ),
            ],
            unit="%",
        )
    )

    debut = diagnostics.get("robust_debut", {})
    charts.append(
        _chart(
            "diagnostic-robust-debut",
            "percentile_timeline",
            "Robust observed debuts",
            "P0, P10, and median observed signal dates reduce dependence on one extreme timestamp.",
            "Percentile timeline · bounded observed dates, not true first-use dates",
            span="full",
            rows=[
                {
                    "label": row.get("agent"),
                    "p0": row.get("signal_p0"),
                    "p10": row.get("signal_p10"),
                    "p50": row.get("signal_p50"),
                    "dated": row.get("dated_repos"),
                    "repos": row.get("repos"),
                    "coverage": (row.get("dated_coverage") or {}).get("percent"),
                }
                for row in debut.get("rows", [])
            ],
        )
    )

    intensity = diagnostics.get("adoption_intensity", {})
    overall_intensity = intensity.get("overall", {})
    charts.append(
        _chart(
            "diagnostic-adoption-intensity",
            "ecdf",
            "Adoption-intensity distribution",
            (
                "The full recent-commit-use distribution among adopters, "
                "with zero use reported separately."
            ),
            "Empirical cumulative distribution · commit ratio > 0; sampled at 0.5-point thresholds",
            span="full",
            points=intensity.get("cdf", []),
            series=intensity.get("cdf_series", []),
            stats=[
                {"label": "P25", "value": overall_intensity.get("p25"), "unit": "%"},
                {"label": "Median", "value": overall_intensity.get("p50"), "unit": "%"},
                {"label": "P75", "value": overall_intensity.get("p75"), "unit": "%"},
                {"label": "P90", "value": overall_intensity.get("p90"), "unit": "%"},
                {
                    "label": "Zero recent use",
                    "value": (overall_intensity.get("zero_recent") or {}).get("percent"),
                    "unit": "%",
                },
                {
                    "label": "Pervasive adopters",
                    "value": (overall_intensity.get("pervasive") or {}).get("percent"),
                    "unit": "%",
                },
            ],
        )
    )

    co_use = diagnostics.get("multi_agent_co_use", {})
    charts.append(
        _chart(
            "diagnostic-multi-agent-co-use",
            "co_use",
            "Multi-agent co-use",
            "Distinct agents per repository and exact owner-wide agent sets.",
            (
                "Multiplicity composition + exact-set ranking · "
                "Users and Organizations remain separate"
            ),
            span="full",
            repositories=co_use.get("repositories", {}),
            owners=co_use.get("owners", []),
        )
    )

    return {
        "charts": charts,
        "summary": [
            {"label": "Repositories", "value": totals.get("scanned")},
            {"label": "Eligible", "value": totals.get("readable")},
            {"label": "Any agent", "value": totals.get("with_agent")},
            {"label": "Observed prevalence", "value": totals.get("adoption_readable"), "unit": "%"},
        ],
    }
