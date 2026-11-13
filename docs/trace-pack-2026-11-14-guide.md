# The 2026-11-14 Coding-Agent Trace Pack: A Complete Human Guide

**Status:** implementation guide for the proposed lifecycle-aware trace pack  
**Guide date:** 2026-11-14  
**Proposed pack version:** `2026-11-14`  
**Proposed artifact:** `packs/2026-11-14.json`  
**Current state:** researched and specified; the JSON pack has not been built yet  
**Frozen predecessors:** `packs/2026-10-14.json` and `packs/2026-10-19.json`  
**Normative audit:** [`findings/2026-11-13-agent-pack-reaudit.md`](findings/2026-11-13-agent-pack-reaudit.md)  
**Research methodology:** [`findings/2026-11-08-agent-fingerprint-methodology.md`](findings/2026-11-08-agent-fingerprint-methodology.md)

---

## How to use this guide

- **First-time reader:** read Sections 1–7 for the mental model, terminology, counts, and complete catalogue.
- **Researcher or analyst:** continue through Sections 8–19 for channels, lifecycle, evidence semantics, and metrics.
- **Implementer:** focus on Sections 10, 14, and 20–23 for schema requirements, build behavior, sequencing, and acceptance criteria.
- **Quick lookup:** use Section 25 for frequently asked questions and Section 26 for the underlying research documents.

The guide explains the system in plain language first. Code, regex, and schema examples appear only where they remove ambiguity.

---

## 1. The short version

This trace pack is a versioned knowledge base of repository-visible evidence left by coding agents.

It is designed to answer questions such as:

- Has this repository ever contained evidence of a particular coding agent?
- Is that evidence current, deprecated, historical, or ambiguous?
- Does the evidence prove configuration, activity, authorship, review, or only orchestration?
- Which current product lineage should an old product name roll up to?
- Should the evidence affect current adoption statistics or only historical reporting?

The proposed catalogue contains:

```text
78 active canonical product lineages
├── 72 detectable with the present matcher
│   ├── 47 normalized active lineages from the previous pack
│   └── 25 newly recognized current-matcher-detectable lineages
└── 6 active lineages that require matcher/schema v2
```

The catalogue also preserves verified historical fingerprints for retired products and predecessor versions. Those historical rules do **not** increase the active-family count or imply current use.

The pack is not a list of AI-related words. A rule is accepted only when official documentation, product source, a distributed implementation, or product-controlled source-control activity establishes what emits it and what it means.

---

## 2. The mental model

The easiest way to understand the system is as a hierarchy:

```text
Pack
└── Family (canonical product lineage)
    ├── Surface (CLI, IDE, cloud agent, reviewer, desktop app)
    ├── Variant or predecessor
    └── Rules
        └── Fingerprints
            └── Evidence found in a repository
```

For example:

```text
Family: Abacus AI Agent / Coding Agent

Surfaces and lineage:
├── DeepAgent                      predecessor name
├── Abacus AI Agent               hosted agent surface
├── Abacus AI Coding Agent        current coding product
├── Abacus.AI CLI                 terminal surface
└── Abacus AI VS Code extension   editor surface

Fingerprints:
├── agent@abacus.ai
├── .abacusai/config.json
├── .abacusai/mcp.json
├── .abacusai/skills/<name>/SKILL.md
└── .abacusai/hooks/**
```

Those names and surfaces count as one family because they belong to one canonical product lineage.

When a repository contains an actual matching artifact, the detector records **evidence**. A definition in the pack is not evidence by itself.

---

## 3. Core vocabulary

### 3.1 Family

A **family** is the canonical product lineage used for counting and reporting.

It may combine:

- a current product name;
- predecessor names;
- rebrands;
- CLI, desktop, IDE, and cloud surfaces;
- variants that share the same underlying product lineage;
- compatibility paths retained after a rename.

“Family” is shorthand for **canonical agent product lineage**.

### 3.2 Surface

A **surface** is one way a family is delivered or participates in software work.

Examples:

- local CLI;
- VS Code extension;
- desktop application;
- cloud coding worker;
- pull-request reviewer;
- issue-to-PR agent;
- orchestrator;
- hosted app builder.

A family may have several surfaces without becoming several families.

### 3.3 Variant

A **variant** is a specialized implementation that should roll up to its parent family.

Example: `dsh-superagent` is a DeepSeek Harness variant, not an additional family.

### 3.4 Fingerprint

A **fingerprint** is an artifact that may survive in a repository or source-control system.

Examples:

- `.abacusai/config.json`;
- `agent@abacus.ai` as a Git author email;
- `Co-Authored-By: Replit Agent <agent@replit.com>`;
- `command-code/<id>` as a generated branch;
- a product-owned hidden ref;
- a workflow file containing a product-specific action;
- a product-specific custom commit trailer.

A fingerprint can be current, deprecated, historical, optional, recovery-only, anomalous, ambiguous, or unsafe.

### 3.5 Rule

A **rule** tells the detector how and where to recognize a fingerprint.

A complete rule needs more than a regular expression. It should eventually describe:

