from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from enrich.geo_validation import file_sha256, sha256_text, write_json, write_jsonl

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "geo_benchmark.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
    )


def _case(name: str, prediction: str | None, confidence: str) -> dict:
    case_id = sha256_text(name)
    return {
        "schema_version": 1,
        "case_id": case_id,
        "family_id": sha256_text("family:" + name),
        "raw_location": name,
        "website_tld": None,
        "owner_type": "User",
        "frequency": 1,
        "prediction_country": prediction,
        "prediction_confidence": confidence,
        "script_group": "latin",
        "evidence_shape": "phrase",
        "stratum": f"{confidence}|latin|phrase",
        "inclusion_probability": 1.0,
        "design_weight": 1.0,
        "owner_weight": 1.0,
        "evaluation_split": "holdout",
        "split_inclusion_probability": 0.8,
    }


def _annotation(case_id: str, annotator: str, status: str, codes: list[str]) -> dict:
    return {
        "schema_version": 1,
        "case_id": case_id,
        "annotator_id": annotator,
        "label_status": status,
        "country_isos": codes,
        "certainty": "certain",
        "policy_tags": [],
        "rationale": "Ambiguous country/state." if status == "ambiguous" else "",
    }


def test_cli_adjudication_evaluation_and_hash_verification(tmp_path: Path):
    workspace = tmp_path / "benchmark"
    workspace.mkdir()
    sample = [
        _case("Germany", "DE", "name"),
        _case("Georgia", None, "unmatched"),
        _case("Remote", None, "unmatched"),
    ]
    sample_path = workspace / "sample.jsonl"
    policy_path = workspace / "annotation-policy.md"
    gates_path = workspace / "release-gates.json"
    schema_path = workspace / "artifact-schema.json"
    challenge_path = workspace / "challenge-cases.jsonl"
    write_jsonl(sample_path, sample)
    policy_path.write_text("# Frozen test policy\n", encoding="utf-8")
    schema_path.write_text("{}\n", encoding="utf-8")
    write_jsonl(
        challenge_path,
        [
            {
                "challenge_id": "germany",
                "raw_location": "Germany",
                "website_tld": None,
                "expected_country": "DE",
                "expected_confidence": "name",
                "rationale": "Explicit country.",
            }
        ],
    )
    write_json(
        gates_path,
        {
            "schema_version": 1,
            "accepted_confidences": [
                "exact-iso",
                "name",
                "region",
                "gazetteer-city",
            ],
            "gates": [
                {
                    "name": "holdout",
                    "path": "evaluation.evaluation_split",
                    "field": "value",
                    "operator": "==",
                    "threshold": "holdout",
                },
                {
                    "name": "cases",
                    "path": "evaluation.cases",
                    "field": "value",
                    "operator": ">=",
                    "threshold": 3,
                },
            ],
        },
    )
    write_json(
        workspace / "manifest.json",
        {
            "schema_version": 1,
            "benchmark_id": "test-benchmark",
            "artifacts": {
                "sample.jsonl": file_sha256(sample_path),
                "annotation-policy.md": file_sha256(policy_path),
                "release-gates.json": file_sha256(gates_path),
                "artifact-schema.json": file_sha256(schema_path),
                "challenge-cases.jsonl": file_sha256(challenge_path),
            },
        },
    )
    left = [
        _annotation(sample[0]["case_id"], "a", "country", ["DE"]),
        _annotation(sample[1]["case_id"], "a", "ambiguous", ["GE", "US"]),
        _annotation(sample[2]["case_id"], "a", "non-location", []),
    ]
    right = [
        _annotation(sample[0]["case_id"], "b", "country", ["DE"]),
        _annotation(sample[1]["case_id"], "b", "country", ["GE"]),
        _annotation(sample[2]["case_id"], "b", "non-location", []),
    ]
    incoming = workspace / "incoming"
    write_jsonl(incoming / "a.jsonl", left)
    write_jsonl(incoming / "b.jsonl", right)

    prepared = _run(
        "adjudicate",
        "--workspace",
        str(workspace),
        "--annotations-a",
        str(incoming / "a.jsonl"),
        "--annotations-b",
        str(incoming / "b.jsonl"),
        "--prepare-only",
    )
    assert prepared.returncode == 0, prepared.stderr
    disagreements_path = workspace / "adjudication" / "disagreements.jsonl"
    disagreements = [json.loads(line) for line in disagreements_path.read_text().splitlines()]
    disagreements[0].update(
        {
            "adjudicator_id": "c",
            "final_status": "ambiguous",
            "final_country_isos": ["GE", "US"],
            "final_certainty": "certain",
            "final_policy_tags": ["subdivision"],
            "final_rationale": "Both are plausible from profile evidence.",
        }
    )
    write_jsonl(disagreements_path, disagreements, overwrite=True)

    finalized = _run("finalize", "--workspace", str(workspace))
    assert finalized.returncode == 0, finalized.stderr
    evaluated = _run(
        "evaluate",
        "--workspace",
        str(workspace),
        "--bootstrap",
        "5",
        "--split",
        "holdout",
    )
    assert evaluated.returncode == 0, evaluated.stderr
    verified = _run("verify", "--workspace", str(workspace))
    assert verified.returncode == 0, verified.stderr
    assert (workspace / "audit" / "report.md").is_file()
    assert (workspace / "audit" / "audit-index.json").is_file()
