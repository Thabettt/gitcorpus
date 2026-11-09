# Definitive Agent Inventory Decision

**Status:** final research decision  
**Date:** 2026-11-09  
**Decision owner:** GitCorpus research  
**Inputs:** Robbes et al. 2026 baseline (63 agents), the 13 directly measurable candidates from the 2026-11-09 landscape revision, the 16 product audits in [`2026-11-08-agent-fingerprint-research.md`](2026-11-08-agent-fingerprint-research.md), the 2026-11-09 pinned-source audit of 13 catalog candidates (§11), and two All the Agents catalog snapshots (100 harnesses; 100 multiplexers).  
**Related outputs:** [`2026-11-08-agent-fingerprint-landscape.md`](2026-11-08-agent-fingerprint-landscape.md) and [`2026-11-08-agent-fingerprint-landscape-candidates.csv`](2026-11-08-agent-fingerprint-landscape-candidates.csv).

---

## 1. Final decision

Adopt **27 new families now**, hold **3 in a watch tier**, keep **5 agent-adjacent layers separate**, treat **5 incumbents as depth deltas**, and use **1 terminal as a negative control**. Herder is excluded by decision on 2026-11-09. The 2026-11-09 source audit promoted 11 of the 13 audited catalog candidates and left one watch and one without a repo-visible trace.

| Disposition | Count | Products |
|---|---:|---|
| **Add now** | 27 | Builder.io Fusion, cubic, GitLab Duo Agent Platform, Greptile, Kody AI, Lovable, Orca, T3 Code, Paperclip, Hermes Agent, Command Code, Oh My Pi, OpenClaw, Claw Code, Docker Agent, GitHub Agentic Workflows, OpenCodeReview, PR-Agent, DeepSeek Reasonix, Grok Build, Prime Agent, JCode, Xiaomi MiMo Code, Codebuff, oh-my-claudecode, Archon, ralph |
| **Watch** | 3 | Herdr, DeepSeek Harness, claude-flow |
| **Adjacent, separate inventory** | 5 | Azure SRE Agent, BMAD-METHOD, OpenSpec, Ruler, LangGraph |
| **Depth delta, already covered** | 5 | Cursor, Pi, Mistral Vibe, OpenHands, OpenCode v2 |
| **Negative control** | 1 | Ghostty |

**Coverage effect:** the Robbes inventory moves from **63 labels to 93 substantive labels** (+30), or **99 labels** if the 5 adjacent layers and Ghostty are carried in the same catalogue. The 5 depth deltas do not add rows because they are already inside the 63.

---

## 2. Why this is the decision

Robbes et al. define a coding agent as an LLM in a loop with tool access, and measure adoption from repository-visible traces:

- product-specific configuration, rules, or guidance files;
- commit author or co-author identity;
- branch names;
- PR labels and bot/SCM activity.

Their heuristics cover 63 agents and 196 patterns, with reported false-positive rates of 0.5–1%. They explicitly warn that generic files such as `AGENTS.md`, `SKILL.md`, and `agent.yaml` prove a shared format, never the executing product. Stars, downloads, and vendor customer counts are discovery signals, not adoption.

Two consequences drive this decision:

1. **Measurement readiness is not the same as addition value.** The 13 direct candidates are the ones with a product-specific trace today, but 5 of them are not coding agents. They belong in an adjacent inventory, not in the 63-agent denominator.
2. **Wrappers do not inherit adoption.** Orca, T3 Code, and Herdr coordinate downstream agents. Their native artifacts can identify the orchestrator, but a downstream coding agent's commit or PR must remain attributed to that coding agent.

---

## 3. Add now (27)

These families have a native, product-specific trace and add real breadth or depth to the Robbes baseline. They are ordered by layer, not by market size.

