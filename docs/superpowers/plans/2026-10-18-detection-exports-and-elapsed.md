# Detection evidence exports: Excel-safe CSVs, two export groups with CSV/JSON, elapsed time

**Base:** `255bc31` (run-wide detection filters, streamed exports, facet table — shipped and verified)
**Spec:** user request 2026-10-18 (three numbered asks). Follow-up to the detection evidence/export work.

## Global Constraints (bind every task)

- Python 3.12, FastAPI/Starlette, SQLAlchemy 2.1 with psycopg3. No new dependencies.
- Run tests with `.venv\Scripts\python.exe -m pytest ...` from the repo root (Windows, PowerShell). The databases are already configured via env vars (`TEST_DATABASE_URL`, `DATABASE_URL`).
- Detect-run exports ALWAYS regenerate from the database with a server-side cursor (`connection.execution_options(stream_results=True)` + `result.partitions(n)`); never `.all()`, never a cached bundle file. Exports keep returning `409 run_not_ready` while a detect run is queued/running and the buttons stay hidden until finished.
- Evidence CSV schema is pinned (order matters): `run_id, repo_id, full_name, agent, channel, pack_version, detected_at, commit_sha, path, path_source, file_size, file_empty, file_generic, file_weight, pr_number, branch_head, branch_match, label, issue_number, issue_role, login, identity_field, snippet, propagated, evidence_json` (constant `EVIDENCE_CSV_HEADER` in `src/serve/executor.py`).
- Repo CSV schema is pinned (`DETECT_REPO_CSV_HEADER` in `src/serve/runs.py`).
- CSV exports must be Excel-safe: UTF-8 with BOM (`utf-8-sig`) and exactly ONE physical line per record (embedded newlines escaped as the two characters `\n`).
- Detect filenames: `gitcorpus-detect-{run_id}-evidence.csv` / `-evidence.json` / `-repos.csv` / `.json`.
- TDD: write the failing test first, watch it fail, implement, watch it pass.
- After template changes: regenerate golden snapshots with `$env:UPDATE_GOLDEN='1'; .venv\Scripts\python.exe -m pytest tests/golden -q`, then re-run `tests/golden` WITHOUT the env var.
- `ruff check src tests` and `black --check src tests` must pass at task end; do not introduce new `mypy` errors (mypy is not CI-gated).
- Do not commit unrelated files; commit the task's own changes with a concise message in the repo's style (`serve: ...`, `detect: ...`, `docs: ...`).
- Human-visible text: plain English, no emojis.

## Task 1: Excel-safe single-line CSVs with read-back validation

**Why:** `gitcorpus-detect-99-evidence.csv` (3.8M rows) is valid CSV (every record parses to exactly 25 fields) but looks corrupted in Excel: it is UTF-8 without BOM (mojibake on non-ASCII snippets like Chinese commit messages), multi-line commit snippets put 2,000 records on 2,471 physical lines, and Excel silently caps at 1,048,576 rows (which is why the user saw "~1m rows"). Make the files Excel-safe and prove it by reading them back.

**Changes**

1. `src/serve/executor.py`
   - Add `def _single_line(value: str) -> str:` replacing `"\r\n"`, then `"\r"`, then `"\n"` with the literal two-character sequence `\n` (backslash + n).
   - Apply it inside `_csv_cell` for string values only (bools stay `"true"`/`"false"`, `None` stays `""`). This automatically covers `evidence_csv_row`, `_detect_repo_cells`, and `_write_corpus`; find-run corpus files have no multi-line fields, so their bytes do not change.
   - `_write_detections` opens the file with `encoding="utf-8-sig"` so the bundle `detections.csv` files also get a BOM.
2. `src/serve/runs.py`
   - `_detections_chunks` and `_detect_repo_chunks`: the first yielded chunk is the BOM + header row (write `"\ufeff"` into the buffer before `writerow`); subsequent chunks unchanged (header no longer repeated).
   - Do NOT change `_csv_chunks` / `_json_chunks` / `_file_chunks` (find-run behavior stays byte-identical).

**Tests (write first, watch fail)**

- `tests/unit/test_executor_unit.py`:
  - `_csv_cell("a\r\nb\nc") == "a\\nb\\nc"` (literal backslash-n), and a newline-free value is unchanged.
  - `test_write_bundle_streams_detections_from_source`: the written file's first 3 bytes are the UTF-8 BOM (`b"\xef\xbb\xbf"`), and a row whose `snippet` contains `\n` occupies exactly one physical line (count `\n` in raw bytes == number of rows + 1).
