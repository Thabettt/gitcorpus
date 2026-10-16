# Agent Detection: Efficient Engineering

**Date**: 2026-10-16. Companion to `detection-pipeline.md` (what the local-clone scan does, stage by stage), `detection-options.md` (API vs scraping vs git, measured), and `corpus-building-efficient-engineering.md` (the same kind of math for building corpora). You need no prior git-plumbing knowledge — every term is introduced where it is first used. Every number below was measured on this machine during the 2026-10-16 session (the run database, live probe scripts, and the working tree that landed as commit `9afd37e`); projections are labelled as projections.

**Purpose of this document**: explain, from scratch, why the agent-detection git scan was slow and sometimes appeared stuck, how we measured the real causes with before/after numbers, and what changed so a scan of N repositories takes roughly the time its data honestly requires — with **no repository ever marked unavailable by our own machinery** and **no channel ever silently incomplete**. It is the engineering story behind one commit, told with the numbers that drove every decision.

**Status note (2026-10-16)**: the git scan's per-repo pipeline was rebuilt around the measured bottlenecks. The single largest defect — a hidden network round trip per commit, hiding inside `git show` — taxed **every** repository and made a 10-repository test batch take ~6 minutes; the same batch's PR phase now finishes in seconds with byte-identical results. A 452-commit repository that took **330–370 seconds** in its commit-reading step (392 lazy-fetch round trips) now takes **3.4 seconds**. The full suite is green (coverage 94.44%, gate 93), and detection #17's 10-repo batch — the first fully complete one on record (615 evidence rows, 0 unavailable, no partial channels) — pays seconds, not minutes, for the same data.

---

## 1. The goal, in one paragraph

Agent detection asks a simple question of every repository in a frozen corpus: *does a coding agent show up in this repo's files, commit history, branches, or pull requests?* There are exactly two ways to get the data: ask GitHub's API (rate-limited — a full 17,757-repo scan is a ~13-hour job bound by the GraphQL budget, measured in `detection-options.md`) or download the repositories with plain git (no hourly quota). The git route is the one this document is about. Its engineering problem is **not** a rate limit — git has none — it is round trips and stalls: every request to GitHub costs latency, every stalled request costs minutes, and the naive pipeline we shipped first paid both in places nobody could see. The work described here removes those costs without removing a single byte of evidence.

---

## 2. How a git scan works (one page)

For each repository, the scan runs four stages in order, then rolls the results up:

| # | Stage | Plain description | What it touches |
|---|---|---|---|
| 1 | **Lean clone** | Copy the repository's recent skeleton: last 100 commits, all directory structures, **zero file contents** (`--depth=100 --filter=blob:none --no-checkout`). | The network (a small pack) |
| 2 | **File channel** | List every path in the tree; match agent-ish files (`CLAUDE.md`, `.cursor/`); read `.gitignore` and up to 5 matched files for evidence. | File **contents** — fetched on demand |
| 3 | **History channel** | Read the last 100 commit messages and author/committer identities; match agent trailers (`Co-authored-by: Claude`), agent emails, bots. | Commit objects (already cloned) |
| 4 | **PR channel** | Fetch the tips of **all** pull requests (`refs/pull/*/head`), walk each tip's last 100 commits, read those commits' identities and messages. | The network (PR refs) + commit objects |
| 5 | **Rollup** | Per-repo adoption ratio, evidence rows, summary. | Local database |

Three pieces of git vocabulary make the rest of this document readable:

- **Shallow** (`--depth=100`): the clone keeps only the newest 100 commits per branch. Git records where it deliberately stops in a small `shallow` file. Walks up the history stop there by design.
- **Filtered** (`--filter=blob:none`): the clone keeps commits and directory structures but **not file contents**. Think of a library that gives you the card catalog (every path and folder) but not the books. If you later ask for one specific book, git phones the warehouse and has it couriered over — automatically, mid-command. This courier trip is called a **lazy fetch**.
- **Promisor**: the arrangement ("origin is my warehouse; fetch what I ask for") is recorded in the clone, so plain commands like `git show` can trigger courier trips you never explicitly ordered.

