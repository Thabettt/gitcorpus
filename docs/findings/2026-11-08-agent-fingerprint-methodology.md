# Repository-Visible Agent Fingerprints — Research Methodology

**Generated:** 2026-11-08T22:21:23+02:00  
**Repository HEAD:** `4f2ba85252ab1ea483f9c96c7e4da752b04385ad`  
**Research date:** 2026-11-08  
**Status:** methodology and confidence record; no detector or pack changes  
**Companion findings:** [2026-11-08-agent-fingerprint-research.md](./2026-11-08-agent-fingerprint-research.md)

---

## 1. The Question and the Scope

The research question was:

> Which artifacts visible in a Git repository can safely indicate use of Orca, DeepSeek Harness, Paperclip, Herdr, Herder, Hermes Agent, Command Code, Cursor, Ghostty, OpenCode v2, Pi, Oh My Pi, OpenClaw, Claw Code, Mistral Vibe, or OpenHands, and which of those artifacts can the current detector represent without creating unacceptable false attribution?

A **repository-visible fingerprint** is an artifact that survives in one of the repository or forge surfaces available to the detector:

- a committed or ignored configuration path;
- a Git author or committer name/email;
- a commit-message trailer or generated footer;
- a branch or pull-request head branch;
- a hidden Git ref;
- a pull-request body footer;
- a pull-request or issue label;
- a bot identity;
- an issue or pull-request comment that invokes an agent.

The scope was deliberately narrower than “anything the product stores.” Local databases, process names, shell history, telemetry, model-provider headers, editor state, and files under a user’s home directory are not repository evidence unless the product explicitly writes or consumes a project-level form that can become visible to Git. A local path can still matter when accidental commitment is diagnostically useful, but it is then classified **anomalous**, not normal adoption.

The research also separated four layers that are often collapsed in public discussions:

1. the product whose usage is being detected;
2. a wrapper or orchestrator that launches another agent;
3. the downstream agent that edits or commits code;
4. a terminal that merely transports the downstream process’s I/O.

That distinction is essential. A Claude or Codex trailer produced inside Ghostty does not identify Ghostty. A downstream agent launched by Orca does not automatically identify Orca. A Herder session trailer, by contrast, is Herder-owned metadata even when the code was written by a downstream model.

### 1.1 Deliberately out of scope

The work did **not**:

- edit `packs/`, `src/`, detector code, tests, or product code;
- propose that every real signal should be deployed;
- estimate unique-user or unique-repository adoption from search totals;
- treat absence of a marker as proof of non-use;
- reverse-engineer private services beyond repository-visible contracts in distributed packages or official documentation;
- conflate provider-side request attribution with Git attribution;
- assign downstream-agent fingerprints to wrappers, orchestrators, or terminals.

The output was a source-linked evidence inventory, a risk classification, a comparison against the frozen detector pack, and a list of schema gaps.

---

## 2. Why Repository-Visible Evidence Is the Right Lens

The detector analyzes repositories and forge metadata. It cannot observe which desktop application was open, which terminal hosted a process, or which local session database existed when a change was made. Repository-visible evidence is therefore the only evidence that can be reproduced after the fact and compared consistently across projects.

This lens has three concrete advantages:

1. **Persistence.** A committed config path, trailer, or branch remains inspectable after the original session ends.
2. **Independent verification.** Another researcher can inspect the same commit, tree, branch, ref, pull request, or issue.
3. **Compatibility with the detector.** The current system already collects a defined subset of these surfaces, so each proposed fingerprint can be evaluated against actual implementation constraints rather than an imaginary ideal detector.

The lens also has a known cost: it undercounts tools that leave no repository artifact, tools whose attribution is disabled, work that is committed manually, and evidence older than an API window. The findings therefore describe **detectable evidence**, not total product usage.

---

## 3. Source Selection

### 3.1 Source hierarchy

Evidence was accepted in this order:

1. current canonical upstream source at a pinned commit;
2. current official product documentation;
3. a pinned distributed package when public source did not contain the shipped implementation;
4. historical canonical source needed to classify a marker as legacy;
5. cross-repository public activity used to validate prevalence and collision risk;
6. secondary claims only as hypotheses to test against the sources above.

Product names, blog posts, repository examples, and a marker’s visual plausibility were never enough on their own. The source had to establish who emits the marker, under what conditions, whether it is default, and whether it is intended to be committed.

### 3.2 Canonical source table

| Product or implementation | Canonical source selected | Pin used | Why this source was authoritative |
|---|---|---|---|
| Orca | `stablyai/orca` | `492ccce634795c6c36a448c652054e1a52adbee1` | Current application, worktree, hook, and documentation implementation |
| DeepSeek Harness | `deepseek-ai/deepseek-harness` | `fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159` | Current experimental worktree and badge bundles live in-tree |
| Paperclip | `paperclipai/paperclip` | `0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2` | Schema, launcher identity, prompt, branch, and recovery behavior are all present |
| Herdr | `herdrdev/herdr` | `ee5bfb5041bb3e4a49d591c72308aae3c81ecdde` | Current branch generation and worktree implementation |
| Herder | `herder-sh/herder` | `701a5b527d486863442b9a3de218e6c02af0e2a4` | Current hooks, trailers, worktree branches, and checkpoint refs |
| Hermes Agent | `NousResearch/hermes-agent` | `444f980868937926562fe5652d26364d45550960` | Current context-file, worktree, subagent, archive, and documentation contracts |
| Command Code | distributed npm package `command-code@1.88.5` | `1.88.5` | The shipped CLI contained current attribution behavior absent from the sparse public source |
| Command Code public source | `CommandCodeAI/command-code` | `630bbf418f62bcdea627e57e6dca60151452355b` | Used for repository identity and public-source comparison, not as a substitute for the distributed implementation |
| Cursor | official Cursor documentation | observed 2026-11-08 | Cursor is not fully represented by a public canonical source tree; official docs define current file, Git, Cloud, Bugbot, and API contracts |
| Ghostty | `ghostty-org/ghostty` | `e035beb9437118b803830a5864ea2f4dd7094354` | Current terminal implementation and contributor files |
| OpenCode v2 | `anomalyco/opencode` | `3ce4ca464dbbd993eb9c3158f7e77cddd80774fb` | Current V2 config, definitions, worktrees, and core behavior |
| OpenCode v1 | historical `anomalyco/opencode` source | `c90281c0d6e6a92309d8d326e732931b92739cdf` | Needed to date branch, bot, email, and footer behavior that no longer belongs to V2 core |
| Pi | `earendil-works/pi` | `5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c` | Current project configuration and provider-attribution implementation |
| Oh My Pi | `can1357/oh-my-pi` | `33a063ce79dfc24d3a99786283d01f6ed127703c` | Current `.omp` surfaces, worktree behavior, and in-tree robomp subcomponent |
| OpenClaw | `openclaw/openclaw` | `476cce7a8a343ac1524bf12276da839a690cff8a` | Current workspace, worktree, refs, attribution, and gateway behavior |
| OpenClaw historical comparison | `openclaw/openclaw` tag/source | `v2026.2.12` | Reconciled public `openclaw@localhost` dates against source available at that time |
| Claw Code | `ultraworkers/claw-code` | `ca48ec75003da7f64a0780996c2ba6e71f78daea` | Current `.claw` project configuration and compatibility handling |
| Mistral Vibe | `mistralai/mistral-vibe` | `c96a6dbb34d34f8a868b3f67b279ecabbf1aa616` | Current footer, config, worktrees, and recovery refs |
| OpenHands | `OpenHands/OpenHands` | `cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05` | Main product, historical locations, Git behavior, and automation |
| OpenHands Software Agent SDK | `OpenHands/software-agent-sdk` | `e6569442a23951f852ead8514ae51dff1b377f37` | Current hooks, agents, skills, planning, and tool behavior |