| Product | Layer | Native trace lead | Why it is a real addition |
|---|---|---|---|
| **Builder.io Fusion** | Coding agent | `.builderrules`; Builder bot comments/commits | Repo-native visual coding agent with a product-owned config and bot-mediated PR workflow. |
| **cubic** | Review agent | `cubic.yaml`; `@cubic-dev-ai` | Current Code Review Bench leader; adds a review-and-fix surface absent from the 63. |
| **GitLab Duo Agent Platform** | Coding/review platform | Duo service account; `duo/(fix\|feature\|refactor\|docs)/...` branches | The first genuinely non-GitHub platform in the inventory; requires a GitLab channel, not a GitHub regex. |
| **Greptile** | Review agent | `.greptile/config.json`, `.greptile/rules.md`, `greptile.json` | Whole-repository review agent with product-owned configuration. |
| **Kody AI** | Review agent | `kodus-config.yml`; `@kody` commands | Smaller but real self-hosted review bot with a canonical config. |
| **OpenCodeReview** | Review agent | `.opencodereview/rule.json`; `~/.opencodereview/rule.json` | Alibaba's hybrid deterministic-plus-LLM reviewer; the repo-committed project rules are a second strong review-agent surface. |
| **PR-Agent** | Review agent | `.pr_agent.toml` (per-repo and per-directory); legacy `.pr_agent.yaml` | Platform-agnostic PR review across GitHub, GitLab, and Bitbucket with an exact config filename. |
| **Lovable** | App-generation agent | `lovable-dev[bot]`; legacy `gpt-engineer-app[bot]`; `lovable-sync*` | Fills the app-generation gap with an exact bot and recovery-branch identity. |
| **Orca** | Orchestrator | Root `orca.yaml`; legacy `help@stably.ai` trailer only | Adds the worktree/orchestration layer. The legacy trailer must stay legacy-scoped; downstream commits are not Orca evidence. |
| **T3 Code** | Orchestrator / control surface | Repository-declared `t3.json` actions and settings; default `t3/` worktree branch prefix | Pinned audit confirms a repo-visible product config. The `t3/` prefix is corroborating only; downstream commits belong to the controlled agent. |
| **oh-my-claudecode** | Orchestrator | `.claude/omc.jsonc`; `.omc/skills/**`; `.omc-config.json` | Teams-first Claude Code orchestration with a committed project config and committable project skills. |
| **Archon** | Orchestrator / harness builder | `.archon/config.yaml`; `.archon/workflows/*.yaml`; `.archon/packs/<pack>.yaml`; `.archon/sdlc/policy/` | YAML workflow harness; the strongest native orchestration artifact in the multiplexer audit. |
| **ralph** | Orchestration loop | `scripts/ralph/ralph.sh`, `scripts/ralph/prompt.md`, `scripts/ralph/CLAUDE.md`; `prd.json` / `progress.txt` corroborating only | Autonomous loop that spawns Amp/Claude Code; the copied `scripts/ralph/` tree is the product-specific trace, not the generic `prd.json`. |
| **Paperclip** | Coding agent | `.paperclip.yaml` + `schema: paperclip/v1`; `noreply@paperclip.ing`; `paperclip/rescue/...` | Strong exact-email identity plus a content-gated config. |
| **Hermes Agent** | Coding agent | `.hermes.md` / `HERMES.md`; `.hermes/plans/*.md`; `hermes/hermes-<8hex>`; `refs/hermes/archive/<tree>` | Broad native surface across files, branches, and refs. |
| **Command Code** | Coding agent | `.commandcode/settings.json` and subpaths; `noreply@commandcode.ai`; `command-code/<id>` | Strong current product namespace plus exact commit identity and cloud branch. |
| **Oh My Pi** | Coding agent | `.omp/config.yml`; `.omp/agents`, `commands`, `skills`, `tools`, `extensions`; `omp/task/<id>` | Product-specific config and an optional isolation branch; low collision. |
| **OpenClaw** | Coding agent / personal agent | `.openclaw/worktree-setup.sh`; `openclaw/<name>`; `refs/openclaw/...`; `openclaw@localhost` synthetic identity | Native managed-worktree surface, but the shared workspace conjunction must not be used as a singleton. |
| **Claw Code** | Coding agent | `.claw/settings.json` and subpaths; `.claw.json`; `CLAW.md` with product content | Current namespace is strong; contentless `CLAW.md` is unsafe. |
| **DeepSeek Reasonix** | Coding agent | Root `reasonix.toml`; `.reasonix/settings.json`, `.reasonix/skills/`, `.reasonix/commands/`, `.reasonix/agent-presets/definitions/<id>.json` | DeepSeek-native static Go agent with a broad project config surface. |
| **Grok Build** | Coding agent | `.grok/workspaced.toml`; `.grok/plan.md`; `.grok/hooks/` | First-party xAI agent. Use `workspaced.toml` and `plan.md`, not bare `.grok/` or `.grok/settings.json`, which collide with the separate Grok CLI. |
| **Prime Agent** | Coding agent | Project `.prime/agent/settings.json`; user `~/.prime/agent/settings.json` | RLM agent with project settings; it deliberately sets no git identity or co-author, so config is the only trace. |
| **JCode** | Coding agent | Project `.jcode/config.toml`; user `~/.jcode/config.toml` | Memory-efficient Rust agent; project config is documented, but jcode also avoids overriding git identity. |
| **Xiaomi MiMo Code** | Coding agent | `.mimocode/mimocode.jsonc` (or `.json`); `.mimocode/tui.json`; `.mimocode/workflows/`; `.mimocode/skills/` | First-party Xiaomi agent with a deep project config tree. |
| **Codebuff** | Coding agent | `.codebuffignore` / `.manicodeignore`; `Co-Authored-By: Codebuff <noreply@codebuff.com>` | Exact product ignore file and co-author identity; attribution is opt-out, so treat the trailer as default-on but suppressible. |
| **Docker Agent** | Platform / harness | Agent YAML/HCL plus Docker Agent schema or product-specific keys | Adds declarative multi-agent definitions. A generic `agent.yaml` filename alone is not evidence. |
| **GitHub Agentic Workflows** | Platform / harness | Agentic workflow Markdown compiled under `.github/workflows/` | Adds GitHub-native workflow agents distinct from Copilot authorship. |