That last point is the villain of §5. Keep it in mind.

---

## 3. The first wall: one path bug made whole runs "unavailable" (run #7)

The very first git-mode detection run wrote, for all ten repositories:

```
FileNotFoundError: ... 'clones\detect-46\<repo>\.gitcorpus-clone-done'
```

Every repo, "unavailable", in under five seconds. The cause was a one-line path subtlety: we passed git a *relative* destination while also telling the command to run *inside the destination's parent folder*. Git resolves relative destinations against its working directory — so each clone landed at `clones/detect-46/clones/detect-46/<repo>`, a nested path, while the scan looked at `clones/detect-46/<repo>`. Git exited successfully (exit code 0) the whole time. We reproduced it in a scratch directory in a minute: nested clone, rc=0, destination missing.

**Fix**: both the clone helper and the scan root resolve to absolute paths before anything runs (`src/detect/gitio.py`, `src/detect/git_orchestrator.py`). A regression test now pins the default relative root, and a real-git test clones into a relative destination and asserts the clone lands exactly there. The leftover nested directories from the bug were swept by hand, and the new **Flush repos** button (§9) exists to reclaim this class of leftover in one click.

**Number**: run #7's wall time was 4.8 seconds for 10 repos — the fastest, most useless run in the ledger.

---

## 4. The second wall: nothing retried (runs #11 and #12)

Run #11 lost **9 of 10 clones in 34 seconds**, every one with `Recv failure: Connection was reset`. Run #12, five minutes later, lost **5 of 10** with `Failed to connect`. The network blipped; the pipeline had no retry logic anywhere, so a two-second outage became permanent data loss — 14 repository slots across two runs.

**Fix**: one small retry helper (`retry_call` in `src/detect/gitio.py`) now wraps every network-shaped operation — clone, PR-ref fetch, object fetch, reference listing. Its properties, all deliberate:

| Property | Value | Why |
|---|---|---|
| Attempts | 4 | Survives a ~15–20 s outage window (blip + backoff + retry). |
| Backoff | 1–2 s, 2–4 s, 4–8 s (doubling, jittered) | De-synchronizes parallel workers so retries don't arrive in a clap. |
| Coverage | git failures **and timeouts** | A slow fetch that times out gets a fresh attempt. |
| Interruptibility | sleeps check cancellation every 0.25 s | Pressing Stop works *during* a retry, not after it (a retry could otherwise ignore the stop for up to 16 s — see §9). |

**Fine print that matters**: retries never swallow a failure into silence. After the final attempt the operation reports — and the report carries the *last non-empty stderr line*, e.g. `pull refs fetch failed: fatal: unable to access 'https://github.com/o/r.git/': Failed to connect`. The old note was one opaque sentence with no reason; the new one tells you what GitHub said.

---

## 5. The real discovery: one hidden network trip per commit

This is the section the whole document builds toward. If you read one thing, read this one.

### 5.1 The symptom

Detection #17 — a 10-repository test batch — took **6 minutes 5 seconds**. Earlier runs of the *same ten repositories* had finished in **20 seconds**, so "fast" looked possible. But those 20-second runs were marked **partial**: their PR-refs fetch had failed fast on the giants, leaving the heaviest channel silently empty. In other words, the fast runs were fast because they broke. The complete run was slow because it worked.

### 5.2 The hunt

Instrumenting each stage on the same repositories produced a lopsided table:

| Stage | Time | Verdict |
|---|---|---|
| Clone | ~1.1–1.3 s | fine |
| File channel | 0.8 s | fine |
| History channel | 0.1 s | fine |
| Reference list (`ls-remote`) | 0.6–1.5 s | fine |
| PR-refs fetch | 1.2–2.5 s | fine |
| PR walk (`rev-list`, 8 parallel workers) | 0.1–0.3 s | fine |
| **Read PR commits** | **317–370 s** | **everything** |

