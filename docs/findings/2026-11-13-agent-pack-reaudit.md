# Coding-Agent Pack Re-audit: Final 78-Family Proposal

**Status:** final re-audit decision; supersedes the provisional 63 → 90 proposal  
**Research date:** 2026-11-13  
**Replit addendum:** official project/checkpoint contracts and product-controlled SCM markers move Replit Agent into the current-schema-safe additions  
**Abacus addendum (checked 2026-11-14):** resolves the orphan Abacus patterns, retains the exact Agent identity, rejects the release-automation bot as authorship, and adds current `.abacusai/**` project contracts  
**Evidence scope:** repository-visible, product-owned files and source-control metadata  
**Implementation scope:** report only; no pack or detector changes  
**Frozen baseline:** [`packs/2026-10-19.json`](../../packs/2026-10-19.json)  
**Superseded proposal:** [`docs/agent-pack-63-and-90.md`](../agent-pack-63-and-90.md)  
**Earlier decision:** [`2026-11-09-agent-inventory-final-decision.md`](2026-11-09-agent-inventory-final-decision.md)  
**Methodology:** [`2026-11-08-agent-fingerprint-methodology.md`](2026-11-08-agent-fingerprint-methodology.md)  
**Prior fingerprint audit:** [`2026-11-08-agent-fingerprint-research.md`](2026-11-08-agent-fingerprint-research.md)  
**Landscape ledger:** [`2026-11-08-agent-fingerprint-landscape-candidates.csv`](2026-11-08-agent-fingerprint-landscape-candidates.csv)  
**Human guide:** [`docs/trace-pack-2026-11-14-guide.md`](../trace-pack-2026-11-14-guide.md)

---

## 1. Decision

The provisional **63 → 90 active families** proposal should **not** ship. It mixes duplicate family rows, retired products, adjacent tooling, wrappers, and rules that the current detector cannot encode safely.

After normalizing duplicate rows, applying current lifecycle state, separating adjacent tooling, and requiring product-owned repository or official source-control evidence, the defensible proposal is:

| Disposition | Families | Meaning |
|---|---:|---|
| **Active, current-schema-safe** | **72** | At least one strong standalone rule can ship in the current pattern model. |
| **Active, schema-v2-gated** | **6** | The family is real and current, but safe detection needs content, conjunctions, hidden refs, custom trailers, or forge/channel scope. |
| **Total active** | **78** | 72 safe now + 6 gated. |
| **Watch** | **5** | Current product, but no reliable durable repository trace yet. |
| **Legacy-only** | **6** | Retain dated historical evidence; do not give the family active rule weight. |
| **Adjacent** | **12** | Methodology, context, orchestration technique, framework, or broad workspace—not code authorship. |
| **Excluded** | **4** | No distinct durable trace, or not a substantive deployed product. |
| **Folded variant** | **1** | Variant of an existing family rather than a separate family row. |
| **Pseudo-family** | **1** | `Generic`, retained only to classify shared-format evidence. |
| **Negative control** | **1** | Ghostty. |

The move from the earlier 76-family draft to 78 is **Replit Agent** plus **Abacus AI Agent / Coding Agent**. Each adds one current-schema-safe family; neither changes the six schema-v2-gated, watch, legacy, adjacent, excluded, variant, pseudo-family, or control groups.

### Shipping recommendation

1. Replace the 90-active-family concept with a **78-active-family catalogue**.
2. Ship only the **72 current-schema-safe families** in the present matcher model.
3. Hold the six composite families until schema v2 and its collector support exist.
4. Preserve legacy evidence with validity dates rather than silently deleting history.
5. Keep adjacent layers outside the coding-agent denominator.
6. Never infer wrapper or orchestrator authorship from the downstream agent it launches.

The audit and product addenda change only this report; they do not modify `packs/`, detector code, or tests.

---

## 2. Evidence and attribution rules

The re-audit uses a stricter standard than popularity, stars, downloads, marketplace installs, or product claims.

### 2.1 Acceptance standard

A current family needs at least one of the following, owned or explicitly documented by the product:

- a product-specific committed repository path;
- an exact Git author, committer, or required co-author identity;
- a generated branch namespace or constrained branch shape;
- a product-owned hidden ref;
- a product-specific custom trailer or workflow marker;
- official forge-native activity whose role is explicitly represented.

Popularity is useful for **discovery and prioritization only**. It is never attribution evidence.

### 2.2 Non-negotiable semantic boundaries

- A downstream agent's commit does not become a wrapper's commit merely because the wrapper launched it.
- PR review, issue participation, labels, comments, and app installation do not prove code authorship.
- A bot login and a commit email are different evidence types.
- `AGENTS.md`, `SKILL.md`, `MEMORY.md`, `agent.yaml`, and other shared formats do not identify a product by themselves.
- Configuration proves configuration. It does not necessarily prove execution or authorship.
- Recovery branches and hidden checkpoint refs identify exceptional modes; they must not be treated as ordinary session frequency.
- User-selected Git identities such as `ChatGPT` are not official source-control contracts.
- A terminal hosting an agent inherits none of the agent's repository evidence.

### 2.3 Why current matcher semantics matter

The frozen pack has five configurable pattern channels: authors, files, branches, labels, and bots. The current implementation cannot safely express all source contracts:

- [`src/detect/attribution.py`](../../src/detect/attribution.py) reuses author patterns across commit identities and message attribution.
- [`src/detect/channels.py`](../../src/detect/channels.py) collects PR and issue participants but does not preserve every semantic role or comment body.
- [`src/detect/local_channels.py`](../../src/detect/local_channels.py) scans ordinary branches, not arbitrary product-owned hidden refs.
- [`src/detect/packs.py`](../../src/detect/packs.py) serializes plain regex rules without lifecycle, content, conjunction, provenance, or rollup policy.

That means “a regex can be written” is not the same as “the rule is safe to ship.”

---

## 3. Count derivation

### 3.1 Frozen baseline normalization

The frozen pack contains **63 labels**, but they normalize to **59 family rows** after four duplicate-family collapses:

1. `CopilotSwe` → **Copilot**
2. `Factory` → **Factory Droid**
3. `Fly` + `Phoenix` → **Phoenix.new (Fly.io)**
4. `Windsurf` → **Devin / Devin Desktop**

The arithmetic is `63 - 1 - 1 - 1 - 1 = 59`: the Fly/Phoenix collapse removes one row, just like each other collapse.

The 59 normalized incumbent rows divide into:

| Incumbent disposition | Rows |
|---|---:|
| Current-schema-safe active | 47 |
| Watch | 3 |
| Legacy-only | 4 |
| Adjacent | 4 |
| Generic pseudo-family | 1 |
| **Total** | **59** |

### 3.2 Re-audited additions and missed candidates

| Candidate disposition | Rows |
|---|---:|
| Current-schema-safe active | 25 |
| Schema-v2-gated active | 6 |
| Watch | 2 |
| Legacy-only | 2 |
| Adjacent | 8 |
| Excluded | 4 |
| Folded variant | 1 |
| Negative control | 1 |

### 3.3 Final arithmetic

```text
Current-schema-safe active = 47 incumbent + 25 additions = 72
Schema-v2-gated active     =  0 incumbent +  6 additions =  6
Total active               = 72 + 6                    = 78

Watch                       = 3 incumbent + 2 additions = 5
Legacy-only                 = 4 incumbent + 2 additions = 6
Adjacent                    = 4 incumbent + 8 additions = 12
```

The folded variant, pseudo-family, exclusions, and negative control do not enter the active-family count.

---

## 4. Final active rosters

### 4.1 The 47 normalized active incumbent families

1. Aider
2. Qoder (Alibaba; successor to Lingma)
3. Amazon Q IDE
4. Amp
5. Atlassian Rovo CLI
6. Augment Code
7. Baidu Comate
8. Charlie
9. Claude Code
10. Cline
11. Codebuddy
12. Codegen
13. CodeRabbit
14. Codex
15. Copilot
16. Crush
17. Cursor
18. DeepSource
19. Devin / Devin Desktop
20. Factory Droid
21. Phoenix.new (Fly.io)
22. Google Antigravity / Gemini Code Assist
23. Goose
24. Gru
25. Jules
26. Junie
27. Kilo Code
28. Kiro
29. LangChain Open SWE
30. Letta Code
31. Microsoft Amplifier
32. Mistral Vibe
33. Ona
34. OpenCode
35. OpenHands
36. Pi
37. Plandex
38. Qodo
39. Qwen Coder
40. Zoo Code
41. Sentry Seer
42. Shelley
43. Sourcery
44. Tessl
45. Trae
46. Verdent
47. Warp

### 4.2 The 25 current-schema-safe additions

1. Builder.io Fusion
2. cubic
3. Greptile
4. Kody AI
5. Lovable
6. Paperclip
7. Hermes Agent
8. Command Code
9. Oh My Pi
10. OpenClaw
11. Gajae-Code
12. Docker Agent
13. OpenCodeReview
14. DeepSeek Harness
15. Grok Build
16. Prime Agent
17. JCode
18. Xiaomi MiMo Code
19. Freebuff (Codebuff lineage)
20. oh-my-claudecode
21. Archon
22. Kimi Code CLI
23. Roomote
24. Replit Agent
25. Abacus AI Agent / Coding Agent (DeepAgent lineage)

### 4.3 The six active schema-v2-gated families

1. GitLab Duo Agent Platform
2. Orca
3. T3 Code
4. GitHub Agentic Workflows
5. PR-Agent
6. Herder

---

## 5. Every frozen label accounted for

This table maps each of the 63 labels in [`packs/patterns/tools.csv`](../../packs/patterns/tools.csv) to its final treatment.

