# Fast, zero-loss git-mode detection — design

**Date:** 2026-10-17 · **Status:** draft for review · **Rollout decision:** stop run 93 (done) → implement + validate → one clean full run

## Context

Run 93 (detect #21, 17,757 imported rust repos, pack `2026-10-14`) ran for ~10.4h to 8,562/17,757
(13.7 repos/min at stop) and was cancelled to rebuild the pipeline. Every number this design cites is
measured and recorded in `docs/superpowers/plans/2026-10-17-run93-live-evidence.md`:

- **Root cause 1 — repair storm:** `fetch_pr_refs` uses `--depth 100 --filter=tree:0`; git then spawns
  per-object promisor repairs (NOOP negotiation, full closure incl. trees) that repeat with 93% object
  overlap. Live fleet: 6,183 packs / 678 MB; repos sat 10–40 min in the PR phase. Fix **proven**:
  `--filter=blob:none` (keep depth) → 10.1 s / 4 packs (stdx), 40 s / 8 packs (592-PR xybrid),
  walk outputs identical.
- **Root cause 2 — spawn storm:** one `git rev-list` spawn per PR ref, 0.31–0.53 s each, ~95% of the
  26 spawns/s ceiling. Batched-walk prototype: single `cat-file --batch` pipe, **0 mismatches** on 44 tips.
- **Zero-loss hazards:** dead repos pop credential dialogs and burn 30-min timeouts; a transient
  network/DNS outage burned **3,717 repos (21% of the corpus)**; `read_commits` silently returns `{}`
  on failure → pr_metadata "ok" with no evidence.
- **Environment:** OneDrive KFM over `clones/`, Defender, IDE/indexer churn, stray serve, PG flaky under load.

Run 93's 8,562 run_items + 1.2M evidence rows are **preserved** and serve as the end-to-end validation baseline.

## Goals and hard constraints

1. **Zero evidence loss. Zero drop in detection quality or accuracy.** Same pack, agents, channels
   (file/author/branch/bot/commit_trailer/pr_metadata), windows (all PR refs, last-100 commits each),
   same `read_commits` formatting, same dedupe/attribution, byte-identical documents/rows modulo timestamps.
2. **Fastest achievable on this machine:** target ≤ 3 h for the full 17,757 (≥ 5× the 12.6/min average).
3. **Zero permanent repo loss on failure:** outages and dead repos must be classified, retried or
   recorded — never silently dropped.
4. Gates are **fail-closed**: any differential mismatch blocks the final run.

## Non-goals (explicit)

- No PR-count capping (would drop rows); no `--depth` change; no API-mode changes; no discovery changes.
- No new runtime dependencies (stdlib + git only).
- UI work limited to an "Unavailable" section on the detect run page; CSV retry remains the manual fallback.

## Verified findings this design rests on

| Fact | Where proven |
|---|---|
| Only per-PR **sets** matter (attribution iterates PRs sorted + `setdefault`; dedupe keyed by JSON) | `local_channels.py:205-224`, `attribution.py:353-363` |
| `tree:0` triggers non-converging tree repairs | scratch repro (stdx hangs; repair pack parent-chains; pack overlap forensics) |
| `blob:none` eliminates it, same walk outputs | matrix A/B/C runs, identical counts across variants |
| Batched walk exact for ≤100-reachable; fallback-by-construction for deeper | walk prototype, 0 mismatches |
| Outage/dead-repo damage mechanisms + numbers | run-93 appendix + `runs/detect-93-clone-failures.csv` |

## Architecture — component changes

### C1. Transport fix (one line, proven)
`src/detect/gitio.py::fetch_pr_refs` (line 350): `--filter=tree:0` → `--filter=blob:none`.
Keep chunking (500 refspecs), keep `--depth 100`, keep retry machinery (now classified, C3).
Completed by the replay gate (C7).

### C2. RepoWalker — batched walks (kills ~95% of spawns)
New module `src/detect/repo_walk.py`. Public contract preserved from `gitio.walk_pr_shas`:
`walk_windows(repo: GitRepo, refs: Mapping[int, str], *, depth: int) -> dict[int, tuple[str, ...]]`.

Implementation:
- One long-lived `git cat-file --batch` process per repo (strict framing; commits only; missing → anomaly).
- Read `.git/shallow` once; grafted commits are treated as parentless (rev-list semantics).
- Per tip, walk with a date-priority queue replicating `git rev-list` default order: pop newest
  committer-date first; equal dates keep insertion order (new equal-date entries insert after existing
  ones, mirroring `commit_list_insert_by_date`); parents enqueued in listed order when a commit is
  popped; seen-set dedup; stop after `depth` pops.
- **Fast path:** if the tip's graft-aware reachable set is ≤ `depth`, order is irrelevant → return the
  set (provably exact for the only contract that matters).
- **Fallback:** any anomaly (missing object, non-commit object, replace-refs present, parse error) →
  spawn `git rev-list -n 100` for that tip (exact by definition).
- **Self-healing verification:** env `GITCORPUS_WALK_VERIFY_PCT` (default 0; gates use 100; at most 2
  spawns per `walk_windows` call, and exhausted-before-depth walks are never sampled). A random share of
  walk results are additionally verified with a real `rev-list`; on mismatch the true result is
  substituted, a counter increments in `field_stats`, and after 3 mismatches the process disables the
  exact-order path entirely (spawn-only) and records a run warning.
- Concurrency: runs inline in the scan thread; the shared 8-thread `walk_pool` and its plumbing in
  `git_orchestrator.py` are removed (this was also a serialization point).
- `read_commits` is **unchanged** (batched `git log --no-walk`, exact formatting).

### C3. Failure taxonomy, retries, circuit breaker (the zero-loss net)
`gitio.classify_git_failure(exc) -> "dead" | "transient" | "local" | "fatal"` (pure, table-driven):

| Class | Signals (stderr) | Policy |
|---|---|---|
| dead | `Repository not found`, `could not read Username`, `Authentication failed`, HTTP 401/404 | no retries; `unavailable: deleted_or_private` (fast) |
| transient | `Could not resolve host`, `Couldn't connect`, `Connection reset`, `timed out`, `early EOF`, `RPC failed`, HTTP 403/429/5xx, rate-limit/abuse text | requeue; eligible for retry wave (C5) |
| local | `index.lock`, `cannot lock`, `Permission denied`, disk errors | inline retry via existing `retry_call` |
| fatal | anything else | fail fast, record note |

- **Global circuit breaker** (mp-shared `Value`s created in `_run_git_detection_processes` and passed to
  workers): 5 consecutive transient failures fleet-wide → all workers pause
  `min(30·2^(n-1), 600)` s, then one probe attempt of the tripping candidate; success resets the counter
  and cooldown. During the run-93 outage this alone would have cost **0 of 3,717 repos**.
- **Askpass hardening** (`git_env()` in `gitio.py` and `_git_env()` in `cloner.py`):
  `GIT_ASKPASS=""`, `SSH_ASKPASS=""` (verified: clean `fatal: could not read Username … terminal prompts
  disabled`, no dialog, fast failure).
- Failure records gain a machine-readable `failure_class` and are summarized in `field_stats`.

### C4. `read_commits` integrity fix
`local_channels.detect_pr_commits_local:209-211`: on `GitError`, return a `partial` channel with the
error note instead of silently producing zero evidence with `status="ok"`.

### C5. Post-sweep retry + unavailable reporting
- Each worker process keeps the indices of candidates that failed with class `transient`; after its
  slice is exhausted it re-runs them **once** (fresh clone), subject to the breaker.
- `result_summary["unavailable"] = [{full_name, reason}]`; compact counts in
  `field_stats["clone"]["unavailable_reasons"]`; detect detail page gets an "Unavailable" section
  (counts + first N names). Rows for unavailable repos still exist (document `unavailable: true`), so
  the JSONB contract is unchanged.
- Manual fallback stays documented: export/import a repo list CSV (workflow proven today with
  `runs/detect-93-clone-failures.csv`).

### C6. Environment / runbook (zero semantic impact)
- New env `GITCORPUS_CLONES_ROOT` (default `"clones"`), consumed when the detect runner builds
  `GitScanConfig` (`serve/detect.py:60-66`). Runbook: `D:\gitcrawl-clones` (off OneDrive KFM); keep
  Defender exclusions for the root + `git.exe`/`git-remote-https.exe`.
- Run-booked hygiene: single serve instance; exclude clones root from IDE indexing; no opencode
  snapshot churn during the run; `_remove_tree` moved to a 2-worker background deletion pool so the
  parent loop never stalls (cancel semantics unchanged — skip sweep).
- Concurrency: measure 32 vs 64 on the benchmark slice after C1–C2; ship the winner (default stays 64
  unless measurement says otherwise).

### C7. Estimator honesty
`serve/detect.py:683-693` git estimate: replace the clone-MB-only 1–4 s model with
`minutes_low/high = repos × (4 s … 12 s) / min(workers, 32) / 60`, a note that PR-heavy corpora skew
high, and the measured floor from the last benchmark run (per-repo seconds) when available.

## Data flow (unchanged shape)

`candidates → per repo: clone → file channel → history → PR refs (fetch, blob:none) → batched walk →
read_commits → matches → persist scan → next` with failure classification around every git boundary.

## Error handling summary

Everything above is fail-closed: unverifiable walk → spawn; anomalous git state → spawn; network class →
pause+retry; dead class → record; anything unexpected → today's behavior (retry, then `unavailable`).

## Testing and acceptance gates (the guarantee)

1. **Unit:** classifier table; breaker state machine (pure, injectable clock); walker cases (graft,
   tie ordering, >100 selection against canned objects); env hardening; `read_commits` partial.
2. **Differential walk gate:** ≥ 10,000 tips across ≥ 100 repos (incl. Perry-class monsters):
   new walker vs `git rev-list -n 100` — **100% set equality required**; exact-order path checked on
   every >100 tip in the cohort.
3. **End-to-end replay gate:** re-scan ≥ 300 repos already covered by run 93 (spread across P classes);
   assert byte-identical `detection_evidence` rows and `run_items.detection` JSONB (modulo timestamps)
   against the preserved run-93 rows.
4. **Outage drill:** block DNS during a ~100-repo run; assert breaker pauses/escalates, retry wave
   recovers everything, zero permanent unavailable.
5. **Dead-repo drill:** include a known-deleted repo; assert no dialog, no retries, `deleted_or_private`.
6. **Perf gate:** 200-repo benchmark slice; require ≥ 5× run-93's equivalent average and a projected
   ≤ 3 h for 17,757. Record repos/min, per-stage seconds, spawn counts.

## Rollout

1. ✅ Run 93 stopped 15:05 (8,562/17,757); rows/evidence preserved as baseline; leftover clones cleaned.
2. Implement C1–C7; run gates 1–6 (no production run until they pass).
3. Fresh full detect run: source run 87, same pack `2026-10-14`, same options, `GITCORPUS_CLONES_ROOT=D:\gitcrawl-clones`,
   machine quiesced.
4. Post-run: quality report, unavailable list review (expect only genuinely dead repos), archive numbers
   into the evidence doc.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Exact-order replication subtlety | verify mode + substitution + auto-disable + spawn fallback; differential gate fail-closed |
| GitHub throttling under sustained clones | breaker + steady pacing; concurrency measured, not assumed |
| OneDrive/Defender regressions | dedicated clone root + exclusions documented in runbook |
| PG under load | unchanged; parent deletion moved off the critical path |
| Scope creep | non-goals list enforced; API mode untouched |
