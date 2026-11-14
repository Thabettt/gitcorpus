"""Draw the stratified validation sample for a detection run.

Design (docs/findings/2026-11-15-trace-pack-audit.md §5 step 4; after the census
paper, arXiv 2606.24429, and the Agentic Much? protocol, arXiv 2601.18341 §4.1.3):

* one stratum per (family, channel) cell that produced positive evidence;
* n = 30 for cells of the ten most prevalent families, n = 8 for the rest
  (the whole cell when it is smaller);
* two independent raters label every row TP / FP / unsure / 404, then adjudicate;
* file rows get a second label: configuration genuine vs evidence of use.

Precision per cell is reported with a Wilson 95% interval; a rule is ``strong``
only when the lower bound is at least 0.90. The labelled CSV is committed next to
the pack version it validates.

Usage::

    PYTHONPATH=<checkout>/src python scripts/trace_pack_validation_sample.py draw \
        --run <run> --out packs/validation/2026-11-15/sample.csv [--seed 20261115]
    python scripts/trace_pack_validation_sample.py score \
        --sheet packs/validation/2026-11-15/sample.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import random
from collections import Counter, defaultdict
from pathlib import Path

TOP_FAMILIES = 10
N_TOP = 30
N_OTHER = 8
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
    import json

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
    rng = random.Random(seed)
    sample: list[dict] = []
    for (family, channel), rows in sorted(cells.items()):
        size = N_TOP if family in top else N_OTHER
        # One row per repository first, so a single noisy repo cannot fill a cell.
        by_repo: dict[str, tuple] = {}
        for row in rows:
            by_repo.setdefault(row[1], row)
        pool = list(by_repo.values())
        rng.shuffle(pool)
        for rule_id, repo, evidence in pool[:size]:
            sample.append(
                {
                    "stratum": f"{family}|{channel}",
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


def summarize(path: Path) -> None:
    """Print per-stratum precision with Wilson intervals from a labelled sheet."""
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    cells: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        label = (row.get("adjudicated") or "").strip().upper()
        if label in {"TP", "FP"}:
            cells[row["stratum"]][label] += 1
    print(f"{'stratum':50s} {'n':>4s} {'precision':>9s} {'95% CI':>15s} gate")
    for stratum, counts in sorted(cells.items()):
        n = counts["TP"] + counts["FP"]
        low, high = wilson(counts["TP"], n)
        gate = "strong" if low >= 0.90 else "corroborating/reject"
        print(f"{stratum:50s} {n:4d} {counts['TP'] / n:9.3f} [{low:.3f}, {high:.3f}] {gate}")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    draw_cmd = sub.add_parser("draw")
    draw_cmd.add_argument("--run", type=int, required=True)
    draw_cmd.add_argument("--out", type=Path, required=True)
    draw_cmd.add_argument("--seed", type=int, default=20261115)
    score = sub.add_parser("score")
    score.add_argument("--sheet", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "score":
        summarize(args.sheet)
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