- channel;
- pattern or structured predicate;
- canonical family;
- observed product name or variant;
- lifecycle interval;
- evidence semantics;
- confidence and collision risk;
- whether it can affect authorship or adoption metrics;
- provenance.

### 3.6 Evidence

**Evidence** is a concrete match found during a scan.

Examples:

- path `.abacusai/config.json` exists in repository `o/r`;
- commit `abc123` has author email `agent@abacus.ai`;
- branch `command-code/7f3a` exists;
- a lockfile contains a GitHub Agentic Workflows metadata header.

Rules are reusable definitions. Evidence is repository-specific observation.

### 3.7 Pack

A **pack** is an immutable, versioned snapshot of families, rules, lifecycle metadata, and provenance.

Detection loads one selected pack. A new pack is a complete snapshot, not a runtime patch layered over an older pack.

### 3.8 Detector

The **detector** is the software that:

1. loads a pack;
2. collects repository and forge data;
3. evaluates rules;
4. records evidence;
5. rolls evidence up to families;
6. computes historical and current metrics.

The pack is research data. The detector is the execution engine.

### 3.9 Evidence strength

The audit uses three positive evidence strengths:

- **Strong:** product-specific enough to stand alone in its intended channel.
- **Corroborating:** useful support, but normally not enough by itself.
- **Composite-only:** reliable only when combined with another path, content value, role, identity, ref, or related file.

“Strong” does not mean universal. A strong fingerprint may be optional or removable, so absence still does not prove non-use.

### 3.10 Product layer or role

Families and evidence can occupy different layers:

- **executor:** edits or generates code;
- **reviewer:** reviews code and may optionally propose fixes;
- **orchestrator:** coordinates other agents, branches, sessions, or worktrees;
- **host:** provides the editor, terminal, machine, or transport;
- **framework:** supplies reusable agent-building infrastructure;
- **downstream agent:** performs work launched by another layer.

The layer determines what a hit may claim. An orchestrator config can prove orchestrator presence while contributing nothing to commit authorship.

---

## 4. Why families are necessary

Product names are not stable. A naive tool list would double-count renames, variants, and product surfaces.

The family model prevents that.

| Historical or duplicate names | Canonical family treatment |
|---|---|
| Alibaba Lingma | Qoder (Alibaba) predecessor |
| Gemini consumer CLI and current enterprise surfaces | Google Antigravity / Gemini Code Assist lineage |
| Roo Code | Zoo Code predecessor and compatibility lineage |
| Sketch | Shelley predecessor |
| Windsurf | Devin / Devin Desktop lineage |
| Amazon Q CLI | Kiro lineage |
| Rovo Dev | Atlassian Rovo CLI lineage |
| Fly + Phoenix | Phoenix.new (Fly.io) |
| CopilotSwe | Copilot |
| Factory | Factory Droid |
| DeepAgent | Abacus AI Agent / Coding Agent predecessor |
| dsh-superagent | DeepSeek Harness variant |

This lets the detector report both the historical form and the canonical family:

```text
Canonical family: Abacus AI Agent / Coding Agent
Observed as: DeepAgent
Rule status: historical name, current identity
Evidence: agent@abacus.ai
```

---

## 5. The four catalogue numbers

The count labels refer to different subsets. They are not four numbers to add together.

### 5.1 Current-matcher-detectable active families: 72

These are current product families with at least one reliable fingerprint that the present collection and matching model can recognize.

The formula is:

```text
47 normalized active incumbents
+ 25 current-matcher-detectable additions
= 72
```

This classification concerns the family's **core matching predicate**. A family may also have richer traces that still require v2.

Example: Abacus is current-matcher-detectable through `agent@abacus.ai` and `.abacusai/config.json`, while its exact `noreply@abacus.ai` name-plus-email trailer is a v2 enrichment.

### 5.2 New current-matcher-detectable additions: 25

These are the newly canonicalized families inside the 72.

“Addition” means a new canonical family row relative to the normalized previous `tools.csv` roster. It does not always mean no old regex existed. Abacus, for example, had orphan patterns but no canonical tool row.

The 25 additions are a subset of the 72:

```text
72 already includes the 25 additions.
Do not calculate 72 + 25.
```

### 5.3 Matcher/schema-v2-gated active families: 6

These are real, current products with good evidence, but all safe detection paths require capabilities absent from the present flat matcher.

The limitation is the detector, not the product or evidence quality.

### 5.4 Total active product catalogue: 78

This is the current-product count:

```text
72 current-matcher-detectable
+ 6 matcher-v2-gated
= 78 total active families
```

“Active” is a product-lifecycle classification. It does not mean every family can be fully detected today.

---

## 6. The complete active roster

### 6.1 The 47 normalized active incumbents

These lineages come from the previous catalogue after duplicates, aliases, and transitions are normalized.

1. Aider
2. Qoder (Alibaba; Lingma successor)
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

### 6.2 The 25 current-matcher-detectable additions

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

### 6.3 The six matcher-v2-gated active families

