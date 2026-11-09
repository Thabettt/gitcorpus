# Consequential Developer-Agent Landscape — Net-New GitCorpus Coverage Candidates

**Generated:** 2026-11-09T16:05:27+02:00  
**Research window:** 2026-11-08–2026-11-09; live-discussion window 2026-10-09–2026-11-09  
**Scope:** the requested 16 developer-agent categories; consequential net-new products and material version/surface deltas only  
**Funnel:** 792 distinct discovery labels screened → 186 source/lifecycle deep dives → 163 canonical candidates reported  
**Tiers:** Tier 1 13 · Tier 2 86 · Tier 3 64  
**Robbes relevance:** directly measurable 13 · conditional 86 · context-only 64  
**Exclusion rule:** absent from the latest trace pack and valid pre-existing findings, except an explicitly named uncovered successor/version/surface delta  
**Invalid inputs excluded:** the earlier generated landscape Markdown and CSV were not used as baseline coverage.

---

## 1. Corrected Research Question

This is a landscape of agents and agent tooling that GitCorpus does not already know, not a re-ranking of products already in the pack. Existing products appear only in the baseline and lineage maps. A retained row is either a genuinely absent product family or a material new surface whose behavior is not represented by the existing family entry.

The discovery universe combined five current curated repositories, the prior 306-name lead set, official corporate portfolio searches, measurements for 506 accessible GitHub repositories plus package and marketplace signals, current buyer/comparison material, and six `/last30days` runs. The result is intentionally selective: active corporate products, category leaders, fast-growing open projects, benchmark leaders, and products with a particularly interesting adoption trajectory survive; thin wrappers, abandoned projects, undifferentiated forks, and marketing-only claims do not.

### 1.1 Evidence hierarchy

1. Official docs, repositories, changelogs, release notes, and product contracts establish identity, lifecycle, and behavior.
2. GitHub GraphQL, npm, PyPI, Homebrew, Docker Hub, and marketplace/install signals establish measurable adoption or momentum, not unique users.
3. Reddit, X, YouTube, TikTok, Instagram, Hacker News, LinkedIn, GitHub activity, and web results establish current discussion, comparisons, and pain points.
4. Vendor benchmarks and customer figures remain explicitly vendor-reported; directories and comparison sites are lead generators or triangulation, never sole proof.

### 1.2 Baseline exclusion inventory

The latest pack plus the valid November source report produce **78 raw covered labels**, canonicalized to **74 product or detector families** after merging aliases and same-family surfaces. These were excluded as additions: Abacus, Aider, Alibaba Lingma, Amazon Q Developer, Amp, Atlassian Rovo Dev, Augment Code, Azad, Baidu Comate, Brokk, Charlie, ChatGPT, Claude Code, Claw Code, Cline, CodeBuddy, CodeRabbit, Codegen, Codex, Command Code, Continue, Crush, Cursor, DeepSeek Harness, DeepSource, Devin, Factory / Droids, Fly, GPT-Engineer, Gemini, Generic, Ghostty, GitHub Copilot, GitHub Spec Kit, Goose, Gru, Herder, Herdr, Hermes Agent, Jules, Junie, Kilo Code, Kimi Code, Kiro, LangChain Open SWE, Letta Code, Microsoft Amplifier, Mistral Vibe, Oh My Pi, Ona, OpenClaw, OpenCode, OpenHands, Orca, Paperclip, Phoenix, Pi, Plandex, Qodo, Qwen Code, Roo Code, Sentry Seer, Serena, Sketch, Sourcery, Sweep, Taskmaster, Tessl, Trae, Verdent, Warp, Windsurf, Zed, rulesync.

A product already in that baseline can survive only as a named delta. For example, GitHub Copilot itself is excluded, while its Fusion/CLI/Agent-HQ delta is retained; Windsurf and Devin are excluded, while Devin Desktop is retained as a successor surface.

### 1.3 Robbes adoption-measurement relevance audit

Robbes et al. define a coding agent as an LLM in a loop with tool access, and measure its adoption from repository-visible traces: product-specific configuration/rules files, commit author or co-author identity, branch names, and PR labels. Their heuristics cover 63 agents and 196 patterns, with reported false-positive rates of 0.5–1%; they explicitly warn that generic files (`AGENTS.md`, `SKILL.md`, `agent.yaml`) prove a shared format, never the executing product. Stars, downloads, and vendor customer counts are discovery signals, not adoption measurement.

Applying that test changes the action set. A candidate is **directly measurable** only if a product-specific artifact or SCM identity can be detected in repositories today; **conditional** if the agent is real but the product-specific trace still needs a pinned source audit or a conjunction; **context-only** if its activity is telemetry-, hosted-, runtime-, or standard-level and does not identify the executing agent. Context-only candidates remain in the landscape because they explain the market and the shared-path collision risk, but they are not independent fingerprint targets and must not be counted as measurable adoption.

| Relevance | Candidates | Meaning for the trace corpus |
|---|---:|---|
| Directly measurable | 13 | Product-specific file/config, SCM bot, branch, or workflow artifact exists; add to the detector backlog. |
| Conditional | 86 | Real agent or surface, but identity is generic, downstream, or unverified; source audit before any detector claim. |
| Context-only | 64 | Market/context signal only; delegated fixes inherit the downstream coding agent's trace. |

The practical consequence is that the 163 candidates are not 163 new detector families. The report previously ranked research priority; it now ranks measurement readiness under Robbes' criteria, and the two are not the same. Re-tiering moves the action set from 63/98/2 to 13/86/64: 50 products that were Tier 1 on market importance are not yet measurable from a product-specific repository trace, and 62 context-only products move out of the detector backlog. A high-momentum orchestration or AIOps product can be strategically important and still be invisible to repository mining.

---

## 2. What Current Discussion Says

The six `/last30days` runs retained evidence from Reddit, X, YouTube, TikTok, Instagram, Hacker News, LinkedIn, GitHub, and the web; Polymarket returned no relevant market and Digg was empty or degraded. The engine outputs and source-status caveats are preserved in the local research artifacts.

