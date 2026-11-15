# Trace packs

A **trace pack** is a frozen, versioned set of detection patterns. A detection run uses
exactly one pack, and every evidence row it stores carries that pack's version. Packs are
**independent**: each one defines its own agents, its own patterns, and the channels it
supports. Nothing is inherited from, merged with, or shared with another pack.

This page is the entry point. The schema-v2 rule contract is in
[`lifecycle-trace-pack.md`](lifecycle-trace-pack.md); the research behind the `2026-11-14`
catalogue is in [`trace-pack-2026-11-14-guide.md`](trace-pack-2026-11-14-guide.md) and
[`findings/2026-11-13-agent-pack-reaudit.md`](findings/2026-11-13-agent-pack-reaudit.md).

## The packs

| Pack | Schema | Source | Agents | Channels |
|---|---|---|---|---|
| `2026-10-14` | v1 (flat) | none kept; frozen artifact only | 62 | 8 |
| `2026-10-19` | v1 (flat) | [`packs/sources/2026-10-19/`](../packs/sources/2026-10-19/) — six CSVs | 62 | 8 |
| `2026-11-14` | v2 (lifecycle) | [`packs/sources/2026-11-14/catalogue.json`](../packs/sources/2026-11-14/catalogue.json) | 86 | 8 (incl. opt-in `hidden_ref`, excl. `issue`) |

