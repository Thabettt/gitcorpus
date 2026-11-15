"""Draw the stratified validation sample for a detection run.

Design (docs/findings/2026-11-15-trace-pack-audit.md §5 step 4; after the census
paper, arXiv 2606.24429, and the Agentic Much? protocol, arXiv 2601.18341 §4.1.3):

* the ten most prevalent families get one stratum per (family, channel);
* every other family is pooled into one stratum per channel (``other|<channel>``),
  so small families get a channel-level precision instead of untestable cells;
* n = 60 rows per stratum (the whole stratum when smaller), one row per
  repository (per repository and family when pooled);
* two independent raters label every row TP / FP / unsure / 404, then adjudicate;
* file rows get a second label: configuration genuine vs evidence of use.

Precision per stratum is reported with a Wilson 95% interval; a rule is
``strong`` only when the lower bound is at least 0.90. n = 60 is the smallest
round size that clears that bar with one false positive (59/60 -> 0.911); 30/30
would only reach 0.886, so smaller cells can never earn ``strong``. The labelled
CSV is committed next to the pack version it validates.

Usage::

    PYTHONPATH=<checkout>/src python scripts/trace_pack_validation_sample.py draw \
        --run <run> --out packs/validation/2026-11-15/sample.csv [--seed 20261115]
    python scripts/trace_pack_validation_sample.py score \
        --sheet packs/validation/2026-11-15/sample.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
from collections import Counter, defaultdict
from pathlib import Path

TOP_FAMILIES = 10
N_PER_STRATUM = 60
COLUMNS = [
    "stratum",
    "family",
    "channel",
    "rule_id",
    "repo",
    "evidence",
    "github_url",
    "rater_a",
    "rater_b",
    "adjudicated",
    "file_usage",
    "notes",
]


def wilson(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def github_url(repo: str, channel: str, evidence: dict) -> str:
    if evidence.get("commit"):
        return f"https://github.com/{repo}/commit/{evidence['commit']}"
    if evidence.get("pr") or (channel == "pr_metadata" and evidence.get("number")):
        return f"https://github.com/{repo}/pull/{evidence.get('pr') or evidence.get('number')}"
    if channel == "issue" and evidence.get("number"):
        return f"https://github.com/{repo}/issues/{evidence['number']}"
    if evidence.get("path"):
        return f"https://github.com/{repo}/blob/HEAD/{evidence['path']}"
    return f"https://github.com/{repo}"


def draw(run_id: int, seed: int) -> list[dict]:
    import sqlalchemy as sa

    engine = sa.create_engine(os.environ["DATABASE_URL"])
    query = sa.text(
        "SELECT de.family_name, de.channel, de.rule_id, i.full_name, de.evidence "
        "FROM detection_evidence de JOIN run_items i "
        "ON i.run_id = de.run_id AND i.repo_id = de.repo_id "
        "WHERE de.run_id = :run AND de.family_name IS NOT NULL "
        "AND coalesce((de.metric_eligibility->>'repository_presence')::boolean, true)"
    )
    cells: dict[tuple[str, str], list[tuple]] = defaultdict(list)
    with engine.connect() as connection:
        for family, channel, rule_id, repo, evidence in connection.execute(query, {"run": run_id}):
            if isinstance(evidence, str):
                evidence = json.loads(evidence)
            evidence = evidence or {}
            if channel == "file" and evidence.get("source") == "gitignore":
                # Ignored-only mentions are their own population (Agentic Much? §5).
                channel = "file:gitignore"
            cells[(family, channel)].append((rule_id, repo, evidence))
    prevalence = Counter()
    for (family, _channel), rows in cells.items():
        prevalence[family] += len({repo for _rule, repo, _ev in rows})
    top = {family for family, _count in prevalence.most_common(TOP_FAMILIES)}
    strata: dict[str, dict[tuple[str, str], tuple]] = defaultdict(dict)
    for (family, channel), rows in cells.items():
        stratum = f"{family}|{channel}" if family in top else f"other|{channel}"
        # One row per repository (and family) so a single noisy repo cannot fill a cell.
        for rule_id, repo, evidence in rows:
            strata[stratum].setdefault((repo, family), (family, channel, rule_id, repo, evidence))
    rng = random.Random(seed)
    sample: list[dict] = []
    for stratum, keyed in sorted(strata.items()):
        pool = sorted(keyed.values(), key=lambda row: (row[3], row[0]))
        rng.shuffle(pool)
        for family, channel, rule_id, repo, evidence in pool[:N_PER_STRATUM]:
            sample.append(
                {
                    "stratum": stratum,
                    "family": family,
                    "channel": channel,
                    "rule_id": rule_id,
                    "repo": repo,
                    "evidence": json.dumps(evidence, sort_keys=True)[:400],
                    "github_url": github_url(repo, channel, evidence),
                    "rater_a": "",
                    "rater_b": "",
                    "adjudicated": "",
                    "file_usage": "" if channel == "file" else "n/a",
                    "notes": "",
                }
            )
    return sample


STRONG_LOWER_BOUND = 0.90


def score_sheet(path: Path) -> list[dict]:
    """Per-stratum precision with Wilson intervals from an adjudicated sheet."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    cells: dict[str, Counter] = defaultdict(Counter)
    rule_ids: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        label = (row.get("adjudicated") or "").strip().upper()
        if label in {"TP", "FP"}:
            cells[row["stratum"]][label] += 1
            if row.get("rule_id"):
                rule_ids[row["stratum"]].add(row["rule_id"])
    scores = []
    for stratum, counts in sorted(cells.items()):
        n = counts["TP"] + counts["FP"]
        low, high = wilson(counts["TP"], n)
        scores.append(
            {
                "stratum": stratum,
                "n": n,
                "tp": counts["TP"],
                "precision": round(counts["TP"] / n, 4),
                "ci95": [round(low, 4), round(high, 4)],
                "gate": "strong" if low >= STRONG_LOWER_BOUND else "corroborating",
                "rule_ids": sorted(rule_ids[stratum]),
                "sheet": path.name,
            }
        )
    return scores