| # | Frozen label | Canonical family / treatment | Disposition |
|---:|---|---|---|
| 1 | Aider | Aider | Active |
| 2 | Alibaba Lingma | Qoder (Alibaba); `.lingma/**` becomes legacy lineage | Rename / active |
| 3 | Amp | Amp | Active |
| 4 | Augment Code | Augment Code | Active |
| 5 | Baidu Comate | Baidu Comate | Active |
| 6 | Brokk | Brokk | Legacy-only |
| 7 | ChatGPT | ChatGPT | Watch |
| 8 | Claude Code | Claude Code | Active |
| 9 | Cline | Cline | Active |
| 10 | Codebuddy | Codebuddy | Active |
| 11 | Codegen | Codegen | Active |
| 12 | Coderabbit | CodeRabbit | Active |
| 13 | Codex | Codex | Active |
| 14 | Continue | Continue | Legacy-only |
| 15 | Copilot | Copilot | Active |
| 16 | CopilotSwe | Copilot | Merge |
| 17 | Crush | Crush | Active |
| 18 | Cursor | Cursor | Active |
| 19 | Deepsource | DeepSource | Active |
| 20 | Devin | Devin / Devin Desktop | Active |
| 21 | Factory | Factory Droid | Merge |
| 22 | Fly | Phoenix.new (Fly.io) | Merge |
| 23 | Gemini | Google Antigravity / Gemini Code Assist | Rename / active |
| 24 | Generic | Shared-format evidence only | Pseudo-family |
| 25 | Goose | Goose | Active |
| 26 | GPT-Engineer | GPT-Engineer, precursor to Lovable | Legacy-only |
| 27 | Gru | Gru | Active |
| 28 | Jules | Jules | Active |
| 29 | Junie | Junie | Active |
| 30 | Kilo Code | Kilo Code | Active |
| 31 | Kiro | Kiro, including transitioned Amazon Q CLI lineage | Active |
| 32 | Langchain Open SWE | LangChain Open SWE | Active |
| 33 | Ona | Ona | Active |
| 34 | Opencode | OpenCode | Active |
| 35 | OpenHands | OpenHands | Active |
| 36 | Plandex | Plandex | Active |
| 37 | Phoenix | Phoenix.new (Fly.io) | Merge |
| 38 | Qwen Coder | Qwen Coder | Active |
| 39 | Roo Code | Zoo Code; `.roo/**` retained as lineage | Rename / active |
| 40 | Sketch | Shelley | Rename / active |
| 41 | Sourcery | Sourcery | Active |
| 42 | Sweep | Sweep | Legacy-only |
| 43 | Taskmaster | Taskmaster | Adjacent |
| 44 | Trae | Trae | Active |
| 45 | Warp | Warp | Active |
| 46 | Windsurf | Devin / Devin Desktop | Merge |
| 47 | Zed | Zed Agent | Watch |
| 48 | SpecKit | SpecKit | Adjacent |
| 49 | Tessl | Tessl | Active |
| 50 | Serena | Serena | Adjacent |
| 51 | Rulesync | Rulesync | Adjacent |
| 52 | Qodo | Qodo | Active |
| 53 | Verdent | Verdent | Active |
| 54 | AmazonQ | Amazon Q IDE; Q CLI lineage moves to Kiro | Transition / active |
| 55 | Charlie | Charlie | Active |
| 56 | Azad | Azad | Watch |
| 57 | Letta Code | Letta Code | Active |
| 58 | Mistral Vibe | Mistral Vibe | Active |
| 59 | Factory Droid | Factory Droid | Active |
| 60 | Microsoft Amplifier | Microsoft Amplifier | Active |
| 61 | Sentry Seer | Sentry Seer | Active |
| 62 | Pi | Pi | Active |
| 63 | Atlassian Rovodev | Atlassian Rovo CLI | Transition / active |

### 5.1 Grouped incumbent disposition

**Retain active, with corrections or enrichment:** Aider, Amp, Augment Code, Baidu Comate, Claude Code, Cline, Codebuddy, Codegen, CodeRabbit, Codex, Copilot, Crush, Cursor, DeepSource, Devin, Goose, Gru, Jules, Junie, Kilo Code, Kiro, LangChain Open SWE, Ona, OpenCode, OpenHands, Plandex, Qwen Coder, Sourcery, Trae, Warp, Tessl, Qodo, Verdent, Charlie, Letta Code, Mistral Vibe, Factory Droid, Microsoft Amplifier, Sentry Seer, and Pi.

**Rename or succeed:** Alibaba Lingma → Qoder; Gemini → Google Antigravity / Gemini Code Assist; Roo Code → Zoo Code; Sketch → Shelley.

**Current transition:** Amazon Q CLI → Kiro while Amazon Q IDE remains supported until its announced 2027 end of life; Atlassian Rovo Dev → unified Atlassian Rovo CLI as migration details settle.

**Merge:** CopilotSwe → Copilot; Factory → Factory Droid; Fly + Phoenix → Phoenix.new; Windsurf → Devin / Devin Desktop.

**Legacy-only:** Brokk, Continue, GPT-Engineer, Sweep.

**Watch:** ChatGPT, Zed Agent, Azad.

**Adjacent:** Taskmaster, SpecKit, Serena, Rulesync.

**Pseudo-family:** Generic.

### 5.2 Orphan pattern subtypes outside the 63-label tool table

The baseline pattern CSVs also contain subtype names that are absent from `tools.csv`; they do not appear in the 63-label table above but still affect matching:

- **Kimi Code** becomes the active Kimi Code CLI addition in §7.22.
- **Verd** is a typo/orphan and must roll up to Verdent.
- **Abacus** becomes the active **Abacus AI Agent / Coding Agent** addition in §7.25, with DeepAgent retained as predecessor lineage.

The two frozen Abacus author rows do not receive the same treatment. Exact `agent@abacus.ai` is valid current Agent attribution. `abacus-ai-automation[bot]` is Abacus release/CI automation and must not count as coding-agent use; preserve it as a rejected/noise fingerprint or generic bot exclusion rather than an Abacus authorship rule.

---

## 6. Successors, renames, and lifecycle transitions

### 6.1 Lingma → Qoder

- Current product-owned surfaces are `.qoder/settings.json`, `.qoder/rules/**`, and `.qoder/agents/*.md`.
- `.lingma/**` is historical lineage evidence.
- The family row should be named **Qoder (Alibaba)** rather than keeping a separate Lingma row.

### 6.2 Gemini → Google Antigravity / Gemini Code Assist

- Antigravity is the consumer successor.
- Gemini CLI remains supported for enterprise and API-key use.
- `.gemini/**` therefore remains valid lineage evidence and is not universally legacy.
- Consumer Gemini CLI rules need a validity boundary around the 2026-06-18 transition rather than an undated deletion.

### 6.3 Roo Code → Zoo Code

- Roo Code ended on 2026-05-15.
- Zoo Code is the direct community continuation.
- Zoo Code deliberately retains `.roo/**`, so that namespace is current compatibility evidence under the successor family as well as historical Roo evidence.

### 6.4 Sketch → Shelley

- Current strong identity: `Shelley <shelley@exe.dev>`.
- Required co-author evidence:

  ```regex
  ^shelley@exe\.dev$
  ```

- `hello@sketch.dev` is predecessor evidence only.
- Schema v2 can add the hidden note ref `refs/notes/shelley-tour`.

### 6.5 Windsurf → Devin Desktop

- Windsurf was renamed on 2026-06-02.
- `.windsurf/**`, `.windsurfrules`, Cascade, and related Codeium/Windsurf surfaces are compatibility or predecessor evidence under the Devin family.
- They should not remain a second active family row.

### 6.6 Amazon Q CLI → Kiro

- Amazon Q CLI was rebranded to Kiro.
- Q CLI evidence should roll into Kiro after the transition.
- Amazon Q IDE remains temporarily distinct and supported until its announced 2027 EOL.
- Historical Q CLI rules need dates; they must not be silently treated as current Amazon Q IDE evidence.

### 6.7 Atlassian Rovo Dev → Rovo CLI

- Preserve the Rovo Dev lineage.
- Move the canonical family name toward **Atlassian Rovo CLI** when the remaining official migration details are stable.
- Fix the frozen CSV subtype that currently carries a leading space.

### 6.8 Phoenix / Fly

- Both frozen rows describe Phoenix.new.
- Public generated commits use the exact identity `Fly Dev <dev@fly.io>`.
- The safe email rule is:

  ```regex
  ^dev@fly\.io$
  ```

- This is one family, **Phoenix.new (Fly.io)**, not separate Fly and Phoenix rows.

---

## 7. Exact current-schema-safe rules for the 25 additions

The regexes below are written in their intended anchored form. They are recommendations, not changes already made to the pack. Directory rules intentionally require a documented product-owned leaf or subtree instead of a bare shared directory.

### 7.1 Builder.io Fusion

**Strong file rule**

```regex
^\.builderrules$
```

The Builder bot's comments or review participation are activity evidence and must not be converted into authorship merely by matching a login.

### 7.2 cubic

**Strong exact commit email / trailer email**

```regex
^191113872\+cubic-dev-ai\[bot\]@users\.noreply\.github\.com$
```

The root `cubic.yaml` path is useful only with content validation; see §9.2.

### 7.3 Greptile

**Strong project files**

```regex
^(?:\.greptile/(?:config\.json|rules\.md)|greptile\.json)$
```

Greptile review comments are review activity, not generated-code authorship.

### 7.4 Kody AI

**Strong project file**

```regex
^kodus-config\.yml$
```

`@kody` commands require comment-body collection and role scope; the config file is the current-schema-safe rule.

### 7.5 Lovable

**Strong exact raw Git author email**

```regex
^159125892\+gpt-engineer-app\[bot\]@users\.noreply\.github\.com$
```

GitHub displays the account under its current `lovable-dev[bot]` name, while raw Git history retains the earlier account identity.

**Recovery/sync branches**

