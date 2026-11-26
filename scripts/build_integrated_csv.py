"""Build the integrated corpus CSV for Cross-Stack Comparison.

Streams the detect run's ``bundle.json`` (one record per repo with the full
detection JSON) and joins country data from ``owners`` by ``owner_login``.
Also streams ``detections.csv`` from the same bundle directory to compute
per-repo primary agent, channels fired, evidence semantics, and
"has AGENTS.md" / framework hints.

The stack label is taken from ``--stack`` (default: "JS/TS") because the
detect bundle does not carry ``language``.  Ecosystem is derived from the
stack; framework_hints is inferred from the owner_login and repo name
against a curated keyword list.

Writes to ``integrated_datasets/corpus_integrated_run<id>_<ts>.csv``.

Usage:
    DATABASE_URL=... python scripts/build_integrated_csv.py \\
        [--run-id N] [--stack "JS/TS"]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import ijson  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from serve.countries import country_name, income_group  # noqa: E402

LANG_TO_STACK = {
    "typescript": "TypeScript/JavaScript", "javascript": "TypeScript/JavaScript",
    "jsx": "TypeScript/JavaScript",        "tsx": "TypeScript/JavaScript",
    "vue": "TypeScript/JavaScript",        "svelte": "TypeScript/JavaScript",
    "python": "Python",                    "jupyter notebook": "Python",
    "java": "Java", "kotlin": "Java", "scala": "Java", "groovy": "Java",
    "rust": "Rust", "c#": "C#", "c++": "C++", "c": "C++",
    "go": "Go", "ruby": "Ruby", "php": "PHP", "swift": "Swift",
}
STACK_TO_ECOSYSTEM = {
    "JS/TS": "npm", "TypeScript/JavaScript": "npm",
    "Python": "PyPI", "Java": "Maven", "Rust": "Cargo",
    "Go": "Go Modules", "Ruby": "RubyGems", "PHP": "Packagist",
    "C#": "NuGet", "C++": "Conan/vcpkg", "Swift": "Swift PM",
}

AGENTIC_LEVELS = {"experimental", "limited", "consistent", "pervasive"}

# --- Framework hint rules ---------------------------------------------------
# Lightweight heuristic: owner_login + repo name tokens → framework/library.
# Used because repos.topics / description are empty in the current DB.
FRAMEWORK_RULES_JSTS: list[tuple[str, re.Pattern]] = [
    ("React",     re.compile(r"\b(react|redux|nextjs?|gatsby|remix|preact|refine)\b", re.I)),
    ("Vue",       re.compile(r"\b(vue|vuejs|nuxt|quasar|vite(?:press|-vue)?)\b", re.I)),
    ("Angular",   re.compile(r"\b(angular|ngrx|ionic)\b", re.I)),
    ("Svelte",    re.compile(r"\b(svelte|sveltekit)\b", re.I)),
    ("Astro",     re.compile(r"\bastro\b", re.I)),
    ("Solid",     re.compile(r"\bsolid(js|-router|-start)?\b", re.I)),
    ("Node/Server", re.compile(r"\b(express|fastify|koa|nestjs?|hono|hapi|adonis)\b", re.I)),
    ("Electron/Desktop", re.compile(r"\b(electron|tauri|neutralino)\b", re.I)),
    ("React Native/Mobile", re.compile(r"\b(react-native|expo)\b", re.I)),
    ("Testing",   re.compile(r"\b(jest|vitest|playwright|cypress|mocha)\b", re.I)),
    ("Build/Tooling", re.compile(r"\b(webpack|rollup|parcel|esbuild|vite|turborepo|nx)\b", re.I)),
    ("UI/Components", re.compile(r"\b(mui|chakra|radix|shadcn|antd|mantine|tailwind)\b", re.I)),
    ("Data/State",    re.compile(r"\b(tanstack|react-query|swr|zustand|jotai|xstate|apollo|trpc)\b", re.I)),
    ("ML/AI",      re.compile(r"\b(langchain|langgraph|llm|openai|anthropic|rag)\b", re.I)),
    ("Blockchain", re.compile(r"\b(web3|ethers|hardhat|solidity|near)\b", re.I)),
]
FRAMEWORK_RULES_PY: list[tuple[str, re.Pattern]] = [
    ("Django",     re.compile(r"\bdjango\b", re.I)),
    ("Flask",      re.compile(r"\bflask\b", re.I)),
    ("FastAPI",    re.compile(r"\bfastapi\b", re.I)),
    ("ML/AI",      re.compile(r"\b(pytorch|torch|tensorflow|keras|langchain|huggingface|transformers)\b", re.I)),
    ("Data",       re.compile(r"\b(pandas|numpy|polars|duckdb|dask)\b", re.I)),
    ("Testing",    re.compile(r"\b(pytest|unittest|tox)\b", re.I)),
]

def framework_hints_for(stack: str, full_name: str) -> list[str]:
    rules = FRAMEWORK_RULES_JSTS if stack in ("JS/TS", "TypeScript/JavaScript") else (
            FRAMEWORK_RULES_PY if stack == "Python" else [])
    if not rules:
        return []
    hits: set[str] = set()
    for name, pat in rules:
        if pat.search(full_name):
            hits.add(name)
    return sorted(hits)


COLUMNS = [
    # identity + stack
    "full_name", "owner_login", "stack", "primary_language", "ecosystem",
    "framework_hints", "stars", "commits", "authored_commits", "commit_ratio",
    # geography (expanded by compare.js)
    "country", "country_iso", "geo_confidence", "income_group",
    # adoption state
    "adoption_label", "adoption_level",
    "agents_found", "current_agents", "configured_agents", "primary_agent",
    "agent_count", "current_agent_count", "configured_agent_count",
    # evidence shape
    "channels_count", "channels_fired",
    "evidence_count", "evidence_semantics",
    "has_file_evidence", "has_commit_trailer_evidence",
    "has_pr_metadata_evidence", "has_author_evidence", "has_branch_evidence",
    "has_agents_md",
    # lifecycle counts (per repo; summed across agent families)
    "review_participation_count", "orchestration_only_count",
    "legacy_markers_count", "recovery_checkpoint_count", "ambiguous_lineage_count",
    "historical_only_count",
    # authored-commits attribution (JSON: {"Claude Code": 32, "Cursor": 11, …})
    "authored_commits_by_agent",
    # timing (all ISO; days are integers; months are YYYY-MM)
    "first_signal_at", "created_at",            # created_at kept as alias for legacy chart code
    "oldest_scanned_commit_at", "last_signal_at",
    "repo_created_at", "pushed_at",
    "first_signal_month", "first_signal_days_ago",
    "repo_age_days", "age_at_adoption_days",
    "days_since_push", "is_active_last_90d",
    # history coverage
    "history_coverage", "history_complete",
    # misc flags
    "is_archived", "license_spdx",
    # seed-corpus metadata (joined from --global-corpus by full_name)
    "ecosystem_type", "primary_language_detected", "size_stratum",
]


def load_global_corpus(path: Path | None) -> dict[str, dict]:
    """Return {full_name: {ecosystem_type, primary_language, size_stratum}} from the
    seed-phase CSV. Returns an empty dict if path is None or missing.
    """
    if not path:
        return {}
    if not path.exists():
        print(f"WARN: --global-corpus {path} not found; skipping", file=sys.stderr)
        return {}
    out: dict[str, dict] = {}
    with path.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            fn = (row.get("full_name") or "").strip()
            if not fn:
                continue
            out[fn] = {
                "ecosystem_type": row.get("ecosystem_type") or "",
                "primary_language_detected": row.get("primary_language") or "",
                "size_stratum": row.get("size_stratum") or "",
            }
    return out


def infer_stack(lang: str | None, override: str | None) -> str:
    if override:
        return override
    if not lang:
        return "Other"
    return LANG_TO_STACK.get(lang.strip().lower(), "Other")


def iso_month(iso_ts: str | None) -> str:
    return iso_ts[:7] if iso_ts else ""


def _parse_dt(iso_ts: str | None):
    if not iso_ts:
        return None
    try:
        return datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def days_between(a_iso: str | None, b_iso_or_dt):
    a = _parse_dt(a_iso)
    b = b_iso_or_dt if isinstance(b_iso_or_dt, datetime) else _parse_dt(b_iso_or_dt)
    if not a or not b:
        return ""
    return int((b - a).total_seconds() // 86400)


def pipe_join(values) -> str:
    if not values:
        return ""
    return "|".join(sorted({str(v) for v in values if v}))


def load_owner_country_map(engine) -> dict[str, dict]:
    out: dict[str, dict] = {}
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT login, country_iso, geo_confidence FROM owners WHERE country_iso IS NOT NULL"
        )).fetchall()
    for login, iso, conf in rows:
        if not login:
            continue
        out[login.strip().lower()] = {
            "country_iso":    iso or "",
            "country":        country_name(iso) or "",
            "geo_confidence": conf or "",
            "income_group":   income_group(iso) or "",
        }
    return out


def aggregate_evidence(detections_csv: Path):
    """Stream detections.csv; return per-repo aggregates."""
    family_counts: dict[str, Counter] = defaultdict(Counter)
    channel_sets:  dict[str, set]     = defaultdict(set)
    semantic_sets: dict[str, set]     = defaultdict(set)
    evidence_totals: Counter = Counter()
    has_agents_md: set[str] = set()

    if not detections_csv.exists():
        print(f"WARN: {detections_csv} not found; evidence aggregates will be empty",
              file=sys.stderr)
        return family_counts, channel_sets, semantic_sets, evidence_totals, has_agents_md

    csv.field_size_limit(1 << 30)
    with detections_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        n = 0
        for row in reader:
            full_name = (row.get("full_name") or "").strip()
            if not full_name:
                continue
            family     = (row.get("family_name") or "").strip()
            channel    = (row.get("channel") or "").strip()
            semantics  = (row.get("evidence_semantics") or "").strip()
            path       = (row.get("path") or "").strip()
            if family and family not in ("Rejected/noise", "Generic"):
                family_counts[full_name][family] += 1
            if channel:
                channel_sets[full_name].add(channel)
            if semantics:
                semantic_sets[full_name].add(semantics)
            if path and path.rsplit("/", 1)[-1] == "AGENTS.md":
                has_agents_md.add(full_name)
            evidence_totals[full_name] += 1
            n += 1
            if n % 500_000 == 0:
                print(f"  ... {n:,} evidence rows aggregated", file=sys.stderr)
    print(f"  aggregated {n:,} evidence rows across {len(evidence_totals):,} repos",
          file=sys.stderr)
    return family_counts, channel_sets, semantic_sets, evidence_totals, has_agents_md


def owner_login_from(full_name: str) -> str:
    return (full_name.split("/", 1)[0] if "/" in full_name else full_name).strip().lower()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, default=None,
                        help="Detect run id; defaults to latest detect run")
    parser.add_argument("--bundle", default=None,
                        help="Path to bundle.json (overrides run-id lookup)")
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--stack", default="JS/TS",
                        help="Stack label to assign to every repo (bundle has no language)")
    parser.add_argument("--global-corpus", default=None,
                        help="Optional seed-phase CSV providing ecosystem_type / "
                             "primary_language / size_stratum per full_name")
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])

    if args.bundle:
        bundle_path = Path(args.bundle)
        run_id = int(bundle_path.parent.name) if bundle_path.parent.name.isdigit() else 0
    else:
        with engine.connect() as conn:
            if args.run_id is None:
                row = conn.execute(text(
                    "SELECT id, bundle_dir FROM runs WHERE kind='detect' AND bundle_dir IS NOT NULL "
                    "ORDER BY id DESC LIMIT 1"
                )).fetchone()
                if not row:
                    print("ERROR: no detect run found", file=sys.stderr); return 1
                run_id, bundle_dir = int(row[0]), row[1]
            else:
                run_id = args.run_id
                row = conn.execute(text("SELECT bundle_dir FROM runs WHERE id = :id"),
                                    {"id": run_id}).fetchone()
                if not row:
                    print(f"ERROR: run {run_id} not found", file=sys.stderr); return 1
                bundle_dir = row[0]
        bundle_path = Path(__file__).resolve().parents[1] / bundle_dir / "bundle.json"

    detections_csv = bundle_path.with_name("detections.csv")
    if not bundle_path.exists():
        print(f"ERROR: {bundle_path} not found", file=sys.stderr); return 1

    print(f"Building CSV for detect run {run_id}", file=sys.stderr)
    print(f"  bundle:     {bundle_path}", file=sys.stderr)
    print(f"  detections: {detections_csv}", file=sys.stderr)
    print(f"  stack:      {args.stack}", file=sys.stderr)

    print("Loading owner → country map ...", file=sys.stderr)
    owner_map = load_owner_country_map(engine)
    print(f"  {len(owner_map):,} owners with country", file=sys.stderr)

    print("Aggregating evidence CSV ...", file=sys.stderr)
    family_counts, channel_sets, semantic_sets, evidence_totals, has_agents_md = aggregate_evidence(detections_csv)

    global_corpus = load_global_corpus(Path(args.global_corpus) if args.global_corpus else None)
    if global_corpus:
        print(f"  loaded {len(global_corpus):,} rows from --global-corpus", file=sys.stderr)

    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[1] / "integrated_datasets"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    stack_slug = re.sub(r"[^a-z0-9]+", "-", args.stack.lower()).strip("-") or "stack"
    out_path = out_dir / f"corpus_integrated_{stack_slug}_run{run_id}_{stamp}.csv"

    n = 0
    agentic = 0
    with_country = 0
    with open(out_path, "w", newline="", encoding="utf-8") as outfh, \
         open(bundle_path, "rb") as infh:
        writer = csv.DictWriter(outfh, fieldnames=COLUMNS)
        writer.writeheader()
        for item in ijson.items(infh, "items.item"):
            full_name    = item.get("full_name") or ""
            det          = item.get("detection") or {}
            repo_created = item.get("repo_created_at") or ""
            pushed_at    = item.get("pushed_at") or ""
            archived     = bool(item.get("archived"))
            license_spdx = (item.get("license_spdx") or "") or ""

            adoption_level = (det.get("adoption_level") or "none").lower()
            label = "agentic" if adoption_level in AGENTIC_LEVELS else "none"
            if label == "agentic":
                agentic += 1

            ever       = det.get("ever_observed") or []
            current    = det.get("current_activity") or []
            configured = det.get("currently_configured") or []
            channels   = det.get("channels") or {}
            channels_fired = [k for k, v in channels.items() if v == "ok"]
            first_signal  = det.get("first_signal_at")
            oldest        = det.get("oldest_scanned_commit_at")

            # Lifecycle rollups from the per-agent lifecycle array.
            lifecycle = det.get("lifecycle") or []
            review_cnt  = sum(1 for a in lifecycle if a.get("review_participation"))
            orches_cnt  = sum(1 for a in lifecycle if a.get("orchestration_only"))
            legacy_cnt  = sum(1 for a in lifecycle if a.get("legacy_marker_present"))
            recov_cnt   = sum(1 for a in lifecycle if a.get("recovery_checkpoint"))
            amb_cnt     = sum(1 for a in lifecycle if a.get("ambiguous_lineage"))
            hist_only   = sum(1 for a in lifecycle
                              if a.get("historical_activity") and not a.get("current_activity"))
            authored_by_agent = {
                a.get("family_name"): int(a.get("authored_commits") or 0)
                for a in lifecycle if a.get("family_name") and (a.get("authored_commits") or 0) > 0
            }

            owner_lc = owner_login_from(full_name)
            geo      = owner_map.get(owner_lc, {})
            if geo.get("country_iso"):
                with_country += 1

            fc = family_counts.get(full_name, Counter())
            primary = fc.most_common(1)[0][0] if fc else ""
            ch_set  = channel_sets.get(full_name, set())
            sem_set = semantic_sets.get(full_name, set())

            stack = infer_stack(item.get("language"), args.stack)

            age_days               = days_between(repo_created, now) if repo_created else ""
            age_at_adoption_days   = days_between(repo_created, first_signal) if (repo_created and first_signal) else ""
            days_since_push        = days_between(pushed_at, now) if pushed_at else ""
            is_active_last_90d     = ("1" if isinstance(days_since_push, int) and days_since_push <= 90 else "0")

            seed = global_corpus.get(full_name, {})

            writer.writerow({
                "full_name": full_name,
                "owner_login": owner_lc,
                "stack": stack,
                "primary_language": item.get("language") or "",
                "ecosystem": STACK_TO_ECOSYSTEM.get(stack, ""),
                "framework_hints": pipe_join(framework_hints_for(stack, full_name)),
                "stars": item.get("stargazers") or 0,
                "commits": det.get("total_commits") or 0,
                "authored_commits": det.get("authored_commits") or 0,
                "commit_ratio": det.get("commit_ratio") or 0,
                "country": geo.get("country", ""),
                "country_iso": geo.get("country_iso", ""),
                "geo_confidence": geo.get("geo_confidence", ""),
                "income_group": geo.get("income_group", ""),
                "adoption_label": label,
                "adoption_level": adoption_level,
                "agents_found": pipe_join(ever),
                "current_agents": pipe_join(current),
                "configured_agents": pipe_join(configured),
                "primary_agent": primary,
                "agent_count": len(ever),
                "current_agent_count": len(current),
                "configured_agent_count": len(configured),
                "channels_count": len(channels_fired),
                "channels_fired": pipe_join(channels_fired),
                "evidence_count": evidence_totals.get(full_name, 0),
                "evidence_semantics": pipe_join(sem_set),
                "has_file_evidence":           "true" if "file" in ch_set else "false",
                "has_commit_trailer_evidence": "true" if "commit_trailer" in ch_set else "false",
                "has_pr_metadata_evidence":    "true" if "pr_metadata" in ch_set else "false",
                "has_author_evidence":         "true" if "author" in ch_set else "false",
                "has_branch_evidence":         "true" if "branch" in ch_set else "false",
                "has_agents_md":               "true" if full_name in has_agents_md else "false",
                "review_participation_count": review_cnt,
                "orchestration_only_count":   orches_cnt,
                "legacy_markers_count":       legacy_cnt,
                "recovery_checkpoint_count":  recov_cnt,
                "ambiguous_lineage_count":    amb_cnt,
                "historical_only_count":      hist_only,
                "authored_commits_by_agent":  json.dumps(authored_by_agent, separators=(",", ":")) if authored_by_agent else "",
                "first_signal_at":           first_signal or "",
                "created_at":                first_signal or "",
                "oldest_scanned_commit_at":  oldest or "",
                "last_signal_at":            "",   # not available at per-repo granularity
                "repo_created_at":           repo_created or "",
                "pushed_at":                 pushed_at or "",
                "first_signal_month":        iso_month(first_signal),
                "first_signal_days_ago":     days_between(first_signal, now),
                "repo_age_days":             age_days,
                "age_at_adoption_days":      age_at_adoption_days,
                "days_since_push":           days_since_push,
                "is_active_last_90d":        is_active_last_90d,
                "history_coverage":          det.get("history_coverage") or 0,
                "history_complete":          "true" if det.get("history_complete") else "false",
                "is_archived":               "true" if archived else "false",
                "license_spdx":              license_spdx,
                "ecosystem_type":              seed.get("ecosystem_type", ""),
                "primary_language_detected":   seed.get("primary_language_detected", ""),
                "size_stratum":                seed.get("size_stratum", ""),
            })
            n += 1
            if n % 10_000 == 0:
                print(f"  ... {n:,} repos written", file=sys.stderr)

    print(f"\nWrote {n:,} rows → {out_path}", file=sys.stderr)
    print(f"  agentic:      {agentic:,} ({agentic/max(n,1):.1%})", file=sys.stderr)
    print(f"  with country: {with_country:,} ({with_country/max(n,1):.1%})", file=sys.stderr)
    print(out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