def summarize(path: Path, out: Path | None = None) -> None:
    scores = score_sheet(path)
    print(f"{'stratum':50s} {'n':>4s} {'precision':>9s} {'95% CI':>15s} gate")
    for item in scores:
        low, high = item["ci95"]
        print(
            f"{item['stratum']:50s} {item['n']:4d} {item['precision']:9.3f} "
            f"[{low:.3f}, {high:.3f}] {item['gate']}"
        )
    if out is not None:
        out.write_text(json.dumps(scores, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {len(scores)} scored strata to {out}")


def apply_scores(catalogue: dict, scores: list[dict], version: str) -> tuple[dict, list[str]]:
    """Return a new catalogue version whose sampled rules carry measured validation.

    Every rule seen in a scored stratum gets that stratum's precision, interval and
    sample size, and is ``strong`` only when the interval's lower bound clears the
    gate; otherwise it becomes ``corroborating``. Unsampled rules are untouched.
    The input catalogue is not modified: frozen versions never change.
    """
    updated = json.loads(json.dumps(catalogue))
    updated["version"] = version
    by_rule: dict[str, dict] = {}
    for item in scores:
        for rule_id in item["rule_ids"]:
            by_rule[rule_id] = item
    report: list[str] = []
    for rule in updated["rules"]:
        item = by_rule.get(rule["id"])
        if item is None:
            continue
        rule["provenance"]["validation"] = {
            "status": "measured",
            "precision": item["precision"],
            "ci95": item["ci95"],
            "n": item["n"],
            "stratum": item["stratum"],
            "sheet": item["sheet"],
        }
        previous = rule["confidence"]["class"]
        rule["confidence"]["class"] = item["gate"]
        if previous != item["gate"]:
            report.append(
                f"{rule['id']}: {previous} -> {item['gate']} "
                f"(precision {item['precision']}, lower bound {item['ci95'][0]})"
            )
    return updated, report


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    draw_cmd = sub.add_parser("draw")
    draw_cmd.add_argument("--run", type=int, required=True)
    draw_cmd.add_argument("--out", type=Path, required=True)
    draw_cmd.add_argument("--seed", type=int, default=20261115)
    score = sub.add_parser("score")
    score.add_argument("--sheet", type=Path, required=True)
    score.add_argument("--out", type=Path, help="write per-stratum scores as JSON")
    apply_cmd = sub.add_parser("apply")
    apply_cmd.add_argument("--catalogue", type=Path, required=True)
    apply_cmd.add_argument("--scores", type=Path, required=True)
    apply_cmd.add_argument("--version", required=True, help="the NEW pack version")
    apply_cmd.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "score":
        summarize(args.sheet, args.out)
        return 0
    if args.command == "apply":
        catalogue = json.loads(args.catalogue.read_text(encoding="utf-8"))
        if catalogue.get("version") == args.version:
            parser.error("apply writes a new version; frozen packs never change")
        scores = json.loads(args.scores.read_text(encoding="utf-8"))
        updated, report = apply_scores(catalogue, scores, args.version)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(
            json.dumps(updated, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        for line in report:
            print(line)
        print(f"wrote {args.out} ({len(report)} confidence changes)")
        return 0
    rows = draw(args.run, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows across {len({r['stratum'] for r in rows})} strata to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
