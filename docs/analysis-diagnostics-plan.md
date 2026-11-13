# Analysis diagnostics, robustness, and performance plan

**Started:** 2026-11-10
**Scope:** Keep the twelve headline measures. Add six diagnostic panels, strengthen the wealth analysis, and make the report and dashboard share one fast, versioned analysis snapshot.

## Locked decisions

- [x] Keep the twelve headline measures unchanged as the descriptive analysis contract.
- [x] Add six diagnostics: evidence robustness, observation/eligibility coverage, owner-cluster robustness, robust debut distributions, adoption-intensity distributions, and multi-agent co-use.
- [x] Repository multiplicity bands: `1`, `2–5`, `6–9`, `10+` distinct agents.
- [x] Owner multiplicity bands: `1`, `2`, `3`, `4–6`, `7–9`, `10+` distinct agents.
- [x] Aggregate each owner's agent set across every repository that owner has in the frozen detection run.
- [x] Report GitHub `User` and `Organization` owners separately.
- [x] Rank exact canonical agent sets, not marginal agent prevalence; count descending, then canonical lexical set key ascending.
- [x] Use targeted tests during development. Run the complete test suite exactly once, at the final gate.
- [x] Do not use Playwright or MCP tools.

## Statistical contract

### Shared population rules

- [x] Define `scanned`: every `run_items` row in the detection run.
- [x] Define `readable`: a non-null detection document not marked unavailable.
- [x] Define `complete-channel eligible`: readable and every channel selected in the frozen run specification has status `ok`.
- [x] Treat missing, malformed, unselected, failed, partial, unavailable, and observed-zero states distinctly.
- [x] Count each repository, owner, agent, channel, and agent set at most once in every relevant estimand.
- [x] Preserve Unknown metadata strata rather than coercing or dropping them.

### D1 — Evidence robustness envelope

- [x] Declare channel families and the non-bot evidence universe in code.
- [x] Broad: at least one non-bot evidence facet.
- [x] Behavioral: evidence in author, commit-trailer, or PR metadata channels.
- [x] Corroborated: evidence in at least two declared non-bot channel families.
- [x] Structural-only: committed file/config evidence and no behavioral evidence.
- [x] Strict: behavioral or corroborated evidence.
- [x] Compare broad and strict on the same complete-channel-eligible denominator.
- [x] Report corroboration among broad detections separately.
- [x] Return numerator, eligible denominator, percent, and Wilson interval for every binomial estimate.
- [x] Label the broad-minus-strict gap as a sensitivity gap, never a confidence interval.

### D2 — Observation and eligibility coverage

- [x] Report readable, complete-channel, successful file-scan, valid commit denominator, observed history coverage, and full-history coverage.
- [x] Use all repositories in a stratum as each coverage denominator.
- [x] Return `not_applicable` rather than zero when the frozen run did not select the required channel family.
- [x] Distinguish an unselected channel from a detection run that never recorded the history-coverage fields; render both as `n/a` with an explicit reason.
- [x] Compute rows for country, language, star tier, and lifetime commit tier.
- [x] Carry count, denominator, percent, Wilson interval, and deterministic stratum order.

### D3 — Owner-cluster robustness

- [x] Use owners with at least one complete-channel-eligible repository as the owner-adoption denominator.
- [x] Adopted owner: at least one eligible repository with broad non-bot evidence.
- [x] Report repo-weighted and owner-weighted adoption on the same eligible owner clusters.
- [x] Report unique owners, eligible repositories, repositories per owner, and missing-owner repositories.
- [x] Report top-one and top-five owner concentration for eligible repositories and adopted repositories.
- [x] Compute deterministic owner-cluster bootstrap intervals when at least 10 owner clusters exist.
- [x] Separate `User` and `Organization`; never pool them into a person-level claim.

### D4 — Robust debut distributions

- [x] For each agent, use one valid repo-level observed signal date per repository.
- [x] Report P0, P10, and P50 with a documented deterministic quantile method.
- [x] Report dated repositories, all repositories carrying the agent, and dated-evidence coverage with Wilson interval.
- [x] Keep earliest repository creation as a separate bound, not as an observed-use date.
- [x] Label all dates as bounded observations, never true first use.

### D5 — Adoption-intensity distributions

