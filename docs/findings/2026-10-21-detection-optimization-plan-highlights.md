# Detection Optimization Plan — Assessment Highlights

**Prepared:** 2026-10-21
**Assessed document:** `C:\Users\Abdul\Downloads\gitcorpus-detection-system-analysis-and-optimization-plan.md`
**Assessed against:** repo HEAD `cea9dc6` and the run-99 / run-101 artifacts
**Purpose:** highlights only — not an implementation plan

---

## Thesis

The source document is a credible forensic audit but not a credible optimization program. Its history and defect ledger are useful. Its Category A recommendations are mostly stale, non-bugs, or product changes. Executed wholesale, it saves seconds, not hours.

**Primary constraint:** faster only with zero negative effect on detection accuracy; accuracy improvements take precedence.

---

## Must-Highlight Facts

1. **A-1 is not the 25-minute problem.** The finalize `run_items` delete/reinsert is real but measured at **2.29 s** (run 99) and **4.36 s** (run 101). The 25-minute stall was read-only `.pack` deletion, already fixed in `2563274`.

2. **A-2 is a non-bug.** Run 99 exported 6 columns; run 101 exports 23. Run 101's CSV has exactly **3,036,007 data rows + one header**, with 23 fields on every row and no join multiplication. The size “regression” is schema width, not duplicate data.

3. **A-4 contradicts the product.** The repository is explicitly live-only (`README.md:3,40`). Air-gap/mirror mode is a separate product decision, not an optimization; current disk headroom also makes a full 17,757-repo mirror questionable.

4. **A-5 is unmeasured, not proven.** Phase metrics exist but were **not enabled** in run 101; `field_stats.walk.checked = 0`. The gate sweep is blind until instrumented, and `detect_concurrency` should be swept alongside the PR gate.

5. **A-6 is not accuracy-neutral.** Resume currently deletes all `run_items`/evidence and rescans from zero (`src/serve/executor.py:527-539`). Live refs drift, so skipping already-completed repos mixes epochs.

6. **B-1 is real but small.** **4/17,757** repos lost the entire `pr_metadata` channel because one PR tip failed (`src/detect/local_channels.py:269-278`). Per-PR fault isolation is worth doing; the stale-tip transport race is rare.

7. **B-2 is the highest-severity unknown.** Any missing parent is treated as a shallow boundary (`src/detect/repo_walk.py:368-379`), and short walks bypass verification (`:462-466`). The deferred gate has not been run, and `scripts/verify_walk_equivalence.py` only tests PR tips — not HEAD walks.

8. **B-3 is already marked.** All **2,392,234** run-101 `pr_metadata` rows carry `"propagated": true`, and the CSV has a `propagated` column. The real cheap accuracy fix is bot contamination in `first_signal_at`: **643 repos** have a first signal but no agents.

9. **B-4 is two different things.** The replay gate is worth running, but it compares `run_items` documents only and re-clones live GitHub. The 400-artifact × 2-annotator audit is a multi-day research protocol; redacted snippets and absent match metadata make post-hoc verification harder than the plan implies.

10. **The speed ceiling is near.** Run 101 is ~5 h 01 m of scanning; the remaining cost is mostly network I/O. Session IV already captured the large safe wins. No item in this plan credibly delivers the ≤3 h target.

---

## What To Explicitly Reject

- “Massive finalize I/O” — wrong by roughly three orders of magnitude.
- “CSV data-integrity anomaly” — explained by schema widening.
- “Derived rows are unmarked” — false for run 101.
- “Air-gap is a violated goal” — not a repository goal; imported framing.
- “Resume is Category A / zero-accuracy-loss” — false for live data.
- “400-artifact audit is a normal plan task” — it is a research validation project.

---

## Three Action Headlines

1. **Validate before optimizing.** Extend the walk gate to HEAD, run the 52-repo / 4,689-tip suite and the 120-repo replay, and publish a diff taxonomy.

2. **Fix confirmed accuracy bugs.** Per-PR walk fault isolation; exclude bots from `first_signal_at`; distinguish unexpected missing parents from real shallow boundaries.

3. **Measure the only plausible speed lever.** Run a phase-metrics benchmark sweeping PR-gate permits and scan concurrency. If it does not scale, stop optimizing and correct the stale “≈1 h” product claim.

---

## What To Omit or Qualify

- **Omit as action items:** A-2, A-4, B-3.
- **Qualify A-1:** UX label only; the finalize rewrite is not a meaningful cost.
- **Qualify A-5:** measurement exercise, not a guaranteed gain.
- **Qualify A-6:** operational recovery, not accuracy-preserving.
- **Keep Sections 1–6** of the source document as the factual record; **rewrite Section 8**.
