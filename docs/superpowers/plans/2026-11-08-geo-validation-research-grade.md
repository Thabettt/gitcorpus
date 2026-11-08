# Research-Grade Geo Validation Implementation Plan

**Goal:** Turn owner-country resolution into a validated, versioned measurement instrument with independent human ground truth, quantified uncertainty, auditable release gates, and reproducible artifacts.

**Principle:** Coverage is never optimized by converting uncertainty into a country. The primary safety metric is wrong-country assignment; unmatched is a valid outcome.

**Status:** Implementation and the initial blinded benchmark workspace are complete. Empirical release claims remain blocked until two independent humans annotate all packs and a third adjudicates every disagreement; no labels were fabricated during implementation.

## Constraints

- Preserve frozen `run_items`; validation and backfills may update only mutable owner enrichment.
- Never put owner login, GitHub id, token, or repository identity in annotation artifacts.
- Annotators see only permitted profile evidence, never resolver predictions or confidence.
- Sampling, pack order, bootstrap intervals, and hashes are deterministic from recorded seeds.
- Resolver tuning uses development data only; the final holdout remains untouched.
- Run targeted tests during implementation. Run the complete suite exactly once, as the final check.

## Deliverables

- [x] `src/enrich/geo_validation.py`: schemas, deterministic stratified sampling, annotation validation, agreement/adjudication, metrics, bootstrap confidence intervals, release gates, and artifact hashing.
- [x] `scripts/geo_benchmark.py`: `sample`, `pack`, `annotate`, `adjudicate`, `finalize`, and `evaluate` commands.
- [x] `docs/geo-validation/annotation-policy-v1.md`: frozen labeling policy and decision tree.
- [x] `docs/geo-validation/release-gates-v1.json`: predeclared acceptance thresholds.
- [x] `docs/geo-validation/artifact-schema-v1.json`: frozen machine-readable annotation and gold-label contracts.
- [x] `docs/geo-validation/challenge-cases-v1.jsonl`: frozen multilingual and adversarial conformance corpus.
- [x] `docs/geo-validation/README.md`: operator workflow and research-reporting contract.
- [x] Unit tests covering deterministic sampling, blinding, invalid labels, agreement, adjudication, weighted metrics, intervals, hashes, and gates.
- [x] A local ignored benchmark workspace sampled from the current owner population, with two blinded annotator packs ready for independent labeling.

## Task 1 — Evidence and Artifact Contracts

- [x] Define versioned case, annotation, gold-label, metric, and manifest schemas.
- [x] Use opaque SHA-256 case ids derived from allowed evidence.
- [x] Record resolver/data/code versions, dirty-tree hash, sampling frame hash, policy hash, seed, stratum counts, inclusion probabilities, and every output hash.
- [x] Make writes atomic and reject silent overwrite unless explicitly requested.

## Task 2 — Deterministic Stratified Sampling

- [x] Build an owner population from `location_raw`, owner type, and the de-identified final website TLD only.
- [x] Aggregate duplicate evidence and retain owner frequency.
- [x] Stratify by predicted confidence, Unicode script group, and evidence shape.
- [x] Allocate a minimum per confidence tier, then distribute remaining capacity proportionally.
- [x] Record `1 / inclusion_probability` for unique-evidence estimates and `frequency / inclusion_probability` for owner-weighted estimates.

## Task 3 — Blinded Annotation Workflow

- [x] Generate independently shuffled packs without prediction, confidence, stratum, or frequency.
- [x] Support resumable terminal annotation with atomic autosave.
- [x] Enforce statuses: `country`, `multi-country`, `ambiguous`, `non-location`, `insufficient`.
- [x] Require ISO codes only where the status permits them and capture certainty, policy tags, and rationale.
- [x] Never infer or prefill a human label from the resolver.

## Task 4 — Agreement and Adjudication

- [x] Compare two independent annotation files by case id.
- [x] Report exact agreement, status agreement, Cohen's kappa, and disagreement taxonomy.
- [x] Auto-accept exact agreements and generate an adjudication-only sheet for disagreements.
- [x] Finalize gold labels only when every disagreement has an adjudicated decision.

## Task 5 — Evaluation and Statistical Reporting

- [x] Measure coverage, assigned precision, resolvable recall, wrong-country rate, false abstention, and abstention accuracy.
- [x] Report unique profile-evidence design-weighted and owner-weighted estimates.
- [x] Report per confidence tier, script group, and evidence shape.
- [x] Produce deterministic stratified-bootstrap 95% intervals.
- [x] Emit machine-readable JSON/CSV plus a publication-ready Markdown methodology report.

## Task 6 — Release Gates and Audit Package

- [x] Evaluate only predeclared gates from the frozen JSON policy.
- [x] Gate the production-accepted tiers (`exact-iso` through `gazetteer-city`) on precision, wrong-country upper bound, sample sufficiency, and annotation agreement.
- [x] Keep `weak` excluded from the default production threshold and report it separately.
- [x] Hash the final gold data, predictions, report, policy, and manifest into one immutable audit index.
- [x] Exit non-zero on any failed gate or integrity mismatch.

## Task 7 — Verification and Initial Workspace

- [x] Run focused unit/CLI tests while implementing each task.
- [x] Generate a deterministic current-data benchmark workspace and two blinded packs; do not fabricate human labels.
- [x] Run Ruff, Black, Mypy, and `pip check`.
- [x] Run the full pytest suite once, only after implementation is complete.
