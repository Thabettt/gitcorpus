# Trace pack 2026-11-14: audit and the method for a defensible pack

**Date:** 2026-11-15
**Audited:** `packs/2026-11-14.json` (schema v2: 108 families, 200 rules, 105 rejections) and the uncommitted v2 matcher in the main checkout (`src/detect/structured.py`, `src/detect/attribution.py`)
**Baselines:** `packs/2026-10-14.json`, `packs/2026-10-19.json`, detect runs 101 (pack 2026-10-19, 14,480 repos with evidence), 158 and 159 (search 152)
**Prior internal work:** `2026-11-08-agent-fingerprint-research.md`, `2026-11-13-agent-pack-reaudit.md`, `docs/trace-pack-2026-11-14-guide.md`

---

## 1. Verdict

The family-level design behind 2026-11-14 is sound: a normalized catalogue, lifecycle states, lineage, explicit rejections, and a matcher that can evaluate structured trailers, PR roles and conjunctions. The **rule content does not implement it**. Translating 63 legacy labels into v2 rules dropped whole surfaces for the agents that matter most. The pack has almost no rules for the channel that carries most agent attribution in the literature (commit trailers). And a silent change in path semantics discards configuration in nested directories.

Replaying run 101 through the new rules:

| | repo–agent pairs |
|---|---:|
| Detected by pack 2026-10-19 (excluding `Generic`) | 20,139 |
| Still matched by a 2026-11-14 file or branch rule | 11,192 (56%) |
| Supported only by identity, trailer, PR or issue evidence | 3,341 |
| Lost to path semantics or missing file/branch rules | ~5,600 |

The identity-only pairs could be replayed only partly, because stored trailer snippets redact email addresses. The new pack has co-author rules for just two families (Replit, Abacus), so nearly all of that trailer evidence is gone.

The verdict therefore isn't "the research was wrong". The problem is that **there is no gate between the research and the shipped JSON**: no per-surface completeness check, no regression replay, and no measured precision. Section 5 sets out the method that closes that gap.

---

## 2. How the space looks (late 2026)

External evidence:

- **Khosravani & Mockus, "A Validated Multi-Method Census of 180 Million Repositories" (arXiv 2606.24429, Jun 2026).** Uses four detector types: bot account (A), commit-message signature or trailer (B), author-name suffix such as `(aider)` (C), and config file only (D). Measured precision: A 100% (n=92), B 75–90%, C 79–87%, D 92% for the file being genuine but only 64% for actual use. For Claude Code, bot-account lookup alone undercounts the A∪B union by about 25–30×, so **trailers carry most of the signal**. Cloud agents (Codex, Cursor) land through squash-merged PRs, which erase commit attribution: Codex has 814k PRs in AIDev but only 843 commits in the census. **PR-level evidence is the only channel that sees them.** Config presence is a separate population that shouldn't be merged into activity counts. The paper reports unions as lower bounds.
- **"Debt Behind the AI Boom" (arXiv 2603.28592).** Explicit Git metadata only: actor logins (`copilot-swe-agent[bot]`), author emails (`noreply@anthropic.com`), author names (`Cursor Agent`) and Co-authored-by trailers. Measured 99% attribution precision (n=100). Its rule file (`collection/config/tools.py` in `yueyueL/tech-debt-ai-coding`) covers 29 tools and includes GitHub App noreply forms such as `%+claude[bot]@users.noreply.github.com` and `%+devin-ai-integration[bot]@…`. It counts `Copilot Autofix powered by AI` / `github-advanced-security[bot]` as Copilot.
- **AIDev (arXiv 2602.09185).** 932,791 agentic PRs from Codex, Devin, Copilot, Cursor and Claude Code, identified at PR level.
- GitHub documents that the Copilot coding agent works on a `copilot/` branch, opens a draft PR, and appears as `copilot-swe-agent`.

Our own run 101 (pack 2026-10-19), as repo–agent pairs by channel: file 13,925, **commit_trailer 8,839**, branch 4,470, author 1,175. By agent: Claude Code 10,439, Codex 2,968, Copilot 1,633, Cursor 1,600, OpenCode 643, Gemini 634.