```regex
^lovable-sync(?:-[0-9]+)?$
```

The branch is a divergence or protected-branch recovery mechanism, not ordinary execution evidence. The schema-v2 edit trailer is listed in §9.2.

### 7.6 Paperclip

**Strong exact author/committer/trailer email**

```regex
^noreply@paperclip\.ing$
```

**Recovery-only branch**

```regex
^paperclip/rescue/[^/]+/[0-9]{8}T[0-9]{6}Z$
```

The `.paperclip.yaml` and `.paperclip.yml` files require `schema: paperclip/v1`; path-only file matching remains gated.

### 7.7 Hermes Agent

**Strong native context files**

```regex
(?:^|/)(?:\.hermes\.md|HERMES\.md)$
```

**Strong generated plans**

```regex
^\.hermes/plans/[^/]+\.md$
```

**Strong automatic worktree branch**

```regex
^hermes/hermes-[0-9a-f]{8}$
```

Named `hermes/<user-value>` branches are only corroborating. Optional subagent branches remain disabled by default:

```regex
^hermes-subagent/subagent-[^/]+$
```

Archive refs and `hermes-archive@localhost` require schema-v2 ref scope.

### 7.8 Command Code

**Strong exact files**

```regex
^\.commandcode/(?:settings\.json|AGENTS\.md)$
```

```regex
^\.commandcode/(?:skills|agents|commands|mods|design|taste)/.+$
```

**Strong exact trailer email**

```regex
^noreply@commandcode\.ai$
```

**Strong cloud branch**

```regex
^command-code/[^/]+$
```

Local `worktree-*` branches are generic and must not be attributed to Command Code.

### 7.9 Oh My Pi

**Strong exact files**

```regex
^\.omp/(?:config\.ya?ml|settings\.json|mcp\.json|AGENTS\.md)$
```

```regex
^\.omp/(?:agents|commands|skills|tools|extensions|prompts|rules|hooks|plugins)/.+$
```

**Optional isolation branch**

```regex
^omp/task/[^/]+$
```

Generic `wt/<timestamp>` and `pr-<number>` branches are not safe product attribution.

### 7.10 OpenClaw

**Strong managed-worktree setup file**

```regex
(?:^|/)\.openclaw/worktree-setup\.sh$
```

**Product branch namespace**

```regex
^openclaw/[^/]+$
```

The branch proves OpenClaw orchestration, not authorship of downstream commits. Shared workspace files, hidden refs, and `openclaw@localhost` are handled in §9.2.

### 7.11 Gajae-Code

**Strong exact files**

```regex
^\.gjc/(?:config\.yml|mcp\.json|\.mcp\.json|AGENTS\.md)$
```

```regex
^\.gjc/(?:agents|skills|commands|extensions)/.+$
```

**Optional task branch**

```regex
^gjc/task/[^/]+$
```

The task branch is real but should be disabled by default because it represents an optional isolation mode.

### 7.12 Docker Agent

**Strong product-named root definitions**

```regex
^docker-agent\.(?:ya?ml|hcl)$
```

Generic `agent.yaml`, `agent.yml`, or HCL files are not safe without Docker Agent schema or product-key content.

### 7.13 OpenCodeReview

**Strong project rules file**

```regex
(?:^|/)\.opencodereview/rule\.json$
```

The user-level `~/.opencodereview/rule.json` is product evidence but is normally outside a repository scan.

### 7.14 DeepSeek Harness

**Strong committed DSH skill entry files**

```regex
^\.dsh/skills/(?:[^/]+/SKILL\.md|[^/]+\.md)$
```

This current product-owned `.dsh` surface replaces the earlier conclusion that only generic `.agents/**` material existed. Generic `.agents/skills/**` remains unsafe.

**Optional experimental worktree branch, disabled by default**

```regex
^dsh-[0-9a-f]{8}(?:-[0-9a-f]{4})?$
```

`dsh-superagent` is a variant of this family, not a separate row.

### 7.15 Grok Build

**Strong exact configuration files**

```regex
^\.grok/(?:config\.toml|sandbox\.toml|lsp\.json)$
```

**Strong product subtrees**

```regex
^\.grok/(?:rules|skills|plugins|agents|hooks)/.+$
```

**Strong workflow files**

```regex
^\.grok/workflows/[^/]+\.rhai$
```

Do **not** use community `.grok/settings.json` or bare `.grok/` as Grok Build evidence.

### 7.16 Prime Agent

**Strong project files and subtrees**

```regex
^\.prime/agent/(?:settings\.json|APPEND_SYSTEM\.md)$
```

```regex
^\.prime/agent/(?:skills|prompts)/.+$
```

Prime Agent deliberately avoids setting Git identity. Do not invent a bot email or infer identity from its downstream model.

### 7.17 JCode

**Strong exact project files**

```regex
^\.jcode/(?:config\.toml|mcp\.json|prompt-overlay\.md|preferred-tools\.md|system-prompt\.md|swarm-prompt\.md|cloud-environment\.json)$
```

**Strong project skills**

```regex
^\.jcode/skills/.+$
```

JCode also avoids overriding Git identity; its repository configuration is the evidence.

### 7.18 Xiaomi MiMo Code

**Strong exact project files**

```regex
^\.mimocode/(?:mimocode\.jsonc?|tui\.json)$
```

**Strong project subtrees**

```regex
^\.mimocode/(?:workflows|skills)/.+$
```

### 7.19 Freebuff (Codebuff)

**Strong product ignore/transfer files**

```regex
(?:^|/)\.(?:codebuff|freebuff|manicode)ignore$
```

**Strong default co-author email**

```regex
^noreply@codebuff\.com$
```

The exact retained trailer is:

```text
Co-Authored-By: Codebuff <noreply@codebuff.com>
```

Attribution is default-on but suppressible. `.freebuffignore` is transfer-scoped rather than a read-policy file; that distinction belongs in evidence semantics even though the filename remains product-owned.

### 7.20 oh-my-claudecode

**Strong project config**

```regex
^\.claude/omc\.jsonc$
```

**Strong committed project skills**

```regex
^\.omc/skills/.+$
```

Do not attribute Claude Code's downstream commits to oh-my-claudecode merely because it orchestrated the session.

### 7.21 Archon

**Strong config and workflow files**

```regex
^\.archon/config\.ya?ml$
```

```regex
^\.archon/workflows/[^/]+\.ya?ml$
```

```regex
^\.archon/packs/[^/]+\.ya?ml$
```

```regex
^\.archon/sdlc/policy/.+$
```

Archon evidence identifies the harness/orchestration layer, not the author of downstream changes.

### 7.22 Kimi Code CLI

**Strong Kimi-specific project files**

```regex
^\.kimi-code/(?:AGENTS\.md|local\.toml|mcp\.json)$
```

**Strong Kimi-specific project agents and skills**

```regex
^\.kimi-code/(?:agents|skills)/.+$
```

The archived Python `MoonshotAI/kimi-cli` is predecessor lineage. The active family is the TypeScript **Kimi Code CLI** and uses `.kimi-code/**`, not the old `.kimi/**` data root.

### 7.23 Roomote

**Strong exact generated-commit email**

```regex
^301996811\+roomote-roomote\[bot\]@users\.noreply\.github\.com$
```

This exact commit email is safe. A bare `roomote` login or review participant is not equivalent to authorship.

### 7.24 Replit Agent

**Strong root Agent context file**

```regex
^replit\.md$
```

Replit's [official `replit.md` contract](https://docs.replit.com/features/project-setup/replit-dot-md.md) says Agent automatically creates this file at the project root, reads it in later conversations, and may update it as the project changes. Users can also create it manually, so the file proves Replit Agent configuration or intended use, not that Agent authored every change in the repository.

**Strong exact Git author, committer, or co-author email**

```regex
(?:^|<)agent@replit\.com(?:>|$)
```

Public Git history shows this exact Replit-controlled identity in two current forms: `agent <agent@replit.com>` as author and committer on Agent-created initial commits, linked by GitHub to the `replit-agent` account; and `Co-authored-by: Replit Agent <agent@replit.com>` on synchronized or squashed Agent work. The explicit start/end-or-angle-bracket boundaries keep both raw identity fields and standard trailer forms exact. This is preferable to a broad `Replit`, `Agent`, or `replit-agent` identity rule that could contaminate forge participation channels.

The email is not universal: many checkpoint commits retain a per-user Replit identity instead. Its absence therefore proves nothing, while its presence remains strong attribution.

The product-specific checkpoint trailer `Replit-Commit-Author: Agent` is stronger execution evidence, but it belongs in the structured-trailer enrichment in §9.2. Its value must remain distinct from `Replit-Commit-Author: Deployment`. `Replit-Commit-Session-Id`, checkpoint type, event ID, screenshot URL, and `Replit-Helium-Checkpoint-Created` are corroborating only because deployment checkpoints can carry the same surrounding fields.

Do **not** use `.replit`, `replit.nix`, `.replit-artifact/**`, or per-user `*@users.noreply.replit.com` addresses as Replit Agent evidence. Those identify Replit hosting, runtime configuration, artifacts, or a user-scoped Replit Git identity; they do not distinguish Agent edits from manual work or publishing.

### 7.25 Abacus AI Agent / Coding Agent

**Strong exact Git author, committer, or co-author email**

```regex
(?:^|<)agent@abacus\.ai(?:>|$)
```

GitHub's exact `author-email:` index returned 2,079 commits and mapped current samples to the product-controlled `abacusai-agent` account. The identity appears as `Abacus AI Agent <agent@abacus.ai>` and historically as `DeepAgent <agent@abacus.ai>`; both roll up to one family. Standard co-author samples also use `Abacus.AI CLI <agent@abacus.ai>`. The explicit boundaries keep raw identity fields and angle-bracket trailer forms exact.

**Strong product-specific project files**