Three fresh reproductions of the same repository (`zeta-lang/zeta`, a 0.2 MB repo with 8 pull requests and 452 PR-branch commits): **364.8 s, 369.9 s, 327.7 s** — every time, all of it in the last row.

### 5.3 The cause

The commit-reading step used `git show -s --format=...` — show me this commit's metadata, no diff. What we missed is that `git show` **resolves each commit's tree** (its directory listing) before honoring `-s`. The PR-refs fetch is `--filter=tree:0`: it transfers commits but explicitly **no trees**. So git did exactly what a promisor clone is designed to do — it went to the warehouse. Once per commit. 

Counting the courier trips settled it: **392 separate lazy-fetch packs** appeared in the repository while one commit-reading step ran. On that repository each round trip cost about 0.8 s — 392 × 0.8 s ≈ 317 s, matching the measurement to the second. The walk (0.1 s) was never the problem; the fetch (2.5 s) was never the problem. The tax was **one network round trip per commit, hiding inside a single innocuous command**.

And it was not one repo's quirk. The tax is proportional to a repo's PR-commit count and was paid by **every repository with pull requests** — the ordinary corpus case. A repository with 30 PR commits paid ~25 seconds; the 452-commit one paid ~5.5 minutes. Nothing in any log said so.

### 5.4 The fix

Read commit metadata **without ever touching trees**:

```
git log --no-walk --format=... <sha> <sha> ...
```

`log --no-walk` reads the commit objects and nothing else — no tree, no diff machinery, no courier trip. Same records, same parsing, same evidence.

**Measured, on the exact same reproduction:**

| | Before | After |
|---|---|---|
| PR phase (`zeta-lang/zeta`, fresh clone) | 327–370 s | **3.4 s** |
| Lazy-fetch packs | 392 | 1 (the legitimate PR-refs fetch) |
| Result | status ok, 3 hits | status ok, **3 hits — identical** |

Roughly **100× faster with byte-identical output**, because the optimization removed *network overhead*, not *work*.

### 5.5 The cousin: file contents had the same disease, caught earlier

The same session found a smaller version of this pattern in the file channel. Reading `.gitignore` plus up to five matched files meant up to **six separate lazy fetches** (each 1–3.3 s, measured: three blobs = three courier trips, one every ~3.3 s). GitHub does not serve file-by-path requests directly — a direct "fetch this blob by ID" is refused (`did not send all necessary objects`) — but the **promisor's own batched object fetch** is served, and it takes *every wanted object in one round trip*:

```
git -c fetch.negotiationAlgorithm=noop fetch origin --no-tags \
    --no-write-fetch-head --recurse-submodules=no --filter=blob:none --stdin   (object IDs on stdin)
```

Measured live: three file contents in **one fetch**; and the production path (`.gitignore` + probes, up to six objects) now costs **one round trip per repository** instead of one per file — with a graceful fallback to per-file lazy fetches if the batch fails. Verified end-to-end: a real repo's README fetched in 0.69 s via the batch, then read locally with no further network traffic.

### 5.6 Why nobody noticed

Because every individual step "worked". Lazy fetches succeed — they're a feature. The failure had no error message, no partial flag, no warning. It was **latency wearing an invisibility cloak**, paid in 0.8-second increments 392 times. The lesson (§12, rule 2) is the sharpest one of the session: *on a filtered clone, any command that resolves a tree is a network command, however local it looks.*

---

## 6. The giants: fetching tens of thousands of PR refs without stalls

Some repositories have enormous pull-request histories. `octocat/Spoon-Knife` has **37,494** PR refs; `octocat/Hello-World` has **2,145** (both measured live). The original code fetched every ref in one wildcard request (`+refs/pull/*/head`). For such repositories the server builds one giant pack — and sometimes simply takes minutes to do it: one observed fetch sat **17 minutes with zero bytes written** before completing, and a small repo's 386-object pack was served in **333 seconds cold, then 2.8–6.7 seconds once GitHub cached it** (reproduced twice, then twice fast).

