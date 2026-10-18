# gitcorpus — Run #99 (Detection #27) Master Report

Generated: **2026-10-18T12:40:00+03:00** · a single-run deep dive of the **first complete
full-corpus git detection**, in the format of `2026-10-18-runs-master-report.md`.
Per-repo evidence pivots are **not** reproduced here — the full per-repo data lives in the
database (`detection_evidence WHERE run_id = 99`, `run_items WHERE run_id = 99`); this report
keeps the aggregates, the analytics that explain them, and the audit findings.

---

## 1. Snapshot identity

| Item | Value |
|---|---|
| Generated at | 2026-10-18T12:40:00+03:00 |
| PostgreSQL | 18.1 on x86_64-windows |
| Database | gitcorpus — **1,984 MB** total (`detection_evidence` 1,763.9 MB, `run_items` 126.3 MB, `runs` 0.6 MB) |
| git HEAD at report time | `a5f09a0` (docs: run 99 detection analysis) |
| Working tree | clean |
| Run under analysis | **id 99, kind detect, status partial** |
| Bundle | `runs/235c6e14447c61ca2a515cef5634f1dcf1a64adf97834d5b9dc4d5d4fb3a3595/99/` |

---

## 2. Executive numbers

| Metric | Value |
|---|---|
| Started / finished | 2026-10-18 04:13:46 → **11:27:41 (+03:00)** — **7 h 13 m 55 s** |
| Repos scanned | **17,757 / 17,757 (100%)** — avg **≈ 41 repos/min** (tail windows 30–62/min) |
| Repos with ≥1 signal | **14,779 (83.2%)**; agentless 2,978 (16.8%) |
| Repos with independent ("anchored") evidence | **13,041 (73.4%)** — see §6 |
| Unavailable | **54 (0.30%)** — all `dead` (`Repository not found`); 0 transient; 0 partial channels |
| Evidence rows | **3,816,399** across 15,229 repos · JSONB payload **411.0 MB** (max row 530 B) |
| Documents | 17,757 × 315 B avg · **5.6 MB** total |
| Overall commit ratio | **20.09%** — the windowed headline pair, pre-FP-correction (§6) |
| Early anomaly | `first_signal_at` = 2016-07-26 (one imported-history repo + one false positive; §6.3) |
| Config | source git · depth 100 · keep=false · channels file/author/branch/bot/commit_trailer/pr_metadata · pack `2026-10-14` · all 63 agents |

Adoption-level mix: pervasive 4,840 · consistent 2,600 · limited 3,709 · experimental 6,540 ·
none 68 (54 dead + 14 empty edge cases).

---

## 3. The run row (all columns)

| column | value |
|---|---|
| id | 99 |
| kind / status | detect / **partial** |
| filter_hash | `235c6e14447c61ca2a515cef5634f1dcf1a64adf97834d5b9dc4d5d4fb3a3595` |
| source_run_id | 87 (import: repos_rust.csv, 17,757 repos) |
| created_at / started_at | 2026-10-18 04:13:46.342 / 04:13:46.350 |
| finished_at | 2026-10-18 11:27:41.213 |
| api_version | 2022-11-28 |
| total_count / fetched / inserted | 17,757 / 17,757 / 17,757 |
| updated / unchanged / skipped | 0 / 0 / 0 |
| incomplete_shards | 1 (partial by design: dead repos) |
| error | none |
| bundle_dir | `runs/235c6e14447c.../99/` |
| progress_* | cleared at completion (normal) |

### 3.1 filter_spec (condensed)

```json
{
  "kind": "detect",
  "source": "git",
  "clone": {"depth": 100, "keep": false},
  "limit": null,
  "pack_version": "2026-10-14",
  "channels": ["file", "author", "branch", "bot", "commit_trailer", "pr_metadata"],
  "windows": {"commits": 100, "prs": 100, "issues": 100},
  "agents": [63 tools, all selected]
}
```

### 3.2 Trace pack

`2026-10-14`: 79 author patterns · 93 file patterns · 20 branch patterns · 4 label patterns ·
84 bot patterns (bots QA-only). Replicated from the Robbes Heuristics Companion; the
`CONVENTIONS.md` exclusion is inherited from the papers' FP validation.

---

## 4. Git provenance

| Event | Commit | Time (+03:00) |
|---|---|---|
| HEAD at run start | `c7a04fd` — serve: flush detection clones in the background with live progress | 04:06:45 |
| Commits landed while this run lived | `8edc49c` — serve: resolve the clones root from the environment | 04:37:41 |
| HEAD at run finish | `8edc49c` | 04:37:41 |
| Landed after completion | `6343c2f` window wording · `a5f09a0` run-99 analysis doc | 11:47 / 12:31 |

