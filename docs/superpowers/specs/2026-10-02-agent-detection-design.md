# Agent-Use Detection Flow — Design

**Date**: 2026-10-02
**Revised**: 2026-10-14 — re-baselined to current `main` and re-checked against the three Robbes papers; see §15 for the change list
**Status**: Revision for review — implementation plan rewrite follows; not yet approved for execution
**Depends on**: US1 discovery, US2 lifecycle, US3 enrichment/serve, US4 console (all shipped), plus 2026-10-03..12 machinery: app settings/limits (`0008`), corpora (`0009`), run progress (`0010`/`0011`), GraphQL discovery (`0012`), audit telemetry (`0014`), adaptive toggle (`0015`, unused by detect v1)
**Spec lineage**: FR-015 (trace packs), FR-016 (commit history), FR-017 (PR channel); this design is the API-only first tier of those tracks.

## 1. Context

The console already produces frozen runs: a `find` run discovers repos live, stores them in `run_items`, and exports a bundle; a finished run can be frozen as a named corpus (`corpora`, migration `0009`). Agent detection is Phase 6 (T039+) and still unbuilt (verified 2026-10-14). This design adds a second run kind — `detect` — that runs the research papers' detection channels over a find run's frozen `run_items`, entirely through the GitHub API, with no clone and no BigQuery. Named corpora are an entry point for detection, not a separate source: a detect run always points at the underlying find run via `runs.source_run_id`.

Decisions made with the operator (2026-10-02, re-confirmed 2026-10-14):

- v1 covers **API-only, all channels**: files (incl. content weighting), authors/committers, branches, labels, bots, commit trailers, PR metadata, issues/users. Deep history (full-history commits, full-history adoption dates/ratios, per-file stats) is explicitly out of scope and documented as the next tier.
- Detection defaults to **all items of the source run**, with an optional top-N limit for pilot runs. No per-row manual selection.
- Results surface as **summary + per-repo matrix + evidence drill-down**, exportable.
- Architecture: **detection is a first-class run type** reusing the runs table, executor (progress, cancel, resume), audit telemetry, history, export, and bundle machinery.
- **Entry points** follow the console redesign (`design/console-ux-redesign.md` §4.7): a finished search's page and corpus pages launch detection; "Detections" is a first-class nav destination. The already-marked-up greyed buttons are wired, not redesigned.
- **Source model**: `runs.source_run_id` → find run. Corpus pages resolve through `corpora.source_run_id`; detect runs never FK a corpus, so deleting a corpus cannot orphan detection history.
- **Legal redaction** (2026-10-14): commit-author/committer emails are matched in memory only; no email is ever persisted in the database, bundles, exports, or audit rows (`docs/legal-gates.md` §4/§5).
- **Pacing** (2026-10-14): static limiter + deadline only. The AdaptiveController (default-off, wired to hydration batches) is not integrated in v1; the sprint/marathon run-modes idea is a later, orthogonal policy layer.
- **Agent selection** (2026-10-14): the options page selects which agents to scan for — any subset of the pack's 63 agents plus the `Generic` pseudo-agent, "Select all" by default. Matching, evidence, per-repo rollups, summaries, and exports are scoped to the selection; the fetch cost is unchanged (the same calls are made, matching is narrowed).
- **Heuristic fidelity** (2026-10-14): heuristics and pipeline rules re-checked against the three Robbes papers (`Robbes-2026-Agentic-Much`, `Robbes-2026-Agentic-Very-Much`, `Robbes-2026-Heuristics-Companion`): branch and label heuristics apply to **PR data** (head branches and PR labels), AI-assisted PRs propagate to their commits, commit **committer** identities match, noise commits are filtered, and a windowed commit ratio + adoption level is reported. §14 maps every signal the papers mention to its v1 channel/rule or its documented deeper tier.

## 2. Goals / Non-goals

**Goals**

1. One action from a finished search's detail page or a corpus page: "Detect agent use", plus a "Detections" section listing detect runs and results.
2. An options page: pack version, agent multi-select (all 63 + Generic, select-all default), channel checkboxes with select-all, top-N limit, cost/time estimate.
3. A detection run that scans the frozen source-run items API-only and stores per-repo, per-agent, per-channel evidence keyed by pack version.
4. Summary page: repos scanned, % with any signal, per-agent and per-channel counts, per-repo agent matrix with evidence drill-down, CSV/JSON export.
5. Corpus building and detection stay separate: a detect run never calls discovery/search endpoints.
6. Documentation deliverable `docs/detection-tiers.md`: what is knowable API-only vs what requires clone/BigQuery.

