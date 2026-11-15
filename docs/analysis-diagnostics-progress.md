# Analysis diagnostics progress log

This is the chronological execution record for [`analysis-diagnostics-plan.md`](analysis-diagnostics-plan.md).

## 2026-11-10 — scope and definitions locked

- Kept the twelve existing headline measures.
- Locked six additional diagnostics: evidence robustness, coverage, owner clustering, robust debuts, intensity distributions, and multi-agent co-use.
- Locked repository bands to `1`, `2–5`, `6–9`, `10+`.
- Locked owner bands to `1`, `2`, `3`, `4–6`, `7–9`, `10+`.
- Locked separate GitHub `User` and `Organization` reporting.
- Locked owner agent sets to the union across every repository owned in the frozen detection run.
- Locked exact-set ranking to count descending with deterministic lexical tie-breaking.
- Confirmed the existing report/dashboard recompute all requested measures independently and have no persisted shared analysis payload.
- Confirmed the dashboard calls the full analysis context again, explaining why navigating from tables to dashboard repeats the expensive work.
- Confirmed development constraints: targeted tests only until one final full-suite run; no Playwright or MCP tooling.

### Next

1. Map detection #29 to its database run id and capture per-measure baseline timings.
2. Implement and unit-test pure statistical primitives and diagnostic estimands.
3. Add the versioned snapshot and invalidation lifecycle.
4. Add report/dashboard projections and visuals only after logic tests pass.

## 2026-11-10 — logic, persistence, and visuals implemented

### Baseline and bottleneck findings

- Mapped detection #29 to database run `101`: 17,757 repository rows, 3,036,007 evidence rows, and 53,602 compact evidence facets.
- Timed every prior measure independently. The six-channel fingerprint path took 15.038 s; creation cohort 6.751 s; star tiers 4.370 s; commit depth 6.162 s; language 6.123 s. All other headline queries together were under one second.
- Confirmed that the report and dashboard each repeated the full computation.
- Replaced repeated cohort/star/commit/language evidence scans with one immutable `AnalysisDataset` load and in-memory deterministic aggregation.
- Added SQL top-k ranking inside fingerprint aggregation, reducing that path from 15.038 s to 4.408 s while preserving the same top-five-per-agent result.
- Measured the committed-file evidence predicate with `EXPLAIN (ANALYZE, BUFFERS)`: 2.786 s and ~15,200 pages read. Added the narrow partial index `de_run_committed_file_repo_idx`; the same query became an index-only scan in 21.6 ms.

### Statistical implementation

- Added explicit frozen-run population states: scanned, readable, complete-channel eligible, successful file observation, valid history denominator, observed history coverage, and full-history coverage.
- Implemented D1 evidence definitions with a common eligible denominator and evidence/document reconciliation counters.
- Implemented D2 coverage matrices for country, language, star tier, and commit tier; unselected channels return `not_applicable` rather than zero.
- Implemented D3 separate User/Organization owner estimates, owner concentration, repositories per owner, and deterministic 1,000-replicate owner-cluster bootstrap intervals.
- Implemented D4 nearest-rank P0/P10/P50 observed dates and dated-evidence Wilson coverage.
- Implemented D5 conditional P25/P50/P75/P90, zero-recent-use and pervasive rates, exact stratum summaries, and selectable ECDF projections.
- Implemented D6 repository bands and owner-wide canonical agent unions. Exact-set rankings reconcile to every band and use count-descending/lexical tie order.
- Expanded M8 with tied-rank Spearman rho, percentage-point slope per GDP doubling, 2,000-replicate deterministic country bootstrap intervals, leave-one-country-out ranges, Cook's distance, and minimum-country rules.

### Cache and invalidation

- Added `analysis_snapshots` in migration 0021, separate from `runs` so normal run reads never deserialize the analysis payload.
- Snapshot validity binds to an explicit analysis schema version and the run's `finished_at` timestamp.
- Added one-build-per-run locking to prevent concurrent cold-request stampedes.
- Report metric selections and the dashboard now project from the same complete payload.
- Run reset/resume and owner-country synchronization invalidate snapshots.
- Successful/partial detection completion precomputes a snapshot; cache failure is logged but can never change valid detection evidence into a failed run.

### Final run #29 measurements

- Completed cold snapshot build: **20.725 s** (one time, normally performed when detection finishes).
- Persisted JSONB payload: **165,487 bytes** in PostgreSQL.
- Warm authoritative analysis payload lookup: approximately **20 ms** in direct profiling.
- End-to-end local TestClient routes after caching:
  - Data tables: 0.310 s first template render, then **0.070 s**.
  - Visual dashboard: 0.081 s first render, then **0.048 s**.
- This removes the former 1–2 minute report wait and the second 0.5–1 minute dashboard recomputation for detection #29.

### Interface and documentation

- Added exact no-JavaScript report tables for all six diagnostics and the expanded wealth analysis.
- Added paired evidence sensitivity, coverage matrix, clustered owner comparison, percentile debut timeline, selectable intensity ECDF, and combined repository/owner co-use visual panels.
- Updated the methodology proposal to v1.4 while retaining exactly twelve headline measures and adding D1–D6 as validity diagnostics rather than headline inflation.

### Targeted verification completed so far

