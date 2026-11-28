"""Export JS/TS raw per-repo detect CSV from the on-disk run bundle.

Run 4 (JS/TS, 60,129 repos) completed detection and wrote its per-repo
documents to ``bundle.json`` on disk, but the DB persistence step didn't
finish (run status = cancelled, run_items empty). The bundle itself has
the full detection payload for every repo, so we can reconstruct the
per-repo CSV that the live export endpoint would have produced.

Schema matches ``DETECT_REPO_CSV_HEADER`` in ``src/serve/runs.py`` so the
output is drop-in compatible with ``build_integrated_from_csvs.py``.

Per-channel evidence row counts come from aggregating the companion raw
``detections.csv`` for the same run.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RUN_DIR = REPO_ROOT / "runs" / (
    "157a81585a78245133f25fd4e7304c7ea9cfa8f1a1be96554007ddfd0b2a8a72"
) / "4"
DEFAULT_OUT = (
    REPO_ROOT / "stacks_data" / "JS-TS"
    / "gitcorpus-detect-4-2026-11-16-repos-js-ts.csv"
)

# Mirror of DETECT_REPO_CSV_HEADER in src/serve/runs.py.
CSV_HEADER = [
    "repo_id", "full_name", "stargazers", "repo_created_at", "commit_count",
    "pushed_at", "archived", "language", "license_spdx",
    "country_iso", "geo_confidence", "country",
    "has_signal", "unavailable", "failure_class",
    "adoption_level", "commit_ratio",
    "history_window_commits", "history_eligible_commits", "total_commits",
    "history_coverage", "history_complete", "first_signal_at",
    "agents", "ever_observed", "currently_configured",
    "current_activity", "historical_activity", "authored_commits",
    "review_participation", "orchestration_only", "legacy_markers",
    "recovery_checkpoint", "ambiguous_lineage",
    "evidence_rows", "signal_rows", "bot_rows",
    "file_rows", "content_rows", "author_rows", "branch_rows", "label_rows",
    "commit_trailer_rows", "pr_metadata_rows", "issue_rows", "hidden_ref_rows",
]


def _truthy(v) -> bool:
    return str(v or "").strip().lower() in {"true", "t", "1", "yes"}


def _pipe(values) -> str:
    if not values:
        return ""
    return "|".join(sorted({str(v) for v in values if v}))


def _bool_str(v) -> str:
    if v is None:
        return ""
    return "true" if bool(v) else "false"


def _cell(v) -> str:
    if v is None:
        return ""
    return str(v)


def aggregate_detections(path: Path) -> dict[str, dict[str, int]]:
    """Return per-repo channel/row counts from detections.csv."""
    csv.field_size_limit(1 << 30)
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {
        "total_rows": 0,
        "signal_rows": 0,
        "bot_rows": 0,
        "file_rows": 0,
        "content_rows": 0,
        "author_rows": 0,
        "branch_rows": 0,
        "label_rows": 0,
        "commit_trailer_rows": 0,
        "pr_metadata_rows": 0,
        "issue_rows": 0,
        "hidden_ref_rows": 0,
    })
    print(f"Aggregating {path} ...", file=sys.stderr)
    n = 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            n += 1
            fn = (row.get("full_name") or "").strip()
            if not fn:
                continue
            c = counts[fn]
            channel = (row.get("channel") or "").strip().lower()
            c["total_rows"] += 1
            # signal_rows: non-bot rows passing repository_presence eligibility
            if channel != "bot" and _truthy(row.get("repository_presence_eligible")):
                c["signal_rows"] += 1
            key = f"{channel}_rows"
            if key in c:
                c[key] += 1
            if n % 500_000 == 0:
                print(f"  scanned {n:,} rows, {len(counts):,} repos so far",
                      file=sys.stderr)
    print(f"  total: {n:,} rows, {len(counts):,} repos", file=sys.stderr)
    return counts


def row_from_bundle_item(item: dict, counts: dict[str, int] | None) -> dict:
    full_name = (item.get("full_name") or "").strip()
    doc = item.get("detection") or {}
    agents = doc.get("agents") or []
    counts = counts or {
        "total_rows": 0, "signal_rows": 0, "bot_rows": 0, "file_rows": 0,
        "content_rows": 0, "author_rows": 0, "branch_rows": 0, "label_rows": 0,
        "commit_trailer_rows": 0, "pr_metadata_rows": 0, "issue_rows": 0,
        "hidden_ref_rows": 0,
    }
    return {
        "repo_id": _cell(item.get("repo_id")),
        "full_name": full_name,
        "stargazers": _cell(item.get("stargazers")),
        "repo_created_at": _cell(item.get("repo_created_at")),
        "commit_count": _cell(item.get("commit_count")),
        "pushed_at": _cell(item.get("pushed_at")),
        "archived": _bool_str(item.get("archived")),
        "language": _cell(item.get("language")),
        "license_spdx": _cell(item.get("license_spdx")),
        "country_iso": _cell(item.get("country_iso")),
        "geo_confidence": _cell(item.get("geo_confidence")),
        "country": _cell(item.get("country")),
        "has_signal": _bool_str(bool(agents)),
        "unavailable": _bool_str(bool(doc.get("unavailable", False))),
        "failure_class": _cell(doc.get("failure_class")),
        "adoption_level": _cell(doc.get("adoption_level")),
        "commit_ratio": _cell(doc.get("commit_ratio")),
        "history_window_commits": _cell(doc.get("history_window_commits")),
        "history_eligible_commits": _cell(doc.get("history_eligible_commits")),
        "total_commits": _cell(doc.get("total_commits")),
        "history_coverage": _cell(doc.get("history_coverage")),
        "history_complete": _bool_str(doc.get("history_complete")),
        "first_signal_at": _cell(doc.get("first_signal_at")),
        "agents": _pipe(agents),
        "ever_observed": _pipe(doc.get("ever_observed")),
        "currently_configured": _pipe(doc.get("currently_configured")),
        "current_activity": _pipe(doc.get("current_activity")),
        "historical_activity": _pipe(doc.get("historical_activity")),
        "authored_commits": _cell(doc.get("authored_commits")),
        "review_participation": _pipe(doc.get("review_participation")),
        "orchestration_only": _pipe(doc.get("orchestration_only")),
        "legacy_markers": _pipe(doc.get("legacy_markers")),
        "recovery_checkpoint": _pipe(doc.get("recovery_checkpoint")),
        "ambiguous_lineage": _pipe(doc.get("ambiguous_lineage")),
        "evidence_rows": counts["total_rows"],
        "signal_rows": counts["signal_rows"],
        "bot_rows": counts["bot_rows"],
        "file_rows": counts["file_rows"],
        "content_rows": counts["content_rows"],
        "author_rows": counts["author_rows"],
        "branch_rows": counts["branch_rows"],
        "label_rows": counts["label_rows"],
        "commit_trailer_rows": counts["commit_trailer_rows"],
        "pr_metadata_rows": counts["pr_metadata_rows"],
        "issue_rows": counts["issue_rows"],
        "hidden_ref_rows": counts["hidden_ref_rows"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run-dir", default=str(DEFAULT_RUN_DIR))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    bundle_path = run_dir / "bundle.json"
    detections_path = run_dir / "detections.csv"
    out_path = Path(args.out)

    for p in (bundle_path, detections_path):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            return 1

    counts = aggregate_detections(detections_path)

    print(f"Loading {bundle_path} ...", file=sys.stderr)
    with bundle_path.open("r", encoding="utf-8") as fh:
        bundle = json.load(fh)
    items = bundle.get("items") or []
    print(f"  {len(items):,} items", file=sys.stderr)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    n_total = 0
    n_signal = 0
    n_agentic = 0
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        fh.write("\ufeff")
        writer = csv.DictWriter(fh, fieldnames=CSV_HEADER)
        writer.writeheader()
        for item in items:
            fn = (item.get("full_name") or "").strip()
            if not fn:
                continue
            row = row_from_bundle_item(item, counts.get(fn))
            writer.writerow(row)
            n_total += 1
            if row["has_signal"] == "true":
                n_signal += 1
            lvl = (row["adoption_level"] or "").strip().lower()
            if lvl and lvl != "none":
                n_agentic += 1

    sig_pct = (n_signal / n_total * 100) if n_total else 0.0
    ag_pct = (n_agentic / n_total * 100) if n_total else 0.0
    print(f"Done. {n_total:,} repos written", file=sys.stderr)
    print(f"  has_signal=true:    {n_signal:,} ({sig_pct:.1f}%)", file=sys.stderr)
    print(f"  adoption agentic:   {n_agentic:,} ({ag_pct:.1f}%)", file=sys.stderr)
    print(f"Output: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