```regex
^\.abacusai/(?:config\.json|mcp\.json)$
```

```regex
^\.abacusai/skills/[^/]+/SKILL\.md$
```

```regex
^\.abacusai/hooks/.+$
```

Current [official settings documentation](https://abacus.ai/help/abacusai-desktop/settings) defines root `.abacusai/config.json` as workspace configuration and explicitly permits committing it for the team. The Agent normally adds that file to `.abacusai/.gitignore`, so committed occurrence is optional and absence proves nothing. Official [MCP](https://abacus.ai/help/abacusai-desktop/mcp-configuration), [skills](https://abacus.ai/help/abacusai-desktop/agents-and-skills), and [hooks](https://abacus.ai/help/abacusai-desktop/hooks) documentation defines the other project paths and recommends committing shared forms. Indexed checks found 49 `.abacusai/config.json` files and 18 `.abacusai/skills/**/SKILL.md` files; inspected samples followed the product contract. No public `.abacusai/mcp.json` or hook sample was indexed, but the official repository contract is exact.

Do **not** retain `abacus-ai-automation[bot]` as an Abacus coding-agent author. Its exact commit email is `194430910+abacus-ai-automation[bot]@users.noreply.github.com`; sampled commits are product release-manifest updates, and the account currently publishes AbacusAI Bot release assets. Move the login to generic release/CI noise or a rejected-fingerprint ledger.

`Co-Authored-By: Abacus AI Agent <noreply@abacus.ai>` is observed and current, but `noreply@abacus.ai` by itself is a broader product-domain address. Keep the exact name-plus-email trailer as schema-v2 corroboration rather than a standalone flat author rule.

The current distributed CLI deliberately refuses to invent Git identity when `user.name` or `user.email` is unset. Its snapshots live outside the project under `~/.abacusai/checkpoints` and “never write to the repository's `.git`.” The packaged synthetic identity `Abacus Checkpoint <checkpoint@abacus.ai>` and `refs/abacus/**` therefore belong to the external checkpoint store, not normal target-repository evidence. Likewise, `.abacusai/worktrees/**` is local worktree state with caller-selected names, `AGENTS.md` is shared, and `.agents/skills/**` is cross-tool.

### 7.26 Optional rules disabled by default

These are source-verified but represent optional isolation, subagent, or recovery modes rather than ordinary use:

```regex
# DeepSeek Harness experimental worktrees
^dsh-[0-9a-f]{8}(?:-[0-9a-f]{4})?$

# Hermes optional subagent worktrees
^hermes-subagent/subagent-[^/]+$

# Paperclip recovery
^paperclip/rescue/[^/]+/[0-9]{8}T[0-9]{6}Z$

# Gajae-Code optional task isolation
^gjc/task/[^/]+$

# Oh My Pi optional task isolation
^omp/task/[^/]+$
```

---

## 8. Six active families gated on schema v2

These families are not speculative. Each has current product-owned evidence. The gate is the detector model, not the evidence quality.

### 8.1 GitLab Duo Agent Platform

**Required evidence**

```regex
^duo/(?:fix|feature|refactor|docs)/.+$
```

The branch must be collected and interpreted as **GitLab** evidence, ideally alongside the Duo service account and its role.

**Why current schema is insufficient**

- The existing collection model is GitHub-centric.
- GitHub user/bot assumptions must not be transferred to GitLab identities.
- Service-account participation needs channel and role semantics.
- Duo orchestration or review participation must not automatically count as authored code.

### 8.2 Orca

**Required evidence**

- root `orca.yaml`; and
- parsed Orca-specific keys, preferably one or more of:
  - `setupAgentStartupPolicy`
  - `environmentRecipes`
  - `issueCommand`
  - `defaultTabs`
  - `worktree.sharedDirectories`
  - `scripts.setup`
  - `scripts.archive`

**Why current schema is insufficient**

`orca.yaml` alone has substantial unrelated use. The re-audit found 689 indexed results with unrelated chemistry, robotics, data, and workflow configurations, including root files. Orca therefore needs a root path plus parsed content predicate.

Orca identifies an orchestrator. Downstream Claude, Codex, or other commits remain attributed to those agents.

### 8.3 T3 Code

**Required evidence**

- root `t3.json`; and
- JSON `$schema` exactly equal to:

  ```text
  https://t3.codes/schema/t3.json
  ```

The branch namespace below is corroborating only:

```regex
^t3/
```

**Why current schema is insufficient**

The filename is generic and the search result set is enormous. The detector must parse JSON content and assert the schema value. A branch prefix alone is not sufficient.

### 8.4 GitHub Agentic Workflows

**Required evidence: either**

1. `.github/workflows/<name>.md` plus `.github/workflows/<name>.lock.yml` with the same stem; or
2. lockfile content beginning with:

   ```text
   # gh-aw-metadata:
   ```

**Why current schema is insufficient**

The signal needs a same-stem file conjunction or bounded content matching. A Markdown file under `.github/workflows/` by itself is not enough.

### 8.5 PR-Agent

**Required workflow content**

```yaml
uses: the-pr-agent/pr-agent@<version>
```

or a container/image reference to:

```text
pragent/pr-agent
```

**Why current schema is insufficient**

Qodo and open-source PR-Agent deliberately share `.pr_agent.toml`. That path proves review-agent lineage but cannot select a family. Safe separation needs workflow content or Qodo-only config content.

### 8.6 Herder

**Required custom trailer**

```regex
^Herder-Session:\s*\S+\s*$
```

**Required hidden ref**

```regex
^refs/herder/[^/]+/[^/]+$
```

Checkpoint identity `herder <herder@localhost>` is valid only under that hidden ref namespace.

**Corroborating default branch**

```regex
^herder/[0-9a-hjkmnp-tv-z]{8}$
```

**Why current schema is insufficient**

- custom trailer tokens are not first-class;
- arbitrary hidden refs are not collected;
- the synthetic identity must be ref-scoped;
- the branch is useful corroboration but not enough to replace the trailer/ref contract.

Herder should be restored as gated active. Current source at `1a5429431a68` still installs `Herder-Session:` and publishes `refs/herder/**`. The earlier exclusion was a schema limitation, not an evidence failure.

---

## 9. Schema-v2 enrichments for otherwise detectable families

These enrichments do not add family rows. They improve precision or recover evidence that current flat regex lists cannot represent.

### 9.1 Composite and scoped evidence

| Family | Schema-v2 evidence and semantics |
|---|---|
| Paperclip | Root `.paperclip.yaml` or `.paperclip.yml` containing `schema: paperclip/v1`. |
| cubic | Root `cubic.yaml` containing `$schema: https://cubic.dev/schema/cubic-repository-config.schema.json`, or parsed `version: 1` plus `reviews`. |
| Qodo | `.pr_agent.toml` containing Qodo-only `[review_agent]`, `/agentic_review`, or `/agentic_describe`; otherwise emit ambiguous Qodo/PR-Agent lineage. |
| Lovable | Custom trailer `X-Lovable-Edit-ID: edt-<uuid>`. |
| Replit Agent | Custom trailer token `Replit-Commit-Author` with value exactly `Agent`; value `Deployment` is an explicit non-Agent control. Session, checkpoint, event, screenshot, and Helium fields are corroborating only. |
| Abacus AI Agent | Standard co-author trailer requiring the exact name `Abacus AI Agent` together with `noreply@abacus.ai`; the email alone is not selected. External checkpoint-store identity and refs are explicitly out of repository scope. |
| OpenClaw | Workspace conjunction `AGENTS.md` + `SOUL.md` + `IDENTITY.md`; product hidden refs; synthetic identity only under those refs. |
| Docker Agent | Generic `agent.yaml`/HCL only when content has the Docker Agent schema or product-specific top-level keys. |
| DeepSeek Harness | `dsh-superagent` comment marker and hidden refs, rolled up as a DSH variant. |
| Shelley | Hidden note ref `refs/notes/shelley-tour`. |
| Hermes Agent | Archive ref plus archive-scoped synthetic identity. |

### 9.2 Exact enrichment contracts

**Paperclip content gate**

```yaml
path: '^\.paperclip\.ya?ml$'
root: true
content:
  format: yaml
  predicates:
    - yaml_path: '$.schema'
      equals: 'paperclip/v1'
```

**cubic content gate**

```yaml
anyOf:
  - content:
      format: yaml
      predicates:
        - yaml_path: '$.$schema'
          equals: 'https://cubic.dev/schema/cubic-repository-config.schema.json'
  - content:
      format: yaml
      predicates:
        - yaml_path: '$.version'
          equals: 1
        - yaml_path: '$.reviews'
          exists: true
```

The exact cubic bot email in §7.2 remains safe without this file rule.

**Qodo-only content selectors**

```text
[review_agent]
/agentic_review
/agentic_describe
```

Without one of those selectors or exact Qodo commit identities, classify `.pr_agent.toml` as ambiguous **Qodo/PR-Agent lineage**, not as either family conclusively.

**Lovable edit trailer**

```regex
^X-Lovable-Edit-ID:\s*edt-[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\s*$
```

**Replit Agent checkpoint trailer**

```regex
^Replit-Commit-Author:\s*Agent\s*$
```

Parse this as the custom token `Replit-Commit-Author` and require the value `Agent`. Do not reduce the rule to a broad match for `Replit` or `Agent`, and do not attribute this explicit deployment form to Replit Agent:

```text
Replit-Commit-Author: Deployment
```

The Replit session ID, checkpoint type, event ID, screenshot URL, deployment build ID, and `Replit-Helium-Checkpoint-Created` fields may describe the checkpoint but do not independently select Agent versus Deployment.

**Abacus AI Agent noreply trailer**

```regex
^Co-Authored-By:\s*Abacus AI Agent\s*<noreply@abacus\.ai>\s*$
```

This is a name-plus-email conjunction. `noreply@abacus.ai` without the exact Agent co-author role is insufficient. Do not collect `checkpoint@abacus.ai` or `refs/abacus/**` from Abacus's external checkpoint store as target-repository activity.

**OpenClaw workspace conjunction**

```yaml
allOf:
  - path: '^AGENTS\.md$'
  - path: '^SOUL\.md$'
  - path: '^IDENTITY\.md$'
same_tree: true
```

No singleton in that set is OpenClaw evidence.

**OpenClaw hidden refs**

```regex
^refs/openclaw/(?:snapshots(?:/exact-v1)?|removals|worker-results)/.+$
```

`openclaw@localhost` is valid only for the owning synthetic operation/ref. Ordinary public-history occurrences remain anomalous, not a verified current default.

**DeepSeek Harness / dsh-superagent variant**

```regex
^<!--\s*dsh-superagent:[^>]+\s*-->$
```

```regex
^refs/dsh-superagent/.+$
```

Those hits roll up to **DeepSeek Harness**, with `variant: dsh-superagent`; they do not create another family count.

**Shelley note ref**

```regex
^refs/notes/shelley-tour$
```

**Hermes archive evidence**

```regex
^refs/hermes/archive/[^/]+$
```

`Hermes worktree archive <hermes-archive@localhost>` is valid only on commits under that ref.

---

## 10. Lifecycle, watch, adjacent, excluded, and control groups

### 10.1 Legacy-only families — 6

1. **Brokk** — source archived in August 2026; the company pivoted to SlopCop.
2. **Continue** — acquired by Cursor and discontinued as a standalone product.
3. **GPT-Engineer** — archived precursor to Lovable.
4. **Sweep** — old GitHub app deprecated; later JetBrains product shut down in April 2026.
5. **Claw Code** — repository now describes itself as an “agent-managed museum exhibit.”
6. **DeepSeek Reasonix** — archived on 2026-11-12.

Legacy-only means historical evidence remains useful with dates. It does not mean deleting old evidence or pretending the products never existed.

### 10.2 Lifecycle-bounded aliases, not extra legacy rows

- `.lingma/**` → Qoder predecessor evidence.
- `.windsurf/**`, `.windsurfrules`, and Cascade → Devin Desktop lineage.
- `.roo/**` historical Roo evidence and current Zoo compatibility.
- `hello@sketch.dev` → Shelley predecessor identity.
- Gemini CLI consumer rules before 2026-06-18.
- Amazon Q CLI rules before the Kiro transition.
- OpenCode v1 identities, generated footer, bot, and `opencode/` branches.
- `DeepAgent` naming → Abacus AI Agent / Coding Agent predecessor lineage; exact `agent@abacus.ai` remains current.
- Orca's retired `help@stably.ai` co-author trailer.
- `.cursorrules`, `.vibe/tools/`, and `.openhands/microagents/`.

### 10.3 Watch — 5

1. **ChatGPT** — `ChatGPT` and `chatgpt@openai.com` are user-selected Git identities, not an official SCM contract.
2. **Azad** — current VS Code product, but its former public repository is gone and no durable project marker is documented.
3. **Zed Agent** — active native agent, but project instruction files are shared standards and `.zed/settings.json` proves editor configuration rather than agent execution.
4. **Herdr** — only the generated `worktree/<adjective>-<noun>-<4hex>` shape is distinctive; caller-selected branches remain possible and no stronger native attribution exists.
5. **claude-flow / Ruflo** — project state is normally ignored and the RuFlo co-author trailer is opt-in.

### 10.4 Adjacent — 12

1. Taskmaster
2. SpecKit
3. Serena
4. Rulesync
5. Azure SRE Agent
6. BMAD-METHOD
7. OpenSpec
8. Ruler
9. LangGraph
10. snarktank/ralph
11. GitAI / Graft
12. Odysseus

Important boundaries:

- Ralph's copied script tree identifies the loop implementation, but the resulting commits remain Amp or Claude Code commits.
- GitAI/Graft is agent-oriented version-control infrastructure, not a coding-agent author family.
- Odysseus is a broad self-hosted AI workspace, not a repository coding-agent family.
- Task planning, spec workflows, semantic tooling, and rules synchronization can be measured in separate inventories without inflating coding-agent adoption.

### 10.5 Excluded — 4

1. **LazyCodex** — documented thin alias for oh-my-openagent installation on Codex; no distinct committed project trace.
2. **Dori superagent** — Herdr + OmO bundle; attribution remains with those layers and any downstream agent.
3. **Aperant** — relevant `.aperant/` and spec state is deliberately ignored; no durable committed product marker.
4. **Odysseus Workshop** — educational minimal harness, not a deployed product trace.

### 10.6 Folded variant — 1

**dsh-superagent** belongs under **DeepSeek Harness**. Its marker may be retained as a variant field in schema v2, but it must not add a family row.

### 10.7 Pseudo-family — 1

**Generic** is retained only for shared-format evidence such as `AGENTS.md`. It must never be presented as a vendor or product family and must never turn a shared file into product attribution.

### 10.8 Negative control — 1

**Ghostty** is a terminal. It leaves no native repository evidence. Its own source repository's `AGENTS.md` and `.agents/**` are contributor guidance, not proof that Ghostty authored downstream changes. Any detected work belongs to the agent running inside the terminal.

---

## 11. Collision findings

The generic-looking filenames and observed identity/trailer sets are not equally safe. Counts below are volatile indexed result sets, not unique repositories, installations, or adoption measurements.

| Candidate | Indexed result set | Decision |
|---|---:|---|
| `orca.yaml` | 689 | Content-gated. Samples include unrelated chemistry, robotics, data, and workflow configs, including many root files. |
| `t3.json` | 116,608 | Schema-gated. Filename search overmatches suffixes, and inspected exact root files still include unrelated uses. |
| `cubic.yaml` | 317 | Content-gated as a file. Samples mix real Cubic configs with unrelated scientific and Nix configs; the exact cubic bot email remains safe. |
| `.builderrules` | 86 | Safe. Sampled results overwhelmingly follow Builder's product contract. |
| `kodus-config.yml` | 39 | Safe. Sampled results are Kody configuration. |
| `.pr_agent.toml` | 867 | Real review-agent evidence, but ambiguous between Qodo and PR-Agent. |
| `.paperclip.yaml` | approximately 165 in the earlier result set | Require `schema: paperclip/v1` for file evidence. |
| `reasonix.toml` | 245 | No active rule regardless of collision count; the product is retired. |
| `agent@replit.com` | 7,717,308 exact-literal results; 1,418,075 `author-email:` results | Safe exact Replit Agent identity. Samples include primary author/committer use and `Co-authored-by: Replit Agent`; the totals are not an adoption census. |
| `Replit-Commit-Author: Agent` | 8,786,746; query reported `incomplete_results: true` | Strong Agent-checkpoint marker. Parse the custom token/value in schema v2 and keep `Deployment` as a negative value. |
| `agent@abacus.ai` | 2,079 `author-email:` results | Safe exact Abacus Agent identity. Samples span 2025-09-05 through 2026-11-13 and map to the `abacusai-agent` account. |
| `.abacusai/config.json` | 49 | Safe product configuration. It is optional and normally ignored when Agent creates it, but official docs permit committing it for team settings. |
| `.abacusai/skills/**/SKILL.md` | 18 | Safe product-namespaced project skills; `.agents/skills/**` remains shared and unsafe. |
| `194430910+abacus-ai-automation[bot]@users.noreply.github.com` | 70 `author-email:` results | Reject as coding-agent evidence. Samples are Abacus release/CI updates; classify as automation noise. |

### 11.1 Interpretation limits

- GitHub search totals drift with indexing and query behavior.
- A total returned with `incomplete_results: true` is retained as an indexed result-set observation, not a complete count.
- A result set can contain several files or commits from one repository.
- Forks, mirrors, fixtures, examples, and copied templates can all appear.
- Sampling was designed to find collisions, not estimate an unbiased false-positive rate.
- Search totals support detector-safety decisions; they do not measure market share.

### 11.2 Shared-file context

The earlier methodology audit also found very high result sets for shared formats, including `AGENTS.md`, `.agents/skills/**/SKILL.md`, `MEMORY.md`, `USER.md`, `IDENTITY.md`, and `SOUL.md`. Those files remain useful in conjunctions or as format evidence, never as singleton product attribution.

---

## 12. Mandatory frozen-pack hygiene

These corrections are required before adding any new family. They are recommendations only; this report does not edit the pack.

### 12.1 Remove unsupported or stale rules

1. Remove unsupported `CURSOR.md`.
2. Remove `openhands-agent` or scope it to dated historical evidence; it is unsafe as a current cross-channel author rule.
3. Remove OpenCode-v1-only `noreply@opencode.ai`, `opencode-agent`, and `opencode/` from current v2 attribution. Preserve them only as lifecycle-bounded v1 evidence.
4. Delete the duplicate `claudecode/` branch rule.

### 12.2 Fix names, whitespace, and orphan subtypes

5. Fix:
   - `AmazonQ` versus `Amazon Q`;
   - the leading-space Atlassian subtype;
   - orphan `Verd`;
   - duplicate/canonical product naming after merges and successors.
6. Resolve orphan active subtypes rather than silently dropping them:
   - add Kimi Code as a real tool row;
   - add Abacus AI Agent / Coding Agent as a real tool row;
   - retain `agent@abacus.ai` as exact Agent attribution;
   - remove `abacus-ai-automation[bot]` from Abacus authorship and preserve it as release/CI noise or rejected evidence.

### 12.3 Correct current product surfaces

7. Replace broad `.tessl/` as the primary Tessl rule with root `tessl.json`; add `.tessl-code-review.yml` and the exact cloud setup hook separately.
8. Replace broad identity rules such as `Claude`, `Copilot`, `cursor`, `cline`, `junie`, `Codex`, model names, `ChatGPT`, and `AI Assistant` with exact emails or explicitly scoped bot identities.
9. Add current product surfaces:
   - Qwen: `.qwen/**`
   - Kilo: `.kilo/**`; retain `.kilocode/**` as compatibility-scoped evidence
   - Brokk legacy: `.brokk/project.properties`, `.brokk/review.md`
   - Factory Droid: `.factory-plugin/plugin.json`
   - DeepSource: `.deepsource.toml`
   - CodeRabbit: `.coderabbit.yaml`
   - Microsoft Amplifier: `.amplifier/settings.yaml`

### 12.4 Replace unsafe Qodo and Sentry identities

10. Replace Qodo's repository-unsafe broad `.qodo/` rule with exact commit emails:

```regex
^189517486\+(?:qodo-free-for-open-source-projects|qodo-merge-for-open-source)\[bot\]@users\.noreply\.github\.com$
```

```regex
^151058649\+(?:qodo-code-review|qodo-merge-pro)\[bot\]@users\.noreply\.github\.com$
```

11. Replace broad Sentry Seer login matching with:

```regex
^157164994\+seer-by-sentry\[bot\]@users\.noreply\.github\.com$
```

### 12.5 Why exact commit emails matter

Forge participant records normally contain logins, not commit emails. Exact Git-generated noreply addresses therefore avoid turning ordinary PR review, issue comments, or app participation into authored-code evidence. The detector must still preserve the role and channel rather than flattening every identity hit into one meaning.

---

## 13. Required schema v2

A safe next schema needs more than additional regex arrays. It must represent where a signal appears, what conditions make it valid, what it proves, and whether it may influence authorship or adoption ratios.

### 13.1 Illustrative rule

```yaml
schema_version: 2

families:
  - id: t3-code
    name: T3 Code
    kind: orchestrator
    aliases: []
    predecessors: []

rules:
  - id: t3.project-config
    family: t3-code
    surface: file
    forge: any

    match:
      path:
        regex: '^t3\.json$'
        root: true
        case_sensitive: true
      content:
        format: json
        predicates:
          - json_path: '$.$schema'
            equals: 'https://t3.codes/schema/t3.json'

    semantics:
      evidence: configured
      attribution_role: orchestrator
      counts_as_authorship: false
      counts_in_commit_ratio: false

    lifecycle:
      status: current
      valid_from: '2026-01-01'
      valid_until: null

    default_state: normal
    confidence:
      class: strong
      collision_risk: low

    provenance:
      repository: pingdotgg/t3code
      commit: f313d0a6cb843551fb60e57a454a71e71a3a8c04
      path: t3.json
      checked_at: '2026-11-13'
```

### 13.2 Required matching capabilities

1. **Structured content predicates**
   - JSONPath
   - YAML paths
   - TOML keys
   - bounded text regex
   - exact schema URLs and versions

2. **Conjunctions and relationships**
   - `allOf`
   - `anyOf`
   - `minMatches`
   - same-stem files
   - same commit
   - same PR
   - same ref
   - same repository tree

3. **Path semantics**
   - explicit root anchoring
   - case sensitivity
   - file versus directory distinction
   - exact leaf versus descendant matching

4. **Trailer semantics**
   - custom trailer tokens such as `Herder-Session` and `Replit-Commit-Author`
   - structured token/value parsing
   - exact co-author name-plus-email conjunctions such as Abacus Agent plus `noreply@abacus.ai`
   - distinction between a trailer and an arbitrary message mention

5. **Hidden refs**
   - arbitrary ref namespaces
   - ref type and reachability
   - identity-plus-ref conjunctions
   - recovery/checkpoint classification

### 13.3 Required channel, role, and forge scope

Rules must distinguish at least:

- commit author;
- commit committer;
- co-author or other trailer identity;
- PR author;
- PR reviewer;
- PR commenter;
- issue author, assignee, or commenter;
- service account;
- generated workflow identity.

Forge scope must support:

- GitHub;
- GitLab;
- Bitbucket;
- Azure DevOps;
- local Git without a forge.

A rule valid for a Git commit email must not automatically match a GitHub commenter login, and GitHub bot normalization must not be projected onto GitLab service accounts.

### 13.4 Required lifecycle model

Each rule needs:

- status: `current`, `deprecated`, `legacy`, `retired`, `recovery-only`, or `anomalous`;
- `valid_from` and `valid_until` dates;
- optional product version bounds;
- successor/predecessor linkage;
- compatibility and migration notes.

Default state also needs an explicit enum:

- default-on;
- default-off;
- opt-in;
- configurable;
- recovery-only;
- normally ignored.

### 13.5 Required confidence and provenance

Confidence should record:

- evidence class: `strong`, `corroborating`, or `composite-only`;
- collision risk: low, medium, or high;
- whether global prevalence/collision sampling was performed;
- known undercount or false-positive hazards.

Provenance should record:

- canonical source URL;
- repository and pinned commit/version;
- source path;
- source type: implementation, official documentation, distributed package, or observed SCM activity;
- check date;
- optional query and sample record for collision tests.

### 13.6 Required semantic and rollup policy

Every rule must state the layer it identifies:

- executor;
- reviewer;
- orchestrator;
- host;
- framework;
- downstream agent.

Every hit must state what it proves:

- configured;
- activity observed;
- authorship;
- generated code;
- review participation;
- orchestration only;
- historical lineage;
- recovery/checkpoint activity.

It must also state whether it can affect:

- repository-level family presence;
- current-family presence;
- commit authorship;
- generated-code counts;
- the commit-adoption ratio;
- first/last signal dates.

An orchestrator config may establish repository-level Orca or T3 presence while setting both `counts_as_authorship: false` and `counts_in_commit_ratio: false`.

### 13.7 Required family lineage

The schema must support:

- aliases;
- rebrands;
- predecessors and successors;
- variants;
- compatibility surfaces;
- rollup family IDs.

This prevents Qoder/Lingma, Shelley/Sketch, Zoo/Roo, Devin/Windsurf, Abacus AI Agent/DeepAgent, and DSH/dsh-superagent from inflating family counts.

---

## 14. Required collector changes

Schema support alone is not sufficient. The detector must collect the evidence the schema describes.

1. **Targeted file-content fetching**
   - fetch only candidate paths;
   - cap bytes and parse by declared format;
   - record fetch failures separately from predicate failures;
   - avoid downloading arbitrary repository contents.

2. **PR and issue comment bodies**
   - collect bounded bodies for product commands;
   - preserve commenter identity and authorization context;
   - distinguish invocation from participation.

3. **Structured trailer parsing**
   - parse token/value lines;
   - retain token spelling and message location;
   - retain co-author name and email as separate matchable fields;
   - distinguish co-author identities from custom session IDs;
   - preserve product-defined value semantics such as Replit `Agent` versus `Deployment`.

4. **Hidden-ref enumeration**
   - query configured namespaces rather than every object;
   - preserve ref name and commit reachability;
   - support ref-scoped synthetic identities.

5. **GitLab-native activity**
   - branches, merge requests, notes, reviewers, and service accounts;
   - no projection through GitHub-only bot conventions.

6. **Separate identities and roles**
   - author, committer, co-author, PR author, reviewer, commenter, assignee, and service account must remain separate fields.

7. **Conjunction evaluation**
   - same-stem workflow source/lock files;
   - same-tree workspace bundles;
   - same-ref identity rules;
   - path-plus-content predicates.

8. **Evidence and metric separation**
   - repository presence, configuration, activity, authorship, and commit-ratio evidence must be separate rollups.

---

## 15. Provenance and preserved audit pins

The following pins were captured during the 2026-11-13 re-audit. A pin establishes the snapshot inspected; it does not imply that stars, forks, or popularity were used as acceptance evidence.

| Product | Canonical repository | Preserved pin |
|---|---|---|
| Paperclip | `paperclipai/paperclip` | `5c5a2fcebef7d6e270192976df00993b56cb8fc7` |
| Hermes Agent | `NousResearch/hermes-agent` | `5c1abd257d0cc1b531ffee6e50bef0621aa49dc4` |
| Command Code | `CommandCodeAI/command-code` | `6bdb1ed1c3ebd1a0e4dfdda3efc8c6a1f63b734f` |
| Oh My Pi | `can1357/oh-my-pi` | `6e374adc76aeed920c5f3ff2674d1c9e3002bcbd` |
| OpenClaw | `openclaw/openclaw` | `a48a3175600e3cad5554128a4cf0012c4e65d9ad` |
| Claw Code | `ultraworkers/claw-code` | `508b4d862d42a5fa5bde8df5b2d3670f4d4ca324` |
| DeepSeek Reasonix | `esengine/DeepSeek-Reasonix` | `cd20bb50be3b1eac5fad0648373a158c35767ae4` |
| Grok Build | `xai-org/grok-build` | `2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8` |
| Prime Agent | `PrimeIntellect-ai/prime-agent` | `01eb3ce111bf2eda83f7efe77c126410db2c6988` |
| JCode | `1jehuang/jcode` | `d75274706baaffa7c4510370f62ebeae1e661e3f` |
| Xiaomi MiMo Code | `XiaomiMiMo/MiMo-Code` | `5a538cb4f97b9c4c8eb09a845ec06c1e5f1f3e8f` |
| Freebuff / Codebuff | `CodebuffAI/codebuff` | `876cbeca158447ce4da8c4bd01a77fdf7aa0dcc9` |
| OpenCodeReview | `alibaba/open-code-review` | `0e9060da66af36a96a15516e76a001953095318b` |
| PR-Agent | `qodo-ai/pr-agent` / `The-PR-Agent/pr-agent` | `af82fe26731ef704abea0762eb5f091fb1c77bed` |
| Orca | `stablyai/orca` | `1af96e86ff80e4de6216cc4fb04dc41a98472f0b` |
| T3 Code | `pingdotgg/t3code` | `f313d0a6cb843551fb60e57a454a71e71a3a8c04` |
| oh-my-claudecode | `Yeachan-Heo/oh-my-claudecode` | `dec7e4188c0e3de6b92fb3d734ee5c95326021ed` |
| Archon | `coleam00/Archon` | `68338422b93ecf96b538dd283fb3aa1703c9bb48` |
| ralph | `snarktank/ralph` | `6c53cb0b831ebe8739c6a003e22af14902d8b0b5` |
| Docker Agent | `docker/docker-agent` | `2cdfde2951bef18205802f0f4e91532809385f80` |
| GitHub Agentic Workflows | `github/gh-aw` | `ee96cdb3b0a9e7182ecebb74af6511c3680526c8` |
| Kody AI | `kodustech/kodus-ai` | `9b69a3257b7b50773bbf06f104e585ace3906d60` |
| DeepSeek Harness | `deepseek-ai/deepseek-harness` | `39163dd30f703a79079e2d2446545cff3c453738` |
| dsh-superagent prototype | `deepseek-ai/dsh-superagent-prototype` | `8c32a9dc5d72c033816c6a8110b37f40cf94fba4` |
| Gajae-Code | `Yeachan-Heo/gajae-code` | `b4127889c4a849133f868cbf8f4d5a65126baec4` |
| LazyCodex | `code-yeongyu/lazycodex` | `0d015b03c5cf664ee76bcf81187cbac795e9aa69` |
| Herder | `herder-sh/herder` | `1a5429431a68` |
| Abacus AI Agent public docs/issues | `abacusai/abacusai-desktop` | `62b5a192122e575351b679bcf4d03fdc1c92cc05` |

Additional official-source checks covered Builder.io Fusion, cubic, Greptile, Lovable, Kimi Code CLI, Roomote, Replit Agent, Abacus AI Agent / Coding Agent, successor product documentation, exact Git identities, and lifecycle announcements. When no canonical source repository exposed a stable implementation pin, the audit required an official product contract or observed product-controlled SCM identity rather than a secondary popularity claim.

### 15.1 Replit Agent contract and observed SCM samples

Replit Agent has no public canonical implementation repository to pin, so its classification combines official product contracts with preserved public Git observations:

- [Official `replit.md` documentation](https://docs.replit.com/features/project-setup/replit-dot-md.md) states that Agent automatically creates the file at the project root, reads it as project context, and can update it.
- [Official version-control documentation](https://docs.replit.com/learn/projects-and-artifacts/version-control.md) and [checkpoint documentation](https://docs.replit.com/features/version-control/checkpoints-and-rollbacks.md) state that Agent checkpoints create corresponding Git commits and can synchronize through GitHub.
- [Official repository-contribution documentation](https://docs.replit.com/build/code/working-with-code.md) states that Agent can create a contribution branch, commit and push changes, and open a pull request. [Identity documentation](https://docs.replit.com/build/code/machine-identities.md) clarifies that interactive work uses the user's authorized forge account, so that account alone is not Replit Agent attribution.
- [`utkarshyadav3436-afk/deepfake-detector@1de22a6979a3e7a7598542200aa25a2a6c1b2214`](https://github.com/utkarshyadav3436-afk/deepfake-detector/commit/1de22a6979a3e7a7598542200aa25a2a6c1b2214) preserves `agent <agent@replit.com>` as author and committer, mapped by GitHub to the [`replit-agent`](https://github.com/replit-agent) account whose public profile names Replit as the company.
- [`Sarbansah07/newsmania@f0c4e06e8c5aa0ff490b553725065528934499d3`](https://github.com/Sarbansah07/newsmania/commit/f0c4e06e8c5aa0ff490b553725065528934499d3) preserves `Replit-Commit-Author: Agent` together with a Replit session ID and checkpoint type under a per-user Replit Git identity.
- [`pkonkle213/MetagameTrackerBot@f5de1e655b3cbe50a22bd8e32234efbf35ee836a`](https://github.com/pkonkle213/MetagameTrackerBot/commit/f5de1e655b3cbe50a22bd8e32234efbf35ee836a) preserves repeated Agent markers plus `Co-authored-by: Replit Agent <agent@replit.com>` after GitHub squash/merge.
- [`CheickDiakite-yikes/my-ai-companion@a82c7587e8fecef0bc48d9602516911dfad9b719`](https://github.com/CheickDiakite-yikes/my-ai-companion/commit/a82c7587e8fecef0bc48d9602516911dfad9b719) is the negative control: it uses the same surrounding Replit checkpoint fields but says `Replit-Commit-Author: Deployment` and includes a deployment build ID.

The retained GitHub queries, checked 2026-11-13, were:

| Query | `total_count` | `incomplete_results` | Use |
|---|---:|---|---|
| `"agent@replit.com"` | 7,717,308 | `false` | Occurrence and sample discovery across primary and co-author forms. |
| `author-email:agent@replit.com` | 1,418,075 | `false` | Confirms extensive primary-author use rather than trailer-only occurrence. |
| `"Replit-Commit-Author: Agent"` | 8,786,746 | `true` | Occurrence and cross-repository sample discovery only; not a complete count. |

These totals are volatile indexed result sets, not unique commits, repositories, users, or adoption estimates. Acceptance rests on the official file/checkpoint contracts and exact product-controlled identity/metadata, not on the size of the totals.

### 15.2 Abacus AI Agent contract and fingerprint audit

The current coding-agent implementation is closed source, so the audit combined official documentation, the public product repository, the distributed CLI package/binary, and public Git activity:

- [Official product documentation](https://abacus.ai/coding-agent/faq) identifies one coding-agent product across Code Mode, the `abacusai` CLI, and the VS Code extension. [The public product repository](https://github.com/abacusai/abacusai-desktop) says the same and explicitly notes that implementation source is not public.
- Official settings, MCP, skills, and hooks documentation establishes the `.abacusai/**` project paths in §7.25. Official CLI documentation says checkpoints live under `~/.abacusai/checkpoints`, outside the project, and never write the target repository's `.git`.
- `@abacus-ai/cli@2.10.18`, published 2026-11-12, was the stable package inspected. The npm tarball SHA-256 was `9abe4dd6901aa23a492ff01d7525a07f735d3d8bbaa0f98ce949c2c4e9741c8`; the distributed Windows x64 binary SHA-256 was `136ec35a38e59402884109f0f1da507be7637405bc21dea4d4bc26e0f86d6054`.
- The current binary contains an explicit instruction never to set, guess, or invent `git config user.name` or `user.email` when they are absent. It contains no `agent@abacus.ai`, `noreply@abacus.ai`, or Abacus co-author literal. Therefore the exact public identity is a verified cloud/hosted Agent signal but is not universal local-CLI behavior.
- The binary's `Abacus Checkpoint <checkpoint@abacus.ai>` and `refs/abacus/**` strings belong to the external checkpoint store described by the docs. They are not target-repository evidence and must not be deployed as ordinary author/ref rules.
- [The March 2026 platform update](https://abacus.ai/help/platform-updates/2026-03-01-platform-update) states that DeepAgent became Abacus AI Agent. Historical `DeepAgent <agent@abacus.ai>` and current Abacus names therefore roll up to one family.

Preserved public SCM samples:

- [`christiangallon/azure-01-secure-webapp@3a782025b146032ee9bfc8d7ef1d4efe3f0025ab`](https://github.com/christiangallon/azure-01-secure-webapp/commit/3a782025b146032ee9bfc8d7ef1d4efe3f0025ab) is a current primary-author sample: `Abacus AI Agent <agent@abacus.ai>`, mapped by GitHub to `abacusai-agent`.
- [`Tahagher/loyalty-@b32dd16ec9ffb47cc858570bc8b422782fcd177b`](https://github.com/Tahagher/loyalty-/commit/b32dd16ec9ffb47cc858570bc8b422782fcd177b) contains both `.abacusai/config.json` and `Co-Authored-By: Abacus.AI CLI <agent@abacus.ai>`.
- [`MokshaOne/WP-THEME@11157684fc10e1e9f463956a4a0b66abbdd4298a`](https://github.com/MokshaOne/WP-THEME/commit/11157684fc10e1e9f463956a4a0b66abbdd4298a) preserves the current composite form `Co-Authored-By: Abacus AI Agent <noreply@abacus.ai>`.
- [`abacusai/deepagent-releases@913af44beadb9be53e85b97b8f95a7a0202c33dd`](https://github.com/abacusai/deepagent-releases/commit/913af44beadb9be53e85b97b8f95a7a0202c33dd) is the control for `abacus-ai-automation[bot]`: its subject and changed files are CI release-manifest updates, not coding-agent work. The same GitHub App currently publishes AbacusAI Bot release assets.

Retained queries, checked 2026-11-14:

| Query | `total_count` | `incomplete_results` | Decision |
|---|---:|---|---|
| `author-email:agent@abacus.ai` | 2,079 | `false` | Strong current Agent identity; earliest sorted sample was 2025-09-05 and current samples reach 2026-11-13. |
| `filename:config.json path:.abacusai` | 49 | `false` | Strong project configuration; sampled files contain documented Abacus permission settings. |
| `filename:SKILL.md path:.abacusai/skills` | 18 | `false` | Strong Abacus-namespaced project skills. |
| `filename:mcp.json path:.abacusai` | 0 | `false` | Official current contract, no indexed public sample retained. |
| `path:.abacusai/hooks` | 0 | `false` | Official current contract, no indexed public sample retained. |
| `author-email:194430910+abacus-ai-automation[bot]@users.noreply.github.com` | 70 | `false` | Release/CI automation; reject as coding-agent attribution. |
| `author-email:noreply@abacus.ai` | 2 | `false` | Too broad alone; retain only with exact Agent name/role corroboration. |

The audit decision is therefore asymmetric: keep and tighten `agent@abacus.ai`; remove the automation bot from Abacus authorship; add exact `.abacusai/**` project surfaces; and retain `noreply@abacus.ai` only as composite evidence. Abacus is a current-schema-safe active family, not stale, watch, adjacent, or excluded.

### 15.3 Important source corrections

- The live Freebuff product repository remains `CodebuffAI/codebuff`; an earlier `CodebuffAI/freebuff` reference was not a valid source location.
- Kimi Code CLI is `MoonshotAI/kimi-code`; archived `MoonshotAI/kimi-cli` is predecessor lineage.
- Grok Build's supported project surfaces are the current `.grok` files and subtrees in §7.15, not community `.grok/settings.json`.
- `dsh-superagent` is a DeepSeek Harness variant.
- Roo Code and Zoo Code must be treated as a successor lineage, not unrelated products merely because the canonical repository changed.

---

## 16. Implementation order

### Pack snapshot and preservation contract

The Phase 1 pack is a **complete immutable, lifecycle-aware snapshot**, not a delta layered on top of an earlier pack. Implementation may use the frozen baseline as input, but detection loads one selected pack at a time and performs no runtime inheritance or parent-pack merge.

Required artifact policy:

1. Preserve `packs/2026-10-14.json` and `packs/2026-10-19.json` byte-for-byte. Never overwrite, rename, regenerate in place, or freeze different content under either existing version.
2. Update the canonical CSV inputs under `packs/patterns/` for the normalized catalogue, retaining every verified historical fingerprint with lifecycle metadata.
3. Extend pattern serialization before the build so each rule can carry at least `status`, `valid_from`, `valid_until`, `rollup_family`, `observed_as`, `counts_as_current_presence`, `counts_as_authorship`, and `counts_in_current_ratio`. Old packs without these fields must remain loadable.
4. Build a new `packs/2026-11-14.json` with pack version `2026-11-14` through `python -m detect.packs build`.
5. Treat the new file as a full replayable snapshot: it must contain every verified current and historical rule intended for the catalogue, even when that rule is unchanged from the baseline.
6. Keep existing detection runs bound to their original frozen pack version. Freezing the new version adds another selectable pack; it must not migrate or reinterpret old evidence.
7. Verify the two preserved pack digests are unchanged and that rebuilding the new pack from the same CSV inputs produces the same digest.

Build command on the repository's Windows development environment:

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m detect.packs build `
  --src packs\patterns `
  --version 2026-11-14 `
  --out packs\2026-11-14.json
```

The new snapshot deliberately combines four operations:

- **retain** source-verified current rules that remain safe;
- **remap and deduplicate** aliases, successors, and variants into their canonical family;
- **replace** broad or stale rules with the exact rules in this report;
- **add** the 25 current-schema-safe families from §7.

No verified historical fingerprint is deleted merely because the current product stopped emitting it. Instead, the new pack keeps the rule and changes its semantics:

- **current** rules can establish current family presence and, where appropriate, authorship;
- **deprecated** rules remain supported but are no longer preferred;
- **legacy** or **retired** rules establish historical lineage and can attribute a dated commit when the commit falls inside the rule's validity interval, but they do not establish current use;
- **compatibility** rules roll up to the successor family while retaining `observed_as` lineage;
- current-tree occurrences of an expired file rule report **legacy marker present; current use unknown** rather than current adoption.

Rules may be absent from active matching only when the audit establishes that they were never reliable product fingerprints. Unsupported `CURSOR.md`, broad user/model names, broad `.qodo/`, unscoped reviewer/release bots such as `openhands-agent` and `abacus-ai-automation[bot]`, and similar false-attribution hazards remain in a rejection ledger with their reason; they are not preserved as positive historical detections. Exact duplicate rows are deduplicated because that loses no evidence.

Examples of retained history include OpenCode-v1 identities, `.lingma/**`, `hello@sketch.dev`, pre-transition Amazon Q CLI evidence, and retired standalone product fingerprints. Current compatibility is remapped rather than discarded: `.roo/**` rolls up under Zoo Code and Windsurf-compatible surfaces roll up under Devin / Devin Desktop.

The expected Phase 1 catalogue is exactly **72 active canonical families**, with `Generic` retained separately as the shared-format pseudo-family and verified legacy families/rules retained with zero current-family weight. Pack rule count, lifetime family coverage, and active-family count are different metrics. Watch, adjacent, excluded, schema-v2-gated, and negative-control entries remain documented; only rules with verified evidence belong in `packs/2026-11-14.json`.

### Phase 0 — hygiene before expansion

Apply all 11 hygiene groups in §12, implement the minimum lifecycle fields required by the preservation contract, and test exact identity rules against PR/issue participation as well as commit history.

### Phase 1 — current-schema-safe pack

1. Normalize the 63 labels to the 47 active incumbent rows.
2. Keep 3 incumbent watch, 4 incumbent legacy-only, 4 adjacent, and Generic outside the active denominator.
3. Add the 25 safe families from §7.
4. Set optional/recovery rules in §7.26 disabled by default.
5. Verify the resulting active count is exactly 72 while verified legacy rules remain present with zero current weight.

### Phase 2 — schema and collector v2

Implement §13 and §14, including content predicates, conjunctions, custom trailers, hidden refs, forge scope, role scope, lifecycle, provenance, and rollup semantics.

### Phase 3 — gated-family activation

Activate GitLab Duo, Orca, T3 Code, GitHub Agentic Workflows, PR-Agent, and Herder only after their composite rules can be represented and tested. Verify the active count then becomes exactly 78.

### Phase 4 — replay and false-positive review

- replay against a labeled repository corpus;
- sample each exact email outside its source repository;
- sample every generic-looking path across unrelated owners and ecosystems;
- test bot participation without authored commits;
- test lifecycle boundaries around rebrands and retirements;
- ensure orchestrator-only hits do not alter commit-adoption ratios;
- retain query timestamps, result totals, `incomplete_results`, and inspected sample selection.

---

## 17. Final recommendation

The previous 90-family proposal is not a safe pack plan. The final recommendation is:

> Maintain a **78-active-family catalogue**, ship **72 current-schema-safe families now**, and hold **6 real but composite families** until schema v2 and collector support exist.

Preserve dated historical evidence for the six legacy-only families and lifecycle aliases. Keep the 12 adjacent layers in separate inventories. Retain `Generic` only as shared-format classification and Ghostty as a negative control. Most importantly, preserve attribution boundaries: review participation is not authorship, configuration is not necessarily execution, and a wrapper never inherits the commits of the downstream agent it launches.

---

## Appendix A. Local baseline and pattern references

- [`packs/2026-10-19.json`](../../packs/2026-10-19.json) — frozen 63-label baseline.
- [`packs/patterns/tools.csv`](../../packs/patterns/tools.csv) — baseline names and URLs.
- [`packs/patterns/authors.csv`](../../packs/patterns/authors.csv) — current author patterns and broad-identity hygiene targets.
- [`packs/patterns/files.csv`](../../packs/patterns/files.csv) — current file rules.
- [`packs/patterns/branches.csv`](../../packs/patterns/branches.csv) — current branch rules, including the duplicate Claude Code entry.
- [`packs/patterns/labels.csv`](../../packs/patterns/labels.csv) — current label rules.
- [`packs/patterns/bots.csv`](../../packs/patterns/bots.csv) — generic bot exclusions.

## Appendix B. Related research

- [`2026-11-08-agent-fingerprint-methodology.md`](2026-11-08-agent-fingerprint-methodology.md) — source hierarchy, evidence classes, current matcher semantics, query limitations, and reproducibility procedure.
- [`2026-11-08-agent-fingerprint-research.md`](2026-11-08-agent-fingerprint-research.md) — pinned source audits for Orca, DeepSeek Harness, Paperclip, Herdr, Herder, Hermes, Command Code, Cursor, Ghostty, OpenCode, Pi, Oh My Pi, OpenClaw, Claw Code, Mistral Vibe, and OpenHands.
- [`2026-11-08-agent-fingerprint-landscape.md`](2026-11-08-agent-fingerprint-landscape.md) — broader product landscape.
- [`2026-11-08-agent-fingerprint-landscape-candidates.csv`](2026-11-08-agent-fingerprint-landscape-candidates.csv) — candidate/source ledger.
- [`2026-11-09-agent-inventory-final-decision.md`](2026-11-09-agent-inventory-final-decision.md) — the earlier 27-add / 3-watch decision that this re-audit revises.
- [`docs/agent-pack-63-and-90.md`](../agent-pack-63-and-90.md) — provisional inventory superseded by this report.

## Appendix C. Compact decision ledger

```text
SHIP NOW (72)
  47 normalized active incumbents
  25 safe additions (including Replit Agent and Abacus AI Agent / Coding Agent)

HOLD FOR SCHEMA V2 (6)
  GitLab Duo Agent Platform
  Orca
  T3 Code
  GitHub Agentic Workflows
  PR-Agent
  Herder

WATCH (5)
  ChatGPT
  Azad
  Zed Agent
  Herdr
  claude-flow / Ruflo

LEGACY-ONLY (6)
  Brokk
  Continue
  GPT-Engineer
  Sweep
  Claw Code
  DeepSeek Reasonix

ADJACENT (12)
  Taskmaster
  SpecKit
  Serena
  Rulesync
  Azure SRE Agent
  BMAD-METHOD
  OpenSpec
  Ruler
  LangGraph
  snarktank/ralph
  GitAI / Graft
  Odysseus

EXCLUDED (4)
  LazyCodex
  Dori superagent
  Aperant
  Odysseus Workshop

FOLDED VARIANT (1)
  dsh-superagent -> DeepSeek Harness

PSEUDO-FAMILY (1)
  Generic

NEGATIVE CONTROL (1)
  Ghostty
```