**Non-goals (v1)**

- Full-history commit analysis: beyond the `first:100` window, full-history commit ratios/adoption dates, diffstats (FR-016 deep tier). Windowed versions ship in v1 (labelled).
- Per-file first-added dates, LOC, two-clone inventory (FR-018).
- Full-history PR sweep beyond the GraphQL window (FR-017 deep tier).
- κ/adjudication validation UI (FR-021) — evidence is exported for it.
- Pack editing UI; packs are frozen files loaded read-only.
- Clone-based ground truth; `clones/` stays a manual/optional follow-up.

## 3. Invariants

1. **No discovery calls.** Detect runs call only per-repo REST/GraphQL endpoints. Enforced by a test that fails if any discovery endpoint is touched during a detect run: REST `/search/repositories`, `/search/code`, `/repositories?since=`, org/repo enumeration, or GraphQL `search(...)` count/page queries.
2. **Sourced from frozen items.** Candidate membership comes from the source run's `run_items` snapshot, never a live re-query. Top-N selection is deterministic: order by `stargazers DESC, repo_id ASC`, take N. (Signal *content* is fetched live per repo at detect time and stamped with `detected_at`; corpus membership and signal freshness are separate concerns.)
3. **Versioned results.** Every evidence row carries `pack_version`; reruns with a new pack are new rows on a new run, never overwrites.
4. **Labelled depth.** Depth windows (last-100-commits, recent PRs/issues) are stored in the run spec and shown in the UI; no shallow result is presented as a census.
5. **No silent partials.** Unavailable repos, truncated trees, GraphQL caps, and missing channels are counted and shown, never dropped.
6. **Selection-scoped.** Evidence, rollups, summaries, and exports contain only the agents and channels selected for the run; unselected agents are never matched, counted, or stored.

## 4. Data model (migration `0016_detect_runs` at execution, down_revision `0015`)

Head is `0015_adaptive_settings_toggle` (verified 2026-10-14). The detect migration claims the next free revision when the plan executes (`0016` today, `down_revision="0015"`; renumber if another plan lands first). `trace_packs` exists only in `data-model.md`, never in a migration — this migration creates it.

```sql
CREATE TABLE trace_packs (
  version         TEXT PRIMARY KEY,
  authors         JSONB NOT NULL,
  files           JSONB NOT NULL,
  branches        JSONB NOT NULL,
  labels          JSONB NOT NULL,
  bots            JSONB NOT NULL DEFAULT '[]',
  generic_weights JSONB NOT NULL DEFAULT '{}',
  exclusions      JSONB NOT NULL DEFAULT '["CONVENTIONS.md"]',
  frozen_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE runs
  ADD COLUMN kind TEXT NOT NULL DEFAULT 'find' CHECK (kind IN ('find','detect')),
  ADD COLUMN source_run_id BIGINT NULL REFERENCES runs(id),
  ADD COLUMN result_summary JSONB NULL;      -- detect: per-agent/per-channel counts, windowed commit ratio + adoption level at finish
CREATE INDEX runs_kind_idx ON runs (kind, created_at DESC);
CREATE INDEX runs_source_idx ON runs (source_run_id) WHERE source_run_id IS NOT NULL;

ALTER TABLE run_items
  ADD COLUMN detection JSONB NULL;           -- detect runs: per-repo rollup (selected agents only)
                                             -- {agents:[...], channels:{...}, unavailable:bool, first_signal_at, commit_ratio, adoption_level, notes:[...]}

CREATE TABLE detection_evidence (
  id            BIGSERIAL PRIMARY KEY,
  run_id        BIGINT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
  repo_id       BIGINT NOT NULL REFERENCES repos(id),
  agent         TEXT NOT NULL,               -- canonical tool id from tools.csv
  channel       TEXT NOT NULL CHECK (channel IN
                  ('file','author','branch','label','bot','commit_trailer','pr_metadata','issue')),
  evidence      JSONB NOT NULL,              -- {path, sha, commit, branch, label, pr, snippet, ...}
  pack_version  TEXT NOT NULL REFERENCES trace_packs(version),
  detected_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX de_run_repo_idx ON detection_evidence (run_id, repo_id);
CREATE INDEX de_run_agent_idx ON detection_evidence (run_id, agent);
CREATE INDEX de_run_channel_idx ON detection_evidence (run_id, channel);
CREATE INDEX de_repo_idx ON detection_evidence (repo_id);
```

