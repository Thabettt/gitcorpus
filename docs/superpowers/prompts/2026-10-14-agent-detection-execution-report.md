# Agent-Detection Execution Report — 2026-10-14 overnight session

**Plan:** `docs/superpowers/plans/2026-10-02-agent-detection.md` (revised 2026-10-14)
**Spec:** `docs/superpowers/specs/2026-10-02-agent-detection-design.md` (revised 2026-10-14)
**Base:** `18a3ba1` (preflight-complete) · **Feature head:** `9224641` · **All work committed locally on `main`; nothing pushed.**

## Status — all 11 tasks complete, each task-reviewed; final whole-branch review returned 3 Important findings, all fixed in one wave and re-reviewed clean.

| Task | Status | Commits | Notes |
|---|---|---|---|
| 1. Migration 0016, models, schema contracts | done | `d8e9708` | trace_packs, detection_evidence, runs.kind/source_run_id/result_summary, run_items.detection |
| 2. Pack build/freeze/load | done | `8728e9d` | vendored `packs/patterns/`, frozen `packs/2026-10-14.json` (sha256 e28a1e0cec20) into dev DB |
| 3. Attribution, selection, propagation, redaction | done | `928a4dc` | rulings A, B, H |
| 4. File channel (tree, .gitignore, probes) | done (+fix) | `4ca03d8`, `5297c05` | ruling I |
| 5. History channels (author, trailer, bot) | done (+fix) | `0589c32`, `223b49f` | ruling J |
| 6. PR channels + propagation + issue channel | done (+fix) | `b4df9f6`, `154ea27` | ruling K |
| 7. Estimate | done | `7220717` | |
| 8. Orchestrator + executor integration | done (+fix) | `587294b`, `ff2f527` | ruling L (bounded submission + cancellation) |
| 9. Detect spec, routes, app wiring, templates | done | `ae0c303` | replaces the dead resume branch; clears the pre-existing ruff I001 |
| 10. Console wiring, export, golden | done (+fix) | `bdc65c4`, `877adcf` | ruling M; OpenAPI re-pinned |
| 11. Docs, README, dev log, full suite | done | `efdbf2c` | `docs/detection-tiers.md`, D13 pointer |
| Final review fix wave | done | `552d5c0`, `0b6312d`, `9224641` | ruling O |

Preflight commits this session: `c36a767` (console polish), `28479ee` (plan/spec revision), `18a3ba1` (ignore .worktrees).

## Verification (final tree `9224641`)

- Full suite: **1640 passed, 1 failed, 0 errors** (1641 collected).
- The 1 failure is **environmental, not feature-related**: `tests/unit/test_cloner.py::test_full_run_clone_estimate_matches_the_full_scan_path` fails because C: free space (~1.9 GB) is below the 2048 MB reserve — it fails identically on the base commit.
- Coverage: **94.17% ≥ 93 floor**. `ruff check src tests` and `black --check src tests` clean.
- Golden: snapshots regenerated, OpenAPI pin re-pinned; detect routes in `PATH_PARAMS`.
- Redis was down mid-session; restored before final verification, so the 2 `test_golden_org.py` integration errors are gone.

## Rulings made on the operator's behalf (full list; each with cost if wrong)

1. **A (T3):** `_generic_weight` normalizes the pattern key (unescape `\.`) so `AGENTS\.md` finds the `AGENTS.md` weight. Cost: weight applied/omitted on AGENTS.md; test-caught.
2. **B (T3):** commit-trailer snippet is a redacted window of the message around the match. Cost: cosmetic snippet wording.
3. **C (T6/T8):** PR→commit propagation emits evidence on channel `pr_metadata` whenever any PR-channel match triggers it, even if `pr_metadata` is unselected (spec §8 propagation mandate beats invariant 6's scoping letter). Cost: exported `pr_metadata` rows for runs not ticking that channel; small filter later.
4. **D (T10):** golden TRUNCATE extended to `detection_evidence, trace_packs` for idempotency. Cost: none.
5. **E (T2):** date-only pack version/file (`packs/2026-10-14.json`) kept over spec §5's suggested `<date>-<sha8>` filename. Cost: filename convention only.
6. **F (T2):** freeze step allowed to `alembic upgrade head` the dev DB first. Cost: dev DB gains tables early.
7. **G (setup):** work in place on `main` per the operator's overnight convention (no worktree; OneDrive risk), no pushes. Cost: commits land on main locally; reversible, nothing pushed.
8. **Baseline:** exclude the known environmental cloner failure from task acceptance. Cost: one known-red test stays red.
9. **H (T3–T6):** bot-channel matching is an explicit selection-scoping exemption (bots.csv labels are not selectable agents). Cost: bot channel populated regardless of selection; one-line change later.
10. **I (T4):** thread `ref` through contents fetches; map `PartialResultsError/ThrottledError/httpx.HTTPError` to `partial` channel results; same pattern into T5/T6/T8 with per-repo future guards. Cost: infra faults show as labelled partial channels instead of failed runs (spec §9-aligned).
11. **J (T5/T6):** GraphQL `errors` payloads map to `partial`, never `unavailable`/`ok`. Cost: resource-cap repos counted under partial_channels (spec-aligned).
12. **K (T6):** harden null GraphQL nodes; add errors+non-null-repo regression test. Cost: none.
13. **L (T8):** bounded submission in `run_detection` with cancellation before each submit/after each completion; `except RunCancelled: raise`. Cost: cancel granularity becomes ~one in-flight scan (spec §9-aligned).
14. **M (T10):** fix schema fixture, add golden `run_items` for run 952, clear the quarantine-manifest gate via direct test usage (not quarantine). Cost: two extra small tests.
15. **N (env):** attempt Redis restart before final verification; else classify golden-org errors as environmental. Cost: none to code.
16. **O (final):** fix all three final-review Importants in one wave — §9 pre-enqueue guards (zero candidates, unknown agents per selected pack), §7 UI affordances (searchable agent list + select all/none; detail has-signal/agent/channel filters), and tests for top-N determinism + committer-only matching. Cost: extra UI surface trimmable later; tests additive.

## Known residuals (deferred minors; final review triaged none as merge-blocking)

- `_MATCHER_CACHE` is keyed by pack version only; two same-version in-memory packs collide in unit tests (prod versions are immutable, full-suite order is unaffected; direct `test_detect_orchestrator.py` before `test_detect_channels.py` in one command can reproduce).
- Freeze select-then-insert race surfaces `IntegrityError` instead of `PackConflict` under concurrency (CLI-only, single operator).
- `redact_emails` does not redact bare no-TLD tokens (e.g. `cursoragent@x`) unless bracketed; standard trailers are bracketed.
- Export download filename ends `.detections` while content is CSV; internal `runs.py` ValueError text still says "json, csv" (unreachable via route).
- Detection `detection.notes` and `result_summary.partial_channels` carry brief-mandated note wording; hardcoded "most recent 100" with non-default limits.
- Evidence rows are written per completed repo in completion order (items/detections.csv order varies with concurrency).
- Tiers doc §2 lacks a call-cost column / §1 a cannot-tell element (brief-verbatim vs spec §10 strict reading).

## What is NOT done

- **Nothing is pushed**; all 19 feature commits are local on `main`.
- The optional token-guarded live smoke (plan Task 11 Step 5) was skipped.
- AdaptiveController / deep-history tiers / detect-run diff remain out of scope (v1.1 per spec §13).
- The environmental cloner low-disk test and the C: free-space situation (~1.9 GB free) are untouched.