Where the literature agrees:
1. Explicit metadata (bot accounts, trailers, author emails, product branches) is high-precision and must be the backbone.
2. No single channel is enough. Report each channel separately, and report the union as a lower bound.
3. Config files measure *configuration*, not *use*. Keep them as their own census.
4. Detection without signatures (stylometry) isn't precise enough for prevalence work: 0.33 precision in arXiv 2610.36229.
5. Fingerprints drift, so detectors need periodic recalibration against data.

---

## 3. Audit findings on 2026-11-14

### F1. Surfaces dropped in translation (high)
Of 324 legacy patterns, **~105 (~70 after merging escaped/unescaped duplicates) have no v2 rule and no rejection**. Many were explicitly approved by our own research. For example, 2026-11-08 marks Cursor's `cursor/` branch "Yes as anchored regex". Missing, among others:
- **Branches:** `claude/`, `copilot/`, `cursor/`, `devin/`, `jules/`, `goose/`, `windsurf-bot/`, `jetbrains_junie`
- **Bot logins:** `copilot-swe-agent`, `devin-ai-integration`, `gemini-code-assist`, `gemini-cli`, `jetbrains-junie`, `openhands-agent`, `opencode-agent`, `factory-droid[bot]`, `sourcery-ai`, `codegen-sh`, `gru-agent`, `roomote-agent`, `open-swe`
- **Emails:** `codex@openai.com`, `aider@aider.chat`, `cascade@windsurf.ai`, `crush@charm.land`, `qwen-coder@alibabacloud.com`, `roomote@roocode.com`
- **Model-name trailers:** `Claude Opus/Sonnet/Haiku 4.x`, `Claude (GLM/kimi/MiniMax)`, `Codex (gpt-5.2-codex)`, `Gemini 2.5 Pro/Flash`
- **Files:** `GEMINI.md`, `.kimi/`, `.taskmaster/`, `.tessl/`, `.github/workflows/claude`, `memory-bank/`
- **Label:** `codex`

### F2. The trailer channel is essentially empty (critical)
The pack has two `co_author` rules (Replit, Abacus) and five `custom_trailer` rules. There's nothing for Claude Code, Cursor, Copilot, Amp, Aider, OpenHands, Gemini or Codex, even though trailers are our second-largest channel (8,839 pairs in run 101) and the dominant one in the census. The structured matcher supports trailer rules (`_v2_trailer_rule_matches`), so this is purely a content gap.

### F3. PR and bot participation is nearly empty (critical)
There is one `pr_author` rule (a Codex task URL in the PR body), and no rules at all for `pr_commenter`, `pr_reviewer`, `issue_*` or `service_account`. Copilot, Devin, Jules, Factory Droid and the Codex connector act mainly as PR bots, and squash merges leave PRs as their only durable trace. As a result **Copilot and Devin are file-only families** (44 of 78 active families are file-only).

### F4. Path semantics regression: nested configuration is lost (high)
Legacy file patterns matched at any depth (`(?:^|/)\.claude/`). The v2 rules are written as `^\.claude/.+$`, and `path_matches` uses `regex.search` on the full path, so they match at the repo root only. In run 101 that loses **5,771 repo hits for nested `.claude/`**, plus 3,665 for nested `CLAUDE.md`, 1,797 for nested `.pi/`, and smaller counts for nested `.cursor/`, `.codex/`, `.kiro/` and `.windsurf/`. Claude Code and Cursor read nested project configuration in monorepos. Nothing records this change as a decision.

### F5. Directory probes on truncated trees are lost (high)
When a repo tree is truncated, the collector probes literal directory candidates and records paths like `.claude/`. The v2 rules require a child file (`.+$`), so the probe evidence no longer matches: **2,463 repos in run 101** for `.claude/` alone. The collector and the rule semantics disagree.

### F6. Adjacent tools are dropped instead of tagged (medium)
SpecKit (95 repos in run 101), Serena (285) and Taskmaster are `adjacent` with zero rules. Keeping them out of the coding-agent denominator is correct. Not recording them throws away correct, cheap evidence that analysis could still use, such as co-occurrence or workflow studies.