### 3.1 Why eight of the 13 direct candidates are here

The 13 direct candidates from the landscape were a measurement-readiness shortlist, not an importance ranking. Eight of them are accepted above. The other five are reclassified:

- **Azure SRE Agent** — AIOps, not coding-agent authorship.
- **BMAD-METHOD** — methodology, not an agent.
- **OpenSpec** — spec workflow, not an agent.
- **Ruler** — rules manager, not an agent.
- **LangGraph** — framework, already represented indirectly by LangChain Open SWE in the 63.

---

## 4. Watch list (3)

These are real products with native traces, but the trace is optional, default-off, branch-only, or not safely encodable in the current schema. Keep them visible without counting them as established adoption.

| Product | Layer | Native trace lead | Why it is not in “add now” |
|---|---|---|---|
| **Herdr** | Orchestrator | `worktree/<adjective>-<noun>-<4hex>` | Branch-only and corroborating; the bare `worktree/` prefix is unsafe. Retained because the generated shape is distinctive enough for a corroborating rule. |
| **DeepSeek Harness** | Harness | `dsh-<8hex>-<4hex>` worktrees; `powered_by-dsh` badge | Worktrees and badge are experimental and default-disabled. Useful only as optional/legacy evidence. |
| **claude-flow** | Orchestrator / meta-harness | `.claude-flow/config.json`; opt-in `Co-Authored-By: RuFlo <ruflo-bot@users.noreply.github.com>` | The config directory is routinely gitignored and the commit trailer is opt-in, so neither is a reliable default-on repository signal. |

**Excluded:** **Herder** is not retained. Its strongest signals are a custom `Herder-Session:` trailer and hidden `refs/herder/...` namespaces, neither of which the current schema can encode safely; the synthetic `herder@localhost` identity is ref-scoped, and the remaining branch shape alone is not enough to justify a family row. The audit remains in `2026-11-08-agent-fingerprint-research.md` for reference.

---

## 5. Adjacent inventory (5)

These products are strategically important and measurable, but they are not coding agents. Keep them in a separate catalogue so they do not inflate the 63-agent denominator or the adoption rate.

| Product | Layer | Native trace lead | Decision |
|---|---|---|---|
| **Azure SRE Agent** | AIOps / SRE | `agent.json`, `connectors.json`, `roles.yaml`, and `config/{skills,subagents,hooks}/` as a conjunction | Separate AIOps inventory. Delegated fixes inherit the downstream coding agent. |
| **BMAD-METHOD** | Methodology / SDD | `_bmad/`, `_bmad-output/`; older `.bmad-*` is legacy | Separate methodology inventory. Shared workflow files are not agent authorship. |
| **OpenSpec** | Spec workflow | `openspec/config.yaml`, `openspec/changes/`, `openspec/specs/` | Separate methodology inventory. |
| **Ruler** | Rules manager | `ruler.toml`, `.ruler/` | Separate rules/context inventory. It propagates instructions to other agents. |
| **LangGraph** | Agent framework | `langgraph.json` | Separate framework inventory. LangChain Open SWE already represents the agent layer in the 63. |

---

## 6. Depth deltas (5)

These are already in the Robbes 63. They should improve fingerprint depth and lifecycle handling, not add new families.

