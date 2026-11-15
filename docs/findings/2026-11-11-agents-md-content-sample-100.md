# `AGENTS.md` content sample: 100 files

- **Date:** 2026-11-11
- **Question:** can the *contents* of `AGENTS.md` attribute a repo to a specific agent, well enough to replace the `Generic` pseudo-agent?
- **Corpus:** detection run #101 (`detection` #29), 17,757 detection documents, 6,606 repos with a `Generic` file hit.
- **Sample:** 100 repos drawn at random (`ORDER BY random()`) from tree-sourced `Generic` file evidence whose path ends in `AGENTS.md`, one file per repo.
- **Fetch:** GitHub contents API, raw media type, 500 KB cap, current `HEAD` (not the scan-time commit).
- **Artifacts:** `%TEMP%\agents_md_sample_100.jsonl` (raw per-file record) and `%TEMP%\agents_md_sample_100_summary.csv` (one row per file).

---

## 1. Headline

Content does **not** solve the attribution problem.

- **42 of 98** fetched files name **no agent product at all** (43%).
- Only **3 of 98** contain an unambiguous single-agent address, and **all 3 already have that agent detected** through another channel.
- **1 of 98** suggests an agent that detection missed (`guixu-project/guixu` → Codex), and that instruction is arguably aspirational.
- Among the **7 Generic-only repos**, content produced **zero** reliable attributions.

A content classifier would therefore move roughly **0 new repos** out of `Generic`, while adding a significant false-positive surface.

## 2. Fetch results

| Status | Files |
|---|---:|
| Fetched | 98 |
| HTTP 404 | 2 |

The two 404s (`Yazelix/mars`, `realchendahuang/DeepMate`) are files present in the scan-time tree but gone at `HEAD`. That is the expected drift between a historical scan and a live fetch.

## 3. How often does the file name a product?

| Products named | Files |
|---|---:|
| 0 | 42 |
| 1 | 29 |
| 2 | 10 |
| 3–4 | 10 |
| 5+ | 7 |

Product mentions skew heavily to Claude Code, then Codex and Cursor:

| Product | Files naming it |
|---|---:|
| Claude Code | 43 |
| Codex | 24 |
| Cursor | 17 |
| Gemini | 9 |
| OpenCode | 8 |
| ChatGPT | 5 |
| Copilot | 4 |
| Sweep | 4 |
| Qwen | 3 |
| Zed | 3 |

Mentions rise with file size, which mostly reflects that tiny stub files have nothing to name:

| File size | Files | Names a product |
|---|---:|---:|
| ≤ 500 chars | 8 | 38% |
| 501–2k | 14 | 36% |
| 2k–10k | 50 | 56% |
| > 10k | 26 | 77% |

Median file size is 5,844 chars; mean 9,437; max 116,634.

## 4. Content vs. detected agents

Of the 98 fetched files, 91 belong to repos with at least one named agent.

| Comparison | Files |
|---|---:|
| Exact agent-set agreement | 11 |
| At least one agent overlap | 47 |
| No overlap but a product is named | 6 |
| No product named, yet a named agent was detected | 38 |

Per-agent recall of content against detection is poor for everything except Claude Code:

| Agent | Files naming it | Repos detected | Both | Content precision | Content recall |
|---|---:|---:|---:|---:|---:|
| Claude Code | 43 | 86 | 42 | 98% | 49% |
| Codex | 24 | 31 | 11 | 46% | 35% |
| Cursor | 17 | 23 | 9 | 53% | 39% |
| Copilot | 4 | 19 | 3 | 75% | 16% |
| Gemini | 9 | 6 | 3 | 33% | 50% |
| Opencode | 8 | 7 | 1 | 12% | 14% |
| Serena | 1 | 5 | 0 | 0% | 0% |
| Jules | 0 | 2 | 0 | — | 0% |

Read the precision column as an upper bound, not as attribution: a file can name a product because the repo *supports* or *documents* it.

## 5. Audit of the strongest content signals

18 files matched an "explicit address" heuristic (phrases such as *you are X*, *guidance for X*, or *use/run X*). Manual reading of all 18:

| Class | Files | Meaning |
|---|---:|---|
| Incidental | 9 | Product appears as a tool, config path, editor enum, or integration |
| Multi-agent | 4 | File explicitly serves several agents |
| Genuine single-agent address | 3 | File is written for one product |
| Subject matter | 1 | Repo is *about* the product |
| Content-only candidate | 1 | File instructs an agent detection missed |

Examples:

