"""Enrich the JS/TS integrated CSV with real framework data.

Joins the existing integrated CSV with ``stacks_data/JS-TS/repo_frameworks.csv``
on ``full_name``. Drops the fabricated ``ecosystem`` and ``framework_hints``
columns, and adds the real framework columns derived from package.json scans:
``frameworks``, ``categories``, ``typescript``, ``monorepo``, ``package_json_count``.

Writes a new dated file to ``integrated_datasets/`` — does NOT overwrite
the input.

Usage::

    python scripts/enrich_jsts_integrated.py \\
        --integrated integrated_datasets/corpus_integrated_js-ts_run4_20261119_170535.csv \\
        --frameworks stacks_data/JS-TS/repo_frameworks.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from datetime import UTC, datetime
from pathlib import Path

DROP_COLUMNS = {"ecosystem", "framework_hints"}
ADD_COLUMNS = ["frameworks", "categories", "typescript", "monorepo", "package_json_count"]


def load_frameworks(path: Path) -> dict[str, dict[str, str]]:
    csv.field_size_limit(1 << 30)
    out: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            fn = (row.get("full_name") or "").strip()
            if not fn:
                continue
            out[fn] = {
                "frameworks": (row.get("frameworks") or "").strip(),
                "categories": (row.get("categories") or "").strip(),
                "typescript": (row.get("typescript") or "").strip(),
                "monorepo": (row.get("monorepo") or "").strip(),
                "package_json_count": (row.get("package_json_count") or "").strip(),
            }
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--integrated", required=True, help="Existing JS/TS integrated CSV")
    ap.add_argument("--frameworks", required=True, help="repo_frameworks.csv")
    ap.add_argument("--out-dir", default=None, help="Default: <repo-root>/integrated_datasets")
    ap.add_argument("--out-name", default=None, help="Override output filename")
    args = ap.parse_args()

    integrated = Path(args.integrated)
    frameworks_csv = Path(args.frameworks)
    for p in (integrated, frameworks_csv):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            return 1

    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[1] / "integrated_datasets"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / (args.out_name or f"corpus_integrated_js-ts_enriched_{stamp}.csv")

    print(f"Loading framework data from {frameworks_csv} ...", file=sys.stderr)
    fw_map = load_frameworks(frameworks_csv)
    print(f"  {len(fw_map):,} repos with framework data", file=sys.stderr)

    csv.field_size_limit(1 << 30)
    n_rows = 0
    n_matched = 0
    n_with_frameworks = 0
    with integrated.open("r", encoding="utf-8-sig", newline="") as fh_in, \
         out_path.open("w", encoding="utf-8", newline="") as fh_out:
        reader = csv.DictReader(fh_in)
        in_fields = reader.fieldnames or []
        kept = [c for c in in_fields if c not in DROP_COLUMNS]
        out_fields = kept + ADD_COLUMNS
        writer = csv.DictWriter(fh_out, fieldnames=out_fields)
        writer.writeheader()

        for row in reader:
            fn = (row.get("full_name") or "").strip()
            out_row = {c: row.get(c, "") for c in kept}
            fw = fw_map.get(fn)
            if fw:
                n_matched += 1
                if fw.get("frameworks"):
                    n_with_frameworks += 1
                for c in ADD_COLUMNS:
                    out_row[c] = fw.get(c, "")
            else:
                for c in ADD_COLUMNS:
                    out_row[c] = ""
            writer.writerow(out_row)
            n_rows += 1
            if n_rows % 10_000 == 0:
                print(f"  wrote {n_rows:,} rows", file=sys.stderr)

    print(f"Done. {n_rows:,} rows | {n_matched:,} matched "
          f"({n_matched / n_rows * 100:.1f}%) | "
          f"{n_with_frameworks:,} with frameworks "
          f"({n_with_frameworks / n_rows * 100:.1f}%)",
          file=sys.stderr)
    print(f"Output: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