| Product | What the research adds | Decision |
|---|---|---|
| **Cursor** | `.cursor-plugin/plugin.json`, `.cursor/config/bugbot.yaml`, `.cursor/BUGBOT.md`, `.cursor/worktrees.json`, `.cursor/environment.json`, `cursoragent@cursor.com`, `cursor/...` | Enrich the existing Cursor row; remove unsupported `CURSOR.md`. |
| **Pi** | `.pi/settings.json`, `.pi/mcp.json`, `.pi/SYSTEM.md`, `.pi/extensions/`, `.pi/prompts/`, `.pi/skills/` | Enrich the existing Pi row. |
| **Mistral Vibe** | `.vibe/config.toml`, `.vibe/hooks/`, `.vibe/skills/`, `vibe@mistral.ai`, `vibe/<name>`, `refs/vibe/reaped/<name>` | Enrich the existing Mistral Vibe row; keep `.vibe/tools/` legacy. |
| **OpenHands** | `.openhands/hooks.json`, `.openhands/memory/MEMORY.md`, `.openhands/agents/`, `openhands@all-hands.dev`, `openhands/<conversation-id>` | Enrich the existing OpenHands row; legacy-scope `.openhands/skills/` and `.openhands/microagents/`. |
| **OpenCode v2** | `opencode.json(c)`, `.opencode/opencode.json(c)`, `.opencode/agents/`, `commands/`, `plugins/`, `tools/`, `skills/` | Treat as the current surface of the existing Opencode family, not a new family. V2 core has no current native branch identity. |

---

## 7. Negative control (1)

**Ghostty** is a terminal, not an agent. It has no native repository marker. Its own `AGENTS.md` and `.agents/` tree are contributor guidance, not evidence that Ghostty authored downstream changes. Keep it as a negative control and attribute all artifacts to the downstream agent.

---

## 8. Coverage math

Robbes' 63 labels are approximately 60 product families plus `Generic`. The decision produces:

| Inventory state | Labels | Notes |
|---|---:|---|
| Robbes baseline | 63 | 2025 snapshot; GitHub-centric |
| + Add now | 27 | 25 agents/orchestrators + 2 platforms |
| **= Strong inventory** | **90** | Product-specific native trace exists |
| + Watch | 3 | Real but optional/default-off/schema-gated |
| **= Substantive inventory** | **93** | +30 over Robbes, about +48% |
| + Adjacent | 5 | Separate catalogue; not coding agents |
| + Ghostty | 1 | Negative control |
| **= Maximum labels** | **99** | Only if all layers share one catalogue |

The five depth deltas are already inside the 63 and do not add rows.

This is breadth, not statistical mass. Codex, Claude Code, Copilot, and Cursor still dominate adoption; the additions mostly land in Robbes' long tail. They improve coverage of GitLab, review agents, app-generation, container/workflow harnesses, and the 2026 orchestration layer. They do not change the 22–28% headline.

---

## 9. Catalog triage: 100 of 553 harnesses

The All the Agents catalog (Prime Radiant) lists 553 coding-agent harnesses; the 100 shown were sorted by GitHub stars. Stars are discovery signals, not adoption, and a catalog entry is not a native trace. The triage below compares each entry against the Robbes 63, the 27 accepted additions, the 3 watch entries, the 5 adjacent layers, and the 163-candidate landscape.

**Result: most of the 100 are not worth adding.** They are already covered, forks or derivatives, wrappers whose commits belong downstream, teaching tools, general agent frameworks, terminals, or telemetry products.

### 9.1 Source-audited and promoted (8)

These were the only entries that combined a plausible native trace with meaningful adoption or a real category gap. All eight passed the pinned-source audit and are now in **Add now** (§3). Evidence is consolidated in §11.

| Product | Stars | Why it was worth the audit | Audit result |
|---|---:|---|---|
| **OpenCodeReview** | 30.8k | Alibaba review agent; hybrid deterministic-plus-LLM pipeline. Review-agent gap. | Add now — `.opencodereview/rule.json` |
| **PR-Agent** | 13.0k | Platform-agnostic PR review agent across GitHub, GitLab, and Bitbucket. | Add now — `.pr_agent.toml` |
| **DeepSeek Reasonix** | 35.6k | DeepSeek-native coding agent distributed as a static Go binary. | Add now — root `reasonix.toml`, `.reasonix/` |
| **Grok Build** | 26.8k | xAI first-party terminal coding agent; distinct from the separate Grok CLI. | Add now — `.grok/workspaced.toml`, narrow |
| **Prime Agent** | 20.9k | Recursive-language-model coding agent with a persistent REPL. | Add now — `.prime/agent/settings.json` |
| **JCode** | 19.8k | Memory-efficient Rust coding agent with swarm and messaging features. | Add now — project `.jcode/config.toml` |
| **Xiaomi MiMo Code** | 13.1k | First-party Xiaomi coding agent with persistent memory and subagents. | Add now — `.mimocode/` config tree |
| **Codebuff** | 12.2k | Multi-agent coding product with CLI, desktop, web, cloud, and chat surfaces. | Add now — `.codebuffignore`, exact co-author |

**Priority order:** OpenCodeReview, PR-Agent, DeepSeek Reasonix, Grok Build, Prime Agent, JCode, Xiaomi MiMo Code, Codebuff.

### 9.2 Worth watching, not auditing yet (4)

