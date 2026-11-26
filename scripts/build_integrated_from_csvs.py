"""Build the integrated corpus CSV from the detect tool's **CSV exports**.

Companion to ``build_integrated_csv.py`` which reads the local bundle.json.
This variant reads two CSVs shipped by teammates who ran detection
themselves (one row per repo + one row per evidence record):

    gitcorpus-detect-<run>-<date>-repos-<stack>.csv
    gitcorpus-detect-<run>-<date>-evidence.csv

Output schema matches the JS/TS integrated CSV so the file can be uploaded
directly in the Cross Stack Comparison dashboard.

Usage::

    python scripts/build_integrated_from_csvs.py \\
        --stack Go \\
        --repos-csv  "stacks_data/GO/gitcorpus-detect-3-2026-11-15-repos-go.csv" \\
        --evidence-csv "stacks_data/GO/gitcorpus-detect-3-2026-11-15-evidence.csv"
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from serve.countries import country_name, income_group  # noqa: E402

AGENTIC_LEVELS = {"experimental", "limited", "consistent", "pervasive"}

STACK_TO_ECOSYSTEM = {
    "JS/TS": "npm", "TypeScript/JavaScript": "npm",
    "Python": "PyPI", "Java": "Maven", "Rust": "Cargo",
    "Go": "Go Modules", "Ruby": "RubyGems", "PHP": "Packagist",
    "C#": "NuGet", "C++": "Conan/vcpkg", "Swift": "Swift PM",
}

# --- Framework hint rules (kept in sync with build_integrated_csv.py) -------
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
FRAMEWORK_RULES_GO: list[tuple[str, re.Pattern]] = [
    ("Web/HTTP",   re.compile(r"\b(gin|echo|fiber|chi|mux|gorilla|beego|iris|revel|buffalo)\b", re.I)),
    ("gRPC/RPC",   re.compile(r"\b(grpc|protobuf|twirp|connect)\b", re.I)),
    ("CLI/Tooling",   re.compile(r"\b(cobra|cli|urfave|cmd|tool|go-tool)\b", re.I)),
    ("Kubernetes/Cloud", re.compile(r"\b(k8s|kubernetes|kube|operator|controller|helm|terraform|crossplane|argo|istio|envoy)\b", re.I)),
    ("DevOps/Infra",  re.compile(r"\b(docker|container|ansible|packer|vault|consul|nomad|prometheus|grafana|loki|tempo)\b", re.I)),
    ("DB/Storage",    re.compile(r"\b(gorm|sqlx|ent|bun|xorm|postgres|mysql|sqlite|redis|mongo|etcd|cockroach|tidb|dgraph)\b", re.I)),
    ("Messaging",     re.compile(r"\b(nats|kafka|rabbitmq|pulsar|nsq)\b", re.I)),
    ("Testing",       re.compile(r"\b(testify|ginkgo|gomega|mockery|ghz)\b", re.I)),
    ("Blockchain",    re.compile(r"\b(geth|ethereum|solana|cosmos|tendermint|ipfs|libp2p|chain|web3)\b", re.I)),
    ("ML/AI",         re.compile(r"\b(langchain|llm|openai|anthropic|rag|ollama)\b", re.I)),
]
FRAMEWORK_RULES_JAVA: list[tuple[str, re.Pattern]] = [
    ("Spring",   re.compile(r"\b(spring|springboot|boot)\b", re.I)),
    ("Android",  re.compile(r"\b(android|compose|jetpack)\b", re.I)),
    ("Kotlin",   re.compile(r"\b(kotlin|ktor|exposed)\b", re.I)),
    ("Build",    re.compile(r"\b(gradle|maven)\b", re.I)),
    ("Testing",  re.compile(r"\b(junit|mockito|testng|spock)\b", re.I)),
]
FRAMEWORK_RULES_RUST: list[tuple[str, re.Pattern]] = [
    ("Web/HTTP",         re.compile(r"\b(actix|axum|rocket|warp|poem|tide|hyper|salvo|leptos|yew|dioxus)\b", re.I)),
    ("Async/Runtime",    re.compile(r"\b(tokio|async[-_ ]?std|smol|mio)\b", re.I)),
    ("CLI/Tooling",      re.compile(r"\b(clap|structopt|cargo[-_]|cli|tui|ratatui)\b", re.I)),
    ("Blockchain",       re.compile(r"\b(solana|substrate|polkadot|near|cosmos|ethereum|foundry|revm|anchor|move)\b", re.I)),
    ("WebAssembly",      re.compile(r"\b(wasm|wasm[-_]?bindgen|wasmer|wasmtime|wasi|yew|leptos|dioxus|trunk)\b", re.I)),
    ("Game/Graphics",    re.compile(r"\b(bevy|amethyst|macroquad|ggez|fyrox|rend3|wgpu|vulkan|opengl)\b", re.I)),
    ("Embedded/Systems", re.compile(r"\b(embedded|rtic|embassy|nrf|stm32|no[-_]?std|esp(32|idf)?|rp2040|microcontroller)\b", re.I)),
    ("Data",             re.compile(r"\b(polars|datafusion|arrow|duckdb|parquet|delta)\b", re.I)),
    ("ML/AI",            re.compile(r"\b(candle|burn|huggingface|llm|llama|langchain|openai|anthropic|rag|ollama)\b", re.I)),
    ("DB/Storage",       re.compile(r"\b(diesel|sqlx|sea[-_]?orm|rusqlite|postgres|mysql|redis|mongo|surreal|tikv)\b", re.I)),
    ("Build/Macros",     re.compile(r"\b(proc[-_]?macro|derive|serde|build[-_]?script|cargo)\b", re.I)),
    ("Testing",          re.compile(r"\b(criterion|proptest|quickcheck|mockall|rstest|insta)\b", re.I)),
]

def framework_hints_for(stack: str, full_name: str) -> list[str]:
    stack_u = (stack or "").strip()
    if stack_u in ("JS/TS", "TypeScript/JavaScript"): rules = FRAMEWORK_RULES_JSTS
    elif stack_u == "Python":                         rules = FRAMEWORK_RULES_PY
    elif stack_u == "Go":                             rules = FRAMEWORK_RULES_GO
    elif stack_u == "Java":                           rules = FRAMEWORK_RULES_JAVA
    elif stack_u == "Rust":                           rules = FRAMEWORK_RULES_RUST
    else:                                             rules = []
    if not rules:
        return []
    hits: set[str] = set()
    for name, pat in rules:
        if pat.search(full_name):
            hits.add(name)
    return sorted(hits)


COLUMNS = [
    "full_name", "owner_login", "stack", "primary_language", "ecosystem",
    "framework_hints", "stars", "commits", "authored_commits", "commit_ratio",
    "country", "country_iso", "geo_confidence", "income_group",
    "adoption_label", "adoption_level",
    "agents_found", "current_agents", "configured_agents", "primary_agent",
    "agent_count", "current_agent_count", "configured_agent_count",
    "channels_count", "channels_fired",
    "evidence_count", "evidence_semantics",
    "has_file_evidence", "has_commit_trailer_evidence",
    "has_pr_metadata_evidence", "has_author_evidence", "has_branch_evidence",
    "has_agents_md",
    "review_participation_count", "orchestration_only_count",
    "legacy_markers_count", "recovery_checkpoint_count", "ambiguous_lineage_count",
    "historical_only_count",
    "authored_commits_by_agent",
    "first_signal_at", "created_at",
    "oldest_scanned_commit_at", "last_signal_at",
    "repo_created_at", "pushed_at",
    "first_signal_month", "first_signal_days_ago",
    "repo_age_days", "age_at_adoption_days",
    "days_since_push", "is_active_last_90d",
    "history_coverage", "history_complete",
    "is_archived", "license_spdx",
]

# ---------------------------------------------------------------------------
def iso_month(iso_ts: str | None) -> str:
    return iso_ts[:7] if iso_ts else ""

def _parse_dt(iso_ts: str | None):
    if not iso_ts: return None
    try:    return datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, TypeError): return None

def days_between(a_iso: str | None, b_iso_or_dt):
    a = _parse_dt(a_iso)
    b = b_iso_or_dt if isinstance(b_iso_or_dt, datetime) else _parse_dt(b_iso_or_dt)
    if not a or not b: return ""
    return int((b - a).total_seconds() // 86400)

def pipe_join(values) -> str:
    if not values: return ""
    return "|".join(sorted({str(v) for v in values if v}))

def parse_pipe(raw: str) -> list[str]:
    if not raw: return []
    return [x.strip() for x in raw.split("|") if x.strip()]

def owner_login_from(full_name: str) -> str:
    return (full_name.split("/", 1)[0] if "/" in full_name else full_name).strip().lower()

def _truthy(v: str) -> bool:
    return (v or "").strip().lower() in ("true", "1", "yes", "t")

def _to_int(v: str, default=0) -> int:
    try:    return int(float((v or "").strip()))
    except (ValueError, TypeError): return default

def _to_float(v: str, default=0.0) -> float:
    try:    return float((v or "").strip())
    except (ValueError, TypeError): return default


def aggregate_evidence(evidence_csv: Path):
    """Stream the evidence CSV; return per-repo aggregates.

    Mirrors the fields the original bundle-based builder computes:
      - family_counts  → used to pick `primary_agent`
      - channel_sets   → not strictly needed (repos.*_rows already carry this),
                         but we include it for forward-compat.
      - semantic_sets  → used to fill `evidence_semantics`
      - evidence_totals → fallback count; prefer `repos.evidence_rows`
      - has_agents_md  → any evidence row whose path ends with ``AGENTS.md``
      - authored_by_agent → commit-trailer rows per family per repo
                            (best-effort reconstruction of the JS/TS JSON)
    """
    family_counts:  dict[str, Counter] = defaultdict(Counter)
    channel_sets:   dict[str, set]     = defaultdict(set)
    semantic_sets:  dict[str, set]     = defaultdict(set)
    authored_by_agent: dict[str, Counter] = defaultdict(Counter)
    evidence_totals: Counter = Counter()
    has_agents_md:  set[str] = set()

    csv.field_size_limit(1 << 30)
    with evidence_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        n = 0
        for row in reader:
            full_name = (row.get("full_name") or "").strip()
            if not full_name:
                continue
            family = (row.get("family_name") or "").strip()
            channel = (row.get("channel") or "").strip()
            semantics = (row.get("evidence_semantics") or "").strip()
            path = (row.get("path") or "").strip()

            if family and family not in ("Rejected/noise", "Generic"):
                family_counts[full_name][family] += 1
            if channel:
                channel_sets[full_name].add(channel)
            if semantics:
                semantic_sets[full_name].add(semantics)
            if path and path.rsplit("/", 1)[-1] == "AGENTS.md":
                has_agents_md.add(full_name)
            # Best-effort per-agent authored commits proxy:
            # count commit_trailer rows attributed to this family.
            if family and family != "Generic" and channel == "commit_trailer":
                authored_by_agent[full_name][family] += 1
            evidence_totals[full_name] += 1
            n += 1
            if n % 500_000 == 0:
                print(f"  ... {n:,} evidence rows aggregated", file=sys.stderr)
    print(
        f"  aggregated {n:,} evidence rows across {len(evidence_totals):,} repos",
        file=sys.stderr,
    )
    return (family_counts, channel_sets, semantic_sets,
            evidence_totals, has_agents_md, authored_by_agent)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack", required=True, help="Stack label (e.g. Go, Java, Python)")
    parser.add_argument("--repos-csv", required=True, help="Path to the per-repo detect CSV")
    parser.add_argument("--evidence-csv", required=True, help="Path to the per-evidence detect CSV")
    parser.add_argument("--out-dir", default=None,
                        help="Default: <repo-root>/integrated_datasets")
    parser.add_argument("--out-name", default=None,
                        help="Override output filename (sans directory)")
    args = parser.parse_args()

    repos_csv = Path(args.repos_csv)
    evidence_csv = Path(args.evidence_csv)
    for p in (repos_csv, evidence_csv):
        if not p.exists():
            print(f"ERROR: {p} not found", file=sys.stderr)
            return 1

    stack = args.stack.strip()
    stack_slug = re.sub(r"[^a-z0-9]+", "-", stack.lower()).strip("-") or "stack"
    out_dir = Path(args.out_dir) if args.out_dir else (
        Path(__file__).resolve().parents[1] / "integrated_datasets"
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / (
        args.out_name or f"corpus_integrated_{stack_slug}_{stamp}.csv"
    )

    print(f"Building integrated CSV", file=sys.stderr)
    print(f"  stack:         {stack}", file=sys.stderr)
    print(f"  repos CSV:     {repos_csv}", file=sys.stderr)
    print(f"  evidence CSV:  {evidence_csv}", file=sys.stderr)
    print(f"  output:        {out_path}", file=sys.stderr)

    print("Aggregating evidence CSV ...", file=sys.stderr)
    (family_counts, channel_sets, semantic_sets,
     evidence_totals, has_agents_md, authored_by_agent) = aggregate_evidence(evidence_csv)

    n_total = 0
    n_agentic = 0
    n_country = 0

    csv.field_size_limit(1 << 30)
    with repos_csv.open("r", encoding="utf-8-sig", newline="") as fh_in, \
         out_path.open("w", encoding="utf-8", newline="") as fh_out:
        reader = csv.DictReader(fh_in)
        writer = csv.DictWriter(fh_out, fieldnames=COLUMNS)
        writer.writeheader()

        for row in reader:
            full_name = (row.get("full_name") or "").strip()
            if not full_name:
                continue

            adoption_level = (row.get("adoption_level") or "none").strip().lower() or "none"
            label = "agentic" if adoption_level in AGENTIC_LEVELS else "none"
            if label == "agentic":
                n_agentic += 1

            ever_observed      = parse_pipe(row.get("ever_observed"))
            currently_configured = parse_pipe(row.get("currently_configured"))
            current_activity   = parse_pipe(row.get("current_activity"))
            historical_activity = parse_pipe(row.get("historical_activity"))

            # Lifecycle counts (these are pipe-lists of agent families in the
            # detect CSV export, matching one tag per family).
            review_cnt   = len(parse_pipe(row.get("review_participation")))
            orches_cnt   = len(parse_pipe(row.get("orchestration_only")))
            legacy_cnt   = len(parse_pipe(row.get("legacy_markers")))
            recov_cnt    = len(parse_pipe(row.get("recovery_checkpoint")))
            amb_cnt      = len(parse_pipe(row.get("ambiguous_lineage")))
            # historical-only = in historical_activity but not in current_activity
            cur_set = set(current_activity)
            hist_only = sum(1 for a in historical_activity if a not in cur_set)

            # Country info: prefer the CSV fields (per-repo).
            iso = (row.get("country_iso") or "").strip().upper() or ""
            country = (row.get("country") or "").strip()
            if not country and iso:
                country = country_name(iso) or ""
            geo_conf = (row.get("geo_confidence") or "").strip()
            inc_grp = income_group(iso) if iso else ""
            if country:
                n_country += 1

            # Primary agent: most common family across evidence rows.
            fc = family_counts.get(full_name, Counter())
            primary = fc.most_common(1)[0][0] if fc else ""

            # Evidence shape — prefer repo-level counts from repos CSV.
            ch_rows = {
                "file":           _to_int(row.get("file_rows")),
                "author":         _to_int(row.get("author_rows")),
                "branch":         _to_int(row.get("branch_rows")),
                "bot":            _to_int(row.get("bot_rows")),
                "label":          _to_int(row.get("label_rows")),
                "commit_trailer": _to_int(row.get("commit_trailer_rows")),
                "pr_metadata":    _to_int(row.get("pr_metadata_rows")),
                "issue":          _to_int(row.get("issue_rows")),
            }
            channels_fired = [k for k, v in ch_rows.items() if v > 0]
            sem_set = semantic_sets.get(full_name, set())

            # Timing fields.
            first_signal = (row.get("first_signal_at") or "").strip()
            repo_created = (row.get("repo_created_at") or "").strip()
            pushed_at    = (row.get("pushed_at") or "").strip()
            archived     = _truthy(row.get("archived"))

            age_days             = days_between(repo_created, now) if repo_created else ""
            age_at_adoption_days = (days_between(repo_created, first_signal)
                                    if (repo_created and first_signal) else "")
            days_since_push      = days_between(pushed_at, now) if pushed_at else ""
            is_active_last_90d   = ("1" if isinstance(days_since_push, int)
                                         and days_since_push <= 90 else "0")

            # commits: CSV has `commit_count` (observed) and sometimes `total_commits`.
            # Prefer commit_count (always populated); fall back to total_commits.
            commits = _to_int(row.get("commit_count") or row.get("total_commits"))
            authored_commits = _to_int(row.get("authored_commits"))
            commit_ratio = _to_float(row.get("commit_ratio"))

            # Best-effort per-agent authored-commit JSON (same shape as JS/TS).
            aba = authored_by_agent.get(full_name)
            aba_json = json.dumps(dict(aba), separators=(",", ":")) if aba else ""

            writer.writerow({
                "full_name": full_name,
                "owner_login": owner_login_from(full_name),
                "stack": stack,
                "primary_language": (row.get("language") or "").strip(),
                "ecosystem": STACK_TO_ECOSYSTEM.get(stack, ""),
                "framework_hints": pipe_join(framework_hints_for(stack, full_name)),
                "stars": _to_int(row.get("stargazers")),
                "commits": commits,
                "authored_commits": authored_commits,
                "commit_ratio": commit_ratio,
                "country": country,
                "country_iso": iso,
                "geo_confidence": geo_conf,
                "income_group": inc_grp,
                "adoption_label": label,
                "adoption_level": adoption_level,
                "agents_found": pipe_join(ever_observed),
                "current_agents": pipe_join(current_activity),
                "configured_agents": pipe_join(currently_configured),
                "primary_agent": primary,
                "agent_count": len(ever_observed),
                "current_agent_count": len(current_activity),
                "configured_agent_count": len(currently_configured),
                "channels_count": len(channels_fired),
                "channels_fired": pipe_join(channels_fired),
                "evidence_count": _to_int(row.get("evidence_rows")) or evidence_totals.get(full_name, 0),
                "evidence_semantics": pipe_join(sem_set),
                "has_file_evidence":           "true" if ch_rows["file"] > 0 else "false",
                "has_commit_trailer_evidence": "true" if ch_rows["commit_trailer"] > 0 else "false",
                "has_pr_metadata_evidence":    "true" if ch_rows["pr_metadata"] > 0 else "false",
                "has_author_evidence":         "true" if ch_rows["author"] > 0 else "false",
                "has_branch_evidence":         "true" if ch_rows["branch"] > 0 else "false",
                "has_agents_md":               "true" if full_name in has_agents_md else "false",
                "review_participation_count": review_cnt,
                "orchestration_only_count":   orches_cnt,
                "legacy_markers_count":       legacy_cnt,
                "recovery_checkpoint_count":  recov_cnt,
                "ambiguous_lineage_count":    amb_cnt,
                "historical_only_count":      hist_only,
                "authored_commits_by_agent":  aba_json,
                "first_signal_at":            first_signal,
                "created_at":                 first_signal,
                "oldest_scanned_commit_at":   "",   # not present in CSV export
                "last_signal_at":             "",
                "repo_created_at":            repo_created,
                "pushed_at":                  pushed_at,
                "first_signal_month":         iso_month(first_signal),
                "first_signal_days_ago":      days_between(first_signal, now) if first_signal else "",
                "repo_age_days":              age_days,
                "age_at_adoption_days":       age_at_adoption_days,
                "days_since_push":            days_since_push,
                "is_active_last_90d":         is_active_last_90d,
                "history_coverage":           _to_float(row.get("history_coverage")),
                "history_complete":           "true" if _truthy(row.get("history_complete")) else "false",
                "is_archived":                "true" if archived else "false",
                "license_spdx":               (row.get("license_spdx") or "").strip(),
            })
            n_total += 1
            if n_total % 5_000 == 0:
                print(f"  wrote {n_total:,} repos", file=sys.stderr)

    print(f"Done. {n_total:,} repos  |  {n_agentic:,} agentic "
          f"({n_agentic / n_total * 100:.1f}%)  |  {n_country:,} with country",
          file=sys.stderr)
    print(f"Output: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
