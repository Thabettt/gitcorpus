# How Detection Works (read this before building the git-first scan)

**Date**: 2026-10-15. Companion to `how-the-data-flows.md`, `detection-options.md`, and `docs/detection-tiers.md`. No prior git-internals knowledge assumed — every concept is introduced where it's first used.

**The document set** (read together — the process, the route choice, the pipeline that feeds it, and what is knowable at each tier):
- This document — the detection process we are implementing, stage by stage, and why each stage exists.
- `detection-options.md` — the three routes we considered (API, scraping, git) and the measurements that picked one.
- `how-the-data-flows.md` — the Find pipeline that produces the frozen repo lists this process consumes.
- `docs/detection-tiers.md` — what is knowable API-only, what needs a clone, what needs BigQuery.

## The one-paragraph version

Detection asks of every repository in a frozen search: *do we see traces of a coding agent having worked here?* The first implementation asked GitHub for the answers over REST and GraphQL and **remains the default method**. This document specifies the **second, user-selectable method — local clone — which downloads each repository with plain git (two commands per repo) and does all matching locally on the checkout**: the file tree, the commit history, the PR tips, and merge-message branch names, matched against a frozen pattern pack. Evidence rows, per-repo rollups and the result summary land in the same database tables the API version writes, so the console, exports and run history are unchanged. Both methods stay available per run and neither replaces the other — the options page shows their pros/cons and a size-based estimate for each. Measured on the 17,757-repo Rust corpus: **about an hour, about 4 GB of temporary disk, zero API calls, no token, and 99.5% of the repo coverage the API run measured**.

## Cast of characters (the only 7 things you must know)