1. GitLab Duo Agent Platform
2. Orca
3. T3 Code
4. GitHub Agentic Workflows
5. PR-Agent
6. Herder

---

## 7. Other catalogue groups

These groups are intentionally outside the active-family count.

### 7.1 Legacy-only families: 6

1. Brokk
2. Continue
3. GPT-Engineer
4. Sweep
5. Claw Code
6. DeepSeek Reasonix

Their verified fingerprints remain useful for historical detection. They receive no current-family weight.

### 7.2 Watch: 5

1. ChatGPT
2. Azad
3. Zed Agent
4. Herdr
5. claude-flow / Ruflo

These are current or relevant products without a sufficiently reliable durable repository trace.

Watch does not mean unimportant. It means the detector should not manufacture certainty.

### 7.3 Adjacent: 12

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

These may be methodologies, planning systems, frameworks, context tools, version-control infrastructure, or broad workspaces. They can be measured in separate inventories, but they should not inflate coding-agent authorship.

### 7.4 Excluded: 4

1. LazyCodex
2. Dori superagent
3. Aperant
4. Odysseus Workshop

These lack a distinct durable trace, are thin bundles over other products, deliberately avoid repository state, or are educational artifacts rather than substantive deployed products.

### 7.5 Folded variant: 1

`dsh-superagent` rolls up to DeepSeek Harness.

### 7.6 Generic pseudo-family: 1

`Generic` classifies shared evidence such as `AGENTS.md` or an `ai-generated` label.

It is not a vendor or product. It must never convert a shared standard into product attribution.

### 7.7 Negative control: 1

Ghostty is retained as a negative control.

Ghostty is a terminal. A coding agent running inside Ghostty leaves the coding agent's fingerprints, not Ghostty fingerprints. This tests whether the detector respects layer boundaries.

---

## 8. What the present matcher can see

The current pack format has five pattern lists:

1. authors;
2. files;
3. branches;
4. labels;
5. bots.

The detector exposes additional evidence channels by applying those patterns to collected data:

| Evidence channel | Typical source | What it can establish |
|---|---|---|
| File | Repository tree and selected ignored paths | Configuration or product surface present |
| Author/committer | Recent Git history | Authorship when identity is exact |
| Commit trailer | Commit message | Co-authorship or product-specific metadata |
| Branch | Recent branches and PR heads | Product workflow or execution mode |
| Label | Pull-request labels | Workflow activity, rarely authorship |
| Bot | Commit/forge identity | Usually automation classification or noise exclusion |
| PR metadata | PR body, head branch, author, labels | Review, task, or generation workflow |
| Issue activity | Issue authors, assignees, participants | Invocation or participation, not automatically authorship |

In the current format, `bots.csv` primarily identifies generic CI/release noise for exclusion and QA. A product-owned account belongs in positive attribution only when its role is proven—usually through an exact commit identity—not merely because it has a `[bot]` suffix.

The present matcher is mostly “regex plus family name.” It cannot safely express every condition a source contract needs.

---

## 9. Why six families require matcher v2

### 9.1 GitLab Duo Agent Platform

The candidate branch shape is product-specific only in GitLab context:

```regex
^duo/(?:fix|feature|refactor|docs)/.+$
```

Safe detection requires:

- GitLab-native collection;
- service-account identity;
- merge-request role semantics;
- separation of orchestration/review from authored code.

GitHub assumptions cannot be projected onto GitLab.

### 9.2 Orca

The filename `orca.yaml` collides with unrelated chemistry, robotics, and workflow projects.

Safe detection requires root `orca.yaml` plus Orca-specific content such as:

- `setupAgentStartupPolicy`;
- `environmentRecipes`;
- `issueCommand`;
- `defaultTabs`;
- `worktree.sharedDirectories`;
- Orca setup/archive scripts.

That requires a path-plus-content predicate.

### 9.3 T3 Code

The root filename `t3.json` is too generic.

Safe detection requires the exact JSON schema value:

```text
https://t3.codes/schema/t3.json
```

That requires structured JSON content matching.

### 9.4 GitHub Agentic Workflows

Safe evidence requires either:

- a Markdown workflow source and same-stem lockfile; or
- lockfile content beginning with `# gh-aw-metadata:`.

That requires file relationships or bounded content matching.

### 9.5 PR-Agent

Qodo and open-source PR-Agent share `.pr_agent.toml`.

Safe separation requires workflow or image content such as:

```text
uses: the-pr-agent/pr-agent@...
pragent/pr-agent
```

A path-only rule would misclassify Qodo as PR-Agent or vice versa.

### 9.6 Herder

Herder's strongest evidence includes:

- custom `Herder-Session:` trailers;
- `refs/herder/**` checkpoint refs;
- checkpoint identity valid only under those refs.

The current collector does not enumerate arbitrary hidden refs, and the flat matcher cannot scope an identity to a ref.

---

## 10. What matcher/schema v2 must add

### 10.1 Structured content predicates

The detector needs bounded parsing for:

- JSON;
- YAML;
- TOML;
- workflow `uses:` values;
- exact schema URLs;
- bounded text markers.

### 10.2 Conjunctions and relationships

