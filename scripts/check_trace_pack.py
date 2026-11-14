"""Regression gate for a schema-v2 trace pack.

Static checks (no database):
  * every Agentic Much? baseline pattern in the mapping CSV resolves to rules or
    rejection-ledger entries that exist in the pack;
  * every rule id of the previous pack still exists (as a rule or a rejection);
  * every positive rule declares ``provenance.cohort`` and ``provenance.validation``.

Replay (``--run``): re-evaluates the file and branch evidence stored for a past
detection run through the new pack and reports, per legacy agent, how many
repo-agent pairs the new pack still detects. No GitHub API calls are made.

Usage::

    PYTHONPATH=<checkout>/src python scripts/check_trace_pack.py \
        --pack packs/2026-11-15.json --previous packs/2026-11-14.json \
        --mapping packs/sources/2026-11-15/baseline-mapping.csv [--run 101]
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path


def static_checks(pack_doc: dict, previous_doc: dict, mapping_path: Path) -> list[str]:
    errors: list[str] = []
    ids = {r["id"] for r in pack_doc["rules"]} | {r["id"] for r in pack_doc["rejections"]}
    with mapping_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if not row["outcome"]:
            errors.append(f"baseline {row['channel']}:{row['pattern']} has no outcome")
        for rule_id in row["rules"].split():
            if rule_id != "noise" and rule_id != "ledger" and rule_id not in ids:
                errors.append(f"baseline {row['pattern']!r} points at missing rule {rule_id}")
        if not row["rules"].strip():
            errors.append(f"baseline {row['pattern']!r} maps to nothing")
    for rule in previous_doc["rules"] + previous_doc["rejections"]:
        if rule["id"] not in ids:
            errors.append(f"previous rule {rule['id']} disappeared without a ledger entry")
    for rule in pack_doc["rules"]:
        if rule.get("disposition") != "positive":
            continue
        provenance = rule.get("provenance") or {}
        if "cohort" not in provenance or "validation" not in provenance:
            errors.append(f"rule {rule['id']} lacks provenance.cohort/validation")
    return errors


def replay(pack_path: Path, run_id: int) -> None:
    import sqlalchemy as sa

    from detect import attribution
    from detect.packs import load_pack_file
    from enrich.trees_first import FilePresence

    pack = load_pack_file(pack_path)
    engine = sa.create_engine(os.environ["DATABASE_URL"])
    files: dict[int, set[str]] = defaultdict(set)
    branches: dict[int, set[str]] = defaultdict(set)
    legacy: dict[tuple[str, int], set[str]] = defaultdict(set)
    query = sa.text(
        "SELECT agent, channel, repo_id, evidence->>'path' AS path, evidence->>'head' AS head "
        "FROM detection_evidence WHERE run_id = :run AND agent <> 'Generic' "
        "AND channel IN ('file', 'branch', 'commit_trailer', 'author', 'label', 'issue')"
    )
    with engine.connect() as connection:
        for agent, channel, repo, path, head in connection.execute(query, {"run": run_id}):
            legacy[(agent, repo)].add(channel)
            if channel == "file" and path:
                files[repo].add(path)
            elif channel == "branch" and head:
                branches[repo].add(head)
    detected: dict[int, set[str]] = defaultdict(set)
    for repo, paths in files.items():
        presence = FilePresence("replay", frozenset(paths), False, "tree")
        for hit in attribution.match_files(pack, presence):
            if hit.is_positive and hit.family_name:
                detected[repo].add(hit.family_name)
    for repo, heads in branches.items():
        for hit in attribution.match_branches(pack, sorted(heads)):
            if hit.is_positive and hit.family_name:
                detected[repo].add(hit.family_name)
    family_of = _legacy_family_names(pack)
    total, kept, identity_only = Counter(), Counter(), Counter()
    for (agent, repo), channels in legacy.items():
        total[agent] += 1
        if family_of.get(agent, agent) in detected.get(repo, set()):
            kept[agent] += 1
        elif channels <= {"commit_trailer", "author", "issue", "label"}:
            identity_only[agent] += 1
    print(f"replay of run {run_id} through {pack.version} (file + branch evidence only)")
    print(f"{'legacy agent':24s} {'pairs':>7s} {'kept':>7s} {'identity-only':>14s}")
    for agent, count in total.most_common():
        print(f"{agent:24s} {count:7d} {kept[agent]:7d} {identity_only[agent]:14d}")
    print(
        f"{'TOTAL':24s} {sum(total.values()):7d} {sum(kept.values()):7d} "
        f"{sum(identity_only.values()):14d}"
    )


def _legacy_family_names(pack) -> dict[str, str]:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from build_trace_pack_2026_11_15 import FAMILY_OF

    names = {family.id: family.name for family in pack.families}
    return {legacy: names.get(fid, legacy) for legacy, fid in FAMILY_OF.items()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--previous", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--run", type=int)
    args = parser.parse_args()
    pack_doc = json.loads(args.pack.read_text(encoding="utf-8"))
    previous_doc = json.loads(args.previous.read_text(encoding="utf-8"))
    errors = static_checks(pack_doc, previous_doc, args.mapping)
    for error in errors:
        print(f"FAIL {error}")
    print(f"static checks: {'FAILED' if errors else 'passed'} ({len(errors)} problems)")
    if args.run is not None:
        replay(args.pack, args.run)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
