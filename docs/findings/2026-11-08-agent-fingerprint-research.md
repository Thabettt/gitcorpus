# Repository-Visible Agent Fingerprints — Research Findings

**Generated:** 2026-11-08T22:21:23+02:00  
**Repository HEAD:** `4f2ba85252ab1ea483f9c96c7e4da752b04385ad`  
**Research date:** 2026-11-08  
**Scope:** repository-visible fingerprints only; documentation and detector recommendations, not detector implementation  
**Companion methodology:** [2026-11-08-agent-fingerprint-methodology.md](./2026-11-08-agent-fingerprint-methodology.md)

---

## 1. How to Read This Report

A **fingerprint** is an observable repository artifact that may indicate that a product was configured, executed, or involved in repository activity. Fingerprints include committed files, Git author or committer identities, commit trailers, branches, hidden refs, pull-request body text, labels, bots, and issue-comment commands.

The **channel** says where the evidence appears. This matters because identical text can mean different things in different channels. For example, `openclaw@localhost` on an internal synthetic snapshot ref is not equivalent to the same email in ordinary branch history, and a bot commenting on a pull request is not proof that the bot authored the code.

The **evidence class** is a recommendation about how much weight to give the signal:

- **strong** — sufficiently product-specific to stand alone in its intended channel;
- **corroborating** — useful support, but not normally enough by itself;
- **composite-only** — reliable only as a conjunction with another path, content marker, ref namespace, or activity condition;
- **legacy** — verified historical behavior that should not be presented as a current default;
- **optional** — real current behavior, but disabled by default, configurable, or limited to a non-default mode;
- **anomalous** — associated with the product but abnormal in the observed channel, such as normally ignored local state committed to Git;
- **unsafe** — too generic, user-controlled, cross-tool, downstream-inherited, or otherwise collision-prone for standalone attribution.

The **collision risk** is not a measure of whether a string is real. It is the chance that matching it would attribute an unrelated repository or the wrong layer of a tool chain. “Low” means the literal and channel are product-specific. “High” means the same artifact is common across tools, configurable by users, or inherited from a downstream agent.

The **encodable** column evaluates the frozen pack model used at repository HEAD. “Yes” means the signal can be represented using the current `authors`, `files`, `branches`, `labels`, or `bots` patterns. It does not mean that adding it is necessarily wise. “No” identifies a schema or collection gap, such as file-content conjunctions, custom trailer tokens, arbitrary hidden refs, PR footers, comment bodies, or signature verification.

### 1.1 Prevalence numbers

Every retained count is attached to its observed result-set size. These are volatile index totals, not estimates of unique repositories and not adoption rates. Exact-email and exact-message searches can contain several matches from one repository or commit. GitHub search totals can change as the index changes, can report `incomplete_results`, and expose at most a capped result window for inspection even when `total_count` is much larger. “Source-only; n=1” means the behavior was verified in one pinned canonical implementation but no global prevalence query was retained.

---

## 2. Executive Findings

1. Current, high-precision standalone evidence is concentrated in exact product configuration paths and exact commit-attribution emails. Branches are useful only when the product owns a constrained namespace.
2. Shared surfaces — especially `AGENTS.md`, `.agents/skills/`, `.worktreeinclude`, `SOUL.md`, `MEMORY.md`, and `USER.md` — are not standalone product evidence. Their global prevalence is too high.
3. Wrapper, orchestrator, and terminal products must be separated from the agents they launch. Ghostty has no native repository attribution; Herdr has almost none; Orca and OpenClaw expose orchestration state that must not be confused with downstream authorship.
4. Current and historical implementations often disagree. OpenCode v2 does not inherit OpenCode v1 attribution. Orca’s exact trailer is retired. `.vibe/tools/` and `.openhands/microagents/` are retired/deprecated. `.cursorrules` remains legacy.
5. The current pack schema cannot express several of the best signals: content conjunctions, custom trailer names, hidden refs, exact PR footers, verified signatures, comment commands, or bot-safe activity.
6. Author patterns are reused across commits, PR authors, and issue participants. That creates a concrete false-adoption path for identities such as `cursor[bot]` and historical reviewer accounts such as `openhands-agent`.

---

