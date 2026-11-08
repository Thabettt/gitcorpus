from __future__ import annotations

import json
from pathlib import Path

import pytest

from enrich.geo_validation import (
    GeoValidationError,
    audit_index,
    blinded_pack,
    build_benchmark_manifest,
    build_population,
    cohen_kappa,
    compare_annotations,
    evaluate_challenge_cases,
    evaluate_gold,
    evaluate_release_gates,
    evidence_shape,
    file_sha256,
    finalize_gold,
    read_json,
    read_jsonl,
    refresh_predictions,
    render_markdown_report,
    runtime_provenance,
    sample_population,
    script_group,
    sha256_text,
    utc_now,
    validate_annotation,
    verify_manifest_artifacts,
    website_tld,
    write_csv,
    write_json,
    write_jsonl,
)


def _case_id(value: str) -> str:
    return sha256_text(value)


def _sample_case(
    name: str,
    prediction: str | None,
    confidence: str,
    *,
    frequency: int = 1,
    stratum: str | None = None,
) -> dict:
    return {
        "case_id": _case_id(name),
        "family_id": _case_id("family:" + name),
        "raw_location": name,
        "website_tld": None,
        "owner_type": "User",
        "frequency": frequency,
        "prediction_country": prediction,
        "prediction_confidence": confidence,
        "script_group": "latin",
        "evidence_shape": "phrase",
        "stratum": stratum or f"{confidence}|latin|phrase",
        "inclusion_probability": 1.0,
        "design_weight": 1.0,
        "owner_weight": float(frequency),
    }


def _annotation(
    case_id: str,
    annotator: str,
    status: str,
    codes: list[str],
    *,
    certainty: str = "certain",
) -> dict:
    rationale = (
        "Required explanation."
        if status in {"ambiguous", "multi-country"} or certainty == "uncertain"
        else ""
    )
    return {
        "case_id": case_id,
        "annotator_id": annotator,
        "label_status": status,
        "country_isos": codes,
        "certainty": certainty,
        "policy_tags": [],
        "rationale": rationale,
    }


def _gold(case_id: str, status: str, codes: list[str]) -> dict:
    return {
        "schema_version": 1,
        "case_id": case_id,
        "label_status": status,
        "country_isos": codes,
        "certainty": "agreed",
        "policy_tags": [],
        "rationale": "",
        "gold_source": "agreement",
    }


def test_build_population_aggregates_without_owner_identity():
    rows = [
        {
            "login": "must-not-leak",
            "type": "User",
            "location_raw": "Berlin, Germany",
            "blog": "https://research.example.de/path",
            "frequency": 2,
        },
        {
            "login": "also-private",
            "type": "User",
            "location_raw": "Berlin, Germany",
            "blog": "research.example.de/other",
            "frequency": 3,
        },
    ]
    population = build_population(rows)
    assert len(population) == 1
    case = population[0]
    assert case["frequency"] == 5
    assert case["website_tld"] == "de"
    assert "research.example.de" not in json.dumps(case)
    assert case["prediction_country"] == "DE"
    assert "login" not in case
    assert "must-not-leak" not in json.dumps(case)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://example.de/path", "de"),
        ("example.co.uk", "uk"),
        ("localhost", None),
        ("", None),
        (None, None),
    ],
)
def test_website_tld_only_retains_the_final_suffix(value, expected):
    assert website_tld(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Berlin", "latin"),
        ("Москва", "cyrillic"),
        ("北京", "cjk"),
        ("القاهرة", "arabic"),
        ("ירושלים", "hebrew"),
        ("Αθήνα", "greek"),
        ("भारत", "indic"),
        ("กรุงเทพ", "thai"),
        ("አዲስ አበባ", "ethiopic"),
        ("Berlin 北京", "mixed"),
        (None, "empty"),
    ],
)
def test_script_group(value, expected):
    assert script_group(value) == expected


def test_sampling_is_deterministic_stratified_and_weighted():
    population = [
        _sample_case(
            f"case-{index}",
            "DE" if index % 2 else None,
            "name" if index % 2 else "unmatched",
            frequency=index + 1,
        )
        for index in range(40)
    ]
    first, first_summary = sample_population(
        population, target_size=20, seed=17, minimum_per_confidence=5
    )
    second, second_summary = sample_population(
        population, target_size=20, seed=17, minimum_per_confidence=5
    )
    assert [row["case_id"] for row in first] == [row["case_id"] for row in second]
    assert first_summary == second_summary
    assert len(first) == 20
    assert first_summary["split_counts"]["holdout"] > first_summary["split_counts"]["development"]
    assert {row["prediction_confidence"] for row in first} == {"name", "unmatched"}
    for row in first:
        probability = row["inclusion_probability"]
        assert row["design_weight"] == pytest.approx(1 / probability)
        assert row["owner_weight"] == pytest.approx(row["frequency"] / probability)