`2026-10-14` and `2026-10-19` carry the same agents and the same patterns, except that
`2026-10-19` escapes the dots in author email patterns (so `.` no longer matches any
character). Both are the heuristic set from the Robbes et al. papers — see
[Provenance](#provenance).

### Where the agent counts come from

- **Schema v1:** every agent name used by an author, file, branch, or label pattern, plus
  `Generic`. Bot patterns are CI/release noise filters, not agents, so they are not listed.
  `tools.csv` names 63 tools, but the roster follows the patterns, not that list: patterns
  use a few names `tools.csv` lacks (`Abacus`, `Amazon Q`, `Kimi Code`, and the typo `Verd`,
  kept because frozen packs never change), and some tools have no pattern (`CopilotSwe`,
  `AmazonQ`, `Phoenix`, `Zed`, `Azad`). The result is 62 selectable names.
- **Schema v2:** every family that owns at least one enabled positive rule: 78 active
  families, the 6 legacy-only families (matched only through historical evidence and shown
  as *legacy*), the `Generic` pseudo-family, and 1 ambiguous lineage. Watch, adjacent,
  excluded, and negative-control families have no positive rules and are not selectable.

The roster is exactly the set of names a run may select, and selecting the whole roster is
stored as "no filter" (`agents: null`). An explicit *Select all* therefore can never drop
rules, such as the legacy-only families' historical rules.

## Channels

The eight channels come from the Robbes et al. heuristic categories (files, commit
authorship, branches, labels, PR authors, issue participants, and a bot filter) plus one
schema-v2 addition:

| Channel | What it reads | v1 packs | `2026-11-14` |
|---|---|---|---|
| `file` | tree, `.gitignore`, bounded content probes | file patterns | `file`, `workflow` rules |
| `author` | commit author/committer identities | author patterns | `author`, `committer` rules |
| `branch` | PR head branches (local: merge commits) | branch patterns | `branch` rules |
| `hidden_ref` | product-owned ref namespaces — **opt-in** | not supported | `hidden_ref` rules |
| `label` | PR labels (API only) | label patterns | `label` rules |
| `bot` | CI/release bot identities, excluded from the commit ratio | bot patterns | `bot` rejection rules |
| `commit_trailer` | `Co-authored-by` and product trailers | author patterns | `co_author`, `custom_trailer` rules |
| `pr_metadata` | PR author, body markers, PR→commit propagation | author + branch + label patterns, Codex body marker | `pr_author`, `pr_reviewer`, `pr_commenter`, `merge_request`, `service_account` rules |
| `issue` | issue authors, assignees, commenters (API only) | author patterns | `issue_*`, `service_account` rules |

A v1 pack supports all eight original channels, because the flat matcher applies its author
list to commit identities, trailers, PR authors, and issue participants. A v2 pack supports
a channel only when an enabled positive rule feeds it (`bot` also counts its noise
rejections). This is computed by `Pack.channels()` in [`src/detect/packs.py`](../src/detect/packs.py).
`2026-11-14` has no issue-participant rules, so it does not offer `issue`.

## How the console and runs use a pack

- The options page lists only the selected pack's agents and channels. Switching packs
  rebuilds both lists from that pack alone and resets them to its defaults (all agents,
  every supported channel except opt-in `hidden_ref`).
- The server rejects agents outside the pack's roster and channels outside
  `Pack.channels()`. The runner also intersects the stored channels with the pack's
  channels, so a run never executes a channel its pack cannot feed.
- The estimate prices only the selected pack's channels.
- Collectors follow the pack's schema. A v1 run keeps its original queries and matching:
  no PR-review fetch, no structured content predicates, and the original `AGENTS.md`
  content attribution. A v2 run uses the lifecycle matcher and stores the rich evidence
  fields; v1 rows leave them null.
- A collector stores evidence only under the channels that were selected.

The JSON API mirrors this: `/api/trace-packs` and `/api/trace-packs/{version}` describe each
frozen pack.

## Sources, building, and freezing

Each pack owns `packs/sources/<version>/`:

- schema v1: `tools.csv`, `authors.csv`, `files.csv`, `branches.csv`, `labels.csv`, `bots.csv`;
- schema v2: `catalogue.json`.

The builder refuses a source directory named for a different version, or one that mixes v1
CSVs with a v2 catalogue. Both kept sources rebuild their artifacts byte for byte, and
`tests/unit/test_trace_pack_2026_11_14.py` checks it.

```powershell
$env:PYTHONPATH = 'src'
.\.venv\Scripts\python.exe -m detect.packs build --src packs\sources\<version> --version <version> --out packs\<version>.json
.\.venv\Scripts\python.exe -m detect.packs freeze --pack packs\<version>.json
```

`packs/<version>.json` and a frozen database row never change. Freezing a version that
already exists with different content fails. To change patterns, create a new version
directory and build a new pack.

## Provenance

The v1 pattern set is vendored from the replication package of Robbes, Matricon, Degueule,
Hora, and Zacchiroli (LaBRI): *Promises, Perils, and (Timely) Heuristics for Mining Coding
Agent Activity* (MSR '26, arXiv 2601.18345), Table 1 and Section 4. It is the set used in
*Agentic Much?* (arXiv 2601.18341, Section 4.1.2: 79 author, 93 file, 20 branch, and
4 label heuristics for 63 agents, plus bot patterns) and reused unchanged in *Agentic Very
Much?* (arXiv 2606.07448). The papers exclude `CONVENTIONS.md` (Aider) as too noisy, which
is why it is the default exclusion.

`2026-11-14` is not from the papers. It is this project's own re-audit of the v1 set, adding
lifecycle, lineage, evidence semantics, and 31 new active families.

## Known gaps in `2026-11-14`

`2026-11-14` is **not** a superset of the papers' heuristics. The re-audit deliberately
rejected broad identities such as the bare names `Claude`, `Copilot`, `cursor`, `Codex`, and
`AI Assistant`; those are in its rejection ledger. But several of the papers' validated,
high-volume heuristics are missing **and are not in the ledger either**, so their removal
is undocumented:

- **Branches:** `copilot/`, `cursor/`, `claude/`, `devin/`, `jules/`, `coderabbit/`,
  `windsurf-bot/`, `goose/`, `serena/`, `jetbrains_junie`. Only the duplicate `claudecode/`
  is ledgered.
- **Label:** `codex`.
- **Identities:** `copilot-swe-agent`, `devin-ai-integration`, `gemini-code-assist`,
  `gemini-cli`, `deepsource-autofix`, `codegen-sh`, `gru-agent`, `windsurf-bot`,
  `cascade@windsurf.ai`, `aider@aider.chat`, `codex@openai.com`, `crush@charm.land`,
  `qwen-coder@alibabacloud.com`, `opencode-agent`, `roomote-agent`, the ChatGPT emails, and
  the Claude/Gemini model-name co-author names.
- **Issue participants:** no rules, so `issue` is not offered.

In Table 1 of the companion paper, `copilot/` (338K), `cursor/` (209K), and the `codex`
label (2.3M) are among the largest signals. Runs on `2026-11-14` therefore undercount
Copilot, Cursor, Devin, Codex, and Aider compared with `2026-10-19`. Results from the two
packs are not directly comparable for those agents. Restoring these heuristics, as exact or
scoped rules, means building a new pack version.