### F7. Confidence and provenance are asserted, not measured (high, defensibility)
All 200 rules say `source_type: official_documentation`, and 192 say `confidence: strong`. No rule records a measured precision, a validation sample, or observed prevalence. "Strong" is an opinion, so a reviewer can't check it.

### F8. Evidence row collapse hides breadth (low)
v2 writes one evidence row per rule per repo, where v1 wrote one per file. The matched paths survive only when several are grouped into `paths`. Evidence row counts are therefore not comparable across pack versions and shouldn't be used as a metric.

### What 2026-11-14 got right (keep)
- Family normalization, lineage, successors and lifecycle validity
- Explicit rejections, such as bare `Copilot` and `abacus-ai-automation[bot]`
- The structured matcher (trailers, PR roles, conjunctions, hidden refs)
- Negative controls
- Separating adjacent and watch families from the active denominator

---

## 4. Decisions needed

1. **Copilot Autofix** (`Co-authored-by: Copilot Autofix powered by AI <…github-advanced-security[bot]…>`). Recommendation: record it as a Copilot *variant* with role `autofix` and keep it out of the coding-agent headline by default. The Debt paper counts it as Copilot, so the choice must be stated either way.
2. **Trailer-only commits** are "agent-touched", not necessarily agent-authored (4.8% of trailer true positives in the census). Report them as a separate role.
3. **Nested configuration.** Recommendation: match at any depth for product-owned directories the product reads at any depth; anchor to the root only where the vendor documents root-only loading. Record the rationale per rule.

---

## 5. The method

### Principle: detect broadly, count narrowly
Detection records every correct trace, tagged with family, category (active, adjacent, legacy…), role and channel. Inclusion rules apply only at analysis time. Nothing correct is discarded at detection time.

### Step 1: one family × surface matrix, with no empty cells
For every family, cover all ten surfaces: file, workflow, branch, hidden ref, author/committer, co-author trailer, custom trailer, PR author, PR reviewer/commenter, issue participant (plus label). Each cell must hold one of:
- one or more **rules**
- a **rejection** with a reason
- **not applicable**, with a reason (for example, an IDE extension that never opens PRs)
- **unresearched**, which blocks the family from reaching `strong`

Store the matrix with the pack and generate it from the rules, so it can't drift.

### Step 2: two kinds of provenance per rule
- **Documented:** a vendor documentation URL with a checked-at date.
- **Observed:** the number of corpus repos in which the exact rule matched, plus 3–5 example permalinks.

A rule with documentation but no observations is `provisional`. One observed in the wild but undocumented, such as a model-name trailer, is acceptable if validation passes. Prevalence comes from our own data, not assertion.

### Step 3: matching conventions (write them once, apply them everywhere)
- **Emails:** anchored full-address regex, plus the GitHub App noreply form `^\d+\+<login>\[bot\]@users\.noreply\.github\.com$`.
- **Bot logins:** exact, normalized for the `[bot]` suffix.
- **Co-author trailers:** name *and* email, or email alone when the email is product-owned. Never a bare name ("Claude" and "Devin" are human names).
- **Branches:** anchored prefix with a non-empty remainder.
- **Paths:** any depth by default for product-owned directories and files; root-only only with a documented reason. Directory probes (`.claude/`) must satisfy directory rules (`kind: directory`).

