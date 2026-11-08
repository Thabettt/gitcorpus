"""Auditable human validation for owner-country resolution.

This module never creates ground truth from resolver output. It builds a
deterministic sampling frame, emits blinded annotation packs, validates two
independent annotations, prepares adjudication, and evaluates finalized human
labels with design-aware metrics and confidence intervals.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import platform
import random
import re
import subprocess
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from importlib.metadata import version as package_version
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from enrich.geo_resolver import (
    GEO_RESOLVER_VERSION,
    KNOWN_ISO_CODES,
    normalize_location,
    resolve_location,
)

SCHEMA_VERSION = 1
LABEL_STATUSES = (
    "country",
    "multi-country",
    "ambiguous",
    "non-location",
    "insufficient",
)
ANNOTATOR_CERTAINTIES = ("certain", "probable", "uncertain")
PREDICTION_CONFIDENCES = (
    "exact-iso",
    "name",
    "region",
    "gazetteer-city",
    "geocoder",
    "weak",
    "unmatched",
)
PRODUCTION_CONFIDENCES = frozenset({"exact-iso", "name", "region", "gazetteer-city"})
DEFAULT_MINIMUM_PER_CONFIDENCE = 150
DEFAULT_BOOTSTRAP_REPLICATES = 1000
DEFAULT_HOLDOUT_FRACTION = 0.8
DEFAULT_RARE_STRATUM_CENSUS = 50
_MULTI_SEPARATOR = re.compile(r"[/|•;]|\s+[–—-]\s+|[⇄⇔↔→]")
_CONTACT = re.compile(r"(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://|www\.)")
_CODE_SHAPE = re.compile(r"(?:^|[,/|;(\s])([A-Z]{2})(?:$|[)\s])")


class GeoValidationError(ValueError):
    """A benchmark artifact violates its declared contract."""


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _atomic_write(path: Path, text: str, *, overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {path}")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def write_json(path: str | Path, value: object, *, overwrite: bool = False) -> None:
    _atomic_write(
        Path(path),
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        overwrite=overwrite,
    )


def read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_jsonl(
    path: str | Path,
    rows: Iterable[Mapping[str, object]],
    *,
    overwrite: bool = False,
) -> None:
    text = "".join(canonical_json(dict(row)) + "\n" for row in rows)
    _atomic_write(Path(path), text, overwrite=overwrite)


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise GeoValidationError(f"{path}:{line_number}: expected a JSON object")
        rows.append(value)
    return rows


def _normalized_owner_type(value: object) -> str:
    text = str(value or "Unknown").strip()
    return text if text in {"User", "Organization", "Bot"} else "Unknown"


def website_tld(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").strip(".").lower()
    return host.rsplit(".", 1)[-1] if "." in host else None


def _unicode_script(char: str) -> str | None:
    if char.isspace() or char.isdigit() or unicodedata.category(char)[0] in {"P", "S", "M"}:
        return None
    name = unicodedata.name(char, "")
    if not name:
        return "other"
    if "LATIN" in name:
        return "latin"
    if "CYRILLIC" in name:
        return "cyrillic"
    if "GREEK" in name:
        return "greek"
    if any(token in name for token in ("CJK", "HIRAGANA", "KATAKANA", "HANGUL", "IDEOGRAPH")):
        return "cjk"
    if "ARABIC" in name:
        return "arabic"
    if "HEBREW" in name:
        return "hebrew"
    if any(
        token in name
        for token in (
            "DEVANAGARI",
            "BENGALI",
            "GURMUKHI",
            "GUJARATI",
            "ORIYA",
            "TAMIL",
            "TELUGU",
            "KANNADA",
            "MALAYALAM",
            "SINHALA",
        )
    ):
        return "indic"
    if "THAI" in name:
        return "thai"
    if "ETHIOPIC" in name:
        return "ethiopic"
    return "other"


def script_group(value: str | None) -> str:
    scripts = {script for char in value or "" if (script := _unicode_script(char))}
    if not scripts:
        return "empty"
    if len(scripts) == 1:
        return next(iter(scripts))
    if scripts == {"latin", "other"}:
        return "latin-other"
    return "mixed"


def evidence_shape(raw_location: str | None) -> str:
    raw = raw_location or ""
    if not raw.strip():
        return "empty"
    if any(0x1F1E6 <= ord(char) <= 0x1F1FF for char in raw):
        return "flag"
    if _CONTACT.search(raw):
        return "contact"
    if _MULTI_SEPARATOR.search(raw):
        return "multi-part"
    if _CODE_SHAPE.search(raw):
        return "code"
    group = script_group(raw)
    if group not in {"latin", "latin-other", "empty"}:
        return "native-script"
    return "phrase"


def _case_identity(raw_location: str | None, tld: str | None, owner_type: str) -> str:
    evidence = {
        "raw_location": raw_location,
        "website_tld": tld,
        "owner_type": owner_type,
    }
    return sha256_text(canonical_json(evidence))


def _family_identity(raw_location: str | None, tld: str | None) -> str:
    evidence = {
        "normalized_location": normalize_location(raw_location or ""),
        "website_tld": tld,
    }
    return sha256_text(canonical_json(evidence))


def build_population(rows: Iterable[Mapping[str, object]]) -> list[dict[str, Any]]:
    """Aggregate de-identified owner evidence and run the candidate resolver."""
    aggregated: dict[tuple[str | None, str | None, str], int] = defaultdict(int)
    for row in rows:
        raw_value = row.get("location_raw")
        raw = raw_value if isinstance(raw_value, str) else None
        tld = website_tld(row.get("blog"))
        owner_type = _normalized_owner_type(row.get("type"))
        frequency_value = row.get("frequency", 1)
        if isinstance(frequency_value, bool) or not isinstance(frequency_value, int):
            raise GeoValidationError("population frequency must be an integer")
        if frequency_value < 1:
            raise GeoValidationError("population frequency must be positive")
        aggregated[(raw, tld, owner_type)] += frequency_value

    population: list[dict[str, Any]] = []
    for (raw, tld, owner_type), frequency in aggregated.items():
        result = resolve_location(raw, blog=f"example.{tld}" if tld else None)
        confidence = result.confidence
        if confidence not in PREDICTION_CONFIDENCES:
            raise GeoValidationError(f"unknown resolver confidence {confidence!r}")
        script = script_group(raw)
        shape = evidence_shape(raw)
        population.append(
            {
                "schema_version": SCHEMA_VERSION,
                "case_id": _case_identity(raw, tld, owner_type),
                "family_id": _family_identity(raw, tld),
                "raw_location": raw,
                "website_tld": tld,
                "owner_type": owner_type,
                "frequency": frequency,
                "prediction_country": result.country_iso,
                "prediction_confidence": confidence,
                "script_group": script,
                "evidence_shape": shape,
                "stratum": f"{confidence}|{script}|{shape}",
            }
        )
    return sorted(population, key=lambda row: row["case_id"])


def _largest_remainder(
    capacities: Mapping[str, int], total: int, *, base: int = 0
) -> dict[str, int]:
    keys = sorted(capacities)
    maximum = sum(capacities.values())
    if total < 0 or total > maximum:
        raise GeoValidationError("allocation total is outside capacity")
    if total == maximum:
        return dict(capacities)
    allocation = {key: min(capacities[key], base) for key in keys}
    if sum(allocation.values()) > total:
        allocation = {key: 0 for key in keys}
    remaining = total - sum(allocation.values())
    while remaining:
        available = {key: capacities[key] - allocation[key] for key in keys}
        available_total = sum(available.values())
        if available_total <= 0:
            break
        ideals = {key: remaining * available[key] / available_total for key in keys}
        floors = {key: min(available[key], math.floor(ideals[key])) for key in keys}
        floor_total = sum(floors.values())
        if floor_total:
            for key, value in floors.items():
                allocation[key] += value
            remaining -= floor_total
            continue
        ranked = sorted(
            (key for key in keys if available[key] > 0),
            key=lambda key: (-(ideals[key] - math.floor(ideals[key])), key),
        )
        for key in ranked[:remaining]:
            allocation[key] += 1
            remaining -= 1
    return allocation


def _derived_seed(seed: int, label: str) -> int:
    digest = hashlib.sha256(f"{seed}:{label}".encode()).digest()
    return int.from_bytes(digest[:8], "big")


def sample_population(
    population: Sequence[Mapping[str, Any]],
    *,
    target_size: int,
    seed: int,
    minimum_per_confidence: int = DEFAULT_MINIMUM_PER_CONFIDENCE,
    holdout_fraction: float = DEFAULT_HOLDOUT_FRACTION,
    rare_stratum_census: int = DEFAULT_RARE_STRATUM_CENSUS,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if target_size < 1:
        raise GeoValidationError("target_size must be positive")
    if not population:
        raise GeoValidationError("population is empty")
    if not 0.5 <= holdout_fraction < 1.0:
        raise GeoValidationError("holdout_fraction must be in [0.5, 1.0)")
    if rare_stratum_census < 0:
        raise GeoValidationError("rare_stratum_census cannot be negative")
    target_size = min(target_size, len(population))
    by_confidence: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in population:
        by_confidence[str(row["prediction_confidence"])].append(row)
    confidence_capacities = {confidence: len(rows) for confidence, rows in by_confidence.items()}
    confidence_allocation = _largest_remainder(
        confidence_capacities,
        target_size,
        base=minimum_per_confidence,
    )

    selected: list[dict[str, Any]] = []
    stratum_summary: dict[str, dict[str, float | int]] = {}
    for confidence in sorted(by_confidence):
        quota = confidence_allocation[confidence]
        strata: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in by_confidence[confidence]:
            strata[str(row["stratum"])].append(row)
        capacities = {name: len(rows) for name, rows in strata.items()}
        rare_allocation = {
            name: capacity if capacity <= rare_stratum_census else 0
            for name, capacity in capacities.items()
        }
        if sum(rare_allocation.values()) <= quota:
            residual_capacities = {
                name: capacities[name] - rare_allocation[name] for name in capacities
            }
            residual = _largest_remainder(
                residual_capacities,
                quota - sum(rare_allocation.values()),
                base=0,
            )
            allocation = {name: rare_allocation[name] + residual[name] for name in capacities}
        else:
            base = 1 if quota >= len(strata) else 0
            allocation = _largest_remainder(capacities, quota, base=base)
        for stratum in sorted(strata):
            rows = sorted(strata[stratum], key=lambda row: str(row["case_id"]))
            count = allocation[stratum]
            if count == len(rows):
                chosen = rows
            else:
                rng = random.Random(_derived_seed(seed, stratum))
                chosen = rng.sample(rows, count)
            probability = count / len(rows) if rows else 0.0
            stratum_summary[stratum] = {
                "population": len(rows),
                "sample": count,
                "inclusion_probability": probability,
            }
            for source in chosen:
                row = dict(source)
                row["inclusion_probability"] = probability
                row["design_weight"] = 1.0 / probability
                row["owner_weight"] = int(row["frequency"]) / probability
                selected.append(row)
    family_split: dict[str, str] = {}
    for row in selected:
        family_id = str(row["family_id"])
        if family_id not in family_split:
            score = _derived_seed(seed, f"split:{family_id}") / (2**64 - 1)
            family_split[family_id] = "holdout" if score < holdout_fraction else "development"
        row["evaluation_split"] = family_split[family_id]
        row["split_inclusion_probability"] = (
            holdout_fraction if row["evaluation_split"] == "holdout" else 1.0 - holdout_fraction
        )
    selected.sort(key=lambda row: row["case_id"])
    split_counts = Counter(str(row["evaluation_split"]) for row in selected)
    summary = {
        "population_size": len(population),
        "population_owner_frequency": sum(int(row["frequency"]) for row in population),
        "target_size": target_size,
        "sample_size": len(selected),
        "seed": seed,
        "minimum_per_confidence": minimum_per_confidence,
        "holdout_fraction": holdout_fraction,
        "rare_stratum_census": rare_stratum_census,
        "split_counts": dict(sorted(split_counts.items())),
        "confidence_population": dict(sorted(confidence_capacities.items())),
        "confidence_sample": dict(sorted(confidence_allocation.items())),
        "strata": dict(sorted(stratum_summary.items())),
    }
    return selected, summary


def blinded_pack(
    sample: Sequence[Mapping[str, Any]], *, annotator_id: str, seed: int
) -> list[dict[str, Any]]:
    if not annotator_id.strip():
        raise GeoValidationError("annotator_id is required")
    rows = [
        {
            "schema_version": SCHEMA_VERSION,
            "case_id": row["case_id"],
            "raw_location": row.get("raw_location"),
            "website_tld": row.get("website_tld"),
            "owner_type": row.get("owner_type"),
            "label_status": "",
            "country_isos": [],
            "certainty": "",
            "policy_tags": [],
            "rationale": "",
        }
        for row in sample
    ]
    random.Random(_derived_seed(seed, f"pack:{annotator_id}")).shuffle(rows)
    return rows


def _country_codes(value: object) -> list[str]:
    if value is None or value == "":
        return []
    if isinstance(value, str):
        parts = re.split(r"[,|\s]+", value.strip())
    elif isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        parts = [str(item) for item in value]
    else:
        raise GeoValidationError("country_isos must be a list or delimited string")
    codes = sorted({part.strip().upper() for part in parts if part.strip()})
    unknown = [code for code in codes if code not in KNOWN_ISO_CODES]
    if unknown:
        raise GeoValidationError(f"unknown country code(s): {', '.join(unknown)}")
    return codes


def validate_annotation(
    row: Mapping[str, object], *, require_complete: bool = True
) -> dict[str, Any]:
    case_id = str(row.get("case_id") or "").strip()
    if not re.fullmatch(r"[0-9a-f]{64}", case_id):
        raise GeoValidationError("annotation has an invalid case_id")
    annotator_id = str(row.get("annotator_id") or "").strip()
    if not annotator_id:
        raise GeoValidationError(f"{case_id}: annotator_id is required")
    status = str(row.get("label_status") or "").strip().lower()
    certainty = str(row.get("certainty") or "").strip().lower()
    if not require_complete and not status:
        return {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "annotator_id": annotator_id,
            "label_status": "",
            "country_isos": [],
            "certainty": "",
            "policy_tags": [],
            "rationale": str(row.get("rationale") or "").strip(),
        }
    if status not in LABEL_STATUSES:
        raise GeoValidationError(f"{case_id}: invalid label_status {status!r}")
    if certainty not in ANNOTATOR_CERTAINTIES:
        raise GeoValidationError(f"{case_id}: invalid certainty {certainty!r}")
    codes = _country_codes(row.get("country_isos"))
    if status == "country" and len(codes) != 1:
        raise GeoValidationError(f"{case_id}: country requires exactly one ISO code")
    if status == "multi-country" and len(codes) < 2:
        raise GeoValidationError(f"{case_id}: multi-country requires at least two ISO codes")
    if status in {"non-location", "insufficient"} and codes:
        raise GeoValidationError(f"{case_id}: {status} cannot carry country codes")
    rationale = str(row.get("rationale") or "").strip()
    if (certainty == "uncertain" or status in {"ambiguous", "multi-country"}) and not rationale:
        raise GeoValidationError(f"{case_id}: {status}/{certainty} annotations require a rationale")
    tags_value = row.get("policy_tags") or []
    if isinstance(tags_value, str):
        tags = sorted({tag.strip() for tag in tags_value.split(",") if tag.strip()})
    elif isinstance(tags_value, Sequence):
        tags = sorted({str(tag).strip() for tag in tags_value if str(tag).strip()})
    else:
        raise GeoValidationError(f"{case_id}: policy_tags must be a list or string")
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": case_id,
        "annotator_id": annotator_id,
        "label_status": status,
        "country_isos": codes,
        "certainty": certainty,
        "policy_tags": tags,
        "rationale": rationale,
    }


def validate_annotation_set(
    rows: Iterable[Mapping[str, object]],
    *,
    expected_case_ids: set[str] | None = None,
    require_complete: bool = True,
) -> dict[str, dict[str, Any]]:
    validated: dict[str, dict[str, Any]] = {}
    annotators: set[str] = set()
    for source in rows:
        row = validate_annotation(source, require_complete=require_complete)
        case_id = row["case_id"]
        if case_id in validated:
            raise GeoValidationError(f"duplicate annotation for {case_id}")
        validated[case_id] = row
        annotators.add(row["annotator_id"])
    if len(annotators) > 1:
        raise GeoValidationError("one annotation file contains multiple annotator ids")
    if expected_case_ids is not None:
        unknown = set(validated) - expected_case_ids
        missing = expected_case_ids - set(validated)
        if unknown:
            raise GeoValidationError(f"annotations contain {len(unknown)} unknown cases")
        if require_complete and missing:
            raise GeoValidationError(f"annotations are missing {len(missing)} cases")
    return validated


def annotation_category(row: Mapping[str, Any]) -> str:
    status = str(row["label_status"])
    codes = "|".join(_country_codes(row.get("country_isos")))
    return f"{status}:{codes}"


def cohen_kappa(
    annotations_a: Mapping[str, Mapping[str, Any]],
    annotations_b: Mapping[str, Mapping[str, Any]],
) -> float | None:
    common = sorted(set(annotations_a) & set(annotations_b))
    if not common:
        return None
    categories_a = [annotation_category(annotations_a[case_id]) for case_id in common]
    categories_b = [annotation_category(annotations_b[case_id]) for case_id in common]
    observed = sum(a == b for a, b in zip(categories_a, categories_b, strict=True)) / len(common)
    counts_a = Counter(categories_a)
    counts_b = Counter(categories_b)
    expected = sum(
        counts_a[category] / len(common) * counts_b[category] / len(common)
        for category in set(counts_a) | set(counts_b)
    )
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1.0 - expected)


def compare_annotations(
    sample: Sequence[Mapping[str, Any]],
    annotations_a: Iterable[Mapping[str, object]],
    annotations_b: Iterable[Mapping[str, object]],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    sample_by_id = {str(row["case_id"]): dict(row) for row in sample}
    expected = set(sample_by_id)
    left = validate_annotation_set(annotations_a, expected_case_ids=expected)
    right = validate_annotation_set(annotations_b, expected_case_ids=expected)
    left_id = next(iter(left.values()))["annotator_id"] if left else ""
    right_id = next(iter(right.values()))["annotator_id"] if right else ""
    if left_id == right_id:
        raise GeoValidationError("independent annotation files must use different annotator ids")

    agreements: list[dict[str, Any]] = []
    disagreements: list[dict[str, Any]] = []
    status_agreements = 0
    for case_id in sorted(expected):
        a = left[case_id]
        b = right[case_id]
        evidence = {
            key: sample_by_id[case_id].get(key)
            for key in ("case_id", "raw_location", "website_tld", "owner_type")
        }
        if a["label_status"] == b["label_status"]:
            status_agreements += 1
        if annotation_category(a) == annotation_category(b):
            agreements.append(
                {
                    **evidence,
                    "label_status": a["label_status"],
                    "country_isos": a["country_isos"],
                    "certainty_a": a["certainty"],
                    "certainty_b": b["certainty"],
                    "policy_tags": sorted(set(a["policy_tags"]) | set(b["policy_tags"])),
                    "rationale_a": a["rationale"],
                    "rationale_b": b["rationale"],
                    "gold_source": "agreement",
                }
            )
        else:
            disagreements.append(
                {
                    **evidence,
                    "annotation_a": a,
                    "annotation_b": b,
                    "adjudicator_id": "",
                    "final_status": "",
                    "final_country_isos": [],
                    "final_certainty": "",
                    "final_policy_tags": [],
                    "final_rationale": "",
                }
            )
    total = len(expected)
    exact = len(agreements)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "annotator_a": left_id,
        "annotator_b": right_id,
        "cases": total,
        "exact_agreements": exact,
        "exact_agreement_rate": exact / total if total else None,
        "status_agreements": status_agreements,
        "status_agreement_rate": status_agreements / total if total else None,
        "cohen_kappa": cohen_kappa(left, right),
        "disagreements": len(disagreements),
    }
    return summary, agreements, disagreements


def finalize_gold(
    sample: Sequence[Mapping[str, Any]],
    agreements: Sequence[Mapping[str, Any]],
    adjudications: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    expected = {str(row["case_id"]) for row in sample}
    gold: dict[str, dict[str, Any]] = {}
    for row in agreements:
        case_id = str(row["case_id"])
        if case_id in gold:
            raise GeoValidationError(f"duplicate gold agreement for {case_id}")
        gold[case_id] = {
            "schema_version": SCHEMA_VERSION,
            "case_id": case_id,
            "label_status": row["label_status"],
            "country_isos": _country_codes(row.get("country_isos")),
            "certainty": "agreed",
            "policy_tags": sorted({str(tag) for tag in row.get("policy_tags", [])}),
            "rationale": " | ".join(
                value
                for value in (
                    str(row.get("rationale_a") or "").strip(),
                    str(row.get("rationale_b") or "").strip(),
                )
                if value
            ),
            "gold_source": "agreement",
        }
    for row in adjudications:
        case_id = str(row.get("case_id") or "")
        adjudicator = str(row.get("adjudicator_id") or "").strip()
        if not adjudicator:
            raise GeoValidationError(f"{case_id}: adjudicator_id is required")
        validated = validate_annotation(
            {
                "case_id": case_id,
                "annotator_id": adjudicator,
                "label_status": row.get("final_status"),
                "country_isos": row.get("final_country_isos"),
                "certainty": row.get("final_certainty"),
                "policy_tags": row.get("final_policy_tags"),
                "rationale": row.get("final_rationale"),
            }
        )
        if case_id in gold:
            raise GeoValidationError(f"{case_id}: adjudication overlaps an agreement")
        gold[case_id] = {
            **validated,
            "gold_source": "adjudication",
        }
        gold[case_id].pop("annotator_id", None)
    unknown = set(gold) - expected
    missing = expected - set(gold)
    if unknown:
        raise GeoValidationError(f"gold labels contain {len(unknown)} unknown cases")
    if missing:
        raise GeoValidationError(f"gold labels are missing {len(missing)} cases")
    return [gold[case_id] for case_id in sorted(gold)]


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator > 0 else None


def _metric(
    numerator: float,
    denominator: float,
    *,
    numerator_cases: int,
    denominator_cases: int,
    denominator_weight_squares: float,
) -> dict[str, float | int | list[float] | None]:
    estimate = _safe_ratio(numerator, denominator)
    effective_n = (
        denominator * denominator / denominator_weight_squares
        if denominator_weight_squares > 0
        else 0.0
    )
    interval: list[float] | None = None
    if estimate is not None and effective_n > 0:
        z = 1.959963984540054
        scale = 1.0 + z * z / effective_n
        center = (estimate + z * z / (2.0 * effective_n)) / scale
        margin = (
            z
            * math.sqrt(
                estimate * (1.0 - estimate) / effective_n
                + z * z / (4.0 * effective_n * effective_n)
            )
            / scale
        )
        interval = [max(0.0, center - margin), min(1.0, center + margin)]
    return {
        "estimate": estimate,
        "numerator_weight": numerator,
        "denominator_weight": denominator,
        "numerator_cases": numerator_cases,
        "denominator_cases": denominator_cases,
        "effective_n": effective_n,
        "ci95": interval,
    }


def _evaluation_flags(row: Mapping[str, Any], accepted: frozenset[str]) -> dict[str, bool]:
    prediction = row.get("prediction_country")
    confidence = str(row.get("prediction_confidence"))
    assigned = isinstance(prediction, str) and confidence in accepted
    status = row["label_status"]
    gold_codes = _country_codes(row.get("country_isos"))
    resolvable = status == "country" and len(gold_codes) == 1
    correct = assigned and resolvable and prediction == gold_codes[0]
    wrong = assigned and not correct
    abstained = not assigned
    unresolvable = not resolvable
    return {
        "assigned": assigned,
        "resolvable": resolvable,
        "correct": correct,
        "wrong": wrong,
        "abstained": abstained,
        "unresolvable": unresolvable,
        "false_abstention": abstained and resolvable,
        "correct_abstention": abstained and unresolvable,
        "decision_correct": correct or (abstained and unresolvable),
    }


def _metric_block(
    rows: Sequence[Mapping[str, Any]],
    *,
    weight_key: str,
    accepted: frozenset[str],
) -> dict[str, Any]:
    totals: Counter[str] = Counter()
    cases: Counter[str] = Counter()
    weight_squares: Counter[str] = Counter()
    for row in rows:
        weight = float(row[weight_key])
        flags = _evaluation_flags(row, accepted)
        totals["all"] += weight
        cases["all"] += 1
        weight_squares["all"] += weight * weight
        for name, enabled in flags.items():
            if enabled:
                totals[name] += weight
                cases[name] += 1
                weight_squares[name] += weight * weight
    return {
        "cases": len(rows),
        "effective_weight": totals["all"],
        "coverage": _metric(
            totals["assigned"],
            totals["all"],
            numerator_cases=cases["assigned"],
            denominator_cases=cases["all"],
            denominator_weight_squares=weight_squares["all"],
        ),
        "precision": _metric(
            totals["correct"],
            totals["assigned"],
            numerator_cases=cases["correct"],
            denominator_cases=cases["assigned"],
            denominator_weight_squares=weight_squares["assigned"],
        ),
        "wrong_assignment_rate": _metric(
            totals["wrong"],
            totals["assigned"],
            numerator_cases=cases["wrong"],
            denominator_cases=cases["assigned"],
            denominator_weight_squares=weight_squares["assigned"],
        ),
        "wrong_population_rate": _metric(
            totals["wrong"],
            totals["all"],
            numerator_cases=cases["wrong"],
            denominator_cases=cases["all"],
            denominator_weight_squares=weight_squares["all"],
        ),
        "resolvable_recall": _metric(
            totals["correct"],
            totals["resolvable"],
            numerator_cases=cases["correct"],
            denominator_cases=cases["resolvable"],
            denominator_weight_squares=weight_squares["resolvable"],
        ),
        "false_abstention_rate": _metric(
            totals["false_abstention"],
            totals["resolvable"],
            numerator_cases=cases["false_abstention"],
            denominator_cases=cases["resolvable"],
            denominator_weight_squares=weight_squares["resolvable"],
        ),
        "abstention_accuracy": _metric(
            totals["correct_abstention"],
            totals["unresolvable"],
            numerator_cases=cases["correct_abstention"],
            denominator_cases=cases["unresolvable"],
            denominator_weight_squares=weight_squares["unresolvable"],
        ),
        "decision_accuracy": _metric(
            totals["decision_correct"],
            totals["all"],
            numerator_cases=cases["decision_correct"],
            denominator_cases=cases["all"],
            denominator_weight_squares=weight_squares["all"],
        ),
    }


def _partition(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        result[str(row.get(key) or "unknown")].append(row)
    return dict(sorted(result.items()))


def _partition_gold_country(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        codes = _country_codes(row.get("country_isos"))
        if row.get("label_status") == "country" and len(codes) == 1:
            key = codes[0]
        else:
            key = str(row.get("label_status") or "unknown")
        result[key].append(row)
    return dict(sorted(result.items()))


def _core_metric_views(rows: Sequence[Mapping[str, Any]], *, weight_key: str) -> dict[str, Any]:
    all_confidences = frozenset(PREDICTION_CONFIDENCES) - {"unmatched"}
    return {
        "all_predictions": _metric_block(rows, weight_key=weight_key, accepted=all_confidences),
        "production_threshold": _metric_block(
            rows, weight_key=weight_key, accepted=PRODUCTION_CONFIDENCES
        ),
        "by_confidence": {
            name: _metric_block(
                group,
                weight_key=weight_key,
                accepted=all_confidences,
            )
            for name, group in _partition(rows, "prediction_confidence").items()
        },
    }


def metric_views(rows: Sequence[Mapping[str, Any]], *, weight_key: str) -> dict[str, Any]:
    all_confidences = frozenset(PREDICTION_CONFIDENCES) - {"unmatched"}

    def grouped(key: str, accepted: frozenset[str] = all_confidences) -> dict[str, Any]:
        return {
            name: _metric_block(
                group,
                weight_key=weight_key,
                accepted=accepted,
            )
            for name, group in _partition(rows, key).items()
        }

    def gold_country_grouped(accepted: frozenset[str]) -> dict[str, Any]:
        return {
            name: _metric_block(group, weight_key=weight_key, accepted=accepted)
            for name, group in _partition_gold_country(rows).items()
        }

    non_latin = [
        row for row in rows if row.get("script_group") not in {"latin", "latin-other", "empty"}
    ]

    return {
        **_core_metric_views(rows, weight_key=weight_key),
        "by_script": grouped("script_group"),
        "by_script_production": grouped("script_group", PRODUCTION_CONFIDENCES),
        "by_evidence_shape": grouped("evidence_shape"),
        "by_evidence_shape_production": grouped("evidence_shape", PRODUCTION_CONFIDENCES),
        "by_owner_type": grouped("owner_type"),
        "by_owner_type_production": grouped("owner_type", PRODUCTION_CONFIDENCES),
        "by_gold_country": gold_country_grouped(all_confidences),
        "by_gold_country_production": gold_country_grouped(PRODUCTION_CONFIDENCES),
        "non_latin_production": _metric_block(
            non_latin,
            weight_key=weight_key,
            accepted=PRODUCTION_CONFIDENCES,
        ),
    }


def _metric_paths(value: Mapping[str, Any], prefix: tuple[str, ...] = ()) -> list[tuple[str, ...]]:
    paths: list[tuple[str, ...]] = []
    for key, child in value.items():
        current = (*prefix, key)
        if isinstance(child, Mapping) and "estimate" in child:
            paths.append(current)
        elif isinstance(child, Mapping):
            paths.extend(_metric_paths(child, current))
    return paths


def _path_get(value: Mapping[str, Any], path: Sequence[str]) -> Any:
    current: Any = value
    for part in path:
        current = current[part]
    return current


def _percentile(values: Sequence[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def _stratified_resample(
    rows: Sequence[Mapping[str, Any]], rng: random.Random
) -> list[Mapping[str, Any]]:
    families = _partition(rows, "family_id")
    strata: dict[str, list[list[Mapping[str, Any]]]] = defaultdict(list)
    for family_rows in families.values():
        family_stratum = min(str(row["stratum"]) for row in family_rows)
        strata[family_stratum].append(family_rows)
    sampled: list[Mapping[str, Any]] = []
    for stratum in sorted(strata):
        family_groups = strata[stratum]
        for _ in range(len(family_groups)):
            sampled.extend(rng.choice(family_groups))
    return sampled


def attach_bootstrap_intervals(
    views: dict[str, Any],
    rows: Sequence[Mapping[str, Any]],
    *,
    weight_key: str,
    replicates: int,
    seed: int,
) -> None:
    if replicates < 1:
        raise GeoValidationError("bootstrap replicates must be positive")
    paths = _metric_paths(views)
    distributions: dict[tuple[str, ...], list[float]] = {path: [] for path in paths}
    rng = random.Random(seed)
    for _ in range(replicates):
        replicate = _core_metric_views(_stratified_resample(rows, rng), weight_key=weight_key)
        for path in paths:
            try:
                estimate = _path_get(replicate, path).get("estimate")
            except KeyError:
                continue
            if isinstance(estimate, (int, float)):
                distributions[path].append(float(estimate))
    for path, values in distributions.items():
        metric = _path_get(views, path)
        lower = _percentile(values, 0.025)
        upper = _percentile(values, 0.975)
        analytic = metric.get("ci95")
        if lower is not None and upper is not None:
            if isinstance(analytic, list) and len(analytic) == 2:
                lower = min(lower, analytic[0])
                upper = max(upper, analytic[1])
            metric["ci95"] = [lower, upper]


def join_sample_and_gold(
    sample: Sequence[Mapping[str, Any]], gold: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    sample_by_id: dict[str, dict[str, Any]] = {}
    for row in sample:
        case_id = str(row.get("case_id") or "")
        if case_id in sample_by_id:
            raise GeoValidationError(f"duplicate sample case {case_id}")
        sample_by_id[case_id] = dict(row)
    gold_by_id: dict[str, dict[str, Any]] = {}
    for source in gold:
        allowed_gold_fields = {
            "schema_version",
            "case_id",
            "label_status",
            "country_isos",
            "certainty",
            "policy_tags",
            "rationale",
            "gold_source",
        }
        extras = set(source) - allowed_gold_fields
        if extras:
            raise GeoValidationError(
                "gold label contains unexpected fields: " + ", ".join(sorted(extras))
            )
        case_id = str(source.get("case_id") or "")
        if not re.fullmatch(r"[0-9a-f]{64}", case_id):
            raise GeoValidationError("gold label has an invalid case_id")
        if case_id in gold_by_id:
            raise GeoValidationError(f"duplicate gold case {case_id}")
        if int(source.get("schema_version", 0)) != SCHEMA_VERSION:
            raise GeoValidationError(f"{case_id}: unsupported gold schema version")
        status = str(source.get("label_status") or "")
        if status not in LABEL_STATUSES:
            raise GeoValidationError(f"{case_id}: invalid gold label status")
        codes = _country_codes(source.get("country_isos"))
        if status == "country" and len(codes) != 1:
            raise GeoValidationError(f"{case_id}: country gold label needs one code")
        if status == "multi-country" and len(codes) < 2:
            raise GeoValidationError(f"{case_id}: multi-country gold label needs two codes")
        if status in {"non-location", "insufficient"} and codes:
            raise GeoValidationError(f"{case_id}: {status} gold label cannot carry codes")
        gold_source = str(source.get("gold_source") or "")
        if gold_source not in {"agreement", "adjudication"}:
            raise GeoValidationError(f"{case_id}: invalid gold source")
        gold_by_id[case_id] = {
            "schema_version": source.get("schema_version", SCHEMA_VERSION),
            "case_id": case_id,
            "label_status": status,
            "country_isos": codes,
            "certainty": source.get("certainty"),
            "policy_tags": source.get("policy_tags") or [],
            "rationale": source.get("rationale") or "",
            "gold_source": gold_source,
        }
    if set(sample_by_id) != set(gold_by_id):
        raise GeoValidationError("sample and gold case ids do not match")
    return [{**sample_by_id[case_id], **gold_by_id[case_id]} for case_id in sorted(sample_by_id)]


def refresh_predictions(
    sample: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    refreshed: list[dict[str, Any]] = []
    for source in sample:
        row = dict(source)
        raw = row.get("raw_location")
        location = raw if isinstance(raw, str) else None
        tld = row.get("website_tld")
        blog = f"example.{tld}" if isinstance(tld, str) else None
        result = resolve_location(location, blog=blog)
        row["prediction_country"] = result.country_iso
        row["prediction_confidence"] = result.confidence
        row["evaluated_resolver_version"] = GEO_RESOLVER_VERSION
        refreshed.append(row)
    return refreshed


def evaluate_challenge_cases(
    cases: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in cases:
        challenge_id = str(source.get("challenge_id") or "").strip()
        if not challenge_id or challenge_id in seen:
            raise GeoValidationError("challenge cases need unique non-empty ids")
        seen.add(challenge_id)
        expected_country = source.get("expected_country")
        if expected_country is not None and expected_country not in KNOWN_ISO_CODES:
            raise GeoValidationError(f"{challenge_id}: invalid expected country")
        expected_confidence = str(source.get("expected_confidence") or "")
        if expected_confidence not in PREDICTION_CONFIDENCES:
            raise GeoValidationError(f"{challenge_id}: invalid expected confidence")
        raw = source.get("raw_location")
        location = raw if isinstance(raw, str) else None
        tld = source.get("website_tld")
        blog = f"example.{tld}" if isinstance(tld, str) and tld else None
        prediction = resolve_location(location, blog=blog)
        passed = (
            prediction.country_iso == expected_country
            and prediction.confidence == expected_confidence
        )
        results.append(
            {
                **source,
                "prediction_country": prediction.country_iso,
                "prediction_confidence": prediction.confidence,
                "passed": passed,
            }
        )
    passed_count = sum(bool(row["passed"]) for row in results)
    summary = {
        "cases": len(results),
        "passed": passed_count,
        "failed": len(results) - passed_count,
        "pass_rate": passed_count / len(results) if results else None,
    }
    return summary, results


def evaluate_gold(
    sample: Sequence[Mapping[str, Any]],
    gold: Sequence[Mapping[str, Any]],
    *,
    bootstrap_replicates: int = DEFAULT_BOOTSTRAP_REPLICATES,
    seed: int = 0,
    evaluation_split: str = "all",
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = join_sample_and_gold(sample, gold)
    if evaluation_split not in {"all", "development", "holdout"}:
        raise GeoValidationError("evaluation_split must be all, development, or holdout")
    if evaluation_split != "all":
        rows = [row for row in rows if row.get("evaluation_split") == evaluation_split]
        adjusted: list[dict[str, Any]] = []
        for source in rows:
            row = dict(source)
            probability = float(row.get("split_inclusion_probability") or 0.0)
            if not 0.0 < probability <= 1.0:
                raise GeoValidationError("sample has an invalid split inclusion probability")
            row["design_weight"] = float(row["design_weight"]) / probability
            row["owner_weight"] = float(row["owner_weight"]) / probability
            adjusted.append(row)
        rows = adjusted
    if not rows:
        raise GeoValidationError(f"no gold cases in evaluation split {evaluation_split}")
    unique = metric_views(rows, weight_key="design_weight")
    owner = metric_views(rows, weight_key="owner_weight")
    attach_bootstrap_intervals(
        unique,
        rows,
        weight_key="design_weight",
        replicates=bootstrap_replicates,
        seed=_derived_seed(seed, "bootstrap:unique"),
    )
    attach_bootstrap_intervals(
        owner,
        rows,
        weight_key="owner_weight",
        replicates=bootstrap_replicates,
        seed=_derived_seed(seed, "bootstrap:owner"),
    )
    errors: list[dict[str, Any]] = []
    for row in rows:
        flags = _evaluation_flags(row, PRODUCTION_CONFIDENCES)
        if flags["wrong"] or flags["false_abstention"]:
            errors.append(
                {
                    **row,
                    "error_type": ("wrong-assignment" if flags["wrong"] else "false-abstention"),
                }
            )
    report = {
        "schema_version": SCHEMA_VERSION,
        "resolver_version": GEO_RESOLVER_VERSION,
        "cases": len(rows),
        "bootstrap_replicates": bootstrap_replicates,
        "bootstrap_seed": seed,
        "evaluation_split": evaluation_split,
        "metrics": {
            "unique_evidence": unique,
            "owner_weighted": owner,
        },
        "production_confidences": sorted(PRODUCTION_CONFIDENCES),
        "error_cases": len(errors),
    }
    return report, errors


def _resolve_report_path(context: Mapping[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise GeoValidationError(f"release gate path does not exist: {path}")
        current = current[part]
    return current


def _gate_value(value: Any, field: str) -> str | float | int | None:
    if field == "value":
        return (
            value if isinstance(value, (str, int, float)) and not isinstance(value, bool) else None
        )
    if not isinstance(value, Mapping):
        return None
    if field == "ci95_lower":
        interval = value.get("ci95")
        return interval[0] if isinstance(interval, list) and len(interval) == 2 else None
    if field == "ci95_upper":
        interval = value.get("ci95")
        return interval[1] if isinstance(interval, list) and len(interval) == 2 else None
    candidate = value.get(field)
    return candidate if isinstance(candidate, (int, float)) else None


def _compare_gate(actual: str | float | int, operator: str, expected: str | float | int) -> bool:
    if isinstance(actual, str) or isinstance(expected, str):
        if operator != "==" or not isinstance(actual, str) or not isinstance(expected, str):
            raise GeoValidationError("string release gates only support string equality")
    operations = {
        ">=": lambda: actual >= expected,
        ">": lambda: actual > expected,
        "<=": lambda: actual <= expected,
        "<": lambda: actual < expected,
        "==": lambda: actual == expected,
    }
    if operator not in operations:
        raise GeoValidationError(f"unsupported release gate operator {operator!r}")
    return operations[operator]()


def evaluate_release_gates(
    evaluation: Mapping[str, Any],
    agreement: Mapping[str, Any],
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    if int(policy.get("schema_version", 0)) != SCHEMA_VERSION:
        raise GeoValidationError("unsupported release gate schema")
    accepted = policy.get("accepted_confidences")
    if accepted is not None and frozenset(str(item) for item in accepted) != PRODUCTION_CONFIDENCES:
        raise GeoValidationError(
            "release gate accepted_confidences do not match the production threshold"
        )
    gates = policy.get("gates")
    if not isinstance(gates, list) or not gates:
        raise GeoValidationError("release gate policy must contain gates")
    context = {"evaluation": evaluation, "agreement": agreement}
    results: list[dict[str, Any]] = []
    for source in gates:
        if not isinstance(source, Mapping):
            raise GeoValidationError("release gate must be an object")
        name = str(source.get("name") or "").strip()
        path = str(source.get("path") or "").strip()
        field = str(source.get("field") or "value").strip()
        operator = str(source.get("operator") or "").strip()
        expected = source.get("threshold")
        if (
            not name
            or not path
            or isinstance(expected, bool)
            or not isinstance(expected, (str, int, float))
        ):
            raise GeoValidationError("release gate is missing name/path/threshold")
        error: str | None = None
        try:
            value = _resolve_report_path(context, path)
            actual = _gate_value(value, field)
            passed = actual is not None and _compare_gate(actual, operator, expected)
        except GeoValidationError as exc:
            actual = None
            passed = False
            error = str(exc)
        results.append(
            {
                "name": name,
                "path": path,
                "field": field,
                "operator": operator,
                "threshold": expected,
                "actual": actual,
                "passed": passed,
                "error": error,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "passed": all(result["passed"] for result in results),
        "passed_count": sum(result["passed"] for result in results),
        "gate_count": len(results),
        "results": results,
    }


def _git_output(repo_root: Path, *args: str) -> bytes | None:
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout


def runtime_provenance(repo_root: str | Path) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    commit_raw = (_git_output(root, "rev-parse", "HEAD") or b"").strip()
    commit = commit_raw.decode("ascii", errors="replace") or None
    status = _git_output(root, "status", "--porcelain=v1", "--untracked-files=all")
    diff = _git_output(root, "diff", "--binary", "HEAD")
    implementation_paths = (
        "src/enrich/geo_resolver.py",
        "src/enrich/geo_validation.py",
        "src/enrich/graphql_owner_location.py",
        "src/serve/runner.py",
        "scripts/geo_benchmark.py",
        "requirements.txt",
    )
    hashes = {
        relative: file_sha256(root / relative)
        for relative in implementation_paths
        if (root / relative).is_file()
    }
    return {
        "git_commit": commit,
        "git_dirty": bool(status and status.strip()),
        "git_status_sha256": hashlib.sha256(status or b"").hexdigest(),
        "git_diff_sha256": hashlib.sha256(diff or b"").hexdigest(),
        "implementation_sha256": hashes,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "geonamescache": package_version("geonamescache"),
        "resolver_version": GEO_RESOLVER_VERSION,
    }


def build_benchmark_manifest(
    *,
    benchmark_id: str,
    sample_path: str | Path,
    policy_path: str | Path,
    gates_path: str | Path,
    schema_path: str | Path,
    challenge_path: str | Path,
    population_frame_hash: str,
    sampling: Mapping[str, Any],
    repo_root: str | Path,
) -> dict[str, Any]:
    sample_file = Path(sample_path)
    policy_file = Path(policy_path)
    gates_file = Path(gates_path)
    schema_file = Path(schema_path)
    challenge_file = Path(challenge_path)
    return {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": benchmark_id,
        "created_at": utc_now(),
        "state": "sampled-unlabeled",
        "population_frame_sha256": population_frame_hash,
        "sampling": dict(sampling),
        "provenance": runtime_provenance(repo_root),
        "artifacts": {
            sample_file.name: file_sha256(sample_file),
            policy_file.name: file_sha256(policy_file),
            gates_file.name: file_sha256(gates_file),
            schema_file.name: file_sha256(schema_file),
            challenge_file.name: file_sha256(challenge_file),
        },
    }


def verify_manifest_artifacts(manifest: Mapping[str, Any], workspace: str | Path) -> None:
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise GeoValidationError("manifest has no artifact hashes")
    root = Path(workspace)
    for relative, expected in artifacts.items():
        path = root / str(relative)
        if not path.is_file():
            raise GeoValidationError(f"missing manifest artifact {relative}")
        actual = file_sha256(path)
        if actual != expected:
            raise GeoValidationError(f"artifact hash mismatch for {relative}")


def audit_index(root: str | Path, paths: Iterable[str | Path]) -> dict[str, Any]:
    base = Path(root).resolve()
    artifacts: dict[str, dict[str, Any]] = {}
    for source in sorted({Path(path).resolve() for path in paths}, key=str):
        relative = source.relative_to(base).as_posix()
        artifacts[relative] = {
            "sha256": file_sha256(source),
            "bytes": source.stat().st_size,
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "artifacts": artifacts,
        "index_sha256": sha256_text(canonical_json(artifacts)),
    }


def _csv_cell(value: object) -> object:
    if isinstance(value, (dict, list)):
        return canonical_json(value)
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@"}:
        return "'" + value
    return value


def write_csv(
    path: str | Path,
    rows: Sequence[Mapping[str, Any]],
    *,
    fieldnames: Sequence[str] | None = None,
    overwrite: bool = False,
) -> None:
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    columns = list(fieldnames or sorted({key for row in rows for key in row}))
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=columns,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(row.get(key)) for key in columns})
    os.replace(temporary, target)


def _format_percent(value: object) -> str:
    return "—" if not isinstance(value, (int, float)) else f"{value * 100:.2f}%"


def render_markdown_report(
    evaluation: Mapping[str, Any],
    agreement: Mapping[str, Any],
    gates: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> str:
    unique = evaluation["metrics"]["unique_evidence"]
    owner = evaluation["metrics"]["owner_weighted"]
    lines = [
        "# Owner Geolocation Validation Report",
        "",
        f"- Benchmark: `{manifest.get('benchmark_id', 'unknown')}`",
        f"- Resolver: `{evaluation.get('resolver_version')}`",
        f"- Evaluation split: `{evaluation.get('evaluation_split')}`",
        f"- Candidate commit: `{evaluation.get('candidate_provenance', {}).get('git_commit')}`",
        f"- Candidate tree dirty: `{evaluation.get('candidate_provenance', {}).get('git_dirty')}`",
        f"- Gold cases: {evaluation.get('cases')}",
        "- Challenge conformance: "
        + _format_percent(evaluation.get("challenge", {}).get("pass_rate")),
        f"- Independent exact agreement: {_format_percent(agreement.get('exact_agreement_rate'))}",
        f"- Cohen's kappa: {agreement.get('cohen_kappa')}",
        f"- Release gates: **{'PASS' if gates.get('passed') else 'FAIL'}**",
        "",
        "## Primary metrics",
        "",
        "| Weighting | View | Coverage | Precision | Wrong assignment | Resolvable recall |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for label, views in (("Unique evidence", unique), ("Owner weighted", owner)):
        for view_name, title in (
            ("production_threshold", "Production threshold"),
            ("all_predictions", "All assignments"),
        ):
            block = views[view_name]
            lines.append(
                "| "
                + " | ".join(
                    (
                        label,
                        title,
                        _format_percent(block["coverage"]["estimate"]),
                        _format_percent(block["precision"]["estimate"]),
                        _format_percent(block["wrong_assignment_rate"]["estimate"]),
                        _format_percent(block["resolvable_recall"]["estimate"]),
                    )
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Confidence tiers",
            "",
            "| Tier | Cases | Precision | 95% CI | Coverage |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for confidence, block in unique["by_confidence"].items():
        precision = block["precision"]
        interval = precision.get("ci95")
        interval_text = (
            "—"
            if not interval
            else f"{_format_percent(interval[0])}–{_format_percent(interval[1])}"
        )
        lines.append(
            f"| `{confidence}` | {block['cases']} | "
            f"{_format_percent(precision['estimate'])} | {interval_text} | "
            f"{_format_percent(block['coverage']['estimate'])} |"
        )
    lines.extend(
        [
            "",
            "## Bias diagnostics at the production threshold",
            "",
            "| Dimension | Group | Cases | Assigned | Precision | 95% CI |",
            "|---|---|---:|---:|---:|---:|",
        ]
    )
    for dimension, groups in (
        ("Script", unique["by_script_production"]),
        ("Owner type", unique["by_owner_type_production"]),
    ):
        for group, block in groups.items():
            precision = block["precision"]
            interval = precision.get("ci95")
            interval_text = (
                "—"
                if not interval
                else f"{_format_percent(interval[0])}–{_format_percent(interval[1])}"
            )
            lines.append(
                f"| {dimension} | `{group}` | {block['cases']} | "
                f"{precision['denominator_cases']} | "
                f"{_format_percent(precision['estimate'])} | {interval_text} |"
            )
    lines.extend(
        [
            "",
            "## Release gates",
            "",
            "| Gate | Actual | Requirement | Result |",
            "|---|---:|---:|---:|",
        ]
    )
    for gate in gates.get("results", []):
        lines.append(
            f"| {gate['name']} | {gate['actual']} | "
            f"{gate['operator']} {gate['threshold']} | "
            f"{'PASS' if gate['passed'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "- The target is a self-reported current profile location, not nationality, "
            "residence, or repository origin.",
            "- Ambiguous, multi-country, fictional, and missing evidence is correctly "
            "allowed to remain unmatched.",
            "- Point estimates and intervals are sampling-frame dependent; report both "
            "unique-evidence and owner-weighted results.",
            "- Resolver, GeoNames, policy, sample, annotations, and reports are "
            "content-hashed in the audit index.",
            "",
        ]
    )
    return "\n".join(lines)
