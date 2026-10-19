# Run 101 (detection #28) — comprehensive analysis

**Generated:** 2026-10-19 · **Run:** 101 · **Source:** search #87 (imported rust corpus, 17,757 repos,
`created:>=2025-02-24`) · **Method:** git-mode local clone scan, depth 100, pack `2026-10-19`.
**Companion:** `2026-10-19-run101-master-report.md` (snapshot numbers); run-99 counterparts
`2026-10-18-run99-detection-analysis.md` / `2026-10-18-run99-master-report.md`.

> Scope: this is the **post-fix re-run of run 99** — same corpus, same spec, new pack and matcher
> semantics. Run 99 quantified a false-positive mechanism; run 101 exists to measure its removal.
> Detection semantics changed deliberately in three places (trailer scope, identity corroboration,
> zero-AI level); everything else is the same pipeline, hardened for the Run-99 wedge and gate
> pathologies.

---

## 1. Headline

| metric | run 99 | run 101 |
|---|---|---|
| Status | partial (54 dead) | partial (58 dead + 4 partial channels) |
| Duration | 04:13:46 → 11:27:41 = **7 h 14 m** | 10:05:11 → 15:31:17 = **5 h 26 m** (scan 5 h 01 m; 25 m of that tail was a cleanup incident, §7) |
| Rate | 40.9 repos/min avg | **54.5/min avg** (peak window ≈76/min) |
| Repos scanned | 17,757 / 17,757 (100%) | 17,757 / 17,757 (100%) |
| Repos with signal | 14,779 (83.2%) | **13,837 (77.9%)** |
| Dead / transient | 54 / 0 | 58 / 0 |
| Evidence rows | 3,816,399 | **3,036,007** (payload 411 → **285 MB**) |
| Overall commit ratio | 20.09% | **18.59%** |
| Earliest first signal | 2016-07-26 (FP + imported history) | **2022-06-19** |

Adoption-level mix: none 9,906 · pervasive 4,512 · limited 1,729 · consistent 1,610 · experimental 0
(run 99: experimental 6,540 · pervasive 4,840 · limited 3,709 · consistent 2,600 · none 68).

---

## 2. Throughput shape

- Head of corpus (monsters) drained continuously at 26–76 repos/min in 15-minute windows; **no
  6–8 minute all-walkers stall**, no idle `cat-file` backlog (oldest child ≈3 min at every
  sampling), no orphaned workers.
- The fleet ran 49–103 live git processes during the scan (clones, chunk fetches, walkers) and
  64 scan threads on 4 processes; the run finished detection in ~5 h 01 m with zero transient
  failures.
- Finalize added ~25 minutes, all of it the read-only-pack cleanup stall (§7) — a deletion bug,
  not a scanning cost. With `2563274` applied, the equivalent tail should be minutes.
- Rate gains vs run 99 (+33%) come from four shipped changes: keep-alive in-process `ls-refs`
  (~1–3 s saved per repo of thread time), pre-probe + dead-skip before cloning, shared per-repo
  `RepoWalkSession` (one `cat-file` child instead of three git children for file/history/PR), and
  the deque scheduler that keeps threads off a saturated monster gate.

---

## 3. Evidence anatomy

By channel (rows, distinct repos):

