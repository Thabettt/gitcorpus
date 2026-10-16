# The Three Detection Routes (API, scraping, git — measured and compared)

**Date**: 2026-10-15. Companion to `detection-pipeline.md` (the local-clone method, specified stage by stage) and `how-the-data-flows.md`. Every number below was measured on the 17,757-repo Rust corpus (search run #41) in October 2026, or comes from GitHub's published budgets and rules. The short version of the same findings lives in the field report (thesis folder, `agent-detection-at-scale-explained.html` + its 4-page brief).

## The one-paragraph version

To detect coding-agent traces across 17,757 repositories there were exactly three ways to get the data: **ask GitHub's API**, **scrape the website**, or **download the repositories with git**. The API works and is what the detection feature speaks fluently — but a full scan is a ~13-hour job bound by the GraphQL budget (5,000 points/hour per account), and on its third run it burned the entire hourly budget in 19 minutes, sat still for 36 minutes, and was stopped deliberately at 1,359 of 17,757 repos. Scraping is ruled out twice over: GitHub's own rules disallow the exact pages a crawler would need, and the arithmetic says 1–2 million page loads, one to two weeks at a pace that avoids blocking. **For large corpora, git wins — while the API stays the default and the right tool for small ones**: the data the detector reads lives inside the repository, two commands per repo fetch it in about an hour and ~4 GB with **zero API quota**, and validation against the API run recovered **99.5% of detected repos** — the only real loss being branch names in squash-merging projects (0.5% of repos). Both methods are selectable per run; the options page shows their pros/cons and a size-based estimate for each.

## The decision table

| | Option 1 — GitHub API | Option 2 — HTML scraping | Option 3 — plain git |
|---|---|---|---|
| **Mechanism** | REST + GraphQL calls per repo | one web page per PR/issue | two git commands per repo |
| **Cost, this corpus** | ~53k REST + ~53k GraphQL calls; ~13 h budget-bound | ~1–2 million page loads; 1–2 weeks at 1–2 pages/s | ~1 h wall clock; ~4 GB disk (or <1 GB, scan-and-delete) |
| **Budgets / rules** | 5,000/hr REST and 5,000/hr GraphQL **per account**; secondary abuse limits | `robots.txt` disallows the pages needed; AUP bans excessive bulk activity | sanctioned mechanism; no hourly quota; no token needed for public repos |
| **What you can't get** | nothing much — but you can't get it *in time* | nothing, technically — but slowly, fragilely and against the rules | labels, comment threads, squash-merged branch names |
| **Failure mode** | exits on any interruption in a 13-hour window; stalls half of every hour | rate-limits, challenges, IP blocks (which also hurt the API features) | repo gone → one `unavailable` note; everything else degrades gracefully |
| **Measured outcome** | run #3: stopped deliberately, 1,359/17,757 scanned | never run — ruled out on rules + arithmetic | validated: 99.5% repo coverage, 98.6% evidence rows |
| **Verdict** | **default method** — best for small corpora and gap-filling | no | **second selectable method** — best for large corpora |

## Option 1 — the GitHub API

**How it works.** Per repository: ~3 REST calls (file tree, `.gitignore`, bounded content probes) and ~3 GraphQL calls (commit history, pull requests, issues). That's ~53,000 REST calls and ~53,000 GraphQL calls for this corpus — cheap per repo, impossible in aggregate.

**The budgets are per account, not per token.** REST gets 5,000 requests/hour and GraphQL gets 5,000 points/hour, and *all tokens from one account draw on the same pool*. A second GitHub account (or a separate App installation) is a second pool; a second personal token is not. The two budget pools run in parallel, so the slower one binds: GraphQL, at roughly **13 hours** for this corpus even with perfect luck.

**What run #3 actually did (the measurement).** It burned the entire hourly GraphQL budget in **19 minutes**. From minute one GitHub pushed back: abuse-detection `403`s asking to "retry after 60–300 s", and 35 gateway timeouts (`504`) on the largest PR queries. When the budget hit zero, the local rate limiter put every worker to sleep until the reset — **36 minutes of zero calls and zero progress**. The run was stopped deliberately at 22:35 because a day-long scan isn't practical. It had scanned 1,359 of 17,757 repos and written 41,189 evidence rows across 882 repos — which later became the ground truth for validating the git route (see below).

**Why it fails at this scale.** Not throughput — fragility. A scan that requires 13+ hours of uninterrupted API access is almost certain to be interrupted before it finishes (a crash, an out-of-memory kill, a reboot, a dropped connection), and any interruption costs the entire run. The budget-reset stalls make the effective duty cycle roughly 20 minutes of work per hour. And the heaviest phase — pull requests, 832 calls averaging 5.1 seconds each — is exactly the phase that kept the budget burning fastest.

**Where the API still makes sense.** Small corpora (the first detection run finished in 8 seconds); label and comment signals, which are API-only; one-shot metadata refreshes; and an optional future top-up pass over repos where labels/comments matter — nothing in the measured corpus currently justifies that.

## Option 2 — scraping the website

**How it would work.** The data *is* visible on github.com, so one could fetch pages instead of asking the API — one page per PR or issue, with comments on further pages.

**The rules say no.** GitHub's `robots.txt` disallows exactly the pages a crawl would need — `/*/*/commits/`, `/*/tree/`, `/*/comments` — and points crawlers at the API instead ("If you would like to crawl GitHub, contact us… We also provide an extensive API"). The Acceptable Use Policy separately prohibits "excessive automated bulk activity" that places "undue burden" on their servers. A crawl of this size falls under that description.

**The arithmetic says no.** The API returns a repository's PR history in *one* request; the website serves one page per item. For this corpus that's on the order of **1–2 million page loads**. At a polite pace that doesn't get you blocked (1–2 pages/second), that's **one to two weeks** of crawling — and going faster means rate-limits, CAPTCHA challenges or IP blocks, which would also degrade the API-based features that work fine today. Add the fragility of parsing pages and embedded JSON that change without notice, and the option closes.

**Verdict:** no. The only conceivable use is a few hundred one-off pages where the API has no equivalent at all — not a pipeline.

## Option 3 — plain git (chosen for large corpora — shipped as a second selectable method)

**Why it works at all.** Every channel's data is either repo-native (file tree, commit authors, commit messages, merge-commit branch names) or fetchable as PR refs (GitHub stores every PR's tip at `refs/pull/{n}/head`, which plain git can fetch). Git is the mechanism GitHub designed for distributing repositories; it has no hourly quota, and public repos need no token. The detector was a messenger for data that ships with the code.

