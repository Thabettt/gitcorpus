from __future__ import annotations

from serve.analysis_dashboard import build_dashboard


def _base_context() -> dict:
    return {
        "totals": {
            "scanned": 20,
            "readable": 18,
            "with_agent": 9,
            "adoption_readable": 50.0,
        },
        "results": {},
    }


def test_dashboard_assigns_visuals_by_statistical_task():
    dashboard = build_dashboard(_base_context())

    assert {chart["key"]: chart["type"] for chart in dashboard["charts"]} == {
        "agent-share": "paired_dot",
        "generic-markers": "lollipop",
        "agents-country": "heatmap",
        "adoption": "composition",
        "country-adoption": "forest",
        "size-adoption": "ordinal_profile",
        "agent-debuts": "range_timeline",
        "fingerprints": "lollipop",
        "country-wealth": "scatter_regression",
        "creation-cohorts": "ordinal_profile",
        "star-tiers": "ordinal_profile",
        "commit-depth": "ordinal_profile",
        "language-adoption": "forest",
        "diagnostic-evidence-robustness": "paired_dot",
        "diagnostic-observation-coverage": "coverage_heatmap",
        "diagnostic-owner-cluster": "paired_dot",
        "diagnostic-robust-debut": "percentile_timeline",
        "diagnostic-adoption-intensity": "ecdf",
        "diagnostic-multi-agent-co-use": "co_use",
    }


def test_dashboard_explains_every_figure():
    dashboard = build_dashboard(_base_context())

    for chart in dashboard["charts"]:
        explanation = chart["explanation"]
        assert explanation is not None, chart["key"]
        assert explanation["kind"] in {"Headline measure", "Validity diagnostic"}
        assert explanation["question"]
        assert explanation["context"]
        assert len(explanation["how"]) >= 4
        assert explanation["example"]
        assert explanation["caveat"]
        assert explanation["terms"]
        for term in explanation["terms"]:
            assert term["term"]
            assert term["meaning"]


def test_every_explanation_term_resolves_to_a_glossary_entry():
    from serve.analysis_explanations import CHART_EXPLANATIONS, CHART_GLOSSARY

    for key, explanation in CHART_EXPLANATIONS.items():
        assert explanation["kind"] in {"Headline measure", "Validity diagnostic"}, key
        for term_key in explanation["terms"]:
            assert term_key in CHART_GLOSSARY, (key, term_key)


def test_dashboard_preserves_uncertainty_and_metric_specific_denominators():
    context = _base_context()
    context["results"] = {
        "adoption_by_country": [
            {
                "country": "Exampleland",
                "country_iso": "EX",
                "repos": 12,
                "readable": 10,
                "with_agent": 5,
            }
        ],
        "star_tiers": [
            {
                "bucket": "10–99",
                "adoption": {
                    "count": 5,
                    "eligible": 10,
                    "percent": 50.0,
                    "ci_low": 23.7,
                    "ci_high": 76.3,
                },
                "file_adoption": {
                    "count": 2,
                    "eligible": 8,
                    "percent": 25.0,
                    "ci_low": 7.1,
                    "ci_high": 59.1,
                },
                "recent_adoption": {
                    "count": 3,
                    "eligible": 7,
                    "percent": 42.9,
                    "ci_low": 15.8,
                    "ci_high": 75.0,
                },
                "median_ratio": 12.5,
                "recent_adopters": 3,
            }
        ],
    }

    charts = {chart["key"]: chart for chart in build_dashboard(context)["charts"]}
    country = charts["country-adoption"]["datasets"][0]["items"][0]
    median = charts["star-tiers"]["datasets"][3]["items"][0]

    assert country == {
        "label": "Exampleland",
        "value": 50.0,
        "detail": "5/10 eligible · 12 scanned",
        "low": 23.7,
        "high": 76.3,
        "count": 5,
        "n": 10,
        "small": False,
        "code": "EX",
    }
    assert median["value"] == 12.5
    assert median["n"] == 3
    assert median["detail"] == "n=3 adopters"


def test_dashboard_projects_diagnostics_without_changing_their_estimands():
    context = _base_context()
    context["diagnostics"] = {
        "evidence_robustness": {
            "definitions": {
                "broad": {
                    "count": 8,
                    "eligible": 10,
                    "percent": 80.0,
                    "ci_low": 49.0,
                    "ci_high": 94.3,
                },
                "strict": {
                    "count": 5,
                    "eligible": 10,
                    "percent": 50.0,
                    "ci_low": 23.7,
                    "ci_high": 76.3,
                },
            },
            "sensitivity_gap_pp": 30.0,
        },
        "owner_cluster": {
            "account_types": [
                {
                    "account_type": "User",
                    "repo_weighted_adoption": {
                        "count": 6,
                        "eligible": 10,
                        "percent": 60.0,
                        "ci_low": 31.3,
                        "ci_high": 83.2,
                    },
                    "owner_weighted_adoption": {
                        "count": 4,
                        "eligible": 8,
                        "percent": 50.0,
                        "ci_low": 21.5,
                        "ci_high": 78.5,
                    },
                    "cluster_bootstrap": {
                        "repo_weighted": {"low": 40.0, "high": 75.0},
                        "owner_weighted": {"low": 25.0, "high": 75.0},
                    },
                }
            ]
        },
        "observation_coverage": {"measures": [], "dimensions": []},
        "robust_debut": {"rows": []},
        "adoption_intensity": {"overall": {}, "cdf": []},
        "multi_agent_co_use": {"repositories": {}, "owners": []},
    }

    charts = {chart["key"]: chart for chart in build_dashboard(context)["charts"]}
    broad = charts["diagnostic-evidence-robustness"]["datasets"][0]["items"][0]
    clustered = charts["diagnostic-owner-cluster"]["datasets"][0]["items"][0]

    assert broad["value"] == 80.0
    assert broad["n"] == 10
    assert clustered["value"] == 60.0
    assert (clustered["low"], clustered["high"]) == (40.0, 75.0)