### 3.3 Why official sources outranked observed strings

Public activity can show that a string exists, but not why it exists. The `126,632` matches for `help@stably.ai` did not establish that Orca currently emits the trailer. Current source showed otherwise. Likewise, `31,846` matches for `openclaw@localhost` did not establish a default because their dates conflicted with the source implementation date.

The source answered four questions that a search count cannot:

- Is the behavior current?
- Is it default or opt-in?
- Is the marker product-owned or user-supplied?
- Does it occur in ordinary history, a hidden ref, a local ignored directory, or a third-party integration?

---

## 4. Collection Method

### 4.1 Snapshot workspace

Research artifacts were kept outside the repository under:

```text
C:\Users\Abdul\AppData\Local\Temp\opencode\fingerprint-research\
```

The workspace contained pinned source directories and recursive tree exports. Relevant directories included:

```text
orca-src/
deepseek-harness-src/
paperclip-src/
herdr-src/
herder-src/
hermes-src/
command-code-src/
command-code-npm/package/
ghostty-src/
opencode-src/
opencode-v1-src/
pi-src/
oh-my-pi-src/
openclaw-src/
openclaw-2026.2.12/
claw-code-src/
mistral-vibe-src/
openhands-src/
openhands-sdk-src/
```

Tree exports included:

```text
stablyai__orca.tree.json
deepseek-ai__deepseek-harness.tree.json
paperclipai__paperclip.tree.json
herdrdev__herdr.tree.json
herder-sh__herder.tree.json
NousResearch__hermes-agent.tree.json
CommandCodeAI__command-code.tree.json
ghostty-org__ghostty.tree.json
anomalyco__opencode.tree.json
earendil-works__pi.tree.json
can1357__oh-my-pi.tree.json
openclaw__openclaw.tree.json
ultraworkers__claw-code.tree.json
mistralai__mistral-vibe.tree.json
OpenHands__OpenHands.tree.json
OpenHands__software-agent-sdk.tree.json
```

### 4.2 What each artifact was for

**Recursive tree exports** provided a cheap, complete path inventory for a pinned revision. They answered whether a suspected filename existed, whether a product had modern and compatibility locations, and where to focus source reads. A tree export does not contain file contents and cannot establish defaults or runtime behavior.

**Blobless partial clones** preserved Git history and object identity while avoiding a full download of every blob in very large repositories. Files needed for analysis were read on demand, including with `git show HEAD:<path>` when the working tree did not materialize a blob. The cost is that an unavailable remote or omitted on-demand fetch can prevent an unmaterialized blob from being read. That is why path inventory and source reads were kept conceptually separate.

**Sparse or targeted checkouts/reads** reduced local I/O for repositories where only a few subsystems were relevant. This improves speed but can hide behavior if the initial path hypothesis is wrong. Recursive tree exports and multiple naming searches were used to reduce that risk.

**Distributed package extraction** was used for Command Code `1.88.5`. The public repository snapshot did not expose the shipped attribution implementation, while the npm package did. The package is minified, so exact literals and control flow were recoverable, but source-level naming and history were less readable. Claims from that package are version-specific.

**Historical source snapshots** were created only when current source could not classify an observed public marker. OpenCode v1 and OpenClaw `v2026.2.12` are the important examples.

### 4.3 Acquisition and rerun command forms

The preserved snapshots establish the repository, pin, and artifact names. The commands below are exact rerun forms for reproducing those artifacts. They are not a claim that every original PowerShell quoting character survived the compacted interactive transcript.

```powershell
$root = 'C:\Users\Abdul\AppData\Local\Temp\opencode\fingerprint-research'

gh api --method GET `
  -H 'Accept: application/vnd.github+json' `
  '/repos/stablyai/orca/git/trees/492ccce634795c6c36a448c652054e1a52adbee1?recursive=1' `
  > "$root\stablyai__orca.tree.json"

git clone --filter=blob:none --no-checkout https://github.com/stablyai/orca.git "$root\orca-src"
git -C "$root\orca-src" fetch origin 492ccce634795c6c36a448c652054e1a52adbee1
git -C "$root\orca-src" checkout --detach 492ccce634795c6c36a448c652054e1a52adbee1

git -C "$root\orca-src" show HEAD:docs/site/content/docs/model/orca-yaml.mdx

npm pack command-code@1.88.5
```

For other repositories, substitute the exact repository and pin from Section 3.2. On Windows, archives were extracted under the same approved temporary root rather than a generic `/tmp` path.

**Unverified:** the exact original shell quoting and option ordering of every acquisition command are not recoverable from the compacted transcript. The repository URLs, output paths, pins, and resulting artifacts are verified. The rerun forms above preserve those semantics.

### 4.4 Source inspection strategy

The source pass began with exact strings suggested by documentation or existing detector rules, then followed the owning runtime code. A documented branch pattern was followed to the function constructing the branch; a trailer to its prompt, hook, or message builder; a synthetic identity to the environment passed to Git; a path to loader precedence and compatibility handling; and a hidden ref to creation, push, retention, and deletion behavior.

Tests were corroboration, not the sole authority, unless generated or packaged production behavior made the test the clearest readable contract. Comments and docs were checked against implementation because stale documentation was one of the threats under investigation.

---

## 5. The Detection Model Being Evaluated

### 5.1 Plain-language model

The detector has five configurable pattern lists: authors, files, branches, labels, and generic bots. It scans a bounded amount of repository history and recent forge activity, turns pattern matches into evidence records, and rolls commit evidence into a windowed adoption ratio.

The important limitation is that a pattern is mostly just **text plus an agent name**. It cannot naturally say:

- “this file must be at the repository root and contain this schema string”;
- “this email is valid only on commits reachable from this hidden ref”;
- “this phrase must be in a PR body, not a username”;
- “this bot comment counts only when the comment body contains a command”;
- “this rule was valid only before a particular version.”

Those are not missing regexes. They are missing data types and channel relationships.

### 5.2 Pack schema

At repository HEAD, a pack pattern is:

```python
@dataclass(frozen=True)
class Pattern:
    pattern: str
    agent: str