| Product | Stars | Reason to wait |
|---|---:|---|
| **Dyad** | 21.6k | Local app builder; real app-generation surface, but Lovable already covers the category and Dyad's native trace is unverified. |
| **ForgeCode** | 7.6k | Real CLI, but lower adoption and no verified product-specific artifact yet. |
| **gptme** | 4.4k | Long-lived general agent CLI; useful history, but not clearly a coding-agent-specific trace. |
| **Melty** | 5.4k | Chat-as-commit model is an interesting native trace, but adoption is small and the product is not clearly a coding harness. |

### 9.3 Not worth adding

- **Already in the Robbes 63 or accepted additions:** OpenCode, Claw Code, Claude Code, Codex CLI, Gemini CLI, Pi, Cline, Warp, Goose, Aider, Cursor, OH-MY-PI, Crush, Qwen Code, Kilo Code, Plandex, Mistral Vibe, Kiro, Sweep, Open SWE, Letta Code, Amplifier, Command Code, Trae Agent, GitHub Copilot CLI.
- **Promoted from this audit:** OpenCodeReview, PR-Agent, DeepSeek Reasonix, Grok Build, Prime Agent, JCode, Xiaomi MiMo Code, Codebuff — see §11.
- **Forks, derivatives, or reimplementations:** Claurst, Zoo Code, Zoo-Code, Tau, little-coder, aider-desk.
- **Teaching or reference tools:** CoreCoder, mini-coding-agent, MiniCode.
- **General agent frameworks, not coding harnesses:** DeerFlow, MetaGPT, ChatDev, Eigent AI, AgentFlow, Prometheus.
- **Terminals, telemetry, or adjacent infrastructure:** Chaterm, Webwright, DevOpsGPT, Superlog, Codex Security, PilotDeck.
- **Wrappers whose commits belong downstream:** OpenChamber, mux, Open Interpreter (already context-only in the 163).

**Decision:** the eight are promoted to **Add now** (§3). The remaining 92 entries are not added: they are already covered, forks, teaching tools, general frameworks, terminals, or wrappers whose commits belong downstream. The catalog changes prioritization, not the acceptance rule.

---

## 10. Agent multiplexer catalog triage

The All the Agents multiplexer catalog lists tools that orchestrate, manage, or run other coding-agent harnesses. The 100-entry snapshot was sorted by GitHub stars. The category is strategically important, but Robbes' attribution rule applies with full force: **a multiplexer does not inherit the downstream agent's commits.** Only native workspace, session, control, or configuration artifacts can identify the multiplexer itself.

**Result: most of the 100 are not worth adding to the coding-agent inventory.** They are wrappers, remote-control shells, terminals, GUI clients, or local-state products whose repository trace is weak or absent.

### 10.1 Source-audited (5): 3 promoted, 1 watch, 1 no trace

These had a plausible native orchestration artifact plus meaningful adoption. They belong in a separate orchestration-layer queue, not the 63-agent denominator. Evidence is consolidated in §11.

| Product | Stars | Why it was worth the audit | Audit result |
|---|---:|---|---|
| **claude-flow** | 72.6k | Large meta-harness around Claude Code and Codex with a planner, neural-pattern layer, and swarm configuration. | Watch — config dir gitignored; trailer opt-in |
| **oh-my-claudecode** | 39.2k | Teams-first orchestration for Claude Code with multiple orchestration modes. | Add now — `.claude/omc.jsonc` |
| **Archon** | 23.5k | Harness builder that encodes development processes as YAML workflows. | Add now — `.archon/` config and workflows |
| **Aperant** | 14.6k | Multi-agent framework running up to 12 agents in isolated worktrees. | No repo-visible trace — `.aperant/` is gitignored |
| **ralph** | 21.8k | Autonomous loop that spawns fresh Claude Code/Amp instances until `prd.json` passes. | Add now — `scripts/ralph/` |

### 10.2 Worth watching, not auditing yet (3)

| Product | Stars | Reason to wait |
|---|---:|---|
| **opcode** | 22.4k | Desktop command center for Claude Code; likely local session state, not a committed repository artifact. |
| **qm** | 15.1k | Multiplayer workspace harness; workspace isolation is real, but the trace may be server-side only. |
| **Agent Orchestrator (AO)** | 12.1k | Desktop workspace unifying 26 agents; useful control surface, but no verified product-specific repo artifact. |

### 10.3 Not worth adding