The run executed the transport-finish build (merged `dee9c28` train): walk verify default 0
(cap 2, exhausted-exempt), unique-tip walks, in-walker commit records, `tree:0`
destination-less PR fetch at 2,000/chunk with scoped `GIT_NO_LAZY_FETCH`, GitHub-scoped auth
header, monster gate 32, paginated console, retention removal, job-object containment.

---

## 5. Evidence analytics

### 5.1 By channel

| channel | rows | repos | nature |
|---|---:|---:|---|
| `pr_metadata` | 2,624,323 | 11,323 | **derived** (git mode): per-(commit, PR) propagation of commit matches |
| `commit_trailer` | 853,439 | 11,011 | author-pattern hits in commit messages — see §6 |
| `bot` | 183,244 | 4,272 | QA only (excluded from agent counts) |
| `file` | 114,864 | 11,192 | HEAD-tree files + `.gitignore` |
| `author` | 32,803 | 1,100 | author/committer identity fields (login/name/email) |
| `branch` | 7,726 | 1,443 | merge-message heads matching branch conventions |

### 5.2 Agents (non-bot; rows / repos-with-evidence)

| agent | rows | repos | | agent | rows | repos |
|---|---:|---:|---|---|---:|---:|
| Claude Code | 3,011,591 | 11,784 | | Coderabbit | 14,944 | 511 |
| Cursor | 237,126 | 7,939 | | Devin | 13,739 | 307 |
| Copilot | 175,991 | 3,424 | | Amp | 9,202 | 298 |
| Jules | 42,422 | 262 | | ChatGPT | 7,922 | 1,019 |
| Cline | 38,002 | 3,027 | | Gemini | 6,318 | 975 |
| Codex | 35,572 | 2,023 | | Opencode | 5,132 | 671 |
| Generic | 16,636 | 6,872 | | Aider | 4,042 | 326 |

### 5.3 Top repos by evidence rows (full list: DB)

| repo | rows | agents | note |
|---|---:|---:|---|
| gunb-ai/gunbc | 54,576 | 6 | |
| loft-lang/loft | 24,033 | 5 | |
| tokuhirom/mutsu | 19,642 | 6 | |
| jamesc/beamtalk | 17,523 | 9 | |
| wado-lang/wado | 17,301 | 8 | |
| AndrewAltimit/legend-of-legaia-re | 15,849 | 3 | |
| autumn-foundation/autumn | 15,346 | 9 | |
| MikkoParkkola/mcp-gateway | 13,666 | 6 | |

---

## 6. Data-quality audit (the important part of this run)

### 6.1 The false-positive mechanism

`match_commit_messages` runs the **author-channel regex over the entire commit message**
(case-sensitive). Nine single-literal patterns (`cursor`, `cline`, `aider`, `Claude`,
`Copilot`, `ChatGPT`, `Coderabbit`, `junie`, `roomote`) therefore act as vocabulary
detectors in prose. The Robbes papers — which we replicate — define commit heuristics as
**author/co-author identity matching** ("list of known author/co-author names"; the pattern
column is titled "Commit co-author or author") and validate at 2% FP on sampled commits.
Our own design spec says "co-author trailers and 'generated with' footers". The whole-message
scope is a deviation on our side; patterns are the papers'.

### 6.2 Impact

`commit_trailer` rows that merely look like a trailer vs prose-looking
(snippet contains `co-authored` / `generated with|by` / `authored-by:`):

| agent | trailer rows | prose-looking | share | "real trailer" rows / repos |
|---|---:|---:|---:|---:|
| Claude Code | 757,814 | 199,822 | 26% | 393,160 / 6,714 |
| Cursor | 48,744 | 36,620 | **75%** | 12,099 / 924 |
| Copilot | 27,817 | 14,681 | 53% | 12,602 / 831 |
| Cline | 6,366 | 6,178 | **97%** | 161 / 99 |
| ChatGPT | 1,912 | 1,745 | **91%** | — |
| Aider | 638 | 520 | **82%** | 114 / 9 |
| Codex | 2,475 | 550 | 22% | — |
| Amp | 753 | 0 | 0% | — (email-only pattern) |

Repo-level, counting only independent evidence (file / author / branch, or trailer-shaped
rows; `pr_metadata` is derived and inherits the FPs):

| agent | recorded repos | anchored repos | inflation |
|---|---:|---:|---:|
| Cursor | 7,939 | 1,727 | 4.6× |
| Cline | 3,027 | 208 | 15× |
| ChatGPT | 1,019 | 30 | 34× |
| Coderabbit | 511 | 109 | 4.7× |
| Copilot | 3,424 | 1,408 | 2.4× |
| Jules | 262 | 90 | 2.9× |
| Gemini | 975 | 640 | 1.5× |
| Claude Code | 11,784 | 10,365 | 1.1× |
| Codex | 2,023 | 1,858 | 1.1× |
| All agents | 14,779 | 13,041 | 1.13× |

