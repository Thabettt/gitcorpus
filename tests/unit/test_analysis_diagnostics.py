from __future__ import annotations

from datetime import UTC, datetime

import pytest

from serve.analysis_dataset import AnalysisDataset, AnalysisRepo
from serve.analysis_diagnostics import (
    OWNER_AGENT_BANDS,
    REPOSITORY_AGENT_BANDS,
    adoption_intensity,
    band_for,
    cluster_bootstrap,
    evidence_robustness,
    multi_agent_co_use,
    nearest_rank,
    observation_coverage,
    owner_cluster_robustness,
    robust_debuts,
    spearman,
    wealth_association,
)


def _repo(
    repo_id: int,
    *,
    owner_id: int | None = 1,
    owner_type: str | None = "User",
    agents: tuple[str, ...] = (),
    evidence_channels: frozenset[str] = frozenset(),
    evidence_families: frozenset[str] = frozenset(),
    structural: bool = False,
    readable: bool = True,
    complete: bool = True,
    file_observed: bool = True,
    ratio: float | None = None,
    coverage: float | None = None,
    history_complete: bool | None = None,
    history_metadata: bool | None = None,
    signal: str | None = None,
    country: str = "US",
    language: str = "Python",
    stars: int | None = 10,
    commits: int | None = 100,
) -> AnalysisRepo:
    return AnalysisRepo(
        repo_id=repo_id,
        owner_id=owner_id,
        owner_type=owner_type,
        country_iso=country,
        language=language,
        stars=stars,
        commit_count=commits,
        repo_created_at=datetime(2025, 1, min(repo_id, 28), tzinfo=UTC),
        detection_present=True,
        readable=readable,
        complete_channels=complete,
        channels={"file": "ok", "author": "ok"},
        agents=agents,
        evidence_channels=evidence_channels,
        evidence_agents=agents,
        evidence_families=evidence_families,
        structural_signal=structural,
        file_observed=file_observed,
        commit_ratio=ratio,
        history_coverage=coverage,
        history_complete=history_complete,
        first_signal_at=signal,
        history_metadata=(
            coverage is not None or history_complete is not None
            if history_metadata is None
            else history_metadata
        ),
    )


def _dataset(*rows: AnalysisRepo) -> AnalysisDataset:
    return AnalysisDataset(
        run_id=41,
        selected_channels=("file", "author"),
        channel_selection_source="run_spec",
        rows=rows,
    )


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "1"), (2, "2–5"), (5, "2–5"), (6, "6–9"), (9, "6–9"), (10, "10+")],
)
def test_repository_agent_bands_are_disjoint_and_exhaustive(count, expected):
    assert band_for(count, REPOSITORY_AGENT_BANDS) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [(1, "1"), (2, "2"), (3, "3"), (4, "4–6"), (6, "4–6"), (7, "7–9"), (9, "7–9"), (10, "10+")],
)
def test_owner_agent_bands_are_disjoint_and_exhaustive(count, expected):
    assert band_for(count, OWNER_AGENT_BANDS) == expected


def test_nearest_rank_dates_use_documented_empirical_rule():
    values = [datetime(2020 + year, 1, 1, tzinfo=UTC) for year in range(10)]

    assert nearest_rank(values, 0.0) == values[0]
    assert nearest_rank(values, 0.1) == values[0]
    assert nearest_rank(values, 0.5) == values[4]


def test_evidence_robustness_uses_one_common_eligible_denominator():
    dataset = _dataset(
        _repo(
            1,
            agents=("A",),
            evidence_channels=frozenset({"file"}),
            evidence_families=frozenset({"structural"}),
            structural=True,
        ),
        _repo(
            2,
            agents=("B",),
            evidence_channels=frozenset({"file", "author"}),
            evidence_families=frozenset({"structural", "commit"}),
            structural=True,
        ),
        _repo(3, complete=False),
    )

    result = evidence_robustness(dataset)

    assert result["eligible"] == 2
    assert result["definitions"]["broad"]["count"] == 2
    assert result["definitions"]["strict"]["count"] == 1
    assert result["definitions"]["structural_only"]["count"] == 1
    assert result["corroboration_among_broad"]["eligible"] == 2
    assert result["sensitivity_gap_pp"] == 50.0


def test_coverage_distinguishes_unobserved_from_observed_zero():
    dataset = _dataset(
        _repo(1, ratio=0.0, coverage=1.0, history_complete=True),
        _repo(2, ratio=None, coverage=None, history_complete=None, file_observed=False),
        _repo(3, readable=False, complete=False, file_observed=False),
    )

    result = observation_coverage(dataset)
    stars = next(group for group in result["dimensions"] if group["key"] == "stars")
    row = stars["rows"][0]

    assert row["repos"] == 3
    assert row["coverage"]["readable"]["count"] == 2
    assert row["coverage"]["file_scan"]["count"] == 1
    assert row["coverage"]["commit_denominator"]["count"] == 1
    assert row["coverage"]["full_history"]["count"] == 1