| channel | rows | repos | run-99 rows | nature |
|---|---:|---:|---:|---|
| `pr_metadata` | 2,392,234 | 9,258 | 2,624,323 | **derived**: per-(commit, PR) propagation of commit matches |
| `commit_trailer` | 261,890 | 7,641 | 853,439 | trailer/footer/**email-salvage** hits only |
| `bot` | 184,048 | 4,291 | 183,244 | QA only, excluded from agent counts |
| `file` | 115,032 | 11,186 | 114,864 | HEAD-tree + `.gitignore` |
| `branch` | 66,140 | 3,629 | 7,726 | merge-message heads **+ live `refs/heads/*`** |
| `author` | 16,663 | 1,113 | 32,803 | identity fields, corroboration-tightened |

Top agents (rows / repos): Claude Code 2,393,840 / 11,237 · Cursor 126,902 / 2,230 · Copilot
125,971 / 2,622 · Codex 101,054 / 3,192 · Jules 40,970 / 264 · Generic 15,100 / 6,606 · Devin
13,697 / 306 · Amp 8,957 / 298 · Opencode 5,116 / 663 · Gemini 3,283 / 716 · Kiro 2,725 / 194 ·
Pi 2,643 / 213.

---

## 4. Comparison anchor: the Robbes papers

The run-99 audit flagged a matching-scope deviation. Before this re-run, all three Robbes papers
were re-read and our implementation checked against them (three papers + the session's audit
hypotheses), with the instruction that agreement is not the goal — correctness is.

**Aligned with the papers:** four heuristic families and pattern counts (79 author / 93 file / 20
branch / 4 label / 63 agents); commit heuristics as *identity/co-authorship* matches; the casing
note ("occasionally using different casings") is now implemented as case-insensitive trailer
matching; bots excluded from metrics; noise filtering (merge/revert/bump); ratio definition
`AI/(AI+human)` with the <1/1–5/5–20/>20% levels; `CONVENTIONS.md` exclusion; propagation of
matched PR commits to the PR author.

**Deliberate divergences (documented, not accidental):**

| Point | Papers | Us | Why |
|---|---|---|---|
| Ratio scope | adoption date → study end | last-100-commit window | lean clones cannot see full history; labelled "windowed intensity" |
| Low activity | analysis filters repos with <10 post-adoption commits | all repos scored | census product; filter downstream when comparing |
| Branch heuristics | PR branch names | + merge messages + live `refs/heads/*` | superset; unmerged agent branches linger |
| PR data | GraphQL (10k PRs, labels, authors, dates) | `refs/pull/*/head` via ls-refs, depth-100 walks | cost; git mode has no label/PR-author channels or PR dates |
| Generic `Token:` lines | not a paper concept | allowlisted tokens + footer phrases anywhere; generic tokens after a blank-line block, **distinctive patterns only** | keeps custom pseudo-headers, kills demonstrated prose FPs |
| First signal | adoption date (file-add or AI commit) | earliest dated hit in window | file hits and most git-mode PR commits are undated |

**Validation gap (unchanged):** the papers validate with a ~400-artifact, two-annotator sample
(370 TP / 8 FP / 19 borderline ≈ 2% FP on commits, 0.5–1% overall). Run 101 is a behavioral
comparison against run 99, not human annotation; that protocol remains the acceptance gate before
quoting adoption rates.

---

## 5. The false-positive mechanism — before and after

### 5.1 What was fixed (implementation summary)

1. **Trailer scope** (`src/detect/attribution.py`): Tier 1 extracts trailer/footer lines only —
   allowlisted trailer tokens and generation footers on any line (line-anchored, quote/bullet/emoji
   tolerant), generic `Token: value` lines only in a real blank-line-separated trailer block and
   only against distinctive patterns. Tier 2 keeps a full-message **email-only** salvage pass so
   unconventional email mentions are never lost. Fast path returns immediately for messages with
   no `@` and no trailer line. One hit per (commit, agent).
2. **Casing + boundaries**: author matching is case-insensitive; the nine ambiguous bare words
   (`aider`, `Claude`, `Copilot`, `cline`, `junie`, `cursor`, `coderabbit`, `ChatGPT`, `roomote`)
   and `Codex` carry `(?<![A-Za-z0-9_-])…(?![A-Za-z0-9_-])` boundaries, so `decline`, `assoc_cursor`
   and `raider` cannot match while `Co-authored-by: Cursor` and `generated with claude code` do.
3. **Identity corroboration**: email and login match by normalized equality for ambiguous words;
   names require email/login corroboration or a multi-token agent pattern — `Jean-Claude Dupont`
   no longer matches Claude Code; `1234+claude[bot]@users.noreply.github.com` now does.
4. **Pack hygiene**: literals escaped (`factory-droid\[bot\]`, `Codex \(gpt-5\.2-codex\)`, email
   dots), `AI [Aa]ssistant` → literal `AI Assistant`, duplicate `codex@openai.com` removed, bare
   `Codex` added — frozen as pack `2026-10-19`.
5. **Two verification-driven corrections** (from the papers cross-check): zero-AI repos now level
   `none` (was `experimental`), and generic `Token:` lines no longer match ambiguous prose
   (`Tests: cursor rendering fixed` no longer hits).

### 5.2 Quantified effect

| indicator | run 99 | run 101 | reading |
|---|---:|---:|---|
| `commit_trailer` rows | 853,439 | 261,890 | −69%: prose vocabulary matches removed |
| Cursor repos | 7,939 | 2,230 | −72% (run-99 anchored estimate 1,727; the extra is casing-recovered genuine trailers) |
| Cline repos | 3,027 | 117 | −96% |
| ChatGPT repos | 1,019 | outside top-18 | 34× repo inflation removed |
| Aider repos | 326 | below top-18 | prose FP removed |
| `author` rows | 32,803 | 16,663 | name-field tightening; repo coverage unchanged (1,100 → 1,113) |
| `branch` rows / repos | 7,726 / 1,443 | 66,140 / 3,629 | live remote-branch coverage added |
| Codex rows / repos | 35,572 / 2,023 | 101,054 / 3,192 | escaped patterns + bare `Codex` recover genuine signals |
| repos with ratio > 0 | 11,149 | 7,851 | pseudo-activity removed; median positive ratio 0.13 → 0.3093 |
| `none` level | 68 | 9,906 | agentless repos correctly non-adopters |
| pre-2025 first signals | 19 | 0 | FP + imported-history artifacts gone |

The two directions (Cursor/Cline collapse, Codex/branch growth) are the intended signature:
precision on prose, recall on genuine trailers and live branches.

---

## 6. Failures and integrity

- **58 dead repos** (0.33%), all `remote: Repository not found`; 52 names overlap run 99's 54
  (persistent deleted/privated repos), 6 additional names failed this time — the class, not the
  code, is the cause. Zero transient failures; zero dialogs; the failure taxonomy worked.
- **4 repos with a partial `pr_metadata` channel** — `Mesh-LLM/mesh-llm`,
  `agentic-os-org/ANOLISA`, `Pinvou/pinvou-agent`, `deeplethe/utopia` — note:
  `pull refs walk failed: fatal: bad object <sha>`. This is the hardened walker behaving as
  designed: a PR head advanced between the ref listing and the fetch, so the listed tip object is
  not in the fetched pack; with lazy fetching disabled the walk fails loudly and the channel is
  marked `partial` (run 99 would have silently lazy-fetched or wedged). **Fix candidate:** fetch by
  the listing-time SHA (`git fetch origin <sha>`) or re-list after fetch; add a regression test.
- **Run status `partial`** is the designed roll-up of the above; `incomplete_shards=1` matches
  run 99's semantics (no data loss — every repo has a document).

---

## 7. The finalization incident

Detection completed at 15:06; finalization appeared hung for ~25 minutes.
`py-spy dump` located the run thread inside `_remove_tree(run_dir)` → `shutil.rmtree` over the
17,699 remaining clone directories. Root cause: Git for Windows marks `.git/objects/pack/*`
read-only; `rmtree(ignore_errors=True)` silently failed on every pack — so per-repo deletions had
failed for the entire run too. Manual remediation (read-only clear + parallel delete) took 99 s and
the run finalized ~2 min later. Permanent fix `2563274` (clear-and-retry handler + regression
test).

Operational notes: the DB remained responsive during the stall; 17,757 `run_items` and 3,036,007
evidence rows were already durable, so **no evidence was at risk** — purely a teardown stall.

---

## 8. Verdict

Run 101 is the first full-corpus detection whose per-agent statistics are clean by construction:
the run-99 false-positive mechanism is gone, the previously-missed casing/broken-literal/branch
signals are recovered, the ratio and first-signal fields no longer inherit prose noise, and the
zero-AI level correction makes the adoption mix honest. Throughput improved 33% while doing more
per repo (live head refs, watchdog, session sharing). The remaining discrepancies against the
papers are documented divergences (windowed ratio, no low-activity filter, git-mode channel gaps)
or pending validation (human-annotated sample).

## 9. Recommended next steps (in order)

1. **Stale-tip race fix** for the 4 partial PR channels (fetch by listed SHA or re-list post-fetch).
2. **Run the deferred gates**: `scripts/verify_walk_equivalence.py` and
   `scripts/verify_detection_replay.py --run-id 99 --pack-version 2026-10-19`, publishing the diff
   taxonomy (expected: FP removals + the two ruled narrowings).
3. **Gate sweep 32/64/128** on a fixed head sample with `GITCORPUS_PHASE_METRICS` enabled; harvest
   per-phase medians and recalibrate the estimator.
4. **Papers' validation protocol**: 400-artifact, two-annotator sample over run-101 evidence.
5. **Console finalize phase**: distinct label + progress so cleanup time never looks like a hang.

Reproduction: run-101 analytics live in the DB (`run_id = 101`); scratch probes and monitors in
`%TEMP%\opencode\gcprobe2\`; the execution ledger in
`gitcrawl/.worktrees/run100/.superpowers/sdd/2026-10-19-run100-accuracy-throughput/progress.md`.