@pytest.mark.parametrize(
    ("raw", "shape"),
    [
        (None, "empty"),
        ("🇩🇪 Berlin", "flag"),
        ("me@example.de", "contact"),
        ("Berlin / NYC", "multi-part"),
        ("Berlin DE", "code"),
        ("北京", "native-script"),
        ("Berlin", "phrase"),
    ],
)
def test_evidence_shape(raw, shape):
    assert evidence_shape(raw) == shape


def test_population_and_sampling_reject_invalid_inputs():
    with pytest.raises(GeoValidationError, match="integer"):
        build_population([{"frequency": "1"}])
    with pytest.raises(GeoValidationError, match="positive"):
        build_population([{"frequency": 0}])
    with pytest.raises(GeoValidationError, match="empty"):
        sample_population([], target_size=1, seed=1)
    population = [_sample_case("one", "DE", "name")]
    with pytest.raises(GeoValidationError, match="positive"):
        sample_population(population, target_size=0, seed=1)
    with pytest.raises(GeoValidationError, match="holdout_fraction"):
        sample_population(population, target_size=1, seed=1, holdout_fraction=0.4)
    with pytest.raises(GeoValidationError, match="negative"):
        sample_population(population, target_size=1, seed=1, rare_stratum_census=-1)


def test_related_location_family_never_leaks_across_splits():
    population = [_sample_case(f"case-{index}", "DE", "name") for index in range(20)]
    population[0]["family_id"] = "shared-family"
    population[1]["family_id"] = "shared-family"
    sample, _summary = sample_population(
        population, target_size=20, seed=9, minimum_per_confidence=1
    )
    shared = {row["evaluation_split"] for row in sample if row["family_id"] == "shared-family"}
    assert len(shared) == 1


def test_sparse_strata_are_censused_before_proportional_allocation():
    population = []
    for index in range(5):
        population.append(
            _sample_case(
                f"rare-{index}",
                "DE",
                "name",
                stratum="name|cjk|native-script",
            )
        )
    for index in range(95):
        population.append(
            _sample_case(
                f"common-{index}",
                "DE",
                "name",
                stratum="name|latin|phrase",
            )
        )
    sample, _summary = sample_population(
        population,
        target_size=20,
        seed=3,
        minimum_per_confidence=1,
        rare_stratum_census=10,
    )
    assert sum(row["stratum"] == "name|cjk|native-script" for row in sample) == 5


def test_refresh_predictions_uses_current_resolver_without_changing_sampling_fields():
    source = _sample_case("Berlin", None, "unmatched")
    source["raw_location"] = "Berlin"
    refreshed = refresh_predictions([source])[0]
    assert refreshed["prediction_country"] == "DE"
    assert refreshed["prediction_confidence"] == "gazetteer-city"
    assert refreshed["stratum"] == source["stratum"]


def test_blinded_pack_omits_every_resolver_and_sampling_field():
    sample = [_sample_case("Berlin", "DE", "gazetteer-city")]
    pack = blinded_pack(sample, annotator_id="a", seed=1)
    assert len(pack) == 1
    forbidden = {
        "prediction_country",
        "prediction_confidence",
        "frequency",
        "stratum",
        "inclusion_probability",
        "design_weight",
        "owner_weight",
    }
    assert not (forbidden & set(pack[0]))
    assert pack[0]["raw_location"] == "Berlin"


def test_annotation_validation_enforces_status_country_contracts():
    case_id = _case_id("one")
    assert validate_annotation(_annotation(case_id, "a", "country", ["de"]))["country_isos"] == [
        "DE"
    ]
    with pytest.raises(GeoValidationError, match="exactly one"):
        validate_annotation(_annotation(case_id, "a", "country", ["DE", "FR"]))
    with pytest.raises(GeoValidationError, match="at least two"):
        validate_annotation(_annotation(case_id, "a", "multi-country", ["DE"]))
    with pytest.raises(GeoValidationError, match="cannot carry"):
        validate_annotation(_annotation(case_id, "a", "non-location", ["DE"]))
    with pytest.raises(GeoValidationError, match="unknown country"):
        validate_annotation(_annotation(case_id, "a", "country", ["XX"]))
    with pytest.raises(GeoValidationError, match="require a rationale"):
        validate_annotation(
            {
                **_annotation(case_id, "a", "ambiguous", ["GE", "US"]),
                "rationale": "",
            }
        )


