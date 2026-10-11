# Methodology: How gitcorpus Was Built, Measured, and Optimized — a Run-by-Run Journal

**Date**: 2026-10-11 (first complete edition). **Status**: living document — expected to grow.
**Companions**: `how-the-data-flows.md` (what the pipeline does), `corpus-building-efficient-engineering.md` (the meters and the math), `run-limits.md` (the operating dials), `runtime-audit-and-adaptive-control.md` (the audit + its §11 production log), `loc-dilemma.md`, `adoption-window.md`, and the frozen journal in `../docs/development-log.md`.

**Purpose of this document.** Every optimization in this repository has a story: a measurement that provoked an idea, an implementation, a live run that tested it, and a verdict — right, wrong, or "right in direction, wrong in magnitude". Until now those stories were scattered across commit messages, plan files, findings notes, run bundles, the database, and two journals that stop at different dates. This document consolidates the whole record into one progressive narrative: **what was tried, where the idea came from, what invoked it, how it was implemented, how it was tested, whether the hypothesis held, and what the next improvement point was.** It is written to be verifiable: every number here can be traced to a commit, a run row, an audit row, a bundle file, or a named document — and where the data does not exist, that gap is stated instead of filled.

---

## 0. How to read this document

### 0.1 The evidence hierarchy

Claims in this document are ranked by the strength of their source. When two sources disagree, the higher rank wins, and the disagreement is recorded in Appendix B:

1. **Primary machine data** — the PostgreSQL database (`runs`, `shards`, `audit_log`, `run_items`, `app_settings`, `corpora`), the run bundles under `runs/<filter_hash>/<run_id>/`, and the Windows audit trail (`%LOCALAPPDATA%\gitcorpus\`). This is what actually happened.
2. **Git history** — 284 commits reachable from `main` (branch `quality-hardening` is an ancestor, not a divergent line; there is a single linear history). Commit messages and diffs are the record of intent and implementation.
3. **Dated in-repo notes** — `docs/development-log.md` (frozen 2026-10-09, see §0.4), `docs/findings/*`, `design/*` status banners, `docs/superpowers/{specs,plans,prompts}/*`.
4. **Reconstructed narrative** — anything only described in prose, labeled as such.

### 0.2 Conventions

- **Times are UTC.** Git timestamps in this repository are authored at `+03:00` (Africa/Cairo, the operator's zone); subtract three hours. Some source documents wrote local times; where the distinction matters the local time is given in parentheses.
- **"Run N"** means the row with `id = N` in the `runs` table — nothing else. Runs referred to inside older documents as "run 24", "run 30" etc. use the same numbering.
- **"Scratch run"** means a live measurement executed directly through `serve.runner.run_filter` or a scratch script, *not* through the console. Scratch runs have no `runs` row (their audit rows carry `run_id = NULL`); the hydration profile (2026-10-08) and the adaptive soak (2026-10-10) are the two important ones.
- **Hypotheses** are numbered `H-n` in the ledgers (Part IV); they are this document's tags, not project rulings.
- **Numbers are verbatim from sources.** Where a number was measured on a scratch run or under a unique condition, that condition is stated with it. Percentages and derived quantities say they are derived.
- **Status labels** used by the console: a `cancelled` run is shown as "Stopped"; `partial` as "Finished — incomplete".

### 0.3 What "all the states" means for this repository

The full working state as of 2026-10-11 04:20 UTC (commit `6d15587`):

| State | Where it lives | What it contains |
|---|---|---|
| Source + docs | working tree, `main` | the whole codebase; docs referenced throughout |
| Full history | git | 284 commits, oldest `717c9b3` (2026-09-29) → `6d15587`; reflog shows ordinary development (no rebases/amends beyond pre-review folds); no stashes; one worktree |
| Run artifacts | `runs/` (git-ignored) | bundles for runs 1, 2, 9, 10, 12, 16–19, 22, 23, 28–30 |
| Operational DB | PostgreSQL `gitcorpus` @ localhost:5433 | 30 runs, 216,217 run items, 6,978 shard rows, 66,729 audit rows, 48,530 repos, 3 corpora, 1 saved filter |
| Ops logs | `%LOCALAPPDATA%\gitcorpus\` | `pg.log` (723 KB), access logs; `serve.log` empty as of the last restart |
| Scratch evidence | `%LOCALAPPDATA%\Temp\opencode\` | the adaptive soak script + payload (`soak\soak_run.py`, `soak_A_payload.json`, `soak_A_summary.json`), corpus-diff scripts from 2026-10-07 |
| Review artifacts | `.superpowers/sdd/2026-10-09-adaptive-rate-controller/` | review diffs for `a723844`, `cb8a674..6dbb759`, `cb8a674..a723844` |

No other branches, no remote work in progress (the repo was never pushed; CI exists but "No CI run has ever executed", per the 2026-10-02 execution report — a *local-only* project, which is itself a fact that shapes this history).

### 0.4 Relationship to the frozen development log

`docs/development-log.md` was the durable session journal from provisioning (2026-10-01) through the quota/limiter work (2026-10-09). It is **frozen as of its last entry**; its front matter now points here. This document *supersedes it as the journal to update* but does not replace its value: the development log keeps the exhaustive R1–R58 rulings table, per-task commit lists, and live-run notes exactly as written at the time. Where this document and the log agree, the log is the deeper reference for rulings; where this document corrects or extends it, the correction is explicit (Appendix B).

### 0.5 How this document gets updated

- **New work appends, never rewrites.** Each optimization campaign gets a new dated section inside the current part, or a new part if it is a new era. Existing sections may gain a dated "Update" line, never a silent edit.
- **The ledgers (Part IV) are living tables.** Every new live run gets a register row; every new optimization gets a hypothesis row; every failure gets a failure row.
- **Corrections go to Appendix B** with the date, the claim corrected, and the evidence.
- **Appendix A keeps the reproduction recipes** current, so any reader can regenerate every number here from the DB, the bundles, and git.

---

# Part I — Foundations (2026-09-29 → 2026-10-02): "correctness before speed"

No database run existed yet. This era's whole output was a pipeline, a console, and a set of gates — and its central hypothesis, stated up front, was that **speed work would be wasted without measurement, reproducibility, and safety rails first** (H-1). Everything in Part II sits on top of this era; that is why it is in this document at all.

## I.1 The frozen objective (2026-09-29)

The founding artifacts landed in one commit, `717c9b3` — "import gitcorpus research + frozen v2 design (live-only freshness, thesis tracks parked)":

- `design/spec.md` — Feature Specification, **Frozen v3** ("2026-10-01 amendment: US4 operator console added"). Four user stories: **US1** discover every matching public repo (sharded search + `since` backfill), **US2** reflect current state at fetch moment (renames/tombstones), **US3** enrich + serve with virtual filters including owner country, **US4** the operator console. Functional requirements FR-001–FR-023; success criteria SC-001–SC-008.
- `design/plan.md` — "historical plan of record": the SEART pattern (crawl → store → serve) hardened with the gap fixes from `findings/05` and an efficiency review; live-only freshness (**D4** in `research.md`), immutable `id BIGINT` keys, Redis per-bucket limiter, cost-aware enrichment (D12), audit logging (FR-010) from day one.
- `findings/00–06` — the research the design is grounded in (parameter matrices, existing-solution analysis, research gaps A-numbered, including A10: no token sharing to evade limits — a legal gate, not an optimization).

Two decisions from this day echo through every part of this document:

1. **Live-only (D4).** A run measures GitHub at `ran_at`; no background pollers, no watermarks, no GH Archive tails. Every later speed problem is a problem of spending one account's metered hours well, never of caching around the API. (The one recurring counter-idea — a local cached corpus for instant repeats — was explicitly parked three times: `further-optimization.md` §6, the run-modes idea, and the hydration-profile's "freshness window" proposal. It stays parked.)
2. **The meters, not the code, are the constraint.** From the first day the design budgeted against GitHub's published limits — search 30 req/min, core 5,000/hr, GraphQL 5,000 points/hr — and treated every API call as a purchase. When a later measurement (`corpus-building-efficient-engineering.md` §9.4) showed a 25×-cheaper discovery path, the design accepted it because the arithmetic was explicit, not because the code was clever.

## I.2 The walking skeleton and the build (`717c9b3` → `918339e`, 115 commits)

The build ran in the tight task-per-commit rhythm visible in the git log. Milestones that matter to the optimization story:

- **T000 walking skeleton** (`8947d1a`): hardcoded filter `language:rust stars:>100` through validate → live search → display → bundle JSON + CSV, in `src/skeleton.py` (later retired under R58 — for a while it survived as the pinned fixture `filter_hash == "2bc6b774968a"`, which is why the oldest directory under `runs/` is named `2bc6b774968a`).
- **US1 discovery, with live evidence** (`0d777d7`…`9f0488d`): the shard planner, Redis Streams queue, `since` cursor scan, org/user enumeration, batched upserts (COPY bootstrap, ruling **R23**: TEXT COPY + `ON_ERROR ignore` because PG18 forbids binary `ON_ERROR`). The acceptance test was live: **golden-org parity `A=566 B=566`**, empty symmetric difference between the sharded search path and a bounded `since` sample. The live delta probe — `language:python` **34,207,993** → `+stars:>1000` **11,756** with `delta_narrows=True` — proved that filtering actually narrows results, an explicit guard against GitHub's silent-typo `200` behavior (a typo'd qualifier becomes a *text search*, so a broken filter produces wrong data with no error; the delta test catches exactly that).
- **Final whole-branch review** (`f64bd69`): one fix wave, "350 tests passing"; the review process itself — spec-compliance + code-quality gates per batch — is a theme of this whole history.

## I.3 The console overnight run (`a98eabd` → `918339e`)

One overnight session (2026-10-01 evening → 02) executed US2 (within-run lifecycle: 301 rename follow, 404 tombstones), US3 (enrichment + serve + clone control) and US4 (console: persistence, executor, library, diff, UI, keyboard, dark mode) as batches B1–B9 plus a final review and fix wave. Result recorded at the time: **1020 tests passing first-hand (live golden-org + delta included)**, ruff/black clean, head `918339e`.

Fourteen rulings R1–R31 and then R32–R57 accumulated in this session (the full tables live in `development-log.md`). Three of them set up later optimization work directly:

- **R46** — hand-rolled CSS and vendored htmx: "no Node, no CDN, no build step at runtime". The frontend-efficiency work later (S10/S14) optimizes within that decision.
- **R52** — `field_stats` on payload + bundle (no DB column). This is the field that eventually carries per-stage timings and per-phase point ledgers — the self-reporting that made Part III reconstructable.
- **R58** — see §I.5.

## I.4 The efficiency audit and its 26 commits (`bf60ced` → `c6cb2df`)

Before optimization was attempted, it was **audited**: `docs/superpowers/plans/2026-10-01-efficiency-audit-report.md` (read-only, line-by-line, 51 numbered findings S1–S16 with a savings model). Then 26 `perf:` commits shipped the highest-value items in one afternoon/evening. The numbers that matter to the historical footprint, all from the audit and its post-implementation status:

| Finding | The problem, in one line | Measured/derived cost |
|---|---|---|
| S1 | O(k²) id accumulation (tuple concatenation) | 128k items → 65 GB copied, ~5–15 s; 1M → 4 TB, ~7 min |
| S2 | One giant SQL `IN` clause | PostgreSQL bind limit — **hard failure above 65,535** parameters |
| S3 | Planner probing day-by-day from 2008 | `language:python` ~8,550 leaves → ~17,100 probes → **~9.5 hours** of search budget; the fix stops at `max_shards` → ~30–50 probes → **~1–2 min** |
| S4 | Unbounded payload cache | 1,000 filter hashes ≈ 1–2 GB retained forever; capped at 100 entries → ~200 MB |
| S5 | Bulk runs blocking interactive cache misses | 10 queued 5-minute runs ⇒ an interactive search waits ~50 min |
| S7 | Per-repo transaction churn | 100k-repo tail: ~300k fewer transactions ⇒ **5–15 min saved per pass** |
| S10 | Clone failure storms re-persisting progress | ~300 MB of disk writes in a storm; capped+throttled ⇒ <1 MB |
| S14 | Polling tabs | **14,400 requests + 28,800 queries per 8-hour abandoned tab**; five tabs ≈ 70k–140k pointless HTTP requests |

The fix commits are the `perf:` block from `9076037` (linear repo_id accumulation) through `c6cb2df` (migration locking docs), including the ones whose shapes survive today: bounded single-flight payload cache (`42c432d`), visibility-gated polling (`f3e7206`), streamed exports (`3c6283e`), batched audit inserts parsing bodies once (`2628e2f`), single-write hydration with ETag (`f6e885c`), and migration `0007` aligning the `run_items` index with the `NULLS LAST` sort (`d903ae1`). Fourteen items were "realized (wired and tested)"; a handful stayed "latent" (GraphQL batching built but unwired — that becomes Part II's biggest lever).

**Verdict on H-1 (first half):** the audit-then-fix order held. Every later speed change in this document quotes a measured cost of the thing it replaces; none was speculative.

## I.5 Quality hardening: the freeze contract and R58 (`8e37d11` → `94a81e2`, 43 commits)

The second gate was correctness *of the development process itself*. `docs/superpowers/specs/2026-10-01-quality-hardening-design.md` declared a **Freeze Contract** — "normal use identical" — with five invariants (INV-1 identical behavior; INV-2 additive-only UI; INV-3 five allowed changes; INV-4 no runtime surface for tooling work; INV-5 exception register E1–E3). Five phases shipped:

- **Phase 0** — CI workflow (Linux with service containers; Windows with native PostgreSQL 17 + Memurai 4.1.8), golden harness (23 GET-route cases), OpenAPI hash pin, coverage floor `fail_under = 93`, measured baseline **93.23% (4965 statements, 336 missed)**. Note: *CI was never observed running* — pushing was deliberately forbidden throughout; the workflow was parse-validated only. This remains true today and is listed as an open thread.
- **Phase 1a** — zero-behavior fixes: clone registry atomicity (`d79eb49`), single-flight lazy loaders (`def016b`), dirty-row isolation, poison-shard recovery, batched `GeoCache` (`968cbf1`), and the **E1** run-counter surfacing (`d894460`); E1 was the one approved visible change (run summaries gained real `updated`/`unchanged`/`skipped`).
- **Phase 1b** — test/tooling hardening: centralized `clean_db` fixtures (22 files), CWD independence, deterministic synchronization replacing wall-clock flakes, JS helper extraction + Node tests, `mypy` ratchet (scoped to `lib`, `limiter`, `store`, `scheduler`), import-boundary tests, and the **quarantine manifest** (13 entries).
- **Phase 2** — adversarial hardening: Origin-aware CSRF, Host allowlist, body caps (1 MiB / 10 MiB), deadline policy (request 3,600 s and clone 1,800 s — sized as "≥ 4× the worst legitimate run", computed as a ≤ 421-call floor ≈ 458 s), clone timeout + `DELETE /runs/{id}/clone`, `GITCORPUS_REDIS_STRICT`, health single-flight.
- **Phase 3** — UX polish (9 additive-only tasks).

The interesting methodological moment of this era is the **inversion of the quarantine policy**:

> **R58** (verbatim): "Supersedes the R24/R57 quarantine policy: unwired surface is triaged, not preserved. Wiring: `reclaim_stale` (crash reclaim), `pel_size` (SLO metric). Deletions: `RetryQueue`, `order_shards`, `plan_id_ranges`, `mirrors`, `graphql_batch`, `fetch_metafiles`, `skeleton.py`. Parked minors closed: metafiles auth (fixed), executor future eviction (fixed). Rationale: dead code is a trap; deleted work is recoverable from git."

The deleted `graphql_batch` is the punchline of this document: within 48 hours the *concept* would be rebuilt as `src/lib/graphql_batch.py` — this time with tests and a demand (the engineering-audit reasoning in `corpus-building-efficient-engineering.md` §10.3 lists the old module's five defects as the requirements for the new one). R58's rule — delete, don't quarantine; git is the archive — is itself a methodology that has held since.

Hardening outcome, measured: **1214 tests, 0 failures/errors/skips, 94.74% coverage**, `mypy` clean on 14 files, 23/23 Node tests. One incident is part of the record: *"a non-session pytest process briefly ran against the shared `gitcorpus_test` DB at 12:03–12:06 during Phase 1 Task 2 and exited… the affected runs were repeated clean."* No cause was ever identified; the lesson recorded was procedural (precondition checks).

### The queued overnight, first batch (2026-10-02, 24 commits)

Between the hardening program and the batch engine came a four-phase queue executed from an operator prompt (`docs/superpowers/prompts/2026-10-02-overnight-queue-prompt.md`; report `2026-10-03-overnight-report.md`; range `9f32d58` → `e21143e`). Its process design is worth recording: the prompt named preconditions (clean tree, no competing process, DB/Redis up), **stop conditions** (including "a required schema change conflicts with an existing migration number"), and a rule that the prompt itself must never be committed. No stop condition fired; no `queue-stop.md` was written.

| Phase | What shipped | Gate |
|---|---|---|
| 1 — unwired-debt triage (R58) | `reclaim_stale` wired before the claim loop; deletions (`RetryQueue`, `order_shards`, `plan_id_ranges`, `mirrors`, `graphql_batch`, `fetch_metafiles`, `skeleton.py`); sanitized run errors; manifest updated | **1140 passed, 96.12%** |
| 2 — QA reconciliation | read-only `run_quality` module + JSON/htmx routes + run-detail panel | **1150 passed, 96.11%** |
| 3 — run resume | `recover_orphaned_runs` at startup (idempotent); `POST /runs/{id}/resume` for failed find runs; crash runbook in `environment.md` | **1157 passed, 95.79%** |
| 4 — SLO dashboard | `metrics_payload` (SLOs + limiter + queue PEL + run counts), `/metrics` page, `/api/metrics` JSON, htmx partial | **1166 → 1168 passed, 95.72%** final |

Whole-branch review verdict at close: "Ready to merge = Yes; 0 Critical, 0 Important, 13 Minor with triage." The coverage decline across the phases (96.12 → 95.72) is the arrival of new code plus a deliberately unreachable detect branch — the ratchet policy recorded a *decrease* as acceptable when caused by unreachable code, and flagged the floor could rise to 94 anyway.

## I.6 Foundation-era verdicts

- **H-1 (correctness and reproducibility gates precede speed): confirmed.** The gates caught real defects (poison shards, silent partials, fixture races) and, more importantly, made every later speed claim checkable — `field_stats`, audit rows, golden pages, and the coverage floor were all in place before the first optimization was attempted.
- **H-2 (audit before optimizing): confirmed.** The efficiency audit's S-numbers were converted into fixes at a 1:1 commit ratio; nothing was optimized without a measured statement of the cost.
- **H-3 (delete dead code, don't quarantine):** recorded as R58. Verdict deferred to Part II where the deleted work's concept immediately returned by demand (the batch engine) — which validates "recoverable from git" as a policy.

---

# Part II — The speed era (2026-10-02 → 2026-10-09): "find it, then fetch it faster"

The console existed; the first run row appeared on 2026-10-03. This part is the story of turning a working pipeline into a fast one: the GraphQL batch engine, the discovery-engine revolution (20 minutes of searching → 68 seconds), the hydration profile that moved the bottleneck, and the concurrency ladder that walked the hydration dial from 10 to 20 and settled at 17. It ends the night before the audit that would push into GitHub's walls.

## II.1 The GraphQL batch engine, settings, and the console redesign (overnight, 2026-10-02 → 03)

Three plans executed back-to-back in one overnight run (`docs/superpowers/prompts/2026-10-04-execution-report.md`; 30 commits; all on `main`):

**Phase 1 — the batch engine** (`0e28c40`…`eaf2a3d`). The old `graphql_batch` module had been deleted under R58; this rebuild was written to a different standard, and the difference is the design: *one bad repo must never cut off the thousands behind it*. Mechanically: GraphQL errors arrive inside `200` responses with a `path` naming the failing alias; the engine parses the data **first**, keeps the good results, attributes every error to the exact repo (alias `n{i}`), splits only the failed half (bounded attempts, down to singles), and falls back to per-repo REST only when a single still fails. Every repo ends `saved` / `fallback-saved` / `unresolved (reason)`; unresolved repos mark the run `partial` — the project's "no silent partials" rule applied to batches. Dedicated `graphql` limiter bucket (5,000 points/hour). Both named isolation tests passed. Gate: **1237 tests, 95.56%**.

**Phase 2 — settings page** (`1cc4d35`…`74a33b3`, `c373ce3`). Single-row `app_settings` table (migration `0008`), precedence **environment → database row → built-in default**, defaults deliberately equal to the existing hard-coded values (10 shards / 500 candidates / 200 hydrate / 100 enrich / 3,600 s / batching on / batch 20 / concurrency 10) "so nothing changes until an operator edits", and every save writes an `audit_log` row with before/after values (`token_fp="settings"`). That audit row is why this document can reconstruct the exact operating-point history of every nightly run. Gate: **1268 passed, 95.40%**.

**Phase 3 — console UX redesign** (`ac7f225`…`c9a87dd`). Naming model **Search → Corpus → Detection**; Detections rendered greyed ("Coming soon"); migration `0009` corpora; run-scoped export; every new GET route into the golden harness. Gate: **1355 passed, 95.22% → 95.23%** after a five-finding fix wave.

## II.2 The first live console runs (runs 1–4, 2026-10-03)

Four interactive runs, made to exercise the console, not to build corpora — every one hit the interactive caps and ended `partial` (one incomplete shard each). They are historically important anyway: run 1's bundle is the proof that exposed the era's biggest silent bug (§II.3).

| Run | Filter | Found (`total_count`) | Fetched | Kept | Elapsed | Notes |
|---|---|---|---|---|---|---|
| 1 | `language:rust` | **1,377,440** | 3,000 | 500 | 315 s | bundle shows hydration `requests 10 / values 0 / handled 200` — every batch fell back to REST |
| 2 | `user:Thabettt fork:true` + `min_commits:100` | 16 | 16 | 8 | 16 s | same fallback signature (`1 / 0 / 16`) |
| 3 | `stars:5..* language:php fork:true` | 152,833 | 3,000 | 500 | 296 s | |
| 4 | `language:java` + `min_stars:9, min_commits:50` | 163,501 | 2,893 | 196 | 303 s | first run where a virtual filter actually dropped repos (196 of 2,893) |

Two of these were frozen as corpora the same morning (`Rust — 2026-10-03` from run 1, `user Thabettt…` from run 2). The settings audit for that day also shows the "maximum" preset being switched on at 12:21 UTC and off again at 12:35 — the contradictory preset that `run-limits.md` later replaced with the corpus preset.

## II.3 The first corpus attempt: preset, overnight failures, and two silent bugs (runs 5–9, 2026-10-06 → 07)

**The corpus profile** was applied on 2026-10-06 at 00:59 UTC (settings audit: 1,000 shards / 100,000 at each stage / 86,400 s deadline; concurrency 10, batch 20). The same session produced the saved filter "Rust Corpus" (22:29 UTC) — the run-#9 filter: `created:>=2025-02-24 language:rust`, virtual `min_stars: 4, min_commits: 50, min_language_bytes: 175000`.

**Three failed overnight attempts (runs 5–7).** All three ended `failed: orphaned: process restarted`:

| Run | Created | Ran | Elapsed recorded | Why it matters |
|---|---|---|---|---|
| 5 | 02:44 | 12:54 → 12:59 | 257 s | queued for 10 h behind a stuck predecessor |
| 6 | 02:50 | 08:36 → 08:44 | 467 s | |
| 7 | 13:01 | 13:01 → 21:16 | **29,667 s (8h14m)** | the run that burned an evening walking single days from 2008 |

What was wrong, verified the next morning:

1. **The planner appended a second `created:` qualifier instead of replacing the first.** GitHub treats duplicate same-type qualifiers as a **union** — live-verified that session — so every shard effectively asked the same question, bisection never converged, and the plan walked day-by-day from 2008. Fixed in `d04bc34` (`split_created` / `replace_created`; plan inside the user's window; transient shard failures deferred with a circuit breaker after 3; deadline keeps shards resumable).
2. **The hydration GraphQL query was invalid since day one.** It asked for `owner { databaseId }`, but `databaseId` does not exist on the `RepositoryOwner` interface; GitHub answered HTTP 200 with a per-alias `undefinedField` error for every repo, so **every batch silently fell back to two REST calls per repo** — the new engine's per-repo error attribution working perfectly on a question that was simply malformed. Run 1's own bundle proves it (`requests 10, values 0, handled 200`). Fixed in `bf2201d`: `... on User { databaseId }` / `... on Organization { databaseId }` inline fragments; language bytes pulled from the same hydration query; bounded-concurrency parallel batches; 303/307/308 redirect follows.

The same fix wave (`f55dc26`, `dc9cc67`, `c99ee13`) added Stop/resume with live progress (migrations `0010`/`0011`), honest partial warnings (tombstones, skipped results, unique under-coverage), the corpus preset, and streamed bundle JSON. Test suite at this point: **1,435 tests collected**.

**Run 9 — the first real corpus.** Created 22:31 UTC, executed 01:07 → 02:25 UTC (elapsed 4,677 s / 78m, including re-planning and page fetching at the 30/min REST search cap — discovery was still the REST path):

- 38,833 repos found and hydrated in **1,942 GraphQL requests, 0 REST fallbacks, 0 unresolved** (~2,800 repos/min at concurrency 10; sequential REST was ~300–400/min).
- Funnel from the bundle: 38,833 → **21,503** (min_commits) → **17,795** (min_language_bytes) exported; 0 skipped; 0 incomplete shards; status `done`.
- Frozen the same night as corpus "Rust Corpus 7th October 2026" (17,795 repos).
- Two drift checks on the same day: `total_count` for the same query drifted 38,820 → 38,823 → 38,833 across ~5 h; and the cross-corpus comparison scripts (still in `%LOCALAPPDATA%\Temp\opencode\`, 2026-10-07 05:37–05:42) diffed run 9's 17,795-row export against `repos_rust.csv` (17,757 rows), checking every missing repo's current stars and deletion state in the DB.

**Lesson of this section (H-9):** both silent bugs were invisible in status codes and metrics; they were caught by *inspecting a bundle against expectations* and by a writer asking "what should these numbers have been?" The rule that follows — trust the live path only after reading its evidence — is applied to every later change.

## II.4 The GraphQL discovery engine: 20 minutes → 68 seconds (`76899fb`…`c1b7350`, 2026-10-08)

### II.4.1 The spike (measured 2026-10-08, ~01:00 UTC)

**The question:** discovery (count probes + result pages) was the last big consumer of the REST search meter (30 req/min), which set a ~20-minute floor on finding a 39k corpus. Can *finding* repos ride the GraphQL points meter the same way hydration does?

**The measurement** (`design/corpus-building-efficient-engineering.md` §9.4; spec `docs/superpowers/specs/2026-10-08-graphql-discovery-design.md` §1): yes, and the numbers are large.

| Step | Result |
|---|---|
| Count probes, batched | 16 aliased `repositoryCount` probes in **one** GraphQL query — ~1 s, **1 point total** |
| Plan (bisect until fetchable) | 111 probes in 9 batched queries → 56 shards in **8.9 s** |
| Fetch (one search connection per page, 32 in flight) | 418 pages → **38,969 unique repos in 59.0 s** |
| **Total shard-and-fetch** | **67.9 s**, 0 retries, 0 failures, ~430–500 points (~10% of the hourly budget), REST search untouched |
| Same job through REST search | ~13 min of pages at 30/min + ~7 min of probes ≈ **20 min** |

**What did not work:** multiple search connections per query — two connections at 100 repos each took ~6 s, three took ~8 s, four hit GitHub's 10-second query timeout (`502`). The recipe that emerged: *probes batch; pages do not*. The same night, the original 35-field page query was measured to time out at 10.6–10.9 s at `first:100` and to storm timeouts under 32-way concurrency (133/192 shards incomplete); a lean **14-field** page query measured 3.9–6.0 s serial and 4.1–4.7 s under load with 0 failures. Adaptive page halving (100 → 50 → 25) became the safety net.

### II.4.2 The build and its first live failure

Twelve commits shipped the engine the same day (planner `021218e`, client `99e20f6`, pipeline `b3cbb70`, graceful deadlines `c9700e0`, Redis queue deleted `c1b7350`, audit/SLO `dd696de`/`61121c2`). The live validation then caught a genuine defect *in our own wiring*, not GitHub:

- **Prescribed run (default `build_deps`, 10 limiter slots):** "finished" in 58.0 s by **failing** — 176 of 192 shards marked `incomplete` with no page ever fetched; 5,276 ids (13.5% of expectation). Diagnosis (from `docs/findings/2026-10-08-hydration-profile.md`): the discovery pool runs 32 workers but the `graphql` bucket had 10 slots; `request_with_retry` raises `ThrottledError` after ~2.5 s of denials instead of waiting for a slot — a perfect slot storm starved the pool. 58 s was "the sound of shards dying fast, not of fetching."
- **Fix** (`0eb1c33`): `BucketLimiter.bound_concurrency(value)` raises the slot ceiling to `max(current, value)` for its body and restores it after; the discovery phase binds to `discovery_concurrency`. Hydration keeps its own worker count, so the binding is a phase-scoped cap, not a global raise.
- **Confirming runs:** conforming scratch run **97.3 s / 39,005 ids / 0 incomplete / 99.99% overlap** with the spike's id set; wired default path **109.3 s / 39,007 ids / 0/192 incomplete** (spec status line). Both plan phases took ~27 s of the total (192 shards, not 56 — planning rides the same slow search endpoint).

### II.4.3 The operator's re-run and the profile (runs 10–17)

**Run 10** (2026-10-08 12:10–12:38 UTC, `done`, 28m34s elapsed): the console re-run of the run-#9 filter after the merge — the documented end-to-end improvement **77m56s → 28m33s** (~2.7×), search phase ~20 min → ~1.7–2 min, hydration now essentially all of the remaining time.

**The hydration profile** (scratch run through `serve.runner.run_filter`, 1,239.7 s of hydration alone; findings note cited above):

| Stage | Wall | Detail |
|---|---|---|
| Count | 0.5 s | one GraphQL count query |
| Discovery | 93.5 s | 483 pages, 0 incomplete (~27 s of it planning probes) |
| **Hydration** | **1,239.7 s (20.7 min)** | 39,005 repos, **1,951** batch requests, 0 fallbacks, 0 unresolved |
| Enrichment | 0.2 s | all three virtuals answered from hydration data; 0 extra calls |
| Writes / bookkeeping | 3.1 s | row loads, ordering, payload assembly |
| **Total** | **22.3 min** | points: `remaining` 4,912 → 1,996 (≈2.9k of the 5,000/hour) |

`cProfile` (hydration only): the run is **blocked on batch completion** (`concurrent.futures.wait` / `Event.wait` dominate cumulative time); TLS body reads ≈ 800 s spread across the wall; SQLAlchemy row construction ~50–90 s is the only material CPU cost. Throughput **1,888 repos/min** at concurrency 10 that day. The ranked next bottleneck was exactly one lever: **raise hydration concurrency** — `min(limiter_max_concurrent, 20)` at the time, corpus preset set to 10; doubling to 20 was predicted to cut 20.7 min toward ~10–11 min at unchanged point cost, with the existing backoff as the watchtower for secondary limits.

**The concurrency ladder (runs 12–23).** The operator then walked the dial, one settings-page save at a time — visible in the settings audit trail to the second:

| When (UTC) | Change (audited) | Run it enabled |
|---|---|---|
| 10-08 14:45:08.203 | concurrency 10 → 20 | **run 12** started 25 ms later, 14:45:08.228 |
| 10-08 15:00:44 | concurrency 20 → 16 | runs 13–16 |
| 10-08 19:42:10 | concurrency 16 → 17 | runs 17–19 |
| 10-09 11:47:36 | concurrency 17 → 18 | run 20 (6 s before submit) |
| 10-09 13:32:54 | concurrency 18 → 17 | run 22 (11 s before submit) |

The measured result (bundle `timings`, where recorded; discovery is the GraphQL engine in all of these):

| Run | C | Filter pages | Discovery | Hydration (fetch / apply) | Total elapsed | Verdict |
|---|---|---|---|---|---|---|
| 12 | 20 | 3×20 | 118.1 s | 826.8 s (763.4 / 62.1) | 954 s | ~13.8 min hydration — the lever works |
| 16 | 16 | 3×20 | 105.3 s | 698.2 s (592.8 / 103.9) | 817 s | apply time grows on a busy DB |
| 17 | 17 | 3×20 | 133.4 s | 556.8 s (554.6 / 104.2) | 704 s | |
| 18 | 17 | 9×20 | 101.5 s | **1,007.6 s** (1,006.1 / 57.1) | 1,144 s | the bad-latency night (2×); enrich 26.6 s / 84 calls — data-source variance |
| 19 | 17 | 9×20 | 95.6 s | **501.7 s** (500.7 / 59.7) | 605 s | the "10-minute baseline" reference run |
| 22 | 17 | 9×20 | 234.7 s | 501.1 s (499.8 / 52.6) | 743 s | `partial` — 1 incomplete shard (discovery that night was slow) |
| 23 | 17 | 9×20 | 124.4 s | 482.6 s (480.3 / 108.1) | 620 s | apply now ~22% of hydration |

Runs 11, 13–15 were cancelled experiments (11 reached 38,919 fetched before cancel; 13 fetched all 39,073 then cancelled mid-hydration; 14/15 aborted in ~7 s). Runs 20–21 were cancelled quickly the next day (20 at C18 after ~4.3 min; 21 in 2 min). Note the spec change between run 17 and 18: `page.max_pages` 3 → 9 (which is why the filter hash changes from `b62f7091…` to `8d661df8…` from run 18 onward).

**Confound, stated honestly:** the ladder was *meant* to be a controlled comparison, but GitHub latency moved the floor each night — run 18 took twice run 19's hydration time on identical code and request counts. The cleaner reading is the aggregate: at C10 the best case measured was ~20.7 min of hydration; at C16–20 the best cases measured were 8–10 min. The predicted "10–12 min at 20" was accurate; concurrency 10 was confirmed as the single biggest removable cost.

Also shipped that evening (`0d232a2`…`43fc69a`): batched DB apply overlapped with in-flight fetches, streamed apply progress, concurrent planning-probe batches, batch-size cap raised to 50 (default stayed 20; `2d6a3cb` + `7cfc5f2`), 502/504 split before REST fallback (`589663a`), the `./start` and `./restart` launcher scripts (`ef807aa`), and folded page upserts (`43fc69a`). **Stage timings and per-stage wall clocks were persisted into every bundle from this night** (`6c7eb04`) — which is why the table above exists at all.

**`design/further-optimization.md`** closed the day by ranking what was left: (4.1) hydration concurrency — already being tested by the ladder; (4.2) stop paying for unchanged rows — **38,893 of 39,005 rows were byte-identical between two runs minutes apart**, yet the second run paid all 1,951 requests (two fixes sketched: freshness window, or REST+ETag refresh path; explicitly "a product decision, not a technical one"); (4.3) cut the SQLAlchemy write CPU; (4.4) discovery polish was diminishing returns; (4.5) make every run self-reporting (shipped later). §6 parked the big bet — a local cached corpus — against D4 (live-only), with the trade-off stated rather than hidden.

## II.5 Era verdicts (speed era)

- **H-4 (batch isolation is enforceable):** confirmed. The named contract tests held; the engine's per-repo attribution is what later let a malformed query hide as "working" without data loss (it degraded cleanly), and what made the `undefiniedField` bug *findable*.
- **H-5 (discovery can ride the points meter):** confirmed. 67.9 s isolated / 109.3 s wired for a corpus that cost ~20 min of REST search; ~430–500 of 5,000 points. The 25× cost-model change predicted in `corpus-building-efficient-engineering.md` §9 materialized as a 2.7× end-to-end win (the rest of the time is hydration).
- **H-6 ("hydration concurrency is the next lever"): directionally right, magnitude confounded.** C10 → C16–20 cut the best-case hydration from ~20.7 min to ~8–10 min, not because the code changed again but because the queue depth did. GitHub's response latency — measured varying 2× night to night on identical code — is a permanent confound; every later timing claim in this document names its night.
- **H-7 (search drift explains cross-run corpus deltas):** supported. 99.93% (17,782/17,795) of run 9's export was rediscovered by the spike; the residue matched the documented drift magnitude for REST runs; `total_count` drift 38,820 → 38,833 within 5 h.
- **H-8 (limiters should adapt to phase, not fight each other):** confirmed the hard way — the discovery starvation incident (`176/192` shards dead) was a *client-side* bug masquerading as an API problem; the phase-scoped `bound_concurrency` fix was the origin of the later "one authority per timescale" principle in the runtime audit.
- **Failure rows added:** planner union bug (runs 5–7), `owner.databaseId` silent fallback (runs 1–9 era), discovery slot storm (58 s scratch run), concurrency-ladder confound (run 18).

---

# Part III — The wall era (2026-10-09 → 2026-10-11): "how fast before GitHub pushes back"

By 2026-10-09 the pipeline could find 39k repos in ~100 s and hydrate them in ~8–10 minutes at concurrency 17–20 — but the *design* said batch 29 and concurrency 32–40 should be safe, and half the hourly point budget sat unused. This part is the story of testing that belief: an audit that predicted 4.5–6 minutes, three shipped themes, one runaway bath, five wall runs, a hardening pass, and two record runs that settled the operating point at **28% slower than the design's projection but with zero pushback**.

## III.1 The audit (2026-10-09): ten minutes, half the meter, invisible walls

`design/runtime-audit-and-adaptive-control.md` (dated 2026-10-09, "No code was changed") is the pivot document of this history. It answered one operator question — *"we finish a 39,000-repo run in 10 minutes and use barely half our 5,000-point hourly allowance; how much faster can we go before GitHub pushes back?"* — with measured arithmetic and an explicit list of unknowns.

**Where the ten minutes went (run 19's own timings):**

| Phase | Seconds | Share |
|---|---|---|
| count | 0.7 | 0% |
| discovery | 95.6 | 16% |
| candidates + enrich + sort + snapshot | ~3.8 | <1% |
| **hydration** | **501.7** | **83%** |

The lopsided shape — 5 of 6 minutes inside 1,959 small batches of 20 — identified batch size as free money: `round(5 × 29 / 100) = 1`, so **29 is the largest batch that still costs one GraphQL point** (30 doubles the price; 50 may triple it). The audit also recorded the variance fact that makes every timing comparison conditional: **run 18 used the same 1,959 requests and took 1,006 s vs run 19's 502 s** — a 2× server-side latency swing on identical code.

**The quota ledger:** a full 39k run at batch 20 measured ~2,916 points (2,455 accounted + ~460 in unaccounted timeout/retry penalties) = 58% of the hourly allowance; ~0.0745 points/repo; peak rate ~235 requests/min (12% of the 2,000/min secondary ceiling); 20 concurrent (20% of 100). At batch 29: ~2,300 points/run (~46–48%), ~85k repos/hour realistic.

**The hidden ceilings** (the audit's most durable contribution): the unadvertised CPU-time rule (90 s CPU/60 s wall, ≤60 s GraphQL — taken literally ≈ 60 in-flight, but the project's own clean runs at C=20 disprove the strict reading); the documented 100-concurrent cap (a tripwire, not a target); the 10-second query timeout that *charges extra points* when it fires; the September-2025 per-query resource limits (large nested queries get partial results + error); and the window-anchor puzzle (`x-ratelimit-reset` timestamps at odd minutes → the window is anchored at first token use, not top-of-hour — while the client's own limiter assumed top-of-hour).

**Two quirk findings in our own limiter:** the in-window count only ratchets up and resets on the UTC-hour boundary (so draining to zero early could self-lock the client for up to ~59 minutes against GitHub's real earlier reset), and the client books exactly 1 point per request — true at batch ≤29, **wrong above it**.

**What the audit recommended** (ranked): (1) batch 20 → 29; (2) concurrency 20 → 32, then 40 (48 as ceiling); (3) HTTP pool hygiene; (4) the adaptive controller (three loops: per-batch guard 10–29, AIMD window 8–48 starting at 20, quota pacer `(remaining − 400) ÷ seconds-to-reset`); (5) cost/latency telemetry; (6) limiter correctness at the edge; (7) optional cleanup. Projection: **4.5–6 minutes** for 39k at batch 29 / C32–40, ~2,300 points, ~400 secondary points/min (20% of that ceiling). Risk verdict: "Yes — and with room", with four honest caveats (invisible CPU rule; timeout penalties grow with batch size, fallback 25; window-anchor quirk becomes operational at the edge; everything about secondary limits is "subject to change without notice").

## III.2 The three themes and the feasibility review

Three implementation plans were written from the audit (`docs/superpowers/plans/2026-10-09-transport-pipeline-efficiency.md`, `-quota-limiter-utilization.md`, `-adaptive-rate-controller.md`) and put through a **consolidated feasibility review** before execution. The review is a methodology artifact in its own right: every file:line anchor re-read; the circular-import blocker reproduced with the repo's own venv before being fixed in-plan (`ImportError: cannot import name 'rate_limit_from_payload' from partially initialized module 'lib.graphql_batch'` → lazy import inside `PointsLedger.add`); a pause-conflict found between themes (Theme 2's 60 s pause could *shorten* Theme 3's longer pause → extend-only fix); a test-vs-behavior conflict caught by cross-checking plans against each other (`max_attempts=1` pin so the first-403 path is reachable after message preservation); and a factual correction ("Theme 2 caps hydration at 32, not 48" — the plan's original claim was wrong). The review also demanded a clean base: the six in-flight working-tree files had to be **committed, not stashed** — "reverting them invalidates all anchors."

**What did not ship from the audit's projection, and why that was right:** the audit's 4.5–6-minute scenario required both batch 29 and concurrency 32–40 to hold up live. Production decided otherwise (§III.6 onward). The audit itself said so in advance: "stop at the first unexplained pushback."

## III.3 Theme 1 — transport and pipeline efficiency (shipped 2026-10-10 00:08–01:00 UTC)

Four commits, each replacing a measured cost:

| Commit | Change | The measured problem it removed |
|---|---|---|
| `09f352c` | `httpx.Limits(max_connections=64, max_keepalive_connections=64, keepalive_expiry=60.0)` + `trust_env=False` | keep-alive pool (20 idle/5 s) smaller than 32 workers; silent env-proxy surprises |
| `039e956` | `_post` reuses the audit hook's cached JSON | every batch body parsed twice |
| `d176e83` + `6ead5cb` | discovery upserts buffered per worker (10 pages / 1,000 items; best-effort deadline flush) | DB latency added directly into the discovery phase on the fetch thread |
| `b721719` | audit inserts on a bounded daemon writer thread (queue depth 4) | audit commits inline with the request path; bounded, acknowledged loss ≤ ~500 rows on a kill |

Verification (`docs/findings/2026-10-09-transport-pipeline-efficiency.md`, measured 2026-10-10): focused deterministic tests (pool config, parse-once, batch-by-threshold event ordering `["page", "page", "page", "upsert-start", "upsert-end"]`, writer-thread blocking semantics), full suite **1495 passed / 94.79% coverage**, ruff/black/mypy clean. Notably, the plan's optional live timing run was **deliberately skipped** — "run-to-run server latency variance was measured at 2x on identical code (run 18 vs run 19); a single live run would not be informative." That is the era's methodology in one sentence: when the instrument is noisy, don't add noise.

## III.4 Theme 2 — quota and limiter correctness (shipped same night)

Eight tasks; the ones that changed behavior:

- **Batch default 20 → 29** (`5444e32`, migration `0014`): server default, settings spec, and a one-time `UPDATE app_settings … WHERE graphql_batch_size = 20`; downgrade restores 20. The cap stays 50 — 29 is a *default*, not a wall.
- **Point telemetry** (`b03dcbd`, `0539373`, `7bbc923`, `1d91f20`): hydration queries now request `rateLimit { cost used remaining }`; `BatchStats` carries `points_cost/used/remaining`; `audit_log` gains `rl_used`, `run_id`, `phase` + `audit_run_idx`; the runner persists a per-phase `PointsLedger` into `field_stats["points"]` (`{count: …, discovery: …, hydration: …}`). This is why every later claim of "the run cost N points" is exact rather than estimated.
- **Hydration ceiling 32** (`f633ce0`): `HYDRATION_CONCURRENCY_CEILING = 32`; each run snapshots `min(limiter_max_concurrent, 32)`; corpus preset 32.
- **Limiter window re-anchored** (`78c1f7e`): stored `window_end` from `x-ratelimit-reset` replaces `floor(now/3600)`; reconcile uses the response's own limit header.
- **403/429 message preservation + 200-body pause** (`4435932`): final throttles keep GitHub's message; a 200 body carrying rate-limit markers pauses the bucket instead of hot-requeueing.

Gate: **1514 passed, 94.86% coverage**. The deliberate deferrals were recorded, not lost: `x-ratelimit-used` is not guaranteed on GraphQL (the ledger relies on the body's `rateLimit.cost`), and "batch 29 narrows the 10-second timeout margin, so live monitoring of 502/504 counts is required before any batch growth, with 25 as the documented fallback" — a sentence that run 24 would prove prescient.

## III.5 Theme 3 — the adaptive controller, and the soak that kept it off

The controller (`src/limiter/adaptive.py`, `088a4f9` + `5a888bd` + `65d0b4c`) implements the audit's three loops as code: AIMD window (`MIN_WINDOW = 8`, `MAX_WINDOW = 48`, start 20), batch guard (10–29, ×0.7 on a signal, +1 per 50 clean batches), quota pacer (reserve 400 points, burst 4, never sleep-to-reset), whole-pool pause with jitter, and a retry budget (10%). It is wired into `fetch_batch(..., adaptive=…)` behind `GITCORPUS_ADAPTIVE=1`, later a settings checkbox (migration `0015`, default **off**, `6dbb759`, 17:49 UTC).

**The soak** (scratch run, 2026-10-10 15:59:03 → 16:19:57 UTC; the run's audit rows carry `run_id = NULL`, which is how it was identified for this document): batch 29, adaptive ON, envelope 32, **wall 20.9 min**, 0×403, but **2 × 504 timeouts** (16:02:22.873Z and 16:08:17.491Z; ~11.2 s; no `retry-after`, no rate-limit headers) triggered two full drop+pause cycles: window 20 → 10 → 8, batch 29 → 20 → 14 (recovering to 26), 2 pauses, 2,387 hydration points, pacer settling at ~1.23 points/s after a mid-run window reset, 0 deferred, 0 unresolved, complete result (39,418/39,418, no warnings).

**Verdict (recorded in `docs/findings/2026-10-09-adaptive-soak.md`): keep the flag OFF.** The controller did exactly what it was designed to do — and that was the problem: one isolated timeout confirmed herded the whole run down to W=8–10 for the rest of its life, and the pacer's post-reset rate alone implies a ~19-minute tail. "The controller is a seatbelt for driving above 20, not a faster engine." Two structural follow-ups were named: don't treat a lone 504 as a drop without corroboration, and decide whether the pacer should pace the whole window or allow a burst above the reserve. Both remain open threads.

The soak's side effect matters to the wall story: it ran via a scratch script that called `update_run_settings` directly — **leaving `limiter_max_concurrent = 32` in the settings row without an audit entry.** Run 24 would start from exactly that value.

## III.6 Run 24: the 403 storm (2026-10-10 17:09–17:17 UTC)

Configuration at submit: **batch 29, concurrency 32** (the profile the plans had agreed on; the controller OFF). The audit rows tell the story minute by minute:

| Phase / minute | Requests | Notes |
|---|---|---|
| discovery (32 workers), 17:09:56–17:11:32 | 434×200, 1×504 (11.6 s) | **clean** — 95 s for the whole corpus |
| hydration 17:11 | 113 (84×200, **28×403**) | first 403 at **17:11:48** — 8 seconds after hydration began |
| hydration 17:12–17:15 | 25 / 104 / 125 / 119 | 403s every minute (4 / 32 / 32 / 31) |
| hydration 17:16–17:17 | 79 / 61 | 4 / 28 |

Totals: **159 × 403**, every one a fast rejection (0.3–1.1 s) carrying `retry-after: 60` and **no rate-limit headers** — GitHub's secondary/scraping limit, not the points meter (only ~370 points spent; `remaining` never fell below 4,144). The mechanism is the exact anti-pattern the audit had warned about: **a 403 slept only the worker that received it; the other 31 kept knocking** — the octokit-#629 pattern. The pool-wide pause existed only inside the controller, which was off. The run was cancelled at 17:17:57 (26% hydrated).

**Verdict: concurrency 32 was the mistake, not batch 29.** Discovery at 32 was clean in every run of this era — search queries are light and ride the points meter; hydration's five-connection documents are what the scraping heuristic watches. Same concurrency, different query weight.

## III.7 The settings interlude (between the two walls)

The settings audit trail shows the operator's exact fingers, to the second:

| Time (UTC) | Change | Notes |
|---|---|---|
| ~15:59 | soak's scratch script sets **C=32** | no audit row (direct `update_run_settings`) — visible only via run 24's starting value |
| 17:17:50 | C 32 → **20** | saved while run 24 was being cancelled |
| 17:18:12 | C 20 → **17** | |
| (unaudited, before 17:55) | B 29 → **25**, C 17 → **20** | not from the settings page; mechanism unrecorded |
| 17:55:52 | **adaptive ON** (B=25, C=20) | 9 seconds before run 25 |
| 18:06:19 | C 20 → 17 | |
| 18:07:59 | **adaptive OFF** | 19 seconds before run 26 |

The §11.4 summary in `runtime-audit…md` ("batch 29 → 25, concurrency 32 → 20, discovery stays 32") is the net of the first three rows. Two transitions happened outside the audited path; this document reports them as gaps rather than guessing their source (one demonstration of such a path is the soak itself).

## III.8 Run 25: the wall that got absorbed (and the controller that did not see it)

Configuration: **batch 25, C=20, adaptive ON**. Start 17:56:01; discovery 84 s, clean; hydration at full window from 17:57:34 at ~6,000 repos/min. At **17:59 (28 seconds in)**: **19 × 403** — again `retry-after: 60`, no headers. Each worker slept its own 60 s; batches/min collapsed to 120; by 18:01–18:03 throughput recovered (292 / 287 / 226 per min) with **zero further 403s**. The run was cancelled at 18:04:07 at ~50% (~19,500/39,432) — on track for ~18:07.

Two findings, one uncomfortable (from §11.5):

1. **Why the wall appeared at "safe" settings:** the token was still *warm* — run 24 had produced 159 secondary hits 40 minutes earlier, and GitHub's secondary sensitivity escalates with repeated triggers and decays slowly — and the profile was slightly hotter than run 19 (batch 25 = +25% compute per query; faster responses meant ~290–330 requests/min vs run 19's ~235).
2. **The controller was ON and could not possibly react:** its drop signal fires only on *batch-level* failures; these 403s were absorbed inside `request_with_retry` (sleep, retry, success), so no drop was recorded, the window never moved, and the Redis pause timestamp never changed. **The controller is blind, by construction, to the exact failure mode that mattered.**

## III.9 Runs 26–27: timeouts, then synchronized waves

**Run 26** (17:56+ session's third attempt, started 18:08:19, cancelled 18:10:38): batch 25 / C=17 / adaptive off. Discovery took 1×504 (11.1 s); hydration produced **20 timeout-class responses in 40 seconds** (latencies 11–34 s, avg 17.2 s — the engine's 30-second client timeout visible in the data). The token's edge was unhealthy; the operator cancelled in 2m20s. No 403s.

**Run 27** (started 18:59:19, cancelled 19:09:13): same profile. Discovery clean (82 s); hydration shows the **synchronized-wave pattern** the hardening was later built against: 17×403 at 19:01, 15 at 19:02, 16 at 19:04, 3 at 19:05, 11 at 19:06, 5 at 19:07, 1 at 19:08 — **68 × 403** total (audit-verified; §11.6's scoreboard says 48 — see Appendix B), in waves as the pool's sleepers woke together and re-knocked. Cancelled at 10 minutes.

## III.10 Run 28: the scraping flag (2026-10-10 21:18–21:34 UTC)

Two hours after run 27, the same profile ran again — and this time the wall introduced itself **in writing**. The 403 body, verbatim (captured that night, quoted in §11.8):

> You have exceeded a secondary rate limit. Please wait a few minutes before you try again. For more on scraping GitHub and how it may affect your rights, please review our Terms of Service...

Same shape as the earlier walls (`retry-after: 60`, no rate-limit headers) — but the wording is the tell: this is GitHub's anti-scraping flag, whose sensitivity escalates with repeated triggers and decays slowly. The night's sequence had been 159 / 19 / 0 / 68 secondary hits across runs 24–27; run 28 collected **83 × 403** more, in six waves through the hydration window (21:20, :22, :24, :27, :29, :31).

**And then it finished the job.** Audit rows show 1,579 × 200 hydration responses — exactly `39,464 ÷ 25` — meaning **every 403ed batch eventually succeeded on retry**, and the DB records the run as `done` at 21:34:10 (15m42s), with the bundle's own ledger: `incomplete: false`, **18,213 items**, warnings `[]`, points `{count 1, discovery 440, hydration 1,579}` = 2,020. The recovery is real — but it was luck of timing (the 403s were absorbed before exhausting retries), not design.

**Corrections this document records (Appendix B has the full list):** §11.6's scoreboard says run 28 was "cancelled at ~50%" — the database, audit log, and bundle all say it completed `done` at 100%; and §11.8's phrase "a three-request hydration probe … tripped it immediately" does not correspond to any audit rows (run 28's hydration was 1,662 requests). The phrase most plausibly describes an unrecorded manual probe made to capture the flag's wording — this document labels it exactly that instead of inventing a mechanism.

## III.11 The hardening (shipped 2026-10-10 23:47 → 2026-10-11 00:10 UTC)

Five mitigations closed the failure modes the runs had exposed (`a723844`, with `4620fb0` making two of them stick; `src/limiter/secondary.py` carries the process-level streak state):

1. **Pool-wide pause on every 403/429** — the retrying worker extends the shared Redis bucket atomically (`pause_at_least`, extend-only) for its computed wait, so *no sibling keeps knocking* — the octokit-#629 anti-pattern finally closed for secondary rejections, not just for 200-body markers.
2. **Multiplicative escalation with a cap** — repeats double the pool pause: **60 → 120 → 240 → 480 s** (cap), plus **0–30 s jitter** so sleepers wake desynchronized instead of in a wave.
3. **Jitter everywhere** — +0–30 s on the pool pause, +0–1 s on limiter-denial sleeps.
4. **A per-pass budget** — after **15 secondary hits in one batch pass** (hydration/enrichment; discovery hits don't count), dispatching stops, remaining queued repos are deferred with the reason "secondary rate limit budget exhausted", and the pass ends **partial and resumable** instead of grinding the token down. `4620fb0` made the stop stick and wired production jitter.
5. **The controller is fed** — each 403/429 seen while adaptive is on calls `note_secondary()`: window halves (floor 8), cooldown starts, and the count lands in the snapshot as `"secondary"` — closing §11.5's blind spot.

A related earlier fix (`439b35c`/`4435932`, from Theme 2) is part of the same story: final 403/429 responses now keep GitHub's message so the *flavor* of throttle is visible in the logs at all.

Section 11.8's operational guidance, recorded verbatim: after a scraping-flavored flag, rest that token for 24 hours or more; "The next full run waits for that." Production would test that guidance within three hours — and win.

## III.12 The record runs: 29 and 30 (2026-10-11 00:22 and 00:44 UTC)

At **00:22:50** the settings row was updated — concurrency to **17**, batch to **20** (the before-state shows an unaudited interlude at C=10/B=20; after: C=17/B=20). Four seconds later, run 29 started. Thirteen minutes earlier the last hardening commit had landed. The changes under test: pool-wide pause/escalation/jitter, the 15-hit budget, message-preserving throttles, and (from Migration 0014) exact point telemetry.

**Run 29** — 39,484 repos in **9m41s** (581 s elapsed), zero 403s:

| Stage | Value |
|---|---|
| count | 0.67 s, 1 point, `remaining` starts fresh (4,999) |
| discovery | 93.7 s, 436 responses, 0 incomplete |
| hydration | 479.8 s (fetch 478.3 / apply 61.4), 1,993 requests (1,975 batches + 18 from 9 splits), **9 × 499** |
| points | 1 + 436 + 1,984 = **2,421**; `remaining` min 2,831 |
| the one rough moment | ~00:28:17–42: a GitHub edge spike — 7.7 s completion gap, 9 requests aborted with `499` after 11–19 s, several 200s at 14–30 s (max **29.82 s**, within 200 ms of the client's 30 s timeout), `x-ratelimit-remaining` flipping between two regions (~3.7k vs ~4.86k) |
| recovery | the engine treated the 499s as timeout-splits — 9 requeues, +18 requests (~1% overhead), all resolved; zero 403s |

**Run 30** — 39,485 repos in **9m08s** (548 s), the cleanest run on record:

| Stage | Value |
|---|---|
| discovery | 99.0 s, 436 responses, 0 incomplete |
| hydration | 440.8 s (fetch 439.0 / apply 60.9), 1,975 requests at batch 20 (1,975 × 200 = exactly `39,485 ÷ 20` — zero retries) |
| points | 1 + 436 + 1,975 = **2,412**; ended at **667 remaining** |
| quality | zero 403s, zero timeouts, zero requeues, zero unresolved; max latency 8.55 s; largest completion gap 2.1 s; throughput flat at 260–277 batches/min |

**The budget math, now exact:** at batch 20 a 39.5k run costs ~2,400 points; two runs fit one 5,000-point window (runs 29 + 30 together left 667); a third must wait for the reset. This is the number the "marathon mode" idea note (`docs/superpowers/plans/2026-10-11-run-modes-idea.md`) builds on, together with the era's central asymmetry: "A 10-minute run that takes one 60 s pause loses >10% — and with retry dynamics we measured 10 → 20.9 min. A 7-hour, 1M-repo build loses 0.24% to the same pause."

## III.13 The settled operating point and era verdicts

**The settled single-token point (documented in `run-limits.md` §4, `further-optimization.md` §4.1, `environment.md`, and §11.6):** **batch 20, concurrency 17–20** (16 after a secondary-limit storm), discovery 32, adaptive off, plus **a 30–60+ minute cooldown after any secondary storm** (repeated trips escalate; the scraping flag asks for 24 h). The zero-403 full-corpus history: run 30 (9m08s), run 29 (9m41s), run 19 (~10m05s, pre-hardening, pre-run-24).

**Hypothesis verdicts for this era:**

- **H-10 (the audit's 4.5–6-minute projection at batch 29 / C32–40): falsified by production — and this was the audit's own stated design.** Concurrency 32 tripped the scraping-flavored secondary limit in the first 8 seconds of hydration (run 24, 159×403); batch 29 + C20 with adaptive on absorbed a 19×403 burst (run 25); the safe operating point turned out to be *below* everything the audit recommended except its "stop at the first unexplained pushback" caveat. Projection error magnitude: **9m08s vs 4.5–6 min ≈ 50–100% slower than projected**, at ~2,400 points vs the projected ~2,300.
- **H-11 (batch 29 is "free money"): falsified in the wall era.** The 1-point arithmetic was right, but the 10-second timeout margin narrows at 29 (the Theme-2 plan said so; run 24 ran at 29) and the extra compute per query feeds the scraping heuristic. The documented fallback (25) held through runs 25–28; the settled point is 20.
- **H-12 (adaptive is the answer, default on): falsified.** The soak showed the controller is sticky (W 20→8 from two lone timeouts) and blind (retry-absorbed 403s never register). It stays off by default; the closure of the blindness (`note_secondary`) makes it *usable* at higher ceilings, not recommended at proven ones.
- **H-13 (burst stalling is worse than pacing): confirmed the hard way.** Every wall run shows the same signature: sleeping workers wake together and re-trip (68×403 in waves, run 27; ~50 s full stall, run 28). The pool-wide pause + jitter + escalation triad is the corrective, and runs 29/30 are its evidence.
- **H-14 (two runs per window is the practical single-token limit at the settled point): confirmed exactly** (runs 29+30 ended at 667 remaining).
- **Failure rows added:** concurrency 32 hydration (run 24); adaptive toggle (soak, run 25's inert controller); batch 29 timeout pressure (run 24's 2×504 at 11–12 s; Theme 2's own warning); the unaudited-settings gap (soak's C=32 leak); warm-token escalation (runs 25–28); run 28's near-miss recovery.

**What remains open from this part** (kept current in §IV.5): cooldown policy as a first-class control (run-modes idea); lone-504 drop policy for the controller; pacer vs burst decision; whether the token's scraping flag had fully decayed or the hardened pacing simply avoided re-tripping it; CI never having run; and the marathon-mode pacing through hourly resets.

---

# Part IV — The ledgers

Everything below is meant to be kept current. See §0.5 for the update rules.

## IV.1 Run register — every row in `runs`, plus the scratch runs that mattered

Settings columns (B = `graphql_batch_size`, C = `limiter_max_concurrent`) are from the settings audit trail in `audit_log` — the values in force at the second each run started. Unless a row says otherwise: runs 1–4 ran the **interactive defaults** (10 shards / 500 candidates / 200 hydrate / 100 enrich / 3,600 s), and runs 5–30 ran the **corpus profile** (1,000 / 100,000 ×3 / 86,400 s); only B and C changed within those profiles. "Items" = rows the run exported after virtual filters (`run_items`). Elapsed is DB `finished_at − started_at`.

### IV.1.1 The console runs (all rows in the `runs` table)

| # | Started (UTC) | Filter | B / C | Found | Fetched | Items | Elapsed | Status | Notes |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 10-03 09:54:56 | `language:rust` | 20 / 10 | 1,377,440 | 3,000 | 500 | 316 s | partial | console smoke; bundle proves REST fallback (`req 10 / val 0 / handled 200`); later frozen as corpus |
| 2 | 10-03 10:48:48 | `user:Thabettt fork:true`, `min_commits:100` | 20 / 10 | 16 | 16 | 8 | 16 s | partial | same fallback signature |
| 3 | 10-03 12:44:31 | `stars:5..* language:php fork:true` | 20 / 10 | 152,833 | 3,000 | 500 | 296 s | partial | |
| 4 | 10-03 13:08:43 | `language:java`, `min_stars:9`, `min_commits:50` | 20 / 10 | 163,501 | 2,893 | 196 | 303 s | partial | first observed virtual-filter drop |
| 5 | 10-06 02:44 (ran 12:54) | run-#9 filter (pages 10×100) | 20 / 10 | — | 0 | 0 | 257 s | failed | `orphaned: process restarted`; queued 10 h |
| 6 | 10-06 02:50 (ran 08:36) | `created:>=2025-02-24 language:rust` + virtuals | 20 / 10 | — | 0 | 0 | 467 s | failed | `orphaned: process restarted` |
| 7 | 10-06 13:01 | run-#9 filter | 20 / 10 | — | 0 | 0 | **29,667 s (8h14m)** | failed | planner union bug; orphaned at 21:16 |
| 8 | 10-06 22:23:53 | `language:rust` | 20 / 10 | — | 0 | 0 | 4 s | cancelled | aborted smoke |
| 9 | 10-06 22:31 (ran 10-07 01:07) | run-#9 filter | 20 / 10 | 38,833 | 38,833 | **17,795** | 4,677 s (78m) | **done** | 1,942 requests, 0 fallbacks; REST-era discovery; corpus frozen |
| 10 | 10-08 12:10:15 | run-#9 filter | 20 / 10 | 39,051 | 39,051 | 17,948 | 1,714 s (28m34s) | **done** | operator re-run; first console run on GraphQL discovery |
| 11 | 10-08 14:33:39 | run-#9 filter | 20 / 10 | 39,072 | 38,919 | 0 | 688 s | cancelled | before the C=20 switch; aborted mid-hydration |
| 12 | 10-08 14:45:08 | run-#9 filter | 20 / **20** | 39,070 | 39,070 | 17,959 | 954 s | **done** | first C=20 run; hydration 826.8 s |
| 13 | 10-08 15:04:35 | run-#9 filter | 20 / 16 | 39,073 | 39,073 | 0 | 1,269 s | cancelled | discovery + hydration completed (updated 39,069); cancelled before snapshot |
| 14 | 10-08 15:30:06 | run-#9 filter | 20 / 16 | — | 0 | 0 | 6 s | cancelled | aborted |
| 15 | 10-08 15:47:39 | run-#9 filter | 20 / 16 | — | 0 | 0 | 8 s | cancelled | aborted |
| 16 | 10-08 17:22:17 | run-#9 filter | 20 / 16 | 39,093 | 39,094 | 17,972 | 817 s | **done** | hydration 698.2 s |
| 17 | 10-08 20:08:05 | run-#9 filter | 20 / 17 | 39,119 | 39,119 | 17,991 | 704 s | **done** | hydration 556.8 s |
| 18 | 10-08 21:02:36 | run-#9 filter (pages 9×20) | 20 / 17 | 39,122 | 39,122 | 17,992 | 1,144 s | **done** | the bad-latency night: hydration 1,007.6 s (2× run 19) |
| 19 | 10-08 21:50:09 | run-#9 filter | 20 / 17 | 39,128 | 39,128 | 17,998 | 605 s | **done** | the 10-minute reference; ~2,916 points |
| 20 | 10-09 11:47:42 | run-#9 filter | 20 / 18 | 39,226 | 38,539 | 0 | 256 s | cancelled | C=18 probe, aborted |
| 21 | 10-09 13:30:44 | run-#9 filter | 20 / 17 | 39,240 | 12,518 | 0 | 123 s | cancelled | aborted |
| 22 | 10-09 13:33:05 | run-#9 filter | 20 / 17 | 39,240 | 35,276 | 16,593 | 743 s | partial | 1 incomplete shard; discovery 234.7 s (slow night) |
| 23 | 10-09 23:44:48 | run-#9 filter | 20 / 17 | 39,287 | 39,287 | 18,103 | 620 s | **done** | hydration 482.6 s; apply 108.1 s |
| 24 | 10-10 17:09:54 | run-#9 filter | **29 / 32** | 39,425 | 39,425 | 0 | 483 s | cancelled | **159×403 within 8 s of hydration start**; cancelled at 26% |
| 25 | 10-10 17:56:01 | run-#9 filter | 25 / 20, adaptive ON | 39,432 | 39,432 | 0 | 486 s | cancelled | 19×403 absorbed in ~1 min; ~50% at cancel; controller inert |
| 26 | 10-10 18:08:18 | run-#9 filter | 25 / 17 | 39,436 | 39,436 | 0 | 140 s | cancelled | 20 timeout-class responses, latencies 11–34 s |
| 27 | 10-10 18:59:19 | run-#9 filter | 25 / 17 | 39,441 | 39,442 | 0 | 594 s | cancelled | 68×403 in synchronized waves |
| 28 | 10-10 21:18:28 | run-#9 filter | 25 / 17 | 39,464 | 39,464 | **18,213** | 942 s | **done** | 83×403, every batch recovered; scraping flag captured; 2,020 points |
| 29 | 10-11 00:22:54 | run-#9 filter | **20 / 17** | 39,483 | 39,484 | 18,224 | **581 s (9m41s)** | **done** | zero 403; 9×499 edge spike; 2,421 points |
| 30 | 10-11 00:44:44 | run-#9 filter | **20 / 17** | 39,485 | 39,485 | 18,225 | **548 s (9m08s)** | **done** | cleanest on record; 2,412 points; ended at 667 remaining |

"run-#9 filter" = `created:>=2025-02-24 language:rust`, virtual `{min_stars: 4, min_commits: 50, min_language_bytes: 175000}`. Runs 1–4 used `page {per_page: 20, max_pages: 3}`; 5–17 used various page settings in the same spec family; 18–30 used `max_pages: 9`.

### IV.1.2 The scratch runs (no `runs` row; the measurements behind the decisions)

| Scratch run | Date (UTC) | What it measured | Headline numbers |
|---|---|---|---|
| Discovery spike | 10-08 ~01:00 | isolated shard-and-fetch on the points meter | plan 8.9 s / fetch 59.0 s → **67.9 s**, 418 pages, 38,969 ids, ~430–500 points, 0 retries |
| Prescribed default-build validation | 10-08 | `build_deps` at 10 slots, 32 workers | **58.0 s of failing**: 176/192 shards incomplete, 5,276 ids (13.5%) — the slot-storm bug |
| Conforming | 10-08 | `max_concurrent=32` | 97.3 s, 39,005 ids, 0 incomplete, 99.99% spike overlap |
| Wired default (post-binding fix) | 10-08 | server path, phase binds 32 | **109.3 s, 39,007 ids, 0/192 incomplete** |
| Hydration profile (Parts A/B) | 10-08 | full `run_filter` at C=10 | 22.3 min total; hydration **1,239.7 s** for 39,005 repos (1,951 requests); 1,888 repos/min; points 4,912 → 1,996; cProfile: blocked on batch completion |
| Adaptive soak | 10-10 15:59:03 → 16:19:57 | `run_filter` with `GITCORPUS_ADAPTIVE=1`, B=29 | **20.9 min**; W 20→10→8; B 29→14→26; drops 2 (504s); pauses 2; 0×403; 2,898 points; decision: keep off |

### IV.1.3 Per-phase timings, where recorded (seconds, bundle `timings`; `—` = not recorded in that bundle)

| Run | count | discovery | hydration | fetch / apply | enrich | snapshot + sort | Sum ≈ elapsed |
|---|---|---|---|---|---|---|---|
| 12 | 0.8 | 118.1 | 826.8 | 763.4 / 62.1 | 0.3 | 2.2 | 954 |
| 16 | 0.6 | 105.3 | 698.2 | 592.8 / 103.9 | 0.5 | 3.7 | 817 |
| 17 | 0.7 | 133.4 | 556.8 | 554.6 / 104.2 | 0.6 | 4.0 | 704 |
| 18 | 1.3 | 101.5 | 1,007.6 | 1,006.1 / 57.1 | 26.6 † | 2.3 | 1,144 |
| 19 | 0.7 | 95.6 | 501.7 | 500.7 / 59.7 | 0.3 | 2.1 | 605 |
| 22 | 0.7 | 234.7 | 501.1 | 499.8 / 52.6 | 0.3 | 1.9 | 743 |
| 23 | 0.6 | 124.4 | 482.6 | 480.3 / 108.1 | 0.5 | 3.9 | 620 |
| 28 | 0.6 | 101.8 | 831.3 | 829.4 / 57.8 | 0.6 | 2.2 | 942 |
| 29 | 0.7 | 93.7 | 479.8 | 478.3 / 61.4 | 0.3 | 2.1 | 581 |
| 30 | 0.6 | 99.0 | 440.8 | 439.0 / 60.9 | 0.3 | 2.1 | 548 |
| soak | 0.9 | 111.1 | 1,136.3 | 1,134.1 / 97.0 | 0.2 | 0.2 | 1,254 |

† Run 18's unique enrich cost (26.6 s, 84 `calls_spent`, `handled 340`, `values 38,782 < keys 39,122`) is a data-source variance from the same era as the `owner.databaseId` fix; it never recurred (runs 19+ show enrich ≤ 0.6 s and 0 calls — all virtuals served from hydration data). Runs 5–11 have no per-stage timings: stage timing instrumentation landed in `6c7eb04` at 2026-10-08 16:11 UTC, run 12 is the first bundle carrying them.

### IV.1.4 Audit-derived phase windows (runs 24–30 + the soak)

From `min(ts)`/`max(ts)` per attributed phase — the wall runs' real clocks, including every sleep, retry and storm. Durations are derived from those timestamps.

| Run | count | discovery window (dur) | hydration window (dur) | End of record |
|---|---|---|---|---|
| 24 | 17:09:56.1 | 17:09:56.8 → 17:11:32.2 (95.4 s) | 17:11:40.5 → 17:17:12.4 (331.9 s) | cancelled 17:17:57 |
| 25 | 17:56:02.7 | 17:56:03.1 → 17:57:27.4 (84.3 s) | 17:57:34.9 → 18:03:52.5 (377.6 s) | cancelled 18:04:07 |
| 26 | 18:08:20.8 | 18:08:21.3 → 18:09:48.9 (87.6 s) | 18:09:58.9 → 18:10:38.6 (39.7 s) | cancelled 18:10:38 |
| 27 | 18:59:21.4 | 18:59:21.9 → 19:00:43.5 (81.6 s) | 19:00:52.4 → 19:09:13.5 (501.1 s) | cancelled 19:09:13 |
| 28 | 21:18:29.8 | 21:18:30.3 → 21:20:11.5 (101.2 s) | 21:20:18.9 → 21:34:04.1 (825.2 s) | **finished 21:34:10 (done)** |
| 29 | 00:22:55.6 | 00:22:56.1 → 00:24:28.3 (92.2 s) | 00:24:35.2 → 00:32:29.8 (474.6 s) | finished 00:32:35 |
| 30 | 00:44:46.1 | 00:44:46.5 → 00:46:24.2 (97.7 s) | 00:46:31.0 → 00:53:46.5 (435.5 s) | finished 00:53:52 |
| soak | 15:59:04.2 | 15:59:05.0 → 16:00:54.7 (109.7 s) | 16:01:04.2 → 16:19:52.9 (1,128.7 s) | finished 16:19:57 |

The gap between a phase's last request and the next phase's first is the runner's transition (ordering, load, snapshot); the gap inside hydration between runs is the storm history in §III.

## IV.2 Hypothesis ledger (living)

| # | Era | Hypothesis | Origin / the idea's provenance | How it was tested | Verdict |
|---|---|---|---|---|---|
| H-1 | I | Correctness/reproducibility gates must precede speed work | quality-hardening spec's Freeze Contract; "freeze, then optimize" | 43-commit program; later optimization never broke a gate | **Confirmed** |
| H-2 | I | Optimization ideas must start from an audit with measured costs | efficiency audit S1–S16 with a savings model | 26 perf commits, 1:1 with findings | **Confirmed** |
| H-3 | I–II | Delete dead code rather than quarantine it (R58) | unwired-debt triage decision table | the deleted batch concept was rebuilt on demand 48 h later, stronger | **Confirmed** |
| H-4 | II | A batch engine with per-repo attribution can keep isolation guarantees | the old module's five defects (corpus doc §10.3) | named contract tests; live `undefinedField` bug degraded cleanly | **Confirmed** |
| H-5 | II | Discovery (count probes + pages) can ride the GraphQL points meter | the 2026-10-08 spike question | spike 67.9 s; wired validation 109.3 s | **Confirmed** |
| H-6 | II | Hydration concurrency is the next big lever (C10 → 20 ⇒ 20.7 min → ~10–12 min) | hydration profile's ranked bottleneck | concurrency ladder runs 12–23 | **Confirmed directionally; magnitude confounded by 2× latency variance (run 18 vs 19)** |
| H-7 | II | Cross-run corpus deltas are search drift, not estimator bugs | findings research (D6, pagination instability) | 99.93% rediscovery + drift observations | **Supported** |
| H-8 | II | The limiter must bind per phase, not globally | the 176/192-shard starvation incident | 97.3 s / 0 incomplete after `bound_concurrency` | **Confirmed** |
| H-9 | II | Trust the live path only after reading its own evidence | two silent bugs (planner union, `owner.databaseId`) invisible in status codes | bundle inspection + live probes | **Confirmed (methodology)** |
| H-10 | III | B=29 / C=32–40 reaches 4.5–6 min on 39k | runtime audit §9 projection | run 24 → walls; settled point 9m08s | **Falsified** |
| H-11 | III | Batch 29 is free money (same 1 point, 31% fewer calls) | audit §3.4 arithmetic `round(5·29/100)=1` | true on paper; timeout margin + scraping sensitivity in practice | **Falsified live; arithmetic stands** |
| H-12 | III | The adaptive controller should default on | audit §7 three-loop design | soak: sticky (2 lone timeouts → W=8), blind to retry-absorbed 403s | **Falsified (default stays off)** |
| H-13 | III | Bursting then stalling is worse than pacing | python-github-backup's own README; taxi-meter metaphor | every wall run shows synchronized re-knock waves | **Confirmed** |
| H-14 | III | Two 39.5k runs fit one 5,000-point window at the settled point | budget math at ~2,400 points/run | runs 29+30 ended at 667 remaining | **Confirmed** |
| H-15 | II–III | Every run should self-report stage timings and points | further-optimization §4.5 | shipped `6c7eb04` + migration `0014`; this document is built on it | **Confirmed (shipped)** |
| H-16 | III | Pool-wide pause + escalation + jitter + hit budget prevents storms | runs 24–28 failure analysis | runs 29/30 clean; confound: token cool-down | **Confirmed (single-condition evidence)** |
| H-17 | — | Repeat runs should skip unchanged rows (freshness window / ETag refresh) | hydration profile fix proposal #3 (38,893/39,005 identical) | never tested — parked against D4 (live-only) | **Open — product decision** |
| H-18 | — | Discovery concurrency can go toward 48 safely | further-optimization §4.4 ("measured fast") | never tested beyond 32 in production | **Open** |

## IV.3 Failure, incident, and near-miss ledger (living)

| # | When | What | Impact | Resolution / status |
|---|---|---|---|---|
| F-1 | 09-30→10-01 | Stray Kilo Code worktree (`.kilo/worktrees/spiky-door`) registered in the repo; unexplained design-doc edits found minutes before it | none (blob-identical); trust cost | removed, prune, exclude-file restored; owner states Kilo never used; **cause unexplained** |
| F-2 | day one → 10-07 | `owner.databaseId` invalid on `RepositoryOwner` → every hydration batch silently REST-fallback (2 calls/repo) | ~ignored for 5 days of dev runs; cost only dev tokens | fixed `bf2201d`; caught by reading run 1's bundle |
| F-3 | 10-06 | Planner appended duplicate `created:` (GitHub unions) → bisection never converged | runs 5–7 dead; run 7 burned 8h14m | fixed `d04bc34` |
| F-4 | 10-06 | Process restarts orphaned queued/running runs (no recovery) | runs 5–7 (`orphaned: process restarted`) | orphan recovery + resume shipped 10-02 batch 1 (`bfa6c42`, `2bc9216`) |
| F-5 | 10-08 | Discovery slot storm (10 limiter slots, 32 workers) | prescribed validation "finished" in 58 s with 176/192 shards dead | fixed `0eb1c33` (`bound_concurrency`) |
| F-6 | 10-02 | Non-session pytest ran against shared `gitcorpus_test` DB 12:03–12:06 | test interference; no corruption | runs repeated clean; cause unknown |
| F-7 | 10-08 21:02 | Run 18: 2× server latency night | timing comparisons invalidated for that night | recorded as a confound, not a bug |
| F-8 | 10-10 17:09 | **Run 24: C=32 hydration storm** | 159×403 in 8 s; cancelled at 26% | diagnosed (per-worker sleeps, siblings knocked); fixed by hardening §III.11 |
| F-9 | 10-10 ~15:59 | Soak's scratch script left C=32 in settings with no audit row | run 24 started from an unintended value | hardening + settings hygiene; this doc records the gap |
| F-10 | 10-10 17:56 | Run 25: wall absorbed, controller inert | 19×403; ~50% wasted; controller blind spot exposed | `note_secondary()` + pool pause shipped |
| F-11 | 10-10 18:08 | Run 26: 20 timeout-class responses (11–34 s) | cancelled in 2m20s; token edge unhealthy | warm-token cooldown guidance |
| F-12 | 10-10 18:59 | Run 27: 68×403 in synchronized waves | cancelled at 10 min | hardening targets exactly this |
| F-13 | 10-10 21:18 | Run 28: scraping flag surfaced in writing; 83×403 | near-miss — every batch recovered; run completed | hardening + 24 h rest guidance; near-miss recorded |
| F-14 | 10-02 → now | CI has never run (never pushed) | .github/workflows unverified against a live runner | open thread §IV.5 |
| F-15 | 10-11 | Docs drift in §11.6/§11.8 (403 counts, run 28 "cancelled", soak date label) | narrative documents disagree with primary data | corrected in Appendix B |
| F-16 | 10-04 | `quickstart.md` Step 5 deferred (thesis tracks) — recorded so it isn't mistaken for done | none | parked with FR-015–FR-022 |

## IV.4 Rulings and decisions that shaped the optimization history (index)

The exhaustive tables live in `docs/development-log.md` (frozen) and the plan files; this is the optimization-relevant digest.

| ID | One line |
|---|---|
| D4 | Live-only: no caches/watermarks/pollers (the recurring counter-idea stays parked) |
| D6 | Search drift is real; label it, don't hide it |
| D12 | Cost-ordered enrichment (record → mirror → single → batched → deep) |
| R23 | TEXT COPY + `ON_ERROR ignore` (PG18 bins binary) |
| R24/R57 → R58 | Quarantine → triage: wired what earned it, deleted the rest |
| R44 | `min_loc`/`max_loc` recorded-only, run flagged incomplete (estimator designed in `loc-dilemma.md`) |
| R52 | `field_stats` on the bundle is the provenance channel (timings + points live here now) |
| R55 | `run_items.repo_id` nullable + surrogate id, `ON DELETE SET NULL` |
| R58 | Death to dead code; git is the archive |
| E1 | The one approved visible change of the freeze contract (run counters) |
| Theme-2 fixes | Batch default 29 (later revised to 20 in practice); ceiling 32; window anchored to `x-ratelimit-reset`; throttles keep GitHub's message |
| Consolidated-review fixes | Lazy import (cycle); extend-only pauses; `max_attempts=1` pin; ceiling 32 not 48 |
| Run-modes idea | Sprint vs marathon; canary; fail-fast vs adapt — not built |

## IV.5 Open threads (living — refreshed 2026-10-11)

1. **Run modes (sprint/marathon)** — idea note dated 2026-10-11; the missing pieces are listed in the note itself (mode setting, sprint canary, fail-fast, reset-spanning pacer, auto-select from `total_count`).
2. **Repeat-run freshness** — 38,893/39,005 rows were byte-identical between runs minutes apart; a freshness window or ETag refresh would make repeats nearly free. Blocked on a deliberate product decision against D4.
3. **Adaptive-controller refinements** — lone-504 handling (require corroboration before a drop?), pacer whole-window vs burst, and whether `note_secondary` makes C≥24 viable on cool tokens. Default stays off.
4. **Cooldown policy** — §11.8 says rest 24 h after a scraping flag; runs 29/30 ran clean ~3 h later on a cooler token with hardened pacing. Which factor dominated is unknowable from the current data; the run-modes note is the vehicle to formalize it.
5. **DB write CPU** — apply times of 100 s+ on busy nights (runs 16, 17, 23) against 57–61 s on quiet ones; the ~50–90 s SQLAlchemy cost from the profile is partly addressed by batched apply but still visible.
6. **Shard-row hygiene** — the `shards` table carries 2,233 `pending` + 540 `incomplete` historical rows with no `run_id`; the startup sweep is a one-statement fix that would stop skewing `shard_coverage` (~0.55 on the dashboard).
7. **Warnings are bundle-only** — run history cannot re-render warnings once a bundle is gone (recorded since 2026-10-07).
8. **Telemetry minors** — count-batch audit rows record only the first probe; `plan_capped` can be true at exact fill; `mypy` does not gate `src/discover/`.
9. **CI first run + `pip-audit` blocking flip** — never observed; parse-validated only.
10. **LOC estimator** — the six-tier fallback architecture in `loc-dilemma.md` is designed, not built; `min_loc`/`max_loc` remain honest no-ops (R44).
11. **Detection** — the agent-use detection flow (FR-015–017, spec + 2,767-line plan) is parked reference, not built; its file channel is the same machinery as `has_dockerfile`.
12. **Multi-token scale-up** — documented preset; unused. The single-token practical ceiling at the settled point is two 39.5k runs per window.

---

# Synthesis: what the record teaches

Across three eras and 30 live runs, the methodology that actually produced results condensed to six behaviors. They are worth stating once, because they are the reusable part of this history:

1. **Measure before optimizing, and price the thing you're replacing.** Every accepted change in this record quotes the measured cost of the old behavior (the audit's S-numbers, the profile's 1,239.7 s, the 20-minute REST shard-and-fetch). No speculative rewrites.
2. **Write audits that can be wrong, then let production grade them.** The runtime audit projected 4.5–6 minutes and said, in its own climax, "stop at the first unexplained pushback." Production graded it: 9m08s. The falsification is recorded, not hidden — that's why the settled point is trustworthy.
3. **Verify the live path by reading its evidence, not its status codes.** Two of the most expensive defects in this history (`owner.databaseId`, the planner's appended `created:`) were invisible in every dashboard and metric. They were caught by opening a bundle and asking what the numbers *should* have been. (H-9.)
4. **One authority per timescale; pace, don't burst.** The starvation incident (client slot storm), the storms (synchronized worker waves), and the soak (sticky controller) are all the same failure: two mechanisms trying to govern the same resource. The settled architecture gives the hour to a pacer, the minute to a concurrency window, the request to a timeout guard, the pool to an atomic pause.
5. **Ship conservative defaults and promote by evidence.** The controller shipped off; batch 29 was tried and demoted to 20; concurrency walked 10 → 20 → 16 → 17 with a settings save between runs. Every promotion in this history has a run behind it.
6. **Reconcile the narrative against the primary data — on a schedule, in writing.** The errata in Appendix B exist because this document did exactly that. The rule that keeps a long-lived research project honest is not "never be wrong"; it is "when wrong, say where and fix the record." (This is the same discipline as the search-drift labeling and the R44 incomplete-flag: honest incompleteness beats confident wrongness.)

---

# Appendices

## Appendix A — Evidence sources and reproduction recipes

**A.1 The database (primary).** Everything in Parts II–IV can be regenerated. Connect with `DATABASE_URL` (project-local cluster on `localhost:5433`; see `../docs/environment.md`), set the session to UTC, and the key queries are:

```sql
-- the run register (IV.1.1 / §0.2)
SELECT id, status, created_at, started_at, finished_at, total_count, fetched,
       inserted, updated, unchanged, skipped, incomplete_shards, error,
       bundle_dir, filter_hash, filter_spec
FROM runs ORDER BY id;

-- per-run, per-phase audit statistics (§IV.1.3's sources; 403 counts etc.)
SELECT run_id, phase, count(*),
       count(*) FILTER (WHERE status = 200)                       AS ok,
       count(*) FILTER (WHERE status = 403)                       AS forbidden,
       count(*) FILTER (WHERE status IN (499,502,504))            AS timeouts,
       count(*) FILTER (WHERE retry_after IS NOT NULL)            AS retried,
       min(ts), max(ts)
FROM audit_log WHERE run_id IS NOT NULL GROUP BY run_id, phase ORDER BY 1, 2;

-- the settings history (the operating-point trail in §II.4.3 / §III.7)
SELECT ts, params->'app_settings'->'before' AS before,
       params->'app_settings'->'after'      AS after
FROM audit_log
WHERE run_id IS NULL AND params ? 'app_settings' ORDER BY ts;

-- the soak's rows (run_id NULL, phase set)
SELECT phase, count(*), count(*) FILTER (WHERE status=200) AS ok,
       count(*) FILTER (WHERE status IN (499,502,504)) AS timeouts
FROM audit_log WHERE run_id IS NULL AND phase IS NOT NULL GROUP BY 1;
```

Session note: `SET timezone = 'UTC'` before reading timestamps; the stored values are `timestamptz` and render in the session zone.

**A.2 Run bundles.** `runs/<filter_hash>/<run_id>/bundle.json` for runs 1, 2, 9, 10, 12, 16–19, 22, 23, 28–30; each bundle carries `ran_at`, `timings`, `field_stats` (per-field survivors, `calls_spent`, `graphql.hydration` with points), `points` (runs 28+), warnings, and the frozen `items`. `corpus.csv` carries the export columns. Runs without bundles (cancelled/failed: 5–8, 11, 13–15, 20, 21, 24–27) exist only in the DB and audit log — which is precisely why the audit-log attribution matters.

**A.3 Audit attribution rules** (so future readers are not misled):
- `audit_log.run_id`/`phase` are populated from commit `0539373` (2026-10-10 01:43 UTC) onward. Runs 24–30 are fully attributed; the soak has `phase` but `run_id = NULL` (scratch path); everything before that is unattributed and mixed in the legacy bucket.
- `rl_used` is GraphQL's **cumulative window usage** at response time, not per-request cost — never sum it. Per-run/per-phase point costs live in `field_stats.points` (runs 28+) and in the findings documents for earlier runs.
- `shards` has no `run_id` column — it is a cumulative table across all eras (states as of 2026-10-11: 4,205 done / 2,233 pending / 540 incomplete).

**A.4 Scratch and ops artifacts.**
- Adaptive soak: `%LOCALAPPDATA%\Temp\opencode\soak\` (`soak_run.py`, `soak_A_payload.json` 13.6 MB, `soak_A_summary.json`).
- Corpus-diff scripts: `%LOCALAPPDATA%\Temp\opencode\gc_corpus_delta.py`, `gc_corpus_diff.py`, `gc_corpus_diff2.py` (compare run 9's export with `repos_rust.csv`, 17,757 rows).
- Service logs: `%LOCALAPPDATA%\gitcorpus\pg.log`, `serve*.log`, `app.out.log`; `repos_rust.csv` sits in the repo root (gitignored corpus export).
- Review artifacts: `.superpowers/sdd/2026-10-09-adaptive-rate-controller/*.diff`.

**A.5 Git.** The commit index is Appendix C; the full history is `git log --all`; the environment documentation generated during the build is in `../docs/environment.md` and `../docs/development-log.md` (frozen). The granular per-commit dump used to build this document is reproducible with `git log --all --pretty=format:'%ad|%h|%s' --date=format:%Y-%m-%d`.

**A.6 Source documents by part.** Part I: `design/spec.md`, `design/plan.md`, `design/tasks.md`, `docs/superpowers/{specs,plans,prompts}/2026-10-01*`–`2026-10-02*`, `docs/development-log.md`. Part II: the 2026-10-02/03 plans and execution reports, `docs/findings/2026-10-08-hydration-profile.md`, `design/corpus-building-efficient-engineering.md` §9–§11, `design/further-optimization.md`. Part III: `design/runtime-audit-and-adaptive-control.md` (all), `docs/findings/2026-10-09-*.md`, `docs/superpowers/plans/2026-10-09-*.md`, `docs/superpowers/plans/2026-10-11-run-modes-idea.md`, `design/run-limits.md` §4–§5.

**A.7 Documentation map** (every tracked document, its era and role; "living" = still updated). This is the map of the whole footprint this methodology rests on — nothing in the repository is unaccounted for:

| Document | Era | Role |
|---|---|---|
| `README.md` | living | the public front door; one-paragraph version, journey, limits, routes |
| `design/spec.md`, `plan.md`, `tasks.md` | I | frozen objective, historical plan of record, phase/task status table |
| `design/research.md` | I | the D-numbered decisions (D4 live-only, D6 drift, D12 cost order, …) |
| `design/data-model.md` | I | entities, implemented/planned split |
| `design/contracts/search-api.md` | I | filter-spec v1 contract, virtuals table, error model |
| `design/quickstart.md` | I | golden-org validation procedure |
| `design/console-spec.md`, `console-plan.md`, `console-ux-redesign.md` | I | the console's design → execution → redesign record |
| `findings/00–06` + `README.md` | pre-I | the research the build is grounded in (parameters, gaps A-numbers, landscape) |
| `docs/legal-gates.md` | I | API-only, robots, PII, trademark gates |
| `docs/environment.md` | living | services, env vars, runbooks, corpus profile, secondary-limit guidance |
| `docs/development-log.md` | **frozen 2026-10-09** | R1–R58 rulings, per-task commits, session records |
| `docs/findings/2026-10-08-hydration-profile.md` | II | discovery validation + hydration profile (the concurrency evidence) |
| `docs/findings/2026-10-09-transport-pipeline-efficiency.md` | III | Theme 1 verification (measured 10-10) |
| `docs/findings/2026-10-09-adaptive-soak.md` | III | the soak watch table + keep-off decision (measured 10-10) |
| `design/corpus-building-efficient-engineering.md` | I–II | meters, touches rule, sharding, batching engine, §9.4 spike ledger |
| `design/how-the-data-flows.md` | I | the stage-by-stage narrative |
| `design/run-limits.md` | II–III | the nine dials, presets, settled point |
| `design/further-optimization.md` | II–III | ranked next moves after the discovery engine |
| `design/runtime-audit-and-adaptive-control.md` | III | the audit + §11 production log (read with Appendix B here) |
| `design/loc-dilemma.md` | I+ | why `min_loc` is recorded-only; the six-tier estimator design |
| `design/adoption-window.md` | I+ | thesis framing (cutoff robustness, cohorts, detector floor) |
| `design/landscape-comparison.md`, `gitcorpus-vs-seart.md` | I | why build rather than adopt |
| `docs/superpowers/{specs,plans,prompts}/*` | I–III | every design spec, implementation plan, overnight queue and execution report |
| `design/methodology.md` (this file) | living | the consolidated history you are reading |

## Appendix B — Errata and corrections to earlier narrative documents

Recorded 2026-10-11 during this document's construction. Corrections are made against primary machine data; each row states the claim, the evidence, and what this document uses instead. The earlier documents are *not* edited here (they are historical; `b5ea869` already synced their banners), but future readers should weight this appendix above them where they collide.

| # | Claim (source) | Primary evidence | Correction used here |
|---|---|---|---|
| B-1 | Run 27: "48× 403 in synchronized waves" (`runtime-audit…md` §11.6 scoreboard) | `audit_log`: 68 rows, `status=403`, `phase=hydration`, all with `retry_after=60` (17:01…19:08 UTC) | **68× 403** |
| B-2 | Run 28: "48× 403; recovered; cancelled at ~50%" (§11.6) | `runs` row: `status done`, finished 21:34:10 UTC; bundle: `incomplete:false`, 18,213 items, `warnings: []`; audit: 83× 403 + 1,579× 200 (= exactly 39,464 ÷ 25) | Run 28 **completed (100%)** with **83× 403**, every batch recovered on retry |
| B-3 | Run 28: "A three-request hydration probe … tripped it immediately" (§11.8) | No audit rows exist for any three-request hydration probe; run 28's hydration carried 1,662 request rows (1,579 ok + 83×403) | The sentence most plausibly describes an **unrecorded manual probe** (e.g., raw HTTP) used to capture the flag's wording; no audit record exists, and this document labels it as such |
| B-4 | Run 19: "B=20, C=20" (§11.6 scoreboard) | Settings audit: concurrency 16 → 17 saved 10-08 19:42:10 UTC; next change 10-09 11:47:36 UTC. Run 19 submitted 10-08 21:50. | Run 19 ran at **C=17** (batch 20). The 2,916-point figure stands |
| B-5 | The soak dated "10-09" (§11.6 row; findings filename `2026-10-09-adaptive-soak.md`) | `soak_A_summary.json`: started 2026-10-10T15:59:03Z, ended 16:19:57Z; audit window 15:59:04–16:19:52 UTC | Soak executed **2026-10-10 15:59–16:20 UTC**; the file is named for its plan date (convention, not error) |
| B-6 | Scoreboard omits run 26 (§11.6) | `runs` row 26: cancelled, 140 s, 20 timeout-class responses in hydration (11–34 s latencies) | Run 26 is listed in §IV.1.1 and §III.9 |
| B-7 | §11.8: "tonight's five runs had already collected 159 / 19 / 48 / 41 / 48 secondary hits" | Audit: run 24 = 159; 25 = 19; 26 = 0; 27 = 68; 28 = 83 | The 48/41/48 sequence could not be reconciled with any per-run audit count; the authoritative per-run counts are in §IV.1.1 |
| B-8 | "two corpora ~12 h apart differ by 49 added / 11 removed / net 38" (`development-log` findings note) | `repos_rust.csv` has 17,757 rows; run 9 exported 17,795; net = 38; the diff scripts in the temp directory implement exactly this comparison | Consistent; net 38 confirmed, and the compared pair is (run 9 export) vs (`repos_rust.csv`) |

*Convention note:* some source documents write local (+03:00) times that can make a late-night run appear on the "next day" (run 28 "10-11 00:18" local = 10-10 21:18 UTC). Both are correct; this document always uses UTC and says so.

## Appendix C — Complete commit index (all 284 commits, oldest first by day)

Every commit reachable from `main` (branch `quality-hardening` is an ancestor — the history is linear). Day boundaries are author dates in the operator's local zone (+03:00). Full diffs: `git show <sha>`.

### 2026-09-30 — 10 commits

- `717c9b3` docs: import gitcorpus research + frozen v2 design (live-only freshness, thesis tracks parked)
- `8947d1a` T000: walking skeleton (validate -> live search -> display -> bundle + CSV)
- `14ec36c` T001: project structure (src packages, tests tiers, docs) + docker-compose (Postgres 17, Redis 7)
- `f8cd570` T002: pinned deps + shared GitHub client (env-only tokens, header defaults, fingerprint logging helper)
- `8174d2f` T003: ruff + black config and pytest layout (zero findings; T000 skeleton.py exempt per constraint)
- `9097849` T004: legal gates checklist (API-only, robots record, token log template, resale/PII, trademark, GDPR)
- `6ae3c32` T005: per-bucket Redis limiter + delayed retry queue
- `01cfdc3` T006: throttle classifier (retry/reset/backoff/422 triage/SSO loud-fail)
- `f583db8` T007: q qualifier allowlist + delta-test validation
- `784117b` T006/T007: fix review findings (422 attempt-5 escalation, props org scope, test rename)

### 2026-10-01 — 87 commits

- `341021a` docs: environment provisioning record + durable development log (WSL Redis, local PG18 cluster, env vars)
- `9e72dfe` docs: log stray Kilo Code worktree removal and .git/info/exclude cleanup
- `dcba8e4` T008: SQLAlchemy models + initial Alembic migration
- `663196f` T009: audit record + SLO snapshot
- `0d777d7` T010: pagination contract test (red)
- `592358c` T012: shard planner
- `c94d572` T013: shard state machine + queue + within-run ordering
- `7289076` T014: sharded search discovery
- `db5f69f` T014: fix review findings (slot release + retry cap)
- `e26c300` T015: since cursor scan + id-range sharding + checkpoint
- `e1ea196` T016: org/user enumeration
- `a5733cc` T017: batched upserts + COPY bootstrap
- `33182f0` T015/T017: fix review findings (array envelope, bootstrap stats, history)
- `6d53778` T011: golden-org parity integration test (red)
- `9f0488d` T018: discovery pipeline wiring + audit logging
- `a0d3b92` docs: post-US1 status, COPY R23 plan amendment, development log
- `f64bd69` US1: final-review fixes (SSO loud-fail, dirty payloads, bootstrap rename/staging, ordering key, delta probe)
- `50af6dd` docs: final-review outcome, R24 unwired-modules note, residual minors
- `a98eabd` docs: US4 console spec + plan, v3 amendment, overnight-run ledger (R26-R31)
- `633daac` T019: within-run dedupe helper + watermark tests
- `0fb6aeb` T020: lifecycle integration tests (red)
- `ab47224` T022: hydrate repo client (ETag, manual 301 follow, 404)
- `a269048` T023: lifecycle handler (rename history, tombstones, purge)
- `8ce4241` T021: within-run refresh driver + throttled-continue test
- `05cdc65` T026: trees-first equivalence tests (red)
- `93050cb` T028: trees-first enrichment (recursive tree + ecosyste.ms metafiles)
- `9a53bcf` T029: GraphQL batch (funding/discussions/sponsors) + gh_client json/header kwargs
- `3f1c9ed` T027: geo resolver fixture tests (red)
- `c464e2a` T030: geo resolver (flag/gazetteer/aliases/geocoder/weak tiers + GeoCache)
- `983d88a` T031: zero-auth third-party mirror fetchers (ecosyste.ms, deps.dev, Scorecard)
- `0d96b44` T030: fix review findings (non-finite tz, NFC, cache None, tz bands)
- `172c1b3` T030: fix tz bands + float overflow (round 2)
- `afd5e61` T052: console persistence models + migration 0003
- `8bae1f8` T053: single-worker run executor (lifecycle, snapshots, bundles)
- `dd75f80` T053: fix submit race (single worker)
- `39e6d74` T025: contract tests for filter-spec + virtual translation (red)
- `89144ea` T033: filter-spec v1 validation + virtual translation
- `efe3cb7` T032: serve app + production runner (bounded discovery, post-filters, cache/replay)
- `847f283` T032: fix review findings (incomplete propagation, sort, truncation, POST errors, SSO tolerance)
- `85c747d` T034: run export endpoint (exact bundle bytes, regeneration, 400/404)
- `93420c8` T056: UI shell + dashboard (templates, hand-rolled CSS, vendored htmx, health, CSRF)
- `ba9ac06` T034/T056: fix review follow-ups (db-down dashboard, regeneration marker, csrf scope)
- `838cc19` T056: allow csrf via form field (no-JS forms)
- `a367f6e` T035: filter form at /find with run page and replay (R48-R50)
- `8343ba3` T035: fix run banner hash
- `8386868` T036: cost-ordered filter planner (D12 priority table, page/full depth)
- `b31913a` T037: segment executor + runner wiring (R51, R52)
- `abe9ec8` T037: surface dropped segments, dedupe field sources, regen field_stats
- `3895883` T051: optional clone control (estimate, background clone, resumable progress)
- `f052827` T054: saved-filter library (validated CRUD) + JSON endpoints
- `994d294` T055: run-to-run diff (added/removed/changed) + JSON endpoint
- `013635b` T057: run detail UI (polling status, sortable/paginated table, flags, export/replay, clone modal)
- `d4b41c4` docs: R54 clone route naming in console spec
- `dc15845` T058: history/diff/library pages, keyboard-first nav, dark mode
- `3c8e440` T059: polish pass (loading indicators, a11y, running-the-app docs)
- `870c288` T058: fix diff empty-against, inline-handler injection, table loading
- `918339e` final-fix: address final review wave (C1, I1, I2, A1-1, A1-2, R57, minors)
- `17df228` docs: console build run completion record (US2+US3+US4), rulings R32-R57, residuals
- `bf60ced` docs: efficiency audit report and implementation plans
- `9076037` perf: linear repo_id accumulation in discovery
- `b18233d` perf: chunk candidate and etag IN queries
- `9878088` perf: lazily plan shards and reuse the root count
- `6023b10` perf: constant-time pending queue and Redis field lookup
- `54f1ee4` perf: atomic shard transitions and memoized stream groups
- `f6e885c` perf: single-write hydration with etag and idempotent history
- `a3e15d2` perf: index and batch tombstone purges
- `6968768` perf: reuse one bootstrap staging table and tokenize login collisions
- `771735e` perf: retry transport errors and avoid decoding full error bodies
- `d4ff586` perf: O(1) literal path matching in tree presence
- `5983718` perf: batch geo cache reads/writes and memoize resolved locations
- `203c9de` perf: keep successful GraphQL split results and shrink count queries
- `c47285a` perf: bounded clone concurrency, timeouts, and capped error lists
- `6ca61be` perf: single-pass segment bucketing with deque work queue
- `42c432d` perf: bounded single-flight payload cache
- `1039762` perf: interactive lane and future pruning in run executor
- `a56ec6a` perf: lock idle event against enqueue and worker interleaving
- `3fbbd8e` perf: single run lookup/count, aggregate clone estimate, cached health
- `d903ae1` perf: align run_items index with NULLS LAST sort and cap diff candidates
- `3c6283e` perf: stream exports in constant memory and make diff NULL-safe
- `2628e2f` perf: batch audit inserts, parse bodies once, unblock the event loop
- `8bc8bec` perf: cap and throttle clone progress persistence and rendering
- `f3e7206` perf: pause htmx polling while the tab is hidden
- `912d73d` perf: cache static assets and move progress animation off layout
- `5899c55` perf: cache row navigation and guard duplicate clone starts
- `58fbc7a` perf: bound transport retry backoff to 15s and fail loud at 3 attempts
- `c6cb2df` perf: document migration locking and audit post-implementation status
- `8e37d11` docs: add quality-hardening spec and plans

### 2026-10-02 — 93 commits

- `b401fd3` style: apply black formatting to drifted files
- `2205dbf` ci: add two-OS workflow and fail-not-skip database guard
- `f1e1897` test: add deterministic endpoint golden harness
- `4a4ff05` test: pin the OpenAPI schema hash
- `5a5d947` ci: enforce a 93% coverage floor and record the baseline
- `9ae1630` ci: add advisory pip-audit dependency report
- `00692a0` fix: keep GitHub token off the metafiles host
- `def016b` fix: serialize lazy serve singleton construction
- `d79eb49` fix: atomic clone claim and bounded clone registry
- `86a5def` fix: roll back and retry failed discovery shards
- `ebc5822` fix: isolate dirty rows from chunked repo upserts
- `9109948` fix: surface incomplete GraphQL sub-batches
- `968cbf1` fix: chunk geo cache bulk writes
- `d894460` fix: persist runner upsert counters in run summaries (E1)
- `a36339c` style: apply black formatting after phase 1a
- `187087d` test: centralize duplicated DB clean/seed fixtures
- `1d0c1ea` test: make test paths independent of the launch directory
- `616e6d6` test: replace wall-clock flake assertions with deterministic synchronization
- `062b4fb` test: extract and cover app.js pure helpers
- `38d3e94` test: add quarantine manifest and tested skeleton entrypoint
- `4046712` types: add scoped mypy baseline and fix annotation defects
- `753d633` refactor: move audit to lib and enforce import boundaries
- `8f911e9` docs: record quality-hardening program entry points and gates
- `01254bc` hardening: reject cross-origin state-changing requests
- `804a6a6` hardening: allowlist loopback Host headers
- `0eabc08` hardening: cap JSON and upload request bodies
- `1366979` hardening: add deadline policy and bound limiter waits
- `61afc42` hardening: bound executor and payload-cache waits with 503
- `841e7a8` hardening: clone timeout, terminal-safe git, cancellation
- `3396637` hardening: fail loud on degraded redis
- `739788e` hardening: single-flight health probe
- `321cee4` hardening: tolerate malformed progress, digits, and shard timestamps
- `304c2bc` ux: show busy feedback for htmx fragments and native navigation
- `753a195` ux: surface structured clone errors with retry and dismiss
- `d62c082` ux: add localStorage recent filters quick-pick
- `a896938` ux: guide empty states with one-click example queries
- `4c5a7cd` ux: expose the keyboard help panel with a header button
- `ac5923f` ux: copy the current run link to the clipboard
- `c17ffb9` ux: expose clone cancellation in the progress panel
- `df98909` ux: trap and restore focus in dialogs
- `8f35eff` ux: pin the run table header and show the visible row count
- `94a81e2` docs: document hardening operations and correct fixture count
- `9f32d58` docs: add quality-hardening execution report
- `e57705a` chore: ignore operator-only overnight queue prompt
- `bde48de` docs: add queued execution plans
- `35dbd5a` docs: ruling R58 triages the unwired surface
- `225d169` fix: reclaim stale shard deliveries before claiming
- `c8e89c3` test: isolate reclaim wiring test with schema fixture
- `5fafdca` chore: delete superseded unwired surfaces (R58)
- `7951b7e` fix: lazy-init lock, sanitized run errors, migration downgrade note
- `6107be7` docs: log Phase 1 unwired-debt triage outcome
- `acb427f` feat: computed run quality report
- `8649b96` feat: run quality panel and JSON route
- `e40f4d4` docs: log Phase 2 QA reconciliation outcome
- `bfa6c42` fix: recover runs orphaned by a process restart
- `2bc9216` feat: resume failed find runs from the stored filter spec
- `7f68e73` test: isolate serve main tests from startup recovery
- `aaac0eb` fix: assert resume reset and offload route db work
- `c668b5b` feat: resume detect runs, console button, and crash runbook
- `a2625be` docs: log Phase 3 run resume outcome
- `e8928c9` feat: ops metrics payload
- `9c43d82` fix: degrade metrics on malformed rl keys and pel errors
- `a045ffe` feat: SLO dashboard page, partial, and JSON API
- `be0d216` test: verify queue PEL wiring in the metrics payload
- `8560611` docs: log Phase 4 SLO dashboard outcome
- `8de9bb5` fix: harden quality bundle and metrics degradation paths
- `e21143e` docs: correct sanitizer/metrics guarantees and manifest
- `2087348` docs: add overnight queue execution report
- `d278b72` docs: add corpus engineering and tool landscape design set
- `22be08b` docs: add graphql batch engine and console settings plans
- `4fb3058` fix: unblock CI on postgres 17 and linux golden headers
- `440fcd8` docs: add console ux redesign design doc
- `04b58cb` docs: add console ux redesign implementation plan
- `3b5aa74` docs: align settings plan with the ux redesign
- `652d3b9` chore: ignore operator-only overnight queue prompt
- `488323d` docs: add export fix, clone copy, aria-current, and props gating to ux plan
- `ef8f647` docs: add min/max commits and greyed unavailable filters to the queue
- `0e28c40` feat: graphql rate bucket and resource mapping
- `726dca4` feat: generic graphql batch core with per-repo attribution
- `2bbf414` feat: graphql batch failure isolation and bounded retries
- `4772ad2` feat: graphql repo details adapter
- `1f88abc` feat: batched hydration with rest fallback and outcome reporting
- `839025d` feat: batched file presence checks with tree fallback
- `e88c917` fix: count each skipped repo once in the dockerfile report
- `16e20f1` feat: batched owner location lookups with rest fallback
- `4c2976a` fix: persist confirmed no-location owners as unmatched
- `f705ff8` fix: count raising owner fallbacks against the geo budget
- `e15cbc3` feat: enforce min/max commits from batched commit counts
- `a19f5c1` fix: keep a hydrated repo when its commit count fetch fails
- `eaf2a3d` docs: log the graphql batch engine outcome
- `1cc4d35` migration: add single-row app settings table
- `23742fd` feat: settings form validation
- `03706de` feat: settings page, audit trail, and navigation

### 2026-10-03 — 21 commits

- `7b4e72d` feat: apply persisted settings to new runs
- `74a33b3` test: cover record_settings_change directly
- `c373ce3` docs: settings page, corpus profile, and outcome
- `ac7f225` feat: console shell, plain-language naming, and error pages
- `e250745` feat: system page and header status dot
- `db565ef` fix: keep the system page usable when metrics are unavailable
- `db0e27f` feat: new search page with common/advanced split and match check
- `4efe837` fix: keep unavailable loc filters and country confidence in the search round-trip
- `61f8b62` feat: full-width results page with page-size selector
- `c141eaf` feat: readable search workspace with explained counts
- `90a9920` feat: corpora freezing, list, and detail pages
- `4956ba9` feat: library run-now and readable saved-filter rows
- `dbf793a` docs: log the console ux redesign outcome
- `c9a87dd` fix: align console copy and counters with the reviewed behavior
- `b0c7110` docs: add overnight queue execution report
- `c919c40` feat: polish console styling and drop the dashboard quick find
- `13a700f` fix: keep action cells in table layout
- `21fe78e` style: format the action-cell regression test
- `b7ce68c` feat: show setting limits and add a maximum preset
- `3eae46c` docs: add README with project overview and installation guide
- `5742e93` docs: rewrite README in the project's explanatory voice

### 2026-10-04 — 1 commit

- `fd8892e` docs: humanize findings and design docs, fix cross-doc inconsistencies

### 2026-10-07 — 9 commits

- `d04bc34` fix(discovery): plan inside created bounds and stop stranding shards
- `bf2201d` fix(hydration): valid owner selection and parallel batched GraphQL
- `f55dc26` feat(runs): abort, live progress, ETA, and save filter
- `dc9cc67` fix(runner): honest partials and scale hardening
- `c99ee13` chore(console): corpus preset, filter copy, and design notes
- `4706513` docs(readme): sync with planner, hydration, and run-controls changes
- `4d979df` docs(design): update behavior, limits, and API contracts for this session
- `c0b0619` docs(findings): record live-verified GitHub API behavior
- `78e766b` docs(dev-log): log the planner, hydration, and run-controls session

### 2026-10-08 — 30 commits

- `76899fb` docs(design): graphql discovery measurement, spec, and implementation plan
- `a9c1e46` refactor(lib): move RequestFailed/short_message/next_link to gh_client
- `99e20f6` feat(discover): graphql search client for batched counts and parallel pages
- `b1ab600` fix(discover): use unquoted graphql after argument
- `021218e` feat(scheduler): level-batched graphql shard planner
- `6d9437d` fix(scheduler): keep ShardPlanner until pipeline rewires
- `7b4ca68` feat(settings): discovery_concurrency (default 32) with migration 0012
- `b3cbb70` feat(discover): graphql discovery engine with parallel shard executor
- `c9700e0` fix(discover): keep deadlines graceful and drop dead planner constant
- `c1b7350` refactor(discover): delete redis shard queue and REST search paging
- `dd696de` feat(serve): record graphql totals in audit and surface graphql remaining
- `61121c2` fix(serve): parse graphql audit bodies once and harden total-count fallback
- `6c35610` docs: sync discovery docs with the graphql engine
- `55a8bbd` docs: fix rest-meter attribution and point wording
- `52b6380` feat(discover): halve page size on graphql query timeouts
- `ce2e38c` fix(discover): lean page fields and resume past malformed responses
- `9942cb0` docs(findings): graphql discovery validation and hydration profile
- `0eb1c33` fix(limiter): bind discovery slots to discovery_concurrency
- `d34a2be` fix(discover): final review wave — 5xx policy, fork/visibility, bounds, docs
- `6c7eb04` perf(hydrate): batch DB apply, stage timings, cancellable sleeps, http-date Retry-After, corpus concurrency 20
- `f666af0` feat(hydrate): stream apply progress per chunk and label the saving phase
- `cdac8f4` perf(discover): dispatch independent shard-planning probe batches concurrently
- `0d232a2` perf(hydrate): overlap batched DB apply with in-flight GraphQL fetches
- `2d6a3cb` feat(settings): raise the GraphQL batch-size cap to 50 (default stays 20)
- `7cfc5f2` fix(settings): keep the batch-size default at 20 after raising the cap
- `589663a` feat(graphql): split 502/504 batch timeouts before per-repo REST fallback
- `14dab90` chore(migrations): update head references to 0013
- `d41e8cc` style(hydrate): wrap the adapter signature after the default rename
- `ef807aa` feat(dev): add start/restart bash launchers for the local stack
- `43fc69a` perf(discover): fold page upserts outside the worker lock

### 2026-10-10 — 27 commits

- `d8c4163` perf(graphql): parallelize REST fallbacks on a bounded worker pool
- `1a4baec` docs(environment): note battery power settings for the auto-start tasks
- `09f352c` perf(lib): pin httpx pool limits and ignore environment proxies
- `039e956` perf(lib): reuse the audit-cached graphql body in fetch_batch
- `d176e83` perf(discover): buffer per-worker upserts on page/item thresholds
- `6ead5cb` fix(discover): keep the deadline flush best-effort so the shard pauses cleanly
- `b721719` perf(audit): write audit batches on a bounded writer thread
- `330264e` docs(findings): transport and pipeline efficiency measurements
- `980abe6` fix(discover): reset the page counter on an empty buffered flush
- `e120283` docs(findings): correct the measurement date and the audit loss bound
- `5444e32` feat(settings): batch default 29, audit point-telemetry columns (migration 0014)
- `7bbc923` feat(telemetry): parse GraphQL rateLimit cost/used/remaining into BatchStats
- `1d91f20` test(hydrate): align batched-request expectations with the batch default 29
- `b03dcbd` feat(audit): rl_used/run_id/phase columns and per-phase PointsLedger
- `0539373` feat(telemetry): run_id/phase audit attribution and per-phase points in field_stats
- `f633ce0` feat(runner): hydration concurrency ceiling 32 and corpus preset 32
- `78c1f7e` fix(limiter): anchor the window to x-ratelimit-reset and use the header limit
- `4435932` fix(graphql): keep GitHub error messages and pause the bucket on 200-body rate limits
- `439b35c` test(gh-client): align deny-loop retry expectations with the reset-anchored window
- `530213c` docs: sync quota utilization and limiter correctness changes
- `4d52808` feat(telemetry): request and parse rateLimit on the enrich adapters
- `088a4f9` feat(limiter): adaptive rate controller core (aimd window, batch guard, pacer, pool pause)
- `5a888bd` feat(graphql): adaptive live gate, batch guard, reserve deferral, pool pause
- `65d0b4c` feat(runner): env-gated adaptive hydration wiring and telemetry
- `6469a9a` docs(findings): adaptive controller soak validation
- `cb8a674` docs(design): runtime audit, adaptive-control plan set, and consolidated review
- `6dbb759` feat(settings): adaptive controller toggle on the settings page (default off)

### 2026-10-11 — 6 commits

- `1aa6fa8` docs(design): production log for the 2026-10-10 walls
- `a723844` feat(limiter): pool-wide secondary-limit pause, escalation, and run budget
- `4620fb0` fix(limiter): make the secondary budget stop stick and wire jitter in production
- `23e9ab7` docs(environment): correct the secondary jitter wording
- `b5ea869` docs(design): sync the design docs with the run 29/30 records and the settled operating point
- `6d15587` docs(plans): sprint vs marathon run-modes idea note

## Appendix D — Glossary (the terms this document leans on)

- **Audit row** — one `audit_log` record per GitHub response (params, status, rate-limit headers, `retry_after`, latency, and — since migration `0014` — `rl_used`/`run_id`/`phase`). The timeline evidence for every wall story.
- **AIMD** — additively increase, multiplicatively decrease; the concurrency window's control law in the adaptive controller.
- **Batch / alias batch** — one GraphQL call carrying N repos, one alias per repo (default 20; 29 is the largest 1-point batch).
- **Batch guard** — the controller's per-batch size knob (10–29; ×0.7 on a bad signal).
- **Corpus** — a frozen, named snapshot of a finished search (3 exist: runs 1, 2, 9).
- **Discovery concurrency** — parallel search-page fetches, one GraphQL connection each (32 default and measured optimum).
- **Drop** — any pushback signal (403/429, 502/504 timeout, or rate-limit error inside a 200 body).
- **Filter hash** — SHA-256 of the canonical filter spec; identifies runs and bundles.
- **Hydration** — fetching a repo's full current record; not cloning. The dominant cost center of every full run.
- **Meter** — a per-identity allowance (`search` 30/min, `core` 5,000/hr, `graphql` 5,000 points/hr). Limits belong to the account, not the token.
- **Point** — GraphQL's cost unit; `round(connections ÷ 100)`, minimum 1 per query.
- **Pool-wide pause** — stopping every worker on a 403/429 (Redis `pause_at_least`, extend-only) so siblings stop knocking.
- **Quota pacer** — the controller's hourly loop: spend `(remaining − reserve) ÷ seconds-to-reset` points per second.
- **Run bundle** — the persisted artifact of a run: filter, `ran_at`, timings, `field_stats` (including points), warnings, items.
- **Scraping flag** — GitHub's anti-scraping 403 (`retry-after: 60`, no rate-limit headers, "scraping…" body); sensitivity escalates with repeats and decays slowly (rest ≥ 24 h per the runbook; production recovered in ~3 h with hardened pacing — §III.13, §IV.5).
- **Secondary limits** — GitHub's anti-abuse ceilings (100 concurrent shared REST+GraphQL; 900/2,000 points/min) that sit behind the primary meters.
- **Settled operating point** — batch 20, concurrency 17–20 (16 after a storm), discovery 32, adaptive off; two 39.5k runs per hourly window.
- **Shard** — a date-sliced sub-query kept under the 1,000-result cap.
- **Stage timings** — per-phase wall clocks persisted in every bundle since `6c7eb04` (count / discovery / hydration fetch+apply / enrich / snapshot).
- **Touch** — one metered contact with one repo (the mother document's word; hydration is one touch per batch now, not per repo).

## Appendix E — How to update this document

Copy the patterns; keep the discipline.

**E.1 A new live run** — add a row to §IV.1.1 with: run id, UTC start, filter short-name, B/C as actually in force at submit (check the settings audit first — do not assume), found/fetched/items, elapsed, status, and one line of notes. If the bundle exists, add its stage timings to §IV.1.3. If it was a scratch run, add §IV.1.2 instead.

**E.2 A new optimization** — write the section as: *the observed problem with its measured cost → where the idea came from → exactly what shipped (with SHAs) → how it was tested (gates, measurements, runs) → verdict → next improvement point*. Then add/refresh a hypothesis row (H-n) and any failure rows.

**E.3 A new era** — open a new `# Part` with a one-paragraph framing that names the question the era is trying to answer. Never merge eras; append.

**E.4 When a number turns out wrong** — add an Appendix B row (claim → primary evidence → correction used). Do not silently edit the old sentence; if the collision is inside this document, add a dated "Update" line.

**E.5 Refresh the quiet parts** — §IV.5 open threads and §0.3's state table are the two places that go stale fastest; refresh them whenever a run or a merge lands.

**E.6 The standing rule** — if a claim cannot be traced to a run id, a commit, a bundle, or a named file, it does not belong in this document except as an explicitly labeled reconstruction.

---

*End of the 2026-10-11 edition. The next entry starts where this one ends: whatever happens after run 30.*