- **Genuine single-agent:** `orbistry/alder` starts with `# Claude Code Guidelines for Alder Compiler`; `Dicklesworthstone/toon_rust` says *"if you are Claude Code"*; `iagolavor/inertia` describes Cursor rule activation. All three already have that agent detected.
- **Multi-agent:** `initorigin/io-harness` addresses *"Claude Code, Codex, Cursor, Gemini CLI, Copilot, or whatever comes next"*; `akitaonrails/ai-memory` maps `CLAUDE.md` and `AGENTS.md` across 11 agents.
- **Incidental false positives:** `empathic/clash` matched `zed` from an editor enum; `ryonakae/zerdr` matched `src/zed.rs`; `dekobon/git-remote-object-store` matched Serena as an MCP tool.
- **Subject matter:** `lch5518/CodexPeek` is an inspector for Codex CLI, and has no named agent detected.

## 6. The Generic-only subset

7 repos in the sample had `Generic` and no named agent:

| Repo | Names a product | Verdict |
|---|---|---|
| `gripebomb/ThreatDeck` | no | no signal |
| `NVIDIA/yaml-sigil-spec` | no | no signal |
| `dimitrovakulenko/dwg-mcp-server` | no | no signal |
| `SuperLiaohy/MemRW3` | no | no signal |
| `shadow3aaa/DaatLocus` | Cursor (not addressed) | incidental |
| `tisrop/MergeBeacon` | OpenCode (not addressed) | incidental |
| `lch5518/CodexPeek` | Codex (subject matter) | repo is about Codex |

None yields a defensible attribution. Five name nothing at all; the other two mention a tool they integrate with.

## 7. Interpretation

1. **`AGENTS.md` is a format, not a fingerprint.** Only ~3% of files carry a clean single-agent address, and those repos are already attributed.
2. **Content is mostly shared boilerplate.** Nearly half of files never name a product, including most of the files in repos where multiple agents are detected.
3. **Mentions are dominated by Claude Code.** That reflects the ecosystem's writing conventions (and `CLAUDE.md` interop notes), not Anthropic authorship.
4. **Precision collapses outside Claude Code.** Codex at 46%, Cursor at 53%, Gemini at 33%, OpenCode at 12%.
5. **The detector already beats content.** Path, identity, branch, and PR channels found agents that 38 of these files never name.

## 8. Recommendation

1. **Demote `Generic` to a marker.** Remove it from `detection.agents`; record `generic_markers` separately. Exclude it from `with_agent`, `agent_share`, and every per-agent metric.
2. **Do not add content-based attribution to the pack.** The measured yield is zero reliable additions and a large false-positive surface.
3. **If content is ever used, keep it diagnostic only.** A `generic_hint` field with `explicit | shared | incidental | none` is defensible for research, never for headline adoption.
4. **Expect the correction to be small.** In run #101, demoting `Generic` removes at most the 785 Generic-only repos from any-agent counts; the 5,821 co-occurring repos stay attributed through their named agent.

## 9. Caveats

- Fetches are from current `HEAD`, not the scan-time tree; 2 of 100 had disappeared.
- Detection is itself an imperfect ground truth. "Precision" here means agreement with detection, not verified usage.
- Regex matching for product names is intentionally broad; the manual audit of the 18 heuristic hits is what limits the conclusions, not the mention counts.
- The sample is one `AGENTS.md` per repo, which undercounts repos with many nested instruction files.

## 10. Production outcome

The recommendation was implemented with a narrower rule than the prototype: content
attribution is a **fallback only**, and only when exactly one agent is explicitly
addressed. Bare mentions, subject-matter mentions, and multi-agent files remain
shared markers.

- Classifier: `src/detect/content_attribution.py`, version `agents-md-v1`.
- Channel: `content`, emitted only for generic files (`AGENTS.md` and variants).
- Run #101 backfill: 6,606 documents lost the `Generic` agent; 5,821 kept a named
  agent, 773 became marker-only, and 12 received a content fallback
  (7 Codex, 5 Claude Code).
- Agents in run #101 fell from 13,837 to 13,064 repositories with any agent;
  shared markers remain visible on 6,606 repositories.
- A false positive found during validation, `zed` inside “specialized agents”, is
  now blocked by a word boundary. The weakest prototype attribution
  (`SergKam/FlyCrys`, matched from “code-specific”) was rejected by the stricter
  rule.

All 12 fallbacks match detection-style addressing: ten titles such as
`# Claude Code Guidelines` or `Project Rules (Codex Agents)`, one “when using
Codex CLI” instruction, and one “instructions for coding agents working in Codex
Ruddr”. They are recorded with cue, snippet, confidence, and classifier version
so the fallback can be audited or removed without rescanning.
