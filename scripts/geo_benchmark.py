from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine, text  # noqa: E402

from enrich.geo_validation import (  # noqa: E402
    SCHEMA_VERSION,
    GeoValidationError,
    audit_index,
    blinded_pack,
    build_benchmark_manifest,
    build_population,
    canonical_json,
    compare_annotations,
    evaluate_challenge_cases,
    evaluate_gold,
    evaluate_release_gates,
    file_sha256,
    finalize_gold,
    read_json,
    read_jsonl,
    refresh_predictions,
    render_markdown_report,
    runtime_provenance,
    sample_population,
    sha256_text,
    validate_annotation,
    validate_annotation_set,
    verify_manifest_artifacts,
    write_csv,
    write_json,
    write_jsonl,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = ROOT / "docs" / "geo-validation" / "annotation-policy-v1.md"
DEFAULT_GATES = ROOT / "docs" / "geo-validation" / "release-gates-v1.json"
DEFAULT_SCHEMA = ROOT / "docs" / "geo-validation" / "artifact-schema-v1.json"
DEFAULT_CHALLENGE = ROOT / "docs" / "geo-validation" / "challenge-cases-v1.jsonl"
SAMPLE_NAME = "sample.jsonl"
MANIFEST_NAME = "manifest.json"
POPULATION_QUERY = (
    "SELECT type, location_raw, blog, count(*)::int AS frequency "
    "FROM owners GROUP BY type, location_raw, blog"
)


def _workspace(value: str) -> Path:
    return Path(value).expanduser().resolve()


def _manifest(workspace: Path) -> dict:
    path = workspace / MANIFEST_NAME
    if not path.is_file():
        raise GeoValidationError(f"missing benchmark manifest: {path}")
    manifest = read_json(path)
    if not isinstance(manifest, dict):
        raise GeoValidationError("benchmark manifest must be an object")
    verify_manifest_artifacts(manifest, workspace)
    return manifest


def _copy_frozen(source: Path, destination: Path, *, overwrite: bool) -> None:
    if destination.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{os.getpid()}.tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def _write_text(path: Path, text_value: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(text_value, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _safe_id(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value)


def _freeze_annotation(
    workspace: Path,
    annotator_id: str,
    rows: list[dict],
    *,
    overwrite: bool,
) -> Path:
    path = workspace / "annotations" / f"{_safe_id(annotator_id)}.jsonl"
    if path.exists() and not overwrite:
        temporary = path.with_name(f".{path.name}.{os.getpid()}.compare")
        write_jsonl(temporary, rows)
        try:
            if file_sha256(path) != file_sha256(temporary):
                raise GeoValidationError(
                    f"frozen annotation differs for {annotator_id}; use a new workspace"
                )
        finally:
            temporary.unlink(missing_ok=True)
        return path
    write_jsonl(path, rows, overwrite=overwrite)
    return path


def command_sample(args: argparse.Namespace) -> int:
    workspace = _workspace(args.output)
    if workspace.exists() and any(workspace.iterdir()) and not args.overwrite:
        raise FileExistsError(f"workspace is not empty: {workspace}")
    if workspace.exists() and any(workspace.iterdir()) and args.overwrite:
        existing_manifest = workspace / MANIFEST_NAME
        if not existing_manifest.is_file():
            raise GeoValidationError(
                "refusing to delete a non-benchmark directory during overwrite"
            )
        existing = read_json(existing_manifest)
        if not isinstance(existing, dict) or existing.get("schema_version") != SCHEMA_VERSION:
            raise GeoValidationError("refusing to overwrite an unknown benchmark schema")
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    engine = create_engine(args.database_url or os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            rows = connection.execute(text(POPULATION_QUERY)).mappings()
            population = build_population(rows)
    finally:
        engine.dispose()
    frame_hash = sha256_text("".join(canonical_json(row) + "\n" for row in population))
    sample, sampling = sample_population(
        population,
        target_size=args.size,
        seed=args.seed,
        minimum_per_confidence=args.minimum_per_confidence,
        holdout_fraction=args.holdout_fraction,
        rare_stratum_census=args.rare_stratum_census,
    )
    sampling["population_query_sha256"] = sha256_text(POPULATION_QUERY)
    sampling["evidence_fields"] = ["location_raw", "website_tld", "owner_type"]
    sample_path = workspace / SAMPLE_NAME
    policy_path = workspace / "annotation-policy.md"
    gates_path = workspace / "release-gates.json"
    schema_path = workspace / "artifact-schema.json"
    challenge_path = workspace / "challenge-cases.jsonl"
    write_jsonl(sample_path, sample, overwrite=args.overwrite)
    _copy_frozen(Path(args.policy), policy_path, overwrite=args.overwrite)
    _copy_frozen(Path(args.gates), gates_path, overwrite=args.overwrite)
    _copy_frozen(Path(args.schema), schema_path, overwrite=args.overwrite)
    _copy_frozen(Path(args.challenge), challenge_path, overwrite=args.overwrite)
    benchmark_id = f"geo-v{SCHEMA_VERSION}-{frame_hash[:12]}-s{args.seed}-n{len(sample)}"
    manifest = build_benchmark_manifest(
        benchmark_id=benchmark_id,
        sample_path=sample_path,
        policy_path=policy_path,
        gates_path=gates_path,
        schema_path=schema_path,
        challenge_path=challenge_path,
        population_frame_hash=frame_hash,
        sampling=sampling,
        repo_root=ROOT,
    )
    write_json(workspace / MANIFEST_NAME, manifest, overwrite=args.overwrite)
    print(
        json.dumps(
            {
                "benchmark_id": benchmark_id,
                "workspace": str(workspace),
                "population": len(population),
                "sample": len(sample),
            },
            sort_keys=True,
        )
    )
    return 0


def command_pack(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    manifest = _manifest(workspace)
    sample = read_jsonl(workspace / SAMPLE_NAME)
    pack = blinded_pack(sample, annotator_id=args.annotator, seed=args.seed)
    safe_id = _safe_id(args.annotator)
    pack_dir = workspace / "packs"
    pack_path = pack_dir / f"{safe_id}.jsonl"
    write_jsonl(pack_path, pack, overwrite=args.overwrite)
    pack_manifest = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_id": manifest["benchmark_id"],
        "annotator_id": args.annotator,
        "order_seed": args.seed,
        "sample_sha256": file_sha256(workspace / SAMPLE_NAME),
        "pack_sha256": file_sha256(pack_path),
        "cases": len(pack),
        "blinded_fields": [
            "prediction_country",
            "prediction_confidence",
            "frequency",
            "stratum",
            "inclusion_probability",
            "evaluation_split",
            "split_inclusion_probability",
            "family_id",
        ],
    }
    write_json(
        pack_path.with_suffix(".manifest.json"),
        pack_manifest,
        overwrite=args.overwrite,
    )
    print(json.dumps({"pack": str(pack_path), "cases": len(pack)}, sort_keys=True))
    return 0


_STATUS_SHORTCUTS = {
    "c": "country",
    "m": "multi-country",
    "a": "ambiguous",
    "n": "non-location",
    "i": "insufficient",
}
_CERTAINTY_SHORTCUTS = {"c": "certain", "p": "probable", "u": "uncertain"}


def _prompt_choice(prompt: str, choices: dict[str, str]) -> str:
    while True:
        value = input(prompt).strip().lower()
        if value in choices:
            return choices[value]
        if value in choices.values():
            return value
        print("Choose one of: " + ", ".join(f"{key}={label}" for key, label in choices.items()))


def _prompt_label(case_id: str, *, annotator_id: str, prefix: str = "") -> dict:
    while True:
        status = _prompt_choice(
            f"{prefix}status "
            "[c=country, m=multi, a=ambiguous, n=non-location, i=insufficient]: ",
            _STATUS_SHORTCUTS,
        )
        country_isos: list[str] | str = []
        if status in {"country", "multi-country", "ambiguous"}:
            country_isos = input(
                f"{prefix}country ISO code(s), comma-separated if needed: "
            ).strip()
        certainty = _prompt_choice(
            f"{prefix}certainty [c=certain, p=probable, u=uncertain]: ",
            _CERTAINTY_SHORTCUTS,
        )
        tags = input(f"{prefix}policy tags, comma-separated (optional): ").strip()
        rationale = input(f"{prefix}rationale (required for ambiguity/uncertainty): ").strip()
        try:
            return validate_annotation(
                {
                    "case_id": case_id,
                    "annotator_id": annotator_id,
                    "label_status": status,
                    "country_isos": country_isos,
                    "certainty": certainty,
                    "policy_tags": tags,
                    "rationale": rationale,
                }
            )
        except GeoValidationError as exc:
            print(f"Invalid annotation: {exc}")


def command_annotate(args: argparse.Namespace) -> int:
    pack_path = Path(args.pack).expanduser().resolve()
    pack_manifest = read_json(pack_path.with_suffix(".manifest.json"))
    if file_sha256(pack_path) != pack_manifest.get("pack_sha256"):
        raise GeoValidationError("annotation pack hash mismatch")
    annotator_id = str(pack_manifest["annotator_id"])
    pack = read_jsonl(pack_path)
    pack_ids = {str(row["case_id"]) for row in pack}
    if len(pack_ids) != len(pack):
        raise GeoValidationError("annotation pack contains duplicate case ids")
    output = Path(args.output).expanduser().resolve()
    completed: dict[str, dict] = {}
    if output.exists():
        completed = validate_annotation_set(
            read_jsonl(output),
            expected_case_ids=pack_ids,
            require_complete=False,
        )
        if any(not row["label_status"] for row in completed.values()):
            raise GeoValidationError("annotation output contains an incomplete saved row")
        if any(row["annotator_id"] != annotator_id for row in completed.values()):
            raise GeoValidationError("existing annotations use a different annotator id")
    print(f"Policy: {args.policy or 'use the frozen policy in the benchmark workspace'}")
    print("Predictions are intentionally hidden. Enter q at the case prompt to stop safely.")
    for index, case in enumerate(pack, start=1):
        case_id = str(case["case_id"])
        if case_id in completed:
            continue
        print("\n" + "=" * 72)
        print(f"Case {index}/{len(pack)}  {case_id[:12]}")
        print(f"Owner type: {case.get('owner_type')}")
        print(f"Location: {case.get('raw_location')!r}")
        print(f"Website TLD: {case.get('website_tld') or '—'}")
        action = (
            input("Press Enter to label, s to skip for now, q to save and quit: ").strip().lower()
        )
        if action == "q":
            break
        if action == "s":
            continue
        completed[case_id] = _prompt_label(case_id, annotator_id=annotator_id)
        write_jsonl(output, completed.values(), overwrite=True)
    write_jsonl(output, completed.values(), overwrite=True)
    print(json.dumps({"completed": len(completed), "total": len(pack), "output": str(output)}))
    return 0


def _load_complete_annotations(path: str, sample_ids: set[str]) -> list[dict]:
    rows = read_jsonl(path)
    validate_annotation_set(rows, expected_case_ids=sample_ids, require_complete=True)
    return rows


def _interactive_adjudicate(path: Path) -> None:
    rows = read_jsonl(path)
    for index, row in enumerate(rows, start=1):
        if row.get("final_status"):
            continue
        print("\n" + "=" * 72)
        print(f"Disagreement {index}/{len(rows)}  {str(row['case_id'])[:12]}")
        print(f"Location: {row.get('raw_location')!r}")
        print(f"Website TLD: {row.get('website_tld') or '—'}")
        print("Annotator A: " + canonical_json(row["annotation_a"]))
        print("Annotator B: " + canonical_json(row["annotation_b"]))
        action = input("Press Enter to adjudicate, q to save and quit: ").strip().lower()
        if action == "q":
            break
        adjudicator = input("Adjudicator id: ").strip()
        label = _prompt_label(str(row["case_id"]), annotator_id=adjudicator, prefix="final ")
        row["adjudicator_id"] = adjudicator
        row["final_status"] = label["label_status"]
        row["final_country_isos"] = label["country_isos"]
        row["final_certainty"] = label["certainty"]
        row["final_policy_tags"] = label["policy_tags"]
        row["final_rationale"] = label["rationale"]
        write_jsonl(path, rows, overwrite=True)
    write_jsonl(path, rows, overwrite=True)


def command_adjudicate(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    _manifest(workspace)
    sample = read_jsonl(workspace / SAMPLE_NAME)
    sample_ids = {str(row["case_id"]) for row in sample}
    left = _load_complete_annotations(args.annotations_a, sample_ids)
    right = _load_complete_annotations(args.annotations_b, sample_ids)
    summary, agreements, disagreements = compare_annotations(sample, left, right)
    left_id = str(summary["annotator_a"])
    right_id = str(summary["annotator_b"])
    frozen_left = _freeze_annotation(workspace, left_id, left, overwrite=args.overwrite)
    frozen_right = _freeze_annotation(workspace, right_id, right, overwrite=args.overwrite)
    summary["annotation_a_sha256"] = file_sha256(frozen_left)
    summary["annotation_b_sha256"] = file_sha256(frozen_right)
    output_dir = workspace / "adjudication"
    summary_path = output_dir / "agreement.json"
    agreements_path = output_dir / "agreements.jsonl"
    template = output_dir / "disagreements.jsonl"
    if template.exists() and not args.overwrite:
        existing_summary = read_json(summary_path)
        if existing_summary != summary:
            raise GeoValidationError("existing agreement summary does not match annotations")
        if read_jsonl(agreements_path) != agreements:
            raise GeoValidationError("existing agreements do not match annotations")
        existing = read_jsonl(template)
        expected_by_id = {str(row["case_id"]): row for row in disagreements}
        existing_by_id = {str(row["case_id"]): row for row in existing}
        if set(existing_by_id) != set(expected_by_id):
            raise GeoValidationError("existing adjudication cases do not match annotations")
        immutable = (
            "case_id",
            "raw_location",
            "website_tld",
            "owner_type",
            "annotation_a",
            "annotation_b",
        )
        for case_id, row in existing_by_id.items():
            if any(row.get(key) != expected_by_id[case_id].get(key) for key in immutable):
                raise GeoValidationError(f"existing adjudication evidence changed for {case_id}")
    else:
        write_json(summary_path, summary, overwrite=args.overwrite)
        write_jsonl(agreements_path, agreements, overwrite=args.overwrite)
        write_jsonl(template, disagreements, overwrite=args.overwrite)
    if not args.prepare_only and disagreements:
        _interactive_adjudicate(template)
    print(json.dumps({**summary, "directory": str(output_dir)}, sort_keys=True))
    return 0


def command_finalize(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    _manifest(workspace)
    sample = read_jsonl(workspace / SAMPLE_NAME)
    directory = workspace / "adjudication"
    agreements = read_jsonl(directory / "agreements.jsonl")
    disagreements = read_jsonl(directory / "disagreements.jsonl")
    gold = finalize_gold(sample, agreements, disagreements)
    output = workspace / "gold.jsonl"
    write_jsonl(output, gold, overwrite=args.overwrite)
    print(json.dumps({"gold": str(output), "cases": len(gold)}, sort_keys=True))
    return 0


def command_evaluate(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    manifest = _manifest(workspace)
    sample = read_jsonl(workspace / SAMPLE_NAME)
    gold_path = Path(args.gold).expanduser().resolve() if args.gold else workspace / "gold.jsonl"
    try:
        gold_path.relative_to(workspace)
    except ValueError as exc:
        raise GeoValidationError("gold labels must be inside the benchmark workspace") from exc
    gold = read_jsonl(gold_path)
    agreement = read_json(workspace / "adjudication" / "agreement.json")
    candidate_sample = refresh_predictions(sample)
    evaluation, errors = evaluate_gold(
        candidate_sample,
        gold,
        bootstrap_replicates=args.bootstrap,
        seed=args.seed,
        evaluation_split=args.split,
    )
    evaluation["candidate_provenance"] = runtime_provenance(ROOT)
    challenge_summary, challenge_results = evaluate_challenge_cases(
        read_jsonl(workspace / "challenge-cases.jsonl")
    )
    evaluation["challenge"] = challenge_summary
    gate_policy = read_json(workspace / "release-gates.json")
    gates = evaluate_release_gates(evaluation, agreement, gate_policy)
    output = workspace / ("audit" if args.split == "holdout" else f"audit-{args.split}")
    output.mkdir(parents=True, exist_ok=True)
    evaluation_path = output / "evaluation.json"
    gates_path = output / "gate-results.json"
    errors_jsonl = output / "error-cases.jsonl"
    errors_csv = output / "error-cases.csv"
    report_path = output / "report.md"
    predictions_path = output / "candidate-predictions.jsonl"
    challenge_path = output / "challenge-results.jsonl"
    write_json(evaluation_path, evaluation, overwrite=args.overwrite)
    write_json(gates_path, gates, overwrite=args.overwrite)
    write_jsonl(errors_jsonl, errors, overwrite=args.overwrite)
    write_jsonl(predictions_path, candidate_sample, overwrite=args.overwrite)
    write_jsonl(challenge_path, challenge_results, overwrite=args.overwrite)
    write_csv(
        errors_csv,
        errors,
        fieldnames=(
            "case_id",
            "raw_location",
            "website_tld",
            "prediction_country",
            "prediction_confidence",
            "label_status",
            "country_isos",
            "script_group",
            "evidence_shape",
            "gold_source",
            "error_type",
        ),
        overwrite=args.overwrite,
    )
    _write_text(
        report_path,
        render_markdown_report(evaluation, agreement, gates, manifest),
        overwrite=args.overwrite,
    )
    source_artifacts = [
        workspace / MANIFEST_NAME,
        workspace / SAMPLE_NAME,
        workspace / "annotation-policy.md",
        workspace / "release-gates.json",
        workspace / "artifact-schema.json",
        workspace / "challenge-cases.jsonl",
        gold_path,
        workspace / "adjudication" / "agreement.json",
        workspace / "adjudication" / "agreements.jsonl",
        workspace / "adjudication" / "disagreements.jsonl",
        evaluation_path,
        gates_path,
        errors_jsonl,
        errors_csv,
        report_path,
        predictions_path,
        challenge_path,
    ]
    source_artifacts.extend(sorted((workspace / "packs").glob("*")))
    source_artifacts.extend(sorted((workspace / "annotations").glob("*.jsonl")))
    index = audit_index(workspace, source_artifacts)
    write_json(output / "audit-index.json", index, overwrite=args.overwrite)
    print(
        json.dumps(
            {
                "passed": gates["passed"],
                "report": str(report_path),
                "audit_index": str(output / "audit-index.json"),
            },
            sort_keys=True,
        )
    )
    return 0 if gates["passed"] or args.informational else 2


def command_verify(args: argparse.Namespace) -> int:
    workspace = _workspace(args.workspace)
    manifest = _manifest(workspace)
    pack_checked = 0
    for pack_manifest_path in sorted((workspace / "packs").glob("*.manifest.json")):
        pack_manifest = read_json(pack_manifest_path)
        pack_name = pack_manifest_path.name.replace(".manifest.json", ".jsonl")
        pack_path = pack_manifest_path.with_name(pack_name)
        if pack_manifest.get("benchmark_id") != manifest.get("benchmark_id"):
            raise GeoValidationError(f"pack benchmark mismatch: {pack_name}")
        if pack_manifest.get("sample_sha256") != file_sha256(workspace / SAMPLE_NAME):
            raise GeoValidationError(f"pack sample hash mismatch: {pack_name}")
        if not pack_path.is_file() or pack_manifest.get("pack_sha256") != file_sha256(pack_path):
            raise GeoValidationError(f"pack hash mismatch: {pack_name}")
        pack_checked += 2
    index_path = workspace / "audit" / "audit-index.json"
    checked = len(manifest["artifacts"]) + pack_checked
    if index_path.is_file():
        index = read_json(index_path)
        artifacts = index.get("artifacts", {})
        if sha256_text(canonical_json(artifacts)) != index.get("index_sha256"):
            raise GeoValidationError("audit index hash is invalid")
        for relative, expected in artifacts.items():
            path = workspace / relative
            if not path.is_file() or file_sha256(path) != expected["sha256"]:
                raise GeoValidationError(f"audit artifact failed verification: {relative}")
            checked += 1
    print(json.dumps({"verified": checked, "workspace": str(workspace)}, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build and evaluate an auditable owner-geolocation benchmark."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    sample = commands.add_parser("sample", help="create a deterministic benchmark sample")
    sample.add_argument("--output", required=True)
    sample.add_argument("--size", type=int, default=3000)
    sample.add_argument("--seed", type=int, default=20261108)
    sample.add_argument("--minimum-per-confidence", type=int, default=150)
    sample.add_argument("--holdout-fraction", type=float, default=0.8)
    sample.add_argument("--rare-stratum-census", type=int, default=50)
    sample.add_argument("--database-url")
    sample.add_argument("--policy", default=str(DEFAULT_POLICY))
    sample.add_argument("--gates", default=str(DEFAULT_GATES))
    sample.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    sample.add_argument("--challenge", default=str(DEFAULT_CHALLENGE))
    sample.add_argument("--overwrite", action="store_true")
    sample.set_defaults(handler=command_sample)

    pack = commands.add_parser("pack", help="create a blinded annotator pack")
    pack.add_argument("--workspace", required=True)
    pack.add_argument("--annotator", required=True)
    pack.add_argument("--seed", type=int, required=True)
    pack.add_argument("--overwrite", action="store_true")
    pack.set_defaults(handler=command_pack)

    annotate = commands.add_parser("annotate", help="label a blinded pack interactively")
    annotate.add_argument("--pack", required=True)
    annotate.add_argument("--output", required=True)
    annotate.add_argument("--policy")
    annotate.set_defaults(handler=command_annotate)

    adjudicate = commands.add_parser(
        "adjudicate", help="compare two annotations and adjudicate disagreements"
    )
    adjudicate.add_argument("--workspace", required=True)
    adjudicate.add_argument("--annotations-a", required=True)
    adjudicate.add_argument("--annotations-b", required=True)
    adjudicate.add_argument("--prepare-only", action="store_true")
    adjudicate.add_argument("--overwrite", action="store_true")
    adjudicate.set_defaults(handler=command_adjudicate)

    finalize = commands.add_parser("finalize", help="finalize agreement and adjudication")
    finalize.add_argument("--workspace", required=True)
    finalize.add_argument("--overwrite", action="store_true")
    finalize.set_defaults(handler=command_finalize)

    evaluate = commands.add_parser("evaluate", help="evaluate gold labels and release gates")
    evaluate.add_argument("--workspace", required=True)
    evaluate.add_argument("--gold")
    evaluate.add_argument("--bootstrap", type=int, default=1000)
    evaluate.add_argument("--seed", type=int, default=20261108)
    evaluate.add_argument("--split", choices=("holdout", "development", "all"), default="holdout")
    evaluate.add_argument(
        "--informational",
        action="store_true",
        help="write development diagnostics without enforcing release-gate exit status",
    )
    evaluate.add_argument("--overwrite", action="store_true")
    evaluate.set_defaults(handler=command_evaluate)

    verify = commands.add_parser("verify", help="verify benchmark and audit hashes")
    verify.add_argument("--workspace", required=True)
    verify.set_defaults(handler=command_verify)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        return int(args.handler(args))
    except (
        GeoValidationError,
        FileExistsError,
        FileNotFoundError,
        KeyError,
        json.JSONDecodeError,
    ) as exc:
        print(f"geo benchmark error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