- `trace_packs` is created in this migration (see above).
- For detect runs, `runs.filter_spec` holds the detection spec and `filter_hash` is its sha256, so replay/diff/export reuse existing machinery:
  `{kind:"detect", source_run_id, pack_version, agents:null|[...], channels:[...], limit:null|N, windows:{commits:100, prs:100, issues:100}, base_filter_hash}` (`agents` null = all; `generic` is a valid entry).
- Detect-spec validation lives in a new `src/serve/detect_spec.py`, mirroring `src/serve/filter_spec.py` (local `400` + hint before enqueue).
- A detect run materializes one `run_items` row per scanned repo (same snapshot semantics as find), with `detection` rollup and `virtuals` left as-is.
- Summary counts live in `runs.result_summary` at finish (fast pages); raw truth remains the evidence table. Summary includes the windowed AI-assisted commit ratio and adoption level (None / Experimental <1% / Limited 1–5% / Consistent 5–20% / Pervasive >20%), explicitly labelled as windowed (last 100 commits), plus the windowed first-signal date.
- `agents` in the run spec scopes matching (null = all). `generic` (AGENTS.md / `ai-generated` label) is a first-class selectable pseudo-agent, never attributed to a specific agent.
- Source find runs are never mutated.
- `runs.source_run_id` (detect → find run) is distinct from `corpora.source_run_id` (corpus → find run); both may point at the same run. The corpora list's "Last detection" column resolves through `corpora.source_run_id` and picks the latest detect run for that run id.
- **Redaction contract**: `detection_evidence.evidence` never contains commit-author/committer emails. The author channel persists `{login, commit, field, pattern}` (field classifies what matched: login/name/email), and commit-trailer snippets are stored with any email replaced by `<email>`. Enforced by test across DB, bundle, export, and audit.
- Statuses include `cancelled`; detect runs use the standard progress columns (`progress_phase/done/total/updated_at/started_at`) written through the executor's `ProgressReporter`, and are resumable via the existing `/runs/{id}/resume` route (its detect branch and `reset_run_artifacts` evidence cleanup already exist on `main` and become live).

## 5. Pack management

- Source of truth for patterns: `labri-progress/agent-impact` `config/patterns/{authors,files,branches,labels,tools,bots}.csv` (public, verified 2026-10-02; documented in the thesis repo `research-notes.md`). Schema: pattern files are `pattern,type,subtype` where `subtype` is the tool label; `tools.csv` is `name,url`. Extra files (`counts.csv`, `rg_patterns.csv`, `top-orgs.csv`) are ignored.
- Matching fidelity: every pattern is a Python regex, case-sensitive, matched as the replication package's `code/heuristics.py` does — one combined alternation per channel with a named group per `subtype`; file patterns get bare dots escaped and a `(?:^|/)` anchor.
- `bots.csv` is **generic CI-bot noise** (dependabot, renovate, `[bot]` accounts) used for exclusion/QA evidence — it is not agent detection. Agent bot accounts (`copilot-swe-agent`, `devin-ai-integration`, `factory-droid[bot]`, …) are rows in `authors.csv`. Bot-channel hits are stored but never counted as adoption.
- Import converts the CSVs unchanged into a vendored `packs/patterns/` snapshot and a versioned pack file `packs/<YYYY-MM-DD>-<sha8>.json` with `{version, agents(name→url), authors[], files[], branches[], labels[], bots[], generic_weights, exclusions}`; `generic_weights` defaults to down-weighting shared `AGENTS.md` (whose subtype is `Generic`, so it is flagged rather than attributed to a specific agent); `exclusions` defaults to `["CONVENTIONS.md"]`.
- `tools.csv` is the agent roster (63 agents in the current pack); the pack build adds the `Generic` pseudo-agent (AGENTS.md / `ai-generated` label). The options page selects from this roster. Any per-heuristic validity metadata the source provides is preserved in the pack; the immutable pack version remains the record.
- A freeze command validates the pack and upserts it into `trace_packs`; packs are immutable once frozen. The UI offers a read-only dropdown of frozen versions; default = latest.
- Attribution: a match maps to the `subtype` recorded by the replication package; per-agent evidence rows are written (one row per agent per signal).

## 6. Components, channels and API mapping

New code:

- `src/detect/packs.py` — CSV import, pack build/validate/freeze/load.
- `src/detect/channels.py` — one detector per channel; pattern matching only.
- `src/detect/attribution.py` — pattern→agent mapping, generic weights, exclusions, evidence dedupe.
- `src/detect/estimate.py` — calls/time estimate from channels × candidates and live settings (`limiter_max_concurrent`, `request_deadline_seconds`), calibrated to the settled operating point (batch 20–29, concurrency 17–20) so estimates track actuals.
- `src/detect/orchestrator.py` — candidates from source `run_items`, cost-ordered channel execution with bounded concurrency (`limiter.bound_concurrency`), per-phase `ProgressReporter` updates, audit hook with `detect:<channel>` phases, rollup + `result_summary`, evidence CSV + bundle writing.
- `src/serve/detect.py` + templates — `/detections` list, options page, and the detect rendering of the run detail page.
- No limiter change needed: the `graphql` point bucket and the `/graphql` resource mapping shipped 2026-10-08 (`src/limiter/buckets.py`, `src/lib/gh_client.py`); detect rides the same transport (`request_with_retry`) and inherits bucket limits, reset-anchored windows, pool-wide secondary pauses, and deadline binding. The unreachable detect-resume branch in `src/serve/app.py:855-868` already names the integration contract (`detect.orchestrator.run_detection`, `detect.packs.load_frozen`, `serve.detect_spec.parse_detect_spec`); the implementation provides those exact names.

Channels:

| Channel | Source call | Extra calls/repo | Depth |
|---|---|---|---|
| `file` | `GET /repos/{o}/{r}/git/trees/HEAD?recursive=1` + `GET .../contents/.gitignore` (the paper's "visible only via ignore" signal) | 2 | full tree + ignore file |
| `author` | GraphQL `history(first:100)` author **and committer** name/email/login (agent users) | shares history call | last 100 commits (labelled) |
| `branch` | PR head branches (`headRefName`) from the PR query — the papers' branch heuristics are PR branches (`codex/…`, `copilot/fix-…`) | shares PR call | recent PR window (labelled) |
| `label` | PR labels from the PR query (the papers' `is:pr label:codex` style heuristics) | shares PR call | recent PR window (labelled) |
| `bot` | commit author/committer identities from the history call matched against `bots.csv` (generic CI bots; exclusion only) | shares history call | last 100 commits (labelled) |
| `commit_trailer` | GraphQL `history(first:100)` messages: co-author trailers (casing variance per the papers) + extra trailers (`Generated by: …`) | shares history call | last 100 commits (labelled) |
| `pr_metadata` | GraphQL recent PRs: labels, headRefName, body snippet, author login, Codex body marker | 1 | recent window, default 100 PRs (labelled) |
| `issue` | GraphQL recent issues + PR comments: known agent users as assignees, authors, or commenters (issues as task descriptions) | 1 | recent window, default 100 (labelled) |

- Full selection ≈ **2 REST + 3 GraphQL calls per repo** (tree, `.gitignore`; history, PRs, issues — GraphQL cost ≈ 1 point each with shallow windows). Branch/label/bot/author/commit-trailer all share existing calls.
- ETag/conditional requests reused from hydration where available; `304` responses do not consume quota.
- Ordering: cheapest channels first within a repo so a rate-limited run still yields partial signal; repos processed in deterministic top-N order (`stargazers DESC, repo_id ASC`) with bounded concurrency from `app_settings.limiter_max_concurrent`.
- Rate limit: the shipped transport carries this — Redis buckets (`search`/`core`/`code_search`/`graphql`), reset-anchored windows reconciled from headers, per-endpoint concurrency cap, retry/backoff classifier, and pool-wide secondary 403/429 pauses. Token pool from `GITHUB_TOKENS` as today. AdaptiveController is not used in v1 (default-off; wired to hydration batches only).

## 7. Routes and UI

New routes (all reuse CSRF/validation patterns); naming follows the console redesign IA:

| Method | Path | Purpose |
|---|---|---|
| GET | `/detections` | Detect-run list (nav destination): source search/corpus, status, summary, links |
| GET | `/runs/{id}/detect` | Options page for an eligible source run (`done`/`partial`); corpus pages link here via their source run |
| POST | `/runs/{id}/detect` | Validate, create detect run, enqueue, 303 → `/runs/{detect_id}` |
| GET | `/runs/{id}/detect-estimate?channels=&limit=` | htmx: calls/time estimate for current options |
| GET | `/partials/runs/{id}/detect-status` | htmx progress poll (repos scanned, signals, failures) |
| GET | `/runs/{id}/export?format=json\|csv\|detections` | Run-scoped export; detect runs: `detections` = flat evidence CSV streamed from the DB, `csv` = per-repo rollup CSV, `json` includes the per-repo `detection` rollup; unfinished detect runs answer `409 run_not_ready` |
| POST | `/runs/{id}/resume` | Existing route; its detect branch becomes live (evidence reset + requeue) |

- **Nav**: the greyed "Detections" span becomes a real `/detections` link (console redesign §4.7).
- **Search detail + corpora pages**: wire the existing greyed "Detect agent use" buttons (`run_detail.html`, `corpora.html`, `corpus_detail.html`); eligible when the source run is `done`/`partial`. The corpora list "Last detection" column populates from the latest detect run over `corpora.source_run_id`.
- **Options page**: pack version dropdown; agent multi-select (searchable, all 63 + `Generic`, "Select all" default, at least one agent or channel required); 8 channel checkboxes with descriptions and calls/repo; "Select all" (default on); top-N slider+digit (default all); live estimate panel (calls, wall-clock at current token count; agent selection does not change call count); start button.
- **Detect run detail** (run detail branches on `kind`): status banner with the standard progress/ETA/cancel/resume controls; summary cards (repos scanned, % any signal, per-agent top-N counts, per-channel counts, pack version, agents scanned N of 63, depth windows, windowed commit ratio + adoption level, first signal date); per-repo table (agent chips per row, selected agents only) with expandable evidence grouped by channel; server-side filters (has-signal, agent, channel — see revision below); export.
- **Find run detail**: latest-detect badge showing signal count from the latest detect run over that source run (cheap join), linking to it.
- **History**: kind badge on `/runs`; replay uses the stored detect spec; diff between two detect runs over the same source run is a later task (v1.1) — diff for find runs is unchanged.
- **Docs link**: options page links to `docs/detection-tiers.md`.

### Revision 2026-10-18 — run-wide evidence filters and streamed exports

Prompted by run #99 (17,757 repos, 3,816,399 evidence rows): the original per-repo filters only filtered the page in the DOM, and exports could serve a stale or mid-run-partial CSV.

- **Filters are server-side, run-wide.** The filter row is a GET form; state lives in the URL (`?signal=1&agent=…&channel=…&page=N`). `signal` selects repos with at least one non-bot evidence row (the "With any signal" card's definition); `agent`/`channel` compose with AND and restrict the evidence rendered inside each repo to matching rows; the dropdowns list the whole run's agents/channels. Pagination counts and fetches the filtered set; pages stay bounded (25 repos × ≤300 evidence rows).
- **Membership is answered by a derived facet table.** Migration `0018_detection_repo_filters` adds `detection_repo_filters (run_id, repo_id, agent, channel)` — the deduplicated facet projection of `detection_evidence` (71,400 rows for run #99 vs 3.8M) — backfilled from evidence and written by both orchestrators in the same transaction as evidence rows; `reset_run_artifacts` clears it. The migration also sets `autovacuum_vacuum_insert_scale_factor`/`autovacuum_analyze_scale_factor = 0.02` on `detection_evidence` (insert-only tables otherwise never get their visibility map set). Filtered pages: 0.2–0.6 s on run #99 (was 5–15 s on live evidence queries).
- **Evidence CSV (`format=detections`)** — one row per evidence item, always regenerated from the database with a server-side cursor in bounded batches (never `.all()`, never a cached bundle file), flat schema with the raw JSON last: `run_id, repo_id, full_name, agent, channel, pack_version, detected_at, commit_sha, path, path_source, file_size, file_empty, file_generic, file_weight, pr_number, branch_head, branch_match, label, issue_number, issue_role, login, identity_field, snippet, propagated, evidence_json`. The completion-time bundle `detections.csv` uses the same schema.
- **Repo CSV (`format=csv`) for detect runs** — one row per scanned repo: corpus fields plus `has_signal, unavailable, failure_class, adoption_level, commit_ratio, first_signal_at, agents` and per-channel row counts; deliberately different from the evidence schema. `format=json` gains the per-repo `detection` rollup. Detect filenames: `gitcorpus-detect-{id}-evidence.csv` / `-repos.csv` / `.json`.
- **Export gating** — detect export buttons are hidden while queued/running and the routes answer `409 run_not_ready`; exports always reflect the finished run's full stored evidence (verified on run #99: 3,816,399/3,816,399 rows, ~8 MB peak memory).
- **Excel-safe exports, two export groups, elapsed time (follow-up, same day)** — every detection CSV export is Excel-safe (find-run CSVs are deliberately left byte-identical): UTF-8 BOM, exactly one physical line per record, embedded newlines escaped as the two characters `\n` (CJK snippets round-trip as real Unicode). The detail page offers two export groups instead of three buttons, each CSV or JSON and each with an `i` info popover: evidence (`detections` CSV / `detections-json` JSON — the streamed JSON twin of the evidence CSV, filename `gitcorpus-detect-{id}-evidence.json`) and repos (`csv` rollup / `json` repos with the `detection` rollup). Runs also show elapsed time: a `Time elapsed` line on the detection detail page and a `Time elapsed` column on the `/detections` history list (shared `_format_span`/`_elapsed_seconds`).

## 8. Evidence and attribution rules

- One evidence row per `(repo, agent, channel, signal)`; identical signals dedupe.
- **No emails, ever.** Author-channel patterns match author login/name/email in memory; persisted evidence carries `{login, commit, field, pattern}` and never the email value. Commit-trailer snippets redact any email to `<email>` before storage. Applies to the database, bundles, exports, and audit rows.
- File matching is regex-based over tree paths plus `.gitignore` lines; `AGENTS.md` (subtype `Generic`) is flagged with its weight, `CONVENTIONS.md` is excluded; generic hits never inflate a specific agent's count.
- Commit-trailer matching: co-author trailers and "generated with" footers in the history window, using the replication package's author regexes (case-sensitive).
- PR matching: head-branch regex, label regex, author login against known agent users, and the hardcoded Codex body marker `https://chatgpt.com/codex/tasks`.
- **PR→commit propagation** (the papers' Codex mechanism): when a PR matches branch/label heuristics or is authored by a known agent user, every commit in that PR authored by the PR's author is tagged AI-assisted for the matched agent(s), even without commit trailers. Squash merges condense the PR into one commit, which inherits the tag — documented imprecision, per the papers.
- Generic CI bots (`bots.csv`, matched from commit author/committer identities) are stored as channel `bot` evidence for QA only and are excluded from `result_summary.agents` and per-repo agent lists.
- **Noise filtering**: merge commits, revert commits, version-bump releases, and housekeeping changes are excluded from commit counts and the commit ratio (recorded as filtered, not silently dropped).
- **Windowed metrics**: `result_summary` carries the AI-assisted commit ratio within the history window and its adoption level (None / Experimental <1% / Limited 1–5% / Consistent 5–20% / Pervasive >20%), always labelled "windowed — last 100 commits"; the full-history ratio is the documented deeper tier.
- **Issue channel**: known agent user accounts as issue assignees/authors/PR-commenters in the recent window; evidence stores `{login, issue/pr number, role}` — the companion's "issues as task descriptions" signal.
- v1 stores which channel(s) fired and the raw evidence; it does not compute a probabilistic confidence. Papers' baseline (~0.5–1% FP, ~3% borderline) is stated in docs and exports.
- Disabled/opt-out agents (Claude opt-out, Pi/OpenCode unsigned) mean detection is an undercount; stated in the UI and export metadata, never silently corrected.
- **CSV formula injection is a conscious non-goal**: snippet/path text is evidence and is exported verbatim, so cells are not sanitized against spreadsheet formula prefixes.

## 9. Error handling

- Repo `404`/private → `detection.unavailable=true`, counted, no evidence; no tombstone changes (source semantics untouched).
- Tree truncated (>100k entries/7 MB) → fall back to per-matched-path `contents` probes; if still incomplete, mark `partial` with reason.
- GraphQL resource-cap partials/timeouts → split or narrow once, then mark channel partial; never retry the same shape.
- `401`/credential lockout → loud fail (existing token incident behavior). `429/403` → existing limiter classifier.
- Missing/failed pack, unknown agent mapping, or empty source run → local `400` with hint before enqueue.
- Any channel failure degrades the run to `partial` with per-channel failure counters in `result_summary`.
- Deadline: detect runs bind the standard request deadline (`app_settings.request_deadline_seconds`); on expiry the run ends `partial` with a recorded reason, never silently.
- Cancellation is honored between channels/repos (existing `cancelled` status), and resume re-queues through the existing route; startup orphan recovery marks interrupted detect runs `failed` like any other run.

## 10. Documentation deliverable

`docs/detection-tiers.md`: table of every signal (8 channels) × tier:

1. **API-only, full** — file existence (config/rules/guidance) + guidance content, `.gitignore` visibility, PR branches/labels.
2. **API-only, windowed** — authors/committers, commit trailers, PR metadata (incl. PR→commit propagation), bots, issues/users, windowed commit ratio + adoption level, windowed adoption date.
3. **Clone required** — per-file first-added dates/change counts/line counts, commit size metrics (added/deleted lines, files), diffstats, ground-truth content audit, full-history commit ratio/adoption date, conventional-commit classification.
4. **BigQuery required** — full windowed commit history beyond `first:100`, 2025+ PR bodies at scale.
5. Pointers: the community heuristics repository (per-heuristic validity periods, sample trace datasets) and the undetected-activity discussion (signing disabled, dotfiles, manual commits) — undercount caveats.

Each row states call cost, freshness, and what it cannot tell you. Both links are part of the deliverable: the options page and `design/research.md` D13.

## 11. Testing

- **Unit**: per-channel pattern matching from pack fixtures; attribution weights/exclusions; agent-selection scoping; deterministic top-N selection; estimate math; dedupe; windowed commit-ratio/level math; noise filtering; PR→commit propagation.
- **Contract**: every new route (status codes, hints, CSRF, 303); `kind` enforcement (detect needs `source_run_id`); agent/channel selection validation (empty selection rejected); export headers/shapes; detect resume (the existing branch + evidence reset); migration up/down at the claimed revision.
- **Integration (offline fixtures)**: repo with `CLAUDE.md` + Claude trailer + `codex/` PR branch → expected agent set and evidence (Claude via file/trailer, Codex via PR branch→commit propagation); a run selecting only those agents never emits others; committer-identity match; noise commit filtered; 404 repo counted unavailable; tree-truncation fallback; GraphQL cap → partial; retry via limiter fake; progress columns written; audit rows carry `detect:<channel>` phases.
- **Invariant**: detect run over a seeded source run makes zero discovery calls — REST `/search/*`, `/repositories?since=`, and GraphQL `search(...)` bodies (spy on the HTTP client).
- **Redaction**: a source run whose commits carry emails yields zero emails in `detection_evidence`, bundles, exports, and `audit_log` (enforced by test).
- **Golden**: detection summary + evidence CSV snapshot; new `/detections` list and detect run/options pages added to golden `PATH_PARAMS` with regenerated snapshots; OpenAPI re-pinned.
- **Fixtures**: new tests use the central `clean_db` fixture (local `TRUNCATE` fails `test_fixture_centralization.py`); new tables join `FULL_TRUNCATE_TABLES`.
- **Live smoke (token-guarded, optional)**: 3-repo fixture org, all channels, one pack.
- Coverage floor stays 93.

## 12. Success criteria

1. A 10k-item Rust find run can be detected API-only, all channels, producing summary + per-repo matrix + evidence export, with zero discovery calls and zero unlabelled partials.
2. Same source run + same pack + same options reproduces the same evidence set on rerun (modulo recorded live drift: ETag/`fetched_at` differences are reported).
3. `docs/detection-tiers.md` shipped and linked from the options page and `design/research.md` D13.
4. Top-N pilot (e.g. 200 repos) completes and estimates match actuals within a stated tolerance.
5. No commit-author/committer email exists in the database, bundles, exports, or audit log after a full detect run.
6. A run selecting only Claude Code and Codex produces evidence, summaries, and exports for exactly those agents (plus `generic` only if selected).

## 13. Assumptions / open items

- Pattern CSVs are public and verified (2026-10-02, `labri-progress/agent-impact`); the import vendors a snapshot under `packs/patterns/` and records the pack digest.
- GraphQL `history(first:100)` is enough for the pilot; deeper history is the documented next tier.
- The bot signal is windowed like every commit channel; absence in the window does not prove absence of a bot.
- PR/issue window defaults 100; the papers' 10k-PR cap applies only if windows are widened later.
- The 63-agent roster and pattern sets come from the replication package (`tools.csv` + the four pattern files + `bots.csv`); the community heuristic repository's validity periods are preserved when present.
- Adaptive pacing, sprint/marathon run modes, and detect-run diff are deferred (v1.1+). The run-modes idea (2026-10-11) is orthogonal; if it (or any other plan) lands first, detection renumbers its migration.
- The dead detect scaffolding on `main` (`app.py` resume branch, `executor.reset_run_artifacts` guard, greyed UI) is satisfied by the implementation — the resume branch's imported names are the integration contract.

## 14. Robbes heuristic coverage map (2026-10-14)

Every signal and rule named in the three Robbes papers (`Agentic Much`, `Agentic Very Much`, `Heuristics Companion`) mapped to this design:

| Paper signal / rule | Where it lives here |
|---|---|
| File heuristics: config / rules / guidance files (93) | `file` channel, v1 (full tree) |
| `.gitignore`-hidden agent files | `file` channel, v1 (`.gitignore` scan) |
| `CONVENTIONS.md` excluded (FP risk) | pack `exclusions`, v1 |
| `AGENTS.md` generic (not Codex) | `Generic` pseudo-agent, v1 |
| Guidance-file content (weighting, permissions/MCP hints) | `file` content fetch per FR-015, v1 |
| Author heuristics (79): co-author trailers, casing variance | `commit_trailer` channel, v1 |
| Agent as commit author **or committer** (name/email) | `author` channel, v1 |
| Extra trailers (`Generated by: …`) | `commit_trailer` channel, v1 |
| Branch heuristics (20) on **PR head branches** | `branch` channel (PR data), v1 |
| Label heuristics (4) on **PR labels** | `label` channel (PR data), v1 |
| PR authored by known agent user | `pr_metadata` (author login), v1 |
| Codex body marker | `pr_metadata`, v1 |
| PR→commit propagation (commits by PR author tagged AI-assisted) | §8 rule, v1 |
| Squash-merge imprecision | documented caveat, v1 |
| Agent user accounts | `author` identities + `issue` channel, v1 |
| Issues as task descriptions / assignment / participation | `issue` channel, v1 |
| PR comment interactions | `issue` channel (commenter role), v1 |
| General bot patterns (exclusion) | `bot` channel (`bots.csv`), v1 |
| Merge/revert/version-bump/housekeeping filtering | §8 noise rule, v1 |
| Adoption date (earliest agent-file or AI-assisted commit) | windowed `first_signal_at`, v1; full = tier 3 |
| Commit ratio + levels (Experimental/Limited/Consistent/Pervasive) | windowed, v1; full = tier 3 |
| Per-file stats: first-added, change count, lines | clone tier (tiers doc) |
| Commit size metrics (added/deleted lines, files) | clone tier |
| Conventional-commit task classification | clone/study tier |
| Study sampling (≥10 stars, ≥5k LOC, ≥100 commits, no forks) | corpus building, not detection |
| Dotfiles-repository filtering | corpus building note; tiers doc |
| Signing disabled / manual commits / Pi-OpenCode unsigned | undercount caveats, docs + UI, v1 |
| FP/borderline validation (0.5–1%, 3%) | docs + exports, v1 |
| Community heuristic repo + validity periods | pack versioning, v1 |
| Sample trace datasets | tiers doc pointer |
| Undetected-activity heuristics (verbose messages, emojis, process metrics) | tiers doc future work |

## 15. Revision log (2026-10-14)

Re-baseline audit: the channel/evidence design survived intact; the implementation plan had drifted mechanically. Changes in this revision:

- Migration `0008`/`0007` → next free revision (`0016`, down `0015` today); number claimed at execution.
- Source model fixed: `runs.source_run_id` → find run; corpora are an entry point, not an FK target.
- Redaction: no commit-author/committer emails persisted anywhere (author + commit-trailer channels).
- IA: "Detections" nav, search + corpus entry points, greyed buttons wired (`design/console-ux-redesign.md` §4.7, §7).
- Machinery: deadline binding, standard progress columns/reporter, audit `detect:<channel>` phases, settings-sourced estimate; the `graphql` bucket and `/graphql` resource mapping are already shipped (dropped from scope).
- Pacing: static limiter only; AdaptiveController not integrated (decision 2026-10-14).
- Plan rewrite must fix: central `clean_db` fixtures (no local `TRUNCATE`), `Deps.token_fp`, golden `PATH_PARAMS` + regenerated snapshots, `export_run`/`_BUNDLE_FILES` for `detections.csv`, deleted-module imports (`lib.gh_client.RequestFailed`, `trees_first.fetch_tree`), and current executor signatures (`create_run`, `RunPayload`).
- Robbes re-check: branch/label channels re-sourced from PR data; PR→commit propagation added; committer matching added; bot channel re-sourced from history (contributors call dropped); noise filtering + windowed commit ratio/adoption level added; `issue` channel added (8 channels); agent multi-select added with the `Generic` pseudo-agent; §14 coverage map added.