def test_coverage_marks_unrecorded_history_metadata_not_applicable():
    dataset = _dataset(
        _repo(1, ratio=0.5, coverage=None, history_complete=None, history_metadata=False),
        _repo(2, ratio=0.0, coverage=None, history_complete=None, history_metadata=False),
    )

    result = observation_coverage(dataset)
    row = result["dimensions"][0]["rows"][0]

    assert row["coverage"]["commit_denominator"]["applicable"] is True
    assert row["coverage"]["commit_denominator"]["count"] == 2
    for key in ("history_observed", "full_history"):
        assert row["coverage"][key]["applicable"] is False
        assert row["coverage"][key]["percent"] is None
        assert "not recorded" in row["coverage"][key]["reason"]


def test_owner_cluster_results_are_separate_and_cluster_bootstrap_is_deterministic():
    rows = tuple(
        _repo(
            index,
            owner_id=index,
            owner_type="User",
            evidence_channels=frozenset({"file"}) if index % 2 else frozenset(),
            evidence_families=frozenset({"structural"}) if index % 2 else frozenset(),
        )
        for index in range(1, 11)
    ) + (
        _repo(
            20,
            owner_id=20,
            owner_type="Organization",
            evidence_channels=frozenset({"file"}),
            evidence_families=frozenset({"structural"}),
        ),
    )
    dataset = _dataset(*rows)

    result = owner_cluster_robustness(dataset)
    users, organizations = result["account_types"]

    assert users["account_type"] == "User"
    assert users["eligible_owners"] == 10
    assert users["adopted_owners"] == 5
    assert users["cluster_bootstrap"]["replicates"] == 1_000
    assert organizations["eligible_owners"] == 1
    assert organizations["cluster_bootstrap"] is None
    assert cluster_bootstrap([(1, index % 2) for index in range(10)], seed=7, replicates=50) == (
        cluster_bootstrap([(1, index % 2) for index in range(10)], seed=7, replicates=50)
    )


def test_robust_debut_reports_p0_p10_p50_and_dated_coverage():
    rows = [
        _repo(
            index,
            agents=("A",),
            signal=f"202{index - 1}-01-01T00:00:00Z" if index < 5 else None,
        )
        for index in range(1, 6)
    ]

    result = robust_debuts(_dataset(*rows))["rows"][0]

    assert result["signal_p0"] == "2020-01-01"
    assert result["signal_p10"] == "2020-01-01"
    assert result["signal_p50"] == "2021-01-01"
    assert result["dated_repos"] == 4
    assert result["dated_coverage"]["percent"] == 80.0


def test_intensity_distribution_conditions_quantiles_on_positive_adopters():
    dataset = _dataset(
        _repo(1, ratio=0.0),
        _repo(2, ratio=0.1),
        _repo(3, ratio=0.2),
        _repo(4, ratio=0.4),
        _repo(5, ratio=None),
    )

    diagnostic = adoption_intensity(dataset)
    result = diagnostic["overall"]

    assert result["history_observed"] == 4
    assert result["recent_adopters"] == 3
    assert result["zero_recent"]["percent"] == 25.0
    assert result["p25"] == 15.0
    assert result["p50"] == 20.0
    assert result["p75"] == 30.0
    assert result["p90"] == 36.0
    assert result["pervasive"]["count"] == 2
    assert diagnostic["cdf_series"][0]["label"] == "All recent adopters"
    assert any(series["label"] == "Star tier · 10–99" for series in diagnostic["cdf_series"])


def test_multi_agent_owner_unions_and_exact_set_ties_are_deterministic():
    dataset = _dataset(
        _repo(1, owner_id=1, agents=("B",)),
        _repo(2, owner_id=1, agents=("A",)),
        _repo(3, owner_id=2, agents=("A", "B")),
        _repo(4, owner_id=3, agents=("C", "D")),
        _repo(5, owner_id=4, agents=("A",)),
        _repo(6, owner_id=5, owner_type="Organization", agents=("A", "B", "C")),
        _repo(7, owner_id=6, owner_type="Organization", agents=()),
    )

    result = multi_agent_co_use(dataset)
    users = result["owners"][0]
    organizations = result["owners"][1]
    pairs = next(row for row in users["bands"] if row["band"] == "2")

    assert users["represented_owners"] == 4
    assert users["owners_with_agents"] == 4
    assert pairs["owners"] == 3
    assert [row["set_key"] for row in pairs["rankings"]] == ["A + B", "C + D"]
    assert [row["count"] for row in pairs["rankings"]] == [2, 1]
    assert organizations["represented_owners"] == 2
    assert organizations["owners_without_agents"] == 1
    assert sum(row["repos"] for row in result["repositories"]["bands"]) == 6


def test_spearman_uses_average_tie_ranks_and_wealth_bootstrap_replays():
    tied = [(1.0, 10.0), (2.0, 20.0), (2.0, 20.0), (4.0, 40.0)]
    records = [
        {
            "x": float(index),
            "y": float(2 * index + 1),
            "label": f"C{index}",
            "country_iso": f"{index:02}",
        }
        for index in range(1, 7)
    ]

    first = wealth_association(records, seed=19, replicates=100)
    second = wealth_association(records, seed=19, replicates=100)

    assert spearman(tied) == pytest.approx(1.0)
    assert first == second
    assert first["pearson"] == 1.0
    assert first["spearman"] == 1.0
    assert first["slope_pp_per_doubling"] == 2.0
    assert first["bootstrap"]["statistics"]["pearson"]["low"] == 1.0
    assert first["leave_one_out"]["pearson"] == {"low": 1.0, "high": 1.0}