**What it costs, measured.** A lean clone (`--depth=100 --filter=blob:none --no-checkout`) keeps the file tree and recent commit metadata while skipping every historical file content. Measured on a 30-repo stratified sample: **0.07–5.4 MB per repo** (a 1.4 GB repo cloned to 0.9 MB), 1–4 seconds each, **~4 GiB projected for the whole corpus if kept — under 1 GB with scan-and-delete**. For reference, full clones would total ~693 GiB (median repo 5.8 MB; the 1,000 biggest repos hold 63% of the bytes; the largest single repo is 24 GB). Total wall time: about an hour at modest concurrency.

**What it recovers, measured against run #3's ground truth.** Every repo the API's PR/branch evidence touched (90 repos) was re-cloned and re-checked:

- **Evidence rows: 40,618 of 41,189 (98.6%)** recovered. The loss is 570 branch names (77% of branch findings) plus a single issue row.
- **Repos: 875 of 882 (99.2%)** have git-visible traces; 3 more come back via their PR commits → **878 of 882 (99.5%)**. The 4 lost repos (0.5%) were visible only as a branch name in a squash-merging project.
- **PR commits: 1,938 of 1,938 (100%)** recovered — 40% from a plain clone, 86% after one PR-refs fetch, 100% after a targeted follow-up for one long-PR straggler.
- **Branch names: 174 of 744 (23%)** via merge-commit messages — 28% in repos that merge with merge commits, **0% in repos that squash or rebase** (the name simply doesn't survive there).

**What it can't get.** Labels and comment threads (API-only; together they produced **one** evidence row in the entire API run) and squash-merged branch names (the 0.5% above). Both are stated in the rollup notes and window labels rather than silently corrected, consistent with `docs/detection-tiers.md`.

**Politeness and failure handling.** Git isn't rate-limited, but the pace stays civil (16–32 parallel clones), reuses the cloner's timeouts, markers and retry conventions, and treats a failed clone as one `unavailable` repo rather than an aborted run. Scan-and-delete keeps disk bounded; `keep: true` allows offline re-scans with future packs — something the API route can never offer.

## Head-to-head (the numbers side by side)

| Measure | API (run #3, measured) | Scraping (arithmetic) | Git (validated) |
|---|---|---|---|
| Operations for 17,757 repos | ~106,000 calls | ~1–2 million pages | ~35,500 git commands |
| Wall time to finish | ~13 h minimum, stall-bound | 1–2 weeks at safe pace | ~1 h |
| Interruption tolerance | any interruption ends the run | IP block ends everything | per-repo; resume skips done repos |
| API quota consumed | 100% of both budgets | none (but blocked anyway) | none |
| Tokens needed | 1 account minimum | none | none |
| Detection coverage (validated) | baseline | n/a | 99.5% of repos; 98.6% of rows |
| Rules/ballpark | sanctioned | disallowed by robots/AUP | sanctioned |

## Why not a hybrid

The two API-only channels contributed one evidence row in the whole measured run, so a per-run hybrid (git plus a tiny API top-up) is unnecessary. Both methods otherwise stay available and user-selectable: the **API remains the default**, local clone is the large-corpus option, and neither replaces the other.

## Where to go next

- `detection-pipeline.md` — the local-clone method specified stage by stage (commands, channels, rollups, lifecycle, codebase map).
- `how-the-data-flows.md` — the Find pipeline whose frozen corpora this process consumes.
- `docs/detection-tiers.md` — what deeper tiers (per-file dates, full-history ratios) would add on top of a clone.
- The field report (thesis folder) — the narrative version of these measurements.
