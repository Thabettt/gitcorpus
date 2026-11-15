# Coding-agent pack inventory: 63 → 90

**Status:** reference inventory for the next pack  
**Current pack:** [`packs/2026-10-19.json`](../packs/2026-10-19.json)  
**Addition source:** [`2026-11-09-agent-inventory-final-decision.md`](findings/2026-11-09-agent-inventory-final-decision.md)  
**Counts:** 63 current + 27 add-now families = **90 agents**. The 3 watch-tier families, 5 adjacent layers, 5 depth deltas, and the negative control are intentionally outside the 90.

## Roster at a glance

**Current 63 — already in the pack:** Aider · Alibaba Lingma · AmazonQ · Amp · Atlassian Rovodev · Augment Code · Azad · Baidu Comate · Brokk · Charlie · ChatGPT · Claude Code · Cline · Codebuddy · Codegen · Coderabbit · Codex · Continue · Copilot · CopilotSwe · Crush · Cursor · Deepsource · Devin · Factory · Factory Droid · Fly · Gemini · Generic · Goose · GPT-Engineer · Gru · Jules · Junie · Kilo Code · Kiro · Langchain Open SWE · Letta Code · Microsoft Amplifier · Mistral Vibe · Ona · Opencode · OpenHands · Phoenix · Pi · Plandex · Qodo · Qwen Coder · Roo Code · Rulesync · Sentry Seer · Serena · Sketch · Sourcery · SpecKit · Sweep · Taskmaster · Tessl · Trae · Verdent · Warp · Windsurf · Zed

**Add-now 27 — bring the pack to 90:** Builder.io Fusion · Paperclip · Hermes Agent · Command Code · Oh My Pi · OpenClaw · Claw Code · DeepSeek Reasonix · Grok Build · Prime Agent · JCode · Xiaomi MiMo Code · Codebuff · cubic · Greptile · Kody AI · OpenCodeReview · PR-Agent · GitLab Duo Agent Platform · Lovable · Orca · T3 Code · oh-my-claudecode · Archon · ralph · Docker Agent · GitHub Agentic Workflows

## How the pack detects an agent

| Channel | Fingerprint type | Examples |
|---|---|---|
| **Files** | Repository-committed configuration, rules, instructions, or product-owned directories | `.cursor/`, `CLAUDE.md`, `.aider.conf.yml` |
| **Identity** | Commit author, committer, or co-author identity | `noreply@anthropic.com`, `copilot-swe-agent` |
| **Branch / PR** | Product-owned branch prefixes and pull-request labels | `codex/`, `claude/`, `ai-generated` |

A single agent can use several channels. The pack treats them as corroborating evidence, not as separate agents. Generic files such as `AGENTS.md` prove a shared format, not a specific product.

## Current pack — 63 agents

Alphabetical. Fingerprints are the patterns currently shipped in `packs/sources/2026-10-19/*.csv`.

