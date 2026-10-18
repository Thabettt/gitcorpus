# Run 99 (detection #27) — comprehensive analysis

**Generated:** 2026-10-18 · **Run:** 99 · **Source:** search #87 (imported rust corpus, 17,757 repos,
`created:>=2025-02-24`) · **Method:** git-mode local clone scan, depth 100, pack `2026-10-14`.

> Scope: post-mortem of the first full-corpus git detection after the transport rebuild
> (walk verify off, in-walker commit parsing, `tree:0` PR fetch, gate 32, process containment,
> paginated console pages). Detection **semantics were unchanged** in that rebuild, so the
> false-positive findings below apply equally to runs 93–98.

---

## 1. Headline

| metric | value |
|---|---|
| Status | **partial** (54 dead repos; zero transient failures) |
| Duration | 04:13:46 → 11:27:41 (+03:00) = **7 h 14 m** for 17,757 repos (**≈ 41 repos/min** avg) |
| Repos scanned | **17,757 / 17,757 (100%)** |
| Repos with ≥1 signal | **14,779 (83.2%)**; 2,978 agentless (16.8%) |
| Repos with *independent* evidence (see §6) | **13,041 (73.4%)** |
| Unavailable (dead) | 54 (0.30%), all `Repository not found`, all live-verified 404 (§7) |
| Evidence rows | **3,816,399** across 15,229 repos |
| Overall commit ratio | 20.09% ("pervasive") — contaminated by the FP mechanism (§5) |
| Early anomalies | `first_signal_at` = 2016-07-26 (imported-history repo + false positive; §5.4) |

Adoption-level mix across the 17,757 scanned repos: pervasive 4,840 · consistent 2,600 ·
limited 3,709 · experimental 6,540 · none 68.

---

## 2. Throughput shape (context for the counts above)

- Head of corpus (monster repos): ~12–27 repos/min, one ~6–8 min fleet-wide stall around
  04:21–04:30 (all 64 walkers in the deep-phase at once), recovered to a sustained **~26–30/min**.
- Tail: **30–62 repos/min**; evidence flow 3k–22k rows/min.
- Finalize step (by design) deletes + re-inserts all 17,757 `run_items` from the in-memory
  payload — the console counter resets to 0 and climbs again; looks like "the number went down",
  nothing is lost.
- Ops: 0 orphans (job-object containment active), packs bounded (≤11 packs/dir), no fetch storm,
  `rev-list`/`git log` spawns zero for walked commits.

---

## 3. Evidence anatomy

By channel (rows, distinct repos):

| channel | rows | repos | nature |
|---|---:|---:|---|
| `pr_metadata` | 2,624,323 | 11,323 | **derived** in git mode: per-(commit, PR) propagation of commit matches |
| `commit_trailer` | 853,439 | 11,011 | author-regex hits in commit messages (see §5) |
| `bot` | 183,244 | 4,272 | QA only, excluded from agent counts |
| `file` | 114,864 | 11,192 | config/rules files in HEAD tree (+.gitignore) |
| `author` | 32,803 | 1,100 | author/committer identity fields (login/name/email) |
| `branch` | 7,726 | 1,443 | merge-message branch heads matching agent conventions |

Top agents (non-bot; rows / repos with any evidence):

| agent | rows | repos | agent | rows | repos |
|---|---:|---:|---|---:|---:|
| Claude Code | 3,011,591 | 11,784 | Coderabbit | 14,944 | 511 |
| Cursor | 237,126 | 7,939 | Devin | 13,739 | 307 |
| Copilot | 175,991 | 3,424 | Amp | 9,202 | 298 |
| Jules | 42,422 | 262 | ChatGPT | 7,922 | 1,019 |
| Cline | 38,002 | 3,027 | Gemini | 6,318 | 975 |
| Codex | 35,572 | 2,023 | Opencode | 5,132 | 671 |
| Generic | 16,636 | 6,872 | Aider | 4,042 | 326 |

Channel mix per top agent shows the dependency structure: Claude Code = 2.16 M `pr_metadata` +
758 k trailers + 74 k files + 22 k authors + 2.6 k branches; Cursor = 183 k + 49 k + 3.7 k + 1.4 k;
Codex is the only big tool whose footprint is dominated by **independent** channels
(file 4.8 k + branch 4.4 k vs 2.5 k trailers).

