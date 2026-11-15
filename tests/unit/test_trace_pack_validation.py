"""Scoring and write-back for the trace-pack validation protocol."""

from __future__ import annotations

import csv
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def validation():
    spec = importlib.util.spec_from_file_location(
        "trace_pack_validation_sample", ROOT / "scripts" / "trace_pack_validation_sample.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_wilson_interval_matches_reference_values(validation):
    low, high = validation.wilson(30, 30)
    assert round(low, 3) == 0.886  # 30/30 still misses a 0.90 lower bound
    assert high == 1.0
    low, high = validation.wilson(0, 0)
    assert (low, high) == (0.0, 0.0)


def _sheet(tmp_path: Path, rows: list[tuple[str, str, str]]) -> Path:
    path = tmp_path / "sheet.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=validation_columns())
        writer.writeheader()
        for stratum, rule_id, label in rows:
            writer.writerow({"stratum": stratum, "rule_id": rule_id, "adjudicated": label})
    return path


def validation_columns() -> list[str]:
    return ["stratum", "rule_id", "adjudicated"]


def test_score_and_apply_promote_and_demote(validation, tmp_path):
    rows = [("Claude Code|commit_trailer", "claude.trailer", "TP")] * 60
    rows += [("Amp|commit_trailer", "amp.thread", "TP")] * 6
    rows += [("Amp|commit_trailer", "amp.thread", "FP")] * 2
    rows += [("Amp|commit_trailer", "amp.thread", "unsure")]
    scores = validation.score_sheet(_sheet(tmp_path, rows))
    by_stratum = {item["stratum"]: item for item in scores}
    assert by_stratum["Claude Code|commit_trailer"]["gate"] == "strong"
    assert by_stratum["Amp|commit_trailer"]["n"] == 8  # unsure is excluded
    assert by_stratum["Amp|commit_trailer"]["gate"] == "corroborating"

    catalogue = {
        "version": "2026-11-15",
        "rules": [
            {
                "id": "claude.trailer",
                "confidence": {"class": "corroborating"},
                "provenance": {"validation": {"status": "unvalidated"}},
            },
            {
                "id": "amp.thread",
                "confidence": {"class": "strong"},
                "provenance": {"validation": {"status": "unvalidated"}},
            },
            {
                "id": "unsampled",
                "confidence": {"class": "strong"},
                "provenance": {"validation": {"status": "unvalidated"}},
            },
        ],
    }
    updated, report = validation.apply_scores(catalogue, scores, "2026-11-16")
    rules = {rule["id"]: rule for rule in updated["rules"]}
    assert updated["version"] == "2026-11-16"
    assert rules["claude.trailer"]["confidence"]["class"] == "strong"
    assert rules["claude.trailer"]["provenance"]["validation"]["status"] == "measured"
    assert rules["amp.thread"]["confidence"]["class"] == "corroborating"
    assert rules["unsampled"]["provenance"]["validation"]["status"] == "unvalidated"
    assert catalogue["rules"][0]["confidence"]["class"] == "corroborating"  # input untouched
    assert len(report) == 2