- **Already in the inventory:** Orca, Herdr, NanoClaw, cmux, Gastown, Paseo, Superset/Paradev, AWS CLI Agent Orchestrator, Omnigent, Claude Squad, Emdash, Agent Teams, OpenChamber, Multica, Happy, JetBrains Air, Orchestrator.inc.
- **Promoted from this audit:** oh-my-claudecode, Archon, ralph — see §11.
- **Remote-control, terminal, or GUI shells:** Kaku, Waku, Calyx, supaterm, dinotty, herdrm, pi-gui, pi-web, codex-mobile, pocketshell, MobileVC, 9remote, WebCode, Pane, harnss.
- **Local-state control planes without a committed artifact:** mission-control, yao, Munder Difflin, hapi, Omnara, OneCLI, AgentBox, Agent-Manager, fanbox.
- **Worktree/session managers that duplicate existing coverage:** Claude Squad, Emdash, dmux, vibe-tree, dev-3.0, ouijit, ORCH, Parallel Code, Ivy Tendril, supacode, vibeyard, agent-deck, arbor, nimbalyst, ai-devkit.
- **General collaboration or telemetry layers:** octo-web, hcom, tutti, solo, hive, the-pair, agentrove, stoneforge, Claudexor, VibePod, VibeKit.
- **Companions or derivatives:** herdrm is a herdr console, not a new family; ralph-wiggum is a SpecKit-style loop derivative.

**Coverage finding:** the landscape's multiplexer category had 190 raw leads but reported only 20. High-star products such as claude-flow (72.6k), oh-my-claudecode (39.2k), and Archon (23.5k) were missed. That is a real discovery gap worth a re-sweep, but it does not justify automatic addition: the acceptance rule remains a pinned, product-specific native trace.

**Promotion:** four entries from this catalog are now in **Add now** (§3): **T3 Code** (22.9k, `t3.json` and default `t3/` prefix), **oh-my-claudecode** (`.claude/omc.jsonc`), **Archon** (`.archon/` workflows), and **ralph** (`scripts/ralph/`). T3 Code's `t3/` prefix and ralph's `prd.json`/`progress.txt` are corroborating only; downstream commits remain attributed to the controlled agent.

**Decision:** the audit resolved the five: three promoted, one watch (claude-flow), and one without a repo-visible trace (Aperant). The substantive inventory moves to 93 labels, with orchestration families counted separately from the 63-agent denominator.

---

## 11. Source-audit results (13 candidates)

**Method:** each repository was pinned and read on 2026-11-09 at its default branch (`main`, `master`, `studio`, `dev`, or `develop` as noted). The audit looked for a repo-visible, product-specific file, identity, branch, or workflow artifact, then checked whether the artifact is committed by design or routinely gitignored. Stars were not used as evidence.

| Product | Repository | Pinned native artifact | Verdict |
|---|---|---|---|
| **OpenCodeReview** | `alibaba/open-code-review` | `.opencodereview/rule.json` project rules (explicitly committable); `~/.opencodereview/rule.json` user layer | **Add now** |
| **PR-Agent** | `qodo-ai/pr-agent` | `.pr_agent.toml` at repo root and per directory; legacy `.pr_agent.yaml` | **Add now** |
| **DeepSeek Reasonix** | `esengine/DeepSeek-Reasonix` | Root `reasonix.toml`; `.reasonix/settings.json`, `.reasonix/skills/`, `.reasonix/commands/`, `.reasonix/agent-presets/definitions/<id>.json` | **Add now** |
| **Grok Build** | `xai-org/grok-build` | `.grok/workspaced.toml`; `.grok/plan.md`; `.grok/hooks/` | **Add now**, narrow |
| **Prime Agent** | `PrimeIntellect-ai/prime-agent` | Project `.prime/agent/settings.json`; user `~/.prime/agent/settings.json` | **Add now** |
| **JCode** | `1jehuang/jcode` | Project `.jcode/config.toml`; user `~/.jcode/config.toml` | **Add now** |
| **Xiaomi MiMo Code** | `XiaomiMiMo/MiMo-Code` | `.mimocode/mimocode.jsonc` (or `.json`), `.mimocode/tui.json`, `.mimocode/workflows/`, `.mimocode/skills/` | **Add now** |
| **Codebuff** | `CodebuffAI/codebuff` | `.codebuffignore` / `.manicodeignore`; `Co-Authored-By: Codebuff <noreply@codebuff.com>` | **Add now** |
| **oh-my-claudecode** | `Yeachan-Heo/oh-my-claudecode` | `.claude/omc.jsonc` project config; `.omc/skills/**` committable; `.omc-config.json` user config | **Add now** |
| **Archon** | `coleam00/Archon` | `.archon/config.yaml`; `.archon/workflows/*.yaml`; `.archon/packs/<pack>.yaml`; `.archon/sdlc/policy/` | **Add now** |
| **ralph** | `snarktank/ralph` | `scripts/ralph/ralph.sh`, `scripts/ralph/prompt.md`, `scripts/ralph/CLAUDE.md`; `prd.json` / `progress.txt` corroborating only | **Add now** |
| **claude-flow** | `ruvnet/claude-flow` | `.claude-flow/config.json`; opt-in `Co-Authored-By: RuFlo <ruflo-bot@users.noreply.github.com>` | **Watch** |
| **Aperant** | `AndyMik90/Aperant` | `.aperant/` and `.auto-claude/specs/` are gitignored; `implementation_plan.json` is local state | **No repo-visible trace** |

