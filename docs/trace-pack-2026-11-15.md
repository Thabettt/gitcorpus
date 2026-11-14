# Trace pack 2026-11-15

**Status:** built and replay-checked. **Not yet validated by labelling.** **Not frozen.**
**Schema:** v2, loaded by the lifecycle matcher (`detect.structured`, `detect.attribution`)
**Files:** [`packs/2026-11-15.json`](../packs/2026-11-15.json), source [`packs/sources/2026-11-15/catalogue.json`](../packs/sources/2026-11-15/catalogue.json), [`baseline-mapping.csv`](../packs/sources/2026-11-15/baseline-mapping.csv)
**Generator:** [`scripts/build_trace_pack_2026_11_15.py`](../scripts/build_trace_pack_2026_11_15.py). Never hand-edit the JSON; change the generator and build a new version.
**Why it exists:** [`findings/2026-11-15-trace-pack-audit.md`](findings/2026-11-15-trace-pack-audit.md)

## What it is

A strict extension of the published *Agentic Much?* heuristics (Robbes et al., arXiv 2601.18341 §4.1.2; MSR '26 arXiv 2601.18345 Table 1), carrying the lifecycle catalogue of 2026-11-14.

| Layer | Rules | What it contributes |
|---|---:|---|
| `agentic-much-baseline` | 293 | Every paper heuristic not already encoded by a 2026-11-14 rule, with v1 semantics: any-depth file paths, substring logins, and author patterns applied to commit identities, co-author trailers, PR authors and PR/issue participants, as v1 did |
| `2026-11-14` | 200 | The re-audited catalogue: 78 active families, lineage, lifecycle, structured rules, rejection ledger. 29 root-only path rules were widened to any depth, and to directory probes, where the baseline required it |
| `extended` | 28 | Surfaces the literature shows matter and neither earlier pack had: GitHub App identities (Claude, Copilot coding agent, Devin, Gemini CLI), the Claude Code commit/PR footer, Copilot and Codex-connector PR authors, review bots (Codex, Gemini Code Assist, CodeRabbit, Sourcery) as review participation, Aider's `(aider)` name suffix, Lovable's sync app, and Amp's thread trailer (provisional) |

Rejection ledger: 107 entries. That's 105 from 2026-11-14 plus two new ones: bare `aider` (substring collisions) and `cline@example.com` (placeholder domain).

### Every paper heuristic is accounted for

`baseline-mapping.csv` lists all 280 heuristics (79 author, 93 file, 20 branch, 4 label, 84 bot) and the rule or ledger entry that carries each one:

| Outcome | Count | Meaning |
|---|---:|---|
| covered | 109 | An existing 2026-11-14 rule already matches every form the heuristic matched |
| widened | 29 | A 2026-11-14 path rule was widened to any depth and directory probes |
| added | 60 | A baseline rule was added with v1 semantics |
| covered+added | 69 | Author heuristics: some surfaces covered, the rest added |
| rejected | 13 | Deliberately not carried forward; each points at a ledger entry with its reason |

The 13 rejections are the bare names `Claude`, `ChatGPT`, `Codex`, `cursor`, `Copilot`, `cline`, `junie`, `aider` and `AI [Aa]ssistant`; the placeholder `cline@example.com`; the Abacus release bot; the duplicate `claudecode/` branch; and `CURSOR.md`, which has no Cursor contract. The specific identities behind those names remain: `noreply@anthropic.com`, the `Claude Opus/Sonnet/Haiku` trailers, `copilot-swe-agent`, `cursoragent@cursor.com` and others.

### Decisions encoded

- **Detect broadly, count narrowly.** Adjacent families (SpecKit, Serena, Rulesync, Taskmaster) and the watch family ChatGPT now have rules. Their family category keeps them out of the coding-agent denominator.
- **Copilot Autofix** (`Co-authored-by: Copilot Autofix powered by AI`) is recorded as Copilot variant `Copilot Autofix`. All its metric-eligibility flags are false, so it never counts as adoption by default.
- **Review bots** count as `review_participation` (presence and activity), never as authorship.
- **Path depth:** product-owned configuration matches at any depth unless a rule documents root-only loading.

## Replay against run 101 (pack 2026-10-19, 14,480 repos)

`scripts/check_trace_pack.py --run 101` re-evaluates stored file and branch evidence. It makes no API calls.

| Pack | Repo–agent pairs kept via file/branch | Identity/trailer-only pairs | Not recovered |
|---|---:|---:|---:|
| 2026-11-14 | 11,341 / 20,139 | 3,341 | 5,457 |
| **2026-11-15** | **16,774 / 20,139** | 3,340 | **25** |

The 25 not recovered were inspected. Nearly all are legacy false positives the new rules reject on purpose:
- `CURSOR.md` copies in translated docs;
- `opencode.jsonl` test fixtures;
- Dependabot branches containing `opencode/`;
- `revert-…-codex/` branches;
- `CLAUDE.md.example`.

The 3,340 identity-only pairs now have matching rules (trailers, author emails, PR authors). Stored evidence redacts email addresses, so they can only be confirmed by a live run (see *Before freezing*).

## Reporting with this pack

Every evidence row stores its `rule_id`, and every rule declares `provenance.cohort`. Report two numbers:

- **Baseline-comparable:** repos whose evidence comes from rules with cohort `agentic-much-baseline`, or from 2026-11-14 rules whose `provenance.baseline_patterns` is non-empty. This is the paper's heuristic coverage, minus the 13 ledgered rejections.
- **Extended:** every positive rule.

For an exact replication of the papers' heuristics, run pack **2026-10-19**. Report per-channel counts and their union as a lower bound, keep configuration presence separate from activity, and keep adjacent families separate.

## Validation (to do before any `strong` claim)

Every rule carries `provenance.validation`:
- baseline rules: `published-pooled`, the paper's pooled ~99% precision over ~1,200 labelled artefacts;
- everything else: `unvalidated`.

Protocol, with tooling in [`scripts/trace_pack_validation_sample.py`](../scripts/trace_pack_validation_sample.py):

1. Run detection with this pack on the target corpus.
2. `draw --run <id>`: a stratified sample with one stratum per (family × channel), n=30 for the ten most prevalent families and n=8 otherwise, one row per repository. Ignored-only file mentions are a separate stratum.
3. Two raters label each row TP / FP / unsure / 404 independently, then adjudicate. File rows also get *configuration genuine* vs *evidence of use*.
4. Add negative controls: humans named Claude, Devin or Cody; `cursor[bot]` review-only repos; repos that only document an agent; forks; templates.
5. `score --sheet`: per-stratum precision with Wilson 95% intervals. A cell is `strong` only if the lower bound is at least 0.90. Otherwise its rules move to `corroborating` or into the ledger in the next version.
6. Commit the labelled sheet under `packs/validation/2026-11-15/` and record the results in each rule's `provenance.validation` in the next pack version.

## Before freezing

1. The pack needs the schema-v2 matcher, which is still uncommitted work on `main`. Merge that first.
2. Run detection with 2026-11-15 on search 152 and on the run-101 corpus. Confirm the identity-only pairs are recovered, and run `check_trace_pack.py`.
3. Complete the validation protocol for at least the ten most prevalent families.
4. Freeze: `python -m detect.packs freeze --pack packs/2026-11-15.json`. After that the file never changes, and fixes go into a new version.

## Rebuild

```bash
PYTHONPATH=<checkout>/src python scripts/build_trace_pack_2026_11_15.py \
  --baseline packs/patterns \
  --previous packs/sources/2026-11-14/catalogue.json \
  --out packs/sources/2026-11-15/catalogue.json \
  --mapping packs/sources/2026-11-15/baseline-mapping.csv
PYTHONPATH=<checkout>/src python -m detect.packs build \
  --src packs/sources/2026-11-15 --version 2026-11-15 --out packs/2026-11-15.json
PYTHONPATH=<checkout>/src python scripts/check_trace_pack.py \
  --pack packs/2026-11-15.json --previous packs/2026-11-14.json \
  --mapping packs/sources/2026-11-15/baseline-mapping.csv --run 101
```

The generator is deterministic: the same inputs give byte-identical output.

## Known limits

- The extended identities come from vendor documentation and the replication package of arXiv 2603.28592. They have not been observed in our corpus yet. Amp's `Amp-Thread-ID` trailer is `corroborating` until validated.
- `claude` as a PR-author login is `corroborating`: GraphQL drops the `[bot]` suffix, so a human account named `claude` could collide.
- Several files can match through more than one rule, such as a baseline rule and a widened 2026-11-14 rule. Repo-level results are unaffected, but evidence row counts are not comparable across pack versions.
- Discovery mining (unmatched co-author names, bot logins, dot-folders, branch prefixes) is not automated yet.