- **Aider** — **Files:** `aider.conf.yaml`, `aider.conf.yml`, `.aider.conf.yaml`, `.aider.conf.yml`, `.aiderignore`, `.aider/`, `.aiderrules`; **Identity:** `aider`, `aider@aider\.chat`
- **Alibaba Lingma** — **Files:** `.lingma/`
- **AmazonQ** — **Files:** `.amazonq/`, `AmazonQ.md`, `AMAZONQ.md`
- **Amp** — **Files:** `AGENT.md`, `.sourcegraph/`; **Identity:** `amp@ampcode\.com`; **Branch / PR:** `^amp$`
- **Atlassian Rovodev** — **Files:** `.rovodev/`
- **Augment Code** — **Files:** `.augment/`, `.augmentignore`, `.augment-guidelines`
- **Azad** — No dedicated pack pattern.
- **Baidu Comate** — **Files:** `.comate/`
- **Brokk** — **Files:** `.brokk/`
- **Charlie** — **Files:** `.charlie/instructions/`
- **ChatGPT** — **Identity:** `ChatGPT`, `chatgpt@chatgpt\.com`, `chatgpt@openai\.com`, `chatGPT@no-reply\.com`
- **Claude Code** — **Files:** `CLAUDE.md`, `.claude/`, `.anthropic/`, `.claudeignore`, `.github/workflows/claude`; **Identity:** `Claude`, `noreply@anthropic\.com`, `claude@anthropic\.com`, `assistant@anthropic\.com`, `Claude Opus 4\.5`, `Claude Opus 4\.6`, `Claude Haiku 4\.5`, `Claude Sonnet 4\.5`, `Claude \(glm-4\.7\)`, `Claude \(GLM-4\.7\)`, `Claude \(glm-4\.6\)`, `Claude \(GLM-4\.6\)`, `Claude \(kimi-for-coding\)`, `Claude \(kimi-k2\.5\)`, `Claude \(MiniMax-M2\.1\)`; **Branch / PR:** `claudecode/`, `claudecode/`, `claude/`
- **Cline** — **Files:** `.clinerules`, `.cline/`, `memory-bank/`, `memory_bank/`; **Identity:** `cline`, `cline@example\.com`
- **Codebuddy** — **Files:** `CODEBUDDY.md`
- **Codegen** — **Identity:** `codegen-sh`; **Branch / PR:** `codegen-bot/`
- **Coderabbit** — **Identity:** `coderabbit`; **Branch / PR:** `coderabbit/`
- **Codex** — **Files:** `.codex/`; **Identity:** `Codex`, `codex@openai\.com`, `Codex \(gpt-5\.2-codex\)`; **Branch / PR:** `codex/`, `codex`
- **Continue** — **Files:** `.continue/`
- **Copilot** — **Files:** `copilot-instructions.md`, `copilot_instructions.md`, `copilot-instructions/`, `.github/instructions/`, `.copilot-*.md`, `.copilotignore`, `.copilot/`, `.github/workflows/copilot/`; **Identity:** `Copilot`, `copilot-swe-agent`; **Branch / PR:** `copilot/`
- **CopilotSwe** — No dedicated subtype. `copilot/` and `copilot-swe-agent` currently sit under **Copilot**.
- **Crush** — **Files:** `.crush/`, `CRUSH.md`; **Identity:** `crush@charm\.land`
- **Cursor** — **Files:** `.cursor/`, `.cursorrules`, `CURSOR.md`; **Identity:** `cursor`, `cursoragent@cursor\.com`; **Branch / PR:** `cursor/`
- **Deepsource** — **Identity:** `deepsource-autofix`
- **Devin** — **Files:** `.devin/`; **Identity:** `devin-ai-integration`; **Branch / PR:** `devin/`
- **Factory** — **Files:** `.factory/droids/`, `.factory/commands/`, `.factory/docs/`
- **Factory Droid** — **Identity:** `factory-droid\[bot\]`
- **Fly** — **Identity:** `dev@fly\.io`
- **Gemini** — **Files:** `GEMINI.md`, `.gemini/`; **Identity:** `gemini-code-assist`, `gemini-cli`, `Gemini 2\.5 Pro`, `Gemini 2\.5 Flash`
- **Generic** — **Pseudo-agent, not a product.** Files: `AGENTS.md`; Identity: `AI Assistant`; Branch / PR: `ai-generated`. The pack points its URL at `https://agents.md` and down-weights `AGENTS.md` to `0.3` because it is a shared format, not a specific vendor.
- **Goose** — **Files:** `.goosehints`; **Branch / PR:** `goose/`
- **GPT-Engineer** — **Identity:** `gpt-engineer`
- **Gru** — **Identity:** `gru-agent`; **Branch / PR:** `gru/`
- **Jules** — **Files:** `.jules/`; **Identity:** `google-labs-jules`, `jules@users\.noreply\.github\.com`; **Branch / PR:** `jules/`
- **Junie** — **Files:** `.junie/`, `.jetbrains/instructions.md`, `.junieignore`; **Identity:** `junie`, `jetbrains-junie`; **Branch / PR:** `jetbrains_junie`
- **Kilo Code** — **Files:** `.kilocode/`, `.kilocodeignore`; **Identity:** `Kilo Code`
- **Kiro** — **Files:** `.kiro/`; **Identity:** `kiro@aws\.amazon\.com`, `kiro-noreply@amazon\.com`, `kiro-agent@amazon\.com`
- **Langchain Open SWE** — **Identity:** `open-swe`; **Branch / PR:** `open-swe/`, `open-swe`
- **Letta Code** — **Identity:** `noreply@letta\.com`
- **Microsoft Amplifier** — **Identity:** `microsoft-amplifier@users\.noreply\.github\.com`
- **Mistral Vibe** — **Identity:** `vibe@mistral\.ai`
- **Ona** — **Identity:** `no-reply@ona\.com`
- **Opencode** — **Files:** `.opencode/`, `.opencode.json`, `opencode.json`; **Identity:** `noreply@opencode\.ai`, `opencode-agent`; **Branch / PR:** `opencode/`
- **OpenHands** — **Files:** `.openhands/`, `.openhands_instructions`; **Identity:** `openhands@all-hands\.dev`, `openhands-agent`; **Branch / PR:** `openhands/`
- **Phoenix** — No dedicated pack pattern.
- **Pi** — **Files:** `.pi/`, `.pi/prompts/`, `.pi/extensions/`
- **Plandex** — **Files:** `.plandexignore`, `.plandex/`, `.plandex-v2`
- **Qodo** — **Files:** `.qodo/`
- **Qwen Coder** — **Files:** `QWEN.md`; **Identity:** `Qwen-Coder`, `qwen-coder@alibabacloud\.com`
- **Roo Code** — **Files:** `.roo/`, `.roorules`; **Identity:** `roomote-agent`, `roomote@roocode\.com`, `roomote`, `Roo Code`
- **Rulesync** — **Files:** `.rulesync/`
- **Sentry Seer** — **Identity:** `seer-by-sentry`
- **Serena** — **Files:** `.serena/`; **Branch / PR:** `serena/`
- **Sketch** — **Identity:** `hello@sketch\.dev`
- **Sourcery** — **Identity:** `sourcery-ai`; **Branch / PR:** `sourcery-ai/`
- **SpecKit** — **Files:** `.specify/memory/constitution.md`, `.specify`
- **Sweep** — **Identity:** `sweep-ai`; **Branch / PR:** `sweep/`
- **Taskmaster** — **Files:** `README-task-master.md`, `taskmaster.md`, `.taskmaster/`
- **Tessl** — **Files:** `.tessl/`
- **Trae** — **Files:** `.trae/`, `.traerules`, `.marscode/`
- **Verdent** — **Files:** `.verdent/`; **Identity:** `verdent@verdent\.ai`
- **Warp** — **Files:** `WARP.md`, `.warp/`; **Identity:** `noreply@warp\.dev`
- **Windsurf** — **Files:** `.windsurf/`, `.windsurfrules`, `.codeium/`; **Identity:** `windsurf-bot`, `cascade@windsurf\.ai`; **Branch / PR:** `windsurf-bot/`
- **Zed** — No dedicated pack pattern.