Rules need constructs such as:

- `allOf`;
- `anyOf`;
- `minMatches`;
- same-stem files;
- same-tree files;
- same commit;
- same PR;
- same ref;
- identity plus ref.

### 10.3 Structured trailers

The detector must preserve:

- trailer token;
- trailer value;
- co-author name;
- co-author email;
- message location;
- product-specific value semantics.

Examples:

- `Herder-Session: ...`;
- `Replit-Commit-Author: Agent` versus `Deployment`;
- `Abacus AI Agent <noreply@abacus.ai>` as an exact name-plus-email conjunction.

### 10.4 Hidden refs

The collector needs targeted support for product-owned namespaces without fetching every arbitrary Git object.

Synthetic identities must remain scoped to the operation/ref that owns them.

### 10.5 Forge and role scope

The detector must distinguish:

- GitHub, GitLab, Bitbucket, Azure DevOps, and local Git;
- commit author and committer;
- co-author;
- PR author, reviewer, and commenter;
- issue author, assignee, and commenter;
- service account;
- generated workflow identity.

### 10.6 Lifecycle and lineage

Every rule needs lifecycle and family relationships. See Section 14.

### 10.7 Provenance and confidence

Every rule should retain:

- canonical source URL;
- pinned source version or commit;
- source path;
- check date;
- source type;
- evidence strength;
- collision risk;
- known false-positive and false-negative hazards.

---

## 11. The 25 additions and their primary current signals

This section is a human summary. The normative audit contains the complete recommended regexes and caveats.

| Family | Primary current evidence | Important boundary |
|---|---|---|
| Builder.io Fusion | Root `.builderrules` | Builder bot comments are activity, not necessarily authorship |
| cubic | Exact Cubic bot commit email | `cubic.yaml` needs content validation |
| Greptile | `.greptile/config.json`, `.greptile/rules.md`, or `greptile.json` | Review comments are not generated-code authorship |
| Kody AI | Root `kodus-config.yml` | `@kody` commands need comment-body and authorization scope |
| Lovable | Exact generated bot email; `lovable-sync...` recovery branches | Recovery branches are not ordinary execution frequency |
| Paperclip | `noreply@paperclip.ing`; rescue branch | `.paperclip.yaml` needs `schema: paperclip/v1` for precision |
| Hermes Agent | `.hermes.md`, `HERMES.md`, `.hermes/plans/**`, generated Hermes branch | Archive identity requires archive-ref context |
| Command Code | `.commandcode/**`, `noreply@commandcode.ai`, cloud branch | Generic local `worktree-*` is unsafe |
| Oh My Pi | `.omp/**` project paths | Generic `wt/*` and `pr-*` branches are unsafe |
| OpenClaw | `.openclaw/worktree-setup.sh`, `openclaw/*` branches | Workspace files require a conjunction; downstream commits stay downstream |
| Gajae-Code | `.gjc/**` project paths | Task branch is optional and default-disabled |
| Docker Agent | `docker-agent.yaml`, `.yml`, or `.hcl` | Generic `agent.yaml` needs content validation |
| OpenCodeReview | `.opencodereview/rule.json` | User-home config is usually outside repository scans |
| DeepSeek Harness | `.dsh/skills/**` | Experimental branches are optional; generic `.agents/**` is shared |
| Grok Build | Supported `.grok/**` config, workflow, and resource paths | Community `.grok/settings.json` is not a product contract |
| Prime Agent | `.prime/agent/**` config, prompts, and skills | Product deliberately avoids replacing Git identity |
| JCode | `.jcode/**` project config and skills | Product does not supply a native Git identity |
| Xiaomi MiMo Code | `.mimocode/**` config, workflows, and skills | Use product-specific paths, not model names |
| Freebuff / Codebuff | `.codebuffignore`, `.freebuffignore`, `.manicodeignore`; `noreply@codebuff.com` | Attribution can be suppressed; ignore files have different semantics |
| oh-my-claudecode | `.claude/omc.jsonc`, `.omc/skills/**` | Orchestrator does not inherit Claude Code commits |
| Archon | `.archon/**` config, workflow, pack, and policy paths | Identifies orchestration/configuration, not downstream authorship |
| Kimi Code CLI | `.kimi-code/**` project config, agents, and skills | Old `.kimi/**` belongs to archived predecessor lineage |
| Roomote | Exact generated-commit email | Bare `roomote` login is not equivalent to authorship |
| Replit Agent | Root `replit.md`; exact `agent@replit.com` | `.replit` and per-user Replit email identify platform/user, not Agent |
| Abacus AI Agent / Coding Agent | Exact `agent@abacus.ai`; `.abacusai/**` project contracts | Release bot is noise; external checkpoints are not target-repository evidence |

---

## 12. Two worked audits

### 12.1 Replit Agent

Strong current evidence includes:

```regex
^replit\.md$
```

and the bounded exact email:

```regex
(?:^|<)agent@replit\.com(?:>|$)
```

The custom trailer below is stronger execution evidence but requires structured handling:

```text
Replit-Commit-Author: Agent
```