---

## 4. Comparison anchor: the Robbes papers

Our pack replicates their heuristics (`Heuristics Companion`: 79 author / 93 file / 20 branch /
4 label patterns, 63 agents; we also mirror their `CONVENTIONS.md` exclusion).
Their method and numbers:

- Commit heuristics are **authorship/co-authorship by known author/co-author names** —
  e.g. `Co-Authored-By: Claude <noreply@anthropic.com>` — matched against identity/trailer
  content, not free prose.
- Validation: ~400 flagged commits sampled, two annotators: 370 TP / 8 FP / 19 borderline
  (**2% FP**), 0.5–1% overall across artifacts.
- Adoption scale: 15–19% (Oct 2025) of ordinary GitHub projects; 22–28% in the main paper's
  later slice; new projects far higher (71.8–76.2% in the companion's follow-up).

Our raw 83.2% is **not** directly comparable (our corpus is *entirely* young repos created
≥ 2025-02-24, i.e. closer to their "new projects" slice), and it is inflated by the
false-positive mechanism below. The corrected independent-evidence number (73.4%) sits in the
same ballpark as their new-project rates — but the matching-scope bug must be fixed before any
number should be quoted.

---

## 5. The false-positive mechanism (dominant data-quality issue)

### 5.1 Root cause

`commit_trailer` matching in `src/detect/attribution.py::match_commit_messages` runs the
**author-channel regex over the entire commit message**, case-sensitively. The papers define
author heuristics for **identity/co-author fields**, and our own design spec says
"co-author trailers and 'generated with' footers". The shipped scope (whole prose) is the
deviation. Nine author patterns are single literals and therefore behave as vocabulary
detectors in prose:

`cursor`, `cline`, `aider`, `Claude`, `Copilot`, `ChatGPT`, `Coderabbit`, `junie`, `roomote`.

Examples pulled from run 99 (all previously counted as agent evidence):

- `EpicGames/lore`: "…no forward **cursor**…" → **Cursor** (also a 2016-imported repo,
  `antonperez33/lmdb-zero`: `assoc_cursor` → "first signal 2016-07-26")
- `Dicklesworthstone/…`: "…push **declined**…" → **Cline**
- `llmmanorg/llmman`: "refactor(aider): move the **aider** launcher…" → **Aider** (a project
  *about* aider, but not an agent-authored commit)
- `Kuberwastaken/claurst`: "codex / openai-codex **ChatGPT** plans" → **ChatGPT**

A second wrinkle: matching is case-sensitive, so the bare `cursor` pattern *misses* the
capitalized "Co-authored-by: **Cursor**" name (real trailers matched via the email pattern,
which storage redacts to `<email>`), while still catching lowercase prose. Worst of both.

### 5.2 Quantified impact (run 99)

`commit_trailer` rows that even resemble a trailer (`co-authored` / `generated with/by` /
`authored-by:` in the snippet window) vs prose-looking:

| agent | trailer rows | prose-looking | prose share | "real trailer" rows (trailer + agent name) | repos |
|---|---:|---:|---:|---:|---:|
| Claude Code | 757,814 | 199,822 | 26% | 393,160 | 6,714 |
| Cursor | 48,744 | 36,620 | **75%** | 12,099 | 924 |
| Copilot | 27,817 | 14,681 | 53% | 12,602 | 831 |
| Cline | 6,366 | 6,178 | **97%** | 161 | 99 |
| ChatGPT | 1,912 | 1,745 | **91%** | — | — |
| Aider | 638 | 520 | **82%** | 114 | 9 |
| Codex | 2,475 | 550 | 22% | — | — |
| Amp | 753 | 0 | 0% | — | — (email-only pattern; clean) |

### 5.3 Repo-level footprint correction

Because git-mode `pr_metadata` is **derived** from the same commit matches, it inherits the
contamination. Counting only *independent* evidence (file / author / branch, or trailer-shaped
trailer rows):

| agent | recorded repos | anchored repos | retention |
|---|---:|---:|---:|
| Claude Code | 11,784 | 10,365 | 88% |
| Codex | 2,023 | 1,858 | 92% |
| Copilot | 3,424 | 1,408 | 41% |
| Cursor | 7,939 | **1,727** | **22%** |
| Cline | 3,027 | **208** | **7%** |
| ChatGPT | 1,019 | **30** | **3%** |
| Coderabbit | 511 | 109 | 21% |
| Gemini | 975 | 640 | 66% |
| Devin | 307 | 141 | 46% |
| Amp | 298 | 207 | 69% |
| Generic | 6,872 | 6,589 | 96% |
| **All agents** | **14,779** | **13,041** | **88%** |

798 repos (of Cursor's 7,939) have *no* Cursor evidence other than prose trailer hits.

### 5.4 Secondary contamination

- **Author-name matches**: `Claude Code` has 11,032 `author` rows matched on the **name** field
  (pattern `Claude` matches human authors named Claude); Aider 353 name rows; Copilot 2,086.
  Email/login-backed matches are the trustworthy subset.
- **First-signal dates**: 19 repos show pre-2025 signals (2016×1, 2017×1, 2020×1, 2022×2, 2023×4,
  2024×11) — imported/backdated histories; combined with a prose FP this produced the headline
  "2016" first signal. 2025: 935 repos, 2026: 11,566.
- **Derived-row dominance**: 69% of all evidence rows (2.62 M of 3.82 M) are `pr_metadata`
  propagation rows. They multiply a single commit match into per-PR rows and should be treated
  as derived in any adoption counting or display.

---

## 6. Failures and integrity

- **54 dead repos** (0.30%): all `remote: Repository not found` at scan time; **all 54 verified
  live via the GitHub REST API = HTTP 404 authenticated** (no 301 → not renamed; 52 distinct
  owners → not one org privatizing). Deleted vs privated is not externally distinguishable.
  Same names also failed in run 94 hours earlier → persistent, not transient.
- 0 transient/network failures; 0 `partial` channel results (`partial_channels = {}`);
  run status "partial" is *only* due to dead repos by design.
- Evidence for 54 dead + 2,978 agentless repos exists as documents with explicit
  `unavailable` / empty `agents` — no silent drops.

---

## 7. Verdict

The run itself is a **clean full-corpus pass**: 100% coverage, 7 h 14 m, 0 infrastructure
failures, bounded memory/process behavior, verified-dead accounting.

Its *statistics*, however, are materially contaminated by the `commit_trailer` scope bug:
Cursor, Cline, ChatGPT, Aider, Coderabbit and (less so) Copilot repo counts are inflated
— Cursor ~4.6×, Cline ~15×, ChatGPT ~34× at repo level — and `commit_ratio`, per-repo agent
lists, and `first_signal_at` inherit the noise. Claude Code's footprint is mostly genuine
(88% anchors; its dominant risk is name-field and prose-mention matches), and Codex/Amp are
largely clean.

## 8. Recommended fixes (in order)

1. **Trailer-scope fix** in `match_commit_messages`: match only trailer-shaped lines
   (`Co-authored-by:`, `Generated with/by …`, `authored-by:`), case-insensitively (the papers
   explicitly note casing variance). Regression tests: LMDB-style prose must not match; a real
   `Co-authored-by: Cursor <cursoragent@cursor.com>` must.
2. **Name-field tightening** for single-literal author patterns (require email/login evidence or
   a two-token name like "Claude Code"); quantify Claude Code impact.
3. **Mark derived channels**: `pr_metadata` propagation rows should not count as independent
   evidence in adoption headlines or ratios, and the console should say "derived".
4. **Re-freeze the pack** semantics (new version) and **re-run** to replace run-99 stats
   (~7 h), or accept a forward-only fix for future runs.
5. **Keep the papers' validation loop**: sample ~400 flagged commits after the fix and measure
   FP rate (their protocol), as the acceptance gate for quoting adoption numbers.

Reproduction: analysis queries live in
`%LOCALAPPDATA%\Temp\opencode\gcprobe\run99_analysis.py`, `run99_fp_audit.py`,
`run99_fp_audit2.py`, `run99_real_trailers.py` (read-only, run with the repo venv).