Two changes fixed the whole class:

1. **Size before you fetch.** One cheap `git ls-remote` lists the repo's PR refs (cost: 0.6–1.5 s). Repos with no PRs skip the fetch entirely — a free win for the many repos that have none.
2. **Fetch exactly those refs, in bounded chunks.** Up to 500 explicit refspecs per fetch (a real fetch, not a wildcard the server must expand). Each chunk streams on its own, succeeds or fails on its own, and is retried on its own. Measured live: **2,145 refs arrived in five chunks in 18.2 seconds** (a depth-2 test run — depth and filter behave identically per chunk); and the same chunked path is what now handles 37,494-ref repositories that previously produced one unbounded request.

Then the walking got the same treatment: each PR tip's last-100-commit walk (`git rev-list -n 100`) used to run **one process per pull request, sequentially** — for a 500-PR repository that is 500 process launches. The walk now runs on an 8-worker pool per repository: measured **12 refs in 0.16 s** (again a depth-2 test), and extrapolating the measured per-walk cost to depth 100, a 12,000-PR repository's walks finish in low single-digit minutes where the serial loop needed tens.

One honest note on GitHub's side: a first-time (cold) pack can take minutes regardless of client behavior. The design now absorbs that instead of stalling on it — bounded chunks, per-chunk timeouts (600 s), retries, and every other repository continuing in parallel.

---

## 7. Surviving the machine: storms, disk, and checkpoints

Three more hazards, all observed live.

**The repack storm.** Every git fetch can trigger automatic "housekeeping" (repacking objects). With 32 parallel workers fetching, this turned into **15 simultaneous repack processes** saturating the disk — and the *database* felt it: Postgres connections that normally answer in 10 ms took **1.5–3 minutes**, or hung entirely. The fix is two git settings applied to every scan process environment (`gc.auto=0`, `maintenance.auto=false`), plus `GIT_OPTIONAL_LOCKS=0` to skip pointless lock-taking by read commands. The storm disappeared; the database breathes.

**The disk floor.** The scan used to refuse to start when free space dropped below a fixed reserve (2,048 MB) — a silent whole-run abort on a nearly full machine. Now: the run **warns and keeps scheduling** while space is above the floor, and if space runs low mid-scan it **stops scheduling** new repositories, finishes what is in flight, and records exactly how many repos were scanned versus skipped in its warnings. A run that cannot fit the disk degrades loudly, never silently and never fatally.

**The checkpoint, or: a killed run must not lose its work.** Look at run #15 (a full-corpus attempt): killed by an unlucky machine restart, it had written **34,181 evidence rows across 276 repositories** — and *zero run items*, because rows were only assembled at the end. The evidence was stranded in the database, invisible to every export. Two fixes: (1) each completed repository now writes its `run_items` row immediately (upsert), so a killed run keeps everything it finished; (2) the evidence and item writes share one small transaction per repo. Nothing else changed — a completed run's final snapshot simply replaces the checkpoints, identically.

**The clone itself** got one small trim: `--no-tags` (tag objects are never read by any channel).

---

## 8. Concurrency, dialed in

Detection runs carry their own concurrency setting, `detect_concurrency` (bounds 1–64, default 32, corpus preset 64 — migration `0017`), deliberately separate from the hydration pipeline's limits so turning detection up never disturbs a find. In practice the old code ran git scans at `min(limiter_max_concurrent, 32)` = **18 workers**; the operator setting is now **64**.

What 64 workers buy, measured indirectly: run #15's head-of-corpus slice ran at **~20 repos/min** (276 repos in 13.5 min at 18 workers, ≈ **51 worker-seconds per repo** — dominated, as we now know, by the §5 tax and the §6 serial walks). Removing those two costs is the whole throughput story; the worker count then decides how many of those now-fast repos run at once. Bigger is not automatically better — the machine has 16 cores and one disk — which is why the number is a bounded, operator-visible setting rather than a constant.

---

## 9. The console: stopping in 0.25 s, and reclaiming the disk