It must remain distinct from:

```text
Replit-Commit-Author: Deployment
```

Unsafe shortcuts include:

- `.replit`;
- `replit.nix`;
- `.replit-artifact/**`;
- per-user `*@users.noreply.replit.com` identities.

Those identify the Replit platform, runtime, artifact system, or user-scoped Git configuration—not necessarily Agent work.

### 12.2 Abacus AI Agent / Coding Agent

Strong exact identity:

```regex
(?:^|<)agent@abacus\.ai(?:>|$)
```

Strong project paths:

```regex
^\.abacusai/(?:config\.json|mcp\.json)$
^\.abacusai/skills/[^/]+/SKILL\.md$
^\.abacusai/hooks/.+$
```

The old pack also contained:

```text
abacus-ai-automation[bot]
```

That identity is release/CI automation. It publishes product release manifests and assets. It is not coding-agent authorship and must move to a rejection/noise classification.

The current composite trailer below is valid only as exact name-plus-email evidence:

```text
Co-Authored-By: Abacus AI Agent <noreply@abacus.ai>
```

The email alone is too broad.

The distributed CLI also contains an internal checkpoint identity and refs, but official docs say the checkpoint store lives outside the project and never writes the target `.git`. Those internal artifacts are therefore outside repository detection scope.

---

## 13. Historical fingerprints are preserved

The new pack follows an append-only principle for **verified** fingerprints:

> A product stopping emission of a fingerprint does not erase repositories that already contain it.

Instead of deletion, the rule receives lifecycle and semantic metadata.

### 13.1 Current

The product currently emits or officially supports the fingerprint.

It may establish current presence and, for exact execution identities, authorship.

### 13.2 Deprecated

The product still recognizes the fingerprint, but a newer form is preferred.

It may still indicate current compatibility.

### 13.3 Legacy

The fingerprint belongs to an earlier product generation or predecessor.

It remains valid historical evidence but does not establish current use.

### 13.4 Retired

The product or standalone family is no longer active.

Dated historical commits can still be attributed when the rule was valid at the commit time.

### 13.5 Compatibility

A successor still accepts the old surface.

Example: `.roo/**` remains a current Zoo Code compatibility path while also preserving Roo lineage.

### 13.6 Optional

The fingerprint is real and current but emitted only when a feature or mode is enabled.

Its presence is meaningful. Its absence says nothing about ordinary product use.

### 13.7 Recovery-only

The fingerprint belongs to rescue, rollback, archive, checkpoint, or divergence recovery.

It can identify the product strongly but must not be presented as normal session frequency.

### 13.8 Anomalous

The artifact is product-associated but unexpected in the scanned channel—for example, normally ignored local state committed to the repository.

An anomalous hit should be visible to investigators without becoming ordinary adoption evidence.

### 13.9 Invalid or unsafe

Some old patterns were never reliable fingerprints.

Examples:

- unsupported `CURSOR.md`;
- broad `Claude`, `ChatGPT`, `Codex`, or `AI Assistant` identities;
- broad `.qodo/`;
- reviewer/release bots treated as authorship;
- duplicate rows.

These belong in a rejection ledger with an explanation. They do not remain positive historical detections because doing so would preserve false attribution rather than history.

---

## 14. The lifecycle model

Each rule should eventually carry fields equivalent to:

```yaml
id: abacus.primary-agent-email
family: abacus-ai-agent
observed_as: Abacus AI Agent
surface: git_identity
channel: commit_author_or_trailer

match:
  regex: '(?:^|<)agent@abacus\.ai(?:>|$)'

lifecycle:
  status: current
  valid_from: '2025-09-05'
  valid_until: null

semantics:
  evidence: authorship
  counts_as_repository_presence: true
  counts_as_current_presence: true
  counts_as_authorship: true
  counts_in_current_ratio: true

lineage:
  aliases:
    - DeepAgent
    - Abacus.AI CLI
  rollup_family: abacus-ai-agent

confidence:
  class: strong
  collision_risk: low

provenance:
  checked_at: '2026-11-14'
  source_type: observed_product_controlled_scm_identity
```

The precise serialization can change. The semantic distinctions should not.

### 14.1 Applying validity to dated evidence

Commit, PR, issue, and branch events often have timestamps.

If a commit matched a rule during that rule's valid interval, it can remain historically attributed even after the rule is retired.

Example:

```text
2025 OpenCode-v1 commit
Fingerprint: noreply@opencode.ai
Result: historical OpenCode v1 authorship
Current OpenCode-v2 presence: not established
```

### 14.2 Current-tree files have weaker chronology

A file in the current tree may be old residue.

If an expired file fingerprint is still present and the detector does not fetch its introduction history, report:

```text
Legacy marker present; current use unknown.
```

Do not silently convert old configuration residue into current adoption.

---

## 15. Evidence semantics

Not all evidence proves the same thing.

### 15.1 Configuration

A project file usually proves that the repository is configured for, compatible with, or intended for a product.

It does not automatically prove execution or authorship.

### 15.2 Activity