### 11.1 Audit notes and encoding constraints

- **Codebuff source correction.** The 163-candidate CSV originally pointed at `CodebuffAI/freebuff`, which does not resolve. The live product repository is `CodebuffAI/codebuff`, and the product is now branded **Freebuff**; this decision retains Codebuff as the family name for continuity. The landscape generator and the regenerated CSV now use the live URL.
- **Grok Build is narrow.** Both Grok Build and the separate Grok CLI use `.grok/`; `.grok/settings.json` is shared. Use only `.grok/workspaced.toml` (the daemon's workspace layer), `.grok/plan.md`, and `.grok/hooks/`. A bare `.grok/` or `.grok/settings.json` is not sufficient.
- **Prime Agent and JCode have no identity trace by design.** Both repositories instruct contributors not to set git identity or `Co-Authored-By` trailers. Their project config is the only signal; do not look for a bot email.
- **Codebuff attribution is default-on but suppressible.** The tool prompt instructs agents to append `Co-Authored-By: Codebuff <noreply@codebuff.com>` unless the repository or user asks for no attribution. Treat the trailer as strong but opt-out, and pair it with `.codebuffignore` where possible.
- **claude-flow is watch, not add.** `.claude-flow/` is routinely gitignored and the `ruflo-bot@users.noreply.github.com` trailer is opt-in. Neither is a reliable default-on signal.
- **Aperant is excluded.** Its workspace and spec directories are deliberately gitignored; `implementation_plan.json` is local execution state. There is no committed project marker to measure.
- **Directory prefixes are unsafe.** Do not use bare `.grok/`, `.jcode/`, `.prime/`, `.mimocode/`, `.archon/`, `.claude/`, `.omc/`, or `.claude-flow/`. Require the specific file or a documented conjunction.
- **ralph needs the script tree.** `prd.json` and `progress.txt` are generic names and unsafe alone. Require `scripts/ralph/ralph.sh` or the `scripts/ralph/` trio.

---

## 12. Implementation rules

1. **Require a product-specific path or conjunction.** Do not use `AGENTS.md`, `SKILL.md`, `agent.yaml`, `MEMORY.md`, `USER.md`, `IDENTITY.md`, `SOUL.md`, or `BOOTSTRAP.md` as standalone attribution.
2. **Prefer exact identities.** Commit author/co-author evidence requires an exact product email or bot login. Do not infer a product from a downstream agent's commit.
3. **Anchor branches and refs.** Caller-supplied names are unsafe. Only generated shapes or product namespaces qualify, and ref-scoped identities need ref scope.
4. **Separate channels.** PR comments, reviews, and bot participation are activity evidence, not proof of code generation. Keep them out of authorship and commit-ratio calculations.
5. **Do not transfer GitHub semantics to GitLab.** GitLab Duo needs a GitLab-native channel: service-account participation and `duo/...` branches.
6. **Carry validity metadata.** Mark current, legacy, deprecated, default-off, recovery-only, and anomalous-when-committed states explicitly.
7. **Report repository-level prevalence.** Raw match counts are not unique repositories and must not be presented as adoption rates.

---

## 13. Open risks

- **Low prevalence.** Herdr, Kody AI, DeepSeek Harness, and several 2026 CLIs may fall below the minimum sample needed for stable estimates.
- **Wrapper attribution.** Orca, T3 Code, Herdr, oh-my-claudecode, Archon, and ralph can look adopted when only the downstream coding agent is doing the work. Their native config and workflow files identify the orchestrator, but generated commits belong to the controlled agent.
- **Schema gaps.** OpenClaw's multi-file workspace conjunction and Paperclip's content-gated YAML cannot be encoded safely in the current pattern model. Herdr's branch shape is corroborating only.
- **Renames and legacy surfaces.** Docker Agent/cagent, OpenCode v2, Lovable's legacy bot, Orca's retired trailer, and the Codebuff→Freebuff product rebrand (with the `CodebuffAI/freebuff` → `CodebuffAI/codebuff` URL correction) need explicit lifecycle handling.
- **Shared `.grok/` namespace.** Grok Build and the separate Grok CLI both use `.grok/`; `.grok/settings.json` is shared. Only `.grok/workspaced.toml`, `.grok/plan.md`, and `.grok/hooks/` are safely attributable to Grok Build, so the family must stay narrow.
- **Config-only identities.** Prime Agent and JCode deliberately set no git identity or `Co-Authored-By` trailer. Their project config is the only signal; do not search for a bot email or infer authorship from the downstream agent.
- **Suppressible attribution.** Codebuff's `Co-Authored-By: Codebuff <noreply@codebuff.com>` trailer is default-on but can be disabled by the repository or user, so it will undercount. Pair it with `.codebuffignore` where possible.
- **Opt-in orchestration signals.** claude-flow's `.claude-flow/` is routinely gitignored and its `ruflo-bot` trailer is opt-in; Aperant's `.aperant/` and `.auto-claude/specs/` are gitignored, leaving no committed project marker.
- **Robbes baseline drift.** The 63-agent list is a 2025 snapshot. The additions will age, and the inventory should be re-reviewed on a fixed cadence.
- **GitLab validation.** GitLab Duo is strategically important but has not been validated at the same repository scale as the GitHub heuristics.

---

## 14. Sources

### Papers

- Robbes, Matricon, Degueule, Hora, Zacchiroli. *Agentic Much? Adoption of Coding Agents on GitHub.* arXiv:2601.18341.
- Robbes, Matricon, Degueule, Hora, Zacchiroli. *Agentic Very Much! Adoption of Coding Agent in New GitHub Projects.* arXiv:2606.07448.
- Robbes, Matricon, Degueule, Hora, Zacchiroli. *Promises, Perils, and (Timely) Heuristics for Mining Coding Agent Activity.* MSR 2026, arXiv:2601.18345.
- Li, Zhang, Hassan. *AIDev: Studying AI Coding Agents on GitHub.* arXiv:2602.09185.
- Giray. *GenAI Adoption Survey.* arXiv:2512.23327.

### Local evidence

- [`2026-11-08-agent-fingerprint-research.md`](2026-11-08-agent-fingerprint-research.md) — pinned product audits, prevalence ledger, and schema limits.
- [`2026-11-08-agent-fingerprint-landscape.md`](2026-11-08-agent-fingerprint-landscape.md) — 163-candidate landscape and Robbes relevance audit.
- [`2026-11-08-agent-fingerprint-landscape-candidates.csv`](2026-11-08-agent-fingerprint-landscape-candidates.csv) — candidate-level trace and relevance fields.
- [`2026-11-08-agent-fingerprint-methodology.md`](2026-11-08-agent-fingerprint-methodology.md) — evidence and schema methodology.
- [All the Agents](https://alltheagents.dev/) — Prime Radiant catalog, 553 harnesses; the 100-entry star-sorted snapshot was triaged on 2026-11-09.
- [`packs/2026-10-19.json`](../../packs/2026-10-19.json) — latest trace-pack baseline.

### Pinned repositories audited on 2026-11-09

Each repository was read at its default branch on 2026-11-09; see §11 for the artifact evidence and verdicts.

- [alibaba/open-code-review](https://github.com/alibaba/open-code-review) — OpenCodeReview (`main`).
- [qodo-ai/pr-agent](https://github.com/qodo-ai/pr-agent) — PR-Agent (`main`).
- [esengine/DeepSeek-Reasonix](https://github.com/esengine/DeepSeek-Reasonix) — DeepSeek Reasonix (`studio`).
- [xai-org/grok-build](https://github.com/xai-org/grok-build) — Grok Build (`main`).
- [PrimeIntellect-ai/prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) — Prime Agent (`main`).
- [1jehuang/jcode](https://github.com/1jehuang/jcode) — JCode (`master`).
- [XiaomiMiMo/MiMo-Code](https://github.com/XiaomiMiMo/MiMo-Code) — Xiaomi MiMo Code (`main`).
- [CodebuffAI/codebuff](https://github.com/CodebuffAI/codebuff) — Codebuff, now branded Freebuff (`main`). This corrects the earlier 163-candidate CSV URL, which pointed at the dead `CodebuffAI/freebuff` repository; the landscape has been regenerated.
- [Yeachan-Heo/oh-my-claudecode](https://github.com/Yeachan-Heo/oh-my-claudecode) — oh-my-claudecode (`main`).
- [coleam00/Archon](https://github.com/coleam00/Archon) — Archon (`dev`).
- [snarktank/ralph](https://github.com/snarktank/ralph) — ralph (`main`).
- [ruvnet/claude-flow](https://github.com/ruvnet/claude-flow) — claude-flow (`main`).
- [AndyMik90/Aperant](https://github.com/AndyMik90/Aperant) — Aperant (`develop`).