**Stop should land the instant you press it.** Three separate latencies were found and removed:

1. The scan loop checked for cancellation every **1.0 s**; it now checks every **0.25 s**.
2. Retry backoff sleeps (up to ~16 s of waiting) ignored the stop; they now wake every 0.25 s (§4).
3. The worst one: after a stop, the run still swept its clone directory — deleting hundreds of megabytes of partially-scanned repositories on Windows, where a locked file turns deletion into a retry loop. The run stayed "running" for the whole sweep. Now a stop **skips the sweep entirely** — the status flips to cancelled immediately — and the leftovers are handed to the explicit tool below. Cancelled runs resume cleanly over the leftovers.

The console also now says what is happening: the status pill reads **Stopping…** and the Stop button is replaced by a short note the moment the request lands (within the 2-second status poll), and cancelling a detection returns you to the detection's own page rather than a search-run page.

**Flush repos** is the new one-click cleaner on the detections page, next to *New detection*. It deletes every leftover `clones/detect-*` directory — except any directory belonging to a queued or running detection, which it never touches. It is the deliberate home for the leftovers that stop-and-resume and interrupted runs produce (and for the residue of the §3 path bug).

---

## 10. What we verified, and the quality bar

Every fix in this document is **exactness-preserving by construction**: batching, parallelizing, or removing overhead — never shortening a window, dropping a ref, or skipping a check. The detection quality bar recorded in `detection-options.md` (99.5% of repos and 98.6% of evidence rows recovered versus the API ground truth) is untouched. Evidence that the bar held:

- The `zeta-lang/zeta` reproduction: **3 hits before, 3 identical hits after** — the 100× fix changed only the clock.
- The 10-repo batch: #17 produced **615 evidence rows, 0 unavailable, zero partial channels** — the first *fully complete* run of that batch on record; its siblings at 20 seconds were the partials (§5.1).
- Full test suite green on the final tree; coverage **94.44%** (gate 93); `ruff`/`black`/`mypy` clean; golden snapshots and the OpenAPI pin regenerated deliberately.
- Live smoke tests, all on real GitHub: chunked PR fetch (2,145 refs / 5 chunks / 18.2 s, depth-2), parallel walk (12 refs / 0.16 s, depth-2), batched object fetch (3 objects / 1 fetch / exit 0), lean clone into a relative destination (lands where asked), `ls-remote` on a 37,494-ref repo.

One more verification lesson, worth its own line: **a run that silently failed its heaviest channel is not a fast run.** The 20-second runs of §5.1 were cited as proof the pipeline was fast; they were proof it was broken. Partial flags and per-repo notes now make that distinction visible — and the retries make the failure mode rare enough that complete runs are the norm.

---

## 11. Before and after, in one table

Per-phase timings on the reproduction repository (`zeta-lang/zeta`, fresh clone each time):

| Step | Before | After | Note |
|---|---|---|---|
| Lean clone | ~1.1 s | ~1.1 s | unchanged |
| File channel | 3–7 s (per-file lazy fetches) | **0.8 s** (one batched object fetch) | §5.5 |
| History channel | 0.1 s | 0.1 s | one log read, now shared with the branch channel |
| Reference list | — | 0.6–1.5 s | new: sizing probe; repos with no PRs skip the fetch |
| PR-refs fetch | 2–5 s, or **minutes** when a mega-pack stalls | **1.2–2.5 s**, bounded chunks | §6 |
| PR walk | ~10–30 s per 500 PRs (one process per PR) | **0.1–0.3 s** (8 workers) | §6 |
| Read PR commits | **327–370 s** (392 lazy fetches) | **3.4 s** (no fetches) | §5.4 |
| **PR phase total** | **~330–375 s** | **~3.4 s** | ≈100× |

Run-level, measured: the 10-repository batch went from **6 min 5 s** (fully complete) or **20 s** (silently partial) to **seconds**, complete. A full 17,795-repository pass, which run #15 projected at **~14 hours** at 18 workers on the old code, is now bounded by GitHub's per-repo serve latency (clone ~1 s, fetch seconds, walk sub-second) across 64 workers — a projection in the low single-digit hours, to be re-measured end-to-end on the next full run.