A bot comment, review, label, or issue command may prove product activity.

It does not automatically prove generated code.

### 15.3 Authorship

An exact Git author, committer, or required co-author identity can establish commit-level attribution.

Exact role and channel matter.

### 15.4 Review participation

A review bot may inspect code without writing it.

Review evidence should not enter generated-code or commit-adoption counts unless a separate exact authored commit exists.

### 15.5 Orchestration

An orchestrator may launch Claude Code, Codex, or another downstream agent.

The orchestrator's project config proves orchestration presence. It does not inherit downstream authorship.

### 15.6 Recovery and checkpoint activity

Recovery branches and hidden refs may be excellent product fingerprints, but they describe exceptional modes rather than normal usage frequency.

### 15.7 Host or transport

A terminal, IDE shell, or cloud machine may host an agent without leaving native authorship evidence.

The host does not inherit the agent's commits, and the agent does not inherit unrelated host activity.

---

## 16. Non-negotiable attribution boundaries

1. **Configuration is not execution.**
2. **Execution is not necessarily authorship.**
3. **Review participation is not authorship.**
4. **A bot login is not the same evidence type as a commit email.**
5. **A wrapper or orchestrator does not inherit downstream commits.**
6. **A terminal does not inherit the program running inside it.**
7. **A shared format does not identify the product that consumed it.**
8. **A recovery marker does not measure normal usage frequency.**
9. **A user-selected identity is not an official product contract.**
10. **Absence of a fingerprint does not prove absence of product use.**

---

## 17. From evidence to repository results

A useful detector should maintain several separate rollups.

### 17.1 Ever observed

Any verified current or historical evidence exists.

### 17.2 Currently configured

A current project-level rule matches.

This still does not prove execution.

### 17.3 Historical activity

Dated activity matches a rule during its valid lifecycle interval.

### 17.4 Current activity

Recent activity matches a current rule in the correct role and channel.

### 17.5 Authored commits

Specific commits carry exact authorship evidence.

### 17.6 Legacy residue

An expired file marker remains in the current tree, but current use cannot be established.

### 17.7 Example output

```json
{
  "family": "abacus-ai-agent",
  "family_name": "Abacus AI Agent / Coding Agent",
  "observed_as": "DeepAgent",
  "channel": "author",
  "evidence": {
    "commit": "abc123",
    "field": "email"
  },
  "rule_status": "current",
  "evidence_semantics": "authorship",
  "counts_as_current_presence": true,
  "counts_as_authorship": true,
  "counts_in_current_ratio": true
}
```

Historical file residue would look different:

```json
{
  "family": "qoder",
  "family_name": "Qoder (Alibaba)",
  "observed_as": "Lingma",
  "channel": "file",
  "evidence": {
    "path": ".lingma/settings.json"
  },
  "rule_status": "legacy",
  "evidence_semantics": "historical_lineage",
  "counts_as_current_presence": false,
  "counts_as_authorship": false,
  "counts_in_current_ratio": false,
  "note": "Legacy marker present; current use unknown"
}
```

---

## 18. Adoption metrics

### 18.1 Active-family count

The active-family count is a product catalogue count: 78.

It is not the number of rules, aliases, files, emails, or pack rows.

### 18.2 Current-matcher-detectable count

This is the number of active families with at least one safe present-matcher rule: 72.

### 18.3 Commit-adoption ratio

The existing detector computes a windowed ratio from recently collected commits.

Only evidence explicitly allowed to count as authorship should enter the numerator.

Configuration, review comments, orchestration, generic labels, and legacy residue must not enter that numerator.

### 18.4 Historical attribution

A historical commit can remain AI-attributed when its timestamp falls inside a verified rule's lifecycle interval.

Historical attribution and current-product presence are separate dimensions.

### 18.5 Rule count is not family count

One family may have many rules. One rule may be historical. One ambiguous artifact may not conclusively select any family.

Never use the number of regexes as the number of products.

---

## 19. Handling ambiguity

Some artifacts prove that an ecosystem or lineage exists without identifying one family conclusively.

Example: `.pr_agent.toml` is shared by Qodo and PR-Agent.

The correct output without discriminating content is:

```text
Ambiguous Qodo / PR-Agent lineage
```

The incorrect output is to claim both products independently.

Other ambiguity controls include:

- exact root anchoring;
- exact leaf names;
- content schemas;
- same-stem relationships;
- name-plus-email trailer conjunctions;
- forge scope;
- role scope;
- validity intervals;
- successor rollups.

---

## 20. The new pack is a full snapshot

The proposed `2026-11-14` pack is not a patch over `2026-10-19`.

It is a complete replayable artifact containing every intended current and verified historical rule.

### 20.1 Old packs remain immutable

The following files must remain byte-for-byte unchanged:

- `packs/2026-10-14.json`;
- `packs/2026-10-19.json`.

Existing detection runs remain bound to the pack version used at run time.

### 20.2 Verified history remains in the new pack

The new pack should retain verified historical fingerprints with lifecycle metadata.

Examples:

- OpenCode-v1 identities and branch lineage;
- `.lingma/**`;
- `hello@sketch.dev`;
- pre-transition Amazon Q CLI evidence;
- retired standalone product fingerprints;
- deprecated but supported compatibility paths.

### 20.3 Invalid rules do not become history

Unsupported or overly broad rules remain documented in a rejection ledger but do not produce positive evidence.

Preserving known false attribution would not preserve history; it would preserve an error.

### 20.4 Proposed build command

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m detect.packs build `
  --src packs\patterns `
  --version 2026-11-14 `
  --out packs\2026-11-14.json
```

The builder and serializer must first be extended to retain lifecycle and semantic metadata. Building the old flat `{pattern, agent}` representation would lose the central historical/current distinction.

---

## 21. A proposed lifecycle-aware rule shape

The final schema may differ, but it needs equivalent expressive power:

```yaml
schema_version: 2

families:
  - id: abacus-ai-agent
    name: Abacus AI Agent / Coding Agent
    status: current
    aliases:
      - Abacus.AI CLI
      - Abacus AI Coding Agent
    predecessors:
      - DeepAgent

rules:
  - id: abacus.primary-agent-email
    family: abacus-ai-agent
    surface: git_identity
    channel: author

    match:
      regex: '(?:^|<)agent@abacus\.ai(?:>|$)'

    lifecycle:
      status: current
      valid_from: '2025-09-05'
      valid_until: null

    semantics:
      evidence: authorship
      counts_as_repository_presence: true
      counts_as_current_presence: true
      counts_as_authorship: true
      counts_in_current_ratio: true

    confidence:
      class: strong
      collision_risk: low

    provenance:
      checked_at: '2026-11-14'
      source_type: observed_product_controlled_scm_identity

  - id: abacus.release-bot-rejection
    family: null
    surface: release_automation
    channel: author

    match:
      regex: '^194430910\+abacus-ai-automation\[bot\]@users\.noreply\.github\.com$'

    lifecycle:
      status: current

    semantics:
      evidence: release_automation
      counts_as_repository_presence: false
      counts_as_current_presence: false
      counts_as_authorship: false
      counts_in_current_ratio: false

    disposition: rejected_as_coding_agent_evidence
```

---

## 22. Implementation order

### Phase 0: correctness foundations

1. Preserve old pack files and digests.
2. Add lifecycle and semantic fields while keeping old packs loadable.
3. Normalize family IDs, aliases, predecessors, variants, and successors.
4. Fix unsupported, broad, duplicate, and orphan rules.
5. Separate exact commit identities from forge participants.
6. Test exact identity matching in author, committer, and trailer contexts.
7. Add a rejection ledger for known unsafe hypotheses.

### Phase 1: 72 current-matcher-detectable active families

1. Normalize the 47 active incumbents.
2. Add the 25 current-matcher-detectable families.
3. Retain verified historical rules with zero current weight.
4. Keep optional and recovery-only rules explicitly classified.
5. Build and freeze `2026-11-14` under a new version.
6. Verify the active count is exactly 72.

### Phase 2: matcher and collector v2

Implement:

- structured content predicates;
- conjunctions;
- custom trailer semantics;
- hidden-ref enumeration;
- forge and role scope;
- targeted comment-body collection;
- lifecycle-aware rollups;
- provenance and confidence fields.

### Phase 3: activate the six gated families

Activate:

- GitLab Duo Agent Platform;
- Orca;
- T3 Code;
- GitHub Agentic Workflows;
- PR-Agent;
- Herder.

Verify the active count becomes exactly 78.

### Phase 4: replay and false-positive review

Replay against a labeled corpus and inspect:

- exact emails outside source repositories;
- generic-looking paths across unrelated ecosystems;
- review bots without authored commits;
- lifecycle boundaries;
- predecessor/successor rollups;
- orchestrator-only evidence;
- recovery-only evidence;
- copied templates and fixtures;
- current-tree legacy residue.

---

## 23. Acceptance criteria

The new pack is ready only when all of the following hold.

### Artifact integrity

- Old JSON packs are byte-for-byte unchanged.
- Rebuilding the new pack from the same inputs produces the same digest.
- The new version freezes without overwriting an existing version.
- Old pack documents still load.

### Catalogue integrity

- Exactly 72 active families are current-matcher-detectable.
- Exactly 25 of those are additions.
- Exactly six active families remain v2-gated.
- Total active catalogue is exactly 78.
- `Generic` is not counted as a vendor family.
- Legacy families and rules do not increase current active counts.

### Lineage integrity

- Aliases and predecessors do not create duplicate family counts.
- `dsh-superagent` rolls up to DeepSeek Harness.
- DeepAgent rolls up to Abacus.
- Windsurf rolls up to Devin.
- Roo lineage rolls up to Zoo.
- Historical names remain visible as `observed_as`.

### Attribution integrity

- Exact commit emails do not become generic forge-participant matches.
- Reviewer activity does not become authorship.
- Release bots do not become coding-agent evidence.
- Wrapper/orchestrator hits do not inherit downstream commits.
- Legacy file residue does not establish current adoption.
- Recovery/checkpoint evidence does not represent ordinary frequency.