- **Configuration is becoming the product layer.** A [2026-11-08 ClaudeCode discussion](https://www.reddit.com/r/ClaudeCode/comments/1xr9qnh/everyones_fix_for_coding_agents_is_a_markdown_file/) summarized the pattern: failures are increasingly handled with committed instructions, skills, specs, and memory rather than model switching alone.
- **Review is the bottleneck.** Current HN and community discussions repeatedly argue that generating more code simply moves work into architecture, verification, and unread diffs; a [same-day AI_Agents thread](https://www.reddit.com/r/AI_Agents/comments/1xr1q5f/how_much_can_realistically_be_built_using_nocode/) says engineering moved up a layer rather than disappearing.
- **Parallelism requires an operating layer.** The orchestration sweep found strong discussion of lead agents, one-worktree-per-task isolation, explicit interfaces, test gates, and diff review. It also found the counterclaim that swarms add context switching and coordination cost when work is not independent.
- **Spec-driven development is now a real category, not one tool.** Current YouTube and HN evidence debates fixing a bad plan before generation versus letting implementation inform the spec; the strongest products make specs durable and verification explicit without forcing ceremony on small changes.
- **AI SRE trust stops before blind production writes.** The SRE sweep found a rapidly consolidating market, hyperscaler launches, and strong interest in autonomous investigation, while remediation remains permissioned and evidence-driven for most operators.
- **App builders are judged after the demo.** The app-generation sweep centers on authentication, database policy, test evidence, staging URLs, code ownership, rollback, and maintainability—not initial prompt-to-preview speed.

---

## 3. Category Coverage and Net-New Yield

| Category | Raw leads | Reported net-new candidates | Directly measurable | Conditional | Context-only | Under-coverage verdict |
|---|---:|---:|---:|---:|---:|---|
| Agent Harnesses & SDKs | 81 | 21 | 2 | 15 | 4 | Near-zero operational attribution: major frameworks are absent and ordinary use is dependency/import content. |
| Agent CLIs / TUIs | 48 | 20 | 2 | 17 | 1 | The pack covers many incumbents but misses the 2026 corporate wave and several fast-growing open harnesses. |
| Agentic / AI-Native Terminals | 43 | 3 | 0 | 3 | 0 | Warp is covered; cmux, Paradev, tuios, and newer agent-aware terminal control planes are not. |
| Agent Multiplexers & Herders | 190 | 20 | 0 | 19 | 1 | Only the November source report covers a few exemplars; the active worktree/workspace category is broadly absent. |
| Agent Orchestrators & Fleet Managers | 109 | 19 | 3 | 15 | 1 | Fleet-level task, queue, review, and agent-to-agent metadata are almost entirely outside current packs. |
| ADEs | 172 | 22 | 0 | 20 | 2 | Editor-like incumbents exist in the pack, but the agent-first workspace layer and corporate ADE launches are mostly missing. |
| AI-Native IDEs (Forked Editors) | 17 | 5 | 0 | 5 | 0 | Core editor families are known, but 2026 successors and agent-manager surfaces need explicit lifecycle coverage. |
| IDE Agent Extensions & Plugins | 37 | 18 | 1 | 11 | 6 | Mainstream extensions are partly covered; enterprise, Neovim, and platform-specific agents remain uneven. |
| Autonomous Cloud SWE Agents / Background Droids | 37 | 15 | 1 | 9 | 5 | Known cloud agents exist, but web/cloud successors and multi-agent platforms need surface-aware provenance. |
| PR Review, Auto-Fix & Code Quality Bots | 36 | 17 | 4 | 11 | 2 | The pack has several actors but misses most current benchmark leaders, canonical configs, and review-versus-authorship semantics. |
| Spec-Driven Development (SDD) & Task Planners | 98 | 13 | 2 | 10 | 1 | Spec Kit, Taskmaster, Kiro, and Tessl are known; the highest-momentum open methodologies are still absent. |
| Rules Managers & Context Syncers | 24 | 6 | 1 | 2 | 3 | rulesync is covered, but Ruler, routing, templates, and Git-native task/context layers are missing. |
| Agent Plugin / Dotfile Frameworks | 28 | 11 | 0 | 3 | 8 | Portable skills appear as shared paths, while new standards, marketplaces, provenance, and corporate skill portfolios are not modeled. |
| Personal AI Daemons & Local Gateways | 85 | 20 | 0 | 2 | 18 | OpenClaw is researched, but its fast-growing ecosystem and the gateway/control-plane layer are largely absent. |
| AIOps & Incident Auto-Remediation Agents | 37 | 19 | 1 | 0 | 18 | Sentry is the lone strong pack entry; nearly the whole AI SRE market remains telemetry-native and unrepresented. |
| Full-Stack Scaffolding / App-Gen Agents | 35 | 14 | 2 | 4 | 8 | GPT-Engineer is covered, while the dominant hosted builders and enterprise app agents are overwhelmingly absent. |

---

## 4. Tiered Action Set

Tiers now encode Robbes measurement readiness, not general market importance. Tier 1 is directly measurable from a product-specific repository artifact; Tier 2 is a real agent or surface whose identity still needs a source audit; Tier 3 is context-only and should not enter the detector backlog as an independent target.

### 4.1 Tier 1 — directly measurable, add next

- **Azure SRE Agent** — Microsoft's real Azure resource supports source, telemetry, subagents, hooks, MCP, IaC export, and configured remediation. **Measurement lead:** IaC/config bundle: `agent.json`, `connectors.json`, `roles.yaml`, and `config/{skills,subagents,hooks}/` as a conjunction. [Primary source](https://learn.microsoft.com/en-us/azure/sre-agent/overview)
- **BMAD-METHOD** — A high-adoption methodology packages analyst, product, architecture, implementation, and review agents into a durable planning workflow. **Measurement lead:** project files: `_bmad/`, `_bmad-output/`; older `.bmad-*` is legacy. [Primary source](https://github.com/bmad-code-org/BMAD-METHOD)
- **Builder.io Fusion** — A repo-native visual coding agent with the distinctive .builderrules contract and bot-mediated PR workflow. **Measurement lead:** project file + SCM activity: `.builderrules`; Builder bot comments/commits need channel separation. [Primary source](https://www.builder.io/c/docs/projects-git-providers)
- **cubic** — The current Code Review Bench leader combines PR review, local CLI review, custom agents, and background fixes. **Measurement lead:** project file + SCM activity: `cubic.yaml`; `@cubic-dev-ai` comments are activity. [Primary source](https://docs.cubic.dev/ai-review/quickstart)
- **Docker Agent (formerly cagent)** — Docker's renamed, fast-moving agent builder and runtime ships in Docker Desktop and defines multi-agent teams, tools, models, and handoffs in portable YAML or HCL. **Measurement lead:** declarative agent definition: agent YAML/HCL plus Docker Agent schema or product-specific keys; a generic `agent.yaml` filename alone is unsafe. [Primary source](https://docs.docker.com/ai/docker-agent)
- **GitHub Agentic Workflows** — GitHub's open workflow system compiles Markdown-defined agents into governed Actions jobs, creating a new repository-native automation surface. **Measurement lead:** workflow source: agentic workflow Markdown compiled under `.github/workflows/`; content/provenance required. [Primary source](https://github.com/github/gh-aw)
- **GitLab Duo Agent Platform** — GitLab's GA platform embeds coding, review, pipeline-repair, security, custom, and external agents across the repository and delivery lifecycle, including self-managed deployments. **Measurement lead:** SCM activity + platform metadata: Duo service-account participation and `duo/(fix|feature|refactor|docs)/...` branches; `AGENTS.md` alone is generic. [Primary source](https://docs.gitlab.com/user/duo_agent_platform/)
- **Greptile** — A leading whole-repository review agent with current benchmark visibility and product-owned configuration. **Measurement lead:** project files + SCM activity: `.greptile/config.json`, `.greptile/rules.md`, `greptile.json`. [Primary source](https://www.greptile.com/docs/introduction)
- **Kody AI** — A top current review benchmark entrant with self-hosting and a repository configuration contract. **Measurement lead:** project file + SCM activity: `kodus-config.yml`; `@kody` commands are activity. [Primary source](https://docs.kodus.io/en/how_to_use/overview)
- **LangGraph** — The dominant stateful graph runtime for durable, inspectable agent workflows, with a large dependency footprint and active production ecosystem. **Measurement lead:** project file: `langgraph.json`. [Primary source](https://github.com/langchain-ai/langgraph)
- **Lovable** — One of the most-used prompt-to-full-stack platforms, with optional Git sync and exact current and legacy bot identities. **Measurement lead:** author/bot + recovery branch: `lovable-dev[bot]`, legacy `gpt-engineer-app[bot]`, `lovable-sync*`. [Primary source](https://docs.lovable.dev/integrations/github)
- **OpenSpec** — A leading open spec-driven workflow stores proposals, requirements, design, tasks, and archived changes as reviewable project artifacts. **Measurement lead:** project files: `openspec/config.yaml`, `openspec/changes/`, `openspec/specs/`. [Primary source](https://github.com/Fission-AI/OpenSpec)
- **Ruler** — The leading cross-agent rules manager compiles one source of project instructions, MCP settings, and skills into many client-specific formats. **Measurement lead:** project files: `ruler.toml` and `.ruler/`. [Primary source](https://github.com/intellectronica/ruler)

### 4.2 Tier 2 — real agent or surface, but source/schema audit first

**Addy Osmani Agent Skills**, **Agent OS**, **Agent Plugins 1.0**, **Agent Teams**, **AgentScope**, **Agno**, **AionUi**, **Amp Orbs**, **avante.nvim**, **AWS CLI Agent Orchestrator**, **Backlog.md**, **Base44**, **Bito**, **Block Berd**, **Claude Agent SDK**, **Claude Code on the web delta**, **Claude Code Review delta**, **Claude Code Router**, **Claude Squad**, **Cloudflare Agents SDK**, **cmux**, **CodeCompanion.nvim**, **Coder Xum / Mux**, **CodeWhale**, **Codex Code Review delta**, **CrewAI**, **Deep Agents Code**, **Devin Desktop**, **Ellipsis**, **Emdash**, **ForgeCode**, **Freebuff (formerly Codebuff)**, **Gastown**, **Gitar**, **Google ADK**, **Google Antigravity 2.0 / CLI / SDK**, **Google Conductor**, **Graphite Agent**, **Grok Build**, **GSD Core**, **Happy**, **Hyrax**, **IBM Bob**, **jcode**, **JetBrains Air**, **JetBrains Junie GA / CLI delta**, **LlamaIndex Workflows**, **Macroscope Review**, **Mastra**, **MausBot (OpenMausBot)**, **Meta Muse Code**, **Microsoft Agent Framework**, **MoAI-ADK**, **Multica**, **Omnigent**, **OpenAI Agents SDK**, **OpenAI Symphony**, **OpenChamber**, **OpenRig**, **Orchestrator.inc**, **Paradev (formerly Superset)**, **Paseo**, **Prime Agent**, **Pydantic AI**, **Qoder 1.0 portfolio delta**, **Reasonix**, **Ruflo**, **Scion**, **Semgrep Multimodal / Autofix**, **smolagents**, **Snowflake Cortex Code (CoCo)**, **Snyk Agent Fix**, **SonarQube AI CodeFix**, **Spec Kitty**, **Strands Harness / Agents SDK**, **Superpowers**, **T3 Code**, **Tau**, **TRAE 2026 platform delta**, **tuios**, **Vercel AI SDK**, **Vibe Kanban**, **VibeSDK**, **Warp Oz / Factories delta**, **Xiaomi MiMo Code**, **Zenflow**.

### 4.3 Tier 3 — context-only, not an independent adoption target

**Agent Skills standard**, **Agent Zero**, **Anyshift**, **AWS Agent Toolkit**, **AWS Bedrock AgentCore Harness**, **AWS DevOps Agent**, **Background Agents / Open Inspect**, **Bifrost**, **Bolt.new**, **Claude Code Templates**, **Cleric**, **CodeGPT**, **Context7**, **Databricks Agent Bricks**, **Databricks Genie Code**, **Datadog Bits AI: Investigation / Remediation**, **Dynatrace SRE Agent**, **Emergent**, **Figma Make**, **GitHub Copilot 2026 surface delta**, **Gitingest**, **Google Elephant-Goldfish Model**, **Google Skills**, **HolmesGPT**, **incident.io Investigations**, **IronClaw**, **LiteLLM**, **LobeHub**, **MCP reference servers**, **Metoro**, **Mezmo AURA**, **Microsoft .NET Agent Skills**, **nanobot**, **NanoClaw**, **NeuBird Hawkeye**, **New Relic AI**, **NVIDIA OpenShell / NemoClaw**, **Octop**, **Oh My Codex**, **Ollama**, **Open Interpreter**, **Open WebUI**, **OpenHuman**, **OpenWorker**, **PagerDuty Paige (SRE Agent)**, **PicoClaw**, **Portkey / Prisma AIRS AI Gateway**, **QwenPaw**, **Replit Agent**, **Repomix**, **Resolve AI**, **Rootly AI SRE**, **Salesforce Agentforce Vibes**, **SAP Joule Studio**, **ServiceNow Build Agent**, **ServiceNow ITOM Prime / AIOps AI Specialist**, **Sinatra**, **Splunk AI SRE**, **Struct**, **Tabnine**, **Tembo**, **Traversal**, **v0**, **ZeroClaw**.

### 4.4 Non-averaged score matrix

**A** adoption · **M** momentum · **C** corporate backing · **D** 30-day discussion · **F** trace distinctiveness · **V** detector/measurement value · **R** collision safety · **E** schema encodability · **I** longitudinal interest. No aggregate score is calculated.

| Candidate | Tier | A | M | C | D | F | V | R | E | I |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Addy Osmani Agent Skills | 2 | 5 | 4 | 5 | 1 | 4 | 4 | 4 | 3 | 5 |
| Agent OS | 2 | 3 | 2 | 3 | 1 | 4 | 4 | 4 | 3 | 4 |
| Agent Plugins 1.0 | 2 | 2 | 2 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| Agent Skills standard | 3 | 5 | 2 | 4 | 5 | 1 | 2 | 1 | 1 | 3 |
| Agent Teams | 2 | 2 | 5 | 1 | 1 | 1 | 4 | 1 | 3 | 4 |
| Agent Zero | 3 | 3 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| AgentScope | 2 | 5 | 4 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| Agno | 2 | 4 | 4 | 3 | 1 | 3 | 4 | 3 | 1 | 4 |
| AionUi | 2 | 4 | 4 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| Amp Orbs | 2 | 3 | 3 | 5 | 1 | 1 | 4 | 1 | 1 | 5 |
| Anyshift | 3 | 1 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| avante.nvim | 2 | 3 | 4 | 1 | 1 | 3 | 4 | 3 | 3 | 4 |
| AWS Agent Toolkit | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| AWS Bedrock AgentCore Harness | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| AWS CLI Agent Orchestrator | 2 | 2 | 4 | 5 | 1 | 1 | 4 | 1 | 3 | 5 |
| AWS DevOps Agent | 3 | 5 | 3 | 5 | 3 | 1 | 2 | 1 | 1 | 5 |
| Azure SRE Agent | 1 | 5 | 3 | 5 | 1 | 3 | 5 | 3 | 1 | 5 |
| Background Agents / Open Inspect | 3 | 2 | 4 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Backlog.md | 2 | 3 | 4 | 1 | 1 | 4 | 4 | 4 | 3 | 4 |
| Base44 | 2 | 3 | 3 | 5 | 2 | 3 | 4 | 3 | 4 | 5 |
| Bifrost | 3 | 3 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Bito | 2 | 1 | 3 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Block Berd | 2 | 2 | 5 | 5 | 1 | 1 | 4 | 1 | 3 | 5 |
| BMAD-METHOD | 1 | 5 | 4 | 3 | 1 | 5 | 5 | 5 | 5 | 5 |
| Bolt.new | 3 | 1 | 3 | 3 | 2 | 1 | 2 | 1 | 1 | 3 |
| Builder.io Fusion | 1 | 1 | 3 | 3 | 2 | 5 | 5 | 5 | 4 | 5 |
| Claude Agent SDK | 2 | 4 | 5 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| Claude Code on the web delta | 2 | 3 | 3 | 5 | 1 | 1 | 4 | 1 | 1 | 5 |
| Claude Code Review delta | 2 | 3 | 3 | 5 | 1 | 1 | 4 | 1 | 1 | 5 |
| Claude Code Router | 2 | 4 | 4 | 1 | 1 | 4 | 4 | 4 | 3 | 4 |
| Claude Code Templates | 3 | 4 | 4 | 1 | 1 | 1 | 2 | 1 | 1 | 3 |
| Claude Squad | 2 | 3 | 2 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| Cleric | 3 | 1 | 3 | 3 | 2 | 1 | 2 | 1 | 1 | 3 |
| Cloudflare Agents SDK | 2 | 3 | 5 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| cmux | 2 | 4 | 5 | 3 | 2 | 1 | 4 | 1 | 3 | 4 |
| CodeCompanion.nvim | 2 | 3 | 5 | 1 | 1 | 3 | 4 | 3 | 3 | 4 |
| CodeGPT | 3 | 5 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Coder Xum / Mux | 2 | 2 | 5 | 5 | 1 | 1 | 4 | 1 | 3 | 5 |
| CodeWhale | 2 | 4 | 5 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Codex Code Review delta | 2 | 3 | 3 | 5 | 1 | 1 | 4 | 1 | 1 | 5 |
| Context7 | 3 | 5 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| CrewAI | 2 | 5 | 5 | 3 | 1 | 3 | 4 | 3 | 1 | 4 |
| cubic | 1 | 5 | 3 | 3 | 4 | 3 | 5 | 3 | 4 | 5 |
| Databricks Agent Bricks | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Databricks Genie Code | 3 | 3 | 3 | 5 | 1 | 2 | 2 | 2 | 3 | 5 |
| Datadog Bits AI: Investigation / Remediation | 3 | 3 | 3 | 5 | 2 | 1 | 2 | 1 | 1 | 5 |
| Deep Agents Code | 2 | 4 | 5 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Devin Desktop | 2 | 1 | 3 | 3 | 1 | 1 | 4 | 1 | 1 | 4 |
| Docker Agent (formerly cagent) | 1 | 2 | 5 | 5 | 1 | 3 | 5 | 3 | 3 | 5 |
| Dynatrace SRE Agent | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Ellipsis | 2 | 1 | 3 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Emdash | 2 | 3 | 5 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| Emergent | 3 | 1 | 3 | 3 | 3 | 1 | 2 | 1 | 1 | 3 |
| Figma Make | 3 | 3 | 3 | 5 | 2 | 1 | 2 | 1 | 1 | 5 |
| ForgeCode | 2 | 3 | 4 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Freebuff (formerly Codebuff) | 2 | 3 | 5 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Gastown | 2 | 3 | 2 | 1 | 2 | 1 | 4 | 1 | 3 | 4 |
| Gitar | 2 | 3 | 3 | 5 | 2 | 3 | 4 | 3 | 3 | 5 |
| GitHub Agentic Workflows | 1 | 3 | 5 | 5 | 1 | 3 | 5 | 3 | 1 | 5 |
| GitHub Copilot 2026 surface delta | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Gitingest | 3 | 3 | 2 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| GitLab Duo Agent Platform | 1 | 3 | 3 | 5 | 1 | 3 | 5 | 3 | 3 | 5 |
| Google ADK | 2 | 4 | 5 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| Google Antigravity 2.0 / CLI / SDK | 2 | 3 | 3 | 5 | 3 | 3 | 4 | 3 | 3 | 5 |
| Google Conductor | 2 | 2 | 2 | 5 | 1 | 4 | 4 | 4 | 3 | 5 |
| Google Elephant-Goldfish Model | 3 | 3 | 5 | 5 | 1 | 3 | 2 | 3 | 1 | 5 |
| Google Skills | 3 | 4 | 4 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Graphite Agent | 2 | 1 | 3 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Greptile | 1 | 5 | 3 | 3 | 5 | 5 | 5 | 5 | 4 | 5 |
| Grok Build | 2 | 4 | 2 | 3 | 2 | 3 | 4 | 3 | 3 | 4 |
| GSD Core | 2 | 3 | 5 | 1 | 1 | 4 | 4 | 4 | 3 | 4 |
| Happy | 2 | 4 | 5 | 3 | 4 | 1 | 4 | 1 | 3 | 4 |
| HolmesGPT | 3 | 2 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Hyrax | 2 | 1 | 3 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| IBM Bob | 2 | 5 | 3 | 5 | 1 | 3 | 4 | 3 | 3 | 5 |
| incident.io Investigations | 3 | 1 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| IronClaw | 3 | 3 | 4 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| jcode | 2 | 4 | 5 | 1 | 2 | 3 | 4 | 3 | 3 | 4 |
| JetBrains Air | 2 | 3 | 3 | 5 | 1 | 1 | 4 | 1 | 3 | 5 |
| JetBrains Junie GA / CLI delta | 2 | 3 | 3 | 5 | 1 | 1 | 4 | 1 | 1 | 5 |
| Kody AI | 1 | 5 | 3 | 3 | 1 | 3 | 5 | 3 | 4 | 5 |
| LangGraph | 1 | 4 | 5 | 3 | 2 | 5 | 5 | 5 | 5 | 5 |
| LiteLLM | 3 | 5 | 5 | 3 | 2 | 1 | 2 | 1 | 1 | 3 |
| LlamaIndex Workflows | 2 | 5 | 4 | 3 | 1 | 3 | 4 | 3 | 1 | 4 |
| LobeHub | 3 | 5 | 5 | 3 | 5 | 1 | 2 | 1 | 1 | 3 |
| Lovable | 1 | 1 | 3 | 3 | 5 | 5 | 5 | 5 | 5 | 5 |
| Macroscope Review | 2 | 1 | 3 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Mastra | 2 | 4 | 5 | 3 | 1 | 3 | 4 | 3 | 1 | 4 |
| MausBot (OpenMausBot) | 2 | 3 | 5 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| MCP reference servers | 3 | 5 | 5 | 4 | 2 | 1 | 2 | 1 | 1 | 3 |
| Meta Muse Code | 2 | 3 | 3 | 5 | 1 | 3 | 4 | 3 | 3 | 5 |
| Metoro | 3 | 1 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Mezmo AURA | 3 | 1 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Microsoft .NET Agent Skills | 3 | 3 | 5 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Microsoft Agent Framework | 2 | 3 | 5 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| MoAI-ADK | 2 | 2 | 5 | 3 | 1 | 4 | 4 | 4 | 3 | 4 |
| Multica | 2 | 5 | 5 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| nanobot | 3 | 4 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| NanoClaw | 3 | 4 | 4 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| NeuBird Hawkeye | 3 | 1 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| New Relic AI | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| NVIDIA OpenShell / NemoClaw | 3 | 4 | 4 | 5 | 4 | 1 | 2 | 1 | 1 | 5 |
| Octop | 3 | 3 | 5 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Oh My Codex | 3 | 4 | 5 | 1 | 1 | 1 | 2 | 1 | 1 | 3 |
| Ollama | 3 | 5 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Omnigent | 2 | 3 | 5 | 5 | 1 | 1 | 4 | 1 | 3 | 5 |
| Open Interpreter | 3 | 5 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Open WebUI | 3 | 5 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| OpenAI Agents SDK | 2 | 4 | 5 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| OpenAI Symphony | 2 | 4 | 4 | 5 | 1 | 1 | 4 | 1 | 3 | 5 |
| OpenChamber | 2 | 3 | 5 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| OpenHuman | 3 | 4 | 5 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| OpenRig | 2 | 3 | 5 | 1 | 1 | 1 | 4 | 1 | 3 | 4 |
| OpenSpec | 1 | 5 | 5 | 3 | 1 | 5 | 5 | 5 | 5 | 5 |
| OpenWorker | 3 | 3 | 5 | 1 | 1 | 1 | 2 | 1 | 1 | 3 |
| Orchestrator.inc | 2 | 3 | 5 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| PagerDuty Paige (SRE Agent) | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Paradev (formerly Superset) | 2 | 3 | 5 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| Paseo | 2 | 4 | 5 | 3 | 2 | 1 | 4 | 1 | 3 | 4 |
| PicoClaw | 3 | 4 | 2 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Portkey / Prisma AIRS AI Gateway | 3 | 3 | 2 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Prime Agent | 2 | 4 | 4 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Pydantic AI | 2 | 4 | 5 | 3 | 1 | 3 | 4 | 3 | 1 | 4 |
| Qoder 1.0 portfolio delta | 2 | 3 | 3 | 5 | 1 | 1 | 4 | 1 | 1 | 5 |
| QwenPaw | 3 | 4 | 5 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Reasonix | 2 | 4 | 5 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| Replit Agent | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Repomix | 3 | 4 | 5 | 1 | 1 | 1 | 2 | 1 | 1 | 3 |
| Resolve AI | 3 | 1 | 3 | 3 | 2 | 1 | 2 | 1 | 1 | 3 |
| Rootly AI SRE | 3 | 1 | 3 | 3 | 2 | 1 | 2 | 1 | 1 | 3 |
| Ruflo | 2 | 5 | 5 | 1 | 1 | 1 | 4 | 1 | 3 | 4 |
| Ruler | 1 | 2 | 4 | 3 | 1 | 5 | 5 | 5 | 5 | 5 |
| Salesforce Agentforce Vibes | 3 | 3 | 3 | 5 | 1 | 2 | 2 | 2 | 3 | 5 |
| SAP Joule Studio | 3 | 3 | 3 | 5 | 1 | 2 | 2 | 2 | 3 | 5 |
| Scion | 2 | 2 | 5 | 5 | 1 | 1 | 4 | 1 | 3 | 5 |
| Semgrep Multimodal / Autofix | 2 | 1 | 3 | 3 | 1 | 3 | 4 | 3 | 3 | 4 |
| ServiceNow Build Agent | 3 | 3 | 3 | 5 | 1 | 2 | 2 | 2 | 3 | 5 |
| ServiceNow ITOM Prime / AIOps AI Specialist | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Sinatra | 3 | 1 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| smolagents | 2 | 4 | 2 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| Snowflake Cortex Code (CoCo) | 2 | 5 | 3 | 5 | 1 | 3 | 4 | 3 | 3 | 5 |
| Snyk Agent Fix | 2 | 3 | 3 | 5 | 1 | 3 | 4 | 3 | 3 | 5 |
| SonarQube AI CodeFix | 2 | 3 | 3 | 5 | 1 | 3 | 4 | 3 | 3 | 5 |
| Spec Kitty | 2 | 2 | 5 | 3 | 1 | 4 | 4 | 4 | 3 | 4 |
| Splunk AI SRE | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Strands Harness / Agents SDK | 2 | 4 | 5 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| Struct | 3 | 1 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| Superpowers | 2 | 5 | 5 | 1 | 2 | 4 | 4 | 4 | 3 | 4 |
| T3 Code | 2 | 5 | 5 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| Tabnine | 3 | 5 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Tau | 2 | 2 | 5 | 5 | 1 | 3 | 4 | 3 | 3 | 5 |
| Tembo | 3 | 1 | 3 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |
| TRAE 2026 platform delta | 2 | 3 | 3 | 5 | 1 | 1 | 4 | 1 | 1 | 5 |
| Traversal | 3 | 1 | 3 | 3 | 3 | 1 | 2 | 1 | 1 | 3 |
| tuios | 2 | 3 | 5 | 1 | 1 | 1 | 4 | 1 | 3 | 4 |
| v0 | 3 | 3 | 3 | 5 | 1 | 1 | 2 | 1 | 1 | 5 |
| Vercel AI SDK | 2 | 4 | 5 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| Vibe Kanban | 2 | 4 | 2 | 3 | 1 | 1 | 4 | 1 | 3 | 4 |
| VibeSDK | 2 | 3 | 2 | 5 | 1 | 3 | 4 | 3 | 1 | 5 |
| Warp Oz / Factories delta | 2 | 1 | 3 | 3 | 1 | 1 | 4 | 1 | 1 | 4 |
| Xiaomi MiMo Code | 2 | 3 | 4 | 5 | 1 | 3 | 4 | 3 | 3 | 5 |
| Zenflow | 2 | 1 | 3 | 3 | 1 | 4 | 4 | 4 | 3 | 4 |
| ZeroClaw | 3 | 4 | 4 | 3 | 1 | 1 | 2 | 1 | 1 | 3 |

---

## 5. Category Landscape

### 5.1 Agent Harnesses & SDKs

Near-zero operational attribution: major frameworks are absent and ordinary use is dependency/import content.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Docker Agent (formerly cagent) | 1 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers | Docker's renamed, fast-moving agent builder and runtime ships in Docker Desktop and defines multi-agent teams, tools, models, and handoffs in portable YAML or HCL. | declarative agent definition: agent YAML/HCL plus Docker Agent schema or product-specific keys; a generic `agent.yaml` filename alone is unsafe |
| LangGraph | 1 | — | The dominant stateful graph runtime for durable, inspectable agent workflows, with a large dependency footprint and active production ecosystem. | project file: `langgraph.json` |
| AgentScope | 2 | — | Alibaba's fast-growing framework combines multi-agent construction with runtime, observability, evaluation, and deployment tooling. | dependency/manifest content: package or import literal; no unique path assumed |
| Agno | 2 | — | A high-adoption Python framework for agents, teams, workflows, memory, storage, and model-provider portability. | dependency/manifest content: package or import literal; no unique path assumed |
| Claude Agent SDK | 2 | — | Anthropic exposes the Claude Code agent loop as Python and TypeScript SDKs, creating a reusable harness surface distinct from the CLI. | dependency/manifest content: package or import literal; no unique path assumed |
| Cloudflare Agents SDK | 2 | — | Cloudflare's framework binds agents to durable state, workflows, browser/code execution, and Workers deployment. | dependency/manifest content: package or import literal; no unique path assumed |
| CrewAI | 2 | — | One of the largest independent multi-agent frameworks, centered on role-based crews, flows, memory, and deployable automation. | dependency/manifest content: package or import literal; no unique path assumed |
| Google ADK | 2 | — | Google's first-party, multi-language framework covers agent composition, A2A interoperability, evaluation, and managed deployment. | dependency/manifest content: package or import literal; no unique path assumed |
| Google Antigravity 2.0 / CLI / SDK | 2 | Agent CLIs / TUIs; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Google made Antigravity its forward developer-agent platform, with one harness across desktop, CLI, SDK, managed agents, and cloud use. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| LlamaIndex Workflows | 2 | — | The event-driven agent-workflow layer in the large LlamaIndex ecosystem, relevant wherever data-centric agents need durable control flow. | dependency/manifest content: package or import literal; no unique path assumed |
| Mastra | 2 | — | A high-momentum TypeScript framework spanning agents, workflows, memory, retrieval, evaluation, observability, and deployment. | dependency/manifest content: package or import literal; no unique path assumed |
| Microsoft Agent Framework | 2 | — | Microsoft's designated successor to AutoGen and Semantic Kernel unifies agent construction and multi-agent workflows across Python and .NET. | dependency/manifest content: package or import literal; no unique path assumed |
| OpenAI Agents SDK | 2 | — | OpenAI's first-party framework standardizes tools, handoffs, guardrails, sessions, and tracing across Python and TypeScript agents. | dependency/manifest content: package or import literal; no unique path assumed |
| Pydantic AI | 2 | — | A rapidly adopted typed Python framework that applies Pydantic validation, model portability, durable graphs, and evaluation to agent systems. | dependency/manifest content: package or import literal; no unique path assumed |
| smolagents | 2 | — | Hugging Face's compact code-agent library is a consequential reference implementation for tool use and open-model agent workflows. | dependency/manifest content: package or import literal; no unique path assumed |
| Strands Harness / Agents SDK | 2 | — | AWS's consolidated monorepo spans low-level Python and TypeScript SDKs, opinionated harness packages, a CLI, tools, and production guidance. | dependency/manifest content: package or import literal; no unique path assumed |
| Vercel AI SDK | 2 | — | A widely used TypeScript toolkit whose agent, tool-calling, streaming, and provider abstractions extend a major web-development ecosystem. | dependency/manifest content: package or import literal; no unique path assumed |
| AWS Bedrock AgentCore Harness | 3 | — | AWS now ships the orchestration loop itself as a managed, model-agnostic microVM harness; it is strategically distinct from the Strands SDK. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| Databricks Agent Bricks | 3 | — | Databricks' developer platform combines a CLI, durable agent runtime, sandboxed code execution, memory, tools, tracing, evaluation, and Unity Catalog governance. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| NVIDIA OpenShell / NemoClaw | 3 | Personal AI Daemons & Local Gateways | NVIDIA's first-party sandbox/runtime stack explicitly hosts OpenClaw, Hermes, and other long-running agents and has fast adoption. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| SAP Joule Studio | 3 | Full-Stack Scaffolding / App-Gen Agents | SAP's intent-based environment builds agents, apps, and workflows through browser and pro-code CLI flows over a managed runtime. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |

### 5.2 Agent CLIs / TUIs

The pack covers many incumbents but misses the 2026 corporate wave and several fast-growing open harnesses.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Docker Agent (formerly cagent) | 1 | Agent Harnesses & SDKs; Agent Orchestrators & Fleet Managers | Docker's renamed, fast-moving agent builder and runtime ships in Docker Desktop and defines multi-agent teams, tools, models, and handoffs in portable YAML or HCL. | declarative agent definition: agent YAML/HCL plus Docker Agent schema or product-specific keys; a generic `agent.yaml` filename alone is unsafe |
| GitLab Duo Agent Platform | 1 | Agent Orchestrators & Fleet Managers; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | GitLab's GA platform embeds coding, review, pipeline-repair, security, custom, and external agents across the repository and delivery lifecycle, including self-managed deployments. | SCM activity + platform metadata: Duo service-account participation and `duo/(fix\|feature\|refactor\|docs)/...` branches; `AGENTS.md` alone is generic |
| CodeWhale | 2 | — | A fast-growing Rust CLI with headless execution, snapshots, permission modes, and model fleets. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Deep Agents Code | 2 | — | LangChain's official terminal coding agent gives the framework vendor a deployable first-party harness and has fast adoption. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| ForgeCode | 2 | — | An active multi-model terminal agent with custom agents and large-refactor tooling. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Freebuff (formerly Codebuff) | 2 | — | The product rebranded to Freebuff but the live repository is still CodebuffAI/codebuff; it remains a high-adoption multi-agent CLI family and needs the rename captured. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Google Antigravity 2.0 / CLI / SDK | 2 | Agent Harnesses & SDKs; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Google made Antigravity its forward developer-agent platform, with one harness across desktop, CLI, SDK, managed agents, and cloud use. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Grok Build | 2 | — | First-party open coding harness with plan review, plugins, skills, parallel subagents, worktrees, ACP, and rapid release cadence. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| IBM Bob | 2 | ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins | IBM's agentic SDLC platform has an unusually large enterprise deployment and coordinates planning, coding, testing, modernization, and governance. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| jcode | 2 | — | A high-momentum Rust harness optimized for many low-memory parallel sessions, native swarms, messaging, and conflict detection. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| JetBrains Junie GA / CLI delta | 2 | IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | Junie is now one engine across CLI, IDE, async execution, debugging, and PR review; the pack models only earlier Junie traces. | new family surface: existing family traces do not identify this specific mode/surface |
| Meta Muse Code | 2 | Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders | Meta's first-party, multi-agent-by-default coding CLI reached GA in 2026 and isolates parallel workers in worktrees. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Prime Agent | 2 | — | A self-improving coding agent with durable skills, daemon sessions, schedules, and an unusual Python-kernel tool boundary. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Qoder 1.0 portfolio delta | 2 | Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop. | new family surface: existing family traces do not identify this specific mode/surface |
| Reasonix | 2 | — | A fast-growing single-binary coding agent with terminal, desktop, browser, ACP, plan mode, and long unattended runs. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Snowflake Cortex Code (CoCo) | 2 | ADEs; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Snowflake reports broad adoption for a data-native coding agent spanning CLI, desktop, Snowsight, cloud agents, and agent teams. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Tau | 2 | — | Hugging Face's small, readable provider-neutral coding agent is both a practical CLI and a reference harness. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| TRAE 2026 platform delta | 2 | Agent Orchestrators & Fleet Managers; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface. | new family surface: existing family traces do not identify this specific mode/surface |
| Xiaomi MiMo Code | 2 | — | Xiaomi's official multi-provider coding CLI is a material new corporate entrant with active distribution and worktree support. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| GitHub Copilot 2026 surface delta | 3 | Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | Fusion, the GA Copilot CLI, Agent HQ, automations, and review effort modes materially expand the existing Copilot family beyond current pack semantics. | mode/control-plane: Fusion model selection and Agent HQ hosting add no distinct repository identity |

### 5.3 Agentic / AI-Native Terminals

Warp is covered; cmux, Paradev, tuios, and newer agent-aware terminal control planes are not.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| cmux | 2 | Agent Multiplexers & Herders | A fast-growing Ghostty-based terminal adds agent-aware workspaces, notifications, and automation for concurrent coding sessions. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Paradev (formerly Superset) | 2 | Agent Multiplexers & Herders; ADEs | The renamed open desktop workspace isolates parallel coding agents in worktrees and centralizes task, terminal, and diff review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| tuios | 2 | Agent Multiplexers & Herders | An active terminal window manager adds durable workspaces, agent-status detection, and a unified inbox for concurrent coding sessions. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |

### 5.4 Agent Multiplexers & Herders

Only the November source report covers a few exemplars; the active worktree/workspace category is broadly absent.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| AionUi | 2 | ADEs | A cross-platform desktop workspace manages multiple CLI-agent families, persistent sessions, scheduled work, and team-style delegation. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Block Berd | 2 | ADEs | Block's first-party desktop agent workspace extends the Goose lineage into shared agents, skills, connections, and worktree-backed projects. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Claude Squad | 2 | — | An established terminal multiplexer isolates several coding-agent sessions with tmux and Git worktrees. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| cmux | 2 | Agentic / AI-Native Terminals | A fast-growing Ghostty-based terminal adds agent-aware workspaces, notifications, and automation for concurrent coding sessions. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Coder Xum / Mux | 2 | ADEs | Coder's first-party parallel-agent desktop/workspace product matters because it connects agent control planes to enterprise developer infrastructure. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Emdash | 2 | ADEs | An open agentic development environment runs provider-independent coding agents in parallel, with worktree isolation and centralized review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Happy | 2 | ADEs | A high-momentum desktop and mobile client supervises Claude, Codex, and Grok sessions while reusing existing subscriptions. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| MausBot (OpenMausBot) | 2 | ADEs; Personal AI Daemons & Local Gateways | A fast-growing local-first workspace that normalizes multiple agent CLIs into persistent bots, multi-agent rooms, scheduled work, memory, approvals, and desktop/mobile access. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Meta Muse Code | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers | Meta's first-party, multi-agent-by-default coding CLI reached GA in 2026 and isolates parallel workers in worktrees. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Multica | 2 | Agent Orchestrators & Fleet Managers | A high-adoption self-hosted control plane coordinates people and multiple coding agents through tasks, workspaces, and review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| OpenChamber | 2 | ADEs | A fast-growing desktop environment wraps OpenCode sessions with project management, history, and agent-workspace controls. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Orchestrator.inc | 2 | Agent Orchestrators & Fleet Managers; ADEs | A cross-platform control plane takes tasks through isolated agent execution, supervision, review, and merged pull requests. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Paradev (formerly Superset) | 2 | Agentic / AI-Native Terminals; ADEs | The renamed open desktop workspace isolates parallel coding agents in worktrees and centralizes task, terminal, and diff review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Paseo | 2 | ADEs | A widely adopted desktop/mobile control plane provides remote steering, notifications, and review for concurrent coding agents. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Qoder 1.0 portfolio delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop. | new family surface: existing family traces do not identify this specific mode/surface |
| T3 Code | 2 | ADEs | A fast-growing desktop environment runs parallel coding agents in isolated worktrees and presents their progress and diffs for review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| tuios | 2 | Agentic / AI-Native Terminals | An active terminal window manager adds durable workspaces, agent-status detection, and a unified inbox for concurrent coding sessions. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Vibe Kanban | 2 | ADEs; Spec-Driven Development (SDD) & Task Planners | A high-adoption task and worktree layer dispatches multiple coding agents and exposes their plans, status, and diffs for review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Warp Oz / Factories delta | 2 | Agent Orchestrators & Fleet Managers; ADEs; Autonomous Cloud SWE Agents / Background Droids | Warp's current cloud orchestrator and software-lifecycle factories are not represented by the pack's terminal-native Warp signals. | new family surface: existing family traces do not identify this specific mode/surface |
| GitHub Copilot 2026 surface delta | 3 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | Fusion, the GA Copilot CLI, Agent HQ, automations, and review effort modes materially expand the existing Copilot family beyond current pack semantics. | mode/control-plane: Fusion model selection and Agent HQ hosting add no distinct repository identity |

### 5.5 Agent Orchestrators & Fleet Managers

Fleet-level task, queue, review, and agent-to-agent metadata are almost entirely outside current packs.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Docker Agent (formerly cagent) | 1 | Agent Harnesses & SDKs; Agent CLIs / TUIs | Docker's renamed, fast-moving agent builder and runtime ships in Docker Desktop and defines multi-agent teams, tools, models, and handoffs in portable YAML or HCL. | declarative agent definition: agent YAML/HCL plus Docker Agent schema or product-specific keys; a generic `agent.yaml` filename alone is unsafe |
| GitHub Agentic Workflows | 1 | — | GitHub's open workflow system compiles Markdown-defined agents into governed Actions jobs, creating a new repository-native automation surface. | workflow source: agentic workflow Markdown compiled under `.github/workflows/`; content/provenance required |
| GitLab Duo Agent Platform | 1 | Agent CLIs / TUIs; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | GitLab's GA platform embeds coding, review, pipeline-repair, security, custom, and external agents across the repository and delivery lifecycle, including self-managed deployments. | SCM activity + platform metadata: Duo service-account participation and `duo/(fix\|feature\|refactor\|docs)/...` branches; `AGENTS.md` alone is generic |
| Agent Teams | 2 | — | A current self-hosted orchestrator organizes heterogeneous coding agents into communicating teams with task boards and peer review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| AWS CLI Agent Orchestrator | 2 | — | AWS's open control plane coordinates coding CLIs in isolated tmux sessions with task decomposition and agent messaging. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Gastown | 2 | — | A well-adopted workspace manager coordinates multiple coding agents, Git worktrees, task state, and handoffs. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| JetBrains Air | 2 | ADEs; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | JetBrains is moving from a single IDE plugin to a multi-agent system spanning IDEs, web, CLI, cloud environments, teams, and governance. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Meta Muse Code | 2 | Agent CLIs / TUIs; Agent Multiplexers & Herders | Meta's first-party, multi-agent-by-default coding CLI reached GA in 2026 and isolates parallel workers in worktrees. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Multica | 2 | Agent Multiplexers & Herders | A high-adoption self-hosted control plane coordinates people and multiple coding agents through tasks, workspaces, and review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Omnigent | 2 | — | A fast-moving meta-harness provides one policy, sandbox, and collaboration layer across several interchangeable coding agents. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| OpenAI Symphony | 2 | — | OpenAI's open orchestration reference turns tracker work into isolated Codex implementation runs with reviewable outcomes. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| OpenRig | 2 | — | An active local orchestrator creates persistent teams from Claude Code, Codex, and Pi with shared context and explicit ownership. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Orchestrator.inc | 2 | Agent Multiplexers & Herders; ADEs | A cross-platform control plane takes tasks through isolated agent execution, supervision, review, and merged pull requests. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Qoder 1.0 portfolio delta | 2 | Agent CLIs / TUIs; Agent Multiplexers & Herders; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop. | new family surface: existing family traces do not identify this specific mode/surface |
| Ruflo | 2 | — | A large open orchestration project adds swarms, memory, routing, and governance around several coding-agent harnesses. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Scion | 2 | — | Google Cloud's open multi-agent orchestrator uses isolated worktrees, role assignment, and coordinated task execution for software work. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| TRAE 2026 platform delta | 2 | Agent CLIs / TUIs; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface. | new family surface: existing family traces do not identify this specific mode/surface |
| Warp Oz / Factories delta | 2 | Agent Multiplexers & Herders; ADEs; Autonomous Cloud SWE Agents / Background Droids | Warp's current cloud orchestrator and software-lifecycle factories are not represented by the pack's terminal-native Warp signals. | new family surface: existing family traces do not identify this specific mode/surface |
| GitHub Copilot 2026 surface delta | 3 | Agent CLIs / TUIs; Agent Multiplexers & Herders; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | Fusion, the GA Copilot CLI, Agent HQ, automations, and review effort modes materially expand the existing Copilot family beyond current pack semantics. | mode/control-plane: Fusion model selection and Agent HQ hosting add no distinct repository identity |

### 5.6 ADEs

Editor-like incumbents exist in the pack, but the agent-first workspace layer and corporate ADE launches are mostly missing.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| AionUi | 2 | Agent Multiplexers & Herders | A cross-platform desktop workspace manages multiple CLI-agent families, persistent sessions, scheduled work, and team-style delegation. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Block Berd | 2 | Agent Multiplexers & Herders | Block's first-party desktop agent workspace extends the Goose lineage into shared agents, skills, connections, and worktree-backed projects. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Coder Xum / Mux | 2 | Agent Multiplexers & Herders | Coder's first-party parallel-agent desktop/workspace product matters because it connects agent control planes to enterprise developer infrastructure. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Devin Desktop | 2 | AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins | The Windsurf successor combines an editor with local and cloud Devin agents and materially changes the old Cascade/Windsurf lineage. | new family surface: existing family traces do not identify this specific mode/surface |
| Emdash | 2 | Agent Multiplexers & Herders | An open agentic development environment runs provider-independent coding agents in parallel, with worktree isolation and centralized review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Google Antigravity 2.0 / CLI / SDK | 2 | Agent CLIs / TUIs; Agent Harnesses & SDKs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Google made Antigravity its forward developer-agent platform, with one harness across desktop, CLI, SDK, managed agents, and cloud use. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Happy | 2 | Agent Multiplexers & Herders | A high-momentum desktop and mobile client supervises Claude, Codex, and Grok sessions while reusing existing subscriptions. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| IBM Bob | 2 | Agent CLIs / TUIs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins | IBM's agentic SDLC platform has an unusually large enterprise deployment and coordinates planning, coding, testing, modernization, and governance. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| JetBrains Air | 2 | Agent Orchestrators & Fleet Managers; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | JetBrains is moving from a single IDE plugin to a multi-agent system spanning IDEs, web, CLI, cloud environments, teams, and governance. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| MausBot (OpenMausBot) | 2 | Agent Multiplexers & Herders; Personal AI Daemons & Local Gateways | A fast-growing local-first workspace that normalizes multiple agent CLIs into persistent bots, multi-agent rooms, scheduled work, memory, approvals, and desktop/mobile access. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| OpenChamber | 2 | Agent Multiplexers & Herders | A fast-growing desktop environment wraps OpenCode sessions with project management, history, and agent-workspace controls. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Orchestrator.inc | 2 | Agent Multiplexers & Herders; Agent Orchestrators & Fleet Managers | A cross-platform control plane takes tasks through isolated agent execution, supervision, review, and merged pull requests. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Paradev (formerly Superset) | 2 | Agentic / AI-Native Terminals; Agent Multiplexers & Herders | The renamed open desktop workspace isolates parallel coding agents in worktrees and centralizes task, terminal, and diff review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Paseo | 2 | Agent Multiplexers & Herders | A widely adopted desktop/mobile control plane provides remote steering, notifications, and review for concurrent coding agents. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Qoder 1.0 portfolio delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop. | new family surface: existing family traces do not identify this specific mode/surface |
| Snowflake Cortex Code (CoCo) | 2 | Agent CLIs / TUIs; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Snowflake reports broad adoption for a data-native coding agent spanning CLI, desktop, Snowsight, cloud agents, and agent teams. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| T3 Code | 2 | Agent Multiplexers & Herders | A fast-growing desktop environment runs parallel coding agents in isolated worktrees and presents their progress and diffs for review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| TRAE 2026 platform delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface. | new family surface: existing family traces do not identify this specific mode/surface |
| Vibe Kanban | 2 | Agent Multiplexers & Herders; Spec-Driven Development (SDD) & Task Planners | A high-adoption task and worktree layer dispatches multiple coding agents and exposes their plans, status, and diffs for review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Warp Oz / Factories delta | 2 | Agent Multiplexers & Herders; Agent Orchestrators & Fleet Managers; Autonomous Cloud SWE Agents / Background Droids | Warp's current cloud orchestrator and software-lifecycle factories are not represented by the pack's terminal-native Warp signals. | new family surface: existing family traces do not identify this specific mode/surface |
| Salesforce Agentforce Vibes | 3 | IDE Agent Extensions & Plugins; Full-Stack Scaffolding / App-Gen Agents | Salesforce ships a VS Code extension and browser IDE that coordinate isolated subagents to build apps, metadata, tests, and Agentforce agents. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |
| ServiceNow Build Agent | 3 | IDE Agent Extensions & Plugins; Full-Stack Scaffolding / App-Gen Agents | ServiceNow's autonomous developer builds and tests governed full-stack platform applications and can itself create agents and skills. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |

### 5.7 AI-Native IDEs (Forked Editors)

Core editor families are known, but 2026 successors and agent-manager surfaces need explicit lifecycle coverage.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Devin Desktop | 2 | ADEs; IDE Agent Extensions & Plugins | The Windsurf successor combines an editor with local and cloud Devin agents and materially changes the old Cascade/Windsurf lineage. | new family surface: existing family traces do not identify this specific mode/surface |
| Google Antigravity 2.0 / CLI / SDK | 2 | Agent CLIs / TUIs; Agent Harnesses & SDKs; ADEs; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Google made Antigravity its forward developer-agent platform, with one harness across desktop, CLI, SDK, managed agents, and cloud use. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| IBM Bob | 2 | Agent CLIs / TUIs; ADEs; IDE Agent Extensions & Plugins | IBM's agentic SDLC platform has an unusually large enterprise deployment and coordinates planning, coding, testing, modernization, and governance. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Qoder 1.0 portfolio delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; ADEs; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop. | new family surface: existing family traces do not identify this specific mode/surface |
| TRAE 2026 platform delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; ADEs; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface. | new family surface: existing family traces do not identify this specific mode/surface |

### 5.8 IDE Agent Extensions & Plugins

Mainstream extensions are partly covered; enterprise, Neovim, and platform-specific agents remain uneven.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| GitLab Duo Agent Platform | 1 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | GitLab's GA platform embeds coding, review, pipeline-repair, security, custom, and external agents across the repository and delivery lifecycle, including self-managed deployments. | SCM activity + platform metadata: Duo service-account participation and `duo/(fix\|feature\|refactor\|docs)/...` branches; `AGENTS.md` alone is generic |
| avante.nvim | 2 | — | One of the largest Neovim-native agent extensions, bringing repository chat, edits, tools, and provider choice into the editor. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Bito | 2 | — | A cross-surface IDE and PR-review agent with enterprise adoption and repository review activity. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| CodeCompanion.nvim | 2 | — | A substantial Neovim extension supports agent chat, inline changes, tools, workflows, and multiple model providers. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| Devin Desktop | 2 | ADEs; AI-Native IDEs (Forked Editors) | The Windsurf successor combines an editor with local and cloud Devin agents and materially changes the old Cascade/Windsurf lineage. | new family surface: existing family traces do not identify this specific mode/surface |
| Google Antigravity 2.0 / CLI / SDK | 2 | Agent CLIs / TUIs; Agent Harnesses & SDKs; ADEs; AI-Native IDEs (Forked Editors); Autonomous Cloud SWE Agents / Background Droids | Google made Antigravity its forward developer-agent platform, with one harness across desktop, CLI, SDK, managed agents, and cloud use. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| IBM Bob | 2 | Agent CLIs / TUIs; ADEs; AI-Native IDEs (Forked Editors) | IBM's agentic SDLC platform has an unusually large enterprise deployment and coordinates planning, coding, testing, modernization, and governance. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| JetBrains Air | 2 | Agent Orchestrators & Fleet Managers; ADEs; Autonomous Cloud SWE Agents / Background Droids | JetBrains is moving from a single IDE plugin to a multi-agent system spanning IDEs, web, CLI, cloud environments, teams, and governance. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| JetBrains Junie GA / CLI delta | 2 | Agent CLIs / TUIs; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | Junie is now one engine across CLI, IDE, async execution, debugging, and PR review; the pack models only earlier Junie traces. | new family surface: existing family traces do not identify this specific mode/surface |
| Qoder 1.0 portfolio delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; ADEs; AI-Native IDEs (Forked Editors); Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop. | new family surface: existing family traces do not identify this specific mode/surface |
| Snowflake Cortex Code (CoCo) | 2 | Agent CLIs / TUIs; ADEs; Autonomous Cloud SWE Agents / Background Droids | Snowflake reports broad adoption for a data-native coding agent spanning CLI, desktop, Snowsight, cloud agents, and agent teams. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| TRAE 2026 platform delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; ADEs; AI-Native IDEs (Forked Editors); Autonomous Cloud SWE Agents / Background Droids; Full-Stack Scaffolding / App-Gen Agents | TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface. | new family surface: existing family traces do not identify this specific mode/surface |
| CodeGPT | 3 | — | A long-running VS Code and JetBrains agent extension with multi-step edits, local and hosted models, and custom-agent support. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |
| Databricks Genie Code | 3 | — | Databricks' autonomous workspace agent plans and runs multi-step code, pipeline, dashboard, SQL, and ML work against governed data and lineage. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |
| GitHub Copilot 2026 surface delta | 3 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | Fusion, the GA Copilot CLI, Agent HQ, automations, and review effort modes materially expand the existing Copilot family beyond current pack semantics. | mode/control-plane: Fusion model selection and Agent HQ hosting add no distinct repository identity |
| Salesforce Agentforce Vibes | 3 | ADEs; Full-Stack Scaffolding / App-Gen Agents | Salesforce ships a VS Code extension and browser IDE that coordinate isolated subagents to build apps, metadata, tests, and Agentforce agents. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |
| ServiceNow Build Agent | 3 | ADEs; Full-Stack Scaffolding / App-Gen Agents | ServiceNow's autonomous developer builds and tests governed full-stack platform applications and can itself create agents and skills. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |
| Tabnine | 3 | — | A large enterprise IDE-agent install base and private deployment model remain strategically important as Tricentis integrates Tabnine's context engine into its agentic quality platform. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |

### 5.9 Autonomous Cloud SWE Agents / Background Droids

Known cloud agents exist, but web/cloud successors and multi-agent platforms need surface-aware provenance.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| GitLab Duo Agent Platform | 1 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; IDE Agent Extensions & Plugins; PR Review, Auto-Fix & Code Quality Bots | GitLab's GA platform embeds coding, review, pipeline-repair, security, custom, and external agents across the repository and delivery lifecycle, including self-managed deployments. | SCM activity + platform metadata: Duo service-account participation and `duo/(fix\|feature\|refactor\|docs)/...` branches; `AGENTS.md` alone is generic |
| Amp Orbs | 2 | — | Amp's scheduled and event-driven cloud Orbs extend the existing Amp agent beyond its pack-visible local/editor surface. | new family surface: existing family traces do not identify this specific mode/surface |
| Claude Code on the web delta | 2 | — | Anthropic's managed VM surface turns the known local product into a background cloud agent with different provenance and execution boundaries. | new family surface: existing family traces do not identify this specific mode/surface |
| Google Antigravity 2.0 / CLI / SDK | 2 | Agent CLIs / TUIs; Agent Harnesses & SDKs; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins | Google made Antigravity its forward developer-agent platform, with one harness across desktop, CLI, SDK, managed agents, and cloud use. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| JetBrains Air | 2 | Agent Orchestrators & Fleet Managers; ADEs; IDE Agent Extensions & Plugins | JetBrains is moving from a single IDE plugin to a multi-agent system spanning IDEs, web, CLI, cloud environments, teams, and governance. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| JetBrains Junie GA / CLI delta | 2 | Agent CLIs / TUIs; IDE Agent Extensions & Plugins; PR Review, Auto-Fix & Code Quality Bots | Junie is now one engine across CLI, IDE, async execution, debugging, and PR review; the pack models only earlier Junie traces. | new family surface: existing family traces do not identify this specific mode/surface |
| Qoder 1.0 portfolio delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Full-Stack Scaffolding / App-Gen Agents | Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop. | new family surface: existing family traces do not identify this specific mode/surface |
| Snowflake Cortex Code (CoCo) | 2 | Agent CLIs / TUIs; ADEs; IDE Agent Extensions & Plugins | Snowflake reports broad adoption for a data-native coding agent spanning CLI, desktop, Snowsight, cloud agents, and agent teams. | native client state: product-owned project config, hooks, sessions, or attribution require a source audit |
| TRAE 2026 platform delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Full-Stack Scaffolding / App-Gen Agents | TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface. | new family surface: existing family traces do not identify this specific mode/surface |
| Warp Oz / Factories delta | 2 | Agent Multiplexers & Herders; Agent Orchestrators & Fleet Managers; ADEs | Warp's current cloud orchestrator and software-lifecycle factories are not represented by the pack's terminal-native Warp signals. | new family surface: existing family traces do not identify this specific mode/surface |
| Background Agents / Open Inspect | 3 | — | An open reference implementation for issue-to-PR background coding agents, including isolated execution and review infrastructure. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |
| Datadog Bits AI: Investigation / Remediation | 3 | PR Review, Auto-Fix & Code Quality Bots; AIOps & Incident Auto-Remediation Agents | Datadog's always-on investigation agent now links telemetry-grounded root cause to governed infrastructure actions and code-fix pull requests through Bits Remediation. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| GitHub Copilot 2026 surface delta | 3 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; IDE Agent Extensions & Plugins; PR Review, Auto-Fix & Code Quality Bots | Fusion, the GA Copilot CLI, Agent HQ, automations, and review effort modes materially expand the existing Copilot family beyond current pack semantics. | mode/control-plane: Fusion model selection and Agent HQ hosting add no distinct repository identity |
| Sinatra | 3 | — | A current background coding agent with issue-to-PR positioning and active category comparison presence. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |
| Tembo | 3 | — | A multi-agent cloud execution platform that runs several coding-agent families in controlled workspaces. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |

### 5.10 PR Review, Auto-Fix & Code Quality Bots

The pack has several actors but misses most current benchmark leaders, canonical configs, and review-versus-authorship semantics.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| cubic | 1 | — | The current Code Review Bench leader combines PR review, local CLI review, custom agents, and background fixes. | project file + SCM activity: `cubic.yaml`; `@cubic-dev-ai` comments are activity |
| GitLab Duo Agent Platform | 1 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | GitLab's GA platform embeds coding, review, pipeline-repair, security, custom, and external agents across the repository and delivery lifecycle, including self-managed deployments. | SCM activity + platform metadata: Duo service-account participation and `duo/(fix\|feature\|refactor\|docs)/...` branches; `AGENTS.md` alone is generic |
| Greptile | 1 | — | A leading whole-repository review agent with current benchmark visibility and product-owned configuration. | project files + SCM activity: `.greptile/config.json`, `.greptile/rules.md`, `greptile.json` |
| Kody AI | 1 | — | A top current review benchmark entrant with self-hosting and a repository configuration contract. | project file + SCM activity: `kodus-config.yml`; `@kody` commands are activity |
| Claude Code Review delta | 2 | — | Anthropic's multi-agent review workflow is a distinct, current SCM surface not represented by Claude Code authorship/config detection. | new family surface: existing family traces do not identify this specific mode/surface |
| Codex Code Review delta | 2 | — | Codex now performs automatic and requested GitHub/GitLab reviews guided by repository AGENTS.md rules. | new family surface: existing family traces do not identify this specific mode/surface |
| Ellipsis | 2 | — | An established reviewer that can push fixes, crossing the boundary between commentary and authored changes. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| Gitar | 2 | — | A multi-forge review-and-fix agent acquired by Sonar in 2026, making it strategically important beyond its standalone adoption. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| Graphite Agent | 2 | — | Review embedded in a material stacked-PR and merge-queue platform remains a distinct workflow signal. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| Hyrax | 2 | — | A current detect-fix-verify PR agent focused on closing issues rather than only commenting. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| JetBrains Junie GA / CLI delta | 2 | Agent CLIs / TUIs; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Junie is now one engine across CLI, IDE, async execution, debugging, and PR review; the pack models only earlier Junie traces. | new family surface: existing family traces do not identify this specific mode/surface |
| Macroscope Review | 2 | — | A current code-review and cloud-agent portfolio with public category comparisons and measurable SCM participation. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| Semgrep Multimodal / Autofix | 2 | — | Semgrep's renamed AI layer combines contextual detection, triage, remediation guidance, and draft fix pull requests across code and dependency findings. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| Snyk Agent Fix | 2 | — | A major security vendor's agentic fix path produces a distinct security-to-code workflow. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| SonarQube AI CodeFix | 2 | — | A major code-quality vendor's agentic remediation path, now strategically linked to Gitar. | SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews |
| Datadog Bits AI: Investigation / Remediation | 3 | Autonomous Cloud SWE Agents / Background Droids; AIOps & Incident Auto-Remediation Agents | Datadog's always-on investigation agent now links telemetry-grounded root cause to governed infrastructure actions and code-fix pull requests through Bits Remediation. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| GitHub Copilot 2026 surface delta | 3 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Fusion, the GA Copilot CLI, Agent HQ, automations, and review effort modes materially expand the existing Copilot family beyond current pack semantics. | mode/control-plane: Fusion model selection and Agent HQ hosting add no distinct repository identity |

### 5.11 Spec-Driven Development (SDD) & Task Planners

Spec Kit, Taskmaster, Kiro, and Tessl are known; the highest-momentum open methodologies are still absent.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| BMAD-METHOD | 1 | — | A high-adoption methodology packages analyst, product, architecture, implementation, and review agents into a durable planning workflow. | project files: `_bmad/`, `_bmad-output/`; older `.bmad-*` is legacy |
| OpenSpec | 1 | — | A leading open spec-driven workflow stores proposals, requirements, design, tasks, and archived changes as reviewable project artifacts. | project files: `openspec/config.yaml`, `openspec/changes/`, `openspec/specs/` |
| Addy Osmani Agent Skills | 2 | Agent Plugin / Dotfile Frameworks | A very large curated skills repository packages engineering workflows for planning, implementation, testing, debugging, and review. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Agent OS | 2 | — | A durable SDD layer captures codebase standards, product context, specifications, and implementation plans for multiple coding agents. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Backlog.md | 2 | Rules Managers & Context Syncers | A Git-native task layer gives humans and coding agents shared backlog, status, acceptance, and handoff artifacts. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Google Conductor | 2 | — | Google's plugin brings a versioned specify-plan-implement workflow to Antigravity and Claude Code projects. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| GSD Core | 2 | — | A fast-growing spec-and-execution system turns goals into versioned plans, atomic tasks, verification gates, and resumable agent state. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| MoAI-ADK | 2 | — | A high-activity single-binary harness adds spec-driven planning, quality gates, synchronization, and model routing around Claude Code. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Spec Kitty | 2 | — | A Git-native SDD system combines specifications, governed missions, worktrees, and verification across different agent harnesses. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Superpowers | 2 | Agent Plugin / Dotfile Frameworks | A very large portable skills framework applies planning, test-driven development, debugging, verification, and fresh-context review across agents. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Vibe Kanban | 2 | Agent Multiplexers & Herders; ADEs | A high-adoption task and worktree layer dispatches multiple coding agents and exposes their plans, status, and diffs for review. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Zenflow | 2 | — | A current commercial SDD workbench that combines specs, worktrees, verification gates, and multi-agent review. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Google Elephant-Goldfish Model | 3 | Agent Plugin / Dotfile Frameworks | Google's plugin separates planning from a fresh-context critic, making deliberate context reset a reusable design-and-review pattern. | portable plugin: plugin/skill installation artifacts identify EGM content, not the host agent |

### 5.12 Rules Managers & Context Syncers

rulesync is covered, but Ruler, routing, templates, and Git-native task/context layers are missing.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Ruler | 1 | — | The leading cross-agent rules manager compiles one source of project instructions, MCP settings, and skills into many client-specific formats. | project files: `ruler.toml` and `.ruler/` |
| Backlog.md | 2 | Spec-Driven Development (SDD) & Task Planners | A Git-native task layer gives humans and coding agents shared backlog, status, acceptance, and handoff artifacts. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Claude Code Router | 2 | Personal AI Daemons & Local Gateways | A widely adopted local routing layer redirects Claude Code across model providers and adds reusable tool and workflow controls. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Context7 | 3 | — | A heavily adopted documentation-context service and MCP integration that changes what coding agents read without identifying the executing client. | portable shared content: identifies a format/package, not the executing client without provenance |
| Gitingest | 3 | — | A high-adoption repository-to-prompt context tool that represents the externalized context layer around coding agents. | portable shared content: identifies a format/package, not the executing client without provenance |
| Repomix | 3 | — | A widely used repository-to-context packager whose generated artifacts and integrations are relevant to measuring agent context workflows. | portable shared content: identifies a format/package, not the executing client without provenance |

### 5.13 Agent Plugin / Dotfile Frameworks

Portable skills appear as shared paths, while new standards, marketplaces, provenance, and corporate skill portfolios are not modeled.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Addy Osmani Agent Skills | 2 | Spec-Driven Development (SDD) & Task Planners | A very large curated skills repository packages engineering workflows for planning, implementation, testing, debugging, and review. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Agent Plugins 1.0 | 2 | — | A new cross-vendor package format for distributing Agent Skills and MCP servers, governed by maintainers from seven major agent platforms. | portable content conjunction: `plugin.json` plus the Agent Plugins schema URL/version |
| Superpowers | 2 | Spec-Driven Development (SDD) & Task Planners | A very large portable skills framework applies planning, test-driven development, debugging, verification, and fresh-context review across agents. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| Agent Skills standard | 3 | — | Anthropic reports more than 70 compatible platforms, one million published skills, and nearly 280 million installs before donating the format to AAIF. | portable shared file: `SKILL.md` proves the standard, never the executing product |
| AWS Agent Toolkit | 3 | — | AWS packages managed MCP access, 75+ skills, plugins, and rules for Kiro, Claude Code, Cursor, Codex, and Devin. | portable shared content: identifies a format/package, not the executing client without provenance |
| Claude Code Templates | 3 | — | A large registry and installer distributes Claude Code agents, commands, skills, hooks, MCP definitions, and settings. | portable shared content: identifies a format/package, not the executing client without provenance |
| Google Elephant-Goldfish Model | 3 | Spec-Driven Development (SDD) & Task Planners | Google's plugin separates planning from a fresh-context critic, making deliberate context reset a reusable design-and-review pattern. | portable plugin: plugin/skill installation artifacts identify EGM content, not the host agent |
| Google Skills | 3 | — | Google's first-party skills repository distributes product- and platform-specific procedures to compatible coding agents. | portable shared content: identifies a format/package, not the executing client without provenance |
| MCP reference servers | 3 | — | The reference tool ecosystem remains central to agent extensibility and is important context for plugin and dependency measurements. | portable shared content: identifies a format/package, not the executing client without provenance |
| Microsoft .NET Agent Skills | 3 | — | Microsoft's first-party skills encode current .NET and C# development practices for portable agent consumption. | portable shared content: identifies a format/package, not the executing client without provenance |
| Oh My Codex | 3 | — | A substantial Codex extension layer adds hooks, specialized agents, teams, status displays, and packaged workflows. | portable shared content: identifies a format/package, not the executing client without provenance |

### 5.14 Personal AI Daemons & Local Gateways

OpenClaw is researched, but its fast-growing ecosystem and the gateway/control-plane layer are largely absent.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Claude Code Router | 2 | Rules Managers & Context Syncers | A widely adopted local routing layer redirects Claude Code across model providers and adds reusable tool and workflow controls. | project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification |
| MausBot (OpenMausBot) | 2 | Agent Multiplexers & Herders; ADEs | A fast-growing local-first workspace that normalizes multiple agent CLIs into persistent bots, multi-agent rooms, scheduled work, memory, approvals, and desktop/mobile access. | orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream |
| Agent Zero | 3 | — | A large self-hosted agent runtime provides a full Linux environment, hierarchical agents, persistent memory, tools, and browser automation. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| Bifrost | 3 | — | A fast-growing high-performance gateway combines model routing, failover, budgets, guardrails, caching, and MCP access for agent workloads. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| IronClaw | 3 | — | NEAR AI's personal-agent operating layer emphasizes privacy, capability isolation, extensibility, and long-running local work. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| LiteLLM | 3 | — | A major open gateway standardizes model access, routing, budgets, guardrails, logging, and fallback behavior across agent clients. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| LobeHub | 3 | — | A large multi-user agent workspace connects persistent agents to team chat, tools, knowledge, and scheduled autonomous work. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| nanobot | 3 | — | A fast-growing lightweight personal-agent runtime combines messaging channels, tools, memory, schedules, and local deployment. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| NanoClaw | 3 | — | A fast-growing container-isolated personal agent connects messaging channels to memory, schedules, skills, and Anthropic's Agent SDK. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| NVIDIA OpenShell / NemoClaw | 3 | Agent Harnesses & SDKs | NVIDIA's first-party sandbox/runtime stack explicitly hosts OpenClaw, Hermes, and other long-running agents and has fast adoption. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| Octop | 3 | — | Tencent Cloud's self-hosted assistant supports multiple users, agents, models, tools, and messaging entry points. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| Ollama | 3 | — | The dominant local model runtime is a strategic enabling layer for coding and personal agents, although ordinary use is not agent-specific. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| Open Interpreter | 3 | — | A large local execution agent gives models controlled access to code, shell, files, and computer-use workflows. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| Open WebUI | 3 | — | A very large self-hosted model interface now includes tools, pipelines, memory, and agent workflows, making it a consequential local gateway layer. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| OpenHuman | 3 | — | A high-momentum open harness focuses on running large numbers of persistent personal or task agents on modest infrastructure. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| OpenWorker | 3 | — | Andrew Ng's open persistent-worker runtime gives agents schedules, tools, memory, and deployable long-running jobs. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| PicoClaw | 3 | — | A compact personal-agent runtime targets low-resource devices while retaining messaging, tools, memory, and scheduled work. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| Portkey / Prisma AIRS AI Gateway | 3 | — | The acquired enterprise gateway provides model routing, policy, observability, and guardrails under Palo Alto Networks' Prisma AIRS portfolio. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| QwenPaw | 3 | — | Alibaba's fast-growing self-hosted personal-agent surface connects AgentScope-based agents to several messaging platforms. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |
| ZeroClaw | 3 | — | A high-momentum Rust personal-agent runtime emphasizes small binaries, local deployment, swappable providers, and persistent automation. | runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible |

### 5.15 AIOps & Incident Auto-Remediation Agents

Sentry is the lone strong pack entry; nearly the whole AI SRE market remains telemetry-native and unrepresented.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Azure SRE Agent | 1 | — | Microsoft's real Azure resource supports source, telemetry, subagents, hooks, MCP, IaC export, and configured remediation. | IaC/config bundle: `agent.json`, `connectors.json`, `roles.yaml`, and `config/{skills,subagents,hooks}/` as a conjunction |
| Anyshift | 3 | — | A topology-grounded agent whose infrastructure graph provides a differentiated causal-investigation path. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| AWS DevOps Agent | 3 | — | A hyperscaler-backed GA incident agent with broad observability and incident-system integrations. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Cleric | 3 | — | A specialist autonomous investigation platform repeatedly present in current AI SRE maps. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Datadog Bits AI: Investigation / Remediation | 3 | Autonomous Cloud SWE Agents / Background Droids; PR Review, Auto-Fix & Code Quality Bots | Datadog's always-on investigation agent now links telemetry-grounded root cause to governed infrastructure actions and code-fix pull requests through Bits Remediation. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Dynatrace SRE Agent | 3 | — | Dynatrace's autonomous SRE Agent investigates detected problems, records root causes and recommendations, and can hand grounded context to cloud remediation agents. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| HolmesGPT | 3 | — | The leading open-source AI SRE investigation agent provides a rare measurable counterpoint to closed observability platforms. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| incident.io Investigations | 3 | — | A prominent incident-management vendor's investigation agent links telemetry, code changes, and incident workflow. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Metoro | 3 | — | A current Kubernetes and cloud investigation agent with production-focused positioning. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Mezmo AURA | 3 | — | An open execution harness for production investigation that creates an alternative to closed AI SRE agents. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| NeuBird Hawkeye | 3 | — | A specialist enterprise AI SRE with active discussion of governed production investigation. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| New Relic AI | 3 | — | A major observability portfolio with AI investigation that remains mostly SaaS-visible. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| PagerDuty Paige (SRE Agent) | 3 | — | PagerDuty's GA SRE agent combines incident context, runbooks, logs, memory, recommended playbooks, and approved remediation inside the incumbent on-call platform. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Resolve AI | 3 | — | A well-funded AI production engineer with graduated remediation autonomy and substantial market attention. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Rootly AI SRE | 3 | — | A current incident platform with agent investigation, MCP integration, and remediation workflow. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| ServiceNow ITOM Prime / AIOps AI Specialist | 3 | — | ITOM Prime adds agentic alert triage, impact analysis, root-cause investigation, and an AIOps AI Specialist inside ServiceNow's governed operations platform. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Splunk AI SRE | 3 | — | Splunk's GA AI SRE spans alert grouping, telemetry-grounded root-cause investigation, impact analysis, and guided remediation inside Observability Cloud. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Struct | 3 | — | An AI incident agent emphasizing bounded remediation and cross-telemetry investigation. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |
| Traversal | 3 | — | A funded AI SRE specialist repeatedly included in current enterprise buyer maps. | telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent |

### 5.16 Full-Stack Scaffolding / App-Gen Agents

GPT-Engineer is covered, while the dominant hosted builders and enterprise app agents are overwhelmingly absent.

| Candidate | Tier | Other categories | Why it matters | Measurement posture |
|---|---:|---|---|---|
| Builder.io Fusion | 1 | — | A repo-native visual coding agent with the distinctive .builderrules contract and bot-mediated PR workflow. | project file + SCM activity: `.builderrules`; Builder bot comments/commits need channel separation |
| Lovable | 1 | — | One of the most-used prompt-to-full-stack platforms, with optional Git sync and exact current and legacy bot identities. | author/bot + recovery branch: `lovable-dev[bot]`, legacy `gpt-engineer-app[bot]`, `lovable-sync*` |
| Base44 | 2 | — | A fast-growing acquired visual app builder with a product-owned config path and unresolved exact shared-connection identity. | project file + unresolved identity: `base44/config.jsonc`; exact shared-connection identity still needs sampling |
| Qoder 1.0 portfolio delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; Agent Multiplexers & Herders; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop. | new family surface: existing family traces do not identify this specific mode/surface |
| TRAE 2026 platform delta | 2 | Agent CLIs / TUIs; Agent Orchestrators & Fleet Managers; ADEs; AI-Native IDEs (Forked Editors); IDE Agent Extensions & Plugins; Autonomous Cloud SWE Agents / Background Droids | TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface. | new family surface: existing family traces do not identify this specific mode/surface |
| VibeSDK | 2 | — | Cloudflare's open reference implementation makes the full app-builder stack itself measurable and reproducible. | dependency/manifest content: package or import literal; no unique path assumed |
| Bolt.new | 3 | — | A category leader for browser-native app generation whose automatic commits are durable but not yet source-attributable. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |
| Emergent | 3 | — | A prominent full-stack and mobile multi-agent builder repeatedly present in current category comparisons. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |
| Figma Make | 3 | — | A major design vendor's prompt-to-interactive-prototype and code workflow is strategically important at the design/code boundary. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |
| Replit Agent | 3 | — | A major end-to-end builder inside a mature cloud IDE and deployment platform. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |
| Salesforce Agentforce Vibes | 3 | ADEs; IDE Agent Extensions & Plugins | Salesforce ships a VS Code extension and browser IDE that coordinate isolated subagents to build apps, metadata, tests, and Agentforce agents. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |
| SAP Joule Studio | 3 | Agent Harnesses & SDKs | SAP's intent-based environment builds agents, apps, and workflows through browser and pro-code CLI flows over a managed runtime. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |
| ServiceNow Build Agent | 3 | ADEs; IDE Agent Extensions & Plugins | ServiceNow's autonomous developer builds and tests governed full-stack platform applications and can itself create agents and skills. | platform metadata: platform artifacts may identify the host but not necessarily agent execution |
| v0 | 3 | — | Vercel's UI-first generator has evolved toward full-stack apps and an API while remaining a strategically distinct surface from AI SDK. | hosted control plane: Git sync may be user-controlled and no fixed identity is assumed |

---

## 6. Candidate Dossiers

### 6.1 Addy Osmani Agent Skills

**Categories:** Spec-Driven Development (SDD) & Task Planners, Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Google / Addy Osmani  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A very large curated skills repository packages engineering workflows for planning, implementation, testing, debugging, and review.  
**Adoption:** 114,114 GitHub stars; 11,919 forks; 148 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 148 commits/30d; latest release 0.6.15 on 2026-10-31.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** 114,114 GitHub stars; 11,919 forks; 148 default-branch commits/30d, checked 2026-11-09; **M4** 148 commits/30d; latest release 0.6.15 on 2026-10-31; **C5** major corporate backing: Google / Addy Osmani; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I5** A very large curated skills repository packages engineering workflows for planning, implementation, testing, debugging, and review.  
**Sources:** [primary](https://github.com/addyosmani/agent-skills); [repository metadata](https://github.com/addyosmani/agent-skills); checked 2026-11-09.

### 6.2 Agent OS

**Categories:** Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** Builder Methods  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A durable SDD layer captures codebase standards, product context, specifications, and implementation plans for multiple coding agents.  
**Adoption:** 5,588 GitHub stars; 831 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release v3.0.0 on 2026-01-20.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 5,588 GitHub stars; 831 forks; 0 default-branch commits/30d, checked 2026-11-09; **M2** 0 commits/30d; latest release v3.0.0 on 2026-01-20; **C3** dedicated company, project organization, or research group: Builder Methods; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I4** A durable SDD layer captures codebase standards, product context, specifications, and implementation plans for multiple coding agents.  
**Sources:** [primary](https://github.com/buildermethods/agent-os); [repository metadata](https://github.com/buildermethods/agent-os); checked 2026-11-09.

### 6.3 Agent Plugins 1.0

**Categories:** Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Vendor-neutral TSC: AWS, Cursor, GitHub, Microsoft, OpenAI, Vercel, Google  
**Coverage decision:** net-new cross-agent packaging standard; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A new cross-vendor package format for distributing Agent Skills and MCP servers, governed by maintainers from seven major agent platforms.  
**Adoption:** 1,440 GitHub stars; 79 forks; 4 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 4 commits/30d; repository pushed 2026-11-06.  
**Measurement posture:** portable content conjunction; candidate `'plugin.json' plus the Agent Plugins schema URL/version`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 1,440 GitHub stars; 79 forks; 4 default-branch commits/30d, checked 2026-11-09; **M2** 4 commits/30d; repository pushed 2026-11-06; **C5** major corporate backing: Vendor-neutral TSC: AWS, Cursor, GitHub, Microsoft, OpenAI, Vercel, Google; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** portable content conjunction: `plugin.json` plus the Agent Plugins schema URL/version; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** A new cross-vendor package format for distributing Agent Skills and MCP servers, governed by maintainers from seven major agent platforms.  
**Sources:** [primary](https://github.com/agentplugins/agent-plugins-spec); [repository metadata](https://github.com/agentplugins/agent-plugins-spec); checked 2026-11-09.

### 6.4 Agent Skills standard

**Categories:** Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Agentic AI Foundation / Linux Foundation  
**Coverage decision:** uncovered standards, governance, and provenance layer; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Anthropic reports more than 70 compatible platforms, one million published skills, and nearly 280 million installs before donating the format to AAIF.  
**Adoption:** Anthropic reports 1 million published skills, nearly 280 million installs, and 70+ compatible platforms as of 2026-10-22; 27,075 GitHub stars; 2,011 forks; 2 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 2 commits/30d; repository pushed 2026-11-04.  
**Measurement posture:** portable shared file; candidate `'SKILL.md' proves the standard, never the executing product`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** Anthropic reports 1 million published skills, nearly 280 million installs, and 70+ compatible platforms as of 2026-10-22; 27,075 GitHub stars; 2,011 forks; 2 default-branch commits/30d, checked 2026-11-09; **M2** 2 commits/30d; repository pushed 2026-11-04; **C4** standards-foundation or cross-vendor backing: Agentic AI Foundation / Linux Foundation; **D5** candidate string appeared 21 times in six retained 30-day research corpora; literal attention hint, not unique posts; **F1** portable shared file: `SKILL.md` proves the standard, never the executing product; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I3** Anthropic reports more than 70 compatible platforms, one million published skills, and nearly 280 million installs before donating the format to AAIF.  
**Sources:** [primary](https://www.anthropic.com/news/donating-agent-skills-to-the-agentic-ai-foundation); [repository metadata](https://github.com/agentskills/agentskills); checked 2026-11-09.

### 6.5 Agent Teams

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** Independent / 777genius  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A current self-hosted orchestrator organizes heterogeneous coding agents into communicating teams with task boards and peer review.  
**Adoption:** 2,448 GitHub stars; 399 forks; 1,089 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,089 commits/30d; latest release v2.18.6 on 2026-11-05.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 2,448 GitHub stars; 399 forks; 1,089 default-branch commits/30d, checked 2026-11-09; **M5** 1,089 commits/30d; latest release v2.18.6 on 2026-11-05; **C1** independent or community backing: Independent / 777genius; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A current self-hosted orchestrator organizes heterogeneous coding agents into communicating teams with task boards and peer review.  
**Sources:** [primary](https://github.com/777genius/agent-teams-ai); [repository metadata](https://github.com/777genius/agent-teams-ai); checked 2026-11-09.

### 6.6 Agent Zero

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Agent Zero  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A large self-hosted agent runtime provides a full Linux environment, hierarchical agents, persistent memory, tools, and browser automation.  
**Adoption:** 19,802 GitHub stars; 3,872 forks; 144 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 144 commits/30d; latest release v2.15 on 2026-11-01.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** 19,802 GitHub stars; 3,872 forks; 144 default-branch commits/30d, checked 2026-11-09; **M5** 144 commits/30d; latest release v2.15 on 2026-11-01; **C3** dedicated company, project organization, or research group: Agent Zero; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A large self-hosted agent runtime provides a full Linux environment, hierarchical agents, persistent memory, tools, and browser automation.  
**Sources:** [primary](https://github.com/agent0ai/agent-zero); [repository metadata](https://github.com/agent0ai/agent-zero); checked 2026-11-09.

### 6.7 AgentScope

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Alibaba / AgentScope team  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Alibaba's fast-growing framework combines multi-agent construction with runtime, observability, evaluation, and deployment tooling.  
**Adoption:** 35k+ stars and about 2.6k stars gained in 30 days in independent November tracking; 35,618 GitHub stars; 3,822 forks; 154 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 154 commits/30d; latest release v2.0.11 on 2026-10-27.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** 35k+ stars and about 2.6k stars gained in 30 days in independent November tracking; 35,618 GitHub stars; 3,822 forks; 154 default-branch commits/30d, checked 2026-11-09; **M4** 154 commits/30d; latest release v2.0.11 on 2026-10-27; **C5** major corporate backing: Alibaba / AgentScope team; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** Alibaba's fast-growing framework combines multi-agent construction with runtime, observability, evaluation, and deployment tooling.  
**Sources:** [primary](https://github.com/agentscope-ai/agentscope); [repository metadata](https://github.com/agentscope-ai/agentscope); checked 2026-11-09.

### 6.8 Agno

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Agno  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-adoption Python framework for agents, teams, workflows, memory, storage, and model-provider portability.  
**Adoption:** 43,110 GitHub stars; 6,263 forks; 171 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 171 commits/30d; latest release v3.1.12 on 2026-10-29.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 43,110 GitHub stars; 6,263 forks; 171 default-branch commits/30d, checked 2026-11-09; **M4** 171 commits/30d; latest release v3.1.12 on 2026-10-29; **C3** dedicated company, project organization, or research group: Agno; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I4** A high-adoption Python framework for agents, teams, workflows, memory, storage, and model-provider portability.  
**Sources:** [primary](https://github.com/agno-agi/agno); [repository metadata](https://github.com/agno-agi/agno); checked 2026-11-09.

### 6.9 AionUi

**Categories:** Agent Multiplexers & Herders, ADEs  
**Parent/backing:** iOfficeAI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A cross-platform desktop workspace manages multiple CLI-agent families, persistent sessions, scheduled work, and team-style delegation.  
**Adoption:** 34,131 GitHub stars; 3,570 forks; 14 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 14 commits/30d; latest release v2.2.2 on 2026-09-09.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 34,131 GitHub stars; 3,570 forks; 14 default-branch commits/30d, checked 2026-11-09; **M4** 14 commits/30d; latest release v2.2.2 on 2026-09-09; **C3** dedicated company, project organization, or research group: iOfficeAI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A cross-platform desktop workspace manages multiple CLI-agent families, persistent sessions, scheduled work, and team-style delegation.  
**Sources:** [primary](https://github.com/iOfficeAI/AionUi); [repository metadata](https://github.com/iOfficeAI/AionUi); checked 2026-11-09.

### 6.10 Amp Orbs

**Categories:** Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** Sourcegraph  
**Coverage decision:** uncovered scheduled cloud-agent surface; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Amp's scheduled and event-driven cloud Orbs extend the existing Amp agent beyond its pack-visible local/editor surface.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Sourcegraph; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I5** Amp's scheduled and event-driven cloud Orbs extend the existing Amp agent beyond its pack-visible local/editor surface.  
**Sources:** [primary](https://ampcode.com/); checked 2026-11-09.

### 6.11 Anyshift

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Anyshift  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A topology-grounded agent whose infrastructure graph provides a differentiated causal-investigation path.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Anyshift; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A topology-grounded agent whose infrastructure graph provides a differentiated causal-investigation path.  
**Sources:** [primary](https://www.anyshift.io/); checked 2026-11-09.

### 6.12 avante.nvim

**Categories:** IDE Agent Extensions & Plugins  
**Parent/backing:** Avante community  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** One of the largest Neovim-native agent extensions, bringing repository chat, edits, tools, and provider choice into the editor.  
**Adoption:** 18,183 GitHub stars; 856 forks; 124 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 124 commits/30d; latest release v0.5.0 on 2026-10-31.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 18,183 GitHub stars; 856 forks; 124 default-branch commits/30d, checked 2026-11-09; **M4** 124 commits/30d; latest release v0.5.0 on 2026-10-31; **C1** independent or community backing: Avante community; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** One of the largest Neovim-native agent extensions, bringing repository chat, edits, tools, and provider choice into the editor.  
**Sources:** [primary](https://github.com/avante-corp/avante.nvim); [repository metadata](https://github.com/avante-corp/avante.nvim); checked 2026-11-09.

### 6.13 AWS Agent Toolkit

**Categories:** Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Amazon Web Services  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** AWS packages managed MCP access, 75+ skills, plugins, and rules for Kiro, Claude Code, Cursor, Codex, and Devin.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Amazon Web Services; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I5** AWS packages managed MCP access, 75+ skills, plugins, and rules for Kiro, Claude Code, Cursor, Codex, and Devin.  
**Sources:** [primary](https://aws.amazon.com/products/developer-tools/agent-toolkit-for-aws/); checked 2026-11-09.

### 6.14 AWS Bedrock AgentCore Harness

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Amazon Web Services  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** AWS now ships the orchestration loop itself as a managed, model-agnostic microVM harness; it is strategically distinct from the Strands SDK.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Amazon Web Services; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I5** AWS now ships the orchestration loop itself as a managed, model-agnostic microVM harness; it is strategically distinct from the Strands SDK.  
**Sources:** [primary](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/harness.html); checked 2026-11-09.

### 6.15 AWS CLI Agent Orchestrator

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** Amazon Web Services  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** AWS's open control plane coordinates coding CLIs in isolated tmux sessions with task decomposition and agent messaging.  
**Adoption:** 1,528 GitHub stars; 317 forks; 200 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 200 commits/30d; latest release v2.5.3 on 2026-10-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 1,528 GitHub stars; 317 forks; 200 default-branch commits/30d, checked 2026-11-09; **M4** 200 commits/30d; latest release v2.5.3 on 2026-10-08; **C5** major corporate backing: Amazon Web Services; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I5** AWS's open control plane coordinates coding CLIs in isolated tmux sessions with task decomposition and agent messaging.  
**Sources:** [primary](https://github.com/awslabs/cli-agent-orchestrator); [repository metadata](https://github.com/awslabs/cli-agent-orchestrator); checked 2026-11-09.

### 6.16 AWS DevOps Agent

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Amazon Web Services  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A hyperscaler-backed GA incident agent with broad observability and incident-system integrations.  
**Adoption:** AWS GA hyperscaler product; no independent installation census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** AWS GA hyperscaler product; no independent installation census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Amazon Web Services; **D3** candidate string appeared 6 times in six retained 30-day research corpora; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** A hyperscaler-backed GA incident agent with broad observability and incident-system integrations.  
**Sources:** [primary](https://aws.amazon.com/devops-agent/); checked 2026-11-09.

### 6.17 Azure SRE Agent

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Microsoft  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Microsoft's real Azure resource supports source, telemetry, subagents, hooks, MCP, IaC export, and configured remediation.  
**Adoption:** Microsoft Azure resource with public docs and IaC support; no independent deployment census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** IaC/config bundle; candidate `'agent.json', 'connectors.json', 'roles.yaml', and 'config/{skills,subagents,hooks}/' as a conjunction`; collision medium; schema no-conjunction.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A5** Microsoft Azure resource with public docs and IaC support; no independent deployment census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Microsoft; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** IaC/config bundle: `agent.json`, `connectors.json`, `roles.yaml`, and `config/{skills,subagents,hooks}/` as a conjunction; **V5** net-new measurement series; **R3** medium; **E1** no-conjunction; **I5** Microsoft's real Azure resource supports source, telemetry, subagents, hooks, MCP, IaC export, and configured remediation.  
**Sources:** [primary](https://learn.microsoft.com/en-us/azure/sre-agent/overview); checked 2026-11-09.

### 6.18 Background Agents / Open Inspect

**Categories:** Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** Open Inspect  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An open reference implementation for issue-to-PR background coding agents, including isolated execution and review infrastructure.  
**Adoption:** 3,471 GitHub stars; 507 forks; 260 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 260 commits/30d; repository pushed 2026-11-08.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A2** 3,471 GitHub stars; 507 forks; 260 default-branch commits/30d, checked 2026-11-09; **M4** 260 commits/30d; repository pushed 2026-11-08; **C3** dedicated company, project organization, or research group: Open Inspect; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** An open reference implementation for issue-to-PR background coding agents, including isolated execution and review infrastructure.  
**Sources:** [primary](https://github.com/open-inspect/background-agents); [repository metadata](https://github.com/open-inspect/background-agents); checked 2026-11-09.

### 6.19 Backlog.md

**Categories:** Spec-Driven Development (SDD) & Task Planners, Rules Managers & Context Syncers  
**Parent/backing:** Independent / MrLesk  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A Git-native task layer gives humans and coding agents shared backlog, status, acceptance, and handoff artifacts.  
**Adoption:** 7,316 GitHub stars; 481 forks; 97 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 97 commits/30d; latest release v1.55.3 on 2026-10-23.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 7,316 GitHub stars; 481 forks; 97 default-branch commits/30d, checked 2026-11-09; **M4** 97 commits/30d; latest release v1.55.3 on 2026-10-23; **C1** independent or community backing: Independent / MrLesk; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I4** A Git-native task layer gives humans and coding agents shared backlog, status, acceptance, and handoff artifacts.  
**Sources:** [primary](https://github.com/MrLesk/Backlog.md); [repository metadata](https://github.com/MrLesk/Backlog.md); checked 2026-11-09.

### 6.20 Base44

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Wix  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing acquired visual app builder with a product-owned config path and unresolved exact shared-connection identity.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** project file + unresolved identity; candidate `'base44/config.jsonc'; exact shared-connection identity still needs sampling`; collision medium; schema yes-partial.  
**Robbes relevance:** conditional — product-owned path is visible, but shared-connection identity is unresolved.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Wix; **D2** candidate string appeared 2 time(s); no strong candidate-specific discussion cluster retained; **F3** project file + unresolved identity: `base44/config.jsonc`; exact shared-connection identity still needs sampling; **V4** important but needs source/schema work; **R3** medium; **E4** yes-partial; **I5** A fast-growing acquired visual app builder with a product-owned config path and unresolved exact shared-connection identity.  
**Sources:** [primary](https://docs.base44.com/); checked 2026-11-09.

### 6.21 Bifrost

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Maxim AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing high-performance gateway combines model routing, failover, budgets, guardrails, caching, and MCP access for agent workloads.  
**Adoption:** 9,437 GitHub stars; 1,551 forks; 1,137 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,137 commits/30d; latest release transports/v2.5.0 on 2026-11-06.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** 9,437 GitHub stars; 1,551 forks; 1,137 default-branch commits/30d, checked 2026-11-09; **M5** 1,137 commits/30d; latest release transports/v2.5.0 on 2026-11-06; **C3** dedicated company, project organization, or research group: Maxim AI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A fast-growing high-performance gateway combines model routing, failover, budgets, guardrails, caching, and MCP access for agent workloads.  
**Sources:** [primary](https://github.com/maximhq/bifrost); [repository metadata](https://github.com/maximhq/bifrost); checked 2026-11-09.

### 6.22 Bito

**Categories:** IDE Agent Extensions & Plugins  
**Parent/backing:** Bito  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A cross-surface IDE and PR-review agent with enterprise adoption and repository review activity.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Bito; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** A cross-surface IDE and PR-review agent with enterprise adoption and repository review activity.  
**Sources:** [primary](https://bito.ai/); checked 2026-11-09.

### 6.23 Block Berd

**Categories:** Agent Multiplexers & Herders, ADEs  
**Parent/backing:** Block  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Block's first-party desktop agent workspace extends the Goose lineage into shared agents, skills, connections, and worktree-backed projects.  
**Adoption:** 1,043 GitHub stars; 134 forks; 43 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 43 commits/30d; latest release v0.6.5 on 2026-11-04.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 1,043 GitHub stars; 134 forks; 43 default-branch commits/30d, checked 2026-11-09; **M5** 43 commits/30d; latest release v0.6.5 on 2026-11-04; **C5** major corporate backing: Block; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I5** Block's first-party desktop agent workspace extends the Goose lineage into shared agents, skills, connections, and worktree-backed projects.  
**Sources:** [primary](https://github.com/block/berd); [repository metadata](https://github.com/block/berd); checked 2026-11-09.

### 6.24 BMAD-METHOD

**Categories:** Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** BMad Code LLC  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-adoption methodology packages analyst, product, architecture, implementation, and review agents into a durable planning workflow.  
**Adoption:** 55,135 GitHub stars; 6,144 forks; 59 default-branch commits/30d; 21,944 npm downloads/week (`bmad-method`, 2026-11-01–07), checked 2026-11-09.  
**Momentum:** 59 commits/30d; latest release v6.12.4 on 2026-10-14.  
**Measurement posture:** project files; candidate `'_bmad/', '_bmad-output/'; older '.bmad-*' is legacy`; collision low; schema yes.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A5** 55,135 GitHub stars; 6,144 forks; 59 default-branch commits/30d; 21,944 npm downloads/week (`bmad-method`, 2026-11-01–07), checked 2026-11-09; **M4** 59 commits/30d; latest release v6.12.4 on 2026-10-14; **C3** dedicated company, project organization, or research group: BMad Code LLC; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F5** project files: `_bmad/`, `_bmad-output/`; older `.bmad-*` is legacy; **V5** net-new measurement series; **R5** low; **E5** yes; **I5** A high-adoption methodology packages analyst, product, architecture, implementation, and review agents into a durable planning workflow.  
**Sources:** [primary](https://github.com/bmad-code-org/BMAD-METHOD); [repository metadata](https://github.com/bmad-code-org/BMAD-METHOD); checked 2026-11-09.

### 6.25 Bolt.new

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** StackBlitz  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A category leader for browser-native app generation whose automatic commits are durable but not yet source-attributable.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: StackBlitz; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A category leader for browser-native app generation whose automatic commits are durable but not yet source-attributable.  
**Sources:** [primary](https://support.bolt.new/integrations/git); checked 2026-11-09.

### 6.26 Builder.io Fusion

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Builder.io  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A repo-native visual coding agent with the distinctive .builderrules contract and bot-mediated PR workflow.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** project file + SCM activity; candidate `'.builderrules'; Builder bot comments/commits need channel separation`; collision low; schema yes-partial.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Builder.io; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F5** project file + SCM activity: `.builderrules`; Builder bot comments/commits need channel separation; **V5** net-new measurement series; **R5** low; **E4** yes-partial; **I5** A repo-native visual coding agent with the distinctive .builderrules contract and bot-mediated PR workflow.  
**Sources:** [primary](https://www.builder.io/c/docs/projects-git-providers); checked 2026-11-09.

### 6.27 Claude Agent SDK

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Anthropic  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Anthropic exposes the Claude Code agent loop as Python and TypeScript SDKs, creating a reusable harness surface distinct from the CLI.  
**Adoption:** 8,491 GitHub stars; 1,401 forks; 54 default-branch commits/30d; 18,545,083 npm downloads/week (`@anthropic-ai/claude-agent-sdk`, 2026-11-01–07), checked 2026-11-09.  
**Momentum:** 54 commits/30d; latest release v0.2.179 on 2026-11-06.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 8,491 GitHub stars; 1,401 forks; 54 default-branch commits/30d; 18,545,083 npm downloads/week (`@anthropic-ai/claude-agent-sdk`, 2026-11-01–07), checked 2026-11-09; **M5** 54 commits/30d; latest release v0.2.179 on 2026-11-06; **C5** major corporate backing: Anthropic; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** Anthropic exposes the Claude Code agent loop as Python and TypeScript SDKs, creating a reusable harness surface distinct from the CLI.  
**Sources:** [primary](https://github.com/anthropics/claude-agent-sdk-python); [repository metadata](https://github.com/anthropics/claude-agent-sdk-python); checked 2026-11-09.

### 6.28 Claude Code on the web delta

**Categories:** Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** Anthropic  
**Coverage decision:** uncovered managed cloud VM surface; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Anthropic's managed VM surface turns the known local product into a background cloud agent with different provenance and execution boundaries.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Anthropic; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I5** Anthropic's managed VM surface turns the known local product into a background cloud agent with different provenance and execution boundaries.  
**Sources:** [primary](https://code.claude.com/docs/en/claude-code-on-the-web); checked 2026-11-09.

### 6.29 Claude Code Review delta

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Anthropic  
**Coverage decision:** uncovered product-family surface; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Anthropic's multi-agent review workflow is a distinct, current SCM surface not represented by Claude Code authorship/config detection.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Anthropic; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I5** Anthropic's multi-agent review workflow is a distinct, current SCM surface not represented by Claude Code authorship/config detection.  
**Sources:** [primary](https://claude.com/marketplace/plugins/code-review); checked 2026-11-09.

### 6.30 Claude Code Router

**Categories:** Rules Managers & Context Syncers, Personal AI Daemons & Local Gateways  
**Parent/backing:** Independent / musistudio  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A widely adopted local routing layer redirects Claude Code across model providers and adds reusable tool and workflow controls.  
**Adoption:** 38,055 GitHub stars; 3,200 forks; 1 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1 commits/30d; latest release v3.1.3 on 2026-10-09.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 38,055 GitHub stars; 3,200 forks; 1 default-branch commits/30d, checked 2026-11-09; **M4** 1 commits/30d; latest release v3.1.3 on 2026-10-09; **C1** independent or community backing: Independent / musistudio; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I4** A widely adopted local routing layer redirects Claude Code across model providers and adds reusable tool and workflow controls.  
**Sources:** [primary](https://github.com/musistudio/claude-code-router); [repository metadata](https://github.com/musistudio/claude-code-router); checked 2026-11-09.

### 6.31 Claude Code Templates

**Categories:** Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Independent / davila7  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A large registry and installer distributes Claude Code agents, commands, skills, hooks, MCP definitions, and settings.  
**Adoption:** 33,216 GitHub stars; 3,894 forks; 266 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 266 commits/30d; latest release v1.29.7 on 2026-10-09.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 33,216 GitHub stars; 3,894 forks; 266 default-branch commits/30d, checked 2026-11-09; **M4** 266 commits/30d; latest release v1.29.7 on 2026-10-09; **C1** independent or community backing: Independent / davila7; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I3** A large registry and installer distributes Claude Code agents, commands, skills, hooks, MCP definitions, and settings.  
**Sources:** [primary](https://github.com/davila7/claude-code-templates); [repository metadata](https://github.com/davila7/claude-code-templates); checked 2026-11-09.

### 6.32 Claude Squad

**Categories:** Agent Multiplexers & Herders  
**Parent/backing:** Smtg AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An established terminal multiplexer isolates several coding-agent sessions with tmux and Git worktrees.  
**Adoption:** 8,752 GitHub stars; 623 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release v1.0.20 on 2026-08-20.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 8,752 GitHub stars; 623 forks; 0 default-branch commits/30d, checked 2026-11-09; **M2** 0 commits/30d; latest release v1.0.20 on 2026-08-20; **C3** dedicated company, project organization, or research group: Smtg AI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** An established terminal multiplexer isolates several coding-agent sessions with tmux and Git worktrees.  
**Sources:** [primary](https://github.com/smtg-ai/claude-squad); [repository metadata](https://github.com/smtg-ai/claude-squad); checked 2026-11-09.

### 6.33 Cleric

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Cleric  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A specialist autonomous investigation platform repeatedly present in current AI SRE maps.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Cleric; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A specialist autonomous investigation platform repeatedly present in current AI SRE maps.  
**Sources:** [primary](https://cleric.ai/); checked 2026-11-09.

### 6.34 Cloudflare Agents SDK

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Cloudflare  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Cloudflare's framework binds agents to durable state, workflows, browser/code execution, and Workers deployment.  
**Adoption:** 5,973 GitHub stars; 837 forks; 125 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 125 commits/30d; latest release agents@0.33.0 on 2026-11-03.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 5,973 GitHub stars; 837 forks; 125 default-branch commits/30d, checked 2026-11-09; **M5** 125 commits/30d; latest release agents@0.33.0 on 2026-11-03; **C5** major corporate backing: Cloudflare; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** Cloudflare's framework binds agents to durable state, workflows, browser/code execution, and Workers deployment.  
**Sources:** [primary](https://github.com/cloudflare/agents); [repository metadata](https://github.com/cloudflare/agents); checked 2026-11-09.

### 6.35 cmux

**Categories:** Agentic / AI-Native Terminals, Agent Multiplexers & Herders  
**Parent/backing:** Manaflow  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing Ghostty-based terminal adds agent-aware workspaces, notifications, and automation for concurrent coding sessions.  
**Adoption:** 28,747 GitHub stars; 2,639 forks; 1,127 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,127 commits/30d; latest release cmux-app-ffi-395681a7115d92d9e851b91b86a89520d47a16e4 on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 28,747 GitHub stars; 2,639 forks; 1,127 default-branch commits/30d, checked 2026-11-09; **M5** 1,127 commits/30d; latest release cmux-app-ffi-395681a7115d92d9e851b91b86a89520d47a16e4 on 2026-11-08; **C3** dedicated company, project organization, or research group: Manaflow; **D2** candidate string appeared 2 time(s); no strong candidate-specific discussion cluster retained; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A fast-growing Ghostty-based terminal adds agent-aware workspaces, notifications, and automation for concurrent coding sessions.  
**Sources:** [primary](https://github.com/manaflow-ai/cmux); [repository metadata](https://github.com/manaflow-ai/cmux); checked 2026-11-09.

### 6.36 CodeCompanion.nvim

**Categories:** IDE Agent Extensions & Plugins  
**Parent/backing:** CodeCompanion community  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A substantial Neovim extension supports agent chat, inline changes, tools, workflows, and multiple model providers.  
**Adoption:** 6,931 GitHub stars; 473 forks; 36 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 36 commits/30d; latest release v20.1.0 on 2026-11-08.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 6,931 GitHub stars; 473 forks; 36 default-branch commits/30d, checked 2026-11-09; **M5** 36 commits/30d; latest release v20.1.0 on 2026-11-08; **C1** independent or community backing: CodeCompanion community; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** A substantial Neovim extension supports agent chat, inline changes, tools, workflows, and multiple model providers.  
**Sources:** [primary](https://github.com/olimorris/codecompanion.nvim); [repository metadata](https://github.com/olimorris/codecompanion.nvim); checked 2026-11-09.

### 6.37 CodeGPT

**Categories:** IDE Agent Extensions & Plugins  
**Parent/backing:** CodeGPT  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A long-running VS Code and JetBrains agent extension with multi-step edits, local and hosted models, and custom-agent support.  
**Adoption:** 2,557,481 installs on the official VS Code Marketplace listing for extension ID `DanielSanMedium.dscodegpt` on 2026-11-09, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 2,557,481 installs on the official VS Code Marketplace listing for extension ID `DanielSanMedium.dscodegpt` on 2026-11-09, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: CodeGPT; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A long-running VS Code and JetBrains agent extension with multi-step edits, local and hosted models, and custom-agent support.  
**Sources:** [primary](https://marketplace.visualstudio.com/items?itemName=DanielSanMedium.dscodegpt); checked 2026-11-09.

### 6.38 Coder Xum / Mux

**Categories:** Agent Multiplexers & Herders, ADEs  
**Parent/backing:** Coder  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Coder's first-party parallel-agent desktop/workspace product matters because it connects agent control planes to enterprise developer infrastructure.  
**Adoption:** 2,070 GitHub stars; 141 forks; 1,341 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,341 commits/30d; latest release v0.32.2-nightly.194 on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 2,070 GitHub stars; 141 forks; 1,341 default-branch commits/30d, checked 2026-11-09; **M5** 1,341 commits/30d; latest release v0.32.2-nightly.194 on 2026-11-08; **C5** major corporate backing: Coder; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I5** Coder's first-party parallel-agent desktop/workspace product matters because it connects agent control planes to enterprise developer infrastructure.  
**Sources:** [primary](https://github.com/coder/xum); [repository metadata](https://github.com/coder/xum); checked 2026-11-09.

### 6.39 CodeWhale

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** CodeWhale  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing Rust CLI with headless execution, snapshots, permission modes, and model fleets.  
**Adoption:** 41,159 GitHub stars; 3,565 forks; 1,770 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,770 commits/30d; latest release v0.10.2 on 2026-10-24.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 41,159 GitHub stars; 3,565 forks; 1,770 default-branch commits/30d, checked 2026-11-09; **M5** 1,770 commits/30d; latest release v0.10.2 on 2026-10-24; **C3** dedicated company, project organization, or research group: CodeWhale; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** A fast-growing Rust CLI with headless execution, snapshots, permission modes, and model fleets.  
**Sources:** [primary](https://github.com/codewhale-hq/Codewhale); [repository metadata](https://github.com/codewhale-hq/Codewhale); checked 2026-11-09.

### 6.40 Codex Code Review delta

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** OpenAI  
**Coverage decision:** uncovered product-family surface; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Codex now performs automatic and requested GitHub/GitLab reviews guided by repository AGENTS.md rules.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: OpenAI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I5** Codex now performs automatic and requested GitHub/GitLab reviews guided by repository AGENTS.md rules.  
**Sources:** [primary](https://learn.chatgpt.com/docs/third-party/github); checked 2026-11-09.

### 6.41 Context7

**Categories:** Rules Managers & Context Syncers  
**Parent/backing:** Upstash  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A heavily adopted documentation-context service and MCP integration that changes what coding agents read without identifying the executing client.  
**Adoption:** 64,373 GitHub stars; 3,226 forks; 138 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 138 commits/30d; latest release mcpb-v4.5.1 on 2026-11-06.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 64,373 GitHub stars; 3,226 forks; 138 default-branch commits/30d, checked 2026-11-09; **M5** 138 commits/30d; latest release mcpb-v4.5.1 on 2026-11-06; **C3** dedicated company, project organization, or research group: Upstash; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I3** A heavily adopted documentation-context service and MCP integration that changes what coding agents read without identifying the executing client.  
**Sources:** [primary](https://github.com/upstash/context7); [repository metadata](https://github.com/upstash/context7); checked 2026-11-09.

### 6.42 CrewAI

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** CrewAI Inc.  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** One of the largest independent multi-agent frameworks, centered on role-based crews, flows, memory, and deployable automation.  
**Adoption:** 60,654 GitHub stars; 9,108 forks; 216 default-branch commits/30d; 589,867 PyPI downloads/week (`crewai`, checked 2026-11-09), checked 2026-11-09.  
**Momentum:** 216 commits/30d; latest release 1.15.38 on 2026-11-08.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** 60,654 GitHub stars; 9,108 forks; 216 default-branch commits/30d; 589,867 PyPI downloads/week (`crewai`, checked 2026-11-09), checked 2026-11-09; **M5** 216 commits/30d; latest release 1.15.38 on 2026-11-08; **C3** dedicated company, project organization, or research group: CrewAI Inc; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I4** One of the largest independent multi-agent frameworks, centered on role-based crews, flows, memory, and deployable automation.  
**Sources:** [primary](https://github.com/crewAIInc/crewAI); [repository metadata](https://github.com/crewAIInc/crewAI); checked 2026-11-09.

### 6.43 cubic

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** cubic  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The current Code Review Bench leader combines PR review, local CLI review, custom agents, and background fixes.  
**Adoption:** #1 at 64.0 F1 on Code Review Bench's month view checked 2026-10-10, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** project file + SCM activity; candidate `'cubic.yaml'; '@cubic-dev-ai' comments are activity`; collision medium; schema yes-partial.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A5** #1 at 64.0 F1 on Code Review Bench's month view checked 2026-10-10, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: cubic; **D4** candidate string appeared 11 times in six retained 30-day research corpora; **F3** project file + SCM activity: `cubic.yaml`; `@cubic-dev-ai` comments are activity; **V5** net-new measurement series; **R3** medium; **E4** yes-partial; **I5** The current Code Review Bench leader combines PR review, local CLI review, custom agents, and background fixes.  
**Sources:** [primary](https://docs.cubic.dev/ai-review/quickstart); checked 2026-11-09.

### 6.44 Databricks Agent Bricks

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Databricks  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Databricks' developer platform combines a CLI, durable agent runtime, sandboxed code execution, memory, tools, tracing, evaluation, and Unity Catalog governance.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Databricks; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I5** Databricks' developer platform combines a CLI, durable agent runtime, sandboxed code execution, memory, tools, tracing, evaluation, and Unity Catalog governance.  
**Sources:** [primary](https://docs.databricks.com/aws/en/agents/concepts); checked 2026-11-09.

### 6.45 Databricks Genie Code

**Categories:** IDE Agent Extensions & Plugins  
**Parent/backing:** Databricks  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Databricks' autonomous workspace agent plans and runs multi-step code, pipeline, dashboard, SQL, and ML work against governed data and lineage.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** platform metadata; candidate `platform artifacts may identify the host but not necessarily agent execution`; collision medium-high; schema partial.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Databricks; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F2** platform metadata: platform artifacts may identify the host but not necessarily agent execution; **V2** strategic context; weak direct attribution; **R2** medium-high; **E3** partial; **I5** Databricks' autonomous workspace agent plans and runs multi-step code, pipeline, dashboard, SQL, and ML work against governed data and lineage.  
**Sources:** [primary](https://docs.databricks.com/aws/en/genie-code); checked 2026-11-09.

### 6.46 Datadog Bits AI: Investigation / Remediation

**Categories:** Autonomous Cloud SWE Agents / Background Droids, PR Review, Auto-Fix & Code Quality Bots, AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Datadog  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Datadog's always-on investigation agent now links telemetry-grounded root cause to governed infrastructure actions and code-fix pull requests through Bits Remediation.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Datadog; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** Datadog's always-on investigation agent now links telemetry-grounded root cause to governed infrastructure actions and code-fix pull requests through Bits Remediation.  
**Sources:** [primary](https://docs.datadoghq.com/bits_ai/bits_remediation); checked 2026-11-09.

### 6.47 Deep Agents Code

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** LangChain  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** LangChain's official terminal coding agent gives the framework vendor a deployable first-party harness and has fast adoption.  
**Adoption:** 31,108 GitHub stars; 4,387 forks; 482 default-branch commits/30d; 13,441 PyPI downloads/week (`deepagents-code`, checked 2026-11-09), checked 2026-11-09.  
**Momentum:** 482 commits/30d; latest release langchain-quickjs==0.3.12 on 2026-11-07.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 31,108 GitHub stars; 4,387 forks; 482 default-branch commits/30d; 13,441 PyPI downloads/week (`deepagents-code`, checked 2026-11-09), checked 2026-11-09; **M5** 482 commits/30d; latest release langchain-quickjs==0.3.12 on 2026-11-07; **C3** dedicated company, project organization, or research group: LangChain; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** LangChain's official terminal coding agent gives the framework vendor a deployable first-party harness and has fast adoption.  
**Sources:** [primary](https://github.com/langchain-ai/deepagents); [repository metadata](https://github.com/langchain-ai/deepagents); checked 2026-11-09.

### 6.48 Devin Desktop

**Categories:** ADEs, AI-Native IDEs (Forked Editors), IDE Agent Extensions & Plugins  
**Parent/backing:** Cognition  
**Coverage decision:** uncovered successor to Windsurf and local/cloud manager; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The Windsurf successor combines an editor with local and cloud Devin agents and materially changes the old Cascade/Windsurf lineage.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Cognition; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I4** The Windsurf successor combines an editor with local and cloud Devin agents and materially changes the old Cascade/Windsurf lineage.  
**Sources:** [primary](https://cognition.com/blog/introducing-devin-desktop); checked 2026-11-09.

### 6.49 Docker Agent (formerly cagent)

**Categories:** Agent Harnesses & SDKs, Agent CLIs / TUIs, Agent Orchestrators & Fleet Managers  
**Parent/backing:** Docker  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Docker's renamed, fast-moving agent builder and runtime ships in Docker Desktop and defines multi-agent teams, tools, models, and handoffs in portable YAML or HCL.  
**Adoption:** 4,666 GitHub stars; 554 forks; 606 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 606 commits/30d; latest release v1.157.2 on 2026-11-05.  
**Measurement posture:** declarative agent definition; candidate `agent YAML/HCL plus Docker Agent schema or product-specific keys; a generic 'agent.yaml' filename alone is unsafe`; collision medium; schema partial.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A2** 4,666 GitHub stars; 554 forks; 606 default-branch commits/30d, checked 2026-11-09; **M5** 606 commits/30d; latest release v1.157.2 on 2026-11-05; **C5** major corporate backing: Docker; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** declarative agent definition: agent YAML/HCL plus Docker Agent schema or product-specific keys; a generic `agent.yaml` filename alone is unsafe; **V5** net-new measurement series; **R3** medium; **E3** partial; **I5** Docker's renamed, fast-moving agent builder and runtime ships in Docker Desktop and defines multi-agent teams, tools, models, and handoffs in portable YAML or HCL.  
**Sources:** [primary](https://docs.docker.com/ai/docker-agent); [repository metadata](https://github.com/docker/docker-agent); checked 2026-11-09.

### 6.50 Dynatrace SRE Agent

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Dynatrace  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Dynatrace's autonomous SRE Agent investigates detected problems, records root causes and recommendations, and can hand grounded context to cloud remediation agents.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Dynatrace; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** Dynatrace's autonomous SRE Agent investigates detected problems, records root causes and recommendations, and can hand grounded context to cloud remediation agents.  
**Sources:** [primary](https://www.dynatrace.com/hub/detail/sre-agent); checked 2026-11-09.

### 6.51 Ellipsis

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Ellipsis  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An established reviewer that can push fixes, crossing the boundary between commentary and authored changes.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Ellipsis; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** An established reviewer that can push fixes, crossing the boundary between commentary and authored changes.  
**Sources:** [primary](https://www.ellipsis.dev/); checked 2026-11-09.

### 6.52 Emdash

**Categories:** Agent Multiplexers & Herders, ADEs  
**Parent/backing:** General Action  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An open agentic development environment runs provider-independent coding agents in parallel, with worktree isolation and centralized review.  
**Adoption:** 6,218 GitHub stars; 664 forks; 204 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 204 commits/30d; latest release v1.2.11 on 2026-11-06.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 6,218 GitHub stars; 664 forks; 204 default-branch commits/30d, checked 2026-11-09; **M5** 204 commits/30d; latest release v1.2.11 on 2026-11-06; **C3** dedicated company, project organization, or research group: General Action; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** An open agentic development environment runs provider-independent coding agents in parallel, with worktree isolation and centralized review.  
**Sources:** [primary](https://github.com/generalaction/emdash); [repository metadata](https://github.com/generalaction/emdash); checked 2026-11-09.

### 6.53 Emergent

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Emergent  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A prominent full-stack and mobile multi-agent builder repeatedly present in current category comparisons.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Emergent; **D3** candidate string appeared 3 times in six retained 30-day research corpora; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A prominent full-stack and mobile multi-agent builder repeatedly present in current category comparisons.  
**Sources:** [primary](https://emergent.sh/); checked 2026-11-09.

### 6.54 Figma Make

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Figma  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A major design vendor's prompt-to-interactive-prototype and code workflow is strategically important at the design/code boundary.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Figma; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** A major design vendor's prompt-to-interactive-prototype and code workflow is strategically important at the design/code boundary.  
**Sources:** [primary](https://www.figma.com/make/); checked 2026-11-09.

### 6.55 ForgeCode

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** Tailcall (formerly Antinomy)  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An active multi-model terminal agent with custom agents and large-refactor tooling.  
**Adoption:** 7,631 GitHub stars; 1,454 forks; 78 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 78 commits/30d; latest release v2.14.0 on 2026-10-01.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 7,631 GitHub stars; 1,454 forks; 78 default-branch commits/30d, checked 2026-11-09; **M4** 78 commits/30d; latest release v2.14.0 on 2026-10-01; **C3** dedicated company, project organization, or research group: Tailcall (formerly Antinomy); **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** An active multi-model terminal agent with custom agents and large-refactor tooling.  
**Sources:** [primary](https://github.com/tailcallhq/forgecode); [repository metadata](https://github.com/tailcallhq/forgecode); checked 2026-11-09.

### 6.56 Freebuff (formerly Codebuff)

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** Codebuff AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The product rebranded to Freebuff but the live repository is still CodebuffAI/codebuff; it remains a high-adoption multi-agent CLI family and needs the rename captured.  
**Adoption:** 14,047 GitHub stars; 1,507 forks; 1,807 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,807 commits/30d; latest release v1.0.420-beta.185 on 2025-10-21.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 14,047 GitHub stars; 1,507 forks; 1,807 default-branch commits/30d, checked 2026-11-09; **M5** 1,807 commits/30d; latest release v1.0.420-beta.185 on 2025-10-21; **C3** dedicated company, project organization, or research group: Codebuff AI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** The product rebranded to Freebuff but the live repository is still CodebuffAI/codebuff; it remains a high-adoption multi-agent CLI family and needs the rename captured.  
**Sources:** [primary](https://github.com/CodebuffAI/codebuff); [repository metadata](https://github.com/CodebuffAI/codebuff); checked 2026-11-09.

### 6.57 Gastown

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** Gastown Hall  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A well-adopted workspace manager coordinates multiple coding agents, Git worktrees, task state, and handoffs.  
**Adoption:** 18,739 GitHub stars; 1,695 forks; 8 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 8 commits/30d; latest release v1.2.1 on 2026-06-06.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 18,739 GitHub stars; 1,695 forks; 8 default-branch commits/30d, checked 2026-11-09; **M2** 8 commits/30d; latest release v1.2.1 on 2026-06-06; **C1** independent or community backing: Gastown Hall; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A well-adopted workspace manager coordinates multiple coding agents, Git worktrees, task state, and handoffs.  
**Sources:** [primary](https://github.com/gastownhall/gastown); [repository metadata](https://github.com/gastownhall/gastown); checked 2026-11-09.

### 6.58 Gitar

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Sonar  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A multi-forge review-and-fix agent acquired by Sonar in 2026, making it strategically important beyond its standalone adoption.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Sonar; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** A multi-forge review-and-fix agent acquired by Sonar in 2026, making it strategically important beyond its standalone adoption.  
**Sources:** [primary](https://docs.gitar.ai/features/code-review); checked 2026-11-09.

### 6.59 GitHub Agentic Workflows

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** Microsoft / GitHub  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** GitHub's open workflow system compiles Markdown-defined agents into governed Actions jobs, creating a new repository-native automation surface.  
**Adoption:** 5,595 GitHub stars; 623 forks; 1,345 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,345 commits/30d; latest release v1.2.1 on 2026-11-06.  
**Measurement posture:** workflow source; candidate `agentic workflow Markdown compiled under '.github/workflows/'; content/provenance required`; collision medium; schema no-content.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A3** 5,595 GitHub stars; 623 forks; 1,345 default-branch commits/30d, checked 2026-11-09; **M5** 1,345 commits/30d; latest release v1.2.1 on 2026-11-06; **C5** major corporate backing: Microsoft / GitHub; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** workflow source: agentic workflow Markdown compiled under `.github/workflows/`; content/provenance required; **V5** net-new measurement series; **R3** medium; **E1** no-content; **I5** GitHub's open workflow system compiles Markdown-defined agents into governed Actions jobs, creating a new repository-native automation surface.  
**Sources:** [primary](https://github.com/github/gh-aw); [repository metadata](https://github.com/github/gh-aw); checked 2026-11-09.

### 6.60 GitHub Copilot 2026 surface delta

**Categories:** Agent CLIs / TUIs, Agent Orchestrators & Fleet Managers, Agent Multiplexers & Herders, IDE Agent Extensions & Plugins, Autonomous Cloud SWE Agents / Background Droids, PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Microsoft / GitHub  
**Coverage decision:** uncovered Fusion, CLI, Agent HQ, automations, and review surfaces; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Fusion, the GA Copilot CLI, Agent HQ, automations, and review effort modes materially expand the existing Copilot family beyond current pack semantics.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** mode/control-plane; candidate `Fusion model selection and Agent HQ hosting add no distinct repository identity`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Microsoft / GitHub; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** mode/control-plane: Fusion model selection and Agent HQ hosting add no distinct repository identity; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** Fusion, the GA Copilot CLI, Agent HQ, automations, and review effort modes materially expand the existing Copilot family beyond current pack semantics.  
**Sources:** [primary](https://github.blog/changelog/2026-10-28-route-and-orchestrate-models-with-github-copilot-fusion/); checked 2026-11-09.

### 6.61 Gitingest

**Categories:** Rules Managers & Context Syncers  
**Parent/backing:** Coderamp Labs / Romain Courtois  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-adoption repository-to-prompt context tool that represents the externalized context layer around coding agents.  
**Adoption:** 16,097 GitHub stars; 1,209 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release v0.3.1 on 2025-07-31.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** 16,097 GitHub stars; 1,209 forks; 0 default-branch commits/30d, checked 2026-11-09; **M2** 0 commits/30d; latest release v0.3.1 on 2025-07-31; **C5** major corporate backing: Coderamp Labs / Romain Courtois; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I5** A high-adoption repository-to-prompt context tool that represents the externalized context layer around coding agents.  
**Sources:** [primary](https://github.com/coderamp-labs/gitingest); [repository metadata](https://github.com/coderamp-labs/gitingest); checked 2026-11-09.

### 6.62 GitLab Duo Agent Platform

**Categories:** Agent CLIs / TUIs, Agent Orchestrators & Fleet Managers, IDE Agent Extensions & Plugins, Autonomous Cloud SWE Agents / Background Droids, PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** GitLab  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** GitLab's GA platform embeds coding, review, pipeline-repair, security, custom, and external agents across the repository and delivery lifecycle, including self-managed deployments.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM activity + platform metadata; candidate `Duo service-account participation and 'duo/(fix|feature|refactor|docs)/...' branches; 'AGENTS.md' alone is generic`; collision medium; schema partial.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: GitLab; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM activity + platform metadata: Duo service-account participation and `duo/(fix|feature|refactor|docs)/...` branches; `AGENTS.md` alone is generic; **V5** net-new measurement series; **R3** medium; **E3** partial; **I5** GitLab's GA platform embeds coding, review, pipeline-repair, security, custom, and external agents across the repository and delivery lifecycle, including self-managed deployments.  
**Sources:** [primary](https://docs.gitlab.com/user/duo_agent_platform/); checked 2026-11-09.

### 6.63 Google ADK

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Google  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Google's first-party, multi-language framework covers agent composition, A2A interoperability, evaluation, and managed deployment.  
**Adoption:** 22,149 GitHub stars; 4,323 forks; 519 default-branch commits/30d; 2,565,393 PyPI downloads/week (`google-adk`, checked 2026-11-09), checked 2026-11-09.  
**Momentum:** 519 commits/30d; latest release v2.14.0 on 2026-11-07.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 22,149 GitHub stars; 4,323 forks; 519 default-branch commits/30d; 2,565,393 PyPI downloads/week (`google-adk`, checked 2026-11-09), checked 2026-11-09; **M5** 519 commits/30d; latest release v2.14.0 on 2026-11-07; **C5** major corporate backing: Google; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** Google's first-party, multi-language framework covers agent composition, A2A interoperability, evaluation, and managed deployment.  
**Sources:** [primary](https://github.com/google/adk-python); [repository metadata](https://github.com/google/adk-python); checked 2026-11-09.

### 6.64 Google Antigravity 2.0 / CLI / SDK

**Categories:** Agent CLIs / TUIs, Agent Harnesses & SDKs, ADEs, AI-Native IDEs (Forked Editors), IDE Agent Extensions & Plugins, Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** Google  
**Coverage decision:** uncovered successor and major-version surface delta; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Google made Antigravity its forward developer-agent platform, with one harness across desktop, CLI, SDK, managed agents, and cloud use.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Google; **D3** candidate string appeared 3 times in six retained 30-day research corpora; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** Google made Antigravity its forward developer-agent platform, with one harness across desktop, CLI, SDK, managed agents, and cloud use.  
**Sources:** [primary](https://developers.googleblog.com/an-important-update-transitioning-gemini-cli-to-antigravity-cli/); checked 2026-11-09.

### 6.65 Google Conductor

**Categories:** Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** Google  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Google's plugin brings a versioned specify-plan-implement workflow to Antigravity and Claude Code projects.  
**Adoption:** 3,779 GitHub stars; 302 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release conductor-v0.4.1 on 2026-03-11.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 3,779 GitHub stars; 302 forks; 0 default-branch commits/30d, checked 2026-11-09; **M2** 0 commits/30d; latest release conductor-v0.4.1 on 2026-03-11; **C5** major corporate backing: Google; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I5** Google's plugin brings a versioned specify-plan-implement workflow to Antigravity and Claude Code projects.  
**Sources:** [primary](https://github.com/gemini-cli-extensions/conductor); [repository metadata](https://github.com/gemini-cli-extensions/conductor); checked 2026-11-09.

### 6.66 Google Elephant-Goldfish Model

**Categories:** Spec-Driven Development (SDD) & Task Planners, Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Google  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Google's plugin separates planning from a fresh-context critic, making deliberate context reset a reusable design-and-review pattern.  
**Adoption:** 15,031 GitHub stars; 1,093 forks; 162 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 162 commits/30d; latest release v0.1.1 on 2026-11-06.  
**Measurement posture:** portable plugin; candidate `plugin/skill installation artifacts identify EGM content, not the host agent`; collision medium; schema no-provenance.  
**Robbes relevance:** context-only — plugin content identifies a design pattern, not the executing agent.  
**Scores:** **A3** 15,031 GitHub stars; 1,093 forks; 162 default-branch commits/30d, checked 2026-11-09; **M5** 162 commits/30d; latest release v0.1.1 on 2026-11-06; **C5** major corporate backing: Google; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** portable plugin: plugin/skill installation artifacts identify EGM content, not the host agent; **V2** strategic context; weak direct attribution; **R3** medium; **E1** no-provenance; **I5** Google's plugin separates planning from a fresh-context critic, making deliberate context reset a reusable design-and-review pattern.  
**Sources:** [primary](https://github.com/google/elephant-goldfish-model); [repository metadata](https://github.com/google/elephant-goldfish-model); checked 2026-11-09.

### 6.67 Google Skills

**Categories:** Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Google  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Google's first-party skills repository distributes product- and platform-specific procedures to compatible coding agents.  
**Adoption:** 23,710 GitHub stars; 1,978 forks; 124 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 124 commits/30d; repository pushed 2026-11-07.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 23,710 GitHub stars; 1,978 forks; 124 default-branch commits/30d, checked 2026-11-09; **M4** 124 commits/30d; repository pushed 2026-11-07; **C5** major corporate backing: Google; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I5** Google's first-party skills repository distributes product- and platform-specific procedures to compatible coding agents.  
**Sources:** [primary](https://github.com/google/skills); [repository metadata](https://github.com/google/skills); checked 2026-11-09.

### 6.68 Graphite Agent

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Graphite  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Review embedded in a material stacked-PR and merge-queue platform remains a distinct workflow signal.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Graphite; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** Review embedded in a material stacked-PR and merge-queue platform remains a distinct workflow signal.  
**Sources:** [primary](https://graphite.com/); checked 2026-11-09.

### 6.69 Greptile

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Greptile  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A leading whole-repository review agent with current benchmark visibility and product-owned configuration.  
**Adoption:** #3 at 63.2 F1 on Code Review Bench's month view checked 2026-10-10, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** project files + SCM activity; candidate `'.greptile/config.json', '.greptile/rules.md', 'greptile.json'`; collision low; schema yes-partial.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A5** #3 at 63.2 F1 on Code Review Bench's month view checked 2026-10-10, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Greptile; **D5** candidate string appeared 45 times in six retained 30-day research corpora; literal attention hint, not unique posts; **F5** project files + SCM activity: `.greptile/config.json`, `.greptile/rules.md`, `greptile.json`; **V5** net-new measurement series; **R5** low; **E4** yes-partial; **I5** A leading whole-repository review agent with current benchmark visibility and product-owned configuration.  
**Sources:** [primary](https://www.greptile.com/docs/introduction); checked 2026-11-09.

### 6.70 Grok Build

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** SpaceXAI / xAI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** First-party open coding harness with plan review, plugins, skills, parallel subagents, worktrees, ACP, and rapid release cadence.  
**Adoption:** 27,715 GitHub stars; 5,244 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; repository pushed 2026-09-29.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 27,715 GitHub stars; 5,244 forks; 0 default-branch commits/30d, checked 2026-11-09; **M2** 0 commits/30d; repository pushed 2026-09-29; **C3** dedicated company, project organization, or research group: SpaceXAI / xAI; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** First-party open coding harness with plan review, plugins, skills, parallel subagents, worktrees, ACP, and rapid release cadence.  
**Sources:** [primary](https://github.com/xai-org/grok-build); [repository metadata](https://github.com/xai-org/grok-build); checked 2026-11-09.

### 6.71 GSD Core

**Categories:** Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** Open GSD  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing spec-and-execution system turns goals into versioned plans, atomic tasks, verification gates, and resumable agent state.  
**Adoption:** 11,358 GitHub stars; 816 forks; 409 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 409 commits/30d; latest release v1.20.1 on 2026-11-05.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 11,358 GitHub stars; 816 forks; 409 default-branch commits/30d, checked 2026-11-09; **M5** 409 commits/30d; latest release v1.20.1 on 2026-11-05; **C1** independent or community backing: Open GSD; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I4** A fast-growing spec-and-execution system turns goals into versioned plans, atomic tasks, verification gates, and resumable agent state.  
**Sources:** [primary](https://github.com/open-gsd/gsd-core); [repository metadata](https://github.com/open-gsd/gsd-core); checked 2026-11-09.

### 6.72 Happy

**Categories:** Agent Multiplexers & Herders, ADEs  
**Parent/backing:** Happy / Slopus  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-momentum desktop and mobile client supervises Claude, Codex, and Grok sessions while reusing existing subscriptions.  
**Adoption:** 24,545 GitHub stars; 2,111 forks; 2,079 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 2,079 commits/30d; latest release cli-1.2.6-beta.1 on 2026-10-09.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 24,545 GitHub stars; 2,111 forks; 2,079 default-branch commits/30d, checked 2026-11-09; **M5** 2,079 commits/30d; latest release cli-1.2.6-beta.1 on 2026-10-09; **C3** dedicated company, project organization, or research group: Happy / Slopus; **D4** candidate string appeared 9 times in six retained 30-day research corpora; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A high-momentum desktop and mobile client supervises Claude, Codex, and Grok sessions while reusing existing subscriptions.  
**Sources:** [primary](https://github.com/slopus/happy); [repository metadata](https://github.com/slopus/happy); checked 2026-11-09.

### 6.73 HolmesGPT

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Robusta  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The leading open-source AI SRE investigation agent provides a rare measurable counterpoint to closed observability platforms.  
**Adoption:** 3,819 GitHub stars; 576 forks; 57 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 57 commits/30d; latest release 0.46.0 on 2026-11-04.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A2** 3,819 GitHub stars; 576 forks; 57 default-branch commits/30d, checked 2026-11-09; **M5** 57 commits/30d; latest release 0.46.0 on 2026-11-04; **C3** dedicated company, project organization, or research group: Robusta; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** The leading open-source AI SRE investigation agent provides a rare measurable counterpoint to closed observability platforms.  
**Sources:** [primary](https://github.com/HolmesGPT/holmesgpt); [repository metadata](https://github.com/HolmesGPT/holmesgpt); checked 2026-11-09.

### 6.74 Hyrax

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Hyrax  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A current detect-fix-verify PR agent focused on closing issues rather than only commenting.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Hyrax; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** A current detect-fix-verify PR agent focused on closing issues rather than only commenting.  
**Sources:** [primary](https://hyrax.dev/); checked 2026-11-09.

### 6.75 IBM Bob

**Categories:** Agent CLIs / TUIs, ADEs, AI-Native IDEs (Forked Editors), IDE Agent Extensions & Plugins  
**Parent/backing:** IBM  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** IBM's agentic SDLC platform has an unusually large enterprise deployment and coordinates planning, coding, testing, modernization, and governance.  
**Adoption:** IBM reports 80,000 internal users before public launch; vendor-reported 2026 adoption, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** IBM reports 80,000 internal users before public launch; vendor-reported 2026 adoption, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: IBM; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** IBM's agentic SDLC platform has an unusually large enterprise deployment and coordinates planning, coding, testing, modernization, and governance.  
**Sources:** [primary](https://www.ibm.com/new/announcements/shifting-from-ai-assisted-coding-to-ai-assisted-delivery-with-ibm-bob); checked 2026-11-09.

### 6.76 incident.io Investigations

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** incident.io  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A prominent incident-management vendor's investigation agent links telemetry, code changes, and incident workflow.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: incident.io; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A prominent incident-management vendor's investigation agent links telemetry, code changes, and incident workflow.  
**Sources:** [primary](https://incident.io/solution/ai-sre); checked 2026-11-09.

### 6.77 IronClaw

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** NEAR AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** NEAR AI's personal-agent operating layer emphasizes privacy, capability isolation, extensibility, and long-running local work.  
**Adoption:** 12,716 GitHub stars; 1,488 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release ironclaw-v1.4.1 on 2026-09-29.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** 12,716 GitHub stars; 1,488 forks; 0 default-branch commits/30d, checked 2026-11-09; **M4** 0 commits/30d; latest release ironclaw-v1.4.1 on 2026-09-29; **C3** dedicated company, project organization, or research group: NEAR AI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** NEAR AI's personal-agent operating layer emphasizes privacy, capability isolation, extensibility, and long-running local work.  
**Sources:** [primary](https://github.com/nearai/ironclaw); [repository metadata](https://github.com/nearai/ironclaw); checked 2026-11-09.

### 6.78 jcode

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** Solo Systems  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-momentum Rust harness optimized for many low-memory parallel sessions, native swarms, messaging, and conflict detection.  
**Adoption:** 21,623 GitHub stars; 2,516 forks; 1,594 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,594 commits/30d; latest release v1.0.0-preview.199 on 2026-11-06.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 21,623 GitHub stars; 2,516 forks; 1,594 default-branch commits/30d, checked 2026-11-09; **M5** 1,594 commits/30d; latest release v1.0.0-preview.199 on 2026-11-06; **C1** independent or community backing: Solo Systems; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** A high-momentum Rust harness optimized for many low-memory parallel sessions, native swarms, messaging, and conflict detection.  
**Sources:** [primary](https://github.com/1jehuang/jcode); [repository metadata](https://github.com/1jehuang/jcode); checked 2026-11-09.

### 6.79 JetBrains Air

**Categories:** Agent Orchestrators & Fleet Managers, ADEs, IDE Agent Extensions & Plugins, Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** JetBrains  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** JetBrains is moving from a single IDE plugin to a multi-agent system spanning IDEs, web, CLI, cloud environments, teams, and governance.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: JetBrains; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I5** JetBrains is moving from a single IDE plugin to a multi-agent system spanning IDEs, web, CLI, cloud environments, teams, and governance.  
**Sources:** [primary](https://www.jetbrains.com/air); checked 2026-11-09.

### 6.80 JetBrains Junie GA / CLI delta

**Categories:** Agent CLIs / TUIs, IDE Agent Extensions & Plugins, Autonomous Cloud SWE Agents / Background Droids, PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** JetBrains  
**Coverage decision:** uncovered GA CLI, async, and review surfaces; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Junie is now one engine across CLI, IDE, async execution, debugging, and PR review; the pack models only earlier Junie traces.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: JetBrains; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I5** Junie is now one engine across CLI, IDE, async execution, debugging, and PR review; the pack models only earlier Junie traces.  
**Sources:** [primary](https://blog.jetbrains.com/junie/2026/06/junie-coding-agent-out-of-beta); checked 2026-11-09.

### 6.81 Kody AI

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Kodus  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A top current review benchmark entrant with self-hosting and a repository configuration contract.  
**Adoption:** #2 at 63.4 F1 on Code Review Bench's month view checked 2026-10-10, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** project file + SCM activity; candidate `'kodus-config.yml'; '@kody' commands are activity`; collision medium; schema yes-partial.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A5** #2 at 63.4 F1 on Code Review Bench's month view checked 2026-10-10, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Kodus; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** project file + SCM activity: `kodus-config.yml`; `@kody` commands are activity; **V5** net-new measurement series; **R3** medium; **E4** yes-partial; **I5** A top current review benchmark entrant with self-hosting and a repository configuration contract.  
**Sources:** [primary](https://docs.kodus.io/en/how_to_use/overview); checked 2026-11-09.

### 6.82 LangGraph

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** LangChain  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The dominant stateful graph runtime for durable, inspectable agent workflows, with a large dependency footprint and active production ecosystem.  
**Adoption:** 44,661 GitHub stars; 7,694 forks; 133 default-branch commits/30d; 4,870,078 npm downloads/week (`@langchain/langgraph`, 2026-11-01–07), checked 2026-11-09.  
**Momentum:** 133 commits/30d; latest release cli==0.4.42 on 2026-11-06.  
**Measurement posture:** project file; candidate `'langgraph.json'`; collision low; schema yes.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A4** 44,661 GitHub stars; 7,694 forks; 133 default-branch commits/30d; 4,870,078 npm downloads/week (`@langchain/langgraph`, 2026-11-01–07), checked 2026-11-09; **M5** 133 commits/30d; latest release cli==0.4.42 on 2026-11-06; **C3** dedicated company, project organization, or research group: LangChain; **D2** candidate string appeared 2 time(s); no strong candidate-specific discussion cluster retained; **F5** project file: `langgraph.json`; **V5** net-new measurement series; **R5** low; **E5** yes; **I5** The dominant stateful graph runtime for durable, inspectable agent workflows, with a large dependency footprint and active production ecosystem.  
**Sources:** [primary](https://github.com/langchain-ai/langgraph); [repository metadata](https://github.com/langchain-ai/langgraph); checked 2026-11-09.

### 6.83 LiteLLM

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** LiteLLM / BerriAI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A major open gateway standardizes model access, routing, budgets, guardrails, logging, and fallback behavior across agent clients.  
**Adoption:** 62,919 GitHub stars; 13,121 forks; 2,020 default-branch commits/30d; 22,301,357 PyPI downloads/week (`litellm`, checked 2026-11-09), checked 2026-11-09.  
**Momentum:** 2,020 commits/30d; latest release v1.110.0-dev.2 on 2026-11-08.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 62,919 GitHub stars; 13,121 forks; 2,020 default-branch commits/30d; 22,301,357 PyPI downloads/week (`litellm`, checked 2026-11-09), checked 2026-11-09; **M5** 2,020 commits/30d; latest release v1.110.0-dev.2 on 2026-11-08; **C3** dedicated company, project organization, or research group: LiteLLM / BerriAI; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A major open gateway standardizes model access, routing, budgets, guardrails, logging, and fallback behavior across agent clients.  
**Sources:** [primary](https://github.com/BerriAI/litellm); [repository metadata](https://github.com/BerriAI/litellm); checked 2026-11-09.

### 6.84 LlamaIndex Workflows

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** LlamaIndex  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The event-driven agent-workflow layer in the large LlamaIndex ecosystem, relevant wherever data-centric agents need durable control flow.  
**Adoption:** 52,848 GitHub stars; 8,531 forks; 8 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 8 commits/30d; latest release v0.14.25 on 2026-09-21.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** 52,848 GitHub stars; 8,531 forks; 8 default-branch commits/30d, checked 2026-11-09; **M4** 8 commits/30d; latest release v0.14.25 on 2026-09-21; **C3** dedicated company, project organization, or research group: LlamaIndex; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I4** The event-driven agent-workflow layer in the large LlamaIndex ecosystem, relevant wherever data-centric agents need durable control flow.  
**Sources:** [primary](https://github.com/run-llama/llama_index); [repository metadata](https://github.com/run-llama/llama_index); checked 2026-11-09.

### 6.85 LobeHub

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** LobeHub  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A large multi-user agent workspace connects persistent agents to team chat, tools, knowledge, and scheduled autonomous work.  
**Adoption:** 84,423 GitHub stars; 16,148 forks; 1,393 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,393 commits/30d; latest release v0.0.0-nightly.pr22540.38538 on 2026-11-07.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 84,423 GitHub stars; 16,148 forks; 1,393 default-branch commits/30d, checked 2026-11-09; **M5** 1,393 commits/30d; latest release v0.0.0-nightly.pr22540.38538 on 2026-11-07; **C3** dedicated company, project organization, or research group: LobeHub; **D5** candidate string appeared 36 times in six retained 30-day research corpora; literal attention hint, not unique posts; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A large multi-user agent workspace connects persistent agents to team chat, tools, knowledge, and scheduled autonomous work.  
**Sources:** [primary](https://github.com/lobehub/lobehub); [repository metadata](https://github.com/lobehub/lobehub); checked 2026-11-09.

### 6.86 Lovable

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Lovable  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** One of the most-used prompt-to-full-stack platforms, with optional Git sync and exact current and legacy bot identities.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** author/bot + recovery branch; candidate `'lovable-dev[bot]', legacy 'gpt-engineer-app[bot]', 'lovable-sync*'`; collision low; schema yes.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Lovable; **D5** candidate string appeared 26 times in six retained 30-day research corpora; literal attention hint, not unique posts; **F5** author/bot + recovery branch: `lovable-dev[bot]`, legacy `gpt-engineer-app[bot]`, `lovable-sync*`; **V5** net-new measurement series; **R5** low; **E5** yes; **I5** One of the most-used prompt-to-full-stack platforms, with optional Git sync and exact current and legacy bot identities.  
**Sources:** [primary](https://docs.lovable.dev/integrations/github); checked 2026-11-09.

### 6.87 Macroscope Review

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Macroscope  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A current code-review and cloud-agent portfolio with public category comparisons and measurable SCM participation.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Macroscope; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** A current code-review and cloud-agent portfolio with public category comparisons and measurable SCM participation.  
**Sources:** [primary](https://macroscope.com/); checked 2026-11-09.

### 6.88 Mastra

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Mastra  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-momentum TypeScript framework spanning agents, workflows, memory, retrieval, evaluation, observability, and deployment.  
**Adoption:** 29,414 GitHub stars; 3,085 forks; 1,910 default-branch commits/30d; 3,157,676 npm downloads/week (`@mastra/core`, 2026-11-01–07), checked 2026-11-09.  
**Momentum:** 1,910 commits/30d; latest release @mastra/core@1.82.0 on 2026-11-04.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 29,414 GitHub stars; 3,085 forks; 1,910 default-branch commits/30d; 3,157,676 npm downloads/week (`@mastra/core`, 2026-11-01–07), checked 2026-11-09; **M5** 1,910 commits/30d; latest release @mastra/core@1.82.0 on 2026-11-04; **C3** dedicated company, project organization, or research group: Mastra; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I4** A high-momentum TypeScript framework spanning agents, workflows, memory, retrieval, evaluation, observability, and deployment.  
**Sources:** [primary](https://github.com/mastra-ai/mastra); [repository metadata](https://github.com/mastra-ai/mastra); checked 2026-11-09.

### 6.89 MausBot (OpenMausBot)

**Categories:** Agent Multiplexers & Herders, ADEs, Personal AI Daemons & Local Gateways  
**Parent/backing:** SupaMaus  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing local-first workspace that normalizes multiple agent CLIs into persistent bots, multi-agent rooms, scheduled work, memory, approvals, and desktop/mobile access.  
**Adoption:** 18,199 GitHub stars; 2,530 forks; 5,318 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 5,318 commits/30d; latest release v0.1.149 on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 18,199 GitHub stars; 2,530 forks; 5,318 default-branch commits/30d, checked 2026-11-09; **M5** 5,318 commits/30d; latest release v0.1.149 on 2026-11-08; **C3** dedicated company, project organization, or research group: SupaMaus; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A fast-growing local-first workspace that normalizes multiple agent CLIs into persistent bots, multi-agent rooms, scheduled work, memory, approvals, and desktop/mobile access.  
**Sources:** [primary](https://docs.openmausbot.com/docs/features); [repository metadata](https://github.com/milind-soni/OpenMausBot); checked 2026-11-09.

### 6.90 MCP reference servers

**Categories:** Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Agentic AI Foundation / Linux Foundation  
**Coverage decision:** net-new ecosystem tooling family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The reference tool ecosystem remains central to agent extensibility and is important context for plugin and dependency measurements.  
**Adoption:** 91,873 GitHub stars; 11,930 forks; 540 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 540 commits/30d; latest release v2.3.0 on 2026-11-04.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 91,873 GitHub stars; 11,930 forks; 540 default-branch commits/30d, checked 2026-11-09; **M5** 540 commits/30d; latest release v2.3.0 on 2026-11-04; **C4** standards-foundation or cross-vendor backing: Agentic AI Foundation / Linux Foundation; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I3** The reference tool ecosystem remains central to agent extensibility and is important context for plugin and dependency measurements.  
**Sources:** [primary](https://github.com/modelcontextprotocol/servers); [repository metadata](https://github.com/modelcontextprotocol/servers); checked 2026-11-09.

### 6.91 Meta Muse Code

**Categories:** Agent CLIs / TUIs, Agent Orchestrators & Fleet Managers, Agent Multiplexers & Herders  
**Parent/backing:** Meta  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Meta's first-party, multi-agent-by-default coding CLI reached GA in 2026 and isolates parallel workers in worktrees.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Meta; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** Meta's first-party, multi-agent-by-default coding CLI reached GA in 2026 and isolates parallel workers in worktrees.  
**Sources:** [primary](https://dev.meta.ai/products/muse-code/); checked 2026-11-09.

### 6.92 Metoro

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Metoro  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A current Kubernetes and cloud investigation agent with production-focused positioning.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Metoro; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A current Kubernetes and cloud investigation agent with production-focused positioning.  
**Sources:** [primary](https://metoro.io/); checked 2026-11-09.

### 6.93 Mezmo AURA

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Mezmo  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An open execution harness for production investigation that creates an alternative to closed AI SRE agents.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Mezmo; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** An open execution harness for production investigation that creates an alternative to closed AI SRE agents.  
**Sources:** [primary](https://www.mezmo.com/); checked 2026-11-09.

### 6.94 Microsoft .NET Agent Skills

**Categories:** Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Microsoft  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Microsoft's first-party skills encode current .NET and C# development practices for portable agent consumption.  
**Adoption:** 5,854 GitHub stars; 457 forks; 148 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 148 commits/30d; latest release skill-validator-nightly on 2026-11-08.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** 5,854 GitHub stars; 457 forks; 148 default-branch commits/30d, checked 2026-11-09; **M5** 148 commits/30d; latest release skill-validator-nightly on 2026-11-08; **C5** major corporate backing: Microsoft; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I5** Microsoft's first-party skills encode current .NET and C# development practices for portable agent consumption.  
**Sources:** [primary](https://github.com/dotnet/skills); [repository metadata](https://github.com/dotnet/skills); checked 2026-11-09.

### 6.95 Microsoft Agent Framework

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Microsoft  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Microsoft's designated successor to AutoGen and Semantic Kernel unifies agent construction and multi-agent workflows across Python and .NET.  
**Adoption:** 14,593 GitHub stars; 2,593 forks; 387 default-branch commits/30d; 44,556 PyPI downloads/week (`agent-framework`, checked 2026-11-09), checked 2026-11-09.  
**Momentum:** 387 commits/30d; latest release dotnet-1.28.0 on 2026-11-06.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 14,593 GitHub stars; 2,593 forks; 387 default-branch commits/30d; 44,556 PyPI downloads/week (`agent-framework`, checked 2026-11-09), checked 2026-11-09; **M5** 387 commits/30d; latest release dotnet-1.28.0 on 2026-11-06; **C5** major corporate backing: Microsoft; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** Microsoft's designated successor to AutoGen and Semantic Kernel unifies agent construction and multi-agent workflows across Python and .NET.  
**Sources:** [primary](https://github.com/microsoft/agent-framework); [repository metadata](https://github.com/microsoft/agent-framework); checked 2026-11-09.

### 6.96 MoAI-ADK

**Categories:** Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** Modu AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-activity single-binary harness adds spec-driven planning, quality gates, synchronization, and model routing around Claude Code.  
**Adoption:** 1,253 GitHub stars; 223 forks; 3,373 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 3,373 commits/30d; latest release v3.1.2 on 2026-08-21.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 1,253 GitHub stars; 223 forks; 3,373 default-branch commits/30d, checked 2026-11-09; **M5** 3,373 commits/30d; latest release v3.1.2 on 2026-08-21; **C3** dedicated company, project organization, or research group: Modu AI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I4** A high-activity single-binary harness adds spec-driven planning, quality gates, synchronization, and model routing around Claude Code.  
**Sources:** [primary](https://github.com/modu-ai/moai-adk); [repository metadata](https://github.com/modu-ai/moai-adk); checked 2026-11-09.

### 6.97 Multica

**Categories:** Agent Multiplexers & Herders, Agent Orchestrators & Fleet Managers  
**Parent/backing:** Multica AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-adoption self-hosted control plane coordinates people and multiple coding agents through tasks, workspaces, and review.  
**Adoption:** 55,306 GitHub stars; 7,288 forks; 464 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 464 commits/30d; latest release v0.8.1 on 2026-11-06.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** 55,306 GitHub stars; 7,288 forks; 464 default-branch commits/30d, checked 2026-11-09; **M5** 464 commits/30d; latest release v0.8.1 on 2026-11-06; **C3** dedicated company, project organization, or research group: Multica AI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A high-adoption self-hosted control plane coordinates people and multiple coding agents through tasks, workspaces, and review.  
**Sources:** [primary](https://github.com/multica-ai/multica); [repository metadata](https://github.com/multica-ai/multica); checked 2026-11-09.

### 6.98 nanobot

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** HKUDS  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing lightweight personal-agent runtime combines messaging channels, tools, memory, schedules, and local deployment.  
**Adoption:** 49,936 GitHub stars; 8,720 forks; 435 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 435 commits/30d; latest release v0.4.1 on 2026-11-06.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 49,936 GitHub stars; 8,720 forks; 435 default-branch commits/30d, checked 2026-11-09; **M5** 435 commits/30d; latest release v0.4.1 on 2026-11-06; **C3** dedicated company, project organization, or research group: HKUDS; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A fast-growing lightweight personal-agent runtime combines messaging channels, tools, memory, schedules, and local deployment.  
**Sources:** [primary](https://github.com/HKUDS/nanobot); [repository metadata](https://github.com/HKUDS/nanobot); checked 2026-11-09.

### 6.99 NanoClaw

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** NanoCo  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing container-isolated personal agent connects messaging channels to memory, schedules, skills, and Anthropic's Agent SDK.  
**Adoption:** 31,098 GitHub stars; 12,661 forks; 126 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 126 commits/30d; latest release v2026.10.1-rc.2 on 2026-10-22.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 31,098 GitHub stars; 12,661 forks; 126 default-branch commits/30d, checked 2026-11-09; **M4** 126 commits/30d; latest release v2026.10.1-rc.2 on 2026-10-22; **C3** dedicated company, project organization, or research group: NanoCo; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A fast-growing container-isolated personal agent connects messaging channels to memory, schedules, skills, and Anthropic's Agent SDK.  
**Sources:** [primary](https://github.com/nanocoai/nanoclaw); [repository metadata](https://github.com/nanocoai/nanoclaw); checked 2026-11-09.

### 6.100 NeuBird Hawkeye

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** NeuBird  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A specialist enterprise AI SRE with active discussion of governed production investigation.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: NeuBird; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A specialist enterprise AI SRE with active discussion of governed production investigation.  
**Sources:** [primary](https://neubird.ai/); checked 2026-11-09.

### 6.101 New Relic AI

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** New Relic  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A major observability portfolio with AI investigation that remains mostly SaaS-visible.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: New Relic; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** A major observability portfolio with AI investigation that remains mostly SaaS-visible.  
**Sources:** [primary](https://newrelic.com/platform/new-relic-ai); checked 2026-11-09.

### 6.102 NVIDIA OpenShell / NemoClaw

**Categories:** Agent Harnesses & SDKs, Personal AI Daemons & Local Gateways  
**Parent/backing:** NVIDIA  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** NVIDIA's first-party sandbox/runtime stack explicitly hosts OpenClaw, Hermes, and other long-running agents and has fast adoption.  
**Adoption:** 22,984 GitHub stars; 3,204 forks; 293 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 293 commits/30d; latest release ci-native-podman-e2e-2026-10-01 on 2026-10-01.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 22,984 GitHub stars; 3,204 forks; 293 default-branch commits/30d, checked 2026-11-09; **M4** 293 commits/30d; latest release ci-native-podman-e2e-2026-10-01 on 2026-10-01; **C5** major corporate backing: NVIDIA; **D4** candidate string appeared 9 times in six retained 30-day research corpora; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I5** NVIDIA's first-party sandbox/runtime stack explicitly hosts OpenClaw, Hermes, and other long-running agents and has fast adoption.  
**Sources:** [primary](https://github.com/NVIDIA/NemoClaw); [repository metadata](https://github.com/NVIDIA/NemoClaw); checked 2026-11-09.

### 6.103 Octop

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Tencent Cloud  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Tencent Cloud's self-hosted assistant supports multiple users, agents, models, tools, and messaging entry points.  
**Adoption:** 11,783 GitHub stars; 1,618 forks; 214 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 214 commits/30d; latest release v1.0.3b4 on 2026-11-06.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** 11,783 GitHub stars; 1,618 forks; 214 default-branch commits/30d, checked 2026-11-09; **M5** 214 commits/30d; latest release v1.0.3b4 on 2026-11-06; **C5** major corporate backing: Tencent Cloud; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I5** Tencent Cloud's self-hosted assistant supports multiple users, agents, models, tools, and messaging entry points.  
**Sources:** [primary](https://github.com/TencentCloud/Octop); [repository metadata](https://github.com/TencentCloud/Octop); checked 2026-11-09.

### 6.104 Oh My Codex

**Categories:** Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Independent / Yeachan-Heo  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A substantial Codex extension layer adds hooks, specialized agents, teams, status displays, and packaged workflows.  
**Adoption:** 33,742 GitHub stars; 2,548 forks; 436 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 436 commits/30d; latest release v0.22.3 on 2026-11-08.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 33,742 GitHub stars; 2,548 forks; 436 default-branch commits/30d, checked 2026-11-09; **M5** 436 commits/30d; latest release v0.22.3 on 2026-11-08; **C1** independent or community backing: Independent / Yeachan-Heo; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I3** A substantial Codex extension layer adds hooks, specialized agents, teams, status displays, and packaged workflows.  
**Sources:** [primary](https://github.com/Yeachan-Heo/oh-my-codex); [repository metadata](https://github.com/Yeachan-Heo/oh-my-codex); checked 2026-11-09.

### 6.105 Ollama

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Ollama  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The dominant local model runtime is a strategic enabling layer for coding and personal agents, although ordinary use is not agent-specific.  
**Adoption:** 186,382 GitHub stars; 18,970 forks; 125 default-branch commits/30d; 198,024,384 lifetime Docker Hub pulls and 62,171 Homebrew installs/30d, checked 2026-11-09.  
**Momentum:** 125 commits/30d; latest release v0.40.15 on 2026-11-03.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 186,382 GitHub stars; 18,970 forks; 125 default-branch commits/30d; 198,024,384 lifetime Docker Hub pulls and 62,171 Homebrew installs/30d, checked 2026-11-09; **M5** 125 commits/30d; latest release v0.40.15 on 2026-11-03; **C3** dedicated company, project organization, or research group: Ollama; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** The dominant local model runtime is a strategic enabling layer for coding and personal agents, although ordinary use is not agent-specific.  
**Sources:** [primary](https://github.com/ollama/ollama); [repository metadata](https://github.com/ollama/ollama); checked 2026-11-09.

### 6.106 Omnigent

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** Databricks / Omnigent  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-moving meta-harness provides one policy, sandbox, and collaboration layer across several interchangeable coding agents.  
**Adoption:** 11,289 GitHub stars; 1,870 forks; 1,502 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,502 commits/30d; latest release v0.21.0 on 2026-11-05.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 11,289 GitHub stars; 1,870 forks; 1,502 default-branch commits/30d, checked 2026-11-09; **M5** 1,502 commits/30d; latest release v0.21.0 on 2026-11-05; **C5** major corporate backing: Databricks / Omnigent; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I5** A fast-moving meta-harness provides one policy, sandbox, and collaboration layer across several interchangeable coding agents.  
**Sources:** [primary](https://github.com/omnigent-ai/omnigent); [repository metadata](https://github.com/omnigent-ai/omnigent); checked 2026-11-09.

### 6.107 Open Interpreter

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Open Interpreter  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A large local execution agent gives models controlled access to code, shell, files, and computer-use workflows.  
**Adoption:** 68,842 GitHub stars; 5,940 forks; 9 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 9 commits/30d; latest release rust-v0.0.59 on 2026-11-04.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 68,842 GitHub stars; 5,940 forks; 9 default-branch commits/30d, checked 2026-11-09; **M5** 9 commits/30d; latest release rust-v0.0.59 on 2026-11-04; **C3** dedicated company, project organization, or research group: Open Interpreter; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A large local execution agent gives models controlled access to code, shell, files, and computer-use workflows.  
**Sources:** [primary](https://github.com/openinterpreter/openinterpreter); [repository metadata](https://github.com/openinterpreter/openinterpreter); checked 2026-11-09.

### 6.108 Open WebUI

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Open WebUI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A very large self-hosted model interface now includes tools, pipelines, memory, and agent workflows, making it a consequential local gateway layer.  
**Adoption:** 158,136 GitHub stars; 22,989 forks; 1,388 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,388 commits/30d; latest release v0.13.2 on 2026-11-08.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 158,136 GitHub stars; 22,989 forks; 1,388 default-branch commits/30d, checked 2026-11-09; **M5** 1,388 commits/30d; latest release v0.13.2 on 2026-11-08; **C3** dedicated company, project organization, or research group: Open WebUI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A very large self-hosted model interface now includes tools, pipelines, memory, and agent workflows, making it a consequential local gateway layer.  
**Sources:** [primary](https://github.com/open-webui/open-webui); [repository metadata](https://github.com/open-webui/open-webui); checked 2026-11-09.

### 6.109 OpenAI Agents SDK

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** OpenAI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** OpenAI's first-party framework standardizes tools, handoffs, guardrails, sessions, and tracing across Python and TypeScript agents.  
**Adoption:** 30,561 GitHub stars; 5,016 forks; 78 default-branch commits/30d; 4,609,673 PyPI downloads/week (`openai-agents`, checked 2026-11-09), checked 2026-11-09.  
**Momentum:** 78 commits/30d; latest release v0.24.0-alpha.7 on 2026-11-08.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 30,561 GitHub stars; 5,016 forks; 78 default-branch commits/30d; 4,609,673 PyPI downloads/week (`openai-agents`, checked 2026-11-09), checked 2026-11-09; **M5** 78 commits/30d; latest release v0.24.0-alpha.7 on 2026-11-08; **C5** major corporate backing: OpenAI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** OpenAI's first-party framework standardizes tools, handoffs, guardrails, sessions, and tracing across Python and TypeScript agents.  
**Sources:** [primary](https://github.com/openai/openai-agents-python); [repository metadata](https://github.com/openai/openai-agents-python); checked 2026-11-09.

### 6.110 OpenAI Symphony

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** OpenAI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** OpenAI's open orchestration reference turns tracker work into isolated Codex implementation runs with reviewable outcomes.  
**Adoption:** 27,979 GitHub stars; 2,889 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release nightly on 2026-09-15.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 27,979 GitHub stars; 2,889 forks; 0 default-branch commits/30d, checked 2026-11-09; **M4** 0 commits/30d; latest release nightly on 2026-09-15; **C5** major corporate backing: OpenAI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I5** OpenAI's open orchestration reference turns tracker work into isolated Codex implementation runs with reviewable outcomes.  
**Sources:** [primary](https://github.com/openai/symphony); [repository metadata](https://github.com/openai/symphony); checked 2026-11-09.

### 6.111 OpenChamber

**Categories:** Agent Multiplexers & Herders, ADEs  
**Parent/backing:** OpenChamber  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing desktop environment wraps OpenCode sessions with project management, history, and agent-workspace controls.  
**Adoption:** 12,712 GitHub stars; 1,458 forks; 1,518 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,518 commits/30d; latest release asr-models on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 12,712 GitHub stars; 1,458 forks; 1,518 default-branch commits/30d, checked 2026-11-09; **M5** 1,518 commits/30d; latest release asr-models on 2026-11-08; **C3** dedicated company, project organization, or research group: OpenChamber; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A fast-growing desktop environment wraps OpenCode sessions with project management, history, and agent-workspace controls.  
**Sources:** [primary](https://github.com/openchamber/openchamber); [repository metadata](https://github.com/openchamber/openchamber); checked 2026-11-09.

### 6.112 OpenHuman

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** TinyHumans AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-momentum open harness focuses on running large numbers of persistent personal or task agents on modest infrastructure.  
**Adoption:** 42,594 GitHub stars; 4,212 forks; 24,200 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 24,200 commits/30d; latest release v0.64.15 on 2026-10-09.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 42,594 GitHub stars; 4,212 forks; 24,200 default-branch commits/30d, checked 2026-11-09; **M5** 24,200 commits/30d; latest release v0.64.15 on 2026-10-09; **C3** dedicated company, project organization, or research group: TinyHumans AI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A high-momentum open harness focuses on running large numbers of persistent personal or task agents on modest infrastructure.  
**Sources:** [primary](https://github.com/tinyhumansai/openhuman); [repository metadata](https://github.com/tinyhumansai/openhuman); checked 2026-11-09.

### 6.113 OpenRig

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** Independent / mvschwarz  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An active local orchestrator creates persistent teams from Claude Code, Codex, and Pi with shared context and explicit ownership.  
**Adoption:** 8,761 GitHub stars; 736 forks; 1,327 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,327 commits/30d; latest release v0.7.10 on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 8,761 GitHub stars; 736 forks; 1,327 default-branch commits/30d, checked 2026-11-09; **M5** 1,327 commits/30d; latest release v0.7.10 on 2026-11-08; **C1** independent or community backing: Independent / mvschwarz; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** An active local orchestrator creates persistent teams from Claude Code, Codex, and Pi with shared context and explicit ownership.  
**Sources:** [primary](https://github.com/mvschwarz/openrig); [repository metadata](https://github.com/mvschwarz/openrig); checked 2026-11-09.

### 6.114 OpenSpec

**Categories:** Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** Fission AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A leading open spec-driven workflow stores proposals, requirements, design, tasks, and archived changes as reviewable project artifacts.  
**Adoption:** 74,294 GitHub stars; 5,098 forks; 66 default-branch commits/30d; 1,272,036 npm downloads/week (`@fission-ai/openspec`, 2026-11-01–07), checked 2026-11-09.  
**Momentum:** 66 commits/30d; latest release v1.16.1 on 2026-11-07.  
**Measurement posture:** project files; candidate `'openspec/config.yaml', 'openspec/changes/', 'openspec/specs/'`; collision low; schema yes.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A5** 74,294 GitHub stars; 5,098 forks; 66 default-branch commits/30d; 1,272,036 npm downloads/week (`@fission-ai/openspec`, 2026-11-01–07), checked 2026-11-09; **M5** 66 commits/30d; latest release v1.16.1 on 2026-11-07; **C3** dedicated company, project organization, or research group: Fission AI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F5** project files: `openspec/config.yaml`, `openspec/changes/`, `openspec/specs/`; **V5** net-new measurement series; **R5** low; **E5** yes; **I5** A leading open spec-driven workflow stores proposals, requirements, design, tasks, and archived changes as reviewable project artifacts.  
**Sources:** [primary](https://github.com/Fission-AI/OpenSpec); [repository metadata](https://github.com/Fission-AI/OpenSpec); checked 2026-11-09.

### 6.115 OpenWorker

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Andrew Ng / open source  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Andrew Ng's open persistent-worker runtime gives agents schedules, tools, memory, and deployable long-running jobs.  
**Adoption:** 18,920 GitHub stars; 2,694 forks; 386 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 386 commits/30d; latest release skills-v0.1.0-beta.2 on 2026-11-07.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** 18,920 GitHub stars; 2,694 forks; 386 default-branch commits/30d, checked 2026-11-09; **M5** 386 commits/30d; latest release skills-v0.1.0-beta.2 on 2026-11-07; **C1** independent or community backing: Andrew Ng / open source; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** Andrew Ng's open persistent-worker runtime gives agents schedules, tools, memory, and deployable long-running jobs.  
**Sources:** [primary](https://github.com/andrewyng/openworker); [repository metadata](https://github.com/andrewyng/openworker); checked 2026-11-09.

### 6.116 Orchestrator.inc

**Categories:** Agent Multiplexers & Herders, Agent Orchestrators & Fleet Managers, ADEs  
**Parent/backing:** Orchestrator Inc.  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A cross-platform control plane takes tasks through isolated agent execution, supervision, review, and merged pull requests.  
**Adoption:** 14,281 GitHub stars; 1,947 forks; 678 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 678 commits/30d; latest release v0.14.11-nightly.202611081824 on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 14,281 GitHub stars; 1,947 forks; 678 default-branch commits/30d, checked 2026-11-09; **M5** 678 commits/30d; latest release v0.14.11-nightly.202611081824 on 2026-11-08; **C3** dedicated company, project organization, or research group: Orchestrator Inc; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A cross-platform control plane takes tasks through isolated agent execution, supervision, review, and merged pull requests.  
**Sources:** [primary](https://github.com/OrchestratorInc/agent-orchestrator); [repository metadata](https://github.com/OrchestratorInc/agent-orchestrator); checked 2026-11-09.

### 6.117 PagerDuty Paige (SRE Agent)

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** PagerDuty  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** PagerDuty's GA SRE agent combines incident context, runbooks, logs, memory, recommended playbooks, and approved remediation inside the incumbent on-call platform.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: PagerDuty; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** PagerDuty's GA SRE agent combines incident context, runbooks, logs, memory, recommended playbooks, and approved remediation inside the incumbent on-call platform.  
**Sources:** [primary](https://docs.pagerduty.com/ai-automation/advance/sre-agent); checked 2026-11-09.

### 6.118 Paradev (formerly Superset)

**Categories:** Agentic / AI-Native Terminals, Agent Multiplexers & Herders, ADEs  
**Parent/backing:** Paradev  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The renamed open desktop workspace isolates parallel coding agents in worktrees and centralizes task, terminal, and diff review.  
**Adoption:** 16,103 GitHub stars; 1,441 forks; 652 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 652 commits/30d; latest release desktop-canary on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 16,103 GitHub stars; 1,441 forks; 652 default-branch commits/30d, checked 2026-11-09; **M5** 652 commits/30d; latest release desktop-canary on 2026-11-08; **C3** dedicated company, project organization, or research group: Paradev; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** The renamed open desktop workspace isolates parallel coding agents in worktrees and centralizes task, terminal, and diff review.  
**Sources:** [primary](https://github.com/ParadevAI/Paradev); [repository metadata](https://github.com/ParadevAI/Paradev); checked 2026-11-09.

### 6.119 Paseo

**Categories:** Agent Multiplexers & Herders, ADEs  
**Parent/backing:** Paseo  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A widely adopted desktop/mobile control plane provides remote steering, notifications, and review for concurrent coding agents.  
**Adoption:** 23,532 GitHub stars; 2,886 forks; 652 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 652 commits/30d; latest release v0.15.3 on 2026-11-06.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 23,532 GitHub stars; 2,886 forks; 652 default-branch commits/30d, checked 2026-11-09; **M5** 652 commits/30d; latest release v0.15.3 on 2026-11-06; **C3** dedicated company, project organization, or research group: Paseo; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A widely adopted desktop/mobile control plane provides remote steering, notifications, and review for concurrent coding agents.  
**Sources:** [primary](https://github.com/getpaseo/paseo); [repository metadata](https://github.com/getpaseo/paseo); checked 2026-11-09.

### 6.120 PicoClaw

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Sipeed  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A compact personal-agent runtime targets low-resource devices while retaining messaging, tools, memory, and scheduled work.  
**Adoption:** 30,113 GitHub stars; 4,422 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release nightly on 2026-07-02.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 30,113 GitHub stars; 4,422 forks; 0 default-branch commits/30d, checked 2026-11-09; **M2** 0 commits/30d; latest release nightly on 2026-07-02; **C3** dedicated company, project organization, or research group: Sipeed; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A compact personal-agent runtime targets low-resource devices while retaining messaging, tools, memory, and scheduled work.  
**Sources:** [primary](https://github.com/sipeed/picoclaw); [repository metadata](https://github.com/sipeed/picoclaw); checked 2026-11-09.

### 6.121 Portkey / Prisma AIRS AI Gateway

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Palo Alto Networks (Portkey)  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The acquired enterprise gateway provides model routing, policy, observability, and guardrails under Palo Alto Networks' Prisma AIRS portfolio.  
**Adoption:** 13,345 GitHub stars; 1,375 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release v1.15.2 on 2026-01-12.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** 13,345 GitHub stars; 1,375 forks; 0 default-branch commits/30d, checked 2026-11-09; **M2** 0 commits/30d; latest release v1.15.2 on 2026-01-12; **C5** major corporate backing: Palo Alto Networks (Portkey); **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I5** The acquired enterprise gateway provides model routing, policy, observability, and guardrails under Palo Alto Networks' Prisma AIRS portfolio.  
**Sources:** [primary](https://github.com/Portkey-AI/gateway); [repository metadata](https://github.com/Portkey-AI/gateway); checked 2026-11-09.

### 6.122 Prime Agent

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** Prime Intellect  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A self-improving coding agent with durable skills, daemon sessions, schedules, and an unusual Python-kernel tool boundary.  
**Adoption:** 22,623 GitHub stars; 2,501 forks; 197 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 197 commits/30d; latest release v0.10.2 on 2026-10-28.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 22,623 GitHub stars; 2,501 forks; 197 default-branch commits/30d, checked 2026-11-09; **M4** 197 commits/30d; latest release v0.10.2 on 2026-10-28; **C3** dedicated company, project organization, or research group: Prime Intellect; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** A self-improving coding agent with durable skills, daemon sessions, schedules, and an unusual Python-kernel tool boundary.  
**Sources:** [primary](https://github.com/PrimeIntellect-ai/prime-agent); [repository metadata](https://github.com/PrimeIntellect-ai/prime-agent); checked 2026-11-09.

### 6.123 Pydantic AI

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Pydantic  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A rapidly adopted typed Python framework that applies Pydantic validation, model portability, durable graphs, and evaluation to agent systems.  
**Adoption:** 21,090 GitHub stars; 3,135 forks; 1,295 default-branch commits/30d; 1,632,581 PyPI downloads/week (`pydantic-ai`, checked 2026-11-09), checked 2026-11-09.  
**Momentum:** 1,295 commits/30d; latest release clai2-bleeding on 2026-10-06.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 21,090 GitHub stars; 3,135 forks; 1,295 default-branch commits/30d; 1,632,581 PyPI downloads/week (`pydantic-ai`, checked 2026-11-09), checked 2026-11-09; **M5** 1,295 commits/30d; latest release clai2-bleeding on 2026-10-06; **C3** dedicated company, project organization, or research group: Pydantic; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I4** A rapidly adopted typed Python framework that applies Pydantic validation, model portability, durable graphs, and evaluation to agent systems.  
**Sources:** [primary](https://github.com/pydantic/pydantic-ai); [repository metadata](https://github.com/pydantic/pydantic-ai); checked 2026-11-09.

### 6.124 Qoder 1.0 portfolio delta

**Categories:** Agent CLIs / TUIs, Agent Orchestrators & Fleet Managers, Agent Multiplexers & Herders, ADEs, AI-Native IDEs (Forked Editors), IDE Agent Extensions & Plugins, Autonomous Cloud SWE Agents / Background Droids, Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Alibaba  
**Coverage decision:** uncovered rename, 1.0 desktop, CLI, and cloud-agent portfolio; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Alibaba; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I5** Alibaba evolved Lingma into a global agentic development portfolio spanning IDE, CLI, Quest, cloud agents, security, and an autonomous desktop.  
**Sources:** [primary](https://www.alibabacloud.com/blog/introducing-qoder-1-0-from-ai-ide-to-autonomous-development-desktop_603260); checked 2026-11-09.

### 6.125 QwenPaw

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** Alibaba / AgentScope  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Alibaba's fast-growing self-hosted personal-agent surface connects AgentScope-based agents to several messaging platforms.  
**Adoption:** 37,498 GitHub stars; 3,264 forks; 173 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 173 commits/30d; latest release v2.3.0-beta.2 on 2026-11-02.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 37,498 GitHub stars; 3,264 forks; 173 default-branch commits/30d, checked 2026-11-09; **M5** 173 commits/30d; latest release v2.3.0-beta.2 on 2026-11-02; **C5** major corporate backing: Alibaba / AgentScope; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I5** Alibaba's fast-growing self-hosted personal-agent surface connects AgentScope-based agents to several messaging platforms.  
**Sources:** [primary](https://github.com/agentscope-ai/QwenPaw); [repository metadata](https://github.com/agentscope-ai/QwenPaw); checked 2026-11-09.

### 6.126 Reasonix

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** ESEngine  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing single-binary coding agent with terminal, desktop, browser, ACP, plan mode, and long unattended runs.  
**Adoption:** 36,136 GitHub stars; 2,507 forks; 4,404 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 4,404 commits/30d; latest release v2.58.0 on 2026-11-07.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 36,136 GitHub stars; 2,507 forks; 4,404 default-branch commits/30d, checked 2026-11-09; **M5** 4,404 commits/30d; latest release v2.58.0 on 2026-11-07; **C3** dedicated company, project organization, or research group: ESEngine; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** A fast-growing single-binary coding agent with terminal, desktop, browser, ACP, plan mode, and long unattended runs.  
**Sources:** [primary](https://github.com/esengine/DeepSeek-Reasonix); [repository metadata](https://github.com/esengine/DeepSeek-Reasonix); checked 2026-11-09.

### 6.127 Replit Agent

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Replit  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A major end-to-end builder inside a mature cloud IDE and deployment platform.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Replit; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** A major end-to-end builder inside a mature cloud IDE and deployment platform.  
**Sources:** [primary](https://docs.replit.com/features/agent/overview); checked 2026-11-09.

### 6.128 Repomix

**Categories:** Rules Managers & Context Syncers  
**Parent/backing:** Independent / yamadashy  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A widely used repository-to-context packager whose generated artifacts and integrations are relevant to measuring agent context workflows.  
**Adoption:** 29,190 GitHub stars; 1,632 forks; 266 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 266 commits/30d; latest release v1.19.0 on 2026-11-08.  
**Measurement posture:** portable shared content; candidate `identifies a format/package, not the executing client without provenance`; collision high; schema no-provenance.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 29,190 GitHub stars; 1,632 forks; 266 default-branch commits/30d, checked 2026-11-09; **M5** 266 commits/30d; latest release v1.19.0 on 2026-11-08; **C1** independent or community backing: Independent / yamadashy; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** portable shared content: identifies a format/package, not the executing client without provenance; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-provenance; **I3** A widely used repository-to-context packager whose generated artifacts and integrations are relevant to measuring agent context workflows.  
**Sources:** [primary](https://github.com/yamadashy/repomix); [repository metadata](https://github.com/yamadashy/repomix); checked 2026-11-09.

### 6.129 Resolve AI

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Resolve AI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A well-funded AI production engineer with graduated remediation autonomy and substantial market attention.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Resolve AI; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A well-funded AI production engineer with graduated remediation autonomy and substantial market attention.  
**Sources:** [primary](https://resolve.ai/); checked 2026-11-09.

### 6.130 Rootly AI SRE

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Rootly  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A current incident platform with agent investigation, MCP integration, and remediation workflow.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Rootly; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A current incident platform with agent investigation, MCP integration, and remediation workflow.  
**Sources:** [primary](https://rootly.com/ai-sre); checked 2026-11-09.

### 6.131 Ruflo

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** Ruvnet  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A large open orchestration project adds swarms, memory, routing, and governance around several coding-agent harnesses.  
**Adoption:** 81,271 GitHub stars; 9,555 forks; 1,206 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,206 commits/30d; latest release v3.72.2 on 2026-11-06.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** 81,271 GitHub stars; 9,555 forks; 1,206 default-branch commits/30d, checked 2026-11-09; **M5** 1,206 commits/30d; latest release v3.72.2 on 2026-11-06; **C1** independent or community backing: Ruvnet; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A large open orchestration project adds swarms, memory, routing, and governance around several coding-agent harnesses.  
**Sources:** [primary](https://github.com/ruvnet/ruflo); [repository metadata](https://github.com/ruvnet/ruflo); checked 2026-11-09.

### 6.132 Ruler

**Categories:** Rules Managers & Context Syncers  
**Parent/backing:** Intellectronica  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** The leading cross-agent rules manager compiles one source of project instructions, MCP settings, and skills into many client-specific formats.  
**Adoption:** 2,964 GitHub stars; 166 forks; 23 default-branch commits/30d; 100,426 npm downloads/week (`@intellectronica/ruler`, 2026-11-01–07), checked 2026-11-09.  
**Momentum:** 23 commits/30d; latest release v0.3.46 on 2026-10-22.  
**Measurement posture:** project files; candidate `'ruler.toml' and '.ruler/'`; collision low; schema yes.  
**Robbes relevance:** direct — product-specific artifact or SCM identity is detectable in repositories.  
**Scores:** **A2** 2,964 GitHub stars; 166 forks; 23 default-branch commits/30d; 100,426 npm downloads/week (`@intellectronica/ruler`, 2026-11-01–07), checked 2026-11-09; **M4** 23 commits/30d; latest release v0.3.46 on 2026-10-22; **C3** dedicated company, project organization, or research group: Intellectronica; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F5** project files: `ruler.toml` and `.ruler/`; **V5** net-new measurement series; **R5** low; **E5** yes; **I5** The leading cross-agent rules manager compiles one source of project instructions, MCP settings, and skills into many client-specific formats.  
**Sources:** [primary](https://github.com/intellectronica/ruler); [repository metadata](https://github.com/intellectronica/ruler); checked 2026-11-09.

### 6.133 Salesforce Agentforce Vibes

**Categories:** ADEs, IDE Agent Extensions & Plugins, Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Salesforce  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Salesforce ships a VS Code extension and browser IDE that coordinate isolated subagents to build apps, metadata, tests, and Agentforce agents.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** platform metadata; candidate `platform artifacts may identify the host but not necessarily agent execution`; collision medium-high; schema partial.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Salesforce; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F2** platform metadata: platform artifacts may identify the host but not necessarily agent execution; **V2** strategic context; weak direct attribution; **R2** medium-high; **E3** partial; **I5** Salesforce ships a VS Code extension and browser IDE that coordinate isolated subagents to build apps, metadata, tests, and Agentforce agents.  
**Sources:** [primary](https://www.salesforce.com/agentforce/developers/vibe-coding/); checked 2026-11-09.

### 6.134 SAP Joule Studio

**Categories:** Agent Harnesses & SDKs, Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** SAP  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** SAP's intent-based environment builds agents, apps, and workflows through browser and pro-code CLI flows over a managed runtime.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** platform metadata; candidate `platform artifacts may identify the host but not necessarily agent execution`; collision medium-high; schema partial.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: SAP; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F2** platform metadata: platform artifacts may identify the host but not necessarily agent execution; **V2** strategic context; weak direct attribution; **R2** medium-high; **E3** partial; **I5** SAP's intent-based environment builds agents, apps, and workflows through browser and pro-code CLI flows over a managed runtime.  
**Sources:** [primary](https://architecture.learning.sap.com/docs/ref-arch/219c07); checked 2026-11-09.

### 6.135 Scion

**Categories:** Agent Orchestrators & Fleet Managers  
**Parent/backing:** Google Cloud  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Google Cloud's open multi-agent orchestrator uses isolated worktrees, role assignment, and coordinated task execution for software work.  
**Adoption:** 2,105 GitHub stars; 308 forks; 1,631 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 1,631 commits/30d; latest release nightly-20261108 on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 2,105 GitHub stars; 308 forks; 1,631 default-branch commits/30d, checked 2026-11-09; **M5** 1,631 commits/30d; latest release nightly-20261108 on 2026-11-08; **C5** major corporate backing: Google Cloud; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I5** Google Cloud's open multi-agent orchestrator uses isolated worktrees, role assignment, and coordinated task execution for software work.  
**Sources:** [primary](https://github.com/GoogleCloudPlatform/scion); [repository metadata](https://github.com/GoogleCloudPlatform/scion); checked 2026-11-09.

### 6.136 Semgrep Multimodal / Autofix

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Semgrep  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Semgrep's renamed AI layer combines contextual detection, triage, remediation guidance, and draft fix pull requests across code and dependency findings.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Semgrep; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I4** Semgrep's renamed AI layer combines contextual detection, triage, remediation guidance, and draft fix pull requests across code and dependency findings.  
**Sources:** [primary](https://docs.semgrep.dev/semgrep-multimodal/overview); checked 2026-11-09.

### 6.137 ServiceNow Build Agent

**Categories:** ADEs, IDE Agent Extensions & Plugins, Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** ServiceNow  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** ServiceNow's autonomous developer builds and tests governed full-stack platform applications and can itself create agents and skills.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** platform metadata; candidate `platform artifacts may identify the host but not necessarily agent execution`; collision medium-high; schema partial.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: ServiceNow; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F2** platform metadata: platform artifacts may identify the host but not necessarily agent execution; **V2** strategic context; weak direct attribution; **R2** medium-high; **E3** partial; **I5** ServiceNow's autonomous developer builds and tests governed full-stack platform applications and can itself create agents and skills.  
**Sources:** [primary](https://www.servicenow.com/docs/r/application-development/build-agent.html); checked 2026-11-09.

### 6.138 ServiceNow ITOM Prime / AIOps AI Specialist

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** ServiceNow  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** ITOM Prime adds agentic alert triage, impact analysis, root-cause investigation, and an AIOps AI Specialist inside ServiceNow's governed operations platform.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: ServiceNow; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** ITOM Prime adds agentic alert triage, impact analysis, root-cause investigation, and an AIOps AI Specialist inside ServiceNow's governed operations platform.  
**Sources:** [primary](https://www.servicenow.com/docs/r/store-release-notes/store-rn-itom-prime.html); checked 2026-11-09.

### 6.139 Sinatra

**Categories:** Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** Sinatra  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A current background coding agent with issue-to-PR positioning and active category comparison presence.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Sinatra; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A current background coding agent with issue-to-PR positioning and active category comparison presence.  
**Sources:** [primary](https://www.sinatra.dev/); checked 2026-11-09.

### 6.140 smolagents

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Hugging Face  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Hugging Face's compact code-agent library is a consequential reference implementation for tool use and open-model agent workflows.  
**Adoption:** 30,267 GitHub stars; 3,199 forks; 0 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 0 commits/30d; latest release v1.26.0 on 2026-05-29.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 30,267 GitHub stars; 3,199 forks; 0 default-branch commits/30d, checked 2026-11-09; **M2** 0 commits/30d; latest release v1.26.0 on 2026-05-29; **C5** major corporate backing: Hugging Face; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** Hugging Face's compact code-agent library is a consequential reference implementation for tool use and open-model agent workflows.  
**Sources:** [primary](https://github.com/huggingface/smolagents); [repository metadata](https://github.com/huggingface/smolagents); checked 2026-11-09.

### 6.141 Snowflake Cortex Code (CoCo)

**Categories:** Agent CLIs / TUIs, ADEs, IDE Agent Extensions & Plugins, Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** Snowflake  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Snowflake reports broad adoption for a data-native coding agent spanning CLI, desktop, Snowsight, cloud agents, and agent teams.  
**Adoption:** Snowflake reported 150,000+ users in its April 2026 product briefing, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** Snowflake reported 150,000+ users in its April 2026 product briefing, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Snowflake; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** Snowflake reports broad adoption for a data-native coding agent spanning CLI, desktop, Snowsight, cloud agents, and agent teams.  
**Sources:** [primary](https://www.snowflake.com/en/product/snowflake-coco/); checked 2026-11-09.

### 6.142 Snyk Agent Fix

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Snyk  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A major security vendor's agentic fix path produces a distinct security-to-code workflow.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Snyk; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** A major security vendor's agentic fix path produces a distinct security-to-code workflow.  
**Sources:** [primary](https://snyk.io/platform/deepcode-ai/); checked 2026-11-09.

### 6.143 SonarQube AI CodeFix

**Categories:** PR Review, Auto-Fix & Code Quality Bots  
**Parent/backing:** Sonar  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A major code-quality vendor's agentic remediation path, now strategically linked to Gitar.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** SCM bot/config activity; candidate `exact app identity and canonical config need separation from comments/reviews`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Sonar; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** SCM bot/config activity: exact app identity and canonical config need separation from comments/reviews; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** A major code-quality vendor's agentic remediation path, now strategically linked to Gitar.  
**Sources:** [primary](https://www.sonarsource.com/solutions/ai/); checked 2026-11-09.

### 6.144 Spec Kitty

**Categories:** Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** Spec Kitty  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A Git-native SDD system combines specifications, governed missions, worktrees, and verification across different agent harnesses.  
**Adoption:** 1,717 GitHub stars; 194 forks; 4,878 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 4,878 commits/30d; latest release v4.0.0rc7 on 2026-10-15.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 1,717 GitHub stars; 194 forks; 4,878 default-branch commits/30d, checked 2026-11-09; **M5** 4,878 commits/30d; latest release v4.0.0rc7 on 2026-10-15; **C3** dedicated company, project organization, or research group: Spec Kitty; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I4** A Git-native SDD system combines specifications, governed missions, worktrees, and verification across different agent harnesses.  
**Sources:** [primary](https://github.com/spec-kitty/spec-kitty); [repository metadata](https://github.com/spec-kitty/spec-kitty); checked 2026-11-09.

### 6.145 Splunk AI SRE

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Cisco / Splunk  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Splunk's GA AI SRE spans alert grouping, telemetry-grounded root-cause investigation, impact analysis, and guided remediation inside Observability Cloud.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Cisco / Splunk; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** Splunk's GA AI SRE spans alert grouping, telemetry-grounded root-cause investigation, impact analysis, and guided remediation inside Observability Cloud.  
**Sources:** [primary](https://help.splunk.com/en/splunk-observability-cloud/release-notes/june-2026); checked 2026-11-09.

### 6.146 Strands Harness / Agents SDK

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Amazon Web Services  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** AWS's consolidated monorepo spans low-level Python and TypeScript SDKs, opinionated harness packages, a CLI, tools, and production guidance.  
**Adoption:** 9,081 GitHub stars; 1,485 forks; 334 default-branch commits/30d; 8,898,970 PyPI downloads/week (`strands-agents`, checked 2026-11-09), checked 2026-11-09.  
**Momentum:** 334 commits/30d; latest release typescript/v1.24.0 on 2026-11-04.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 9,081 GitHub stars; 1,485 forks; 334 default-branch commits/30d; 8,898,970 PyPI downloads/week (`strands-agents`, checked 2026-11-09), checked 2026-11-09; **M5** 334 commits/30d; latest release typescript/v1.24.0 on 2026-11-04; **C5** major corporate backing: Amazon Web Services; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** AWS's consolidated monorepo spans low-level Python and TypeScript SDKs, opinionated harness packages, a CLI, tools, and production guidance.  
**Sources:** [primary](https://github.com/strands-agents/harness-sdk); [repository metadata](https://github.com/strands-agents/harness-sdk); checked 2026-11-09.

### 6.147 Struct

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Struct  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An AI incident agent emphasizing bounded remediation and cross-telemetry investigation.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Struct; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** An AI incident agent emphasizing bounded remediation and cross-telemetry investigation.  
**Sources:** [primary](https://struct.ai/); checked 2026-11-09.

### 6.148 Superpowers

**Categories:** Spec-Driven Development (SDD) & Task Planners, Agent Plugin / Dotfile Frameworks  
**Parent/backing:** Independent / obra  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A very large portable skills framework applies planning, test-driven development, debugging, verification, and fresh-context review across agents.  
**Adoption:** 314,584 GitHub stars; 27,994 forks; 4 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 4 commits/30d; latest release v7.0.2 on 2026-11-03.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** 314,584 GitHub stars; 27,994 forks; 4 default-branch commits/30d, checked 2026-11-09; **M5** 4 commits/30d; latest release v7.0.2 on 2026-11-03; **C1** independent or community backing: Independent / obra; **D2** candidate string appeared 1 time(s); no strong candidate-specific discussion cluster retained; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I4** A very large portable skills framework applies planning, test-driven development, debugging, verification, and fresh-context review across agents.  
**Sources:** [primary](https://github.com/obra/superpowers); [repository metadata](https://github.com/obra/superpowers); checked 2026-11-09.

### 6.149 T3 Code

**Categories:** Agent Multiplexers & Herders, ADEs  
**Parent/backing:** Ping Labs  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A fast-growing desktop environment runs parallel coding agents in isolated worktrees and presents their progress and diffs for review.  
**Adoption:** 52,454 GitHub stars; 10,008 forks; 4,624 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 4,624 commits/30d; latest release v0.1.8-nightly.20261108.4380 on 2026-11-08.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A5** 52,454 GitHub stars; 10,008 forks; 4,624 default-branch commits/30d, checked 2026-11-09; **M5** 4,624 commits/30d; latest release v0.1.8-nightly.20261108.4380 on 2026-11-08; **C3** dedicated company, project organization, or research group: Ping Labs; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A fast-growing desktop environment runs parallel coding agents in isolated worktrees and presents their progress and diffs for review.  
**Sources:** [primary](https://github.com/pingdotgg/t3code); [repository metadata](https://github.com/pingdotgg/t3code); checked 2026-11-09.

### 6.150 Tabnine

**Categories:** IDE Agent Extensions & Plugins  
**Parent/backing:** Tricentis (acquired Tabnine)  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A large enterprise IDE-agent install base and private deployment model remain strategically important as Tricentis integrates Tabnine's context engine into its agentic quality platform.  
**Adoption:** 9.7 million VS Code installs surfaced by AgentGid on 2026-11-02, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A5** 9.7 million VS Code installs surfaced by AgentGid on 2026-11-02, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Tricentis (acquired Tabnine); **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** A large enterprise IDE-agent install base and private deployment model remain strategically important as Tricentis integrates Tabnine's context engine into its agentic quality platform.  
**Sources:** [primary](https://www.tricentis.com/news/tricentis-acquires-tabnine); checked 2026-11-09.

### 6.151 Tau

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** Hugging Face  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Hugging Face's small, readable provider-neutral coding agent is both a practical CLI and a reference harness.  
**Adoption:** 3,032 GitHub stars; 397 forks; 11 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 11 commits/30d; latest release v0.4.9 on 2026-11-03.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A2** 3,032 GitHub stars; 397 forks; 11 default-branch commits/30d, checked 2026-11-09; **M5** 11 commits/30d; latest release v0.4.9 on 2026-11-03; **C5** major corporate backing: Hugging Face; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** Hugging Face's small, readable provider-neutral coding agent is both a practical CLI and a reference harness.  
**Sources:** [primary](https://github.com/huggingface/tau); [repository metadata](https://github.com/huggingface/tau); checked 2026-11-09.

### 6.152 Tembo

**Categories:** Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** Tembo  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A multi-agent cloud execution platform that runs several coding-agent families in controlled workspaces.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Tembo; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A multi-agent cloud execution platform that runs several coding-agent families in controlled workspaces.  
**Sources:** [primary](https://www.tembo.io/); checked 2026-11-09.

### 6.153 TRAE 2026 platform delta

**Categories:** Agent CLIs / TUIs, Agent Orchestrators & Fleet Managers, ADEs, AI-Native IDEs (Forked Editors), IDE Agent Extensions & Plugins, Autonomous Cloud SWE Agents / Background Droids, Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** ByteDance  
**Coverage decision:** uncovered unified Agent mode, Work, cloud, automation, and CLI 2.0 surfaces; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: ByteDance; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I5** TRAE merged TraeCode and TraeWork into one Agent/IDE platform with multi-project orchestration, automation, skills, cloud execution, and a separate enterprise CLI 2.0 surface.  
**Sources:** [primary](https://docs.trae.ai/ide/traework-to-traecode-data-migration); checked 2026-11-09.

### 6.154 Traversal

**Categories:** AIOps & Incident Auto-Remediation Agents  
**Parent/backing:** Traversal  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A funded AI SRE specialist repeatedly included in current enterprise buyer maps.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** telemetry/platform activity; candidate `investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Traversal; **D3** candidate string appeared 7 times in six retained 30-day research corpora; **F1** telemetry/platform activity: investigation and remediation usually remain outside Git; delegated fixes inherit the coding agent; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I3** A funded AI SRE specialist repeatedly included in current enterprise buyer maps.  
**Sources:** [primary](https://www.traversal.com/); checked 2026-11-09.

### 6.155 tuios

**Categories:** Agentic / AI-Native Terminals, Agent Multiplexers & Herders  
**Parent/backing:** Independent / Gaurav Gosain  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** An active terminal window manager adds durable workspaces, agent-status detection, and a unified inbox for concurrent coding sessions.  
**Adoption:** 6,450 GitHub stars; 316 forks; 2,598 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 2,598 commits/30d; latest release v0.12.1 on 2026-10-31.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 6,450 GitHub stars; 316 forks; 2,598 default-branch commits/30d, checked 2026-11-09; **M5** 2,598 commits/30d; latest release v0.12.1 on 2026-10-31; **C1** independent or community backing: Independent / Gaurav Gosain; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** An active terminal window manager adds durable workspaces, agent-status detection, and a unified inbox for concurrent coding sessions.  
**Sources:** [primary](https://github.com/Gaurav-Gosain/tuios); [repository metadata](https://github.com/Gaurav-Gosain/tuios); checked 2026-11-09.

### 6.156 v0

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Vercel  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Vercel's UI-first generator has evolved toward full-stack apps and an API while remaining a strategically distinct surface from AI SDK.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** hosted control plane; candidate `Git sync may be user-controlled and no fixed identity is assumed`; collision high; schema no.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A3** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C5** major corporate backing: Vercel; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** hosted control plane: Git sync may be user-controlled and no fixed identity is assumed; **V2** strategic context; weak direct attribution; **R1** high; **E1** no; **I5** Vercel's UI-first generator has evolved toward full-stack apps and an API while remaining a strategically distinct surface from AI SDK.  
**Sources:** [primary](https://v0.app/docs); checked 2026-11-09.

### 6.157 Vercel AI SDK

**Categories:** Agent Harnesses & SDKs  
**Parent/backing:** Vercel  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A widely used TypeScript toolkit whose agent, tool-calling, streaming, and provider abstractions extend a major web-development ecosystem.  
**Adoption:** 27,816 GitHub stars; 5,557 forks; 542 default-branch commits/30d; 45,312,935 npm downloads/week (`ai`, 2026-11-01–07), checked 2026-11-09.  
**Momentum:** 542 commits/30d; latest release @ai-sdk/zai@3.0.49 on 2026-11-07.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 27,816 GitHub stars; 5,557 forks; 542 default-branch commits/30d; 45,312,935 npm downloads/week (`ai`, 2026-11-01–07), checked 2026-11-09; **M5** 542 commits/30d; latest release @ai-sdk/zai@3.0.49 on 2026-11-07; **C5** major corporate backing: Vercel; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** A widely used TypeScript toolkit whose agent, tool-calling, streaming, and provider abstractions extend a major web-development ecosystem.  
**Sources:** [primary](https://github.com/vercel/ai); [repository metadata](https://github.com/vercel/ai); checked 2026-11-09.

### 6.158 Vibe Kanban

**Categories:** Agent Multiplexers & Herders, ADEs, Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** BloopAI  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-adoption task and worktree layer dispatches multiple coding agents and exposes their plans, status, and diffs for review.  
**Adoption:** 28,622 GitHub stars; 3,056 forks; 4 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 4 commits/30d; latest release v0.1.44-20260424091429 on 2026-04-24.  
**Measurement posture:** orchestration metadata; candidate `native workspace/session config may be useful; downstream agent commits must stay downstream`; collision high; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A4** 28,622 GitHub stars; 3,056 forks; 4 default-branch commits/30d, checked 2026-11-09; **M2** 4 commits/30d; latest release v0.1.44-20260424091429 on 2026-04-24; **C3** dedicated company, project organization, or research group: BloopAI; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** orchestration metadata: native workspace/session config may be useful; downstream agent commits must stay downstream; **V4** important but needs source/schema work; **R1** high; **E3** partial; **I4** A high-adoption task and worktree layer dispatches multiple coding agents and exposes their plans, status, and diffs for review.  
**Sources:** [primary](https://github.com/BloopAI/vibe-kanban); [repository metadata](https://github.com/BloopAI/vibe-kanban); checked 2026-11-09.

### 6.159 VibeSDK

**Categories:** Full-Stack Scaffolding / App-Gen Agents  
**Parent/backing:** Cloudflare  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Cloudflare's open reference implementation makes the full app-builder stack itself measurable and reproducible.  
**Adoption:** 5,462 GitHub stars; 1,282 forks; 5 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 5 commits/30d; latest release v1.5.0 on 2026-02-06.  
**Measurement posture:** dependency/manifest content; candidate `package or import literal; no unique path assumed`; collision medium; schema no-content.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 5,462 GitHub stars; 1,282 forks; 5 default-branch commits/30d, checked 2026-11-09; **M2** 5 commits/30d; latest release v1.5.0 on 2026-02-06; **C5** major corporate backing: Cloudflare; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** dependency/manifest content: package or import literal; no unique path assumed; **V4** important but needs source/schema work; **R3** medium; **E1** no-content; **I5** Cloudflare's open reference implementation makes the full app-builder stack itself measurable and reproducible.  
**Sources:** [primary](https://github.com/cloudflare/vibesdk); [repository metadata](https://github.com/cloudflare/vibesdk); checked 2026-11-09.

### 6.160 Warp Oz / Factories delta

**Categories:** Agent Multiplexers & Herders, Agent Orchestrators & Fleet Managers, ADEs, Autonomous Cloud SWE Agents / Background Droids  
**Parent/backing:** Warp  
**Coverage decision:** uncovered Oz cloud orchestration and Factories surfaces; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Warp's current cloud orchestrator and software-lifecycle factories are not represented by the pack's terminal-native Warp signals.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** new family surface; candidate `existing family traces do not identify this specific mode/surface`; collision high; schema no.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Warp; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** new family surface: existing family traces do not identify this specific mode/surface; **V4** important but needs source/schema work; **R1** high; **E1** no; **I4** Warp's current cloud orchestrator and software-lifecycle factories are not represented by the pack's terminal-native Warp signals.  
**Sources:** [primary](https://www.warp.dev/); checked 2026-11-09.

### 6.161 Xiaomi MiMo Code

**Categories:** Agent CLIs / TUIs  
**Parent/backing:** Xiaomi  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** Xiaomi's official multi-provider coding CLI is a material new corporate entrant with active distribution and worktree support.  
**Adoption:** 13,768 GitHub stars; 1,475 forks; 98 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 98 commits/30d; latest release v0.1.16 on 2026-10-26.  
**Measurement posture:** native client state; candidate `product-owned project config, hooks, sessions, or attribution require a source audit`; collision medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A3** 13,768 GitHub stars; 1,475 forks; 98 default-branch commits/30d, checked 2026-11-09; **M4** 98 commits/30d; latest release v0.1.16 on 2026-10-26; **C5** major corporate backing: Xiaomi; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F3** native client state: product-owned project config, hooks, sessions, or attribution require a source audit; **V4** important but needs source/schema work; **R3** medium; **E3** partial; **I5** Xiaomi's official multi-provider coding CLI is a material new corporate entrant with active distribution and worktree support.  
**Sources:** [primary](https://github.com/XiaomiMiMo/MiMo-Code); [repository metadata](https://github.com/XiaomiMiMo/MiMo-Code); checked 2026-11-09.

### 6.162 Zenflow

**Categories:** Spec-Driven Development (SDD) & Task Planners  
**Parent/backing:** Zenflow  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A current commercial SDD workbench that combines specs, worktrees, verification gates, and multi-agent review.  
**Adoption:** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09.  
**Momentum:** current 2026 official launch, release, or material portfolio update; public source cadence unavailable.  
**Measurement posture:** project artifacts; candidate `product-owned specs, plans, task state, or source directories require exact-path verification`; collision low-medium; schema partial.  
**Robbes relevance:** conditional — agent is plausible, but the product-specific trace requires a pinned source audit.  
**Scores:** **A1** current official product and portfolio signal verified; no comparable public usage census retained, checked 2026-11-09; **M3** current 2026 official launch, release, or material portfolio update; public source cadence unavailable; **C3** dedicated company, project organization, or research group: Zenflow; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F4** project artifacts: product-owned specs, plans, task state, or source directories require exact-path verification; **V4** important but needs source/schema work; **R4** low-medium; **E3** partial; **I4** A current commercial SDD workbench that combines specs, worktrees, verification gates, and multi-agent review.  
**Sources:** [primary](https://www.infoworld.com/article/4171332/4-cutting-edge-tools-for-spec-driven-development.html); checked 2026-11-09.

### 6.163 ZeroClaw

**Categories:** Personal AI Daemons & Local Gateways  
**Parent/backing:** ZeroClaw Labs  
**Coverage decision:** net-new product family; absent from latest pack and valid findings at canonical product/surface level.  
**Lifecycle:** current  
**Why it matters:** A high-momentum Rust personal-agent runtime emphasizes small binaries, local deployment, swappable providers, and persistent automation.  
**Adoption:** 33,285 GitHub stars; 5,004 forks; 266 default-branch commits/30d, checked 2026-11-09.  
**Momentum:** 266 commits/30d; latest release v0.8.7 on 2026-10-27.  
**Measurement posture:** runtime/dependency config; candidate `gateway, endpoint, image, or deployment content; local use may be invisible`; collision high; schema no-content.  
**Robbes relevance:** context-only — telemetry-, hosted-, runtime-, or standard-level activity does not identify the executing agent.  
**Scores:** **A4** 33,285 GitHub stars; 5,004 forks; 266 default-branch commits/30d, checked 2026-11-09; **M4** 266 commits/30d; latest release v0.8.7 on 2026-10-27; **C3** dedicated company, project organization, or research group: ZeroClaw Labs; **D1** no candidate-specific high-signal cluster retained; category discussion may still be strong; **F1** runtime/dependency config: gateway, endpoint, image, or deployment content; local use may be invisible; **V2** strategic context; weak direct attribution; **R1** high; **E1** no-content; **I3** A high-momentum Rust personal-agent runtime emphasizes small binaries, local deployment, swappable providers, and persistent automation.  
**Sources:** [primary](https://github.com/zeroclaw-labs/zeroclaw); [repository metadata](https://github.com/zeroclaw-labs/zeroclaw); checked 2026-11-09.

---

## 7. Corporate Portfolio Coverage

| Vendor | Current developer-agent portfolio | Net-new decision |
|---|---|---|
| Microsoft / GitHub | Copilot CLI, Fusion, Agent HQ, Agentic Workflows, code review Max; Azure SRE Agent; .NET Agent Skills | Copilot family exists in pack; all listed 2026 surfaces are deltas or new products |
| Google | Antigravity 2.0/CLI/SDK, ADK, Scion, Elephant-Goldfish, Conductor, Skills | Gemini/Jules exist; current successor and portfolio surfaces are net-new |
| AWS | Kiro successor path, AgentCore Harness, Strands, CLI Agent Orchestrator, DevOps Agent, Agent Toolkit | Kiro/Amazon Q exist; platform, orchestration, and SRE entries are net-new |
| Anthropic | Claude Code web, Agent SDK, Code Review, Agent Skills origin | Claude Code exists; cloud/review/SDK are deltas, Agent Skills is now AAIF |
| OpenAI | Codex Code Review, Agents SDK, Symphony | Codex exists; review and Symphony are deltas/new |
| Meta | Muse Code | Entire first-party coding-agent family is net-new |
| JetBrains | Junie GA/CLI and Air | Junie exists; GA/CLI and Air are material deltas |
| IBM | Bob; Concert reviewed but kept below the reporting line | Bob is the consequential net-new developer-agent entry |
| Salesforce | Agentforce Vibes and Agent Script development | Net-new platform-specific developer agent |
| ServiceNow | Build Agent; ITOM Prime / AIOps AI Specialist | Net-new app-generation and operations agents |
| SAP | Joule Studio | Net-new enterprise agent/app-development environment |
| Snowflake | Cortex Code / CoCo | Net-new data-native coding-agent family |
| NVIDIA | OpenShell / NemoClaw | Net-new agent runtime and sandbox portfolio |
| Alibaba | Qoder 1.0 portfolio, AgentScope, QwenPaw | Lingma/Qwen Code exist; Qoder successor plus frameworks are deltas/new |
| SpaceXAI / xAI | Grok Build | Net-new first-party open coding harness |
| Xiaomi | MiMo Code | Net-new first-party coding CLI |
| Cloudflare | Agents SDK and VibeSDK | Net-new framework and app-builder reference platform |
| Vercel | AI SDK, v0, Agent Plugins co-stewardship | All are absent as operational product entries |
| Coder | Xum/Mux and AgentAPI ecosystem | Net-new agent workspace/control-plane family |
| Block | Berd; Goose lineage | Goose exists; Berd is a new first-party workspace |
| Tricentis | Tabnine Enterprise Context Engine integrated into Agentic Quality Engineering | Tabnine remains supported after its July 2026 acquisition; ownership and portfolio context are updated |
| GitLab | Duo Agent Platform, foundational flows, Duo CLI, external agents, and agentic code review | Entire GA repository-side agent platform is net-new |
| ByteDance | Unified TRAE Agent/IDE platform, TraeWork lineage, cloud execution, and TraeCode CLI 2.0 | Base TRAE is covered; the merged 2026 platform is a material surface delta |
| Docker | Docker Agent, formerly cagent, bundled with Docker Desktop | Net-new declarative multi-agent builder and runtime |
| Databricks | Genie Code, Agent Bricks, and Omnigent | Net-new autonomous data-development agent and governed agent runtime portfolio |
| Datadog | Bits Investigation, Bits Remediation, and code-fix workflows | Net-new AI SRE investigation and remediation portfolio |
| Figma | Figma Make | Net-new prompt-to-prototype and code surface from independent public company Figma |
| Wix | Base44, Base Code, and Superagents | Base44 is retained as the acquired but distinct app-builder family |
| StackBlitz / Bolt.new | Bolt.new, Bolt Forge preview, and acquired Dokai orchestration technology | Bolt.new is retained; temporary research previews are not split into separate products |
| Replit | Replit Agent | Net-new hosted end-to-end app-development agent |
| Cognition | Devin and Devin Desktop, including the Windsurf successor lineage | Devin is covered; Devin Desktop is a material successor surface |
| Red Hat | Developer Lightspeed, Kaiden preview, agent sandboxes, and agentic SDLC tooling | Portfolio reviewed; preview/adjacent surfaces remain below the candidate line |
| Oracle | Oracle Code Assist and Fusion AI Studio Skill | Portfolio reviewed; Code Assist remains limited and assistant-like, while Fusion Agent Studio is outside the core developer-agent boundary |

---

## 8. Version, Rename, Acquisition, and Successor Ledger

- **GitHub Copilot:** Fusion is a routing/orchestration mode inside Copilot, not a standalone author identity; CLI, Agent HQ, automations, and review effort modes are surface deltas.
- **Google:** Antigravity 2.0 and Antigravity CLI are the consumer-forward successors to Gemini CLI/Code Assist, while enterprise Gemini access continues separately.
- **Alibaba:** Lingma became Qoder CN; Qoder 1.0 added an autonomous development desktop, while Qwen Code remains a distinct open CLI family.
- **Cognition:** Windsurf became Devin Desktop, replacing Cascade with Devin Local and combining local/cloud agents; old Windsurf evidence is not automatically current Devin evidence.
- **JetBrains:** Junie moved from plugin beta to a GA CLI-centered engine; Air is the wider multi-agent environment and governance portfolio.
- **IBM:** Bob is the forward agentic SDLC platform; watsonx Code Assistant remains supported with migration paths rather than being silently reclassified.
- **AWS:** Amazon Q Developer is transitioning toward Kiro for IDE/CLI development; AgentCore, Strands, DevOps Agent, and the agent toolkit are separate layers.
- **Portkey:** Palo Alto Networks acquired Portkey and now positions it as Prisma AIRS AI Gateway; repository/package names remain Portkey.
- **Kilo Code:** acquired by Anaconda in July 2026; the existing pack entry remains one family rather than a new product.
- **Gitar:** acquired by Sonar in May 2026; track Gitar's review identity separately from generic Sonar analysis and AI CodeFix.
- **Semgrep:** Semgrep Assistant was renamed Semgrep Multimodal in March 2026; Autofix is the current draft-PR remediation surface.
- **PagerDuty:** the SRE Agent is now named Paige; the current identity should replace generic pre-launch naming in future measurements.
- **MausBot:** the product and documentation now use MausBot while the public source repository remains `milind-soni/OpenMausBot`.
- **Strands:** the former Python SDK URL now redirects to the `strands-agents/harness-sdk` monorepo, which contains the SDKs, opinionated harness, CLI, docs, and tools; count it once.
- **ForgeCode:** `antinomyhq/forge` moved to `tailcallhq/forgecode`; Antinomy was a GitHub alias and Tailcall Inc. remains the company, so this is one product lineage.
- **Tabnine:** Tricentis acquired Tabnine in July 2026 and is integrating its Enterprise Context Engine into the Tricentis Agentic Quality Engineering Platform; existing products remain supported.
- **Paradev:** Superset was renamed Paradev and moved to `ParadevAI/Paradev`; the old Superset identity is an alias, not a second workspace.
- **Freebuff:** the Codebuff product rebranded to Freebuff, but the live repository remains `CodebuffAI/codebuff` (`CodebuffAI/freebuff` does not resolve); retain Codebuff as a historical alias.
- **Coder Mux:** the former Xum repository now resolves to `coder/mux`; treat Xum and Mux as one evolving product family.
- **TRAE:** TRAE SOLO became TraeWork, then TraeCode and TraeWork were merged into the unified TRAE Agent/IDE experience; TraeCode CLI 2.0 remains a separate enterprise terminal surface.
- **Docker Agent:** Docker renamed cagent to Docker Agent and moved the repository to `docker/docker-agent`; Docker Desktop 4.63+ ships the current name.
- **Datadog Bits:** the former Bits AI SRE naming now resolves into Bits Investigation plus Bits Remediation; preserve legacy names as aliases, not separate agents.
- **GitLab Duo:** distinguish the current agentic Code Review Flow inside Duo Agent Platform from the separately documented non-agentic Duo Code Review feature.
- **Figma:** Adobe and Figma terminated their proposed merger in 2023; Figma remains an independent public company, so Figma Make is not an Adobe portfolio entry.
- **Base44:** Wix acquired Base44 in June 2025 but continues to operate it as a distinct product; Base Code and Superagents remain surfaces of that family.
- **Bolt.new:** Bolt acquired Dokai in September 2026 and is folding its orchestration technology into Bolt; Dokai is not counted as a separate current developer agent.

---

## 9. Significant Rejections

These products were source-checked rather than silently omitted. They did not clear the current-addition gate.

| Candidate | Final reason |
|---|---|
| AutoGen | Microsoft designates Agent Framework as the forward path; keep as lineage/package history, not a new current addition. |
| Semantic Kernel | Still active, but Microsoft Agent Framework is the designated consolidated successor for this landscape decision. |
| TensorZero | Significant gateway concept, but the measured repository had no recent default-branch commits and weaker current momentum than retained gateways. |
| Aperant | Large star count but source cadence and 2.x maintenance/3.0 rebuild make the current product boundary unstable. |
| Crystal | Deprecated in favor of Nimbalyst; retain the successor rather than both names. |
| Nimbalyst | Current successor is credible but lower current adoption than the retained workspace leaders; monitor from the screen ledger. |
| Agent Deck | Active but materially below the retained multiplexer leaders in adoption and differentiation. |
| Agent of Empires | Credible active multiplexer, but below the retained category saturation line. |
| AnythingLLM | Large adjacent platform, but general document chat and local-agent features do not justify a coding-agent trace entry here. |
| LibreChat | Large self-hosted chat client, but coding-agent execution is not the product's defining repository behavior. |
| Jan | Important local assistant, but less directly relevant to the 16 developer-agent categories than retained daemon/runtime candidates. |
| Raven | Active meta-harness, but lower adoption and clearer alternatives place it below the final orchestrator saturation line. |
| Reason Agent | The cloud SWE product is current, but public adoption and independent discussion remain too thin relative to retained background-agent platforms. |
| Mobb | Real security remediation product, but lower measured category prominence than the retained review/fix agents. |
| Neovate Code | The CLI has a distinctive plugin architecture, but its last measured repository push was 2026-03-24 and corporate backing is indirect. |
| IBM Concert | Strategically relevant application-risk tooling, but its agent behavior is less distinct and less developer-facing than IBM Bob. |
| 8090 Software Factory | Material enterprise offer but public usage evidence is too opaque for the final set. |
| Murmur | Interesting self-verifying cloud fleet, but independent adoption evidence remains below the reporting gate. |
| Letta | The latest pack already represents the Letta product family through Letta Code; do not re-add it under a broader family label. |
| VoltAgent | Active framework with real adoption, but it falls below the saturated harness cut after adding Docker and Databricks' first-party runtimes. |
| Tabby | Large installed open-source assistant, but its repository cadence has slowed and the current agent surface is less distinct than retained IDE agents. |
| a0.dev | Useful React Native niche, but category influence and measurable use remain too narrow. |
| OpenRouter | A consequential model-routing service, but ordinary use is not agent-specific and retained gateways already cover the measurement class. |

---

## 10. Measurement Limits

- GitHub stars, forks, commits, registry downloads, marketplace installs, and search matches are different populations and are never added together.
- GitHub commit counts cover the current default branch and a 30-day window; repositories that squash, move development branches, or mirror code can look quieter than they are.
- Candidate-string counts in the six `/last30days` corpora are literal attention hints, not sentiment, unique posts, or verified product mentions; collision-prone names receive no special inflation.
- Corporate products often expose no public install count. Corporate backing guarantees a deep dive, not a high adoption score.
- Hosted builders, AIOps agents, and orchestration control planes can be strategically important while leaving no safe Git trace. Tier now expresses Robbes measurement readiness, not market importance; collision and encodability stay separate, and no identity is invented.
- Exact detector patterns are asserted only where official source contracts were retained. Every other Tier 1 entry still requires a pinned-source audit before pack implementation.
- The Robbes relevance label is a measurement-readiness judgment, not a product-quality judgment. Direct means a product-specific repository trace exists today; it does not mean the trace has been validated at the 0.5–1% false-positive level reported by Robbes et al. Conditional and context-only candidates remain valid market coverage but must not be counted as measured adoption.