---

## 12. Rules of thumb (what we'd tell the next engineer)

1. **Measure the phase before optimizing the phase.** The walk looked guilty; the commit read was guilty. Three fresh reproductions and a package-count settled it in an hour.
2. **On a filtered clone, tree access is network access.** Any command that resolves a tree (`show`, diffs, checkouts) pays a courier trip per object unless the data is already local. Read metadata with `log --no-walk`; read contents through one batched object fetch.
3. **Count the round trips, not the commands.** 392 fetches inside one command is one line in a log and five minutes on the clock.
4. **Size a network operation before doing it.** One `ls-remote` per repo costs under a second; knowing whether to fetch 8 refs or 37,494 is worth it every time.
5. **Bound every unit of work so failure is small.** Chunks of 500 refs turn a 17-minute stall into one retried chunk; a 600-second timeout turns infinity into ten minutes.
6. **Retries must be interruptible and must say why they failed.** Sleep in 0.25-second slices so Stop works; carry the last stderr line into the run notes.
7. **A stopped run should stop visibly and immediately.** Skip long cleanups on the cancel path; keep the disk work behind an explicit button.
8. **Checkpoint continuously; assemble at the end.** A killed run should lose seconds, not the run (34,181 stranded rows taught this).
9. **Silence is not speed.** A fast partial is a lie; a slow complete run with honest notes is the product.
10. **Keep exactness by construction.** Batch and parallelize freely; shorten, skip, and drop — never. Every number in §11 came with identical output, which is the only reason any of it was safe to ship.

---

## 13. Glossary

- **Git scan**: the local-clone route for detection — clone each repo, match locally, write evidence. No API quota.
- **Lean clone**: `--depth=100 --filter=blob:none --no-checkout` — recent commits plus directory structure, no file contents.
- **Shallow**: the clone's deliberate history cutoff (100 commits here); walks stop there by design.
- **Filtered clone / partial clone**: a clone that omits some object classes (file contents are omitted here) and fetches them later on demand.
- **Promisor / lazy fetch**: the arrangement that lets git fetch missing objects mid-command — automatically, one round trip per object unless batched. The subject of §5.
- **PR refs**: `refs/pull/N/head` — GitHub stores every pull request's tip as a git reference; fetching them makes PR history walkable without the API.
- **Walk**: `git rev-list` over a commit's ancestry, limited to a depth — here, the last 100 commits of each PR tip.
- **Chunk**: a bounded batch of refspecs (500 here) fetched as one unit, so no single request is unbounded.
- **Checkpoint**: a `run_items` row written as each repository completes, so a killed run keeps finished work.
- **Worker-seconds per repo**: total CPU/wall time spent divided by repos — the honest unit for comparing scans at different concurrency (run #15 measured ~51).
- **Cold pack / warm pack**: GitHub computing an object pack for the first time (minutes, occasionally) versus serving a cached one (seconds). Client-side fix: stay bounded and retry, let other repos proceed.
- **Flush repos**: the console button that deletes leftover clone directories except those of active scans.

---

## 14. Sources

- Detection pipeline, stage by stage — `design/detection-pipeline.md`
- API vs scraping vs git, with the validation numbers — `design/detection-options.md`
- Detection tier boundaries — `docs/detection-tiers.md`
- The console: stop semantics, resume, flushing — `src/serve/detect.py`, `src/serve/templates/detect_list.html`
- The scan implementation — `src/detect/git_orchestrator.py` (loop, chunks, checkpoint), `src/detect/gitio.py` (clone, retries, object fetch, walks), `src/detect/local_channels.py` (channels)
- The commit this document describes — `9afd37e perf(detect): make git scans fast, complete, and stoppable`
- Corpus-building companion (the same style, for the search-and-save pipeline) — `design/corpus-building-efficient-engineering.md`