### Abacus-specific regression cases

- `agent@abacus.ai` matches the Abacus family.
- `DeepAgent <agent@abacus.ai>` rolls up to Abacus with predecessor naming.
- `.abacusai/config.json` establishes configuration, not authorship.
- `abacus-ai-automation[bot]` produces no Abacus authorship/current-use hit.
- `checkpoint@abacus.ai` in the external checkpoint implementation does not become target-repository evidence.
- Bare `noreply@abacus.ai` does not match without exact Agent role/name corroboration.

### Replit-specific regression cases

- `agent@replit.com` matches Replit Agent.
- `Replit-Commit-Author: Agent` is distinct from `Deployment`.
- `.replit` alone does not establish Replit Agent use.
- Per-user Replit Git email does not establish Agent authorship.

---

## 24. Known limitations

### Absence is not proof of non-use

Products can:

- disable attribution;
- use user Git identity;
- keep state outside the repository;
- remove generated branches;
- squash away trailers;
- rely on ignored project files;
- fall outside the detector's recent history window.

### Search totals are not adoption counts

GitHub search totals can contain:

- forks;
- mirrors;
- repeated commits;
- fixtures;
- examples;
- copied templates;
- incomplete index results.

They help evaluate collision risk. They do not measure unique users or repositories.

### Current file trees lose chronology

The live tree does not reveal when a file was introduced unless additional history is collected.

### Closed products limit reproducibility

Some products require official documentation, distributed binaries, packages, or observed product-controlled SCM identities because implementation source is not public.

### Configurability creates undercount

Default attribution may be disabled, replaced, or omitted. Missing fingerprints should produce uncertainty, not a claim of human authorship.

---

## 25. Frequently asked questions

### Is a family the same thing as a tool name?

Not always. A family may include several tool names, product surfaces, and predecessor brands.

### Is every fingerprint an authorship signal?

No. Most files establish configuration. Reviews establish participation. Only exact evidence with authorship semantics should count commits.

### Why keep old fingerprints?

Repositories preserve history. Removing a verified old fingerprint would make genuine historical use disappear from future scans.

### Why remove any old rule at all?

Rules are removed from positive detection only when they were unsupported, overbroad, duplicate, or represented another layer such as release automation. Those hypotheses remain documented in a rejection ledger.

### Does “active family” mean detectable today?

No. Six active families require matcher v2.

### Does “current-matcher-detectable” mean every use is detected?

No. It means at least one safe rule can be matched. Detection remains incomplete when attribution is disabled or absent.

### Why is `AGENTS.md` not a product fingerprint?

It is a shared standard used by many agents. It can establish generic agent-oriented configuration, not which product used it.

### Why is a product bot sometimes rejected?

A product may have release, review, support, and coding bots. Product ownership alone does not make every bot a coding-agent author.

### Can one repository contain several families?

Yes. A repository may be configured for several agents and contain authored commits from several others.

### Can one fingerprint map to several families?

Sometimes. Shared artifacts should remain ambiguous until content or context selects a family.

### Is the new pack already available?

No. This guide and the reaudit define the implementation contract. `packs/2026-11-14.json` still needs to be built, tested, replayed, and frozen.

---

## 26. How to read the research documents

Use the documents in this order:

1. **This guide** — concepts, catalogue, lifecycle, and implementation overview.
2. [`findings/2026-11-13-agent-pack-reaudit.md`](findings/2026-11-13-agent-pack-reaudit.md) — normative decisions, exact rules, collision findings, and source pins.
3. [`findings/2026-11-08-agent-fingerprint-methodology.md`](findings/2026-11-08-agent-fingerprint-methodology.md) — evidence standard, source hierarchy, detector semantics, and validation method.
4. [`findings/2026-11-08-agent-fingerprint-research.md`](findings/2026-11-08-agent-fingerprint-research.md) — detailed source-level fingerprint audits.
5. [`findings/2026-11-08-agent-fingerprint-landscape.md`](findings/2026-11-08-agent-fingerprint-landscape.md) — broader market and candidate landscape.
6. [`agent-pack-63-and-90.md`](agent-pack-63-and-90.md) — superseded provisional proposal, useful only for decision history.

The reaudit is normative when an older document disagrees.

---

## 27. Final principles

The trace pack should remain understandable through a small set of principles:

1. Count canonical product lineages, not names.
2. Preserve verified history with lifecycle metadata.
3. Do not preserve false attribution as history.
4. Keep configuration, activity, authorship, review, and orchestration separate.
5. Treat exact source-control identities as stronger than product-name mentions.
6. Require content or conjunctions for generic-looking paths.
7. Keep forge roles and channels explicit.
8. Never let wrappers or hosts inherit downstream authorship.
9. Report uncertainty instead of manufacturing precision.
10. Keep every frozen pack immutable and reproducible.

The result is not merely a bigger list of agent names. It is a lifecycle-aware evidence model capable of explaining what was observed, which product lineage it belongs to, what it proves, when it was valid, and whether it should affect current or historical adoption.