def test_agreement_adjudication_and_gold_are_complete():
    one = _sample_case("Berlin", "DE", "gazetteer-city")
    two = _sample_case("Georgia", None, "unmatched")
    sample = [one, two]
    left = [
        _annotation(one["case_id"], "a", "country", ["DE"]),
        _annotation(two["case_id"], "a", "ambiguous", ["GE", "US"]),
    ]
    right = [
        _annotation(one["case_id"], "b", "country", ["DE"]),
        _annotation(two["case_id"], "b", "country", ["GE"]),
    ]
    summary, agreements, disagreements = compare_annotations(sample, left, right)
    assert summary["exact_agreements"] == 1
    assert summary["disagreements"] == 1
    assert (
        cohen_kappa({row["case_id"]: row for row in left}, {row["case_id"]: row for row in right})
        < 1
    )
    disagreement = dict(disagreements[0])
    disagreement.update(
        {
            "adjudicator_id": "c",
            "final_status": "ambiguous",
            "final_country_isos": ["GE", "US"],
            "final_certainty": "certain",
            "final_policy_tags": ["subdivision"],
            "final_rationale": "Country and US state are both plausible.",
        }
    )
    gold = finalize_gold(sample, agreements, [disagreement])
    assert len(gold) == 2
    assert {row["gold_source"] for row in gold} == {"agreement", "adjudication"}


def test_metrics_distinguish_precision_coverage_and_abstention():
    sample = [
        _sample_case("correct", "DE", "exact-iso", frequency=10),
        _sample_case("wrong", "US", "gazetteer-city"),
        _sample_case("missed", None, "unmatched"),
        _sample_case("good-abstention", None, "unmatched"),
        _sample_case("weak-correct", "DE", "weak"),
    ]
    gold = [
        _gold(sample[0]["case_id"], "country", ["DE"]),
        _gold(sample[1]["case_id"], "country", ["FR"]),
        _gold(sample[2]["case_id"], "country", ["FR"]),
        _gold(sample[3]["case_id"], "ambiguous", ["GE", "US"]),
        _gold(sample[4]["case_id"], "country", ["DE"]),
    ]
    report, errors = evaluate_gold(sample, gold, bootstrap_replicates=20, seed=7)
    production = report["metrics"]["unique_evidence"]["production_threshold"]
    all_predictions = report["metrics"]["unique_evidence"]["all_predictions"]
    assert production["coverage"]["estimate"] == pytest.approx(2 / 5)
    assert production["precision"]["estimate"] == pytest.approx(1 / 2)
    assert production["wrong_assignment_rate"]["estimate"] == pytest.approx(1 / 2)
    assert production["abstention_accuracy"]["estimate"] == 1
    assert all_predictions["precision"]["estimate"] == pytest.approx(2 / 3)
    assert production["precision"]["ci95"][0] < production["precision"]["estimate"]
    assert len(errors) == 3


def test_release_gates_use_predeclared_paths_and_interval_bounds():
    evaluation = {
        "cases": 2500,
        "evaluation_split": "holdout",
        "metrics": {
            "unique_evidence": {
                "production_threshold": {"precision": {"estimate": 0.995, "ci95": [0.985, 1.0]}}
            }
        },
    }
    agreement = {"cohen_kappa": 0.9}
    policy = {
        "schema_version": 1,
        "gates": [
            {
                "name": "holdout",
                "path": "evaluation.evaluation_split",
                "field": "value",
                "operator": "==",
                "threshold": "holdout",
            },
            {
                "name": "sample",
                "path": "evaluation.cases",
                "field": "value",
                "operator": ">=",
                "threshold": 2000,
            },
            {
                "name": "precision",
                "path": "evaluation.metrics.unique_evidence.production_threshold.precision",
                "field": "ci95_lower",
                "operator": ">=",
                "threshold": 0.98,
            },
            {
                "name": "agreement",
                "path": "agreement.cohen_kappa",
                "field": "value",
                "operator": ">=",
                "threshold": 0.8,
            },
        ],
    }
    result = evaluate_release_gates(evaluation, agreement, policy)
    assert result["passed"] is True
    evaluation["metrics"]["unique_evidence"]["production_threshold"]["precision"]["ci95"][0] = 0.97
    assert evaluate_release_gates(evaluation, agreement, policy)["passed"] is False