### Step 4: a frozen, labelled validation set
- A stratified random sample of n=60 per stratum. The top ~10 families by prevalence get one stratum per (family × channel); all other families are pooled into one stratum per channel. Hand-label true positive, false positive or uncertain. For file rules, add a second label: *configuration genuine* vs *evidence of use*. (Correction: an earlier draft copied the census paper's n=30/n=8. With those sizes the 0.90 lower-bound gate below can never be met: 30/30 gives 0.886. 59/60 gives 0.911.)
- **Negative controls:** humans named Claude/Devin/Cody; `cursor[bot]` review comments; repos that only *document* an agent (docs mentioning `CLAUDE.md`); forks; template repos.
- Report precision with Wilson 95% intervals. Gate: a rule ships as `strong` only if the lower bound is at least 0.90. Otherwise it is `corroborating` (it counts only alongside another channel) or rejected.
- Commit the labels with the pack version, so any number in a paper traces back to labelled data.

### Step 5: a regression gate on every pack change (static + replay)
- **Static:** every rule in the previous pack maps to a rule or a rejection in the new one. CI fails on an unmapped rule.
- **Replay:** re-evaluate the new pack against the stored evidence and audit log of the last full run (no API calls). Emit a loss/gain report per family × channel. Every loss above a small threshold needs a written justification that cites a rejection or a validation result.
- This check would have caught F1–F5 before 2026-11-14 shipped.

### Step 6: data-driven discovery each release
Documentation lags the products. Each release, mine the corpus for:
- the most frequent unmatched `Co-authored-by` names and emails
- unmatched `[bot]` logins on PRs
- unmatched top-level dot-directories and `*.md` instruction files
- unmatched branch prefixes on bot PRs

Candidates enter Step 2 and are validated in Step 4. This is how model-name trailers and new tools get picked up without relying on vendor documentation.

### Step 7: reporting
- Per-channel counts and their union, with the union stated as a lower bound.
- Config census separate from activity.
- Adjacent and legacy layers reported separately.
- Squash-merge and trailer-only caveats stated.
- Pack JSON, matrix, labels and replay report published with every dataset release.

---

## 6. Concrete fixes for the next pack version (as a new version, never edit 2026-11-14 in place)

**P0: restore lost high-volume evidence**
1. Co-author rules for Claude Code (`noreply@anthropic.com`, the `claude[bot]` App noreply, the `Claude <model>` name family together with an Anthropic email), Cursor (`cursoragent@cursor.com`, `Cursor Agent`), Copilot (`copilot-swe-agent[bot]` noreply), Amp (`amp@ampcode.com`), Aider (`aider@aider.chat`, author-name suffix `(aider)`), OpenHands (`openhands@all-hands.dev`), Codex (`codex@openai.com`), Gemini and Jules (App noreply forms).
2. Branch rules: `claude/`, `copilot/`, `cursor/`, `devin/`, `jules/`, `goose/`, `windsurf-bot/`.
3. PR-author and service-account rules: `copilot-swe-agent`, `devin-ai-integration`, `google-labs-jules`, `factory-droid`, `chatgpt-codex-connector`, `gemini-code-assist`, `openhands-agent`, `jetbrains-junie`, `sourcery-ai`, `codegen-sh`.
4. Path semantics: any-depth matching for `.claude/`, `CLAUDE.md`, `.cursor/`, `.codex/`, `.pi/`, `.kiro/`, `.windsurf/`, `.gemini/`, `GEMINI.md`, plus directory-kind rules so truncated-tree probes still match.

**P1: completeness and defensibility**
5. Map or reject the rest of the ~70 unmapped legacy patterns.
6. Rules for adjacent families (SpecKit `.specify/`, Serena `.serena/`, Taskmaster `.taskmaster/`), tagged `adjacent`.
7. Build the matrix (Step 1), the observed provenance (Step 2), and the labelled set for the top 10 families (Step 4).

**P2: process**
8. The static and replay gate in CI (Step 5).
9. Discovery mining (Step 6).

Acceptance for P0: replaying run 101 recovers at least the 20,139 legacy pairs, minus pairs dropped through a documented rejection, and validation precision on the new trailer and PR rules has a lower bound of at least 0.90.

---

## 7. Notes on this audit's own limits

- The replay credits only file and branch evidence. Identity and trailer evidence couldn't be replayed exactly, because stored snippets redact email addresses.
- The static comparison between legacy and v2 is heuristic: legacy literals were tested as sample strings against v2 regexes. Treat each listed gap as "needs a decision", not as a confirmed miss.
- The census paper's 30× figure has an internal arithmetic inconsistency (28,154 + 821,824 − 21,971 ≠ 850,157), and its label total (495 vs 485 per cell). Cite the direction, not the exact multiplier, until the replication package is checked.
- The v2 matcher audited here is uncommitted work in the main checkout.
