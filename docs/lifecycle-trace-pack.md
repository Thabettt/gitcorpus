# Lifecycle-aware coding-agent traces

`packs/2026-11-14.json` is the first schema-v2 trace pack. Its only editable source is
`packs/sources/2026-11-14/catalogue.json`; `python -m detect.packs build` validates and
serializes that complete snapshot deterministically. Frozen `2026-10-14` and `2026-10-19`
documents remain schema-v1 artifacts and load and run with their original behavior.

This page is the schema-v2 rule contract. For how packs relate to each other, which agents
and channels each pack offers, sources, and the known coverage gaps of this pack, read
[`trace-packs.md`](trace-packs.md) first.

## Evidence contract

Every schema-v2 evidence row can retain the canonical family ID and display name, `observed_as`
predecessor or surface, variant, stable rule ID, lifecycle, semantic meaning, channel, forge,
participant role, confidence, provenance reference, current/historical flags, metric eligibility,
and an explanatory note. Old rows keep these nullable; no migration reinterprets them.

Repository summaries keep separate projections for ever observed, currently configured, current
activity, historical activity, authored commits, review participation, orchestration-only traces,
legacy residue, recovery/checkpoint activity, ambiguous lineage, and rejected/noise diagnostics.
Only rules explicitly eligible for current presence enter current family metrics, and only exact
authorship rules eligible for the current commit ratio enter its numerator.

## Bounded collection

- JSON, YAML, TOML, text, workflow `uses`, and container-image predicates run only after a rule's
  declared path predicate matches.
- Content is capped at 128 KiB by default and at 64 candidate paths per repository. Fetch, parse,
  and predicate failures are recorded separately.
- PR/MR and issue bodies are bounded and requested only when selected rules require them.
- Hidden refs use declared namespaces only. Synthetic identities are evaluated only with their
  owning ref; ordinary `herder@localhost` is never authorship.
- GitLab collection preserves MR author, reviewer, commenter, assignee, and service-account roles
  without GitHub bot normalization. Forge IDs already include extension points for Bitbucket and
  Azure DevOps.

Every collector difference above applies only to schema-v2 packs. A v1 run keeps its original
GraphQL queries (no PR reviews, no comment bodies), file probing, and `AGENTS.md` content
attribution.

The hidden-ref channel is opt-in in the console because namespace and tip enrichment can cost up
to six additional API requests per repository. Trailer and structured-file contracts still make
the six formerly gated families operational without enabling recovery scans by default.

## Analysis and exports

A fresh API detection snapshots repository language from the stored repository record and records
GraphQL default-branch `totalCount` with the inspected history window. The repository document and
CSV therefore expose `commit_count`, `total_commits`, `history_window_commits`,
`history_eligible_commits`, `history_coverage`, and `history_complete`. These feed:

- **Observation and eligibility coverage** — History coverage observed and Full default-branch
  history;
- **Commits vs agent use** — lifetime commit-depth strata plus recent eligible-commit ratios;
- **Language vs agent use** — frozen primary-language strata.

Evidence CSV/JSON exports preserve the rich rule contract. Repository CSV/JSON exports preserve
the analysis inputs and lifecycle rollups. `/api/trace-packs`, `/api/trace-packs/{version}`, and
`/api/detections/{run_id}/evidence` expose the same contracts through OpenAPI.

## Migration safety

Migration `0025_lifecycle_trace_pack.py` adds nullable evidence metadata and a versioned pack
document without changing old rows. Its downgrade succeeds on databases containing only schema-v1
data and refuses to discard schema-v2 packs or lifecycle evidence; remove or export that data
explicitly before downgrading.