def test_manifest_verification_detects_tampering(tmp_path: Path):
    sample = tmp_path / "sample.jsonl"
    write_jsonl(sample, [{"case_id": _case_id("x")}])
    manifest = {"artifacts": {"sample.jsonl": file_sha256(sample)}}
    verify_manifest_artifacts(manifest, tmp_path)
    sample.write_text("tampered\n", encoding="utf-8")
    with pytest.raises(GeoValidationError, match="hash mismatch"):
        verify_manifest_artifacts(manifest, tmp_path)


def test_json_jsonl_manifest_and_audit_artifacts_are_deterministic(tmp_path: Path):
    document = tmp_path / "document.json"
    rows = tmp_path / "rows.jsonl"
    write_json(document, {"b": 2, "a": 1})
    write_jsonl(rows, [{"case_id": _case_id("a")}, {"case_id": _case_id("b")}])
    assert read_json(document) == {"a": 1, "b": 2}
    assert len(read_jsonl(rows)) == 2
    with pytest.raises(FileExistsError):
        write_json(document, {})
    write_json(document, {"updated": True}, overwrite=True)
    malformed = tmp_path / "malformed.jsonl"
    malformed.write_text("[]\n", encoding="utf-8")
    with pytest.raises(GeoValidationError, match="expected a JSON object"):
        read_jsonl(malformed)

    policy = tmp_path / "policy.md"
    gates = tmp_path / "gates.json"
    schema = tmp_path / "schema.json"
    challenge = tmp_path / "challenge.jsonl"
    for path in (policy, gates, schema, challenge):
        path.write_text("frozen\n", encoding="utf-8")
    manifest = build_benchmark_manifest(
        benchmark_id="benchmark",
        sample_path=rows,
        policy_path=policy,
        gates_path=gates,
        schema_path=schema,
        challenge_path=challenge,
        population_frame_hash="f" * 64,
        sampling={"sample_size": 2},
        repo_root=Path(__file__).resolve().parents[2],
    )
    verify_manifest_artifacts(manifest, tmp_path)
    provenance = runtime_provenance(Path(__file__).resolve().parents[2])
    assert provenance["resolver_version"]
    assert provenance["implementation_sha256"]
    index = audit_index(tmp_path, [document, rows])
    assert index["index_sha256"] == sha256_text(
        json.dumps(index["artifacts"], ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    assert utc_now().endswith("Z")


def test_challenge_evaluation_and_markdown_report():
    challenge, challenge_rows = evaluate_challenge_cases(
        [
            {
                "challenge_id": "germany",
                "raw_location": "Germany",
                "website_tld": None,
                "expected_country": "DE",
                "expected_confidence": "name",
                "rationale": "Explicit country.",
            }
        ]
    )
    assert challenge == {"cases": 1, "passed": 1, "failed": 0, "pass_rate": 1.0}
    assert challenge_rows[0]["passed"] is True
    with pytest.raises(GeoValidationError, match="unique"):
        evaluate_challenge_cases([challenge_rows[0], challenge_rows[0]])
    with pytest.raises(GeoValidationError, match="expected country"):
        evaluate_challenge_cases(
            [
                {
                    "challenge_id": "bad",
                    "expected_country": "XX",
                    "expected_confidence": "unmatched",
                }
            ]
        )

    sample = [_sample_case("Germany", "DE", "name")]
    gold = [_gold(sample[0]["case_id"], "country", ["DE"])]
    evaluation, _errors = evaluate_gold(sample, gold, bootstrap_replicates=2, seed=1)
    evaluation["challenge"] = challenge
    evaluation["candidate_provenance"] = {"git_commit": "abc", "git_dirty": False}
    agreement = {"exact_agreement_rate": 1.0, "cohen_kappa": 1.0}
    gates = {"passed": True, "results": []}
    report = render_markdown_report(evaluation, agreement, gates, {"benchmark_id": "benchmark"})
    assert "Owner Geolocation Validation Report" in report
    assert "Challenge conformance: 100.00%" in report


def test_csv_export_neutralizes_spreadsheet_formulas(tmp_path: Path):
    output = tmp_path / "errors.csv"
    write_csv(output, [{"raw_location": "=HYPERLINK('x')", "country": "DE"}])
    assert "'=HYPERLINK" in output.read_text(encoding="utf-8")