### Pack hygiene notes

- `AmazonQ` is named `Amazon Q` in the pattern CSVs.
- `Atlassian Rovodev` appears with a leading space in the pattern CSVs.
- `CopilotSwe`, `Phoenix`, `Zed`, and `Azad` have no dedicated pattern subtype.
- `Kimi Code`, `Abacus`, and `Verd` appear as pattern subtypes but not as tools in the 63-agent pack.

## New pack — add 27 families to reach 90

These are the **add-now** families from the final inventory decision. Ordering follows the decision document by layer, not by market size.

### Coding agents (13)

- **Builder.io Fusion** — `.builderrules`; Builder bot comments/commits
- **Paperclip** — `.paperclip.yaml` with `schema: paperclip/v1`; `noreply@paperclip.ing`; `paperclip/rescue/...`
- **Hermes Agent** — `.hermes.md` / `HERMES.md`; `.hermes/plans/*.md`; `hermes/hermes-<8hex>`; `refs/hermes/archive/<tree>`
- **Command Code** — `.commandcode/settings.json` and subpaths; `noreply@commandcode.ai`; `command-code/<id>`
- **Oh My Pi** — `.omp/config.yml`; `.omp/agents`, `.omp/commands`, `.omp/skills`, `.omp/tools`, `.omp/extensions`; `omp/task/<id>`
- **OpenClaw** — `.openclaw/worktree-setup.sh`; `openclaw/<name>`; `refs/openclaw/...`; `openclaw@localhost`
- **Claw Code** — `.claw/settings.json` and subpaths; `.claw.json`; `CLAW.md` with product content
- **DeepSeek Reasonix** — Root `reasonix.toml`; `.reasonix/settings.json`, `.reasonix/skills/`, `.reasonix/commands/`, `.reasonix/agent-presets/definitions/<id>.json`
- **Grok Build** — `.grok/workspaced.toml`; `.grok/plan.md`; `.grok/hooks/`
- **Prime Agent** — Project `.prime/agent/settings.json`; user `~/.prime/agent/settings.json`
- **JCode** — Project `.jcode/config.toml`; user `~/.jcode/config.toml`
- **Xiaomi MiMo Code** — `.mimocode/mimocode.jsonc` (or `.json`); `.mimocode/tui.json`; `.mimocode/workflows/`; `.mimocode/skills/`
- **Codebuff** — `.codebuffignore` / `.manicodeignore`; `Co-Authored-By: Codebuff <noreply@codebuff.com>`