- Pure diagnostic/statistical unit tests: green.
- Frozen-run integration estimands and exact owner-set reconciliation: green.
- Snapshot hit/version/finished-time/invalidation/concurrent-stampede tests: green.
- Detection completion precompute and reset invalidation tests: green.
- Analysis report/dashboard contract tests: green.
- Migration/model tests through head 0022: green.
- JavaScript syntax check and targeted Ruff checks: green.

### Remaining final gates

1. Run the UI mechanical detector once and address actionable findings.
2. Regenerate and verify affected golden snapshots.
3. Run final targeted formatting/static checks.
4. Run the complete test suite exactly once.

## 2026-11-10 — final gate complete

- Mechanical UI detector run completed once. It found no dashboard/report findings; the proposal-only warnings were reviewed, with timeline padding and repetitive table copy corrected. Its print-oriented `pt` headings were retained because the oversized-heading warning interpreted print points as screen pixels.
- Affected golden route snapshots were regenerated and then verified clean. The intentional analysis-dashboard route contract is pinned by the updated OpenAPI digest.
- Final Ruff, Black, JavaScript syntax, JavaScript unit, HTML structure, Alembic-head, and targeted Python checks all passed.
- The complete test suite was run exactly once after every targeted gate was green. It passed at 100% with only the existing Starlette/httpx deprecation warning.

### Residual methodological limits

- Historical detection rows store one repository-level `first_signal_at`, not an agent-specific signal timestamp on each evidence row. D4 therefore computes P0/P10/P50 from the repository-level earliest observed signal among repositories carrying each agent. It is more robust than a single minimum but remains a bounded emergence proxy; it must not be described as the agent's true first use. Future detection schemas can add an immutable per-evidence `signal_at`, but run #29 cannot reconstruct that field retrospectively.
- Owner-cluster bootstrap intervals quantify dependence among repositories owned by the same GitHub account; they do not model cross-owner ecosystem dependence or turn Organizations into individual people.
- Wealth coefficients remain unweighted ecological country associations. Bootstrap, leave-one-out, and Cook's-distance diagnostics expose fragility but do not establish causality.
- A cold snapshot for run #29 still takes about 21 seconds because it intentionally reads and validates the frozen evidence once. Finished detections precompute this snapshot, and every subsequent report/dashboard request is sub-second.

## 2026-11-10 — figure usability pass

- Fixed the adoption-intensity ECDF: the line chart used `{x, y}` points without declaring a linear x-axis, so Chart.js fell back to a category axis with no labels and the figure collapsed to 0%. The axis is now explicit.
- Confirmed that run #101 predates the history-coverage schema: none of its 17,757 detection documents contain `history_coverage` or `history_complete` keys. The 0% cells were therefore absent metadata, not zero coverage.
- Coverage cells now distinguish “not selected in this run” from “not recorded by this detection run”. A missing history schema renders `n/a` with an explicit reason instead of 0%, while the valid commit denominator remains available.
- Added an accessible `i` button and native dialog to every dashboard figure. Each dialog states whether the figure is a headline measure or a validity diagnostic, then gives the question, the data definition behind the marks, reading steps, a worked example, definitions for the jargon used in that figure, and one limitation.
- Bumped the persisted snapshot version to `analysis-2026-11-10-v4` so existing cached payloads refresh with the coverage reasons.

### Verification

- Targeted diagnostics, dashboard, analysis-page contract, snapshot, and golden tests passed.
- Ruff and Black pass on every changed Python file; `node --check` and the JavaScript helper suite pass.
- The complete test suite was run exactly once after the changes and passed.
- Pre-existing Black drift remains in three untouched files (`src/detect/git_orchestrator.py`, `src/detect/orchestrator.py`, `src/store/upserts.py`); they were left alone to avoid rewriting unrelated user work.



## 2026-11-10 - unknown creation dates excluded from cohorts

- Creation cohorts now exclude repositories with no recorded creation date instead of plotting them as an "Unknown" cohort. In run #101 this affects 72 of 17,757 repositories (0.4%), all CSV-import placeholders with synthetic negative ids.
- The chart subtitle reports the excluded count, and the figure explanation notes the exclusion.
- TODO: hydrate imported repositories from GitHub so they can rejoin the cohort analysis.
- Bumped the persisted snapshot version to `analysis-2026-11-10-v5`.

## 2026-11-11 - Generic demoted to shared markers

- Classified `Generic` as a shared marker rather than a product. `AGENTS.md`, the
  `AI Assistant` identity, and the `ai-generated` label describe a convention, an
  alias, or a PR label; none identifies an agent.
- Detection documents now keep `generic_markers` and no longer include `Generic`
  in `agents`. The marker is excluded from `with_agent`, `agent_share`, agent
  debuts, fingerprints, language leaders, size profiles, facet maps, and summary
  agent counts.
- Added a narrow content fallback (`agents-md-v1`) for shared instruction files.
  It attributes only when exactly one agent is explicitly addressed; bare and
  multi-agent mentions stay markers. Content hits use a dedicated `content`
  evidence channel and migration `0023`.
- Backfilled run #101: 6,606 documents updated, 5,821 kept a named agent, 773
  became marker-only, and 12 received a content fallback (7 Codex, 5 Claude Code).
  Repositories with any agent fell from 13,837 to 13,064.
- Added a dashboard figure and a report table for shared markers and content
  fallbacks, each with a full `i` explanation.
- Bumped the persisted snapshot version to `analysis-2026-11-11-v6`.