```

The pack stores `authors`, `files`, `branches`, `labels`, `bots`, `generic_weights`, and `exclusions`. There is no lifecycle, confidence, source version, default/optional status, content, ref namespace, bot semantics, or channel-specific author use.

### 5.3 File matching

File matching is case-sensitive. If a pattern does not begin with `^` or `(?:^|/)`, the matcher prepends `(?:^|/)`. Dots are escaped automatically when the input contains a literal dot but not `\.`. It does **not** append an end anchor.

Consequences:

- a pattern can match at any path-segment boundary;
- root-only behavior needs an explicit `^...$`;
- `opencode.json` can match the prefix of `opencode.jsonc` unless deliberately end-anchored;
- directory patterns can match descendants, useful for `.cursor/` but dangerous for generic names.

The collector scans the live tree and `.gitignore`. API mode probes at most 20 literal paths when a tree is truncated. Content probes are limited to the first five matched tree paths and record only size and whether content is empty; they do not run product-specific content regexes.

### 5.4 Identity matching

Author patterns are case-insensitive. The same set is used for commit authors and committers, PR authors, and issue authors, assignees, and commenters. Patterns containing `@` are email patterns. Multi-token patterns can match names and login substrings. Ambiguous one-word patterns such as `cursor` receive special handling, while bot suffix normalization removes `[bot]` or `-bot`. Consequently, `cursor[bot]` can normalize to `cursor` and satisfy the Cursor identity rule.

This reuse is why product bots cannot simply be added as authors. A useful commit identity can become false adoption when it merely comments on an issue.

### 5.5 Commit messages and trailers

Commit-message extraction skips configured noise subjects such as merges, reverts, version bumps, and `[skip ci]`. It recognizes:

```text
co-authored-by
authored-by
author
committer
signed-off-by
assisted-by
co-developed-by
developed-by
generated-by
written-by
ai-assisted
```

It also recognizes broad footer lines beginning with verbs such as `generated`, `created`, `written`, `made`, `built`, `assisted`, `co-authored`, `authored`, `powered`, or `developed`, followed by `with`, `by`, or `using` within a bounded span.

After the final blank line, other token-shaped lines can be inspected, but only the general author matcher is available. This cannot cleanly represent `Herder-Session: <id>` because adding `Herder` to authors also affects identity and activity channels.

If a message contains an email and no first-tier email match was found in extracted footer lines, the whole message is scanned for configured emails. This makes exact product email trailers deployable, but does not distinguish an author identity from an email mentioned in message text.

### 5.6 Branches, labels, PRs, and issues

Branch and label regexes are case-sensitive and not automatically anchored. API mode examines the most recent 100 pull requests and collects each head branch, up to 20 labels, body text, author login, up to 50 comment-author logins, and up to 100 commits.

The only arbitrary PR-body marker implemented directly is the hard-coded Codex task URL. Cursor and OpenClaw footers cannot be configured in the pack. PR evidence can propagate to commits when the commit’s GitHub author login matches the PR author, so a false branch, label, or bot hit can also propagate.

Issue mode examines the most recent 100 issues, up to 10 assignees and 50 comment authors per issue. It does not fetch comment bodies. Therefore `@cursor`, `bugbot run`, and robomp directives cannot be observed.

### 5.7 Local clone mode

Clone mode reads a configurable recent commit window, defaults to 100, fetches PR refs to a configured depth, parses branch names from merge messages, and lists remote branch heads under `refs/heads/*`. It does not enumerate arbitrary hidden refs such as:

```text
refs/herder/<session>/<turn>
refs/hermes/archive/<tree>
refs/vibe/reaped/<name>
refs/openclaw/snapshots/<id>
refs/openclaw/worker-results/...
```

### 5.8 Deduplication and rollups

Evidence is deduplicated by the exact serialized tuple `[agent, channel, evidence]`. Two hits from one commit remain distinct if their channel or evidence document differs.

The commit adoption ratio excludes detected generic bots and noise commits, then compares AI-attributed OIDs with the remaining commit window:

| Ratio | Adoption level |
|---:|---|
| `0` or unavailable | `none` |
| `< 0.01` | `experimental` |
| `< 0.05` | `limited` |
| `< 0.20` | `consistent` |
| `>= 0.20` | `pervasive` |

These are windowed labels. Bot exclusion protects the commit ratio, not PR/issue participation or `first_signal_at` derived from those channels.

### 5.9 Evidence windows

| Evidence | Current window or scope | Important absence limitation |
|---|---|---|
| file tree and `.gitignore` | live at detection time | deleted historical files are absent |
| authors, committers, trailers | last 100 commits by default | older attribution is missed |
| PR metadata | most recent 100 PRs | older closed PRs are missed |
| PR comments | first 50 comments per PR | later comments and all bodies are missed |
| PR commits | first 100 commits per PR | very large PRs are partial |
| issue activity | most recent 100 issues, first 50 comments | no comment bodies; older issues are missed |
| local branch history | last 100 merge messages plus current remote heads | deleted branches and hidden refs are missed |
| clone-only enrichment | separate audit paths | not part of a normal API-only census |

---

## 6. Evidence Classification

The classification concerns safe detector use, not whether a literal exists.

### 6.1 Strong

A strong signal is product-specific and has a clear current contract in its channel. Examples are `Co-Authored-By: Paperclip <noreply@paperclip.ing>`, `.openclaw/worktree-setup.sh`, `command-code/<id>`, and `.cursor/config/bugbot.yaml`. Strong does not mean universal: Cursor’s trailer is configurable, so absence proves nothing.

### 6.2 Corroborating

A corroborating signal improves confidence but should not normally stand alone. Examples are Herdr’s full `worktree/<adjective>-<noun>-<4hex>` shape, a named Hermes `hermes/<sanitized-name>` branch, Claw Code’s `.claw.json`, and a broad `.pi/` hit.

### 6.3 Composite-only

A composite-only signal is reliable only with another fact. Examples are `.paperclip.yaml` plus `schema: paperclip/v1`, `herder <herder@localhost>` plus `refs/herder/...`, the OpenClaw workspace-file conjunction, and robomp labels together with deployment context.

### 6.4 Legacy

Legacy evidence is verified historical behavior that should be bounded by version or date. Examples are `Co-authored-by: Orca <help@stably.ai>`, OpenCode v1’s identity and footer, `.cursorrules`, `.openhands/microagents/`, and `.vibe/tools/`.

### 6.5 Optional

Optional evidence is current but requires opt-in or a non-default mode. Examples are DeepSeek’s worktree and badge bundles, Hermes subagent worktrees, OpenClaw’s PR footer, Oh My Pi’s `omp/task/<id>`, and Paperclip rescue branches.

### 6.6 Anomalous

Anomalous evidence is product-associated but unexpected in the scanned channel. Examples are committed `.orca/issue-command`, committed `.agents/worktrees/dsh-*`, committed `.agents_tmp/PLAN.md`, and ordinary public-history `openclaw@localhost` commits that do not align with a verified default.

### 6.7 Unsafe

Unsafe evidence has too much collision, user control, cross-tool reuse, or layer ambiguity for standalone attribution. Examples are `AGENTS.md`, `.worktreeinclude`, `pr-<number>`, bare `worktree/`, `cursor[bot]` comments, human OpenClaw co-author trailers, and downstream-agent markers observed inside Ghostty.

---

## 7. The Central Difficulty: Defaults, Options, History, and Inheritance

The hardest part was not finding strings. It was identifying the conditions under which each string is emitted.

### 7.1 Default versus optional

DeepSeek Harness demonstrates why source ownership is insufficient. Its worktree and “powered by dsh” badge are official, but both ship disabled. Cursor’s local attribution is default-on but configurable. Mistral Vibe’s footer is default-on with `include_commit_signature` able to disable it. OpenClaw’s lobster PR footer is default-off. These markers cannot be given the same lifecycle semantics.

### 7.2 Current versus legacy

Orca’s public trailer count initially made it look current. Current source did not support that reading, so the marker was retained as legacy rather than discarded. OpenCode required a full generation split: V1 supplied branch, bot, identity, and footer signals; V2 uses detached worktrees and emits no native core attribution.

### 7.3 Core versus third-party or subcomponent

Pi’s `PI_ATTRIBUTION` labels outbound model-provider requests, not Git. Oh My Pi’s `python/robomp` has a stable branch namespace but deployment-configurable bot and Git identity. OpenCode plugin trailers identify an optional plugin layer, not V2 core.

### 7.4 Wrapper versus orchestrator versus terminal

- A **wrapper** prepares or launches a downstream environment but may leave little native metadata.
- An **orchestrator** owns sessions, branches, refs, or workflow metadata across downstream agents.
- A **terminal** transports another process’s interface and does not claim authorship.
- A **downstream agent** performs code and Git actions inside the parent layer.

Worked cases forced this distinction:

- **Orca** owns worktree orchestration; current downstream commits are not automatically Orca-attributed.
- **Herdr** manages agents/worktrees but adds almost no native attribution.
- **Herder** adds `Herder-Session:` and checkpoint refs, so it has native session evidence.
- **Ghostty** is a terminal. Its source `AGENTS.md` is contributor guidance, not downstream usage evidence.
- **OpenClaw** owns managed branches and snapshots, while its co-author trailers credit people rather than the product.

---

## 8. Validation Against Public GitHub Activity

### 8.1 Search endpoints

Two GitHub search families were used:

1. **Code search** for committed paths and exact file literals, using the endpoint’s `total_count` and a retrievable result sample.
2. **Commit search** for exact emails, author-email qualifiers, and exact message phrases.

Reproducible request forms are:

```powershell
gh api --method GET `
  -H 'Accept: application/vnd.github+json' `
  search/commits `
  -f q='"vibe@mistral.ai"' `
  -f per_page=1

gh api --method GET `
  -H 'Accept: application/vnd.github+json' `
  search/commits `
  -f q='author-email:help@stably.ai' `
  -f per_page=1

gh api --method GET `
  -H 'Accept: application/vnd.github+json' `
  search/code `
  -f q='filename:.paperclip.yaml' `
  -f per_page=1
```

The exact logical query literals retained from the session include:

```text
cursoragent@cursor.com
noreply@paperclip.ing
openhands@all-hands.dev
noreply@opencode.ai
help@stably.ai
author-email:help@stably.ai
noreply@commandcode.ai
vibe@mistral.ai
Generated by Mistral Vibe.
openclaw@localhost
AGENTS.md
.agents/skills/**/SKILL.md
MEMORY.md
USER.md
IDENTITY.md
SOUL.md
BOOTSTRAP.md
.worktreeinclude
.hermes/plans/*.md
.pi/settings.json
.commandcode/**/SKILL.md
.omp/config.yml
.paperclip.yaml
.vibe/config.toml
.cursor/config/bugbot.yaml
.openhands/hooks.json
.openclaw/worktree-setup.sh
.orca/issue-command
```

**Unverified:** the exact original shell quoting and GitHub query syntax used for every wildcard-shaped path query were not retained byte-for-byte after conversation compaction. The logical predicates, returned totals, and source corroboration are preserved. A rerun should save the emitted URL and query string directly.

### 8.2 Exact identity queries versus free text

Exact product-domain emails were treated as higher quality than product names. `cursoragent@cursor.com` is much less ambiguous than `cursor`. Exact phrase searches such as `Generated by Mistral Vibe.` distinguished a complete footer from an email that might occur in another context.

`author-email:help@stably.ai` was deliberately separated from free-text/message search for `help@stably.ai`. Exactly `0` author-email matches versus `126,632` message/email matches showed that Orca’s email appeared as a trailer rather than the primary author identity in the indexed activity.

Free-text totals were used qualitatively. They established public occurrence and supplied samples for context checks. They were not treated as counts of product-generated commits.

### 8.3 Capped and incomplete results

GitHub search can report a `total_count` much larger than the result window a client may page through. The prevalence values in the findings are those index totals. The inspected samples were necessarily capped and were not random samples of the full total.

Every future rerun should retain:

```text
query string
request time
total_count
incomplete_results
X-RateLimit-Limit
X-RateLimit-Remaining
X-RateLimit-Reset
number of results actually retrieved
sample selection rule
```

The compacted session record preserves exact totals but not a complete per-query response-header ledger. Counts therefore remain labeled volatile and potentially incomplete rather than being promoted to census figures.

### 8.4 Sampling across unrelated repositories

Samples were selected to answer collision questions rather than estimate population proportions. Exact product emails were checked outside the product’s own repository to verify propagation into unrelated projects. Generic paths and prefixes were tested across unrelated owners, languages, and tool stacks.

Examples of the collision design:

- `.worktreeinclude` was checked across Orca, Hermes, OpenClaw, and unrelated worktree use.
- `AGENTS.md`, `MEMORY.md`, `USER.md`, and `SOUL.md` were counted globally before product attribution was accepted.
- `worktree/`, `worktree-*`, `wt/`, and `pr-*` were compared with multiple worktree implementations.
- bot logins were checked as commenters/reviewers as well as commit identities.
- `openclaw@localhost` samples were ordered by date to compare activity with implementation history.

This purposive method is suitable for finding false positives. It is not an unbiased estimate of a false-positive rate.

### 8.5 Rate limits and sequencing

Code and commit search have separate search budgets from ordinary API calls. Queries were sequenced rather than launched as an uncontrolled burst. When a response exhausted its search bucket, source inspection and local tree analysis continued until the reported reset. Counts from separate reset periods were never added together; each prevalence claim uses one query’s `total_count`.

The exact rate-limit interruption log did not survive compaction. This is a reproducibility limitation, not a reason to alter the retained totals. A rerun should save response headers alongside every result.

---

## 9. False Positives and Attribution Hazards

### 9.1 Shared filenames

The strongest empirical collision warning came from path prevalence:

| Path | Indexed total and sample size |
|---|---:|
| `AGENTS.md` | 1,196,032; n=1,196,032 |
| `.agents/skills/**/SKILL.md` | 496,640; n=496,640 |
| `MEMORY.md` | 133,120; n=133,120 |
| `USER.md` | 86,784; n=86,784 |
| `IDENTITY.md` | 79,872; n=79,872 |
| `SOUL.md` | 38,464; n=38,464 |
| `BOOTSTRAP.md` | 37,632; n=37,632 |
| `.worktreeinclude` | 1,474; n=1,474 |

These paths remain useful as content or conjunction evidence. They are unsafe as singleton product detectors.

### 9.2 User-controlled branches

A product can create a worktree without owning its branch name. Paperclip issue branches, Orca work-item branches, Hermes named worktrees, Vibe supplied names, Herdr CLI branches, and generic PR checkout names all demonstrate this hazard.

The applied rule was:

> Match a branch strongly only when the product supplies a stable namespace and generation rule. Treat a user-supplied name as unsafe even if it passed through a product API.

### 9.3 Recovery and internal refs

Recovery artifacts are excellent product fingerprints but poor evidence of ordinary workflow frequency. Examples include:

```text
paperclip/rescue/<identifier>/<UTC timestamp>
refs/hermes/archive/<tree>
refs/vibe/reaped/<name>
refs/openclaw/removals/<id>
```

They were retained with recovery/optional classification rather than generalized to every session.

### 9.4 Synthetic identities outside their ref context

`herder@localhost`, `hermes-archive@localhost`, and current `openclaw@localhost` identities are meaningful only with their owning synthetic operation. A global author-email rule would lose that context and could mark ordinary commits.

### 9.5 Bots and activity contamination

Bots often participate without authoring code. `cursor[bot]` can comment or review. `all-hands-bot` can run review automation. A configured robomp bot can triage issues. Those events indicate integration activity, not necessarily generated commits.

The current detector’s author-pattern reuse makes this especially dangerous. Commit-ratio bot exclusion does not repair PR or issue hits. A bot-safe activity channel needs explicit semantics rather than another author regex.

### 9.6 Copied templates and fixtures

A product’s source repository naturally contains its own paths, examples, fixtures, and documentation. Public repositories can copy them. A file hit means “repository contains a recognized surface,” not necessarily “the product executed here.” Exact Git attribution is normally stronger execution evidence than configuration presence.

### 9.7 Case, boundaries, and partial matches

Case-sensitive branch/file matching and unanchored regexes can create false negatives and false positives. Exact filenames and generated branch shapes should be anchored. Broad prefixes should be deliberately weighted rather than accidentally broadened by matcher defaults.

### 9.8 Absence is not evidence of absence

Markers can be disabled, omitted by manual commits, removed after use, kept only in local ignored state, or fall outside recent windows. Pi and OpenCode v2 deliberately have no native core Git attribution. Their detection will be file-based and incomplete.

---

## 10. Decision Log and Reversals

This section records hypotheses that changed and the evidence that forced each change.

### 10.1 Regex availability was separated from safe representation

The initial temptation was to ask whether a literal could be written as a regex. Reading the detector changed the question. Many literals are mechanically encodable but unsafe because author patterns cross channels, files cannot inspect content, and branch collection excludes hidden refs.

**Decision change:** every candidate received both an encodability result and a separate safety/evidence class. “Yes” stopped meaning “should add.”

### 10.2 Shared files were downgraded after collision measurement

Names such as `AGENTS.md`, `SOUL.md`, and `MEMORY.md` looked meaningful in individual product docs. Global totals showed they were too common for singleton attribution.

**Decision change:** shared surfaces became composite-only or unsafe. Product-specific conjunctions remained useful, particularly OpenClaw’s workspace set.

### 10.3 Orca’s trailer moved from plausible current to retired legacy

Public `help@stably.ai` matches were numerous and the trailer was product-specific. Current source showed no current committed attribution default. `author-email:help@stably.ai` returned `0`, confirming trailer/message use rather than primary identity.

**Decision change:** `Co-authored-by: Orca <help@stably.ai>` became legacy. Root `orca.yaml` became the primary current signal. Issue-derived branches were rejected.

### 10.4 DeepSeek official features were split by default state

The worktree and badge implementations were official, initially suggesting strong current detection. Bundle configuration and docs showed both were experimental/default-disabled.

**Decision change:** generated `dsh-*` branches and the badge became optional. The ignored local pool became anomalous if committed. Generic `.agents` files were rejected.

### 10.5 Paperclip’s filename became a content conjunction

`.paperclip.yaml` was distinctive, but source defined `schema: paperclip/v1` as canonical and accepted `.paperclip.yml` as compatibility input.

**Decision change:** the recommended file detector became path plus content. The exact email/trailer remained standalone. Rescue branches were scoped to recovery.

### 10.6 Herdr and Herder were disentangled

Their similar names and worktree roles made conflation likely. Source showed incompatible contracts:

- Herdr: `worktree/<adjective>-<noun>-<4hex>`, no native attribution;
- Herder: `herder/<session-suffix>`, `Herder-Session:`, checkpoint refs, `herder@localhost` synthetic commits.

**Decision change:** they received separate product identities and confidence levels. Bare `worktree/` was rejected. `herder@localhost` became ref-scoped composite evidence.

### 10.7 Hermes’ branch and archive behavior was separated

Hermes has native context files, automatic and named worktrees, optional subagent branches, and archive refs. The archive identity is not an ordinary author.

**Decision change:** native files and generated branches became deployable. `hermes-archive@localhost` requires `refs/hermes/archive/...`. `.worktreeinclude` was rejected as shared.

### 10.8 Command Code’s distributed package outranked sparse public source

The public source snapshot did not expose the shipped attribution implementation. `command-code@1.88.5` contained:

```text
Co-authored-by: CommandCodeBot <noreply@commandcode.ai>
```

It also showed `attribution.commit`, the empty-string disable path, and deprecated `includeCoAuthoredBy`.

**Decision change:** claims were versioned to `1.88.5`. Cloud `command-code/<id>` came from official docs. Local `worktree-<name>` was rejected.

### 10.9 Cursor folklore and official contracts were separated

The frozen pack included `CURSOR.md`, but current official docs did not support it. Official docs did support current `.cursor/` surfaces, `.cursor-plugin/plugin.json`, Bugbot files, worktree/environment files, attribution, cloud branches, cloud identity, and HSM signatures.

Bot activity then exposed a detector-specific hazard: normalized `cursor[bot]` can satisfy generic `cursor` in PR/issue channels.

**Decision change:** `CURSOR.md` was rejected; `.cursorrules` remained legacy; local and cloud attribution were separated; bot participation became unsafe standalone evidence.

### 10.10 Ghostty was removed from downstream attribution reasoning

Ghostty contains agent contributor guidance, but the product is a terminal emulator and adds no repository attribution to programs running inside it.

**Decision change:** no native Ghostty detector was recommended. Downstream markers stay attributed to the downstream agent.

### 10.11 OpenCode was split by implementation generation

Existing pack rules combined `.opencode` files, V1 email/bot/footer, and `opencode/` branches. V2 showed current config paths, detached worktrees, and no native core attribution.

**Decision change:** current files were retained; V1 branch/identity/footer/bot became legacy; plugin trailers became optional third-party evidence. An undated combined OpenCode rule was rejected.

### 10.12 Pi’s attribution was reclassified as provider telemetry

References to attribution initially suggested a Git marker. Following `PI_ATTRIBUTION` showed outbound model-provider request identity.

**Decision change:** Pi retained project-file fingerprints only. No author, trailer, branch, footer, bot, label, or issue trigger was claimed.

### 10.13 Oh My Pi core and robomp were split

Current `.omp` paths are stable. `omp/task/<id>` is product-specific, `wt/<timestamp>` is generic, and `pr-<number>` is unsafe. robomp adds a stable branch namespace but configurable identities and composite labels.

**Decision change:** robomp was documented separately rather than rolled into OMP core. Its labels and triggers remained real-but-composite.

### 10.14 OpenClaw’s identity required chronology

Current source defines `OpenClaw <openclaw@localhost>` for synthetic internal worktree commits. Public ordinary-history matches began on `2026-02-12`; current implementation arrived in September; `v2026.2.12` lacked the default.

Two readings remain:

1. an earlier private, deployed, or removed product path emitted it;
2. users or adjacent automation independently adopted it.

**Decision change:** ordinary-history `openclaw@localhost` became anomalous/product-associated, not current or legacy default. Its origin remains **unverified**. Human co-author credit and the optional PR footer were classified separately.

### 10.15 Claw Code’s root file was retained as compatibility evidence

It would have been tidy to label `.claw.json` obsolete after finding `.claw/`. Source still accepted it and scaffolding could emit it.

**Decision change:** `.claw.json` became corroborating compatibility evidence. `CLAW.md` requires content corroboration.

### 10.16 Mistral Vibe’s footer and retired tools path were separated

Source established the complete default footer and disable switch. It also showed `.vibe/tools/` is retired and only warned about.

**Decision change:** exact phrase and email were preserved separately; current `.vibe` files were recommended; `.vibe/tools/` became legacy; recovery refs remained hidden-ref evidence.

### 10.17 OpenHands planning and automation were corrected

Current SDK behavior established `.agents_tmp/PLAN.md` as default, root `PLAN.md` as legacy fallback, and `.openhands/PLAN.md` as configurable/test evidence. Current review automation uses `all-hands-bot` and `review-this`; `openhands-agent` is historical/example evidence.

**Decision change:** planning paths received distinct lifecycle classes. `openhands-agent` became an unsafe existing pack rule because author patterns flow into PR and issue activity.

---

## 11. Limitations and Threats to Validity

### 11.1 Source snapshots age

Every source claim is pinned. Products can change after the pin. Cursor documentation was observed on a date rather than pinned to a public Git commit, making future diffs harder.

### 11.2 Closed or distributed implementations

Command Code was verified from a minified package. Literals and fallback logic are high confidence for `1.88.5`, but minification reduces readability and historical explanation. Cursor relies on official docs because a complete canonical implementation is not public.

### 11.3 Search totals are not adoption counts

Totals can include repeated commits, forks, mirrors, examples, fixtures, copied templates, and multiple matches per repository. They can be incomplete and drift with GitHub’s index. They support occurrence and collision analysis, not market-share estimates.

### 11.4 Sample inspection was purposive

Samples were chosen to find collisions and disagreements. That supports detector safety but not an unbiased false-positive rate.

### 11.5 API windows undercount

The detector’s recent-100 windows miss older history and activity. `first_signal_at` is first observed in the collected window, not first-ever adoption.

### 11.6 Hidden refs are incompletely observable

Several high-quality signals are outside `refs/heads/*`. Source establishes their existence, but the current detector cannot validate them at scale. Servers can also refuse hidden refs during fetch.

### 11.7 Configurability weakens absence reasoning

Cursor, Command Code, and Mistral Vibe attribution can be disabled or replaced. OpenClaw’s footer is optional. Branch prefixes can be configured. Missing markers do not prove non-use.

### 11.8 Documentation can be stale

Official docs were checked against source where available. Source comments and tests can also be stale. Confidence is highest when docs, production code, and tests agree.

### 11.9 Product self-repositories and copied examples

A source repository naturally contains its own literals. Search hits do not prove execution, especially for portable skills and examples.

### 11.10 Unresolved OpenClaw origin

The source/date conflict was resolved enough to reject ordinary `openclaw@localhost` as a default, but not enough to identify its first emitter. Both readings remain **unverified**.

### 11.11 Compacted research transcript

The session preserved findings, totals, pins, and reconciliation outcomes, but not every byte of shell quoting, response headers, or sample URLs. Exact original wildcard-query quoting remains **unverified**.

### 11.12 No implementation test was performed

No pack or detector change was made. Recommendations were evaluated against code semantics, not inserted and benchmarked against a labeled corpus. Deployment still requires unit tests, replay, and false-positive review.

---

## 12. Reproducibility Appendix

### 12.1 Repository under analysis

```powershell
git rev-parse HEAD
# 4f2ba85252ab1ea483f9c96c7e4da752b04385ad

git status --short
```

The working tree already contained unrelated user modifications. Research did not reset, discard, or modify them.

### 12.2 Detector files to inspect

```text
src/detect/packs.py
src/detect/attribution.py
src/detect/channels.py
src/detect/local_channels.py
packs/2026-10-19.json
docs/detection-tiers.md
```

### 12.3 Snapshot pins

```text
Orca                 492ccce634795c6c36a448c652054e1a52adbee1
DeepSeek Harness     fcc0ad462172522aaf5c93a7b2e01f6b9f0b0159
Paperclip            0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2
Herdr                ee5bfb5041bb3e4a49d591c72308aae3c81ecdde
Herder               701a5b527d486863442b9a3de218e6c02af0e2a4
Hermes Agent         444f980868937926562fe5652d26364d45550960
Command Code source  630bbf418f62bcdea627e57e6dca60151452355b
Command Code package 1.88.5
Ghostty              e035beb9437118b803830a5864ea2f4dd7094354
OpenCode v2          3ce4ca464dbbd993eb9c3158f7e77cddd80774fb
OpenCode v1          c90281c0d6e6a92309d8d326e732931b92739cdf
Pi                   5ea81d2cd9bb997774b49e379aa5bc496fdfeb6c
Oh My Pi             33a063ce79dfc24d3a99786283d01f6ed127703c
OpenClaw             476cce7a8a343ac1524bf12276da839a690cff8a
OpenClaw historical  v2026.2.12
Claw Code            ca48ec75003da7f64a0780996c2ba6e71f78daea
Mistral Vibe         c96a6dbb34d34f8a868b3f67b279ecabbf1aa616
OpenHands            cc99322a1efd0f4be8d6934ae93a4d1d4bc33e05
OpenHands SDK        e6569442a23951f852ead8514ae51dff1b377f37
```

### 12.4 Generic snapshot procedure

```powershell
$owner = 'paperclipai'
$repo = 'paperclip'
$sha = '0a64c9b4abfb1aed8ed199a03e3ed90a595cbff2'
$name = 'paperclip-src'
$root = 'C:\Users\Abdul\AppData\Local\Temp\opencode\fingerprint-research'

gh api --method GET `
  -H 'Accept: application/vnd.github+json' `
  "/repos/$owner/$repo/git/trees/$sha?recursive=1" `
  > "$root\${owner}__${repo}.tree.json"

git clone --filter=blob:none --no-checkout "https://github.com/$owner/$repo.git" "$root\$name"
git -C "$root\$name" fetch origin $sha
git -C "$root\$name" checkout --detach $sha
git -C "$root\$name" rev-parse HEAD
git -C "$root\$name" remote get-url origin
```

### 12.5 Exact commit-search predicates and retained totals

```text
"cursoragent@cursor.com"       -> 9,589,537
"noreply@paperclip.ing"       -> 461,628
"openhands@all-hands.dev"     -> 273,260
"noreply@opencode.ai"         -> 226,793 retained OpenCode email/message total
"help@stably.ai"              -> 126,632
author-email:help@stably.ai    -> 0
"noreply@commandcode.ai"      -> 90,412
"vibe@mistral.ai"             -> 49,443
"Generated by Mistral Vibe."  -> 43,071
"openclaw@localhost"          -> 31,846
```

Rerun template:

```powershell
$q = '"Generated by Mistral Vibe."'
gh api --method GET `
  -H 'Accept: application/vnd.github+json' `
  search/commits `
  -f q=$q `
  -f per_page=1
```

Record `total_count`, `incomplete_results`, rate-limit headers, and timestamp. Do not compare a rerun count with the retained value without recording index drift.

### 12.6 Retained path-query totals

```text
AGENTS.md                         1,196,032
.agents/skills/**/SKILL.md         496,640
MEMORY.md                           133,120
USER.md                              86,784
IDENTITY.md                          79,872
SOUL.md                              38,464
BOOTSTRAP.md                         37,632
.worktreeinclude                      1,474
.hermes/plans/*.md                    5,896
.commandcode/**/SKILL.md              1,800
.pi/settings.json                     1,310
.omp/config.yml                         230
.paperclip.yaml                         165
.vibe/config.toml                        67
.cursor/config/bugbot.yaml               36
.openhands/hooks.json                     22
.openclaw/worktree-setup.sh                3
.orca/issue-command                        0
```

Rerun template:

```powershell
$q = 'filename:.paperclip.yaml'
gh api --method GET `
  -H 'Accept: application/vnd.github+json' `
  search/code `
  -f q=$q `
  -f per_page=1