### Review agents (5)

- **cubic** — `cubic.yaml`; `@cubic-dev-ai`
- **Greptile** — `.greptile/config.json`, `.greptile/rules.md`, `greptile.json`
- **Kody AI** — `kodus-config.yml`; `@kody` commands
- **OpenCodeReview** — `.opencodereview/rule.json`; `~/.opencodereview/rule.json`
- **PR-Agent** — `.pr_agent.toml` (per-repo and per-directory); legacy `.pr_agent.yaml`

### Coding / review platform (1)

- **GitLab Duo Agent Platform** — Duo service account; `duo/(fix|feature|refactor|docs)/...` branches

### App-generation agent (1)

- **Lovable** — `lovable-dev[bot]`; legacy `gpt-engineer-app[bot]`; `lovable-sync*`

### Orchestrators (5)

- **Orca** — Root `orca.yaml`; legacy `help@stably.ai` trailer only
- **T3 Code** — Repository-declared `t3.json` actions and settings; default `t3/` worktree branch prefix
- **oh-my-claudecode** — `.claude/omc.jsonc`; `.omc/skills/**`; `.omc-config.json`
- **Archon** — `.archon/config.yaml`; `.archon/workflows/*.yaml`; `.archon/packs/<pack>.yaml`; `.archon/sdlc/policy/`
- **ralph** — `scripts/ralph/ralph.sh`, `scripts/ralph/prompt.md`, `scripts/ralph/CLAUDE.md`; `prd.json` / `progress.txt` corroborating only

### Platforms / harnesses (2)

- **Docker Agent** — Agent YAML/HCL plus Docker Agent schema or product-specific keys. A generic `agent.yaml` alone is not evidence.
- **GitHub Agentic Workflows** — Agentic workflow Markdown compiled under `.github/workflows/`

## Not counted in the 90

| Disposition | Count | Families |
|---|---:|---|
| Watch tier | 3 | Herdr, DeepSeek Harness, claude-flow |
| Adjacent inventory | 5 | Azure SRE Agent, BMAD-METHOD, OpenSpec, Ruler, LangGraph |
| Depth delta, already covered | 5 | Cursor, Pi, Mistral Vibe, OpenHands, OpenCode v2 |
| Negative control | 1 | Ghostty |
| Excluded | 1 | Herder |

The 5 depth deltas are already inside the 63 and do not add rows. The 3 watch families would bring the catalogue to 93 if promoted later.

## Sources

- Current names and URLs: `packs/sources/2026-10-19/tools.csv` and `packs/2026-10-19.json`.
- Current fingerprints: `packs/sources/2026-10-19/files.csv`, `authors.csv`, `branches.csv`, and `labels.csv`.
- New families and native traces: [`2026-11-09-agent-inventory-final-decision.md`](findings/2026-11-09-agent-inventory-final-decision.md).
- Detection design: [`agent-detection-efficient-engineering.md`](../design/agent-detection-efficient-engineering.md).