Examples: `EpicGames/lore` "no forward cursor" → Cursor; `…"push declined"` → Cline;
`llmmanorg/llmman` "aider launcher" → Aider. 798 repos have *no* Cursor evidence other than
prose trailer hits. Residual risk: name-field identity matches (`Claude` as a human first
name — 11,032 Claude Code `author` rows on the name field).

### 6.3 The 2016 first signal

`antonperez33/lmdb-zero` — repo **created 2025-09-14** (passes the corpus filter, which is on
repo creation), but a pushed copy of LMDB with its **2016–2017 history preserved**; matched
commit dated 2017-02-15, and the matched signal itself is a `cursor`-in-prose FP
(`assoc_cursor`). Year histogram of repo first signals: pre-2025 = 19 (imports/backdating),
2025 = 935, 2026 = 11,566.

### 6.4 Dead repos (all 54 verified)

Every dead repo (error `remote: Repository not found`) was re-checked live: **REST API 404 on
all 54** (authenticated; 301 excluded → not renames; the first four also 404 anonymously), 52
distinct owners (no bulk privatization), identical failures hours earlier in run 94, and
17,703 unrelated repos cloned fine with the same token. Deleted vs privatized is not
externally distinguishable; both mean out of reach. Full name list: DB (`failure_class = 'dead'`).

### 6.5 Wording corrections shipped

Detect page, git-mode runs: "last N commits on the default branch; every PR ref walked N
commits deep — labels and issues are API-only" (was "N commits · N PRs · N issues", which
implied a 100-PR cap that git mode does not have). API-mode text unchanged; golden-safe.

---

## 7. Throughput timeline (measured from `detected_at` buckets)

| Window | Done | Rate | Notes |
|---|---|---|---|
| 04:13–04:21 | 126 | 16–20/min | monster head; gate 32 live; 0 spawn-storm anomalies |
| 04:21–04:30 | ~130 | ≈0 | **all-walkers wedge** (60+ idle `cat-file`, 9–10 min old) — self-recovered |
| 04:34–04:51 | 248 → 696 | 26/min | recovery; sustained |
| 04:51–11:10 | 967 → 16,795 | 26–30/min | steady; zero new wedges |
| 11:10–11:27 | 17,757 | 30–62/min | tail decile (median 14 PRs) flying |
| Completion | — | — | finalize: delete + re-insert of all run_items (console counter resets — cosmetic alarm) |

Fleet facts throughout: `rev-list` spawns 0; `git log` spawns 0 for walked commits; ≤11
packs/dir; serve RSS ~0.1–0.3 GB (retention removed pre-run); workers ~0.2 GB each;
job-object containment active (zero orphans).

---

## 8. Disk usage of artifacts

| Artifact | Size |
|---|---|
| `runs/<hash>/99/detections.csv` | **669.9 MB** (streamed from DB at completion) |
| `runs/<hash>/99/bundle.json` | 14.1 MB |
| `runs/<hash>/99/corpus.csv` | 0.7 MB |
| DB `detection_evidence` (all runs) | 1,763.9 MB |
| DB `run_items` (all runs) | 126.3 MB |
| Clone root (`%LOCALAPPDATA%\gitcrawl\clones`) | **empty** — run dir swept at completion |

---

## 9. Configuration state (as used)

- `detect_concurrency` 64 (4 processes × 16 threads); monster gate 32; PR-fetch chunk 2,000;
  walk depth 100; verify sampling 0 (cap 2); `GITCORPUS_CLONES_ROOT=%LOCALAPPDATA%\gitcrawl\clones`;
  `GITHUB_TOKEN` present (git HTTPS authenticated; GraphQL points untouched).
- Console: 2 s status polling (bounded); detection page paginated 25 repos × ≤300 evidence rows.

---

## 10. Methodology, definitions & caveats

- **Derived vs independent channels.** In git mode `pr_metadata` is propagation output derived
  from commit matches; it multiplies one match into per-PR rows (69% of all evidence) and
  inherits any upstream false positive. Adoption-style claims in this report use *anchored*
  counts (file/author/branch, or trailer-shaped trailer rows).
- **Snippet-shape classification** (§6.2) is a bounded heuristic over the stored ±30/+70-char
  window, not manual annotation; it bounds, but does not equal, the FP count. Commit-trailer
  emails are redacted to `<email>` at storage time by contract.
- **The FP mechanism is a matching-scope defect**, not a pattern-list defect: the papers'
  lists are safe in their identity-field scope (validated 0.5–1% overall; 2% on commits). The
  planned trailer-scope fix + re-run (~7 h) will replace §6 with clean numbers.
- **"Dead"** = server-said-not-found/unauthorized; verified externally for all 54. Deleted vs
  private is not observable externally.
- Per-repo pivots (all repos, all evidence, all documents) are intentionally omitted; they live
  in the DB for `run_id = 99`. Full narrative: `gitcorpus-detection-session-report-3.md`
  (companion folder) and `docs/findings/2026-10-18-run99-detection-analysis.md`.