```

For wildcard-shaped paths, save the final URL-encoded query. Original shell quoting is **unverified**; totals and logical path predicates are verified.

### 12.7 High-value literals to verify in source

```text
Co-authored-by: Orca <help@stably.ai>
https://img.shields.io/badge/powered_by-dsh-4D6BFE?style=flat-square&logo=deepseek&logoColor=white
schema: paperclip/v1
Paperclip <noreply@paperclip.ing>
Co-Authored-By: Paperclip <noreply@paperclip.ing>
Herder-Session: <session-id>
herder <herder@localhost>
Hermes worktree archive <hermes-archive@localhost>
Co-authored-by: CommandCodeBot <noreply@commandcode.ai>
Co-authored-by: Cursor <cursoragent@cursor.com>
Made with [Cursor](https://cursor.com)
Generated by Mistral Vibe.
Co-Authored-By: Mistral Vibe <vibe@mistral.ai>
Co-authored-by: openhands <openhands@all-hands.dev>
openhands <openhands@all-hands.dev>
🦞 Made with [OpenClaw](https://openclaw.ai)
OpenClaw <openclaw@localhost>
```

### 12.8 Revalidation checklist

For each product:

1. Resolve the current canonical repository and record its HEAD.
2. Diff relevant source paths against Section 12.3.
3. Check whether defaults, disable switches, and compatibility paths changed.
4. Rerun exact email, phrase, and path queries with headers saved.
5. Inspect unrelated-repository samples for every proposed standalone rule.
6. Re-read the detector before asserting that a channel is encodable.
7. Test proposed pack changes against bot PR/issue activity as well as commits.
8. Preserve historical rules with validity metadata rather than silently deleting or modernizing them.

---

## 13. Confidence Assessment

### 13.1 Confidence scale

| Confidence | Meaning | Typical evidence in this research |
|---|---|---|
| High | Current production code or official contract agrees with tests/docs; exact literal and channel are known | Paperclip email/trailer, Command Code `1.88.5` trailer, Cursor attribution, Mistral footer, OpenHands email, product-specific config paths |
| Medium | Source establishes behavior but it is optional, configurable, recovery-only, or not prevalence-tested | Generated worktree branches, recovery refs, compatibility files, default-off footers |
| Low | Origin, prevalence, or channel context remains unresolved | First emitter of pre-implementation ordinary `openclaw@localhost` commits |

### 13.2 Confidence by conclusion type

- **Exact current source literals:** high at the pinned revision.
- **“No native attribution found” conclusions:** medium. Absence is harder to prove than presence, and private/generated services can change.
- **Legacy classification:** high when current and historical source directly disagree; medium when based on a deprecation warning alone.
- **Prevalence totals:** high confidence that the listed total was returned during the session; low confidence as a stable or complete population estimate.
- **Collision classifications:** medium to high for globally common paths; medium for purposively sampled branch prefixes.
- **Encodability judgments:** high at repository HEAD because they follow the implementation directly.

---

## 14. Glossary

**Adoption ratio**  
The share of non-noise, non-excluded-bot commits in the detector’s current history window carrying an attributed signal. It is not a full-history or user-adoption measure.

**Anomalous evidence**  
A product-associated artifact appearing where it normally should not, such as ignored local state committed to Git.

**Author**  
The Git identity recorded as having written a commit’s change. It can differ from the committer.

**Author pattern**  
A detector regex used for commit identities and reused for PR and issue users. That reuse is a major attribution hazard.

**Bot-safe activity**  
Activity represented so recognizing a bot does not automatically turn every comment, review, or assignment into code adoption.

**Branch head**  
The commit currently named by a branch under `refs/heads/`, or the head branch attached to a pull request.

**Canonical source**  
The upstream source or official documentation defining current behavior, rather than a copied example or secondary claim.

**Channel**  
The surface where evidence occurs: file, identity, trailer, branch, hidden ref, label, PR body, bot, or comment trigger.

**Collision**  
A match caused by something other than the intended product behavior. A generic filename can have high collision even when each occurrence is real.

**Committer**  
The Git identity that created or applied a commit object. It can differ from the author after rebases, merges, or automation.

**Composite-only evidence**  
Evidence safe only with another condition, such as a path plus schema content or an identity plus hidden-ref namespace.

**Conjunction**  
A rule requiring two or more facts simultaneously. The current pack cannot express general conjunctions.

**Core product**  
The main implementation, distinct from a plugin, deployment-specific integration, or bundled subcomponent.

**Corroborating evidence**  
A signal that increases confidence but is not unique enough to stand alone.

**Default**  
Behavior active without explicit opt-in in the studied version. A default can still be configurable or disabled.

**Detector pack**  
The versioned document containing agent URLs and author, file, branch, label, and bot patterns.

**Downstream agent**  
The coding agent launched inside a wrapper, orchestrator, or terminal. Its fingerprints remain its own unless the parent adds separate metadata.

**Evidence window**  
The bounded set examined, such as the last 100 commits or most recent 100 pull requests.

**Fingerprint**  
A repository-visible artifact that may indicate product configuration, execution, or activity.

**Footer**  
Generated prose near the end of a commit message or PR body. It is not necessarily a structured Git trailer.

**Hidden ref**  
A Git ref outside ordinary branch and tag namespaces, often used for snapshots, checkpoints, or recovery. It is outside normal enumeration, not necessarily secret.

**Ignored path**  
A path intended to remain local through `.gitignore` or equivalent behavior. Commitment is usually anomalous.

**Issue trigger**  
Text in an issue or PR comment that starts an agent or review, such as `@cursor` or `bugbot run`.

**Legacy evidence**  
Verified historical behavior that no longer describes the current default.

**Optional evidence**  
Current behavior requiring an opt-in feature, alternate mode, or non-default configuration.

**Orchestrator**  
A product owning sessions, worktrees, branches, refs, or workflow state while potentially launching downstream agents.

**Partial/blobless clone**  
A Git clone that initially omits file blobs and fetches them on demand, reducing transfer while retaining commit and tree identity.

**Pinned snapshot**  
A source checkout fixed to an exact SHA or package version so upstream changes do not silently alter the evidence.

**PR propagation**  
The detector mechanism assigning PR branch/label/body evidence to associated commits by the PR author.

**Prevalence**  
How often a path or literal appeared in the external search index during research. It is not unique repositories or adoption.

**Recovery-only**  
An artifact produced while preserving failed, dirty, or removed work rather than during every ordinary run.

**Ref**  
A Git name pointing to an object, including branches, tags, checkpoints, and snapshots.

**Schema gap**  
Evidence that exists but cannot be represented or collected by the current pack and detector model.

**Source-only; n=1**  
Behavior verified in one pinned canonical implementation with no retained public prevalence count.

**Strong evidence**  
A product-specific current signal safe to use alone in its intended channel, subject to normal detector caveats.

**Synthetic commit**  
A commit created by machinery to hold a snapshot, checkpoint, or internal state rather than ordinary source history.

**Terminal**  
Software hosting another process’s text interface. It does not inherit repository authorship from that process.

**Trailer**  
A structured `Token: value` line in a commit message, commonly after a blank line, such as `Co-authored-by: Name <email>`.

**Tree export**  
A recursive list of paths and Git object IDs at one commit. It inventories names but does not establish runtime behavior.

**Unsafe evidence**  
A real or plausible signal with too much collision, user control, cross-tool reuse, or layer ambiguity for standalone attribution.

**Unverified**  
A reading not settled by preserved source, chronology, or activity. Competing readings and a recommendation must remain visible.

**Validity period**  
The versions or dates during which a fingerprint describes product behavior. The current pack cannot store it.

**Wrapper**  
A layer preparing or launching a downstream agent without necessarily owning resulting Git attribution.

**Worktree**  
A Git checkout linked to an existing repository object store, commonly used to isolate concurrent tasks.