## 3. Orca

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| Root-anchored `orca.yaml` | file | strong | current, checked-in project configuration | Source audit only; n=1 pinned upstream snapshot; no global count retained | Low — product-specific name and required root location | Yes — use an explicitly anchored file regex | [`docs/site/content/docs/model/orca-yaml.mdx`](https://github.com/stablyai/orca/blob/492ccce634795c6c36a448c652054e1a52adbee1/docs/site/content/docs/model/orca-yaml.mdx) |
| Committed `.orca/issue-command` | file | anomalous | current local override; intended to be ignored | 0 committed path matches; n=0 global path-query matches | Low lexical collision, but commitment is abnormal | Yes mechanically; it should not count as normal adoption | [`orca-yaml.mdx`](https://github.com/stablyai/orca/blob/492ccce634795c6c36a448c652054e1a52adbee1/docs/site/content/docs/model/orca-yaml.mdx) |
| `.worktreeinclude` | file | unsafe | shared worktree convention | 1,474 indexed path matches; n=1,474 | High — shared by Orca, Hermes, OpenClaw, and other worktree tooling | Yes mechanically; no as Orca attribution | [`docs/site/content/docs/model/worktrees.mdx`](https://github.com/stablyai/orca/blob/492ccce634795c6c36a448c652054e1a52adbee1/docs/site/content/docs/model/worktrees.mdx) |
| `Co-authored-by: Orca <help@stably.ai>` | trailer | legacy | retired Orca attribution | 126,632 indexed exact-email message matches; n=126,632; `author-email:help@stably.ai` returned exactly `0` | Low — exact product-controlled email, but retired | Yes through an author-email pattern; schema cannot mark it legacy | [Pinned Orca source/history](https://github.com/stablyai/orca/tree/492ccce634795c6c36a448c652054e1a52adbee1) |
| Issue-derived or user-selected worktree branch names | branch | unsafe | current orchestration input, not native attribution | Source audit only; n=1 | High — names can originate in GitHub, GitLab, Linear, or the user | No useful stable regex exists | [`docs/site/content/docs/review/github.mdx`](https://github.com/stablyai/orca/blob/492ccce634795c6c36a448c652054e1a52adbee1/docs/site/content/docs/review/github.mdx) |

**Trust:** root `orca.yaml`. Preserve the exact Orca trailer only as dated legacy evidence. **Ignore:** `.worktreeinclude`, work-item branch names, and downstream-agent fingerprints as Orca evidence. **Highest-risk signal:** generic worktree or issue-derived branch inference. The frozen pack has no Orca coverage.

---

## 4. DeepSeek Harness

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| `.agents/worktrees/dsh-<8hex>-<4hex>`; fallback `dsh-<8hex>` when no session UUID exists | file | anomalous | experimental worktree allocation; normally ignored | Source-only; n=1 upstream implementation; the pool receives a generated `*` ignore rule when created | Medium — distinctive generated leaf, but committed presence is abnormal | Yes as a path regex, but not as normal durable adoption | [`packages/experimental/worktree/README.md`](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/experimental/worktree/README.md) |
| `dsh-<8hex>-<4hex>` or `dsh-<8hex>` generated branch | branch | optional | experimental worktree tool; default-disabled | Source-only; n=1 | Medium — exact shape is distinctive, but caller-supplied names are also supported | Yes for the generated shape; exclude caller-supplied branches | [`packages/experimental/worktree/src/name.ts`](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/experimental/worktree/src/name.ts) |
| Exact `powered_by-dsh` Shields.io badge linked to `https://github.com/deepseek-ai/deepseek-harness` | file / PR footer | optional | bundled badge skill; default-off | Source-only; n=1 bundled badge implementation | Low when image URL and destination are matched together | No — requires exact content or PR-body matching | [`packages/experimental/skill-badge/assets/dsh-badge.md`](https://github.com/deepseek-ai/deepseek-harness/blob/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159/packages/experimental/skill-badge/assets/dsh-badge.md) |
| Generic `.agents/`, `.agents/skills/`, or `AGENTS.md` surfaces | file | unsafe | shared standards / contributor guidance | `.agents/skills/**/SKILL.md`: 496,640 indexed matches; n=496,640. `AGENTS.md`: 1,196,032; n=1,196,032 | High — cross-tool standards, not DSH ownership | Yes mechanically; no as product attribution | [Pinned DeepSeek Harness source](https://github.com/deepseek-ai/deepseek-harness/tree/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159) |
| Native author, committer, trailer, label, bot, or issue trigger | author email / committer / trailer / label / bot / issue trigger | unsafe | none found | None found; n=1 complete pinned-source audit | High if inferred from a downstream model or shared file | No stable native fingerprint exists | [Pinned source](https://github.com/deepseek-ai/deepseek-harness/tree/fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159) |

**Trust:** the exact generated branch shape as optional evidence and the complete badge content as low-collision opt-in evidence. **Ignore:** shared `.agents` surfaces and caller-selected branches. **Highest-risk signal:** broad `.agents/` attribution. The frozen pack has no DeepSeek Harness coverage.

---

## 5. Paperclip

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| Root `.paperclip.yaml` containing `schema: paperclip/v1` | file | composite-only | current canonical sidecar | 165 indexed `.paperclip.yaml` path matches; n=165 | Low for the conjunction; path alone is weaker | No — current schema cannot require path plus file content | [`docs/companies/companies-spec.md`](https://github.com/paperclipai/paperclip/blob/0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2/docs/companies/companies-spec.md) |
| `.paperclip.yml` containing `schema: paperclip/v1` | file | corroborating | current compatibility input | Source-only; n=1 implementation; no separate prevalence count | Low with content; less canonical than `.yaml` | No for the conjunction; yes for path alone | [`server/src/services/company-portability.ts`](https://github.com/paperclipai/paperclip/blob/0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2/server/src/services/company-portability.ts) |
| `Paperclip <noreply@paperclip.ing>` as fallback author and committer | author email / committer | strong | current fallback Git identity | 461,628 indexed exact-email identity/message matches; n=461,628 | Low — exact product domain and name | Yes, though author and committer cannot be scoped separately | [`doc/execution-github-identity.md`](https://github.com/paperclipai/paperclip/blob/0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2/doc/execution-github-identity.md) |
| `Co-Authored-By: Paperclip <noreply@paperclip.ing>` | trailer | strong | current required prompt instruction | Included in the 461,628 exact-email result universe; n=461,628 | Low — exact required trailer | Yes through exact email matching | [`skills/paperclip/SKILL.md`](https://github.com/paperclipai/paperclip/blob/0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2/skills/paperclip/SKILL.md) |
| `paperclip/rescue/<identifier>/<UTC timestamp>` | branch | optional | recovery-only | Source-only; n=1 recovery implementation | Low lexical collision, but it proves recovery rather than ordinary execution | Yes as an anchored regex; retain recovery-only status | [`server/src/services/workspace-runtime.ts`](https://github.com/paperclipai/paperclip/blob/0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2/server/src/services/workspace-runtime.ts) |
| Ordinary issue-derived branch names | branch | unsafe | user/issue-derived | Source-only; n=1 | High — arbitrary issue data and SCM naming conventions | No stable product namespace | [Pinned Paperclip source](https://github.com/paperclipai/paperclip/tree/0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2) |

**Trust:** the exact email/trailer and the `.paperclip.yaml` plus schema conjunction. Treat rescue branches as recovery-only. **Ignore:** ordinary issue branches. **Highest-risk signal:** path-only matching without schema content. The frozen pack has no Paperclip coverage.

---

## 6. Herdr (`herdrdev/herdr`)

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| Omitted branch generates `worktree/<adjective>-<noun>-<4hex>` | branch | corroborating | current default generation | Source-only; n=1 pinned implementation | Medium — full shape helps, but `worktree/` is generic | Yes as a fully anchored shape regex | [`src/worktree.rs`](https://github.com/herdrdev/herdr/blob/ee5bfb5041bb3e4a49d591c72308aae3c81ecdde/src/worktree.rs) |
| Bare `worktree/` prefix | branch | unsafe | generic worktree namespace | Source-only; n=1 | High — examples, APIs, and unrelated tools use it | Yes mechanically; should not be deployed | [`docs/next/website/src/content/docs/socket-api.mdx`](https://github.com/herdrdev/herdr/blob/ee5bfb5041bb3e4a49d591c72308aae3c81ecdde/docs/next/website/src/content/docs/socket-api.mdx) |
| Caller-supplied branch | branch | unsafe | current arbitrary input | Source-only; n=1 | High — arbitrary user input | No stable pattern exists | [`docs/next/website/src/content/docs/cli-reference.mdx`](https://github.com/herdrdev/herdr/blob/ee5bfb5041bb3e4a49d591c72308aae3c81ecdde/docs/next/website/src/content/docs/cli-reference.mdx) |
| Native files, Git identity, trailer, footer, label, bot, or issue trigger | file / author email / committer / trailer / PR footer / label / bot / issue trigger | unsafe | none found | None found; n=1 complete pinned-source audit | High if inferred from an agent Herdr launches | No native fingerprint exists | [Pinned Herdr source](https://github.com/herdrdev/herdr/tree/ee5bfb5041bb3e4a49d591c72308aae3c81ecdde) |

**Trust:** only the complete adjective–noun–hex shape, and only as corroboration. **Ignore:** the bare `worktree/` namespace and downstream-agent attribution. **Highest-risk signal:** `worktree/`. The frozen pack has no Herdr coverage.

---

## 7. Herder (`herder-sh/herder`)

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| Default `herder/<last-8-session-ULID-chars>` | branch | strong | current default | Source-only; n=1 pinned implementation | Low–medium — product namespace plus constrained session suffix; explicit branches remain possible | Yes as an anchored branch regex | [`crates/herder-daemon/src/worktree/mod.rs`](https://github.com/herder-sh/herder/blob/701a5b527d486863442b9a3de218e6c02af0e2a4/crates/herder-daemon/src/worktree/mod.rs) |
| `Herder-Session: <session-id>` | trailer | strong | current Git hooks | Source-only; n=1 implementation and hook tests | Low — custom product-specific trailer token | No — no trailer-token-specific channel; an author pattern would contaminate identities and activity | [`crates/herder-daemon/src/prs/hooks.rs`](https://github.com/herder-sh/herder/blob/701a5b527d486863442b9a3de218e6c02af0e2a4/crates/herder-daemon/src/prs/hooks.rs) |
| `refs/herder/<session>/<turn>` | hidden ref | strong | current pushed checkpoints | Source-only; n=1 checkpoint implementation | Low — product-owned hidden namespace | No — arbitrary refs are not collected | [`crates/herder-daemon/src/worktree/checkpoint.rs`](https://github.com/herder-sh/herder/blob/701a5b527d486863442b9a3de218e6c02af0e2a4/crates/herder-daemon/src/worktree/checkpoint.rs) |
| `herder <herder@localhost>` on checkpoint commits | author email / committer | composite-only | current synthetic checkpoint identity | Source-only; n=1 | Medium in ordinary history — intended commits live under hidden checkpoint refs, are unsigned, and omit `Herder-Session` | No safely — requires identity plus hidden-ref scope | [`checkpoint.rs`](https://github.com/herder-sh/herder/blob/701a5b527d486863442b9a3de218e6c02af0e2a4/crates/herder-daemon/src/worktree/checkpoint.rs) |
| Generic or explicitly supplied `herder/<name>` | branch | unsafe | caller-controlled alternative | Source-only; n=1 | Medium — product-like prefix, but caller control weakens provenance | Yes mechanically; prefer the default shape | [`worktree/mod.rs`](https://github.com/herder-sh/herder/blob/701a5b527d486863442b9a3de218e6c02af0e2a4/crates/herder-daemon/src/worktree/mod.rs) |

**Trust:** the custom trailer and default session-shaped branch. Treat checkpoint identities only in conjunction with `refs/herder/...`. **Ignore:** `herder@localhost` in unscoped ordinary history. **Highest-risk signal:** the checkpoint identity without ref scope. The frozen pack has no Herder coverage.

---

## 8. Hermes Agent

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| Exact `.hermes.md` or `HERMES.md` | file | strong | current Hermes-native context | Source-only; n=1 pinned implementation; no retained global count | Low — explicitly Hermes-native and highest priority | Yes with exact path patterns | [`website/docs/user-guide/features/context-files.md`](https://github.com/NousResearch/hermes-agent/blob/444f980868937926562fe5652d26364d45550960/website/docs/user-guide/features/context-files.md) |
| `.hermes/plans/*.md` | file | strong | current built-in plan output | 5,896 indexed path matches; n=5,896 | Low — product-specific directory | Yes | [`website/docs/reference/slash-commands.md`](https://github.com/NousResearch/hermes-agent/blob/444f980868937926562fe5652d26364d45550960/website/docs/reference/slash-commands.md) |
| Automatic `hermes/hermes-<8hex>` | branch | strong | current automatic worktree | Source-only; n=1 | Low — exact generated namespace and shape | Yes | [`hermes_cli/worktree_ops.py`](https://github.com/NousResearch/hermes-agent/blob/444f980868937926562fe5652d26364d45550960/hermes_cli/worktree_ops.py) |
| Named `hermes/<sanitized-name>` | branch | corroborating | current named worktree | Source-only; n=1 | Medium — name is user-supplied after sanitization | Yes, but broad prefix should have lower confidence | [`worktree_ops.py`](https://github.com/NousResearch/hermes-agent/blob/444f980868937926562fe5652d26364d45550960/hermes_cli/worktree_ops.py) |
| `hermes-subagent/subagent-<id>` | branch | optional | optional subagent worktree | Source-only; n=1 | Low — distinctive namespace | Yes | [`tools/subagent_worktree.py`](https://github.com/NousResearch/hermes-agent/blob/444f980868937926562fe5652d26364d45550960/tools/subagent_worktree.py) |
| `refs/hermes/archive/<tree>` | hidden ref | strong | current recovery archive | Source-only; n=1 | Low | No — arbitrary hidden refs are not collected | [`hermes_cli/worktree_archive.py`](https://github.com/NousResearch/hermes-agent/blob/444f980868937926562fe5652d26364d45550960/hermes_cli/worktree_archive.py) |
| `Hermes worktree archive <hermes-archive@localhost>` | author email / committer | composite-only | synthetic archive identity | Source-only; n=1 | Medium outside the archive ref context | No safely — needs hidden-ref scoping | [`worktree_archive.py`](https://github.com/NousResearch/hermes-agent/blob/444f980868937926562fe5652d26364d45550960/hermes_cli/worktree_archive.py) |
| `AGENTS.md`, `CLAUDE.md`, `.cursorrules` | file | unsafe | compatibility inputs | `AGENTS.md`: 1,196,032 indexed matches; n=1,196,032. Other counts not retained | High — shared or foreign formats | Yes mechanically; not as Hermes attribution | [`context-files.md`](https://github.com/NousResearch/hermes-agent/blob/444f980868937926562fe5652d26364d45550960/website/docs/user-guide/features/context-files.md) |

**Trust:** Hermes-native files and exact generated branch namespaces. Archive identities require archive-ref context. **Ignore:** compatibility inputs as Hermes evidence. **Highest-risk signal:** broad `hermes/` matching that treats arbitrary names as generated. The frozen pack has no Hermes Agent coverage.

---

## 9. Command Code

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| `.commandcode/settings.json`, `.commandcode/skills/`, `.commandcode/agents/`, `.commandcode/commands/`, `.commandcode/mods/`, `.commandcode/design/`, `.commandcode/taste/` | file | strong | current product configuration | `.commandcode/**/SKILL.md`: 1,800 indexed matches; n=1,800. Other paths source-only | Low — product-specific namespace | Yes; prefer specific subpaths | [Hooks](https://commandcode.ai/docs/hooks), [Skills](https://commandcode.ai/docs/skills), [Custom agents](https://commandcode.ai/docs/custom-agents) |
| `Co-authored-by: CommandCodeBot <noreply@commandcode.ai>` | trailer | strong | v1.88.5 default | 90,412 indexed exact-email/message matches; n=90,412 | Low — exact product domain and name | Yes through exact email matching | [`command-code@1.88.5/dist/cli.mjs`](https://unpkg.com/command-code@1.88.5/dist/cli.mjs) |
| `attribution.commit` replacement or `""`; deprecated `includeCoAuthoredBy` | trailer | optional | current configuration override | Source-only; n=1 distributed package version `1.88.5` | Medium for absence-based interpretation — configured sessions can leave no marker | Partly — replacement text can match; disabled/default state cannot be modeled | [`dist/cli.mjs`](https://unpkg.com/command-code@1.88.5/dist/cli.mjs) |
| Local `worktree-<name>` | branch | unsafe | current local managed worktree | Source-only; n=1 | High — generic namespace and user-controlled name | Yes mechanically; should not be attribution | [Worktrees](https://commandcode.ai/docs/worktrees) |
| Cloud `command-code/<id>` | branch | strong | current Cloud branch | Source-only; n=1 official cloud contract | Low — product-specific hosted namespace | Yes as anchored regex | [Cloud docs](https://commandcode.ai/docs/cloud) |
| Native bot login, label, PR footer, or issue trigger | bot / label / PR footer / issue trigger | unsafe | no stable contract found | None found as stable contracts; n=1 package/docs audit | High if inferred from app installation or generic activity | No stable fingerprint exists | [Command Code docs](https://commandcode.ai/docs) |

**Trust:** the default exact trailer, product-specific files, and Cloud branch prefix. **Ignore:** local `worktree-*` branches. **Highest-risk signal:** the generic local worktree branch. The frozen pack has no Command Code coverage.

---

## 10. Cursor

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| `.cursor/rules/*.mdc`, `.cursor/agents/*.md`, `.cursor/hooks.json`, `.cursor/mcp.json`, and documented `.cursor/` project configuration | file | strong | current | Source/docs audit; n=1 official documentation corpus; no aggregate count retained | Low–medium — namespace is distinctive but spans several Cursor features | Yes | [Rules](https://cursor.com/docs/rules), [Subagents](https://cursor.com/docs/subagents), [Hooks](https://cursor.com/docs/hooks) |
| `.cursor-plugin/plugin.json` | file | strong | current required Cursor plugin manifest | Source/docs audit; n=1 | Low | Yes | [Plugins reference](https://cursor.com/docs/reference/plugins) |
| `.cursor/config/bugbot.yaml` | file | strong | current optional repository configuration | 36 indexed path matches; n=36 | Low | Yes | [Bugbot](https://cursor.com/docs/bugbot) |
| Root or nested `.cursor/BUGBOT.md` | file | strong | current Bugbot rules | Source/docs audit; n=1; no retained global count | Low | Yes | [Bugbot repository rules](https://cursor.com/docs/bugbot.md#repository-rules) |
| `.cursor/worktrees.json` | file | strong | current worktree setup | Source/docs audit; n=1 | Low | Yes | [Worktrees](https://cursor.com/docs/configuration/worktrees) |
| `.cursor/environment.json` | file | strong | current Cloud environment configuration | Source/docs audit; n=1 | Low | Yes | [Cloud environment setup](https://cursor.com/docs/cloud-agent/setup) |
| `.cursorrules` | file | legacy | supported legacy rules format | Source/docs audit; n=1 | Medium — recognizable but superseded by `.cursor/rules` | Yes; schema cannot mark it legacy | [Rules](https://cursor.com/docs/rules) |
| `CURSOR.md` | file | unsafe | unsupported hypothesis rejected | No official support found; n=1 official-doc/source audit | High — folklore can collide with arbitrary project docs | Yes mechanically; should be removed from the pack | [Rules](https://cursor.com/docs/rules) |
| `Co-authored-by: Cursor <cursoragent@cursor.com>` | trailer | strong | local Agent default-on, configurable | 9,589,537 indexed exact-email/message matches; n=9,589,537 | Low — exact official address | Yes through exact email matching | [Git attribution](https://cursor.com/docs/integrations/git) |
| `Made with [Cursor](https://cursor.com)` | PR footer | strong | local Agent default-on, configurable | Official contract; no separate retained prevalence query | Low — exact URL and phrase | No — arbitrary PR-body footers are unsupported | [Git attribution](https://cursor.com/docs/integrations/git) |
| `Cursor Agent <cursoragent@cursor.com>` plus HSM-backed verified signature | author email / committer | strong | GitHub Cloud Agents | Email included in 9,589,537 matches; signature prevalence not counted | Very low when identity and verified signature are combined | Email yes; signature no because verification data is not fetched | [Secrets and Network](https://cursor.com/docs/cloud-agent/security-network) |
| Default `cursor/...` Cloud Agent branch | branch | strong | current cloud default | Source/docs audit; n=1 official API contract | Low | Yes as anchored regex | [Cloud Agents API example](https://docs.cursor.com/en/background-agent/api/list-agents) |
| `cursor[bot]` / Cursor GitHub App participation | bot | unsafe | current app activity, not necessarily authorship | Source/activity validation; n=1 official integration plus cross-repository checks | High as adoption evidence — comments and reviews do not prove generation | No safely — `bots` are exclusion-only while author patterns contaminate PR/issue evidence | [GitHub integration](https://cursor.com/docs/integrations/github) |
| `@cursor` or `@cursoragent` | issue trigger | composite-only | current Cloud Agent invocation | Source/docs audit; n=1 | Medium — strong command text, but only when posted by an authorized user | No — comment bodies are not collected | [Cloud Agents](https://cursor.com/docs/cloud-agent) |
| `cursor review` or `bugbot run` | issue trigger | composite-only | current Bugbot invocation | Source/docs audit; n=1 | Medium — proves reviewer invocation, not code authorship | No — comment bodies are not collected | [Bugbot](https://cursor.com/docs/bugbot) |

**Trust:** exact Cursor paths, email/trailer, PR footer, signed Cloud Agent commits, and anchored Cloud branches. **Ignore:** `CURSOR.md` and `cursor[bot]` participation as standalone adoption. **Highest-risk signal:** the broad `cursor` author pattern; login normalization can turn `cursor[bot]` into `cursor`, contaminating PR and issue evidence. The frozen pack otherwise has `.cursor/`, `.cursorrules`, the email, and `cursor/`, but incorrectly includes `CURSOR.md` and lacks footer, signature, and trigger support.

---

## 11. Ghostty

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| Ghostty hosts a downstream agent | file / author email / committer / trailer / branch | unsafe | terminal layer only | Source-only; n=1 pinned source audit | High — effects belong to the downstream program | No repository-visible native marker exists | [`README.md`](https://github.com/ghostty-org/ghostty/blob/e035beb9437118b803830a5864ea2f4dd7094354/README.md) |
| Ghostty’s own `AGENTS.md` | file | unsafe | contributor guidance in Ghostty’s source repo | `AGENTS.md`: 1,196,032 indexed matches; n=1,196,032 | High — standard guidance, not proof Ghostty authored downstream changes | Yes mechanically; not as Ghostty evidence | [`AGENTS.md`](https://github.com/ghostty-org/ghostty/blob/e035beb9437118b803830a5864ea2f4dd7094354/AGENTS.md) |
| Ghostty repository `.agents/` content | file | unsafe | contributor/tool guidance | Shared `.agents/skills/**/SKILL.md`: 496,640 indexed matches; n=496,640 | High | Yes mechanically; not as Ghostty evidence | [Pinned Ghostty source](https://github.com/ghostty-org/ghostty/tree/e035beb9437118b803830a5864ea2f4dd7094354) |
| Native identity, trailer, branch, ref, label, footer, bot, or issue trigger | author email / committer / trailer / branch / hidden ref / label / PR footer / bot / issue trigger | unsafe | none found | None found; n=1 complete source audit | High if inferred from a launched agent | No native contract exists | [Pinned source](https://github.com/ghostty-org/ghostty/tree/e035beb9437118b803830a5864ea2f4dd7094354) |

**Trust:** no repository fingerprint as proof of Ghostty usage. Attribute artifacts to downstream agents. **Ignore:** Ghostty’s contributor files as downstream evidence. **Highest-risk signal:** its own `AGENTS.md` or `.agents/` tree. The frozen pack correctly has no Ghostty detector.

---

## 12. OpenCode v2

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| Root `opencode.json` or `opencode.jsonc` | file | strong | current V2 project configuration | Source/docs audit; n=1 pinned V2 snapshot; no retained path count | Low–medium — explicit config; pattern must be end-anchored | Yes | [`packages/web/src/content/docs/config.mdx`](https://github.com/anomalyco/opencode/blob/3ce4ca464dbbd993eb9c3158f7e77cddd80774fb/packages/web/src/content/docs/config.mdx) |
| `.opencode/opencode.json` or `.opencode/opencode.jsonc` | file | strong | current V2 project configuration | Source/docs audit; n=1 | Low | Yes | [`config.mdx`](https://github.com/anomalyco/opencode/blob/3ce4ca464dbbd993eb9c3158f7e77cddd80774fb/packages/web/src/content/docs/config.mdx) |
| `.opencode/agents/`, `commands/`, `plugins/`, `tools/`, `skills/`, `themes/`, plans and related definitions | file | strong | current V2 definitions | Source/docs audit; n=1 | Low–medium — product namespace, though individual skills are portable | Yes; prefer specific subpaths | [Agents](https://github.com/anomalyco/opencode/blob/3ce4ca464dbbd993eb9c3158f7e77cddd80774fb/packages/web/src/content/docs/agents.mdx), [Plugins](https://github.com/anomalyco/opencode/blob/3ce4ca464dbbd993eb9c3158f7e77cddd80774fb/packages/web/src/content/docs/plugins.mdx) |
| Root `.opencode.json` | file | legacy | undocumented V2 compatibility/history | Source audit; n=1 | Medium | Yes; schema cannot mark it legacy | [Pinned V2 source](https://github.com/anomalyco/opencode/tree/3ce4ca464dbbd993eb9c3158f7e77cddd80774fb) |
| V2 detached worktrees | branch | unsafe | current V2 core creates no named branch | Source audit; n=1 | High if `opencode/` is assumed to be current | No positive current branch fingerprint exists | [Pinned V2 core](https://github.com/anomalyco/opencode/tree/3ce4ca464dbbd993eb9c3158f7e77cddd80774fb/packages/opencode/src) |
| V2 core native author identity, trailer, or footer | author email / committer / trailer / PR footer | unsafe | none found in current core | None found; n=1 complete V2 core audit | High if legacy/plugin behavior is presented as current core | No current core contract exists | [Pinned V2 core](https://github.com/anomalyco/opencode/tree/3ce4ca464dbbd993eb9c3158f7e77cddd80774fb) |
| `opencode/<name>`, timestamped GitHub branches, `opencode-agent[bot]`, `🤖 Generated with opencode`, `noreply@opencode.ai` | branch / bot / trailer / author email | legacy | OpenCode V1 / historical GitHub flow | 226,793 indexed OpenCode email/message matches; n=226,793 | Medium — historically distinctive, but wrong for current-core attribution | Yes mechanically; schema lacks validity periods | [Pinned V1 source](https://github.com/anomalyco/opencode/tree/c90281c0d6e6a92309d8d326e732931b92739cdf) |
| `Harness: OpenCode …`, model/session trailers, `Opencode-Session:` | trailer | optional | third-party/plugin-only, not V2 core | Cross-repository plugin validation; no retained global count | Medium — meaningful only for the emitting plugin | No safely — requires trailer-specific schema and plugin provenance | [Pinned V2 core, which has no equivalent default](https://github.com/anomalyco/opencode/tree/3ce4ca464dbbd993eb9c3158f7e77cddd80774fb) |

**Trust:** current V2 configuration paths. **Ignore:** `opencode/` branches, `noreply@opencode.ai`, `opencode-agent[bot]`, and the old generated footer as current V2 evidence. **Highest-risk signal:** conflating V1 and plugin attribution with V2 core. The frozen pack partially covers files but retains `.opencode.json` and undated V1 branch/identity rules.

---

## 13. Pi

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| `.pi/settings.json` | file | strong | current project settings | 1,310 indexed path matches; n=1,310 | Low | Yes | [`packages/coding-agent/docs/configuration.md`](https://github.com/earendil-works/pi/blob/5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c/packages/coding-agent/docs/configuration.md) |
| `.pi/mcp.json`, `.pi/SYSTEM.md`, `.pi/APPEND_SYSTEM.md` | file | strong | current project configuration | Source/docs audit; n=1; no retained individual counts | Low | Yes | [`configuration.md`](https://github.com/earendil-works/pi/blob/5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c/packages/coding-agent/docs/configuration.md) |
| `.pi/extensions/`, `.pi/prompts/`, `.pi/skills/`, `.pi/themes/` | file | strong | current project resources | Source/docs audit; n=1 | Low–medium — specific subpaths are safer than broad `.pi/` | Yes | [`configuration.md`](https://github.com/earendil-works/pi/blob/5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c/packages/coding-agent/docs/configuration.md) |
| Any bare `.pi/` path | file | corroborating | broad namespace | Frozen-pack pattern exists; no separate count retained | Medium — can include unrelated data | Yes, but specific paths should carry more weight | [`configuration.md`](https://github.com/earendil-works/pi/blob/5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c/packages/coding-agent/docs/configuration.md) |
| Provider request attribution through `PI_ATTRIBUTION` | author email / trailer | unsafe | outbound HTTP/provider attribution, not Git | Source-only; n=1 | High category error — it labels model-provider requests, not repository history | No repository channel exists because this is not Git evidence | [Pinned Pi source](https://github.com/earendil-works/pi/tree/5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c) |
| Native Git identity, trailer, branch, footer, bot, label, or issue trigger | author email / committer / trailer / branch / PR footer / bot / label / issue trigger | unsafe | none found | None found; n=1 complete pinned-source audit | High if provider or downstream attribution is confused with Git attribution | No native Git fingerprint exists | [Pinned Pi source](https://github.com/earendil-works/pi/tree/5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c) |

**Trust:** specific documented `.pi` project paths. **Ignore:** model-provider HTTP attribution and downstream identities as Git evidence. **Highest-risk signal:** treating every `.pi/` directory or `PI_ATTRIBUTION` as repository authorship. The frozen pack has broad `.pi/`, prompts, and extensions coverage but omits several stronger explicit paths.

---

## 14. Oh My Pi

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| `.omp/config.yml` or `.omp/config.yaml` | file | strong | current project settings | `.omp/config.yml`: 230 indexed path matches; n=230 | Low | Yes | [`docs/config-usage.md`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/docs/config-usage.md) |
| `.omp/agents`, `commands`, `skills`, `tools`, `extensions`, `prompts`, `rules`, `mcp.json`, `hooks`, `plugins`, native context files | file | strong | current core project configuration | Source/docs audit; n=1 pinned snapshot; no retained per-path totals | Low–medium — product namespace; some contained formats are portable | Yes | [`config-usage.md`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/docs/config-usage.md), [`docs/custom-tools.md`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/docs/custom-tools.md) |
| `wt/<yyyymmdd-hhmmss>` | branch | optional | default `/wt` branch, user-overridable | Source-only; n=1 | Medium–high — short generic namespace | Yes mechanically; corroborating only | [`packages/coding-agent/src/modes/controllers/command-controller.ts`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/packages/coding-agent/src/modes/controllers/command-controller.ts) |
| `omp/task/<id>` | branch | optional | optional isolation branch-merge mode | Source-only; n=1 | Low — product-specific | Yes | [`docs/tools/task.md`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/docs/tools/task.md) |
| `pr-<number>` | branch | unsafe | PR checkout helper | Source-only; n=1 | High — common across tools | Yes mechanically; not as attribution | [`docs/tools/github.md`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/docs/tools/github.md) |
| `farm/<8hex>/<slug>` | branch | composite-only | `python/robomp` subcomponent only | Source-only; n=1 | Low lexical collision, but identifies robomp rather than OMP core | Yes mechanically; needs separate subcomponent identity | [`python/robomp/src/sandbox.py`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/python/robomp/src/sandbox.py) |
| robomp Git author name/email and bot login | author email / committer / bot | composite-only | deployment-configurable third-party/subcomponent activity | Source-only; n=1; values are configured by `ROBOMP_BOT_LOGIN`, `ROBOMP_GIT_AUTHOR_NAME`, `ROBOMP_GIT_AUTHOR_EMAIL` | High across deployments — no fixed identity | No stable literal; no deployment conjunctions | [`python/robomp/src/config.py`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/python/robomp/src/config.py) |
| `triaged`, `prio:p0..p3`, `review:p0..p3`, taxonomy labels | label | composite-only | robomp workflow | Source-only; n=1 | High standalone — common labels and configurable taxonomy | Yes mechanically; no conjunction support | [`python/robomp/src/host_tools.py`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/python/robomp/src/host_tools.py) |
| `@<configured-bot>` | issue trigger | composite-only | robomp directive | Source-only; n=1 | High without deployment config and comment content | No — comment bodies are not collected | [`python/robomp/src/github_events.py`](https://github.com/can1357/oh-my-pi/blob/33a063ce79dfc24d3a99786283d01f6ed127703c/python/robomp/src/github_events.py) |
| Core native Git identity or trailer | author email / committer / trailer | unsafe | none found | None found; n=1 complete core audit | High if robomp or downstream identities are assigned to core | No stable core contract | [Pinned source](https://github.com/can1357/oh-my-pi/tree/33a063ce79dfc24d3a99786283d01f6ed127703c) |

**Trust:** `.omp` project surfaces and, when present, `omp/task/<id>`. Keep robomp separately named. **Ignore:** `pr-*`, generic `wt/*`, and configurable robomp identities as standalone product evidence. **Highest-risk signal:** `pr-<number>`. The frozen pack has no Oh My Pi coverage.

---

## 15. OpenClaw

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| Workspace conjunction: `AGENTS.md` + `SOUL.md` + `IDENTITY.md`, with optional `USER.md`, optional `BOOT.md`, one-time `BOOTSTRAP.md`, optional `MEMORY.md` | file | composite-only | current workspace bootstrap contract | `AGENTS.md` 1,196,032; `SOUL.md` 38,464; `IDENTITY.md` 79,872; `USER.md` 86,784; `BOOTSTRAP.md` 37,632; `MEMORY.md` 133,120 indexed matches; each n equals its listed total | Low–medium for the documented conjunction; extremely high for a singleton | No — cannot require multiple paths or their relationship | [`docs/concepts/agent-workspace.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/concepts/agent-workspace.md) |
| Any singleton from that workspace set | file | unsafe | shared/generic filenames | Counts above | High — all names are shared; `AGENTS.md` is especially ubiquitous | Yes mechanically; no as OpenClaw attribution | [`agent-workspace.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/concepts/agent-workspace.md) |
| `TOOLS.md` as runtime bootstrap | file | legacy | retired; doctor migrates content into `AGENTS.md` | Source/docs audit; n=1 | High as current evidence | Yes mechanically; should not be added | [`docs/automation/hooks/bundled-hooks.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/automation/hooks/bundled-hooks.md) |
| Executable `.openclaw/worktree-setup.sh` | file | strong | current managed-worktree setup | 3 indexed path matches; n=3 | Low | Yes | [`docs/concepts/managed-worktrees.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/concepts/managed-worktrees.md) |
| `.worktreeinclude` | file | unsafe | shared worktree convention | 1,474 indexed path matches; n=1,474 | High | Yes mechanically; no as OpenClaw attribution | [`managed-worktrees.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/concepts/managed-worktrees.md) |
| `openclaw/<name>` | branch | strong | current local managed branch | Source-only; n=1 | Low — product namespace, though name is selected/generated | Yes as anchored prefix | [`managed-worktrees.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/concepts/managed-worktrees.md) |
| `<repositoryBranchPrefix>/<workspace GUID>`, default prefix `openclaw` | branch | strong | current remote repository session | Source-only; n=1 official config contract | Low for default GUID-shaped branch; prefix is configurable | Yes for default prefix only | [`docs/gateway/config-runtime.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/gateway/config-runtime.md) |
| `refs/openclaw/snapshots/<id>`, `refs/openclaw/snapshots/exact-v1/<id>`, `refs/openclaw/removals/<id>` | hidden ref | strong | current internal recovery | Source-only; n=1 | Low | No — arbitrary refs are not collected | [`managed-worktrees.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/concepts/managed-worktrees.md) |
| `refs/openclaw/worker-results/...` | hidden ref | strong | current cloud-worker result fence | Source-only; n=1 | Low | No — hidden refs unsupported | [`docs/gateway/cloud-workers/session-lifecycle.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/gateway/cloud-workers/session-lifecycle.md) |
| Exact human `Co-authored-by` trailers from verified participants | trailer | unsafe | current human credit, not product attribution | Source-only; n=1 | High as product evidence — identifies humans | Yes mechanically for known emails, but semantically wrong | [`docs/concepts/user-model.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/concepts/user-model.md) |
| `🦞 Made with [OpenClaw](https://openclaw.ai)` | PR footer | optional | current; off by default | Source-only; n=1 | Low | No — arbitrary PR-body footers unsupported | [`user-model.md`](https://github.com/openclaw/openclaw/blob/476cce7a8a343ac1524bf12276da839a690cff8a/docs/concepts/user-model.md) |
| `OpenClaw <openclaw@localhost>` synthetic internal commits | author email / committer | composite-only | current source-defined synthetic identity | Source-only for current implementation; ordinary public-history query found 31,846 `openclaw@localhost` matches; n=31,846 for that query | Medium — exact identity, but intended only for synthetic internal commits | No safely — needs purpose/ref scope | [Pinned current source](https://github.com/openclaw/openclaw/tree/476cce7a8a343ac1524bf12276da839a690cff8a) |
| Ordinary public-history `openclaw@localhost` commits beginning `2026-02-12` | author email / committer | anomalous | product-associated public activity, not a verified default | 31,846 indexed matches; n=31,846 | High for default/legacy interpretation — activity predates the September synthetic-worktree implementation, and v2026.2.12 contains no such default | Yes mechanically; should not be represented as current or legacy default | [Historical v2026.2.12 comparison](https://github.com/openclaw/openclaw/tree/v2026.2.12) |

**Competing readings — unverified origin of ordinary `openclaw@localhost` history:** (1) an earlier private, deployed, or subsequently removed product path emitted it; (2) users or product-adjacent automation independently adopted the identity. The verified facts rule out the current implementation and v2026.2.12 as the default source. The recommended classification is **anomalous/product-associated**, never current-default or legacy-default evidence.

**Trust:** `.openclaw/worktree-setup.sh`, product-prefixed branches, and hidden refs when collected. Use workspace files only as a conjunction. **Ignore:** singleton workspace names and human co-author credit as product authorship. **Highest-risk signal:** singleton `AGENTS.md`, with exactly 1,196,032 indexed matches. The frozen pack has no OpenClaw coverage.

---

## 16. Claw Code

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| `.claw/settings.json`, `.claw/skills/`, `.claw/agents/`, `.claw/commands/`, `.claw/rules/`, related project configuration | file | strong | current | Source-only; n=1 pinned upstream snapshot; no retained global count | Low | Yes | [Pinned Claw Code source](https://github.com/ultraworkers/claw-code/tree/ca48ec75003da7f64a0780996c2ba6e71f78daea) |
| Root `.claw.json` | file | corroborating | current compatibility input and scaffold output | Source-only; n=1 | Low–medium | Yes | [Pinned source](https://github.com/ultraworkers/claw-code/tree/ca48ec75003da7f64a0780996c2ba6e71f78daea) |
| `CLAW.md` with Claw Code-specific content | file | composite-only | current content-dependent context | Source-only; n=1; no prevalence query | Medium–high without content — generic name used by other “claw” projects | No — needs file-content corroboration | [Pinned source](https://github.com/ultraworkers/claw-code/tree/ca48ec75003da7f64a0780996c2ba6e71f78daea) |
| `.claw/sessions/`, local settings, local state committed to Git | file | anomalous | ignored/local state | Source-only; n=1 | Low lexical collision, but abnormal as committed evidence | Yes mechanically; not normal adoption | [Pinned source](https://github.com/ultraworkers/claw-code/tree/ca48ec75003da7f64a0780996c2ba6e71f78daea) |
| Native Git identity, trailer, branch, hidden ref, label, footer, bot, or issue trigger | author email / committer / trailer / branch / hidden ref / label / PR footer / bot / issue trigger | unsafe | none found | None found; n=1 complete pinned-source audit | High if inferred from compatible/downstream agents | No stable native contract | [Pinned source](https://github.com/ultraworkers/claw-code/tree/ca48ec75003da7f64a0780996c2ba6e71f78daea) |

**Trust:** the current `.claw/` namespace and `.claw.json` as compatibility corroboration. **Ignore:** contentless `CLAW.md` and committed local state as normal adoption. **Highest-risk signal:** `CLAW.md` without product content. The frozen pack has no Claw Code coverage.

---

## 17. Mistral Vibe

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| `.vibe/config.toml`, `.vibe/hooks/`, `.vibe/skills/`, `.vibe/agents/`, `.vibe/prompts/`, `.vibe/plugins/` | file | strong | current | `.vibe/config.toml`: 67 indexed path matches; n=67. Remaining paths source-only | Low | Yes | [Pinned Mistral Vibe source](https://github.com/mistralai/mistral-vibe/tree/c96a6dbb34d34f8a868b3f67b279ecabbf1aa616) |
| `.vibe/tools/` | file | legacy | retired; current code warns about it | Source-only; n=1 | Medium as current evidence | Yes mechanically; schema cannot mark it retired | [Pinned source](https://github.com/mistralai/mistral-vibe/tree/c96a6dbb34d34f8a868b3f67b279ecabbf1aa616) |
| `Generated by Mistral Vibe.` plus `Co-Authored-By: Mistral Vibe <vibe@mistral.ai>` | trailer | strong | current default-on footer | Exact phrase: 43,071 indexed matches; n=43,071. Exact email: 49,443; n=49,443 | Low | Email yes; exact phrase lacks a message-specific rule without abusing author patterns | [Pinned source](https://github.com/mistralai/mistral-vibe/tree/c96a6dbb34d34f8a868b3f67b279ecabbf1aa616) |
| `include_commit_signature=false` | trailer | optional | current disable switch | Source-only; n=1 | Low collision, but absence cannot prove non-use | No — local disablement is not observable from absence | [Pinned source](https://github.com/mistralai/mistral-vibe/tree/c96a6dbb34d34f8a868b3f67b279ecabbf1aa616) |
| Auto-named `vibe/<name>` | branch | strong | current auto-name path | Source-only; n=1 | Low–medium — product namespace; only automatic when no name is supplied | Yes as anchored prefix; origin cannot be distinguished | [Pinned source](https://github.com/mistralai/mistral-vibe/tree/c96a6dbb34d34f8a868b3f67b279ecabbf1aa616) |
| Caller-supplied worktree branch | branch | unsafe | arbitrary input | Source-only; n=1 | High | No stable pattern | [Pinned source](https://github.com/mistralai/mistral-vibe/tree/c96a6dbb34d34f8a868b3f67b279ecabbf1aa616) |
| `refs/vibe/reaped/<name>` | hidden ref | strong | recovery-only | Source-only; n=1 | Low | No — hidden refs unsupported | [Pinned source](https://github.com/mistralai/mistral-vibe/tree/c96a6dbb34d34f8a868b3f67b279ecabbf1aa616) |
| Native bot, label, PR footer, or issue trigger | bot / label / PR footer / issue trigger | unsafe | none found | None found; n=1 complete source audit | High if inferred from unrelated Mistral activity | No stable native fingerprint | [Pinned source](https://github.com/mistralai/mistral-vibe/tree/c96a6dbb34d34f8a868b3f67b279ecabbf1aa616) |

**Trust:** the exact trailer/email, current `.vibe` paths, and auto `vibe/` branches. **Ignore:** `.vibe/tools/` as current evidence and caller-supplied branches. **Highest-risk signal:** retired `.vibe/tools/` presented as current. The frozen pack has only `vibe@mistral.ai` and misses current files, exact phrase, branches, and recovery refs.

---

## 18. OpenHands

| Fingerprint | Channel | Evidence class | Lifecycle / ownership | Observed prevalence + sample size | Collision risk | Encodable in current pack schema? | Source |
|---|---|---|---|---|---|---|---|
| `.openhands/hooks.json`, `.openhands/memory/MEMORY.md`, `.openhands/agents/` | file | strong | current | `.openhands/hooks.json`: 22 indexed path matches; n=22. Remaining paths source-only | Low | Yes | [Pinned Software Agent SDK](https://github.com/OpenHands/software-agent-sdk/tree/e6569442a23951f852ead8514ae51dff1b377f37) |
| `.agents/agents/`, `.agents/skills/` | file | composite-only | current preferred shared locations | `.agents/skills/**/SKILL.md`: 496,640 indexed matches; n=496,640 | High standalone — portable/shared standard | Yes mechanically; no as OpenHands attribution | [Pinned SDK](https://github.com/OpenHands/software-agent-sdk/tree/e6569442a23951f852ead8514ae51dff1b377f37) |
| `.openhands/skills/` | file | legacy | legacy location | Source-only; n=1 | Low lexical collision, temporal risk | Yes; schema cannot mark legacy | [Pinned SDK](https://github.com/OpenHands/software-agent-sdk/tree/e6569442a23951f852ead8514ae51dff1b377f37) |
| `.openhands/microagents/` | file | legacy | deprecated | Source-only; n=1 | Low lexical collision, high temporal misclassification risk | Yes; schema cannot mark deprecated | [Pinned OpenHands source](https://github.com/OpenHands/OpenHands/tree/cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05) |
| `.agents_tmp/PLAN.md` | file | anomalous | current default planner path; temporary | Source-only; n=1 | Medium — distinctive but not expected to be committed | Yes mechanically; not normal durable adoption | [Pinned SDK](https://github.com/OpenHands/software-agent-sdk/tree/e6569442a23951f852ead8514ae51dff1b377f37) |
| Root `PLAN.md` | file | legacy | legacy fallback | Source-only; n=1 | High — generic filename | Yes mechanically; not product attribution | [Pinned SDK](https://github.com/OpenHands/software-agent-sdk/tree/e6569442a23951f852ead8514ae51dff1b377f37) |
| `.openhands/PLAN.md` | file | optional | configurable/test evidence; not default | Source-only; n=1 | Medium | Yes, but not as default behavior | [Pinned SDK](https://github.com/OpenHands/software-agent-sdk/tree/e6569442a23951f852ead8514ae51dff1b377f37) |
| `openhands/<conversation-id>` | branch | strong | current default | Source-only; n=1 | Low | Yes as anchored regex | [Pinned OpenHands source](https://github.com/OpenHands/OpenHands/tree/cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05) |
| `Co-authored-by: openhands <openhands@all-hands.dev>` | trailer | strong | current prompt requirement | 273,260 indexed exact-email/message matches; n=273,260 | Low | Yes through exact email matching | [Pinned OpenHands source](https://github.com/OpenHands/OpenHands/tree/cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05) |
| `openhands <openhands@all-hands.dev>` when Git identity is absent | author email / committer | strong | current fallback | Included in the 273,260 exact-email result universe; n=273,260 | Low | Yes, though author and committer are not separately scoped | [Pinned OpenHands source](https://github.com/OpenHands/OpenHands/tree/cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05) |
| `all-hands-bot` together with `review-this` | bot / label / issue trigger | composite-only | current review automation | Source/activity validation; no retained global count | Medium — review automation does not necessarily author code; conjunction matters | No safely — bot-safe activity and trigger/label conjunction are unsupported | [Pinned OpenHands source](https://github.com/OpenHands/OpenHands/tree/cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05) |
| `openhands-agent` | bot | legacy | historical/example reviewer identity | Historical/example evidence; no retained count | High as current adoption evidence; dangerous in PR/issue channels | Yes mechanically as an author pattern; should be removed or legacy-scoped | [Pinned OpenHands source](https://github.com/OpenHands/OpenHands/tree/cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05) |

**Trust:** the exact email/trailer, `openhands/<conversation-id>`, and current product-specific `.openhands` files. **Ignore:** `.agents` alone, generic planning files, and historical bot activity as standalone adoption. **Highest-risk signal:** the frozen pack’s `openhands-agent` author pattern, because author patterns are reused for PR and issue participants. The pack otherwise partially covers `.openhands/`, the email, and branch prefix but conflates current, legacy, deprecated, and bot activity.

---

## 19. Detector Additions, in Priority Order

1. **Correct unsafe existing rules before expanding coverage.**
   - Remove unsupported `CURSOR.md`.
   - Remove or legacy-scope `openhands-agent`.
   - Stop presenting `opencode/`, `noreply@opencode.ai`, `opencode-agent[bot]`, and `🤖 Generated with opencode` as current OpenCode v2 evidence.
   - Prevent normalized `cursor[bot]` from satisfying the generic `cursor` author rule in PR and issue channels.

2. **Add high-value exact commit attribution.**
   - Paperclip: `noreply@paperclip.ing`.
   - Command Code: `noreply@commandcode.ai`.
   - Retain Cursor: `cursoragent@cursor.com`.
   - Retain and supplement Mistral Vibe: `vibe@mistral.ai`.
   - Retain OpenHands: `openhands@all-hands.dev`.
   - Orca’s `help@stably.ai` only in a legacy-validity rule, not as current behavior.

3. **Add strong current product-specific files.**
   - Orca: `^orca\.yaml$`.
   - Hermes: exact `.hermes.md`, `HERMES.md`, `.hermes/plans/`.
   - Command Code: `.commandcode/settings.json`, skills, agents, commands, mods, and design paths.
   - Cursor: `.cursor-plugin/plugin.json`, `.cursor/config/bugbot.yaml`, `.cursor/BUGBOT.md`, `.cursor/worktrees.json`, `.cursor/environment.json`.
   - OpenCode v2: anchored `opencode.json(c)` and documented `.opencode/` definitions.
   - Pi: settings, MCP, system-prompt, extensions, prompts, skills, and themes paths.
   - Oh My Pi: current `.omp/` configuration and extension paths.
   - OpenClaw: `.openclaw/worktree-setup.sh`.
   - Claw Code: current `.claw/` project paths.
   - Mistral Vibe: current `.vibe/` paths, excluding `.vibe/tools/` from current evidence.
   - OpenHands: `.openhands/hooks.json`, `.openhands/memory/MEMORY.md`, `.openhands/agents/`.

4. **Add low-collision current branches.**
   - Herder default `herder/<session-suffix>`.
   - Hermes `hermes/hermes-<8hex>` and `hermes-subagent/subagent-<id>`.
   - Command Code Cloud `command-code/<id>`.
   - Cursor `cursor/...`.
   - Oh My Pi `omp/task/<id>`.
   - OpenClaw `openclaw/<name>` and GUID-shaped remote branches.
   - Mistral Vibe `vibe/<name>`.
   - OpenHands `openhands/<conversation-id>`.
   - Herdr’s full adjective–noun–hex branch only as corroborating evidence.

5. **Add compatibility and legacy rules only with explicit reduced weight and validity metadata.**
   - `.cursorrules`.
   - `.opencode.json`.
   - `.claw.json` as compatibility corroboration.
   - `.openhands/skills/`, `.openhands/microagents/`.
   - `.vibe/tools/`.
   - OpenCode v1 identities, branches, bot, and footer.
   - Orca’s retired trailer.

6. **Keep generic and inherited surfaces out of standalone adoption scoring.**
   - `.worktreeinclude`.
   - `AGENTS.md`, `.agents/skills/`, `SOUL.md`, `MEMORY.md`, `USER.md`, `IDENTITY.md`, `BOOTSTRAP.md` individually.
   - `worktree/*`, `worktree-*`, `wt/*`, `pr-*`.
   - Issue-derived or caller-supplied branches.
   - Terminal/wrapper fingerprints inferred from downstream agents.
   - Product bots appearing only as commenters, reviewers, or issue participants.

---

## 20. Real Signals the Current Schema Cannot Encode Safely

1. **File-content and conjunction rules**
   - `.paperclip.yaml` plus `schema: paperclip/v1`.
   - OpenClaw’s workspace-file conjunction.
   - Claw Code-specific content in `CLAW.md`.
   - Exact DeepSeek `powered_by-dsh` badge content.
   - Any “path A and path B” or “path plus content” rule.

2. **Custom trailer schemas**
   - `Herder-Session: <id>`.
   - Plugin-defined `Harness: OpenCode …` and `Opencode-Session:`.
   - Exact message phrases without leaking them into author, PR-author, and issue-participant matching.

3. **Hidden refs**
   - `refs/herder/<session>/<turn>`.
   - `refs/hermes/archive/<tree>`.
   - `refs/vibe/reaped/<name>`.
   - `refs/openclaw/snapshots/...`, `refs/openclaw/removals/...`, `refs/openclaw/worker-results/...`.

4. **Arbitrary PR-body footers**
   - `Made with [Cursor](https://cursor.com)`.
   - `🦞 Made with [OpenClaw](https://openclaw.ai)`.
   - DeepSeek’s optional badge when placed in a PR body.

5. **Comment-body and issue triggers**
   - `@cursor` / `@cursoragent`.
   - `cursor review` / `bugbot run`.
   - robomp’s deployment-configured `@<configured-bot>` directives.

6. **Commit signature verification**
   - Cursor Cloud Agent’s HSM-backed verified signatures.
   - Any signer-key, verification-state, or GitHub “Verified” requirement.

7. **Ref-scoped synthetic identities**
   - `herder@localhost` only on checkpoint refs.
   - `hermes-archive@localhost` only on archive refs.
   - `openclaw@localhost` only for current synthetic internal commits.

8. **Bot-safe activity evidence**
   - `cursor[bot]`, `all-hands-bot`, and deployment-specific robomp bots without turning comments into adoption.
   - The current `bots` channel is exclusion-oriented, while author patterns are reused across commits, PR authors, and issue participants.

9. **Validity and provenance metadata**
   - Current versus legacy versus deprecated date ranges.
   - Default-on versus optional/default-off behavior.
   - Core product versus plugin, wrapper, orchestrator, terminal, or subcomponent.
   - Recovery-only and anomalous-when-committed classifications.

These limitations follow from the shared `Pattern(pattern, agent)` model in [`src/detect/packs.py`](../../src/detect/packs.py), channel reuse in [`src/detect/attribution.py`](../../src/detect/attribution.py), the API fields collected by [`src/detect/channels.py`](../../src/detect/channels.py), and branch/ref limits in [`src/detect/local_channels.py`](../../src/detect/local_channels.py).

---

## 21. Prevalence Ledger

This ledger preserves every exact count retained from the research. Counts are volatile index totals, not unique-repository counts.

| Query target | Exact observed total | Sample-size interpretation | Caveat |
|---|---:|---|---|
| `cursoragent@cursor.com` | 9,589,537 | n=9,589,537 indexed exact-email/message matches | Can include author identities, trailers, repeated commits, and multiple matches per repository |
| `noreply@paperclip.ing` | 461,628 | n=461,628 | Same caveat |
| `openhands@all-hands.dev` | 273,260 | n=273,260 | Same caveat |
| `noreply@opencode.ai` / retained OpenCode identity-message query | 226,793 | n=226,793 | Primarily V1/legacy evidence, not V2 core |
| `help@stably.ai` in messages/trailers | 126,632 | n=126,632 | `author-email:help@stably.ai` separately returned exactly `0` |
| `noreply@commandcode.ai` | 90,412 | n=90,412 | Exact v1.88.5 default trailer email |
| `vibe@mistral.ai` | 49,443 | n=49,443 | Exact email can occur in trailer or identity text |
| `Generated by Mistral Vibe.` | 43,071 | n=43,071 | Exact message phrase query |
| `openclaw@localhost` | 31,846 | n=31,846 | Ordinary public matches are anomalous; not a verified current or legacy default |
| `AGENTS.md` | 1,196,032 | n=1,196,032 indexed path matches | Shared standard; high collision |
| `.agents/skills/**/SKILL.md` | 496,640 | n=496,640 | Shared portable skills location |
| `MEMORY.md` | 133,120 | n=133,120 | Shared generic filename |
| `USER.md` | 86,784 | n=86,784 | Shared generic filename |
| `IDENTITY.md` | 79,872 | n=79,872 | Shared generic filename |
| `SOUL.md` | 38,464 | n=38,464 | Shared across agent systems |
| `BOOTSTRAP.md` | 37,632 | n=37,632 | Shared/generic bootstrap name |
| `.worktreeinclude` | 1,474 | n=1,474 | Cross-tool worktree convention |
| `.hermes/plans/*.md` | 5,896 | n=5,896 | Product-specific path |
| `.commandcode/**/SKILL.md` | 1,800 | n=1,800 | Product namespace |
| `.pi/settings.json` | 1,310 | n=1,310 | Product-specific path |
| `.omp/config.yml` | 230 | n=230 | Product-specific current path |
| `.paperclip.yaml` | 165 | n=165 | Path count only; schema content was not part of this total |
| `.vibe/config.toml` | 67 | n=67 | Product-specific current path |
| `.cursor/config/bugbot.yaml` | 36 | n=36 | Product-specific current path |
| `.openhands/hooks.json` | 22 | n=22 | Product-specific current path |
| `.openclaw/worktree-setup.sh` | 3 | n=3 | Product-specific current path |
| committed `.orca/issue-command` | 0 | n=0 | Supports “normally local/ignored,” not proof of impossibility |

---

## 22. Corrections and Rejected Hypotheses

- **Orca attribution is not current.** The exact `Co-authored-by: Orca <help@stably.ai>` trailer was initially plausible as a current default because public message matches were abundant. Current source instead showed local-only attribution and no committed default; the trailer was reclassified as retired legacy evidence.
- **Orca branch names are not native signatures.** Issue and work-item branch names inherit external SCM naming or user input.
- **DeepSeek’s badge is not a default.** It comes from a bundled experimental skill provider that ships disabled.
- **DeepSeek worktrees are also default-disabled.** Their generated names are real but optional, and their local pool is normally ignored.
- **Paperclip’s extension requires content awareness.** `.paperclip.yaml` is canonical only with `schema: paperclip/v1`; `.paperclip.yml` is compatibility input.
- **Herdr and Herder are different products.** Herdr uses generic `worktree/<adjective>-<noun>-<4hex>` and no native attribution. Herder uses `herder/<session-suffix>`, `Herder-Session:`, and checkpoint refs.
- **Ghostty is a terminal, not an attribution source.** Its own `AGENTS.md` and `.agents/` files are contributor guidance.
- **`CURSOR.md` is unsupported.** Official current Cursor documentation supports `.cursor/rules`, `AGENTS.md`, and `.cursorrules` legacy behavior, but no `CURSOR.md` contract was found.
- **Cursor local and cloud attribution differ.** Local Agent adds configurable default trailers and PR footers. Cloud Agents use the `Cursor Agent` identity and verified signatures.
- **OpenCode v1 and v2 cannot share an undated detector.** V2 uses current configuration files and detached worktrees with no native core attribution. The branch, bot, email, and generated footer belong to V1/history.
- **OpenCode’s current attribution-like trailers are plugin-only.** They are not core V2 defaults.
- **Pi’s `PI_ATTRIBUTION` is not Git attribution.** It labels outbound model-provider requests. Pi core has no native Git identity, trailer, branch, footer, bot, label, or issue trigger.
- **Oh My Pi and robomp must be separated.** robomp’s branch namespace is stable, but its bot and Git identities are deployment-configurable, and its labels are workflow evidence rather than core OMP evidence.
- **OpenClaw co-author trailers credit people.** They are not a product co-author marker.
- **OpenClaw’s optional PR footer is default-off.** It cannot be treated like Cursor’s default-on local footer.
- **`openclaw@localhost` required historical reconciliation.** Public ordinary-history matches begin on `2026-02-12`, while the current synthetic-worktree implementation was added in September; v2026.2.12 contains no matching default.
- **`.claw.json` was not simply obsolete.** It remains compatibility input and scaffold output, while `.claw/` contains the stronger current surfaces.
- **`.vibe/tools/` is retired.** Current Vibe only warns about it.
- **OpenHands planning does not default to `.openhands/PLAN.md`.** The current default is `.agents_tmp/PLAN.md`; root `PLAN.md` is a legacy fallback; `.openhands/PLAN.md` is configurable/test evidence.
- **`openhands-agent` is not the current primary review identity.** Current automation uses `all-hands-bot` with `review-this`; `openhands-agent` is historical/example evidence and unsafe in shared author/activity matching.

---

## 23. Source Snapshot Provenance

| Product/source | Pinned revision or version |
|---|---|
| Orca | `492ccce634795c6c36a448c652054e1a52adbee1` |
| DeepSeek Harness | `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159` |
| Paperclip | `0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2` |
| Herdr | `ee5bfb5041bb3e4a49d591c72308aae3c81ecdde` |
| Herder | `701a5b527d486863442b9a3de218e6c02af0e2a4` |
| Hermes Agent | `444f980868937926562fe5652d26364d45550960` |
| Command Code distributed package | `command-code@1.88.5` |
| Command Code public source snapshot | `630bbf418f62bcdea627e57e6dca60151452355b` |
| Cursor | official documentation as observed on `2026-11-08` |
| Ghostty | `e035beb9437118b803830a5864ea2f4dd7094354` |
| OpenCode v2 | `3ce4ca464dbbd993eb9c3158f7e77cddd80774fb` |
| OpenCode v1 | `c90281c0d6e6a92309d8d326e732931b92739cdf` |
| Pi | `5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c` |
| Oh My Pi | `33a063ce79dfc24d3a99786283d01f6ed127703c` |
| OpenClaw current | `476cce7a8a343ac1524bf12276da839a690cff8a` |
| OpenClaw historical comparison | `v2026.2.12` |
| Claw Code | `ca48ec75003da7f64a0780996c2ba6e71f78daea` |
| Mistral Vibe | `c96a6dbb34d34f8a868b3f67b279ecabbf1aa616` |
| OpenHands | `cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05` |
| OpenHands Software Agent SDK | `e6569442a23951f852ead8514ae51dff1b377f37` |

---

## 24. Coverage Appendix

This appendix is the inventory safeguard for findings that do not fit cleanly into one product matrix.

### 24.1 Detector semantics that affect every recommendation

- File matching is case-sensitive. Patterns are prefixed with `(?:^|/)` unless already explicitly anchored, but are not automatically end-anchored. A literal-looking `opencode.json` therefore needs deliberate end anchoring if `opencode.jsonc` should be separately classified.
- Branch and label patterns are case-sensitive and substring-matched unless the pack supplies anchors.
- Author patterns are case-insensitive and reused for commit author/committer identities, PR authors, and issue participants.
- Ambiguous one-word author patterns such as `cursor` receive special login handling, but bot suffix normalization can still collapse `cursor[bot]` to `cursor`.
- Commit-message extraction recognizes a fixed trailer-token list and a broad “generated/made/built … with/by/using” footer form. Exact emails can also be found by a fallback scan of the whole message.
- A custom token such as `Herder-Session:` cannot be represented without adding a broad `Herder` author pattern, which would alter unrelated channels.
- API history is the last 100 commits. PR metadata is the most recent 100 PRs, with up to 20 labels, 50 comments, and 100 commits per PR. Issue activity is the most recent 100 issues, with up to 10 assignees and 50 comments.
- Clone mode can inspect a configurable commit window, fetched PR refs, merge-message branch names, and remote `refs/heads/*`; it does not enumerate arbitrary hidden namespaces.
- Bot exclusion protects commit-ratio calculations only. It does not make PR authors, commenters, or issue participants bot-safe.
- Deduplication is exact over serialized `(agent, channel, evidence)`, so the same underlying product can still produce several distinct hits and channels.
- Adoption levels are windowed: `experimental` below 1%, `limited` below 5%, `consistent` below 20%, and `pervasive` at or above 20% of non-noise, non-excluded-bot commits.

### 24.2 Product-layer distinctions

- **Wrapper/orchestrator:** Orca coordinates agents and worktrees. Its downstream agent’s trailer is not Orca evidence.
- **Orchestrator with native session metadata:** Herder adds a session trailer and checkpoint refs, even though a downstream coding agent may author the code.
- **Terminal:** Ghostty transports terminal I/O and emits no native repository attribution.
- **Core versus subcomponent:** Oh My Pi core and `python/robomp` have different fingerprints and deployment assumptions.
- **Core versus plugin:** OpenCode v2 core emits no native Git attribution; plugin trailers must be attributed to the plugin configuration.
- **Provider telemetry versus Git:** Pi’s outbound request attribution is not repository evidence.

### 24.3 Open questions

- **Unverified:** the emitter responsible for ordinary public `openclaw@localhost` commits before the current synthetic-worktree implementation. The two plausible readings and recommendation are preserved in Section 15.
- Exact global prevalence was not measured for every source-verified optional branch, ref, and file. “Source-only; n=1” is deliberately not converted into an adoption estimate.
- Search totals are snapshots of an external index and will drift. Reproduction should record the query time, `total_count`, `incomplete_results`, rate-limit state, and the number of retrievable results sampled.
- Absence of a fingerprint never proves absence of product use: attribution can be disabled, local state can remain uncommitted, and history/API windows can miss older activity.

### 24.4 Preservation check

All sixteen requested products appear in dedicated sections. All retained exact strings, counts, source pins, current-versus-legacy corrections, wrapper/downstream distinctions, schema gaps, and the one unresolved OpenClaw-origin question appear either in the product matrices, closing recommendations, methodology companion, or this appendix.
