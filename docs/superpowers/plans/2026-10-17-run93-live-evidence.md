# Run 93 live evidence — git-mode detection performance (2026-10-17 04:39–06:35)

Collected live while run 93 (detect #21, source run 87: 17,757 imported rust repos) was running.
All rows/evidence below are measured, not estimated.

## Throughput

| Time | Done | Rate in window |
|---|---|---|
| 05:00 | 105 | — |
| 05:36 | 283 | 4.9/min (head of whales) |
| 06:11 | 820 | 15.3/min |
| 06:33 | 1,236 | 18.9/min (tail lighter) |

Persistence: 415,868 evidence rows across 1,158 repos; docs tiny (avg 335 B, p95 391 B, max 566 B) — JSONB/IPC is NOT a bottleneck. Failure rate so far: 3 clone failures (deleted repos), 5 `pr_metadata: pull refs fetch failed` (partial).

## THE root cause: promisor "repair fetch" storm inside chunk fetches

Live process evidence: **11 concurrent `git fetch --stdin` repair fetches, all spawned by the 12 live
`git fetch --quiet --depth 100 --filter=tree:0 ... +refs/pull/N/head` chunk fetches** (verified parent
chain: repair fetch → chunk fetch (same repo)). Repair fetch command = git's promisor path
(`-c fetch.negotiationAlgorithm=noop fetch origin --no-tags --no-write-fetch-head
--recurse-submodules=no --filter=blob:none --stdin`) — i.e. **NO negotiation: the server sends the full
reachable closure (commits + trees, blobs filtered) for every missing object**, one pack + one network
round trip + ~3 process spawns per object.

Effect: in-flight clones hold **6,183 packs / 677.7 MB**; 25 dirs >50 packs, 9 dirs >200 packs, while
`refs` stay frozen (monitor CSV). Expected packs per repo ≈ 3–6 (clone + ceil(P/500) chunks + blob fetch);
observed hundreds → **>95% of all fetch work is repair traffic**. Repos sit in the PR-fetch phase for
tens of minutes (`octos` 38+ min / 510 packs; `tempo` 36 min / 518 packs; `libnativeapi` 130 packs for 3 PR refs).

Trigger: shallow multi-ref fetching (`--depth 100` × 500 refspecs × `--filter=tree:0`) on repos with
massive shared bot-PR ancestry. Git finds objects missing for ref updates and repairs each individually.

## Other measured constants

- Clone (blobless depth-100): 4.0–4.9 s, 1 pack. **Cheap — not the problem.**
- `ls-remote refs/pull/*/head`: 3.0–3.7 s (Perry = 7,989 PR refs).
- One 500-ref `--depth 100 --filter=tree:0` chunk fetch clean: 14.2 s (Perry chunk 1), 21.5 s under load.
  In the live run the same fetch spawns repairs instead — minutes to tens of minutes.
- **One `git rev-list -n 100 <tip>` = 0.48 s (spawn-dominated; 0.31 s even on tiny repos).** Perry-class
  repo: 7,989 walks ≈ 64 min serial, ~8 min through the shared 8-thread walk pool per mp process.
  Scratch test confirmed walks create no packs when objects exist; `log --no-walk` is 20 ms/sha batch.
- PR distribution in the head cohort (hit repos): max PR numbers up to **12,690** (`PerryTS/perry`),
  12,514 (`t8y2/dbx`), 8,432, 8,405, 8,202, 8,119; run-93 hit-repo percentiles: median 409, p90 2,522.
- Process spawn capacity under load: **~26 git spawns/s** fleet-wide (235 distinct PIDs / 9 s); CPU 100%,
  disk 6–10% → spawn/CPU-bound.
- Config: 4 mp processes × 16 threads = 64 repos in flight (`serve/detect.py:60-66`, detect_concurrency 64);
  walk pool = 8 threads shared per process (`gitio._WALK_WORKERS`).
- Quality bug found: `detect_pr_commits_local` swallows `GitError` in `read_commits`
  (`local_channels.py:209-211`) → `records={}` → **zero pr_metadata evidence while channel reports `ok`**.
- Environment: OneDrive KFM sync over clones dir (1.1k CPU-s), Defender, SearchIndexer, JetBrains git probes,
  opencode snapshot `git gc/repack` (multi-core), stray second `-m serve` (PID 9080), PG auth-starved under load
  (connect timeouts, statement timeouts).
- Askpass: run environment carries `GIT_ASKPASS`/`SSH_ASKPASS`; dead repos (404) popped 16 blocking dialogs
  (see `2026-10-17-dead-repo-handling.md`). Watcher auto-killed them.

## Optimization plan implied by the evidence (zero evidence-loss)

1. **Kill the repair storm**: drop `--depth 100` from `fetch_pr_refs` (fetch full commit history,
   keep `--filter=tree:0` — blobs still never fetched; per-repo data stays small). No shallow state → no
   repair fetches. Fallback/alternative: fetch all PR refs in ONE command so shallow computation is
   consistent across the ref set. Verify evidence equality on sample repos before rollout.
   Expected: PR-fetch phase minutes→seconds; fleet pack count collapses; 10–40 min monsters → ~1 min.
2. **Batch the walk** (0.48 s × P spawns is the next wall): in-process ancestry walk over a single
   `cat-file --batch` pipe; use real `rev-list` spawn only when local ancestry >100 (provably same set).
   Differential test vs current output required.
3. Fix `read_commits` silent failure → channel `partial` (never silent-empty).
4. Environment: clones on `D:\` (off OneDrive), no IDE/opencode snapshot churn during runs, single serve.
5. Estimator: price PR refs (chunk fetches + walks), not clone MB only; report hours honestly (~2–4 h).

Artifacts: `%TEMP%\opencode\clone_monitor.csv` (per-dir packs/refs timeline),
`%TEMP%\opencode\askpass-watch.log` (dead-repo dialogs), `%TEMP%\opencode\inflight_inventory.csv` (snapshot).

## VERIFIED FIX (controlled experiments, 2026-10-17 11:00-11:10)

Root trigger isolated: **`--filter=tree:0` on `fetch_pr_refs`**. Repair packs contain ~290 TREES each
with 93% object overlap between consecutive packs — git repeatedly fetches per-commit tree closures
because trees are promised-but-absent (shallow × treeless × multi-ref on GitHub). Reproduced in a scratch
clone of `rust-stdx/stdx` (44 PR refs): current fetch NEVER completes (15 min, 33-51+ packs, refs 0).

| Variant (scratch, no load) | Result |
|---|---|
| clone depth100 + fetch `--depth 100 --filter=tree:0` (current) | hangs; 33-51+ packs; refs 0 |
| clone depth100 + fetch `--filter=tree:0` (no depth) | still storms (shallow clone present) |
| full clone + fetch `--filter=blob:none` no depth | **15.1 s, 4 packs, 44/44 refs** |
| shallow clone + fetch `--filter=blob:none` no depth | **15.1 s, 4 packs, 44/44 refs** |
| **clone depth100 + fetch `--depth 100 --filter=blob:none` (one-arg change)** | **10.1 s, 4 packs, 44/44 refs** |
| same one-arg change on `xybrid-ai/xybrid` (592 PRs; live run: 308+ packs) | **40 s total, 8 packs, 592/592 refs** |

Walk outputs are IDENTICAL across variants ([30..75] on stdx everywhere; xybrid gives clean 100s) —
**zero evidence drift**; blobs still never fetched (tree data for PR windows is modest, ~2.7 MB for 592 refs).

Minimal fix: in `fetch_pr_refs` (`gitio.py:350`) change `--filter=tree:0` → `--filter=blob:none`.
Keep `--depth 100` and the clone unchanged.

Batched-walk prototype (Fix 2) validated: in-process cat-file walk vs `git rev-list -n 100` on all 44
stdx tips → **0 mismatches** (21 exact-set matches for ≤100-reachable tips; 23 auto-fallbacks to a real
`rev-list` spawn for >100-reachable). In-process walk cost ≈ milliseconds; all measured time was the
verification spawns (~0.4 s each).

Expected effect: fleet pack counts collapse (6,183 in-flight packs → a few per repo); PR-fetch phase
minutes→seconds-to-40s; with Fix 2, projected full-corpus ≈ 2-4 h (was ~80 h).

## APPENDIX — late-run rate analysis + network outage damage (14:45, same day)

Run 93 is the same continuous run (no stop/resume): **7,947/17,757 at 14:45**, overall avg 12.6/min,
recent sustained **~27/min with bursts 47–110/min** (the console ETA collapsed from days to ~4–6 h).

Why the late speed-up (measured):
1. Cohort now at rank ~8,000+/17,757 (stars 12–18): in-flight median **14 PR refs** (early cohort ~101–128;
   head monsters up to 12,690). Per-repo serial work scales ~linearly with PR count.
2. Repair storm faded: fleet packs 310 (was 6,183), 0 dirs >50 packs (was 9 dirs >200);
   live repair:chunk process ratio ~2:11 (was 11:12).
3. Recovery flush: an ~11-min stall at 14:02–14:13 (in-flight dirs collapsed to 3–9) then 56 new dirs in
   one 25 s sample (14:13:40) — the network recovered; backlog flushed at 90–110/min briefly.

**DATA-LOSS EVENT:** 3,717 consecutive clone failures (48% of scanned docs; 21% of the full corpus)
caused by a **network/DNS outage** ("fatal: unable to access 'https://github.com/…': Could not resolve
host" — confirmed on 25 notes; the rest truncate identically; zero 4xx/5xx/auth errors). Failure density
along scan order: buckets 519–525 ≈ 0–1%, bucket 526 = 27%, **buckets 527–533 = 100% (~3,500 straight)**,
bucket 534 = 15%, bucket 535+ = 0%. Estimated window ≈ 09:30–14:13 local. All failed repos clone fine now
(verified 5.8 s / 4.2 s live). They exist as `unavailable` docs with no evidence.

Remediation ready: **`runs/detect-93-clone-failures.csv`** (3,717 rows: full_name, stargazers) — import via
the console (repo-list import) to create a source run, then run detection on it after run 93 finishes.

Plan additions from this event:
- Classify transient-network errors distinctly from dead repos; add a global circuit breaker
  (N consecutive network failures → cooldown/resume) instead of burning 4 retries × 3,700 repos;
  the outage would then have cost ~0 repos.
- The planned "unavailable report + targeted retry" is now clearly required (dead repos 404 + outages).

## STATUS UPDATE — run 93 stopped (15:05)

Cancelled gracefully via `POST /runs/93/cancel` at 8,562/17,757 (13.7 repos/min stop-rate).
`run_items` (8,562) + `detection_evidence` (1,208,034 rows) preserved: they are the end-to-end
replay baseline for the new pipeline. Leftover clone dirs cleaned. Design for the rebuild:
`docs/superpowers/specs/2026-10-17-fast-zero-loss-detection-design.md`.