- [x] Define a valid history denominator as a finite commit ratio in `[0, 1]` on a readable repository.
- [x] Compute P25, P50, P75, and P90 among recent adopters (`commit_ratio > 0`).
- [x] Report zero-recent-use share among repositories with a valid history denominator.
- [x] Report pervasive share at the preregistered `commit_ratio >= 0.20` threshold among recent adopters.
- [x] Provide overall and country/language/star/commit/cohort stratified summaries without converting missing ratios to zero.
- [x] Include the empirical distribution needed for an ECDF-style visual without exposing one row per repository in HTML.

### D6 — Multi-agent co-use

- [x] Derive a canonical distinct non-bot agent set per repository.
- [x] Report repository bands `1`, `2–5`, `6–9`, and `10+`, with detected repositories as the primary denominator and the eligible frame as context.
- [x] Derive each owner's canonical union of agents across every repository owned in the frozen run.
- [x] Report owner bands `1`, `2`, `3`, `4–6`, `7–9`, `10+` separately for `User` and `Organization`.
- [x] Report total represented owners, owners with no observed agent, and owners with at least one agent.
- [x] Rank every exact canonical set within its band by owner count descending and lexical set key ascending.
- [x] Verify that band counts and exact-set counts reconcile exactly.

### Wealth robustness upgrade

- [x] Keep the current unweighted country-level Pearson correlation on `log2(GDP per capita)` and repo-weighted adoption.
- [x] Add Spearman rho with average ranks for ties.
- [x] Add OLS slope in adoption percentage points per doubling of GDP per capita.
- [x] Add deterministic nonparametric country bootstrap intervals and report valid replicate count.
- [x] Add leave-one-country-out ranges.
- [x] Add Cook's distance and leave-one-out deltas for influential-country identification.
- [x] Require at least 3 qualifying countries for coefficients and at least 5 for bootstrap/influence diagnostics.
- [x] Keep all language explicitly descriptive and non-causal.

## Persistence and performance

- [x] Identify the database run id for detection #29 and record baseline route/metric timings.
- [x] Profile every current measure independently before changing query paths.
- [x] Add a versioned persisted analysis snapshot with generated timestamp and explicit invalidation.
- [x] Make report selections project from the shared full snapshot rather than recomputing metrics.
- [x] Make the dashboard consume that same snapshot and only reshape it for charts.
- [x] Prevent concurrent requests from stampeding the same uncached run.
- [x] Invalidate on run reset/resume and owner-country backfill.
- [x] Generate the snapshot at successful/partial detection completion; failure must not corrupt the detection run.
- [x] Optimize expensive evidence/fingerprint and repeated-strata paths.
- [x] Add indexes only when justified by measured query plans.
- [x] Record cold-build, warm-report, and warm-dashboard timings for detection #29.

## Authoritative tables and visuals

- [x] Add exact-data report sections for all six diagnostics and expanded wealth statistics.
- [x] Add a paired robustness interval/sensitivity chart.
- [x] Add a coverage heatmap with dimension and coverage selectors.
- [x] Add an owner-cluster comparison/interval panel split by account type.
- [x] Upgrade debut visualization to P0–P10–P50 percentile ranges with coverage.
- [x] Add an intensity distribution/ECDF panel with stratum selector.
- [x] Add repository multiplicity composition plus owner exact-set rankings split by account type and band.
- [x] Expand wealth stat strip and influential-country detail.
- [x] Add a keyboard-accessible info control and explanation dialog to every dashboard figure, including data context, reading steps, a worked example, and key-term definitions.
- [x] Preserve no-JavaScript access to all exact values in data tables.
- [x] Preserve keyboard, dark-mode, reduced-motion, responsive, and missing-data behavior.

## Test and quality gates

- [x] Pure unit tests for bands, quantiles, ranks/ties, Wilson rates, bootstrap determinism, Spearman, OLS, leave-one-out, and Cook's distance.
- [x] Integration tests for evidence definitions, eligibility/missingness, owner aggregation, account-type separation, and exact-set tie ordering.
- [x] Snapshot cache hit/miss/version/invalidation/stampede tests.
- [x] Contract tests for report and dashboard projections.
- [x] Performance regression test that proves a warm request performs no analytical source scans.
- [x] Targeted ruff/format/static checks.
- [x] Targeted Python and JavaScript tests.
- [x] Regenerate only affected golden snapshots after contracts stabilize.
- [x] Run the complete 2,000+ test suite exactly once, only after every preceding item is green.
- [x] Record final outcome and any residual limitations in the progress log.
