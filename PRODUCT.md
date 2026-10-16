# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary users are both equally, on the same single-operator console:

1. Researcher building a defensible corpus: defines a filter, runs a live measurement, freezes results into a named corpus, exports / replays / diffs / cites with per-repo evidence.
2. Operator running repeated measurements: monitors live phase progress with ETA, manages rate limits, resumes failed/stopped runs, audits calls, checks data quality, manages library / corpora / detections.

Situation: localhost console (`127.0.0.1:8000`), single operator, laptop-friendly defaults with raised caps for corpus builds. Frequency ranges from one-off study frames to repeated same-filter measurements over time.

## Product Purpose

Live-only GitHub repository discovery for evidence-backed research corpora.

What it does: validates a filter-spec v1 before any API call, discovers live via GraphQL sharded search past the 1,000-result cap, hydrates full current records, applies virtual filters (file presence, owner country, commits, language bytes), enriches survivors, geo-resolves owners honestly, merges by immutable repo `id`, displays with provenance and truncation warnings, freezes into replayable bundles (bundle.json + corpus.csv + audit log).

Why it exists: a script answers a query; this produces a corpus you can defend — complete as of `ran_at`, with evidence to explain every row, every drop, and every gap.

Success: first-time operator can go open → search → freeze a corpus without docs; every action states cost; every count/status explains itself; no orphans or dead ends.

## Positioning

The intersection none of the alternatives covers: live measurement at a chosen `ran_at`, arbitrary filters including file presence and owner location, coverage below the 10-star floor, frozen per-run evidence with raw upstream responses, audited pacing, and coding-agent detection.

Neighbors it is not: one-off `gh search repos` scripts (same 1,000 cap, no virtual filters, no persistence); pre-crawled catalogs (SEART: fixed columns, 10-star floor, crawl-time freshness); offline archives (World of Code / GH Archive / BigQuery: history, not live selection); analytics dashboards (aggregates, not frozen per-repo corpora); thin API wrappers (pass-through, no evidence bundle).

## Operating Context

Model: Search → Corpus → Detection. A Search queries GitHub live. Finished results freeze into a named Corpus. Detections scan a frozen corpus API-only (windowed depth, labelled as such).

Console routes (must all keep working): `/` dashboard, `/find` new search, `/runs` history, `/runs/{id}` detail + `/results` full table + `/diff` compare + `/detect` + clone controls, `/corpora`, `/filters` library, `/system` status/performance/limits, `/settings` caps, `/metrics`, `/health`.

Workflows: define filter (Common/Advanced on one page) → Check matches → Run search (live, minutes, uses allowance) → watch phase progress (Finding / Saving details / Applying extra rules) → inspect What-happened counters → View all results (URL state) → Export / Clone / Freeze as corpus / Search again / Compare. Library stores recipes; System shows requests left / failures / median response.

Environment: PostgreSQL 17 + Redis 7 + GitHub token from environment only; `docker-compose.yml` for services; project-local PG + WSL Redis on Windows dev. No background pollers between measurements; one executor per run.

## Capabilities and Constraints

Confirmed functionality must remain absolutely unchanged in this redesign — visual reskin only. No functional changes. No UX / IA / copy changes. Same routes, same forms, same controls, same validations, same behaviors.

Technical constraints (hard):

- Stack stays: Python 3.12+, FastAPI + Uvicorn, Jinja2 + vendored htmx + hand-rolled CSS in `src/serve/static/app.css`. No Node, no CDN, no build step at runtime.
- Read paths and forms keep working without JS (current behavior preserved).
- Page, sort, page size stay in URL; CSRF-protected forms; TrustedHost allowlist; localhost default with no auth — do not expose without real auth in front.
- Tokens only in environment; audit logs store fingerprint only; filter-spec files reject token-like fields.
- Dark mode, keyboard shortcuts (`/`, `g h/f/r/l`, `j`/`k`, `Enter`, `?`, `Esc`), `aria-current`, dialog focus trap, status text not color-only — all preserved.
- Undecided: exact redesign scope order (full console vs dashboard + tables + forms first) — visual-only either way.

## Brand Commitments

Name: gitcorpus (repo folder `gitcrawl`). No affiliated / endorsed-by-GitHub marks; User-Agent `gitcorpus/0.0.1`.

Voice: plain words first, every action explains cost, every number/status explains itself, honest data (`~` for estimates, explicit incomplete / tombstone / warning states). Internal vocabulary never a label.

Visual commitments: none binding beyond the incumbent implementation. Current `app.css` header comment declares "terminal-precision" (neutral surfaces, mono numerals, hairline structure, one teal accent) — treated as evidence for redesign, not authority.

## Evidence on Hand

Real product content: `README.md` full pipeline narrative; `design/console-spec.md` (backend/route contract, authoritative); `design/console-ux-redesign.md` (implemented 2026-10-03, IA + copy deck authoritative for labels); `design/how-the-data-flows.md`; `design/corpus-building-efficient-engineering.md`; live templates in `src/serve/templates/` and `src/serve/static/app.css`.

No invented testimonials, customers, benchmarks, pricing, or deployment claims. Demonstration data in future visual work must be labelled synthetic; commercial/factual claims stay uninventable.

## Product Principles

1. Live measurement, frozen evidence — every result carries its `ran_at` and its upstream proof.
2. Honest about limits — approximate, incomplete, unavailable, and unenforceable are stated, never hidden.
3. Cheap screens first, survivors only — cost-ordered enrichment; nothing fetched for a display you won't show.
4. Plain words over pipeline jargon — operator language on the surface, internals behind disclosures.
5. Reproducible by file — filter-spec in, bundle out; same file replays and diffs across machines.

## Accessibility & Inclusion

Known requirements: full keyboard operation with visible shortcuts help; `aria-current` on nav; dialog focus trap; status conveyed by text, not color alone; `prefers-reduced-motion` respected; light + dark themes; read paths usable without JS. No additional product-specific standard established — do not regress these.