- `tests/contract/test_detect_pages.py`:
  - Update `test_detections_export_renders_flat_evidence_csv`: decode with `response.content.decode("utf-8-sig")` (or equivalent) and assert the body starts with `\ufeff` in raw bytes (`response.content[:3] == b"\xef\xbb\xbf"`).
  - New test `test_detections_export_is_single_line_and_reads_back`: seed a detect run whose `commit_trailer` evidence snippet contains `"first\n\nsecond"`; download `?format=detections`; assert (a) `csv.DictReader` over the decoded body parses `len(rows) == DB count`, (b) every row's `snippet` contains the literal two-character `\n` and no real newline, (c) the number of physical lines in the body equals records + 1, (d) each record has exactly `len(EVIDENCE_CSV_HEADER)` fields.
  - Same single-line guarantee for `?format=csv` (repo export) via one assertion in an existing repo-export test or the same new test.
- Golden: regenerate `tests/golden` (the `runs_detect_export` snapshot body now starts with `\ufeff`).

**Validation beyond tests (must appear in the report)**

- Read back the REAL export for run 99 from the database using a throwaway script (like `.venv\Scripts\python.exe - <<script>>` style, or a temp file under `C:\Users\Abdul\AppData\Local\Temp\opencode\`): stream `_detections_chunks(engine, 99)`, accumulate the first ~300KB, then (a) `csv.reader` parses every record with exactly 25 fields, (b) physical line count == records + 1 in the sample, (c) body decodes as UTF-8, (d) a snippet containing Chinese text round-trips into real Unicode characters (not mojibake). Report the observed numbers.

**Constraints for this task**

- `evidence_json` content must not change (json.dumps already escapes newlines; `_single_line` must not alter it).
- Row counts and column order must not change; only encoding/escaping changes.
- The bounded-batch test `test_detections_export_streams_bounded_batches` must still pass (adjust its first-chunk assertion to decode with `utf-8-sig`).

## Task 2: Two export groups (Evidence / Repos), each CSV or JSON, with info popovers

**Why:** four buttons are confusing; the user wants exactly two export actions, each offering CSV or JSON, each clearly described via an 'i' info card. Also add an evidence JSON format (evidence CSV's JSON twin) — it is the only way to get all 3.8M evidence rows into a tool that ignores Excel's row cap.

**Backend (`src/serve/runs.py`, `src/serve/app.py`)**

1. New format key `detections-json` → `_MEDIA_TYPES` value `application/json`; add to the format validation tuples in BOTH export routes (`/runs/{run_id}/export` and `/vsearch/runs/{filter_hash}/export` keeps `json`/`csv` only — do not extend vsearch).
2. New `_detections_json_chunks(engine, run_id, *, batch_rows=EVIDENCE_BATCH_ROWS)` streamed generator, bounded per partition: yields `[` then per partition the comma-joined JSON objects, then `]`; each object:
   `{"run_id": …, "repo_id": …, "full_name": …, "agent": …, "channel": …, "pack_version": …, "detected_at": ISO-Z or null, "evidence": {…raw dict…}}`.
   Human-friendly: `ensure_ascii=False`. Never buffer all rows. Empty run yields `[]`.
3. `export_bundle`: for detect runs, `format == "detections-json"` returns the new chunks. `export_run`: filename map gains `"detections-json": f"gitcorpus-detect-{run_id}-evidence.json"`; `regenerated` stays true for all detect formats; 409 behavior unchanged.
4. `src/serve/app.py` route validation tuple becomes `("json", "csv", "detections", "detections-json")` with the hint string updated.

**Template (`src/serve/templates/detect_detail.html`)**

Replace the three-button `.form-actions` block (only rendered when `not run.polling`) with two GET forms; keep the `run.polling` branch exactly as is ("Exports unlock when the run finishes."):

- Evidence group: `<form method="get" action="/runs/{{ run.id }}/export" class="export-group">` containing a `<select class="field-input" name="format" id="detection-export-evidence-format">` with options `detections` (label: `CSV — one row per evidence item`) and `detections-json` (label: `JSON — one object per evidence item`), a submit button `id="detection-export-evidence"` labelled `Export evidence`, and an `i` popover using the existing `details.info-pop` pattern describing: every stored evidence row for the run with agent, channel, commit/path/PR details and the raw evidence JSON; CSV is a flat table for spreadsheets, JSON preserves the nested objects; regenerated live from the database (nothing is capped by Excel's row limit).
- Repos group: same shape, action `/runs/{{ run.id }}/export`, `id="detection-export-run-format"`, options `csv` (label: `CSV — one row per scanned repo`) and `json` (label: `JSON — repos with detection rollup`), submit button `id="detection-export-run"` labelled `Export repos`, popover describing: one row/item per repo scanned, corpus fields plus detection rollup (agents, adoption level, commit ratio, per-channel evidence counts); use it to join detection results back onto the search corpus.
- Keep ids stable for tests; no JavaScript. The form must be usable without JS (native GET submit).

**Tests (write first, watch fail)**

- `tests/contract/test_detect_pages.py`:
  - `test_detect_export_forms_offer_csv_and_json`: page contains both forms, both selects with the four option values, both button labels, and each popover's descriptive sentence (assert on stable substrings you put in the template).
  - `test_detect_export_evidence_json_streams_all_rows`: seed a small detect run (reuse `seed_detect_run_with_evidence`); GET `?format=detections-json` → 200, `content-type` starts with `application/json`, `x-gitcorpus-regenerated == "true"`, filename `gitcorpus-detect-{id}-evidence.json`; `json.loads(response.text)` is a list with `len == DB evidence count` and the first object has exactly the keys `{run_id, repo_id, full_name, agent, channel, pack_version, detected_at, evidence}`; `evidence` equals the seeded dict.
  - `test_detect_export_refuses_while_run_is_unfinished` gains `detections-json` to its format loop.
- Golden: regenerate (detail page markup changed).

**Constraints for this task**

- Bounded memory: JSON chunking uses the same `partitions(batch_rows)` pattern as the CSV (default `EVIDENCE_BATCH_ROWS`); no `.all()`.
- Keep `X-Gitcorpus-Regenerated` semantics and 409 behavior for the new format.
- Do not touch find-run exports or the vsearch route's accepted formats.

## Task 3: Time elapsed on detection detail and history list

**Why:** the detection detail page and the `/detections` history table do not show how long a run took; run #99 took 7h 14m.

**Changes**

1. `src/serve/templates/detect_detail.html`: inside `#run-header`, directly after `{% include "partials/detect_status.html" %}`, add `<p class="muted" id="run-elapsed">Time elapsed: {{ run.elapsed if run.elapsed else "—" }}</p>`. `run.elapsed` already exists in `_run_detail_summary` (format like `7h 13m`, `43m 12s`, `12s`, `—` when not started; for a running run it is the elapsed-so-far at render time — that is fine).
2. `src/serve/detect.py` `detections_page` list building: add `"duration": _format_span(_elapsed_seconds(row)) or "—"` to each detection dict (import `_elapsed_seconds`, `_format_span` from `serve.pages`; `row` mappings have `started_at`/`finished_at`).
3. `src/serve/templates/detect_list.html`: add a `Time elapsed` column header after `Started` and a `<td id="detection-{item.id}-elapsed">{{ item.duration }}</td>` cell (keep the table column count consistent with the thead).

**Tests (write first, watch fail)**

- `tests/contract/test_detect_pages.py` (or the existing detect-list contract file if one fits better — check where `/detections` list assertions live, e.g. `test_detections_use_their_own_numbering`; put list tests beside them):
  - Detail: seed a detect run with `started_at`/`finished_at` two hours apart; GET `/detections/{id}` → body contains `id="run-elapsed"` and `Time elapsed: 2h 0m`.
  - List: GET `/detections` → header `Time elapsed` present and the seeded run's row shows the formatted duration (e.g. `2h 0m`); a queued run (no `started_at`) shows `—`.
- Golden: regenerate (both pages changed).

**Constraints for this task**

- Reuse `_format_span`/`_elapsed_seconds` — do not invent a second duration formatter.
- Do not alter the existing `Duration` field inside the "Technical details" block on the detail page (it stays).

## Task 4: Docs for the three changes

**Changes**

- `README.md`: in the "Coding-agent detection shipped" paragraph, replace the export sentence with the new reality: two export actions (evidence / repos), each CSV or JSON; evidence CSV is flat, one row per evidence item, Excel-friendly (UTF-8 BOM, one record per line); evidence JSON mirrors it; repo CSV/JSON carry the detection rollup; exports unlock when a run finishes. Mention the detection detail page and history list show the run's elapsed time.
- `docs/development-log.md`: append a dated entry `## Detection evidence exports and elapsed time (2026-10-18)` in the established format: scope line, "What shipped" bullets (Excel-safe single-line CSVs with BOM + read-back validation; `detections-json` format; two export groups with info popovers; elapsed time on detail + list), tests added, verification line (use the real final counts from Task 1-3 reports: full suite count, golden count, ruff/black clean, the run-99 read-back numbers from Task 1's report).
- `docs/superpowers/specs/2026-10-02-agent-detection-design.md`: extend the "Revision 2026-10-18" subsection with one bullet: exports are Excel-safe (BOM, one record per line, newlines escaped as `\n`) and offered as two groups (evidence/repos, CSV or JSON; `detections-json` moved evidence JSON); elapsed time shown on the detection page and history list.

**Constraints for this task**

- Do not claim numbers you did not read from the task reports; copy them verbatim.
- Markdown only; no code changes; run `black --check` is not needed but do not touch Python files.