- **Frozen corpus** — a finished Find (e.g. run #41, the 17,757-repo Rust import) whose `run_items` list is the scan order. Detection never searches; it only visits repos it was already given.
- **Trace pack** — a versioned, immutable set of patterns (authors, files, branches, labels, bots) covering the agent roster, frozen into `trace_packs` and referenced by every evidence row. Packs are the research artifact; nothing here changes them.
- **Lean clone** — `git clone --depth=N --filter=blob:none --no-checkout`: the repository's file tree and its last N commits, *without* any historical file contents. Measured at 0.07–5.4 MB per repo on this corpus.
- **PR refs** — GitHub's behind-the-scenes storage of every pull request's tip at `refs/pull/{n}/head`. Fetchable with plain git even when a squash-merge erased those commits from the default branch.
- **Merge-message recovery** — parsing the branch name out of a merge commit ("Merge pull request #123 from owner/claude/fix-login…"). The only way a deleted branch name survives inside the repo.
- **Evidence row** — one `detection_evidence` row: run, repo, agent, channel, evidence JSON, pack version. Same schema as the API implementation, so the same pages read it.
- **Rollup** — the per-repo `run_items.detection` document: agents found, per-channel statuses, commit ratio, adoption level, first-signal date, notes. Also unchanged.

## The journey, stage by stage

```
frozen corpus → Clone lean → Read the tree → Read the history → Fetch PR refs
→ Recover branch names → Match the pack → Roll up per repo → Store evidence → Delete clone → next repo
```

### Stage 0 — Inputs (both frozen, nothing downloaded yet)

Inputs are the source run (must be `done` or `partial`, the same eligibility rule the API version enforces), the pack version, the agent selection, and the channel selection. In git mode the locally supported channels are `file`, `author`, `bot`, `commit_trailer`, `pr_metadata` and `branch`; `label` and `issue` are recorded as *skipped* — they live only in GitHub's PR/issue system and contributed a single evidence row across the entire API run (see `detection-options.md` for the full accounting). The run spec gains a `source` field (`"api"` or `"git"`, default `"api"` — the API method is unchanged) and a `clone` block (`{depth: 100, keep: false}`), so old specs replay exactly as before. The options page presents both methods as selectable cards — pros and cons next to each, plus a size-based estimate computed from the corpus's stored repo sizes (API: calls/hours; local clone: MB/minutes for the selected top-N) — so the choice is informed by corpus size.

### Stage 1 — Clone lean (one command per repo)

```
git clone --depth=100 --filter=blob:none --no-checkout \
  https://github.com/{owner}/{repo}.git  <scan-root>/{owner}__{repo}
```

What lands on disk is the repository's **file tree plus the last 100 commits** — no working-tree files, and `--filter=blob:none` means *no file contents are downloaded at all* until something asks for one specific file (a "promisor" lazy fetch, tiny for text files). Measured on a 30-repo stratified sample: 0.07–5.4 MB per repo, 1–4 seconds each; a 1.4 GB repository cloned to 0.9 MB. A full clone of the corpus *would* be ~693 GiB (median repo is 5.8 MB, but the 1,000 biggest repos hold 63% of the bytes and the largest single repo weighs 24 GB) — the lean mode sidesteps all of that. Why this stage exists: everything the six supported channels read is commit metadata or file paths; the bytes that dominate repository size are history and binaries nobody reads.

### Stage 2 — Read the tree (the file channel)

`git ls-tree -r --name-only HEAD` returns every path in the repository — the same list the API's tree call returned. Paths are matched against the pack's file patterns (`CLAUDE.md`, `.claude/`, `.cursorrules`, `.copilot-*.md`, …); `.gitignore` is read as a blob (`git show HEAD:.gitignore`) so agent files hidden from the repo still count; matched guidance files get a bounded content probe (`git show HEAD:{path}`) for the empty/placeholder check and the Claude Code content weight. Each content probe is one lazy blob fetch — bytes are only paid for files that already matched. Why this stage exists: the file heuristics are the most interpretive channel (config files are deliberate signals), and in the API measurement they touched 721 of 882 detected repos.

### Stage 3 — Read the history (the author, bot and commit_trailer channels)

```
git log -n 100 --format=%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%cI%x1f%B
```

One pass yields everything the API's history query yielded: author and committer names/emails, the committer date, and the full message. Identities are matched against the pack's author and bot patterns (the matchers check `name` and `email` fields; the small set of login-only patterns still resolves through GitHub noreply emails, which embed the login). Commit trailers (`Co-authored-by: Claude…`, casing variants) are matched from the messages. The window is the clone depth — the UI's "last 100 commits" label becomes "the clone window (default: last 100 commits)" and the number is recorded in the run. Committer date (`%cI`) is used for `first_signal_at`, matching the API's `committedDate` semantics. Why this stage exists: in the API measurement, trailers alone produced 22,049 of the 41,189 evidence rows — this stage is the single most productive one.

### Stage 4 — Fetch PR refs (the pr_metadata channel)

```
git fetch --depth=100 --filter=tree:0 origin '+refs/pull/*/head:refs/gc/pr/*'
```

One command asks GitHub for the tip of **every pull request**, downloading commit metadata only (`tree:0` means no trees and no contents — the smallest possible object set). The PR number is preserved in the local ref name (`refs/gc/pr/123`), so a matched commit can be written exactly as the API wrote it: `{"pr": 123, "commit": "<sha>", "propagated": true}`. This is what recovers agent commits that a squash-merge removed from the default branch. Measured recovery against the API ground truth (1,938 distinct commits across 58 repos): **40% found by a plain clone, 86% after this one fetch, 100% after a targeted follow-up** for the single straggler — one repo whose PR history was 300 commits long, fetchable by explicit commit id. Why this stage exists: without it, the 60% of PR-only evidence a plain clone misses would stay invisible; with the API, the same data cost a GraphQL call per repo and helped exhaust the hourly budget.

### Stage 5 — Recover branch names (the branch channel, partial by nature)

Merge commits in the cloned history are parsed for "Merge pull request #N from owner/branch" and matched against the pack's branch prefixes (`claude/`, `codex/`, `devin/`, …), producing the same evidence shape the API wrote: `{"pr": N, "head": "…", "match": "claude/"}`. Measured on the corpus: **174 of 744 branch findings (23%)** — 28% where the project merges with merge commits, **0% where it squashes or rebases**, because those histories contain no trace of the name. Branch findings are corroborating evidence: in 83 of the 90 repos involved, other channels had already detected the agent, and only 4 repos in 882 depended on a branch name alone. Why this stage exists anyway: it is free (the history is already local) and it is the only existing branch-name recovery.

### Stage 6 — Match the pack (one shared matcher set)

All matching runs through the same code the API implementation uses (`src/detect/attribution.py`): case rules, pattern classes, agent-selection scoping, hit de-duplication, noise filtering (merges/reverts/version bumps excluded from the ratio), and email redaction before anything is stored. Nothing about matching is re-implemented; only the *source of the strings* changes — git output instead of HTTP payloads. Why this stage exists: the pack (and the papers it encodes) is the research artifact; sharing the matchers means git-mode numbers are comparable with API-mode numbers **by construction**, and both are validated against each other.

### Stage 7 — Roll up per repo (the same document the UI reads)

The existing rollup builder turns a finished repo scan into the `run_items.detection` document: `agents` (bots excluded), per-channel statuses, `unavailable`, `first_signal_at`, `commit_ratio` (agent vs human commits in-window, with PR-propagated commits folded in), `adoption_level`, and `notes` (which also carry skip reasons, e.g. channels not available locally). Because the shape is identical, the detection detail page, filters and exports work without modification.

### Stage 8 — Store, report, clean up (lifecycle)

Evidence rows are inserted per repo as it finishes (one batch per repo — the same insert the API runner does), and the plan `pending → clone → read → match → insert → delete` is checkpointed per repo so an interrupted run resumes without re-cloning finished repos (the cloner's `.gitcorpus-clone-done` marker pattern). Progress reports through the existing `progress.report("detecting", done, total)`; **Stop** is honored between repos via the same cancellation check the API orchestrator uses; at the end the runner returns the same `RunPayload` (`items`, `result_summary`, `detections`, `warnings`), so `serve/executor.py` and every page behave identically. Deletion is the default (`keep: false`) — each clone is removed right after its scan, which is what keeps peak disk under 1 GB; `keep: true` retains clones so interrupted runs resume and re-scan offline without re-downloading. The cloner's low-disk guard (2 GB reserve, estimated from stored `size_kb`) stays in front of the run. Why this stage exists: it makes a git-mode run *indistinguishable from an API run at the seams* — same tables, same pages, same stop/resume behavior — which keeps the console honest about what was measured either way.

## What each channel keeps (measured against run #3's 41,189 evidence rows)

| Channel | Found by the API | Recovered via git | Lost |
|---|---|---|---|
| `commit_trailer` | 22,049 | 22,049 | — |
| `file` | 8,150 | 8,150 | — |
| `bot` (QA only) | 7,390 | 7,390 | — |
| `author` | 793 | 793 | — |
| `pr_metadata` | 2,062 | 2,062 | — |
| `branch` | 744 | 174 (23%) | 570 (77%) |
| `issue` | 1 | 0 | 1 |
| `label` | 0 | 0 | — |
| **All channels** | **41,189** | **40,618 (98.6%)** | **571 (1.4%)** |

At the repository level — the number that matters for detection — **875 of 882 detected repos (99.2%)** have git-visible traces, and 3 more come back via their PR commits: **878 of 882 (99.5%)**. The 4 lost repos (0.5%) were visible only as a branch name in a squash-merging project. Everything above was re-verified by cloning every repo the API's PR/branch evidence touched (90 repos) and replaying the checks against the real evidence rows — this is a measurement, not an estimate.

## What still needs the API (and why we're fine with it)

- **Labels and issue/PR comments** cannot come from git; they contributed **one evidence row** in the entire API run. Local mode records them as skipped in the rollup notes and the result summary.
- **A future hybrid top-up** remains possible — a small API pass over just the repos where labels/comments matter — but nothing in the measured corpus justifies it by default.
- **Exact GitHub logins** are only partially available (noreply emails embed them); the API run's own matches for the target agent came from `email` and `name` fields, so this costs nothing measurable.

## Measured cost and scale

- **Time**: 1–4 s per repo including reads; ~1 hour for 17,757 repos at modest concurrency (16–32 parallel clones; git has no hourly quota, but keep the pace civil).
- **Disk**: ~4 GiB if all clones are kept (30-repo stratified projection), **under 1 GB peak with scan-and-delete** — this is why the mode exists.
- **Quota**: zero API calls, no token required (public repos).
- **Timeouts and retries**: reuse the cloner's conventions — `GIT_TERMINAL_PROMPT=0`, clean config, a 1,800-second clone timeout by default, retry-then-record-failure semantics.

## Failure handling (the honest limits list)

- **Repo gone / renamed / privatized** → the clone fails; the repo is recorded `unavailable` with a note — the same treatment the API path gives a 404.
- **Empty repository** → zero commits; the history channels return "ok, no hits"; nothing crashes.
- **Giant repositories** → `blob:none` sidesteps the bytes (the 1.4 GB sample cloned to 0.9 MB); tree size grows only with file count, and no sample exceeded 5.4 MB.
- **Very long PR histories** → deepen the fetch per straggler (`--depth` bump or explicit commit fetch); measured to close the last gap.
- **Squash-merged branch names** → permanently lost; this is the 0.5% of repos, stated in the window labels, not silently corrected.
- **Labels and comments** → not available locally; stated as skipped per repo.
- **Windows specifics** → git runs through the same subprocess harness the cloner already uses (Git for Windows, no prompts, no system/global config).

## What changes in the codebase (the map)

- `src/enrich/cloner.py` — add the detection clone mode (`--depth=N --filter=blob:none --no-checkout`) and a mode factor fitted from the 30-repo measurement (~0.006 × repository size); reuse the existing progress, marker, cancel, timeout and low-disk machinery.
- `src/detect/` — add a local source layer that produces the **same intermediates the HTTP channel functions return** (hits + channel status), built from `git ls-tree` / `git log` / `git show` / PR-ref fetches, reusing `attribution.py` untouched; add local `pr_metadata` and `branch` detectors; add a local orchestrator sibling of `run_detection` (or a `source` switch inside it) that walks clones instead of HTTP calls.
- `src/serve/detect.py` and `src/serve/executor.py` — a second runner factory for `"source": "git"` specs; runs stay `kind='detect'` and keep their `source_run_id`; the options page marks `label`/`issue` as unavailable in git mode; the estimate partial switches to clone math (from stored `size_kb`).
- **Unchanged**: `packs/`, `trace_packs`, `detection_evidence`, `run_items.detection`, `result_summary`, all detection pages, exports and the bundle format.

## Where to go next

- Build it: `docs/superpowers/plans/2026-10-15-git-first-detection.md` (T1–T11; tests-first, each task independently reviewable).
- Why this route and not the others: `detection-options.md` (the three routes, measured side by side).
- The narrative version of the measurements: the field report and its 4-page brief (thesis folder, `agent-detection-at-scale-explained.html`).
- What deeper tiers would add (per-file dates, full-history ratios): `docs/detection-tiers.md`.
- The Find pipeline that produces corpora: `how-the-data-flows.md`.
