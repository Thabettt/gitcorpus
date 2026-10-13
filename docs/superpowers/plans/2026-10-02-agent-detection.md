# Agent-Use Detection (v1, API-only) Implementation Plan — Revised 2026-10-14

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `detect` run kind that scans a frozen find-run corpus through GitHub APIs only, detects coding-agent use across the papers' eight channels with per-agent selection, stores per-repo/per-agent/per-channel evidence, and exposes options, list, and detail pages in the console.

**Architecture:** Detection is a first-class run kind: `runs.kind='detect'` with `source_run_id`, candidates read from the source run's frozen `run_items`, a new `src/detect/` package does pack management + channel detection + orchestration, and results persist in a new `detection_evidence` table plus a per-repo `run_items.detection` rollup and `runs.result_summary`. It reuses the existing executor (progress, cancel, resume), transport, limiter, audit telemetry, run history, exports, and bundle machinery.

**Tech Stack:** Python 3.12, FastAPI + Jinja2 + htmx, SQLAlchemy 2 + Alembic (Postgres), Redis bucket limiter, httpx, pytest, ruff, black.

**Spec:** `docs/superpowers/specs/2026-10-02-agent-detection-design.md` (revised 2026-10-14; §14 is the Robbes coverage map)

## Global Constraints

- Python `>=3.12`; line length 100; ruff (`E,F,I,UP,B`) + black clean; coverage floor `fail_under = 93` (`pyproject.toml`).
- DB tests require `TEST_DATABASE_URL` ending in `_test` (or `GITCORPUS_REQUIRE_TEST_DB=1`); use the central `clean_db` fixture from `tests/conftest.py` — **never** add a local `TRUNCATE` fixture (`tests/unit/test_fixture_centralization.py` fails otherwise).
- Detection runs MUST NOT call discovery/search endpoints: REST `/search/repositories`, `/search/code`, `/repositories?since=`, org/repo enumeration, or GraphQL `search(...)` count/page bodies; enforced by test.
- Candidates come from the source run's `run_items`; top-N order is `stargazers DESC NULLS LAST, repo_id ASC`.
- Channels (exact names, in this order): `file, author, branch, label, bot, commit_trailer, pr_metadata, issue`.
- Depth windows (v1): commits `first:100`, PRs `first:100`, issues `first:100`; all recorded in the run spec and shown in the UI.
- Agent selection scopes matching: only selected agents are matched, stored, counted, or exported. `agents: null` means all; `generic` (AGENTS.md / `ai-generated` label) is a first-class selectable pseudo-agent.
- No commit-author/committer emails in the database, bundles, exports, or audit rows. Author-channel matching reads emails in memory only; persisted evidence carries `{login, commit, field, pattern}`; commit-trailer snippets redact emails to `<email>`.
- No raw tokens in logs/bundles; limiter keys use `deps.token_fp` (`token_fingerprint`). GraphQL/API calls go through `lib.gh_client.request_with_retry` with `limiter=deps.limiter`, `token_id=deps.token_fp`, and an `on_response` audit hook.
- Migration: claim the next free revision at execution time — `0016` with `down_revision="0015"` today (`0015_adaptive_settings_toggle` is head); if head has moved, renumber and use the new head as `down_revision`.
- Run statuses: `queued|running|done|failed|partial|cancelled`. Never present partial data as complete.
- Keep the integration-contract names that `src/serve/app.py` already references: `detect.orchestrator.run_detection(deps, run_id, spec, pack, *, config=None)`, `detect.packs.load_frozen(engine, version)`, `serve.detect_spec.parse_detect_spec(doc)`.
- Every new GET route must be added to `tests/golden/conftest.py::PATH_PARAMS` (or `EXTRA_CASES`); snapshots regenerate with `UPDATE_GOLDEN=1`; the OpenAPI pin is re-pinned manually from the failing test's printed hash.
- All commits: conventional prefixes matching repo style (`feat:`, `test:`, `docs:`, `migration:`, `fix:`).
- Run tests with: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest <path> -q` (Windows PowerShell).

**Preflight (once, before Task 1):** `git status --porcelain` must be clean. The working tree previously carried uncommitted console/metrics changes plus regenerated golden snapshots; if they are still uncommitted, commit them first — every golden step below assumes a clean base.

## Source references (for revision)

Consult these before changing any heuristic; the spec's §14 coverage map is the authoritative mapping of paper signal → plan location.

- **Spec** (design + §14 coverage map): `docs/superpowers/specs/2026-10-02-agent-detection-design.md`.
- **Papers** (local copies, in `01-adoption-measurement/`):
  - `Robbes-2026-Heuristics-Companion-2601.18345.pdf` (arXiv:2601.18345) — the heuristic taxonomy (files/commits/PRs/issues/users), matching semantics, perils, community repo.
  - `Robbes-2026-Agentic-Much-2601.18341.pdf` (arXiv:2601.18341) — methodology and pipeline rules (`.gitignore` scan, PR→commit propagation, bot/noise exclusion), adoption baselines, FP rates.
  - `Robbes-2026-Agentic-Very-Much-2606.07448.pdf` (arXiv:2606.07448) — newer-project companion; same heuristics.
  - Folder: `C:\Users\Abdul\OneDrive\Documents\Projects\thisisjustthebeginning\looked-up papers\01-adoption-measurement\`.
- **Extracted text** (for agents that cannot read PDFs): `pip install pypdf`, then run `C:\Users\Abdul\AppData\Local\Temp\opencode\extract_pdfs.py` (writes `…\Temp\opencode\robbes\*.txt`), or extract from the PDFs directly.
- **Replication package** (pattern source of truth): `https://github.com/labri-progress/agent-impact` — `config/patterns/{authors,files,branches,labels,bots,tools}.csv` and `code/heuristics.py` (Task 2 vendors the CSVs into `packs/patterns/`).
- **Community heuristics repository**: the companion's shared heuristics repo (per-heuristic validity periods, sample trace datasets). If it publishes updated patterns, build and freeze a new pack version — never edit a frozen pack.
- If you revise a heuristic: update the vendored CSVs (or add a new pack version), the attribution tests (Task 3), and keep `docs/detection-tiers.md` and spec §14 in sync.

## File Structure

**Create**

- `migrations/versions/0016_detect_runs.py` — trace_packs, runs kind/source/summary, run_items.detection, detection_evidence.
- `src/detect/__init__.py`
- `src/detect/packs.py` — CSV→pack build, validate, freeze (DB), load.
- `src/detect/attribution.py` — pattern→agent matching, selection scoping, PR→commit propagation, noise filter, adoption levels.
- `src/detect/channels.py` — per-channel API detectors (file, history, PR, issue).
- `src/detect/estimate.py` — call/time estimates from live settings.
- `src/detect/orchestrator.py` — candidates, channel execution, evidence + rollup + summary, evidence CSV.
- `src/serve/detect_spec.py` — detect-spec validation (mirrors `filter_spec.py`).
- `src/serve/detect.py` — routes + detect page rendering.
- `src/serve/templates/detect_list.html`, `detect_options.html`, `detect_detail.html`
- `src/serve/templates/partials/detect_status.html`, `partials/detect_estimate.html`
- `docs/detection-tiers.md`
- Tests: `tests/unit/test_detect_packs.py`, `test_detect_attribution.py`, `test_detect_channels.py`, `test_detect_estimate.py`, `test_detect_orchestrator.py`, `tests/contract/test_detect_routes.py`, `test_detect_pages.py`

**Modify**

- `src/store/models.py` — `Runs` (+kind, source_run_id, result_summary), `RunItem` (+detection), new `TracePack`, `DetectionEvidence`.
- `src/serve/executor.py` — `RunPayloadItem.detection`, `RunPayload.result_summary`/`detections`, `create_run(kind=..., source_run_id=...)`, `execute_run` writes `result_summary`, `_write_bundle` writes `detections.csv`.
- `src/serve/runs.py` — `_BUNDLE_FILES` + `detections` format with regeneration from the evidence table.
- `src/serve/app.py` — `create_app(detect_runner_factory=...)`, `register_detect`, live detect-resume branch.
- `src/serve/pages.py` — run page branches to the detect detail renderer for `kind='detect'`.
- `src/serve/corpora.py` — corpora list/detail carry the latest detect run.
- `src/serve/templates/base.html`, `run_detail.html`, `corpora.html`, `corpus_detail.html` — Detections nav + wired buttons.
- `tests/conftest.py` — `FULL_TRUNCATE_TABLES` gains `detection_evidence`, `trace_packs`.
- `tests/integration/test_models_console.py`, `test_models_migrations.py` — schema contracts.
- `tests/contract/test_run_detail.py`, `test_corpora.py`, `test_resume.py` — wired-button + detect-resume assertions.
- `tests/golden/conftest.py` + snapshots + `openapi.sha256` — new routes.
- `design/research.md` — D13 pointer to `docs/detection-tiers.md`.
- `README.md`, `docs/development-log.md` — status updates.

---

## Task 1: Migration 0016, models, and schema contracts

**Files:**
- Create: `migrations/versions/0016_detect_runs.py`
- Modify: `src/store/models.py` (class `Runs` at ~:158, `RunItem` at ~:193; append `TracePack`, `DetectionEvidence` after `Corpus`)
- Modify: `tests/conftest.py` (`FULL_TRUNCATE_TABLES` at ~:105)
- Modify: `tests/integration/test_models_console.py` (`ALL_TABLES` :15, `RUN_COLUMNS` :29, `RUN_ITEM_COLUMNS` :54, head :111)
- Modify: `tests/integration/test_models_migrations.py` (`TABLES` :14, `EXPECTED_COLUMNS` :28)
- Test: the two integration test files.

**Interfaces:**
- Consumes: current head `0015`.
- Produces: tables `trace_packs`, `detection_evidence`; columns `runs.kind` (default `'find'`, check `IN ('find','detect')`), `runs.source_run_id` (FK runs.id), `runs.result_summary`; `run_items.detection`; ORM models `TracePack`, `DetectionEvidence` and updated `Runs`/`RunItem` — used by every later task.

- [ ] **Step 1: Write the failing schema tests**

In `tests/integration/test_models_console.py`, extend the contracts:

```python
ALL_TABLES = {
    "repos",
    "owners",
    "full_name_history",
    "geo_cache",
    "shards",
    "audit_log",
    "runs",
    "run_items",
    "saved_filters",
    "app_settings",
    "corpora",
    "trace_packs",
    "detection_evidence",
}
```

Add to `RUN_COLUMNS`: `"kind": False, "source_run_id": True, "result_summary": True`. Add to `RUN_ITEM_COLUMNS`: `"detection": True`. Change the head assertion:

```python
def test_single_alembic_head(alembic_config):
    assert ScriptDirectory.from_config(alembic_config).get_heads() == ["0016"]
```

In `tests/integration/test_models_migrations.py`, add `"trace_packs"` and `"detection_evidence"` to `TABLES`, add to `EXPECTED_COLUMNS`:

```python
    "trace_packs": {
        "version": False,
        "authors": False,
        "files": False,
        "branches": False,
        "labels": False,
        "bots": False,
        "generic_weights": False,
        "exclusions": False,
        "frozen_at": False,
    },
    "detection_evidence": {
        "id": False,
        "run_id": False,
        "repo_id": False,
        "agent": False,
        "channel": False,
        "evidence": False,
        "pack_version": False,
        "detected_at": False,
    },
```

and append a round-trip test:

```python
def test_detect_rows_round_trip(migrated: Engine):
    with migrated.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('rt-1', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)"
            )
        )
        source_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version)"
                " VALUES ('rt-find', '{}'::jsonb, '2022-11-28') RETURNING id"
            )
        ).scalar_one()
        detect_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, kind, source_run_id)"
                " VALUES ('rt-detect', '{}'::jsonb, '2022-11-28', 'detect', :src) RETURNING id"
            ),
            {"src": source_id},
        ).scalar_one()
        connection.execute(
            text("INSERT INTO owners (id, login, type) VALUES (901, 'octo', 'User')")
        )
        connection.execute(
            text(
                "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility)"
                " VALUES (901, 'rt-n1', 'octo/rt', 901, 'rt', 'public')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO detection_evidence"
                " (run_id, repo_id, agent, channel, evidence, pack_version)"
                " VALUES (:run, 901, 'claude', 'file', '{\"path\": \"CLAUDE.md\"}'::jsonb, 'rt-1')"
            ),
            {"run": detect_id},
        )
    assert detect_id != source_id
    with pytest.raises(IntegrityError):
        with migrated.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO detection_evidence"
                    " (run_id, repo_id, agent, channel, evidence, pack_version)"
                    " VALUES (:run, 901, 'claude', 'nope', '{}'::jsonb, 'rt-1')"
                ),
                {"run": detect_id},
            )
```

In `tests/conftest.py`:

```python
FULL_TRUNCATE_TABLES = (
    "detection_evidence",
    "trace_packs",
    "app_settings",
    "corpora",
    "run_items",
    "runs",
    "saved_filters",
    "audit_log",
    "shards",
    "geo_cache",
    "owners",
    "repos",
    "full_name_history",
)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/integration/test_models_console.py tests/integration/test_models_migrations.py -q`
Expected: FAIL (`0016` head missing; `trace_packs`/`detection_evidence` not in metadata; columns missing).

- [ ] **Step 3: Write the migration**

Create `migrations/versions/0016_detect_runs.py`:

```python
"""detect runs: trace packs + detection evidence

Revision ID: 0016
Revises: 0015
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

CHANNELS = "'file','author','branch','label','bot','commit_trailer','pr_metadata','issue'"


def upgrade() -> None:
    op.create_table(
        "trace_packs",
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("authors", postgresql.JSONB(), nullable=False),
        sa.Column("files", postgresql.JSONB(), nullable=False),
        sa.Column("branches", postgresql.JSONB(), nullable=False),
        sa.Column("labels", postgresql.JSONB(), nullable=False),
        sa.Column(
            "bots", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "generic_weights",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "exclusions",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[\"CONVENTIONS.md\"]'::jsonb"),
        ),
        sa.Column(
            "frozen_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("version"),
    )
    op.add_column(
        "runs",
        sa.Column("kind", sa.Text(), nullable=False, server_default=sa.text("'find'")),
    )
    op.create_check_constraint("runs_kind_check", "runs", "kind IN ('find','detect')")
    op.add_column(
        "runs",
        sa.Column("source_run_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key("runs_source_run_id_fkey", "runs", "runs", ["source_run_id"], ["id"])
    op.add_column("runs", sa.Column("result_summary", postgresql.JSONB(), nullable=True))
    op.create_index("runs_kind_idx", "runs", ["kind", sa.text("created_at DESC")])
    op.create_index(
        "runs_source_idx",
        "runs",
        ["source_run_id"],
        postgresql_where=sa.text("source_run_id IS NOT NULL"),
    )
    op.add_column("run_items", sa.Column("detection", postgresql.JSONB(), nullable=True))
    op.create_table(
        "detection_evidence",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("repo_id", sa.BigInteger(), nullable=False),
        sa.Column("agent", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("evidence", postgresql.JSONB(), nullable=False),
        sa.Column("pack_version", sa.Text(), nullable=False),
        sa.Column(
            "detected_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(f"channel IN ({CHANNELS})", name="detection_evidence_channel_check"),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["repo_id"], ["repos.id"]),
        sa.ForeignKeyConstraint(["pack_version"], ["trace_packs.version"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("de_run_repo_idx", "detection_evidence", ["run_id", "repo_id"])
    op.create_index("de_run_agent_idx", "detection_evidence", ["run_id", "agent"])
    op.create_index("de_run_channel_idx", "detection_evidence", ["run_id", "channel"])
    op.create_index("de_repo_idx", "detection_evidence", ["repo_id"])


def downgrade() -> None:
    op.drop_index("de_repo_idx", table_name="detection_evidence")
    op.drop_index("de_run_channel_idx", table_name="detection_evidence")
    op.drop_index("de_run_agent_idx", table_name="detection_evidence")
    op.drop_index("de_run_repo_idx", table_name="detection_evidence")
    op.drop_table("detection_evidence")
    op.drop_column("run_items", "detection")
    op.drop_index("runs_source_idx", table_name="runs")
    op.drop_index("runs_kind_idx", table_name="runs")
    op.drop_column("runs", "result_summary")
    op.drop_constraint("runs_source_run_id_fkey", "runs", type_="foreignkey")
    op.drop_column("runs", "source_run_id")
    op.drop_constraint("runs_kind_check", "runs", type_="check")
    op.drop_column("runs", "kind")
    op.drop_table("trace_packs")
```

- [ ] **Step 4: Update the ORM models**

In `src/store/models.py`, extend `Runs.__table_args__` with:

```python
        CheckConstraint("kind IN ('find','detect')", name="runs_kind_check"),
        Index("runs_kind_idx", "kind", text("created_at DESC")),
        Index("runs_source_idx", "source_run_id", postgresql_where=text("source_run_id IS NOT NULL")),
```

(import `CheckConstraint` from `sqlalchemy` if not already imported; `postgresql_where` works on the model `Index`.) Add after `filter_spec`:

```python
    kind: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'find'"))
    source_run_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("runs.id"))
```

and after `bundle_dir`:

```python
    result_summary: Mapped[dict | None] = mapped_column(JSONB)
```

Add to `RunItem` after `virtuals`:

```python
    detection: Mapped[dict | None] = mapped_column(JSONB)
```

Append after `Corpus`:

```python
class TracePack(Base):
    __tablename__ = "trace_packs"

    version: Mapped[str] = mapped_column(Text, primary_key=True)
    authors: Mapped[list] = mapped_column(JSONB, nullable=False)
    files: Mapped[list] = mapped_column(JSONB, nullable=False)
    branches: Mapped[list] = mapped_column(JSONB, nullable=False)
    labels: Mapped[list] = mapped_column(JSONB, nullable=False)
    bots: Mapped[list] = mapped_column(JSONB, nullable=False, server_default=text("'[]'"))
    generic_weights: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'"))
    exclusions: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[\"CONVENTIONS.md\"]'")
    )
    frozen_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )


class DetectionEvidence(Base):
    __tablename__ = "detection_evidence"
    __table_args__ = (
        CheckConstraint(
            "channel IN ('file','author','branch','label','bot','commit_trailer',"
            "'pr_metadata','issue')",
            name="detection_evidence_channel_check",
        ),
        Index("de_run_repo_idx", "run_id", "repo_id"),
        Index("de_run_agent_idx", "run_id", "agent"),
        Index("de_run_channel_idx", "run_id", "channel"),
        Index("de_repo_idx", "repo_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False
    )
    repo_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("repos.id"), nullable=False)
    agent: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONB, nullable=False)
    pack_version: Mapped[str] = mapped_column(
        Text, ForeignKey("trace_packs.version"), nullable=False
    )
    detected_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/integration/test_models_console.py tests/integration/test_models_migrations.py -q`
Expected: PASS. If the metadata-index contract test flags `runs_source_idx`, align the model `Index` expression with the migration (`postgresql_where`).

- [ ] **Step 6: Commit**

```bash
git add migrations/versions/0016_detect_runs.py src/store/models.py tests/conftest.py tests/integration/test_models_console.py tests/integration/test_models_migrations.py
git commit -m "migration: add detect runs, trace packs, and detection evidence"
```

---

## Task 2: Pack build / validate / freeze / load

**Files:**
- Create: `src/detect/__init__.py`, `src/detect/packs.py`, `packs/patterns/` (vendored CSVs)
- Test: `tests/unit/test_detect_packs.py`

**Interfaces:**
- Consumes: `store.models.TracePack`, the central `clean_db` fixture.
- Produces (used by Tasks 3, 8, 9, 10):
  - `@dataclass(frozen=True) class Pattern: pattern: str; agent: str`
  - `@dataclass(frozen=True) class Pack: version; agents; authors/files/branches/labels/bots: tuple[Pattern, ...]; generic_weights; exclusions`
  - `build_pack_from_dir(src: Path, *, version: str) -> Pack` (adds the `Generic` pseudo-agent)
  - `pack_to_document(pack) -> dict`, `pack_from_document(doc) -> Pack`, `pack_digest(pack) -> str`
  - `write_pack_file(pack, path) -> str`, `load_pack_file(path) -> Pack`
  - `freeze_pack(engine, pack) -> None` (immutable; raises `PackConflict` on differing content)
  - `load_frozen(engine, version) -> Pack`
  - `main(argv=None) -> int` for `python -m detect.packs build|freeze`

- [ ] **Step 1: Fetch and vendor the real pattern CSVs (once)**

From the public replication package `labri-progress/agent-impact`:

```powershell
New-Item -ItemType Directory -Force -Path packs\patterns | Out-Null
$base = "https://raw.githubusercontent.com/labri-progress/agent-impact/main/config/patterns"
foreach ($name in "authors","files","branches","labels","bots","tools") {
  curl.exe -fsSL "$base/$name.csv" -o "packs\patterns\$name.csv"
}
```

Verified schema (2026-10-02): pattern files are `pattern,type,subtype` (`subtype` is the tool label; `type` is informational: `AI`, `AI_FILE`, `AI-PR`, `Bot`); `tools.csv` is `name,url`. Ignore `counts.csv`, `rg_patterns.csv`, `top-orgs.csv`. Matching semantics (from the replication package's `code/heuristics.py`, do not invent): every pattern is a Python regex, case-sensitive, `finditer`; patterns sharing a `subtype` become one named group per channel; file patterns get bare dots escaped and a `(?:^|/)` anchor. `bots.csv` is **generic CI bots to exclude**, not agent detection. Background: Heuristics Companion §4 and “Agentic Much?” §4.1 (see Source references above).

- [ ] **Step 2: Write the failing tests**

Create `tests/unit/test_detect_packs.py`:

```python
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from detect.packs import (
    PackConflict,
    build_pack_from_dir,
    freeze_pack,
    load_frozen,
    pack_from_document,
    pack_to_document,
)


def write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


def make_src(tmp_path: Path) -> Path:
    src = tmp_path / "patterns"
    src.mkdir()
    write_csv(src / "tools.csv", "name,url", ["Claude Code,https://claude.com", "Cursor,https://cursor.com"])
    write_csv(src / "authors.csv", "pattern,type,subtype", ["noreply@anthropic.com,AI,Claude Code"])
    write_csv(src / "files.csv", "pattern,type,subtype", ["CLAUDE.md,AI_FILE,Claude Code", ".cursor/,AI_FILE,Cursor"])
    write_csv(src / "branches.csv", "pattern,type,subtype", ["claude/,AI-PR,Claude Code"])
    write_csv(src / "labels.csv", "pattern,type,subtype", ["ai-generated,AI-PR,Generic"])
    write_csv(src / "bots.csv", "pattern,type,subtype", [r"dependabot\[bot\],Bot,dependabot"])
    return src


def test_build_pack_from_dir_maps_all_channels(tmp_path):
    pack = build_pack_from_dir(make_src(tmp_path), version="2026-10-02-test")
    assert pack.version == "2026-10-02-test"
    assert pack.agents["Claude Code"] == "https://claude.com"
    assert pack.agents["Generic"] == "https://agents.md"  # pseudo-agent is always in the roster
    assert pack.files[0].pattern == "CLAUDE.md"
    assert pack.files[0].agent == "Claude Code"
    assert pack.bots[0].agent == "dependabot"
    assert pack.generic_weights == {"AGENTS.md": 0.3}
    assert pack.exclusions == frozenset({"CONVENTIONS.md"})


def test_document_roundtrip(tmp_path):
    pack = build_pack_from_dir(make_src(tmp_path), version="v1")
    assert pack_from_document(pack_to_document(pack)) == pack


def test_freeze_is_immutable(clean_db, tmp_path):
    engine = clean_db()
    pack = build_pack_from_dir(make_src(tmp_path), version="v1")
    freeze_pack(engine, pack)
    # trace_packs stores patterns only; the agents name->url map is not persisted
    assert load_frozen(engine, "v1") == replace(pack, agents={})
    with pytest.raises(PackConflict):
        freeze_pack(engine, replace(pack, generic_weights={"AGENTS.md": 0.1}))


def test_missing_channel_file_is_rejected(tmp_path):
    src = make_src(tmp_path)
    (src / "labels.csv").unlink()
    with pytest.raises(ValueError, match="labels.csv"):
        build_pack_from_dir(src, version="v1")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_packs.py -q`
Expected: FAIL (`ModuleNotFoundError: detect.packs`).

- [ ] **Step 4: Implement `src/detect/packs.py`**

Create `src/detect/__init__.py` (empty) and:

```python
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from store.models import TracePack

CHANNEL_FILES = ("authors.csv", "files.csv", "branches.csv", "labels.csv", "bots.csv")
DEFAULT_GENERIC_WEIGHTS = {"AGENTS.md": 0.3}
DEFAULT_EXCLUSIONS = ("CONVENTIONS.md",)
GENERIC_AGENT = "Generic"
GENERIC_AGENT_URL = "https://agents.md"


class PackConflict(ValueError):
    pass


@dataclass(frozen=True)
class Pattern:
    pattern: str
    agent: str


@dataclass(frozen=True)
class Pack:
    version: str
    agents: Mapping[str, str]
    authors: tuple[Pattern, ...]
    files: tuple[Pattern, ...]
    branches: tuple[Pattern, ...]
    labels: tuple[Pattern, ...]
    bots: tuple[Pattern, ...]
    generic_weights: Mapping[str, float] = None  # type: ignore[assignment]
    exclusions: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "generic_weights", dict(self.generic_weights or DEFAULT_GENERIC_WEIGHTS)
        )
        object.__setattr__(self, "exclusions", frozenset(self.exclusions or DEFAULT_EXCLUSIONS))

    def roster(self) -> tuple[str, ...]:
        names = {pattern.agent for pattern in (*self.authors, *self.files, *self.branches, *self.labels)}
        names.add(GENERIC_AGENT)
        return tuple(sorted(names))


def _read_patterns(path: Path) -> tuple[Pattern, ...]:
    if not path.exists():
        raise ValueError(f"missing pattern file: {path.name}")
    patterns: list[Pattern] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            pattern = (row.get("pattern") or "").strip()
            agent = (row.get("subtype") or "").strip()
            if not pattern or not agent:
                continue
            patterns.append(Pattern(pattern=pattern, agent=agent))
    return tuple(patterns)


def build_pack_from_dir(src: Path, *, version: str) -> Pack:
    src = Path(src)
    tools_path = src / "tools.csv"
    if not tools_path.exists():
        raise ValueError("missing pattern file: tools.csv")
    agents: dict[str, str] = {}
    with tools_path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = (row.get("name") or "").strip()
            url = (row.get("url") or "").strip()
            if name:
                agents[name] = url
    agents.setdefault(GENERIC_AGENT, GENERIC_AGENT_URL)
    channels = {name: _read_patterns(src / name) for name in CHANNEL_FILES}
    return Pack(
        version=version,
        agents=agents,
        authors=channels["authors.csv"],
        files=channels["files.csv"],
        branches=channels["branches.csv"],
        labels=channels["labels.csv"],
        bots=channels["bots.csv"],
    )


def pack_to_document(pack: Pack) -> dict:
    def patterns(items: Sequence[Pattern]) -> list[dict]:
        return [{"pattern": p.pattern, "agent": p.agent} for p in items]

    return {
        "version": pack.version,
        "agents": dict(pack.agents),
        "authors": patterns(pack.authors),
        "files": patterns(pack.files),
        "branches": patterns(pack.branches),
        "labels": patterns(pack.labels),
        "bots": patterns(pack.bots),
        "generic_weights": dict(pack.generic_weights),
        "exclusions": sorted(pack.exclusions),
    }


def pack_from_document(doc: Mapping[str, object]) -> Pack:
    def patterns(key: str) -> tuple[Pattern, ...]:
        raw = doc.get(key) or []
        return tuple(
            Pattern(str(item["pattern"]), str(item["agent"]))
            for item in raw  # type: ignore[union-attr]
        )

    return Pack(
        version=str(doc["version"]),
        agents={str(k): str(v) for k, v in dict(doc.get("agents") or {}).items()},  # type: ignore[union-attr]
        authors=patterns("authors"),
        files=patterns("files"),
        branches=patterns("branches"),
        labels=patterns("labels"),
        bots=patterns("bots"),
        generic_weights={str(k): float(v) for k, v in dict(doc.get("generic_weights") or {}).items()},  # type: ignore[union-attr]
        exclusions=frozenset(str(x) for x in (doc.get("exclusions") or [])),  # type: ignore[union-attr]
    )


def pack_digest(pack: Pack) -> str:
    canonical = json.dumps(pack_to_document(pack), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def write_pack_file(pack: Pack, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pack_to_document(pack), indent=2), encoding="utf-8")
    return pack_digest(pack)


def load_pack_file(path: Path) -> Pack:
    return pack_from_document(json.loads(Path(path).read_text(encoding="utf-8")))


def _stored_pack(row: Mapping[str, object]) -> Pack:
    return pack_from_document(
        {
            "version": row["version"],
            "agents": {},  # agents are not persisted in trace_packs; version identity is content-based
            "authors": row["authors"],
            "files": row["files"],
            "branches": row["branches"],
            "labels": row["labels"],
            "bots": row["bots"],
            "generic_weights": row["generic_weights"],
            "exclusions": row["exclusions"],
        }
    )


def freeze_pack(engine: Engine, pack: Pack) -> None:
    doc = pack_to_document(pack)
    with engine.begin() as connection:
        existing = (
            connection.execute(select(TracePack).where(TracePack.version == pack.version))
            .mappings()
            .one_or_none()
        )
        if existing is not None:
            if _stored_pack(existing) != replace(pack, agents={}):
                raise PackConflict(
                    f"pack version {pack.version!r} already frozen with different content"
                )
            return
        connection.execute(
            insert(TracePack).values(
                version=pack.version,
                authors=doc["authors"],
                files=doc["files"],
                branches=doc["branches"],
                labels=doc["labels"],
                bots=doc["bots"],
                generic_weights=doc["generic_weights"],
                exclusions=doc["exclusions"],
            )
        )


def load_frozen(engine: Engine, version: str) -> Pack:
    with engine.connect() as connection:
        row = (
            connection.execute(select(TracePack).where(TracePack.version == version))
            .mappings()
            .one_or_none()
        )
    if row is None:
        raise KeyError(version)
    return _stored_pack(row)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m detect.packs")
    sub = parser.add_subparsers(dest="command", required=True)
    build = sub.add_parser("build")
    build.add_argument("--src", required=True)
    build.add_argument("--version", required=True)
    build.add_argument("--out", required=True)
    freeze = sub.add_parser("freeze")
    freeze.add_argument("--pack", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        pack = build_pack_from_dir(Path(args.src), version=args.version)
        digest = write_pack_file(pack, Path(args.out))
        print(f"wrote {args.out} sha256={digest[:12]}")
        return 0
    from sqlalchemy import create_engine

    engine = create_engine(os.environ["DATABASE_URL"])
    freeze_pack(engine, load_pack_file(Path(args.pack)))
    print("frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_packs.py -q`
Expected: PASS (4 tests).

- [ ] **Step 6: Build and freeze the first pack (once a DB is available)**

Run:
```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m detect.packs build --src packs\patterns --version 2026-10-14 --out packs\2026-10-14.json
$env:DATABASE_URL='<your database url>'; $env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m detect.packs freeze --pack packs\2026-10-14.json
```
Expected: `wrote … sha256=…`, then `frozen`.

- [ ] **Step 7: Commit**

```bash
git add src/detect/__init__.py src/detect/packs.py tests/unit/test_detect_packs.py packs/patterns packs/2026-10-14.json
git commit -m "feat: trace pack build, freeze, and load"
```

---

## Task 3: Attribution, selection scoping, propagation, noise, and redaction

**Files:**
- Create: `src/detect/attribution.py`
- Test: `tests/unit/test_detect_attribution.py`

**Interfaces:**
- Consumes: `detect.packs.Pack/Pattern`, `enrich.trees_first.FilePresence`.
- Produces (used by Tasks 4–6, 8):
  - `@dataclass(frozen=True) class Hit: agent: str; channel: str; evidence: dict`
  - `@dataclass(frozen=True) class ChannelRegex: regex: re.Pattern | None; names: Mapping[str, str]`
  - `build_channel_regex(patterns, *, is_files=False) -> ChannelRegex`
  - `matchers_for(pack, agents: frozenset[str] | None = None) -> dict[str, ChannelRegex]` (keys `file`, `author`, `branch`, `label`, `bot`; cache key includes the selection; `clear_matcher_cache()` for tests)
  - `match_files(pack, presence, agents=None) -> list[Hit]` (evidence `{path, source, generic?, weight?}`)
  - `match_author_identities(pack, entries, agents=None) -> list[Hit]` (entries: `{"login","name","email","commit"}`; evidence `{login, commit, field}` — **never** the raw value)
  - `match_bots(pack, entries, agents=None) -> list[Hit]` (same shape; QA evidence only)
  - `match_commit_messages(pack, messages, agents=None) -> list[Hit]` (messages: `(commit_oid, message)`; noise commits skipped; evidence `{commit, snippet}` with emails redacted)
  - `match_branches(pack, branches, agents=None)`, `match_labels(pack, labels, agents=None)` (evidence keeps the value)
  - `match_pr_metadata(pack, prs, agents=None) -> list[Hit]` (branch + label + Codex body marker)
  - `match_pr_authors(pack, prs, agents=None) -> list[Hit]` (PR author login vs author heuristics)
  - `match_issue_participants(pack, entries, agents=None) -> list[Hit]` (entries `{"login","number","role"}`)
  - `propagate_pr_commits(hits, prs) -> list[Hit]` — the papers' Codex mechanism
  - `is_noise_commit(message) -> bool`, `redact_emails(text) -> str`, `adoption_level(ratio) -> str`, `dedupe_hits(hits)`
  - `CODEX_PR_BODY_MARKER = "https://chatgpt.com/codex/tasks"`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_detect_attribution.py`:

```python
from __future__ import annotations

from detect.attribution import (
    CODEX_PR_BODY_MARKER,
    Hit,
    adoption_level,
    build_channel_regex,
    clear_matcher_cache,
    dedupe_hits,
    is_noise_commit,
    match_author_identities,
    match_branches,
    match_commit_messages,
    match_files,
    match_issue_participants,
    match_labels,
    match_pr_authors,
    match_pr_metadata,
    propagate_pr_commits,
    redact_emails,
)
from detect.packs import Pack, Pattern
from enrich.trees_first import FilePresence

PACK = Pack(
    version="v1",
    agents={"Claude Code": "https://claude.com", "Cursor": "https://cursor.com", "Generic": "https://agents.md"},
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"), Pattern("cursoragent", "Cursor")),
    files=(Pattern(r"CLAUDE\.md", "Claude Code"), Pattern(r"\.cursor/", "Cursor"), Pattern(r"AGENTS\.md", "Generic")),
    branches=(Pattern("claude/", "Claude Code"), Pattern("cursor/", "Cursor")),
    labels=(Pattern("ai-generated", "Claude Code"), Pattern("^amp$", "Amp")),
    bots=(Pattern(r"dependabot\[bot\]", "dependabot"),),
    generic_weights={"AGENTS.md": 0.3},
    exclusions=frozenset({"CONVENTIONS.md"}),
)


def presence(paths, *, source="tree"):
    return FilePresence(repo_full_name="o/r", paths=frozenset(paths), truncated=False, source=source)


def test_channel_regex_builds_named_groups_and_escapes_file_dots():
    channel = build_channel_regex(PACK.files, is_files=True)
    assert channel.regex is not None
    match = channel.regex.search(".cursor/rules/x.md")
    assert match is not None
    assert channel.names[match.lastgroup] == "Cursor"


def test_match_files_maps_regexes_and_weights():
    hits = match_files(
        PACK, presence(["CLAUDE.md", "AGENTS.md", "CONVENTIONS.md", ".cursor/rules/x.md", "claude.md"])
    )
    by_path = {h.evidence["path"]: h for h in hits}
    assert by_path["CLAUDE.md"].agent == "Claude Code"
    assert by_path[".cursor/rules/x.md"].agent == "Cursor"
    assert by_path["AGENTS.md"].agent == "Generic"
    assert by_path["AGENTS.md"].evidence["generic"] is True
    assert by_path["AGENTS.md"].evidence["weight"] == 0.3
    assert "CONVENTIONS.md" not in by_path
    assert "claude.md" not in by_path  # case-sensitive, like the replication package


def test_selection_scopes_matching():
    clear_matcher_cache()
    hits = match_files(PACK, presence(["CLAUDE.md", ".cursor/rules/x.md"]), agents=frozenset({"Cursor"}))
    assert [h.agent for h in hits] == ["Cursor"]
    authors = match_author_identities(
        PACK,
        [{"login": "jane", "name": "Jane", "email": "noreply@anthropic.com", "commit": "c1"}],
        agents=frozenset({"Cursor"}),
    )
    assert authors == []


def test_author_evidence_never_contains_the_identity_value():
    hits = match_author_identities(
        PACK,
        [{"login": "jane", "name": "Jane", "email": "noreply@anthropic.com", "commit": "c1"}],
    )
    assert [(h.agent, h.channel) for h in hits] == [("Claude Code", "author")]
    assert hits[0].evidence == {"login": "jane", "commit": "c1", "field": "email"}


def test_commit_messages_redact_emails_and_skip_noise():
    hits = match_commit_messages(
        PACK,
        [
            ("c1", "fix: x\n\nCo-authored-by: Cursor <cursoragent@x>"),
            ("c2", "Merge branch 'main' into dev"),
            ("c3", "chore: bump version to 1.2.3"),
        ],
    )
    assert [(h.agent, h.evidence["commit"]) for h in hits] == [("Cursor", "c1")]
    assert "cursoragent@x" not in str(hits[0].evidence)
    assert "<email>" in hits[0].evidence["snippet"]
    assert is_noise_commit("Revert \"feat: y\"")
    assert not is_noise_commit("feat: real work")


def test_branches_labels_and_pr_metadata():
    assert [h.agent for h in match_branches(PACK, ["claude/add-tests"])] == ["Claude Code"]
    assert [h.agent for h in match_labels(PACK, ["ai-generated", "example"])] == ["Claude Code"]
    prs = [
        {
            "number": 7,
            "headRefName": "cursor/fix",
            "labels": [],
            "body": f"task: {CODEX_PR_BODY_MARKER}",
            "author": "cursoragent",
            "commits": [
                {"oid": "a1", "author": "cursoragent"},
                {"oid": "a2", "author": "human"},
            ],
        }
    ]
    hits = match_pr_metadata(PACK, prs)
    assert {(h.agent, h.channel) for h in hits} == {("Cursor", "branch"), ("Codex", "pr_metadata")}
    assert all(h.evidence["pr"] == 7 for h in hits)
    author_hits = match_pr_authors(PACK, prs)
    assert [h.agent for h in author_hits] == ["Cursor"]


def test_propagate_pr_commits_tags_only_the_pr_authors_commits():
    prs = [
        {
            "number": 7,
            "headRefName": "cursor/fix",
            "labels": [],
            "body": "",
            "author": "cursoragent",
            "commits": [
                {"oid": "a1", "author": "cursoragent"},
                {"oid": "a2", "author": "human"},
            ],
        }
    ]
    hits = match_pr_metadata(PACK, prs)
    propagated = propagate_pr_commits(hits, prs)
    assert [(h.agent, h.evidence["commit"]) for h in propagated] == [("Cursor", "a1")]
    assert propagated[0].evidence["propagated"] is True


def test_issue_participants_and_levels():
    entries = [
        {"login": "cursoragent", "number": 12, "role": "assignee"},
        {"login": "jane", "number": 12, "role": "commenter"},
    ]
    hits = match_issue_participants(PACK, entries)
    assert [(h.agent, h.channel, h.evidence["role"]) for h in hits] == [
        ("Cursor", "issue", "assignee")
    ]
    assert adoption_level(0.004) == "experimental"
    assert adoption_level(0.03) == "limited"
    assert adoption_level(0.1) == "consistent"
    assert adoption_level(0.5) == "pervasive"
    assert adoption_level(0.0) == "experimental"
    assert adoption_level(None) == "none"
    assert redact_emails("a <b@c.dev>") == "a <email>"


def test_dedupe_collapses_identical_hits():
    hits = [Hit("Claude Code", "file", {"path": "CLAUDE.md"}), Hit("Claude Code", "file", {"path": "CLAUDE.md"})]
    assert dedupe_hits(hits) == [hits[0]]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_attribution.py -q`
Expected: FAIL (`ModuleNotFoundError: detect.attribution`).

- [ ] **Step 3: Implement `src/detect/attribution.py`**

```python
from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from detect.packs import Pack, Pattern
from enrich.trees_first import FilePresence

CODEX_PR_BODY_MARKER = "https://chatgpt.com/codex/tasks"

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_NOISE_PATTERNS = (
    re.compile(r"^Merge "),
    re.compile(r"^Revert "),
    re.compile(r"^chore(\(.+\))?: (bump|release|version)\b", re.IGNORECASE),
    re.compile(r"^v?\d+\.\d+\.\d+\s*$"),
    re.compile(r"\[skip ci\]", re.IGNORECASE),
)


@dataclass(frozen=True)
class Hit:
    agent: str
    channel: str
    evidence: dict


@dataclass(frozen=True)
class ChannelRegex:
    regex: re.Pattern[str] | None
    names: Mapping[str, str]


def redact_emails(text: str) -> str:
    return _EMAIL.sub("<email>", text)


def is_noise_commit(message: str) -> bool:
    first = (message or "").split("\n", 1)[0].strip()
    return any(pattern.search(first) for pattern in _NOISE_PATTERNS)


def adoption_level(ratio: float | None) -> str:
    if ratio is None:
        return "none"
    if ratio < 0.01:
        return "experimental"
    if ratio < 0.05:
        return "limited"
    if ratio < 0.20:
        return "consistent"
    return "pervasive"


def _sanitize(name: str) -> str:
    return re.sub(r"\W+", "_", name)


def _selected(patterns: Sequence[Pattern], agents: frozenset[str] | None) -> tuple[Pattern, ...]:
    if agents is None:
        return tuple(patterns)
    return tuple(pattern for pattern in patterns if pattern.agent in agents)


def build_channel_regex(patterns: Sequence[Pattern], *, is_files: bool = False) -> ChannelRegex:
    groups: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for pattern in patterns:
        name = _sanitize(pattern.agent)
        names.setdefault(name, pattern.agent)
        raw = pattern.pattern
        if is_files:
            if "." in raw and "\\." not in raw:
                raw = raw.replace(".", "\\.")
            if not raw.startswith("(?:^|/)") and not raw.startswith("^"):
                raw = "(?:^|/)" + raw
        groups.setdefault(name, []).append(raw)
    if not groups:
        return ChannelRegex(regex=None, names={})
    parts = [f"(?P<{name}>{'|'.join(pats)})" for name, pats in groups.items()]
    return ChannelRegex(regex=re.compile("|".join(parts)), names=names)


_MATCHER_CACHE: dict[str, dict[str, ChannelRegex]] = {}


def clear_matcher_cache() -> None:
    _MATCHER_CACHE.clear()


def _cache_key(pack: Pack, agents: frozenset[str] | None) -> str:
    suffix = "*" if agents is None else ",".join(sorted(agents))
    return f"{pack.version}|{suffix}"


def matchers_for(pack: Pack, agents: frozenset[str] | None = None) -> dict[str, ChannelRegex]:
    key = _cache_key(pack, agents)
    cached = _MATCHER_CACHE.get(key)
    if cached is None:
        cached = {
            "file": build_channel_regex(_selected(pack.files, agents), is_files=True),
            "author": build_channel_regex(_selected(pack.authors, agents)),
            "branch": build_channel_regex(_selected(pack.branches, agents)),
            "label": build_channel_regex(_selected(pack.labels, agents)),
            "bot": build_channel_regex(pack.bots),
        }
        _MATCHER_CACHE[key] = cached
    return cached


def _generic_weight(pack: Pack, path: str) -> float | None:
    for pattern in pack.files:
        if pattern.pattern in pack.generic_weights:
            escaped = pattern.pattern.replace(".", "\\.")
            if re.search(f"(?:^|/){escaped}", path):
                return pack.generic_weights[pattern.pattern]
    return None


def match_files(
    pack: Pack,
    presence: FilePresence,
    agents: frozenset[str] | None = None,
) -> list[Hit]:
    channel = matchers_for(pack, agents)["file"]
    if channel.regex is None:
        return []
    hits: list[Hit] = []
    for path in sorted(presence.paths):
        if path.rsplit("/", 1)[-1] in pack.exclusions or path in pack.exclusions:
            continue
        for match in channel.regex.finditer(path):
            if match.lastgroup is None:
                continue
            evidence: dict = {"path": path, "source": presence.source}
            weight = _generic_weight(pack, path)
            if weight is not None:
                evidence["generic"] = True
                evidence["weight"] = weight
            hits.append(Hit(channel.names[match.lastgroup], "file", evidence))
    return dedupe_hits(hits)


def _match_values(
    channel: ChannelRegex,
    values: Iterable[str],
    *,
    name: str,
    key: str,
) -> list[Hit]:
    if channel.regex is None:
        return []
    hits: list[Hit] = []
    for value in values:
        if not value:
            continue
        for match in channel.regex.finditer(value):
            if match.lastgroup is None:
                continue
            hits.append(
                Hit(
                    channel.names[match.lastgroup],
                    name,
                    {key: value[:300], "match": match.group()[:100]},
                )
            )
    return hits


def _match_identity_fields(
    channel: ChannelRegex,
    entries: Iterable[Mapping[str, object]],
    *,
    name: str,
) -> list[Hit]:
    if channel.regex is None:
        return []
    hits: list[Hit] = []
    for entry in entries:
        commit = str(entry.get("commit") or "")
        login = str(entry.get("login") or "")
        for field in ("login", "name", "email"):
            value = str(entry.get(field) or "")
            if not value:
                continue
            for match in channel.regex.finditer(value):
                if match.lastgroup is None:
                    continue
                hits.append(
                    Hit(
                        channel.names[match.lastgroup],
                        name,
                        {"login": login, "commit": commit, "field": field},
                    )
                )
    return hits


def match_author_identities(
    pack: Pack,
    entries: Iterable[Mapping[str, object]],
    agents: frozenset[str] | None = None,
) -> list[Hit]:
    channel = matchers_for(pack, agents)["author"]
    return dedupe_hits(_match_identity_fields(channel, entries, name="author"))


def match_bots(pack: Pack, entries: Iterable[Mapping[str, object]]) -> list[Hit]:
    channel = matchers_for(pack)["bot"]
    return dedupe_hits(_match_identity_fields(channel, entries, name="bot"))


def match_commit_messages(
    pack: Pack,
    messages: Iterable[tuple[str, str]],
    agents: frozenset[str] | None = None,
) -> list[Hit]:
    channel = matchers_for(pack, agents)["author"]
    if channel.regex is None:
        return []
    hits: list[Hit] = []
    for commit, message in messages:
        if not message or is_noise_commit(message):
            continue
        for match in channel.regex.finditer(message):
            if match.lastgroup is None:
                continue
            snippet = redact_emails(match.group()[:100])
            hits.append(
                Hit(channel.names[match.lastgroup], "commit_trailer", {"commit": commit, "snippet": snippet})
            )
    return dedupe_hits(hits)


def match_branches(pack: Pack, branches: Iterable[str], agents: frozenset[str] | None = None) -> list[Hit]:
    return _match_values(matchers_for(pack, agents)["branch"], branches, name="branch", key="branch")


def match_labels(pack: Pack, labels: Iterable[str], agents: frozenset[str] | None = None) -> list[Hit]:
    return _match_values(matchers_for(pack, agents)["label"], labels, name="label", key="label")


def match_pr_metadata(
    pack: Pack, prs: Iterable[Mapping[str, object]], agents: frozenset[str] | None = None
) -> list[Hit]:
    hits: list[Hit] = []
    for pr in prs:
        number = pr.get("number")
        head = str(pr.get("headRefName") or "")
        labels = [str(x) for x in pr.get("labels") or []]
        body = str(pr.get("body") or "")
        for hit in match_branches(pack, [head] if head else [], agents):
            hits.append(
                Hit(hit.agent, "branch", {"pr": number, "head": head, "match": hit.evidence["match"]})
            )
        for hit in match_labels(pack, labels, agents):
            hits.append(
                Hit(
                    hit.agent,
                    "label",
                    {"pr": number, "label": hit.evidence["label"], "match": hit.evidence["match"]},
                )
            )
        if body and CODEX_PR_BODY_MARKER in body and (agents is None or "Codex" in agents):
            hits.append(Hit("Codex", "pr_metadata", {"pr": number, "snippet": CODEX_PR_BODY_MARKER}))
    return dedupe_hits(hits)


def match_pr_authors(
    pack: Pack, prs: Iterable[Mapping[str, object]], agents: frozenset[str] | None = None
) -> list[Hit]:
    channel = matchers_for(pack, agents)["author"]
    hits: list[Hit] = []
    for pr in prs:
        login = str(pr.get("author") or "")
        if not login:
            continue
        for hit in _match_values(channel, [login], name="pr_metadata", key="author"):
            hits.append(Hit(hit.agent, "pr_metadata", {"pr": pr.get("number"), "author": login}))
    return dedupe_hits(hits)


def match_issue_participants(
    pack: Pack, entries: Iterable[Mapping[str, object]], agents: frozenset[str] | None = None
) -> list[Hit]:
    channel = matchers_for(pack, agents)["author"]
    hits: list[Hit] = []
    for entry in entries:
        login = str(entry.get("login") or "")
        if not login:
            continue
        for hit in _match_values(channel, [login], name="issue", key="login"):
            hits.append(
                Hit(
                    hit.agent,
                    "issue",
                    {
                        "login": login,
                        "number": entry.get("number"),
                        "role": entry.get("role"),
                    },
                )
            )
    return dedupe_hits(hits)


def propagate_pr_commits(
    hits: Iterable[Hit], prs: Iterable[Mapping[str, object]]
) -> list[Hit]:
    by_number = {pr.get("number"): pr for pr in prs}
    agents_by_pr: dict[object, set[str]] = {}
    for hit in hits:
        number = hit.evidence.get("pr")
        if number is not None:
            agents_by_pr.setdefault(number, set()).add(hit.agent)
    propagated: list[Hit] = []
    for number, agents in agents_by_pr.items():
        pr = by_number.get(number)
        if pr is None:
            continue
        author = str(pr.get("author") or "")
        if not author:
            continue
        for commit in pr.get("commits") or []:
            if not isinstance(commit, Mapping):
                continue
            oid = str(commit.get("oid") or "")
            if not oid or str(commit.get("author") or "") != author:
                continue
            for agent in sorted(agents):
                propagated.append(
                    Hit(agent, "pr_metadata", {"pr": number, "commit": oid, "propagated": True})
                )
    return dedupe_hits(propagated)


def dedupe_hits(hits: Iterable[Hit]) -> list[Hit]:
    seen: set[str] = set()
    unique: list[Hit] = []
    for hit in hits:
        key = json.dumps([hit.agent, hit.channel, hit.evidence], sort_keys=True, separators=(",", ":"))
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_attribution.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/detect/attribution.py tests/unit/test_detect_attribution.py
git commit -m "feat: trace-pack attribution, selection scoping, and PR propagation"
```

---

## Task 4: File channel (tree, `.gitignore`, content probes)

**Files:**
- Create: `src/detect/channels.py`
- Test: `tests/unit/test_detect_channels.py`

**Interfaces:**
- Consumes: `detect.attribution`, `detect.packs.Pack`, `discover.pipeline.Deps`, `enrich.trees_first.fetch_tree/FilePresence`, `lib.gh_client.request_with_retry`.
- Produces (used by Tasks 5–6, 8):
  - `@dataclass(frozen=True) class ChannelResult: hits: tuple[Hit, ...] = (); status: str = "ok"; note: str | None = None; stats: Mapping[str, object] = field(default_factory=dict)` (status ∈ `ok|partial|unavailable|skipped`)
  - `detect_files(deps, full_name, pack, *, ref=None, agents=None, on_response=None) -> ChannelResult`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_detect_channels.py`:

```python
from __future__ import annotations

import json

import httpx

from detect.channels import detect_files
from detect.packs import Pack, Pattern
from discover.pipeline import Deps

PACK = Pack(
    version="v1",
    agents={"Claude Code": "https://claude.com", "Cursor": "https://cursor.com", "Generic": "https://agents.md"},
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"), Pattern("cursoragent", "Cursor")),
    files=(Pattern(r"CLAUDE\.md", "Claude Code"), Pattern(r"\.cursor/", "Cursor"), Pattern(r"AGENTS\.md", "Generic")),
    branches=(Pattern("claude/", "Claude Code"), Pattern("cursor/", "Cursor")),
    labels=(Pattern("ai-generated", "Claude Code"), Pattern("^amp$", "Amp")),
    bots=(Pattern(r"dependabot\[bot\]", "dependabot"),),
    generic_weights={"AGENTS.md": 0.3},
    exclusions=frozenset({"CONVENTIONS.md"}),
)


def make_deps(handler) -> Deps:
    return Deps(
        client=httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
        engine=None,
    )


def tree_response(paths: list[str], *, truncated: bool = False) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "truncated": truncated,
            "tree": [{"path": path, "type": "blob"} for path in paths],
        },
    )


def test_detect_files_matches_tree_gitignore_and_probes_content():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/repos/octo/repo/git/trees/main":
            return tree_response(["CLAUDE.md", ".cursor/rules/x.md", "AGENTS.md", "CONVENTIONS.md"])
        if request.url.path == "/repos/octo/repo/contents/.gitignore":
            return httpx.Response(200, text=".cursor/\n# comment\n")
        if request.url.path.startswith("/repos/octo/repo/contents/"):
            return httpx.Response(200, text="# guidance\n")
        raise AssertionError(request.url)

    result = detect_files(make_deps(handler), "octo/repo", PACK, ref="main")
    assert result.status == "ok"
    by_path = {(h.agent, h.evidence["path"]): h for h in result.hits}
    assert ("Claude Code", "CLAUDE.md") in by_path
    assert ("Cursor", ".cursor/rules/x.md") in by_path
    assert ("Generic", "AGENTS.md") in by_path
    assert ("Claude Code", "CONVENTIONS.md") not in by_path
    assert ("Cursor", ".cursor/") in by_path
    assert by_path[("Cursor", ".cursor/")].evidence["source"] == "gitignore"
    assert by_path[("Claude Code", "CLAUDE.md")].evidence["size"] == len("# guidance\n")
    assert by_path[("Claude Code", "CLAUDE.md")].evidence["empty"] is False


def test_detect_files_truncated_tree_probes_literal_paths():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octo/repo/git/trees/main":
            return tree_response(["src/a.py"], truncated=True)
        if request.url.path == "/repos/octo/repo/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/repos/octo/repo/contents/CLAUDE.md":
            return httpx.Response(200, text="# x\n")
        if request.url.path.startswith("/repos/octo/repo/contents/"):
            return httpx.Response(404)
        raise AssertionError(request.url)

    result = detect_files(make_deps(handler), "octo/repo", PACK, ref="main")
    assert result.status == "partial"
    assert [h.evidence["path"] for h in result.hits] == ["CLAUDE.md"]
    assert "truncated" in (result.note or "")


def test_detect_files_unavailable_repo():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    result = detect_files(make_deps(handler), "octo/gone", PACK, ref="main")
    assert result.status == "unavailable"
    assert result.hits == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_channels.py -q`
Expected: FAIL (`ModuleNotFoundError: detect.channels`).

- [ ] **Step 3: Implement the file channel**

Create `src/detect/channels.py`:

```python
from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import httpx

from detect.attribution import Hit, dedupe_hits, match_files
from detect.packs import Pack
from discover.pipeline import Deps
from enrich.trees_first import FilePresence, fetch_tree
from lib.gh_client import API_BASE, RequestFailed, request_with_retry

OnResponse = Callable[[httpx.Response, float], None] | None

_CONTENT_PROBE_LIMIT = 5
_TRUNCATED_PROBE_LIMIT = 20
_RAW_ACCEPT = {"Accept": "application/vnd.github.raw+json"}


@dataclass(frozen=True)
class ChannelResult:
    hits: tuple[Hit, ...] = ()
    status: str = "ok"  # ok | partial | unavailable | skipped
    note: str | None = None
    stats: Mapping[str, object] = field(default_factory=dict)


def _raw_text(deps: Deps, url: str, *, on_response: OnResponse) -> tuple[str | None, str | None]:
    response = request_with_retry(
        deps.client,
        "GET",
        url,
        extra_headers=_RAW_ACCEPT,
        limiter=deps.limiter,
        token_id=deps.token_fp,
        on_response=on_response,
    )
    if response.status_code == 404:
        return None, None
    if response.status_code != 200:
        return None, f"HTTP {response.status_code}"
    return response.text, None


def _gitignore_paths(deps: Deps, full_name: str, *, on_response: OnResponse) -> tuple[tuple[str, ...], str | None]:
    text, error = _raw_text(deps, f"{API_BASE}/repos/{full_name}/contents/.gitignore", on_response=on_response)
    if text is None:
        return (), error
    lines = tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    return lines, None


def _literal_candidates(pack: Pack) -> tuple[str, ...]:
    candidates: list[str] = []
    for pattern in pack.files:
        candidate = pattern.pattern.replace("\\.", ".")
        if re.fullmatch(r"[A-Za-z0-9._/-]+", candidate) and candidate not in candidates:
            candidates.append(candidate)
    return tuple(candidates)


def _probe_missing_paths(
    deps: Deps,
    full_name: str,
    pack: Pack,
    presence: FilePresence,
    *,
    on_response: OnResponse,
) -> tuple[str, ...]:
    found: list[str] = []
    for candidate in _literal_candidates(pack)[:_TRUNCATED_PROBE_LIMIT]:
        if candidate in presence.paths or candidate.rsplit("/", 1)[-1] in pack.exclusions:
            continue
        text, error = _raw_text(
            deps, f"{API_BASE}/repos/{full_name}/contents/{candidate}", on_response=on_response
        )
        if error is None and text is not None:
            found.append(candidate)
    return tuple(found)


def _probe_content(deps: Deps, full_name: str, path: str, *, on_response: OnResponse) -> dict:
    text, error = _raw_text(
        deps, f"{API_BASE}/repos/{full_name}/contents/{path}", on_response=on_response
    )
    if error is not None or text is None:
        return {}
    return {"size": len(text), "empty": not text.strip()}


def detect_files(
    deps: Deps,
    full_name: str,
    pack: Pack,
    *,
    ref: str | None = None,
    agents: frozenset[str] | None = None,
    on_response: OnResponse = None,
) -> ChannelResult:
    try:
        presence = fetch_tree(
            deps.client,
            full_name,
            ref=ref,
            limiter=deps.limiter,
            token_id=deps.token_fp,
            on_response=on_response,
        )
    except RequestFailed as exc:
        if exc.status == 404:
            return ChannelResult(status="unavailable", note="repo not found")
        return ChannelResult(status="partial", note=f"tree: {exc.message}")
    status = "ok"
    notes: list[str] = []
    hits = list(match_files(pack, presence, agents))
    if presence.truncated:
        status = "partial"
        notes.append("tree truncated; literal-path probes used")
        probed_paths = _probe_missing_paths(deps, full_name, pack, presence, on_response=on_response)
        if probed_paths:
            probed_presence = FilePresence(
                repo_full_name=full_name,
                paths=frozenset(probed_paths),
                truncated=False,
                source="contents",
            )
            hits.extend(match_files(pack, probed_presence, agents))
    ignored, ignore_error = _gitignore_paths(deps, full_name, on_response=on_response)
    if ignore_error is not None:
        status = "partial"
        notes.append(f"gitignore: {ignore_error}")
    elif ignored:
        ignored_presence = FilePresence(
            repo_full_name=full_name,
            paths=frozenset(ignored),
            truncated=False,
            source="gitignore",
        )
        hits.extend(match_files(pack, ignored_presence, agents))
    hits = dedupe_hits(hits)
    content_paths = sorted(
        {
            hit.evidence["path"]
            for hit in hits
            if hit.evidence.get("source") == "tree"
        }
    )[:_CONTENT_PROBE_LIMIT]
    for path in content_paths:
        info = _probe_content(deps, full_name, path, on_response=on_response)
        if not info:
            continue
        for hit in hits:
            if hit.evidence.get("path") == path:
                hit.evidence.update(info)
    return ChannelResult(
        hits=tuple(hits),
        status=status,
        note="; ".join(notes) or None,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_channels.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/detect/channels.py tests/unit/test_detect_channels.py
git commit -m "feat: file channel detection"
```

---

## Task 5: History channels (author, commit_trailer, bot — one GraphQL call)

**Files:**
- Modify: `src/detect/channels.py`
- Test: `tests/unit/test_detect_channels.py`

**Interfaces:**
- Produces: `detect_history(deps, full_name, pack, *, limit=100, agents=None, on_response=None) -> dict[str, ChannelResult]` with keys `author`, `commit_trailer`, `bot`; one GraphQL call serves all three. History stats: `{"commits": int, "ai_oids": tuple[str, ...], "human_oids": tuple[str, ...]}` (noise and bot commits excluded from both counts).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_detect_channels.py`:

```python
from detect.channels import detect_history


def history_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/graphql"
    body = json.loads(request.content)
    assert body["variables"]["limit"] == 100
    return httpx.Response(
        200,
        json={
            "data": {
                "repository": {
                    "defaultBranchRef": {"name": "main"},
                    "object": {
                        "history": {
                            "nodes": [
                                {
                                    "oid": "c1",
                                    "committedDate": "2026-01-02T00:00:00Z",
                                    "message": "feat: x\n\nCo-authored-by: Cursor <cursoragent@x>",
                                    "author": {"name": "Jane", "email": "noreply@anthropic.com", "user": {"login": "jane"}},
                                    "committer": {"name": "Jane", "email": "noreply@anthropic.com", "user": {"login": "jane"}},
                                },
                                {
                                    "oid": "c2",
                                    "message": "chore: bump",
                                    "author": {"name": "bot", "email": "b@x", "user": {"login": "dependabot[bot]"}},
                                    "committer": {"name": "bot", "email": "b@x", "user": {"login": "dependabot[bot]"}},
                                },
                                {
                                    "oid": "c3",
                                    "message": "Merge branch 'main'",
                                    "author": {"name": "Jane", "email": "jane@example.com", "user": {"login": "jane"}},
                                    "committer": {"name": "Jane", "email": "jane@example.com", "user": {"login": "jane"}},
                                },
                                {
                                    "oid": "c4",
                                    "message": "fix: human work",
                                    "author": {"name": "Bob", "email": "bob@example.com", "user": {"login": "bob"}},
                                    "committer": {"name": "Bob", "email": "bob@example.com", "user": {"login": "bob"}},
                                },
                            ]
                        }
                    },
                }
            }
        },
    )


def test_history_channels_share_one_call_and_compute_window_stats():
    result = detect_history(make_deps(history_handler), "octo/repo", PACK, limit=100)
    assert [h.agent for h in result["author"].hits] == ["Claude Code"]
    assert result["author"].hits[0].evidence == {"login": "jane", "commit": "c1", "field": "email"}
    assert [h.agent for h in result["commit_trailer"].hits] == ["Cursor"]
    assert [h.agent for h in result["bot"].hits] == ["dependabot"]
    stats = result["author"].stats
    assert stats["commits"] == 2  # c1 and c4; c2 is a bot, c3 is noise
    assert set(stats["ai_oids"]) == {"c1"}
    assert set(stats["human_oids"]) == {"c4"}
    assert stats["committed_at"]["c1"] == "2026-01-02T00:00:00Z"


def test_history_null_repository_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"repository": None}})

    result = detect_history(make_deps(handler), "octo/gone", PACK)
    assert result["author"].status == "unavailable"


def test_history_selection_scopes_matching():
    result = detect_history(make_deps(history_handler), "octo/repo", PACK, agents=frozenset({"Cursor"}))
    assert result["author"].hits == ()
    assert [h.agent for h in result["commit_trailer"].hits] == ["Cursor"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_channels.py -q`
Expected: FAIL (`cannot import name 'detect_history'`).

- [ ] **Step 3: Implement `detect_history`**

Add to `src/detect/channels.py`:

```python
from detect.attribution import (
    is_noise_commit,
    match_author_identities,
    match_bots,
    match_commit_messages,
)
from lib import audit

_HISTORY_QUERY = """
query($owner: String!, $name: String!, $limit: Int!) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { name }
    object(expression: "HEAD") {
      ... on Commit {
        history(first: $limit) {
          nodes {
            oid
            committedDate
            message
            author { name email user { login } }
            committer { name email user { login } }
          }
        }
      }
    }
  }
}
"""


def _graphql(
    deps: Deps, query: str, variables: dict, *, on_response: OnResponse
) -> tuple[dict | None, str, str | None]:
    response = request_with_retry(
        deps.client,
        "POST",
        f"{API_BASE}/graphql",
        json_body={"query": query, "variables": variables},
        limiter=deps.limiter,
        token_id=deps.token_fp,
        on_response=on_response,
        retry_5xx=False,
    )
    if response.status_code != 200:
        return None, "partial", f"HTTP {response.status_code}"
    payload = audit.cached_json(response) or response.json()
    if not isinstance(payload, dict):
        return None, "partial", "malformed graphql payload"
    if payload.get("errors"):
        return payload, "partial", "graphql errors"
    return payload, "ok", None


def _person_entry(person: object, *, commit: str) -> dict[str, str]:
    if not isinstance(person, Mapping):
        return {"login": "", "name": "", "email": "", "commit": commit}
    user = person.get("user")
    login = ""
    if isinstance(user, Mapping) and user.get("login"):
        login = str(user["login"])
    return {
        "login": login,
        "name": str(person.get("name") or ""),
        "email": str(person.get("email") or ""),
        "commit": commit,
    }


def detect_history(
    deps: Deps,
    full_name: str,
    pack: Pack,
    *,
    limit: int = 100,
    agents: frozenset[str] | None = None,
    on_response: OnResponse = None,
) -> dict[str, ChannelResult]:
    owner, _, name = full_name.partition("/")
    payload, status, note = _graphql(
        deps, _HISTORY_QUERY, {"owner": owner, "name": name, "limit": limit}, on_response=on_response
    )
    if payload is None:
        return {
            key: ChannelResult(status=status, note=note)
            for key in ("author", "commit_trailer", "bot")
        }
    repository = (payload.get("data") or {}).get("repository")
    if repository is None:
        return {
            key: ChannelResult(status="unavailable", note="repo not found")
            for key in ("author", "commit_trailer", "bot")
        }
    nodes = ((repository.get("object") or {}).get("history") or {}).get("nodes") or []
    identities: list[dict[str, str]] = []
    messages: list[tuple[str, str]] = []
    committed_at: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        oid = str(node.get("oid") or "")
        message = str(node.get("message") or "")
        if node.get("committedDate"):
            committed_at[oid] = str(node["committedDate"])
        if is_noise_commit(message):
            continue
        messages.append((oid, message))
        identities.append(_person_entry(node.get("author"), commit=oid))
        identities.append(_person_entry(node.get("committer"), commit=oid))
    author_hits = match_author_identities(pack, identities, agents)
    trailer_hits = match_commit_messages(pack, messages, agents)
    bot_hits = match_bots(pack, identities)
    ai_oids = {hit.evidence.get("commit") for hit in (*author_hits, *trailer_hits)}
    bot_oids = {hit.evidence.get("commit") for hit in bot_hits}
    commit_oids = {oid for oid, _ in messages} - bot_oids
    human_oids = commit_oids - ai_oids
    stats: dict[str, object] = {
        "commits": len(commit_oids),
        "ai_oids": tuple(sorted(str(oid) for oid in ai_oids if oid)),
        "human_oids": tuple(sorted(str(oid) for oid in human_oids if oid)),
        "committed_at": committed_at,
    }
    return {
        "author": ChannelResult(
            hits=tuple(author_hits), status=status, note=note, stats=stats
        ),
        "commit_trailer": ChannelResult(
            hits=tuple(trailer_hits), status=status, note=note, stats=stats
        ),
        "bot": ChannelResult(
            hits=tuple(bot_hits),
            status=status,
            note="window: last 100 commits; generic bot evidence only",
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_channels.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/detect/channels.py tests/unit/test_detect_channels.py
git commit -m "feat: history channels (author, trailers, bots) with window stats"
```

---

## Task 6: PR channels (branch, label, pr_metadata) + PR→commit propagation + issue channel

**Files:**
- Modify: `src/detect/channels.py`
- Test: `tests/unit/test_detect_channels.py`

**Interfaces:**
- Produces:
  - `detect_prs(deps, full_name, pack, *, limit=100, agents=None, on_response=None) -> ChannelResult` — channel `pr_metadata`; hits from `match_pr_metadata` + `match_pr_authors` + `propagate_pr_commits`; `stats = {"propagated_oids": tuple[str, ...], "commenter_entries": tuple[dict, ...]}`.
  - `detect_issues(deps, full_name, pack, *, limit=100, agents=None, on_response=None, extra_entries=()) -> ChannelResult` — channel `issue`; agent users as issue assignees/authors/commenters plus any `extra_entries` (PR commenters from `detect_prs` stats).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_detect_channels.py`:

```python
from detect.channels import detect_issues, detect_prs


def pr_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["variables"]["limit"] == 100
    return httpx.Response(
        200,
        json={
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": [
                            {
                                "number": 7,
                                "headRefName": "cursor/fix",
                                "bodyText": "task: https://chatgpt.com/codex/tasks",
                                "author": {"login": "cursoragent"},
                                "labels": {"nodes": [{"name": "ai-generated"}]},
                                "comments": {"nodes": [{"author": {"login": "cursoragent"}}]},
                                "commits": {
                                    "nodes": [
                                        {"commit": {"oid": "a1", "author": {"user": {"login": "cursoragent"}}}},
                                        {"commit": {"oid": "a2", "author": {"user": {"login": "human"}}}},
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        },
    )


def test_detect_prs_matches_propagates_and_collects_commenters():
    result = detect_prs(make_deps(pr_handler), "octo/repo", PACK, limit=100)
    assert result.status == "ok"
    pairs = {(h.agent, h.evidence.get("pr")) for h in result.hits}
    assert ("Cursor", 7) in pairs and ("Claude Code", 7) in pairs and ("Codex", 7) in pairs
    propagated = [h for h in result.hits if h.evidence.get("propagated")]
    assert [(h.agent, h.evidence["commit"]) for h in propagated] == [("Claude Code", "a1"), ("Codex", "a1"), ("Cursor", "a1")]
    assert result.stats["propagated_oids"] == ("a1",)
    assert result.stats["commenter_entries"] == ({"login": "cursoragent", "number": 7, "role": "pr_commenter"},)


def issue_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": {
                "repository": {
                    "issues": {
                        "nodes": [
                            {
                                "number": 12,
                                "author": {"login": "jane"},
                                "assignees": {"nodes": [{"login": "cursoragent"}]},
                                "comments": {"nodes": [{"author": {"login": "jane"}}]},
                            }
                        ]
                    }
                }
            }
        },
    )


def test_detect_issues_matches_roles_and_extra_entries():
    result = detect_issues(
        make_deps(issue_handler),
        "octo/repo",
        PACK,
        extra_entries=({"login": "cursoragent", "number": 7, "role": "pr_commenter"},),
    )
    roles = {(h.agent, h.evidence["number"], h.evidence["role"]) for h in result.hits}
    assert roles == {("Cursor", 12, "assignee"), ("Cursor", 7, "pr_commenter")}


def test_detect_prs_unavailable_repo():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"repository": None}})

    result = detect_prs(make_deps(handler), "octo/gone", PACK)
    assert result.status == "unavailable"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_channels.py -q`
Expected: FAIL (`cannot import name 'detect_prs'`).

- [ ] **Step 3: Implement `detect_prs` and `detect_issues`**

Add to `src/detect/channels.py`:

```python
from detect.attribution import (
    match_issue_participants,
    match_pr_authors,
    match_pr_metadata,
    propagate_pr_commits,
)

_PR_QUERY = """
query($owner: String!, $name: String!, $limit: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $limit, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes {
        number
        createdAt
        headRefName
        bodyText
        author { login }
        labels(first: 20) { nodes { name } }
        comments(first: 50) { nodes { author { login } } }
        commits(first: 100) {
          nodes { commit { oid author { user { login } } } }
        }
      }
    }
  }
}
"""

_ISSUE_QUERY = """
query($owner: String!, $name: String!, $limit: Int!) {
  repository(owner: $owner, name: $name) {
    issues(first: $limit, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes {
        number
        createdAt
        author { login }
        assignees(first: 10) { nodes { login } }
        comments(first: 50) { nodes { author { login } } }
      }
    }
  }
}
"""


def _prs_from_payload(payload: dict) -> tuple[list[dict], str, str | None]:
    repository = (payload.get("data") or {}).get("repository")
    if repository is None:
        return [], "unavailable", "repo not found"
    nodes = (repository.get("pullRequests") or {}).get("nodes") or []
    prs: list[dict] = []
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        author = node.get("author")
        prs.append(
            {
                "number": node.get("number"),
                "createdAt": str(node.get("createdAt") or ""),
                "headRefName": node.get("headRefName"),
                "body": node.get("bodyText"),
                "author": str(author.get("login") or "") if isinstance(author, Mapping) else "",
                "labels": [
                    str(label.get("name"))
                    for label in (node.get("labels") or {}).get("nodes") or []
                    if isinstance(label, Mapping)
                ],
                "comments": [
                    str(comment.get("author", {}).get("login") or "")
                    for comment in (node.get("comments") or {}).get("nodes") or []
                    if isinstance(comment, Mapping)
                ],
                "commits": [
                    {
                        "oid": str((commit.get("commit") or {}).get("oid") or ""),
                        "author": str(
                            ((commit.get("commit") or {}).get("author") or {}).get("user", {}).get("login")
                            or ""
                        ),
                    }
                    for commit in (node.get("commits") or {}).get("nodes") or []
                    if isinstance(commit, Mapping)
                ],
            }
        )
    return prs, "ok", None


def detect_prs(
    deps: Deps,
    full_name: str,
    pack: Pack,
    *,
    limit: int = 100,
    agents: frozenset[str] | None = None,
    channels: frozenset[str] | None = None,
    on_response: OnResponse = None,
) -> ChannelResult:
    owner, _, name = full_name.partition("/")
    payload, status, note = _graphql(
        deps, _PR_QUERY, {"owner": owner, "name": name, "limit": limit}, on_response=on_response
    )
    if payload is None:
        return ChannelResult(status=status, note=note)
    prs, status, note = _prs_from_payload(payload)
    if status == "unavailable":
        return ChannelResult(status=status, note=note)
    hits = match_pr_metadata(pack, prs, agents) + match_pr_authors(pack, prs, agents)
    if channels is not None:
        hits = [hit for hit in hits if hit.channel in channels]
    propagated = propagate_pr_commits(hits, prs)
    commenter_entries = tuple(
        {"login": login, "number": pr["number"], "role": "pr_commenter"}
        for pr in prs
        for login in pr.get("comments") or []
        if login
    )
    return ChannelResult(
        hits=tuple(dedupe_hits([*hits, *propagated])),
        status=status,
        note="window: most recent 100 PRs",
        stats={
            "propagated_oids": tuple(sorted({h.evidence["commit"] for h in propagated})),
            "commenter_entries": commenter_entries,
            "created_at": {pr["number"]: pr["createdAt"] for pr in prs if pr.get("createdAt")},
        },
    )


def detect_issues(
    deps: Deps,
    full_name: str,
    pack: Pack,
    *,
    limit: int = 100,
    agents: frozenset[str] | None = None,
    on_response: OnResponse = None,
    extra_entries: tuple[dict, ...] = (),
) -> ChannelResult:
    owner, _, name = full_name.partition("/")
    payload, status, note = _graphql(
        deps, _ISSUE_QUERY, {"owner": owner, "name": name, "limit": limit}, on_response=on_response
    )
    if payload is None:
        return ChannelResult(status=status, note=note)
    repository = (payload.get("data") or {}).get("repository")
    if repository is None:
        return ChannelResult(status="unavailable", note="repo not found")
    entries: list[dict] = list(extra_entries)
    created_at: dict[object, str] = {}
    for node in (repository.get("issues") or {}).get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        number = node.get("number")
        if node.get("createdAt"):
            created_at[number] = str(node["createdAt"])
        author = node.get("author")
        if isinstance(author, Mapping) and author.get("login"):
            entries.append({"login": str(author["login"]), "number": number, "role": "author"})
        for assignee in (node.get("assignees") or {}).get("nodes") or []:
            if isinstance(assignee, Mapping) and assignee.get("login"):
                entries.append({"login": str(assignee["login"]), "number": number, "role": "assignee"})
        for comment in (node.get("comments") or {}).get("nodes") or []:
            comment_author = comment.get("author") if isinstance(comment, Mapping) else None
            if isinstance(comment_author, Mapping) and comment_author.get("login"):
                entries.append(
                    {"login": str(comment_author["login"]), "number": number, "role": "commenter"}
                )
    return ChannelResult(
        hits=tuple(match_issue_participants(pack, entries, agents)),
        status=status,
        note="window: most recent 100 issues; PR comments included",
        stats={"created_at": created_at},
    )
```

- [ ] **Step 4: Run all channel tests**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_channels.py -q`
Expected: PASS (10 tests).

- [ ] **Step 5: Commit**

```bash
git add src/detect/channels.py tests/unit/test_detect_channels.py
git commit -m "feat: PR and issue channels with PR-to-commit propagation"
```

---

## Task 7: Call/time estimate from live settings

**Files:**
- Create: `src/detect/estimate.py`
- Test: `tests/unit/test_detect_estimate.py`

**Interfaces:**
- Produces (used by Tasks 9, 10): `estimate(candidates, channels, *, tokens, concurrency=10, deadline_seconds=None) -> dict` with keys `repos`, `rest_calls`, `graphql_calls`, `hours`, `per_channel`, `concurrency`, `deadline_exceeded`. Call attribution: `file` owns its REST calls; each GraphQL group (history `author/commit_trailer/bot`, PRs `branch/label/pr_metadata`, issues `issue`) costs one call per repo, attributed to the first selected member.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_detect_estimate.py`:

```python
from __future__ import annotations

import pytest

from detect.estimate import estimate


def test_estimate_all_channels():
    result = estimate(
        1000,
        ["file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata", "issue"],
        tokens=2,
    )
    assert result["repos"] == 1000
    assert result["rest_calls"] == 3000  # file: tree + gitignore + content probes
    assert result["graphql_calls"] == 3000  # history + PRs + issues
    assert result["hours"] == 0.6
    assert result["per_channel"]["commit_trailer"] == 0.0
    assert result["per_channel"]["issue"] == 1.0
    assert result["deadline_exceeded"] is False


def test_estimate_file_only():
    result = estimate(200, ["file"], tokens=1)
    assert result["rest_calls"] == 600
    assert result["graphql_calls"] == 0


def test_estimate_pr_group_attributed_to_branch():
    result = estimate(200, ["branch"], tokens=1)
    assert result["rest_calls"] == 0
    assert result["graphql_calls"] == 200
    assert result["per_channel"]["branch"] == 1.0


def test_estimate_rejects_zero_tokens():
    with pytest.raises(ValueError, match="tokens"):
        estimate(10, ["file"], tokens=0)


def test_estimate_flags_deadline_overrun():
    result = estimate(100000, ["file"], tokens=1, deadline_seconds=3600)
    assert result["deadline_exceeded"] is True
```

- [ ] **Step 2: Run to verify failure**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_estimate.py -q`
Expected: FAIL (`ModuleNotFoundError: detect.estimate`).

- [ ] **Step 3: Implement `src/detect/estimate.py`**

```python
from __future__ import annotations

from collections.abc import Sequence

CHANNELS = ("file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata", "issue")

_REST_CALLS_PER_REPO = {"file": 3.0}  # tree + .gitignore + bounded content probes
_GRAPHQL_GROUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("author", "commit_trailer", "bot"), "author"),
    (("branch", "label", "pr_metadata"), "pr_metadata"),
    (("issue",), "issue"),
)
_POINTS_PER_HOUR = 5000.0


def estimate(
    candidates: int,
    channels: Sequence[str],
    *,
    tokens: int,
    concurrency: int = 10,
    deadline_seconds: float | None = None,
) -> dict:
    """Calls/time estimate. `concurrency` is display-only: the steady-state rate cap
    (points per hour per token) does not change with it."""
    if tokens <= 0:
        raise ValueError("tokens must be >= 1")
    unknown = [channel for channel in channels if channel not in CHANNELS]
    if unknown:
        raise ValueError(f"unknown channels: {unknown}")
    selected = set(channels)
    per_channel = {channel: 0.0 for channel in channels}
    rest_calls = 0.0
    if "file" in selected:
        rest_calls = candidates * _REST_CALLS_PER_REPO["file"]
        per_channel["file"] = _REST_CALLS_PER_REPO["file"]
    graphql_calls = 0.0
    for members, _owner in _GRAPHQL_GROUPS:
        picked = [channel for channel in members if channel in selected]
        if picked:
            graphql_calls += candidates
            per_channel[picked[0]] = per_channel.get(picked[0], 0.0) + 1.0
    hours = round((rest_calls + graphql_calls) / (_POINTS_PER_HOUR * tokens), 2)
    return {
        "repos": candidates,
        "rest_calls": int(rest_calls),
        "graphql_calls": int(graphql_calls),
        "hours": hours,
        "per_channel": per_channel,
        "concurrency": concurrency,
        "deadline_exceeded": deadline_seconds is not None and hours * 3600.0 > deadline_seconds,
    }
```

- [ ] **Step 4: Run to verify pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_estimate.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/detect/estimate.py tests/unit/test_detect_estimate.py
git commit -m "feat: detection call/time estimate from live settings"
```

---

## Task 8: Orchestrator + executor integration

**Files:**
- Create: `src/detect/orchestrator.py`
- Modify: `src/serve/executor.py` (`RunPayloadItem` :25, `RunPayload` :40, `_snapshot_item` :88, `create_run` :107, `_write_bundle` :196, `execute_run` :317)
- Modify: `tests/integration/test_executor.py` (expected snapshots gain `"detection": None`)
- Test: `tests/unit/test_detect_orchestrator.py`

**Interfaces:**
- Produces (used by Tasks 9–11):
  - `@dataclass(frozen=True) class DetectOptions: source_run_id: int; pack_version: str; agents: frozenset[str] | None; channels: frozenset[str]; limit: int | None = None; windows: Mapping[str, int] = {"commits":100,"prs":100,"issues":100}`
  - `@dataclass(frozen=True) class DetectConfig: deadline_seconds: float | None = None; concurrency: int = 10`
  - `run_detection(deps, run_id, spec, pack, *, config=None) -> RunPayload` — writes `detection_evidence` rows, returns items with `detection` rollups, `result_summary`, and flat `detections` rows for `detections.csv`.
- Executor gains: `RunPayloadItem.detection`, `RunPayload.result_summary`/`detections`, `create_run(..., kind=, source_run_id=)`, `result_summary` persisted at finish, `detections.csv` in the bundle.

- [ ] **Step 1: Write the failing orchestrator tests**

Create `tests/unit/test_detect_orchestrator.py`:

```python
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from detect.orchestrator import CHANNELS, DetectConfig, DetectOptions, run_detection
from detect.packs import Pack, Pattern, freeze_pack
from discover.pipeline import Deps
from serve.executor import create_run, execute_run

PACK = Pack(
    version="v1",
    agents={"Claude Code": "https://claude.com", "Codex": "https://openai.com/codex", "Generic": "https://agents.md"},
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"),),
    files=(Pattern(r"CLAUDE\.md", "Claude Code"),),
    branches=(Pattern("codex/", "Codex"),),
    labels=(Pattern("codex", "Codex"),),
    bots=(Pattern(r"dependabot\[bot\]", "dependabot"),),
    generic_weights={"AGENTS.md": 0.3},
    exclusions=frozenset({"CONVENTIONS.md"}),
)

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def seed_source_run(engine) -> int:
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO owners (id, login, type) VALUES (1, 'octo', 'User')")
        )
        connection.execute(
            text(
                "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility, default_branch)"
                " VALUES (1, 'n1', 'octo/one', 1, 'one', 'public', 'main'),"
                " (2, 'n2', 'octo/two', 1, 'two', 'public', 'main')"
            )
        )
    source_id = create_run(engine, {"q": "language:rust"}, api_version="2022-11-28")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                " VALUES (:run, 1, 'octo/one', 10), (:run, 2, 'octo/two', 5)"
            ),
            {"run": source_id},
        )
    freeze_pack(engine, PACK)
    return source_id


def make_handler(seen: list[str], queries: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/repos/octo/one/git/trees/main":
            return httpx.Response(200, json={"truncated": False, "tree": [{"path": "CLAUDE.md", "type": "blob"}]})
        if request.url.path == "/repos/octo/one/contents/CLAUDE.md":
            return httpx.Response(200, text="# guidance\n")
        if request.url.path == "/repos/octo/one/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/repos/octo/two/git/trees/main":
            return httpx.Response(404, json={"message": "Not Found"})
        if request.url.path == "/repos/octo/two/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/graphql":
            body = json.loads(request.content)
            queries.append(body["query"])
            if body["variables"].get("name") == "two":
                return httpx.Response(200, json={"data": {"repository": None}})
            if "history(" in body["query"]:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "repository": {
                                "object": {
                                    "history": {
                                        "nodes": [
                                            {
                                                "oid": "a1",
                                                "committedDate": "2026-01-02T00:00:00Z",
                                                "message": "feat: x",
                                                "author": {"name": "Jane", "email": "jane@example.com", "user": {"login": "jane"}},
                                                "committer": {"name": "Jane", "email": "jane@example.com", "user": {"login": "jane"}},
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    },
                )
            if "pullRequests(" in body["query"]:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "repository": {
                                "pullRequests": {
                                    "nodes": [
                                        {
                                            "number": 7,
                                            "createdAt": "2026-01-03T00:00:00Z",
                                            "headRefName": "codex/fix",
                                            "bodyText": "",
                                            "author": {"login": "jane"},
                                            "labels": {"nodes": []},
                                            "comments": {"nodes": []},
                                            "commits": {"nodes": [{"commit": {"oid": "a1", "author": {"user": {"login": "jane"}}}}]},
                                        }
                                    ]
                                }
                            }
                        }
                    },
                )
            if "issues(" in body["query"]:
                return httpx.Response(200, json={"data": {"repository": {"issues": {"nodes": []}}}})
        raise AssertionError(request.url)

    return handler


def make_deps(engine, handler) -> Deps:
    return Deps(
        client=httpx.Client(transport=httpx.MockTransport(handler), base_url="https://api.github.com"),
        engine=engine,
    )


def make_options(source_id: int, *, agents=None, channels=CHANNELS) -> DetectOptions:
    return DetectOptions(
        source_run_id=source_id,
        pack_version="v1",
        agents=frozenset(agents) if agents is not None else None,
        channels=frozenset(channels),
    )


def test_run_detection_writes_evidence_and_never_searches(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    queries: list[str] = []
    deps = make_deps(engine, make_handler(seen, queries))
    run_id = create_run(
        engine, {"kind": "detect", "source_run_id": source_id}, api_version="2022-11-28",
        kind="detect", source_run_id=source_id,
    )
    options = make_options(source_id, agents=["Claude Code", "Codex"])
    payload = run_detection(deps, run_id, options, PACK, config=DetectConfig(concurrency=2))

    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT repo_id, agent, channel, evidence FROM detection_evidence"
                " WHERE run_id = :run ORDER BY agent, channel, repo_id"
            ),
            {"run": run_id},
        ).mappings().all()
    pairs = {(row["agent"], row["channel"], row["repo_id"]) for row in rows}
    assert ("Claude Code", "file", 1) in pairs
    assert ("Codex", "pr_metadata", 1) in pairs  # branch match propagated to the PR author's commit
    assert ("Claude Code", "file", 2) not in pairs  # repo two is unavailable
    assert payload.result_summary["agents"] == {"Claude Code": 1, "Codex": 2}  # branch + propagated commit
    assert payload.result_summary["repos_scanned"] == 2
    assert payload.result_summary["repos_unavailable"] == 1
    item_one = next(item for item in payload.items if item.repo_id == 1)
    assert item_one.detection["agents"] == ["Claude Code", "Codex"]
    assert item_one.detection["adoption_level"] == "pervasive"  # 1 AI of 1 windowed commit -> 100%
    assert item_one.detection["first_signal_at"] == "2026-01-02T00:00:00Z"
    assert len(payload.detections) == len(rows)
    assert all("/search" not in path for path in seen)
    assert all("search(" not in query for query in queries)


def test_run_detection_never_persists_emails(clean_db):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/graphql":
            body = json.loads(request.content)
            if "history(" in body["query"]:
                return httpx.Response(
                    200,
                    json={
                        "data": {
                            "repository": {
                                "object": {
                                    "history": {
                                        "nodes": [
                                            {
                                                "oid": "a1",
                                                "committedDate": "2026-01-02T00:00:00Z",
                                                "message": "fix: x\n\nCo-authored-by: Claude <noreply@anthropic.com>",
                                                "author": {"name": "Jane", "email": "jane@example.com", "user": {"login": "jane"}},
                                                "committer": {"name": "Jane", "email": "jane@example.com", "user": {"login": "jane"}},
                                            }
                                        ]
                                    }
                                }
                            }
                        }
                    },
                )
            if "pullRequests(" in body["query"]:
                return httpx.Response(200, json={"data": {"repository": {"pullRequests": {"nodes": []}}}})
            if "issues(" in body["query"]):
                return httpx.Response(200, json={"data": {"repository": {"issues": {"nodes": []}}}})
        if request.url.path.endswith("/contents/.gitignore"):
            return httpx.Response(404)
        return httpx.Response(404, json={"message": "Not Found"})

    deps = make_deps(engine, handler)
    run_id = create_run(
        engine, {"kind": "detect", "source_run_id": source_id}, api_version="2022-11-28",
        kind="detect", source_run_id=source_id,
    )
    options = make_options(source_id)
    payload = run_detection(deps, run_id, options, PACK)
    with engine.connect() as connection:
        evidence_text = "\n".join(
            str(row[0])
            for row in connection.execute(
                text("SELECT evidence::text FROM detection_evidence WHERE run_id = :run"), {"run": run_id}
            )
        )
        audit_text = "\n".join(
            str(row[0])
            for row in connection.execute(
                text("SELECT params::text FROM audit_log WHERE run_id = :run"), {"run": run_id}
            )
        )
    assert not EMAIL.search(evidence_text), evidence_text
    assert not EMAIL.search(audit_text), audit_text
    assert not EMAIL.search(json.dumps(payload.detections))
    assert "<email>" in evidence_text


def test_execute_run_writes_result_summary_and_detections_csv(clean_db, tmp_path):
    engine = clean_db()
    source_id = seed_source_run(engine)
    seen: list[str] = []
    queries: list[str] = []
    deps = make_deps(engine, make_handler(seen, queries))
    options = make_options(source_id, agents=["Claude Code", "Codex"])
    run_id = create_run(
        engine, {"kind": "detect", "source_run_id": source_id}, api_version="2022-11-28",
        kind="detect", source_run_id=source_id,
    )
    execute_run(
        engine,
        run_id,
        runner=lambda rid, _doc: run_detection(deps, rid, options, PACK, config=DetectConfig(concurrency=2)),
        runs_root=str(tmp_path),
    )
    with engine.connect() as connection:
        row = connection.execute(
            text("SELECT status, result_summary FROM runs WHERE id = :run"), {"run": run_id}
        ).mappings().one()
        detections = connection.execute(
            text("SELECT detection FROM run_items WHERE run_id = :run AND repo_id = 1"), {"run": run_id}
        ).scalar_one()
    assert row["status"] in ("done", "partial")
    assert row["result_summary"]["agents"] == {"Claude Code": 1, "Codex": 2}
    assert detections["agents"] == ["Claude Code", "Codex"]
    evidence_csv = list(Path(tmp_path).glob(f"*/{run_id}/detections.csv"))
    assert len(evidence_csv) == 1
    with evidence_csv[0].open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert header == ["full_name", "repo_id", "agent", "channel", "evidence", "pack_version"]
```

- [ ] **Step 2: Run to verify failure**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_orchestrator.py -q`
Expected: FAIL (`ModuleNotFoundError: detect.orchestrator`; `create_run` has no `kind` kwarg).

- [ ] **Step 3: Update the executor**

In `src/serve/executor.py`:

`RunPayloadItem` gains (after `virtuals`):

```python
    detection: dict | None = None
```

`RunPayload` gains (after `field_stats`):

```python
    result_summary: dict | None = None
    detections: list[dict] = field(default_factory=list)
```

`_snapshot_item` gains `"detection": item.detection,` after `"virtuals": item.virtuals,`.

`create_run` becomes:

```python
def create_run(
    engine: Engine,
    filter_spec: dict,
    *,
    api_version: str,
    kind: str = "find",
    source_run_id: int | None = None,
) -> int:
    with engine.begin() as connection:
        run_id = connection.execute(
            insert(Runs)
            .values(
                filter_hash=_filter_hash(filter_spec),
                filter_spec=filter_spec,
                api_version=api_version,
                kind=kind,
                source_run_id=source_run_id,
            )
            .returning(Runs.id)
        ).scalar_one()
    return int(run_id)
```

`_write_bundle` gains after `_write_corpus(directory / "corpus.csv", payload.items)`:

```python
    if payload.detections:
        _write_detections(directory / "detections.csv", payload.detections)
```

and a new helper next to `_write_corpus`:

```python
_DETECTIONS_HEADER = ["full_name", "repo_id", "agent", "channel", "evidence", "pack_version"]


def _write_detections(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(_DETECTIONS_HEADER)
        for row in rows:
            writer.writerow([_csv_cell(row.get(name)) for name in _DETECTIONS_HEADER])
```

`execute_run`'s terminal success update gains `result_summary=payload.result_summary,` (inside the `.values(...)` block at ~:317-338).

In `tests/integration/test_executor.py`: `_expected_snapshot()` and every inline expected item dict gain `"detection": None,` after `"virtuals": ...` (the diffs will point at the exact spots; three inline dicts plus the helper).

- [ ] **Step 4: Implement `src/detect/orchestrator.py`**

```python
from __future__ import annotations

import json
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

import httpx
from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from detect.attribution import Hit, adoption_level, dedupe_hits
from detect.channels import ChannelResult, detect_files, detect_history, detect_issues, detect_prs
from detect.packs import Pack
from discover.pipeline import Deps
from lib import audit, cancellation, progress
from lib.deadlines import Deadline, request_deadline_seconds
from serve.executor import RunPayload, RunPayloadItem
from store.models import DetectionEvidence, Repo, RunItem

CHANNELS = ("file", "author", "branch", "label", "bot", "commit_trailer", "pr_metadata", "issue")
_HISTORY_KEYS = ("author", "commit_trailer", "bot")
_PR_KEYS = ("branch", "label", "pr_metadata")
_BOT_CHANNEL = "bot"


@dataclass(frozen=True)
class DetectOptions:
    source_run_id: int
    pack_version: str
    agents: frozenset[str] | None
    channels: frozenset[str]
    limit: int | None = None
    windows: Mapping[str, int] = field(
        default_factory=lambda: {"commits": 100, "prs": 100, "issues": 100}
    )


@dataclass(frozen=True)
class DetectConfig:
    deadline_seconds: float | None = None
    concurrency: int = 10


@dataclass
class _RepoScan:
    repo_id: int
    full_name: str
    stargazers: int | None
    hits: list[Hit]
    results: dict[str, ChannelResult]
    pr_result: ChannelResult | None
    history_stats: Mapping[str, object]
    document: dict = field(default_factory=dict)


def _audit_hook(deps: Deps, run_id: int, ledger: audit.PointsLedger, phase: str):
    def hook(response: httpx.Response, latency_ms: float) -> None:
        record = audit.record_from_response(
            {}, response, token_fp=deps.token_fp, latency_ms=latency_ms, run_id=run_id, phase=phase
        )
        ledger.add(phase, audit.cached_json(response))
        if deps.audit_buffer is not None:
            deps.audit_buffer.add(record)
        else:
            audit.record_audit(deps.engine, record)

    return hook


def _candidates(engine: Engine, source_run_id: int, limit: int | None) -> list[Mapping]:
    statement = (
        select(RunItem.repo_id, RunItem.full_name, RunItem.stargazers, Repo.default_branch)
        .join(Repo, Repo.id == RunItem.repo_id, isouter=True)
        .where(RunItem.run_id == source_run_id)
        .order_by(RunItem.stargazers.desc().nullslast(), RunItem.repo_id)
    )
    if limit is not None:
        statement = statement.limit(limit)
    with engine.connect() as connection:
        return list(connection.execute(statement).mappings())


def _scan_repo(
    deps: Deps,
    pack: Pack,
    options: DetectOptions,
    run_id: int,
    ledger: audit.PointsLedger,
    candidate: Mapping,
) -> _RepoScan:
    full_name = str(candidate["full_name"])
    ref = candidate["default_branch"]
    channels = options.channels
    results: dict[str, ChannelResult] = {}
    history_stats: Mapping[str, object] = {}
    if "file" in channels:
        results["file"] = detect_files(
            deps, full_name, pack, ref=ref, agents=options.agents,
            on_response=_audit_hook(deps, run_id, ledger, "detect:file"),
        )
    if set(_HISTORY_KEYS) & channels:
        history = detect_history(
            deps, full_name, pack, limit=options.windows.get("commits", 100), agents=options.agents,
            on_response=_audit_hook(deps, run_id, ledger, "detect:history"),
        )
        for key in _HISTORY_KEYS:
            if key in channels:
                results[key] = history[key]
        history_stats = history["author"].stats
    pr_result: ChannelResult | None = None
    if set(_PR_KEYS) & channels:
        pr_result = detect_prs(
            deps, full_name, pack, limit=options.windows.get("prs", 100), agents=options.agents,
            channels=channels, on_response=_audit_hook(deps, run_id, ledger, "detect:prs"),
        )
        for key in _PR_KEYS:
            if key in channels:
                results[key] = pr_result
    if "issue" in channels:
        extra = tuple(pr_result.stats.get("commenter_entries", ())) if pr_result is not None else ()
        results["issue"] = detect_issues(
            deps, full_name, pack, limit=options.windows.get("issues", 100), agents=options.agents,
            extra_entries=extra, on_response=_audit_hook(deps, run_id, ledger, "detect:issues"),
        )
    hits: list[Hit] = []
    for result in results.values():
        hits.extend(result.hits)
    return _RepoScan(
        repo_id=int(candidate["repo_id"]),
        full_name=full_name,
        stargazers=candidate["stargazers"],
        hits=dedupe_hits(hits),
        results=results,
        pr_result=pr_result,
        history_stats=history_stats,
    )


def _ratio_sets(scan: _RepoScan) -> tuple[set[str], set[str]]:
    ai = {str(oid) for oid in scan.history_stats.get("ai_oids", ())}
    human = {str(oid) for oid in scan.history_stats.get("human_oids", ())}
    if scan.pr_result is not None:
        propagated = {str(oid) for oid in scan.pr_result.stats.get("propagated_oids", ())}
        propagated_in_window = propagated & human
        ai |= propagated_in_window
        human -= propagated_in_window
    return ai, human


def _first_signal_at(scan: _RepoScan) -> str | None:
    dates: list[str] = []
    committed = scan.history_stats.get("committed_at") or {}
    for hit in scan.hits:
        oid = hit.evidence.get("commit")
        if oid is not None and oid in committed:
            dates.append(str(committed[oid]))
    if scan.pr_result is not None:
        created = scan.pr_result.stats.get("created_at") or {}
        for hit in scan.hits:
            number = hit.evidence.get("pr")
            if number is not None and number in created:
                dates.append(str(created[number]))
    return min(dates) if dates else None


def _repo_document(scan: _RepoScan) -> dict:
    ai, human = _ratio_sets(scan)
    ratio = len(ai) / (len(ai) + len(human)) if (ai or human) else None
    notes = [
        f"{key}: {result.note}"
        for key, result in scan.results.items()
        if result.note and result.status != "ok"
    ]
    return {
        "agents": sorted({hit.agent for hit in scan.hits if hit.channel != _BOT_CHANNEL}),
        "channels": {key: result.status for key, result in scan.results.items()},
        "unavailable": any(result.status == "unavailable" for result in scan.results.values()),
        "first_signal_at": _first_signal_at(scan),
        "commit_ratio": round(ratio, 4) if ratio is not None else None,
        "adoption_level": adoption_level(ratio),
        "notes": notes,
    }


def _summary(scans: list[_RepoScan], spec: DetectOptions, pack: Pack) -> dict:
    agent_counts: dict[str, int] = {}
    channel_counts: dict[str, int] = {}
    partials: dict[str, str] = {}
    firsts: list[str] = []
    repos_with_signal = 0
    unavailable = 0
    ai_total = 0
    human_total = 0
    for scan in scans:
        document = scan.document
        if document["unavailable"]:
            unavailable += 1
        if document["agents"]:
            repos_with_signal += 1
        for hit in scan.hits:
            if hit.channel == _BOT_CHANNEL:
                continue
            agent_counts[hit.agent] = agent_counts.get(hit.agent, 0) + 1
            channel_counts[hit.channel] = channel_counts.get(hit.channel, 0) + 1
        for key, result in scan.results.items():
            if result.status == "partial" and result.note:
                partials.setdefault(key, result.note)
        ai, human = _ratio_sets(scan)
        ai_total += len(ai)
        human_total += len(human)
        if document["first_signal_at"]:
            firsts.append(document["first_signal_at"])
    ratio = ai_total / (ai_total + human_total) if (ai_total + human_total) else None
    return {
        "repos_scanned": len(scans),
        "repos_with_signal": repos_with_signal,
        "repos_unavailable": unavailable,
        "agents": dict(sorted(agent_counts.items())),
        "channels": dict(sorted(channel_counts.items())),
        "pack_version": pack.version,
        "agents_selected": sorted(spec.agents) if spec.agents is not None else "all",
        "windows": dict(spec.windows),
        "commit_ratio": round(ratio, 4) if ratio is not None else None,
        "adoption_level": adoption_level(ratio),
        "first_signal_at": min(firsts) if firsts else None,
        "partial_channels": partials,
    }


def run_detection(
    deps: Deps,
    run_id: int,
    spec: DetectOptions,
    pack: Pack,
    *,
    config: DetectConfig | None = None,
) -> RunPayload:
    cfg = config or DetectConfig()
    if deps.limiter is not None:
        seconds = cfg.deadline_seconds if cfg.deadline_seconds is not None else request_deadline_seconds()
        deps.limiter.bind_deadline(Deadline(seconds))
    ledger = audit.PointsLedger()
    candidates = _candidates(deps.engine, spec.source_run_id, spec.limit)
    total = len(candidates)
    scans: list[_RepoScan] = []
    try:
        with ThreadPoolExecutor(max_workers=max(1, cfg.concurrency)) as pool:
            futures = [
                pool.submit(_scan_repo, deps, pack, spec, run_id, ledger, candidate)
                for candidate in candidates
            ]
            done = 0
            for future in as_completed(futures):
                cancellation.check()
                scan = future.result()
                scan.document = _repo_document(scan)
                scans.append(scan)
                rows = [
                    {
                        "run_id": run_id,
                        "repo_id": scan.repo_id,
                        "agent": hit.agent,
                        "channel": hit.channel,
                        "evidence": hit.evidence,
                        "pack_version": pack.version,
                    }
                    for hit in scan.hits
                ]
                if rows:
                    with deps.engine.begin() as connection:
                        connection.execute(insert(DetectionEvidence), rows)
                done += 1
                progress.report("detecting", done, total)
    finally:
        if deps.limiter is not None:
            deps.limiter.bind_deadline(None)
        if deps.audit_buffer is not None:
            deps.audit_buffer.flush()
    partial = any(
        result.status in ("partial", "unavailable")
        for scan in scans
        for result in scan.results.values()
    )
    items = [
        RunPayloadItem(
            repo_id=scan.repo_id,
            full_name=scan.full_name,
            stargazers=scan.stargazers,
            detection=scan.document,
        )
        for scan in scans
    ]
    detections = [
        {
            "full_name": scan.full_name,
            "repo_id": scan.repo_id,
            "agent": hit.agent,
            "channel": hit.channel,
            "evidence": json.dumps(hit.evidence, sort_keys=True),
            "pack_version": pack.version,
        }
        for scan in scans
        for hit in scan.hits
    ]
    return RunPayload(
        total_count=total,
        items=items,
        incomplete=partial,
        fetched=total,
        result_summary=_summary(scans, spec, pack),
        detections=detections,
        field_stats={"points": ledger.as_dict()},
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/unit/test_detect_orchestrator.py tests/integration/test_executor.py -q`
Expected: PASS. `test_detect_orchestrator.py` has 3 tests; `test_executor.py` diffs will be exactly the `"detection": None` key — fix any remaining expected dicts the same way.

- [ ] **Step 6: Commit**

```bash
git add src/detect/orchestrator.py src/detect/channels.py src/serve/executor.py tests/unit/test_detect_orchestrator.py tests/integration/test_executor.py
git commit -m "feat: detection orchestrator and detect run payloads"
```

---

## Task 9: Detect spec, routes, app wiring, and templates

**Files:**
- Create: `src/serve/detect_spec.py`, `src/serve/detect.py`, `src/serve/templates/detect_list.html`, `detect_options.html`, `detect_detail.html`, `partials/detect_estimate.html`, `partials/detect_status.html`
- Modify: `src/serve/app.py` (create_app :344, detect_runner_for after :408, resume branch :855, register call :1100)
- Modify: `tests/contract/test_resume.py` (detect-resume test)
- Test: `tests/contract/test_detect_routes.py`

**Interfaces:**
- Produces: `parse_detect_spec(doc) -> DetectOptions` (raises `DetectSpecError`), `detect_spec_to_dict(spec) -> dict`, `build_detect_runner(engine) -> Runner`, `register_detect(app, *, engine_factory, executor_factory, runner_factory)`, `detect_detail_response(request, engine, row)`, `latest_detect_for_run(engine, run_id)` (used in Task 10), and `create_app(detect_runner_factory=...)`.

- [ ] **Step 1: Write the failing spec + route tests**

Create `tests/contract/test_detect_routes.py` (copy the module fixtures/helpers from `tests/contract/test_resume.py:74-130` — its `make_client` already injects `runner_factory`; extend it with a `detect_runner_factory` kwarg forwarded to `create_app`, and use its `csrf_token(client)` cookie helper):

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from serve.app import create_app


@pytest.fixture()
def clean(clean_db):
    return clean_db(
        owners=[{"id": 1, "login": "octo", "type": "User"}],
        repos=[{"id": 1, "node_id": "n1", "full_name": "octo/one", "owner_id": 1, "name": "one", "visibility": "public"}],
    )


def seed_find_run(engine, status="done") -> int:
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, finished_at)"
                " VALUES ('find-hash', '{\"q\": \"rust\"}'::jsonb, '2022-11-28', :status, now())"
                " RETURNING id"
            ),
            {"status": status},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                " VALUES (:run, 1, 'octo/one', 10)"
            ),
            {"run": run_id},
        )
    return int(run_id)


def seed_pack(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('test-pack',"
                " '[{\"pattern\": \"noreply@anthropic\\\\.com\", \"agent\": \"Claude Code\"}]'::jsonb,"
                " '[{\"pattern\": \"CLAUDE\\\\.md\", \"agent\": \"Claude Code\"}]'::jsonb,"
                " '[{\"pattern\": \"codex/\", \"agent\": \"Codex\"}]'::jsonb,"
                " '[]'::jsonb)"
            )
        )


def make_client(engine, *, detect_runner=None):
    def runner_factory(_engine):
        def runner(_run_id, _spec):
            raise AssertionError("find runner must not run in detect tests")

        return runner

    def detect_factory(_engine):
        return detect_runner or (lambda run_id, spec: None)

    return TestClient(
        create_app(
            engine=engine,
            runner_factory=runner_factory,
            detect_runner_factory=detect_factory,
            runs_root="runs",
            clone_root="clones",
            redis_ping=lambda: True,
            token_present=lambda: True,
        )
    )


def csrf_token(client: TestClient) -> str:
    return client.cookies.get("gc_csrf")


def test_detections_list_renders_empty_and_filled(clean):
    client = make_client(clean)
    assert "No detections yet" in client.get("/detections").text
    seed_find_run(clean)
    client = make_client(clean)
    response = client.get("/detections")
    assert response.status_code == 200


def test_options_page_requires_finished_find_run(clean):
    client = make_client(clean)
    running = seed_find_run(clean, status="running")
    assert client.get(f"/runs/{running}/detect").status_code == 400
    done = seed_find_run(clean, status="done")
    seed_pack(clean)
    response = client.get(f"/runs/{done}/detect")
    assert response.status_code == 200
    assert "Claude Code" in response.text
    assert "test-pack" in response.text


def test_start_detection_creates_run_and_submits_runner(clean):
    calls: list[tuple[int, dict]] = []

    def detect_runner(run_id, spec):
        calls.append((run_id, spec))

    client = make_client(clean, detect_runner=detect_runner)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/runs/{source}/detect")  # sets the CSRF cookie
    response = client.post(
        f"/runs/{source}/detect",
        data={
            "csrf": csrf_token(client),
            "pack_version": "test-pack",
            "agents": ["Claude Code", "Codex"],
            "channels": ["file", "pr_metadata"],
            "limit": "50",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    new_id = int(response.headers["location"].rsplit("/", 1)[-1])
    with clean.connect() as connection:
        row = connection.execute(
            text("SELECT kind, source_run_id, filter_spec FROM runs WHERE id = :id"), {"id": new_id}
        ).mappings().one()
    assert row["kind"] == "detect"
    assert row["source_run_id"] == source
    assert row["filter_spec"]["agents"] == ["Claude Code", "Codex"]
    assert row["filter_spec"]["channels"] == ["file", "pr_metadata"]
    assert row["filter_spec"]["limit"] == 50


def test_start_detection_rejects_empty_selection(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    seed_pack(clean)
    client.get(f"/runs/{source}/detect")
    response = client.post(
        f"/runs/{source}/detect",
        data={"csrf": csrf_token(client), "pack_version": "test-pack", "channels": []},
    )
    assert response.status_code == 400
    assert "channels must be a non-empty list" in response.text


def test_estimate_partial_renders(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(f"/runs/{source}/detect-estimate?channels=file&channels=issue&limit=10")
    assert response.status_code == 200
    assert "REST calls" in response.text


def test_detect_status_partial(clean):
    client = make_client(clean)
    source = seed_find_run(clean)
    response = client.get(f"/partials/runs/{source}/detect-status")
    assert response.status_code == 200
```

Append to `tests/contract/test_resume.py` (reuse its fixtures/helpers):

```python
def test_resume_detect_run_uses_detect_runner_and_clears_evidence(clean):
    engine = clean
    with engine.begin() as connection:
        source = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status)"
                " VALUES ('s', '{}'::jsonb, '2022-11-28', 'done') RETURNING id"
            )
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('p1', '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO owners (id, login, type) VALUES (1, 'octo', 'User')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO repos (id, node_id, full_name, owner_id, name, visibility)"
                " VALUES (1, 'n1', 'octo/one', 1, 'one', 'public')"
            )
        )
        detect_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, kind, source_run_id)"
                " VALUES ('d', :spec, '2022-11-28', 'failed', 'detect', :src) RETURNING id"
            ),
            {
                "spec": json.dumps(
                    {
                        "version": 1,
                        "kind": "detect",
                        "source_run_id": int(source),
                        "pack_version": "p1",
                        "agents": None,
                        "channels": ["file"],
                        "limit": None,
                        "windows": {"commits": 100, "prs": 100, "issues": 100},
                    }
                ),
                "src": source,
            },
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO detection_evidence (run_id, repo_id, agent, channel, evidence, pack_version)"
                " VALUES (:run, 1, 'claude', 'file', '{}'::jsonb, 'p1')"
            ),
            {"run": detect_id},
        )
    seen: list[int] = []

    def detect_factory(_engine):
        def runner(run_id, _spec):
            seen.append(run_id)
            from serve.executor import RunPayload

            return RunPayload(total_count=0, items=[], fetched=0)

        return runner

    client = make_client(engine, detect_runner_factory=detect_factory)
    client.get(f"/runs/{detect_id}")  # CSRF cookie
    response = client.post(
        f"/runs/{detect_id}/resume", data={"csrf": csrf_token(client)}, follow_redirects=False
    )
    assert response.status_code == 303
    with engine.connect() as connection:
        status = connection.execute(
            text("SELECT status FROM runs WHERE id = :id"), {"id": detect_id}
        ).scalar_one()
        evidence = connection.execute(
            text("SELECT count(*) FROM detection_evidence WHERE run_id = :id"), {"id": detect_id}
        ).scalar_one()
    assert status in ("queued", "running", "done")
    assert evidence == 0
```

(`test_resume.py`'s `make_client` needs the same `detect_runner_factory` kwarg forwarding added; `json` and `text` are already imported there.)

- [ ] **Step 2: Run to verify failure**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_routes.py tests/contract/test_resume.py -q`
Expected: FAIL (`create_app` has no `detect_runner_factory`; `/detections` 404).

- [ ] **Step 3: Implement `src/serve/detect_spec.py`**

```python
from __future__ import annotations

from collections.abc import Mapping

from detect.orchestrator import CHANNELS, DetectOptions

DETECT_SPEC_VERSION = 1
DEFAULT_WINDOWS = {"commits": 100, "prs": 100, "issues": 100}


class DetectSpecError(ValueError):
    def __init__(self, errors: list[str], hints: list[str] | None = None) -> None:
        super().__init__("; ".join(errors))
        self.errors = tuple(errors)
        self.hints = tuple(hints or ())


def parse_detect_spec(doc: Mapping[str, object]) -> DetectOptions:
    if not isinstance(doc, Mapping):
        raise DetectSpecError(["detect spec must be an object"])
    errors: list[str] = []
    hints: list[str] = []
    if doc.get("kind") != "detect":
        errors.append("kind must be 'detect'")
    source = doc.get("source_run_id")
    if not isinstance(source, int) or isinstance(source, bool) or source <= 0:
        errors.append("source_run_id must be a positive integer")
        source = 0
    pack_version = doc.get("pack_version")
    if not isinstance(pack_version, str) or not pack_version:
        errors.append("pack_version is required")
        pack_version = ""
    raw_agents = doc.get("agents")
    agents: frozenset[str] | None
    if raw_agents is None:
        agents = None
    elif (
        isinstance(raw_agents, list)
        and raw_agents
        and all(isinstance(agent, str) and agent for agent in raw_agents)
    ):
        agents = frozenset(str(agent) for agent in raw_agents)
    else:
        errors.append("agents must be null or a non-empty list of agent names")
        agents = None
    raw_channels = doc.get("channels")
    if (
        isinstance(raw_channels, list)
        and raw_channels
        and all(isinstance(channel, str) for channel in raw_channels)
    ):
        unknown = sorted({str(channel) for channel in raw_channels} - set(CHANNELS))
        if unknown:
            errors.append(f"unknown channels: {unknown}")
            hints.append(f"channels must be a subset of: {', '.join(CHANNELS)}")
        channels = frozenset(str(channel) for channel in raw_channels)
    else:
        errors.append("channels must be a non-empty list")
        hints.append(f"channels must be a non-empty subset of: {', '.join(CHANNELS)}")
        channels = frozenset()
    limit = doc.get("limit")
    if limit is not None and (
        not isinstance(limit, int) or isinstance(limit, bool) or limit <= 0
    ):
        errors.append("limit must be null or a positive integer")
        limit = None
    raw_windows = doc.get("windows")
    windows = dict(DEFAULT_WINDOWS)
    if isinstance(raw_windows, Mapping):
        for key, default in DEFAULT_WINDOWS.items():
            value = raw_windows.get(key, default)
            if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 1000:
                windows[key] = value
            else:
                errors.append(f"windows.{key} must be an integer between 1 and 1000")
    if errors:
        raise DetectSpecError(errors, hints)
    return DetectOptions(
        source_run_id=int(source),
        pack_version=str(pack_version),
        agents=agents,
        channels=channels,
        limit=limit,
        windows=windows,
    )


def detect_spec_to_dict(spec: DetectOptions) -> dict:
    return {
        "version": DETECT_SPEC_VERSION,
        "kind": "detect",
        "source_run_id": spec.source_run_id,
        "pack_version": spec.pack_version,
        "agents": sorted(spec.agents) if spec.agents is not None else None,
        "channels": [channel for channel in CHANNELS if channel in spec.channels],
        "limit": spec.limit,
        "windows": dict(spec.windows),
    }
```

- [ ] **Step 4: Implement `src/serve/detect.py` and the templates**

`src/serve/detect.py`:

```python
from __future__ import annotations

import json
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from starlette.concurrency import run_in_threadpool

from detect.estimate import estimate
from detect.orchestrator import CHANNELS, DetectConfig, run_detection
from detect.packs import load_frozen
from lib.gh_client import API_VERSION, load_tokens
from serve import errors
from serve.detect_spec import DetectSpecError, detect_spec_to_dict, parse_detect_spec
from serve.executor import RunExecutor, Runner, RunPayload, create_run
from serve.pages import _item_count, _run_detail_summary, templates, validate_csrf
from store.models import DetectionEvidence, RunItem, Runs, TracePack
from store.settings import load_run_settings


def build_detect_runner(engine: Engine) -> Runner:
    def runner(run_id: int, spec_doc: dict) -> RunPayload:
        from serve.runner import build_deps

        settings = load_run_settings(engine)
        spec = parse_detect_spec(spec_doc)
        pack = load_frozen(engine, spec.pack_version)
        deps = build_deps(engine, max_concurrent=settings.limiter_max_concurrent)
        try:
            return run_detection(
                deps,
                run_id,
                spec,
                pack,
                config=DetectConfig(
                    deadline_seconds=float(settings.request_deadline_seconds),
                    concurrency=min(settings.limiter_max_concurrent, 32),
                ),
            )
        finally:
            deps.client.close()

    return runner


def _run_row(engine: Engine, run_id: int):
    with engine.connect() as connection:
        return connection.execute(select(Runs).where(Runs.id == run_id)).mappings().one_or_none()


def _pack_versions(engine: Engine) -> list[str]:
    with engine.connect() as connection:
        return [
            str(row[0])
            for row in connection.execute(
                select(TracePack.version).order_by(TracePack.frozen_at.desc(), TracePack.version)
            )
        ]


def _latest_pack(engine: Engine):
    versions = _pack_versions(engine)
    if not versions:
        return None
    return load_frozen(engine, versions[0])


def _candidate_count(engine: Engine, run_id: int) -> int:
    with engine.connect() as connection:
        count = connection.scalar(
            select(func.count()).select_from(RunItem).where(RunItem.run_id == run_id)
        )
    return int(count or 0)


def latest_detect_for_run(engine: Engine, run_id: int):
    with engine.connect() as connection:
        return (
            connection.execute(
                select(Runs)
                .where(Runs.kind == "detect", Runs.source_run_id == run_id)
                .order_by(Runs.created_at.desc(), Runs.id.desc())
                .limit(1)
            )
            .mappings()
            .one_or_none()
        )


def _options_context(engine: Engine, run_id: int, *, errors_: list[str], hints: list[str]) -> dict:
    pack = _latest_pack(engine)
    return {
        "source": {"id": run_id, "eligible": True, "status": "done"},
        "packs": _pack_versions(engine),
        "roster": pack.roster() if pack is not None else (),
        "channels": CHANNELS,
        "candidate_count": _candidate_count(engine, run_id),
        "errors": errors_,
        "hints": hints,
    }


def _evidence_summary(evidence: dict) -> str:
    if "path" in evidence:
        suffix = " (hidden via .gitignore)" if evidence.get("source") == "gitignore" else ""
        return f"{evidence['path']}{suffix}"
    if "commit" in evidence and "snippet" in evidence:
        return f"{evidence['commit']}: {evidence['snippet']}"
    if "commit" in evidence and evidence.get("propagated"):
        return f"PR #{evidence.get('pr')} → commit {evidence['commit']}"
    if "pr" in evidence and "head" in evidence:
        return f"PR #{evidence['pr']} branch {evidence['head']}"
    if "pr" in evidence and "label" in evidence:
        return f"PR #{evidence['pr']} label {evidence['label']}"
    if "pr" in evidence and "snippet" in evidence:
        return f"PR #{evidence['pr']} body marker"
    if "pr" in evidence and "author" in evidence:
        return f"PR #{evidence['pr']} author {evidence['author']}"
    if "login" in evidence and "number" in evidence:
        return f"{evidence.get('role')} of #{evidence['number']} ({evidence['login']})"
    if "commit" in evidence and "field" in evidence:
        return f"commit {evidence['commit']} ({evidence['field']} match)"
    return json.dumps(evidence, sort_keys=True)[:120]


def detect_detail_response(request: Request, engine: Engine, row) -> HTMLResponse:
    run_id = int(row["id"])
    summary = _run_detail_summary(row, _item_count(engine, run_id))
    with engine.connect() as connection:
        item_rows = list(
            connection.execute(
                select(RunItem)
                .where(RunItem.run_id == run_id)
                .order_by(RunItem.stargazers.desc().nullslast(), RunItem.repo_id)
            ).mappings()
        )
        evidence_rows = list(
            connection.execute(
                select(DetectionEvidence)
                .where(DetectionEvidence.run_id == run_id)
                .order_by(DetectionEvidence.repo_id, DetectionEvidence.agent, DetectionEvidence.channel)
            ).mappings()
        )
    by_repo: dict[int, list] = {}
    for evidence in evidence_rows:
        by_repo.setdefault(evidence["repo_id"], []).append(evidence)
    repos = []
    for item in item_rows:
        rollup = item["detection"] or {}
        grouped: dict[str, list] = {}
        for evidence in by_repo.get(item["repo_id"], []):
            grouped.setdefault(evidence["channel"], []).append(
                {"agent": evidence["agent"], "summary": _evidence_summary(evidence["evidence"])}
            )
        repos.append(
            {
                "repo_id": item["repo_id"],
                "full_name": item["full_name"],
                "agents": rollup.get("agents", []),
                "unavailable": bool(rollup.get("unavailable")),
                "notes": rollup.get("notes", []),
                "channels": grouped,
            }
        )
    spec = row["filter_spec"] or {}
    return templates.TemplateResponse(
        request,
        "detect_detail.html",
        {
            "run": summary,
            "detection": {
                "source_run_id": row["source_run_id"],
                "summary": row["result_summary"] or {},
                "windows": spec.get("windows") or {"commits": 100, "prs": 100, "issues": 100},
                "repos": repos,
            },
            "csrf_token": request.state.csrf_token,
        },
    )


def register_detect(
    application: FastAPI,
    *,
    engine_factory: Callable[[], Engine],
    executor_factory: Callable[[], RunExecutor],
    runner_factory: Callable[[], Runner],
) -> None:
    @application.get("/detections", response_class=HTMLResponse)
    def detections_page(request: Request):
        engine = engine_factory()
        with engine.connect() as connection:
            rows = list(
                connection.execute(
                    select(Runs)
                    .where(Runs.kind == "detect")
                    .order_by(Runs.created_at.desc(), Runs.id.desc())
                    .limit(200)
                ).mappings()
            )
        return templates.TemplateResponse(
            request,
            "detect_list.html",
            {
                "detections": [
                    {
                        "id": row["id"],
                        "status": row["status"],
                        "source_run_id": row["source_run_id"],
                        "created_at": row["created_at"],
                        "summary": row["result_summary"] or {},
                    }
                    for row in rows
                ],
                "csrf_token": request.state.csrf_token,
            },
        )

    @application.get("/runs/{run_id}/detect", response_class=HTMLResponse)
    def detect_options_page(request: Request, run_id: int):
        engine = engine_factory()
        row = _run_row(engine, run_id)
        if row is None:
            return templates.TemplateResponse(
                request, "detect_options.html", {"source": None}, status_code=404
            )
        if row["kind"] != "find" or row["status"] not in ("done", "partial"):
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {"source": {"id": run_id, "eligible": False, "status": row["status"]}},
                status_code=400,
            )
        return templates.TemplateResponse(
            request,
            "detect_options.html",
            {**_options_context(engine, run_id, errors_=[], hints=[]), "csrf_token": request.state.csrf_token},
        )

    @application.post("/runs/{run_id}/detect")
    async def detect_start(request: Request, run_id: int):
        if not await validate_csrf(request):
            return errors.csrf_error_page(request)
        form = await request.form()
        raw_limit = str(form.get("limit") or "").strip()
        limit: int | None = None
        if raw_limit:
            try:
                limit = int(raw_limit)
            except ValueError:
                limit = 0
        doc = {
            "version": 1,
            "kind": "detect",
            "source_run_id": run_id,
            "pack_version": str(form.get("pack_version") or "").strip(),
            "agents": [str(value) for value in form.getlist("agents") if str(value).strip()] or None,
            "channels": [str(value) for value in form.getlist("channels") if str(value).strip()],
            "limit": limit,
            "windows": {"commits": 100, "prs": 100, "issues": 100},
        }
        engine = engine_factory()
        try:
            spec = parse_detect_spec(doc)
        except DetectSpecError as exc:
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {
                    **_options_context(engine, run_id, errors_=list(exc.errors), hints=list(exc.hints)),
                    "csrf_token": request.state.csrf_token,
                },
                status_code=400,
            )
        row = await run_in_threadpool(_run_row, engine, run_id)
        if row is None or row["kind"] != "find" or row["status"] not in ("done", "partial"):
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {"source": {"id": run_id, "eligible": False, "status": row["status"] if row else "missing"}},
                status_code=400,
            )
        try:
            await run_in_threadpool(load_frozen, engine, spec.pack_version)
        except KeyError:
            return templates.TemplateResponse(
                request,
                "detect_options.html",
                {
                    **_options_context(engine, run_id, errors_=[f"unknown pack version {spec.pack_version!r}"], hints=[]),
                    "csrf_token": request.state.csrf_token,
                },
                status_code=400,
            )
        new_id = await run_in_threadpool(
            create_run,
            engine,
            detect_spec_to_dict(spec),
            api_version=API_VERSION,
            kind="detect",
            source_run_id=run_id,
        )
        executor_factory().submit(new_id, runner_factory())
        return RedirectResponse(f"/runs/{new_id}", status_code=303)

    @application.get("/runs/{run_id}/detect-estimate", response_class=HTMLResponse)
    def detect_estimate_partial(request: Request, run_id: int):
        engine = engine_factory()
        raw_channels = request.query_params.getlist("channels")
        if len(raw_channels) == 1 and "," in raw_channels[0]:
            raw_channels = raw_channels[0].split(",")
        channels = [channel for channel in raw_channels if channel in CHANNELS] or list(CHANNELS)
        raw_limit = request.query_params.get("limit", "").strip()
        candidates = _candidate_count(engine, run_id)
        if raw_limit.isdigit() and int(raw_limit) > 0:
            candidates = min(candidates, int(raw_limit))
        settings = load_run_settings(engine)
        result = estimate(
            candidates,
            channels,
            tokens=max(1, len(load_tokens())),
            concurrency=settings.limiter_max_concurrent,
            deadline_seconds=float(settings.request_deadline_seconds),
        )
        return templates.TemplateResponse(
            request, "partials/detect_estimate.html", {"estimate": result}
        )

    @application.get("/partials/runs/{run_id}/detect-status", response_class=HTMLResponse)
    def detect_status_partial(request: Request, run_id: int):
        engine = engine_factory()
        row = _run_row(engine, run_id)
        if row is None:
            return HTMLResponse("run not found", status_code=404)
        return templates.TemplateResponse(
            request,
            "partials/detect_status.html",
            {
                "run": _run_detail_summary(row, _item_count(engine, run_id)),
                "result_summary": row["result_summary"] or {},
                "csrf_token": request.state.csrf_token,
            },
        )
```

Templates — `src/serve/templates/detect_list.html`:

```html
{% extends "base.html" %}
{% block title %}Detections · gitcorpus{% endblock %}
{% block body %}
<section class="panel" id="detections-header">
  <div class="panel-head">
    <h1>Detections</h1>
    <p class="muted">Detection runs scan a frozen search through GitHub’s API and store per-repo agent evidence. Start one from a finished search or a corpus.</p>
  </div>
  <div class="table-wrap">
    <table id="detections-table" class="data-table">
      <thead>
        <tr><th scope="col">Run</th><th scope="col">From search</th><th scope="col">Status</th><th scope="col">Started</th><th scope="col">Signals</th></tr>
      </thead>
      <tbody>
      {% for item in detections %}
        <tr id="detection-{{ item.id }}">
          <td><a href="/runs/{{ item.id }}">#{{ item.id }}</a></td>
          <td><a href="/runs/{{ item.source_run_id }}">#{{ item.source_run_id }}</a></td>
          <td>{{ status_label(item.status) }}</td>
          <td>{{ item.created_at }}</td>
          <td>{% if item.summary.agents %}{{ item.summary.agents | length }} agents · {{ item.summary.repos_with_signal }} repos{% else %}—{% endif %}</td>
        </tr>
      {% endfor %}
      </tbody>
    </table>
  </div>
  {% if not detections %}
  <div id="detections-empty" class="empty-state">
    <p>No detections yet</p>
    <p class="muted">Open a finished search or a corpus and choose “Detect agent use”.</p>
    <p class="empty-actions"><a class="button ghost" href="/runs">Browse searches</a></p>
  </div>
  {% endif %}
</section>
{% endblock %}
```

`detect_options.html`:

```html
{% extends "base.html" %}
{% block title %}Detect agent use · gitcorpus{% endblock %}
{% block body %}
{% if not source %}
<section class="panel" id="detect-not-found">
  <h1>Search not found</h1>
  <p class="muted">No search with this id exists in the database.</p>
  <p><a href="/runs">All searches</a></p>
</section>
{% elif not source.eligible %}
<section class="panel" id="detect-ineligible">
  <h1>Detection needs a finished search</h1>
  <p class="muted">Search #{{ source.id }} is {{ status_label(source.status) }}; detection runs on searches that finished (done or partial).</p>
  <p><a href="/runs/{{ source.id }}">Back to the search</a></p>
</section>
{% else %}
<section class="panel" id="detect-options" data-run-id="{{ source.id }}">
  <div class="panel-head">
    <h1>Detect agent use — search #{{ source.id }}</h1>
    <p class="muted">Scans the frozen corpus through GitHub’s API on its own allowance and stores evidence per repo. It never calls discovery/search endpoints and never copies code.</p>
  </div>
  {% if errors %}
  <div id="detect-errors" class="empty-state error-state" role="alert">
    {% for error in errors %}<p>{{ error }}</p>{% endfor %}
    {% for hint in hints %}<p class="muted">{{ hint }}</p>{% endfor %}
  </div>
  {% endif %}
  {% if not packs %}
  <p id="detect-no-packs" class="flag warn">No trace packs are frozen yet. Build one with <code>python -m detect.packs build</code> and <code>… freeze</code>, then reload this page.</p>
  {% endif %}
  <form id="detect-form" action="/runs/{{ source.id }}/detect" method="post">
    <input type="hidden" name="csrf" value="{{ csrf_token }}">
    <label class="field" for="detect-pack">
      <span class="field-label">Pack version</span>
      <select class="field-input" id="detect-pack" name="pack_version">
        {% for version in packs %}<option value="{{ version }}">{{ version }}</option>{% endfor %}
      </select>
    </label>
    <fieldset>
      <legend>Agents ({{ roster | length }})</legend>
      <p class="muted">Only the selected agents are matched, counted, and exported. Keep all checked to scan for every agent.</p>
      <div class="checklist" id="detect-agents">
        {% for agent in roster %}
        <label><input type="checkbox" name="agents" value="{{ agent }}" checked> {{ agent }}</label>
        {% endfor %}
      </div>
    </fieldset>
    <fieldset>
      <legend>Channels</legend>
      <div class="checklist" id="detect-channels">
        {% for channel in channels %}
        <label><input type="checkbox" name="channels" value="{{ channel }}" checked> {{ channel }}</label>
        {% endfor %}
      </div>
    </fieldset>
    <label class="field" for="detect-limit">
      <span class="field-label">Top-N repos (blank = all {{ candidate_count }})</span>
      <input class="field-input" id="detect-limit" name="limit" type="number" min="1">
    </label>
    <div id="detect-estimate"
         hx-get="/runs/{{ source.id }}/detect-estimate"
         hx-trigger="load, change from:#detect-form"
         hx-include="#detect-form"
         hx-swap="outerHTML">
      <p class="muted">Estimating…</p>
    </div>
    <div class="form-actions">
      <button id="detect-start" class="button primary" type="submit">Start detection</button>
      <a class="button" href="/runs/{{ source.id }}">Cancel</a>
    </div>
  </form>
  <p class="muted">Depth is windowed: last 100 commits, most recent 100 PRs and issues — labelled as windowed, never presented as a census. Tier boundaries are documented in <code>docs/detection-tiers.md</code>. Detection is an undercount: agents that hide their traces are not visible.</p>
  <p><a href="/detections">All detections</a></p>
</section>
{% endif %}
{% endblock %}
```

`partials/detect_estimate.html`:

```html
<div id="detect-estimate">
  <p><strong>{{ estimate.rest_calls }}</strong> REST calls + <strong>{{ estimate.graphql_calls }}</strong> GraphQL calls ≈ <strong>{{ estimate.hours }}h</strong> for {{ estimate.repos }} repos ({{ estimate.concurrency }} concurrent).</p>
  {% if estimate.deadline_exceeded %}
  <p class="flag warn">This estimate exceeds the request deadline; the run would stop partial. Narrow the top-N or the channels.</p>
  {% endif %}
</div>
```

`partials/detect_status.html`:

```html
<div id="detect-status"{% if run.polling %} hx-get="/partials/runs/{{ run.id }}/detect-status" hx-trigger="every 2s [document.visibilityState === 'visible']" hx-swap="outerHTML"{% endif %}>
  <p class="run-status-line">
    <span class="status-pill status-{{ run.status }}">{{ status_label(run.status) }}</span>
    {% if run.progress %}<span class="muted">{{ run.progress.label }} — {{ run.progress.done }} / {{ run.progress.total or "?" }}{% if run.progress.eta %} · {{ run.progress.eta }} left{% endif %}</span>{% endif %}
    {% if run.error %}<span class="flag error">{{ run.error }}</span>{% endif %}
  </p>
  {% if run.status in ('queued', 'running') %}
  <form class="inline-form" method="post" action="/runs/{{ run.id }}/cancel">
    <input type="hidden" name="csrf" value="{{ csrf_token }}">
    <button class="button" type="submit">Stop detection</button>
  </form>
  {% elif run.status in ('failed', 'partial', 'cancelled') %}
  <form class="inline-form" method="post" action="/runs/{{ run.id }}/resume">
    <input type="hidden" name="csrf" value="{{ csrf_token }}">
    <button class="button primary" type="submit">Resume</button>
  </form>
  {% endif %}
  {% if result_summary and result_summary.repos_scanned %}
  <p class="muted">{{ result_summary.repos_scanned }} repos scanned · {{ result_summary.repos_with_signal }} with signals{% if result_summary.repos_unavailable %} · {{ result_summary.repos_unavailable }} unavailable{% endif %}</p>
  {% endif %}
</div>
```

`detect_detail.html`:

```html
{% extends "base.html" %}
{% block title %}Detection {{ run.id if run else "not found" }} · gitcorpus{% endblock %}
{% block body %}
{% if not run %}
<section class="panel" id="run-not-found">
  <h1>Detection not found</h1>
  <p class="muted">No run with this id exists in the database.</p>
  <p><a href="/detections">All detections</a></p>
</section>
{% else %}
<section class="panel" id="run-header" data-run-id="{{ run.id }}">
  <div class="panel-head">
    <h1>Detection #{{ run.id }} — search #{{ detection.source_run_id }}</h1>
    <span class="run-hash-wrap"><span class="mono" data-hash="{{ run.filter_hash }}">{{ run.hash_short }}</span></span>
  </div>
  {% include "partials/detect_status.html" %}
</section>
<section class="panel" id="detection-summary">
  <div class="panel-head"><h2>Summary</h2></div>
  <div class="cards">
    <div class="card"><span class="muted">Repos scanned</span><strong>{{ detection.summary.repos_scanned or 0 }}</strong></div>
    <div class="card"><span class="muted">With any signal</span><strong>{{ detection.summary.repos_with_signal or 0 }}</strong></div>
    <div class="card"><span class="muted">Unavailable</span><strong>{{ detection.summary.repos_unavailable or 0 }}</strong></div>
    <div class="card"><span class="muted">Windowed commit ratio</span><strong>{{ detection.summary.commit_ratio if detection.summary.commit_ratio is not none else "—" }}</strong> <span class="muted">{{ detection.summary.adoption_level or "—" }}</span></div>
    <div class="card"><span class="muted">Pack</span><strong>{{ detection.summary.pack_version or "—" }}</strong></div>
    <div class="card"><span class="muted">First signal</span><strong>{{ detection.summary.first_signal_at or "—" }}</strong></div>
  </div>
  {% if detection.summary.agents %}
  <p id="detection-agents">{% for agent, count in detection.summary.agents.items() %}<span class="chip">{{ agent }} · {{ count }}</span> {% endfor %}</p>
  {% endif %}
  {% if detection.summary.partial_channels %}
  <p class="flag warn" id="detection-partials">Partial channels: {% for channel, note in detection.summary.partial_channels.items() %}{{ channel }} ({{ note }}){% if not loop.last %}; {% endif %}{% endfor %}</p>
  {% endif %}
  <p class="muted">Depth: {{ detection.windows.commits }} commits · {{ detection.windows.prs }} PRs · {{ detection.windows.issues }} issues (windowed). Papers’ baseline: ~0.5–1% false positives, ~3% borderline; detection is an undercount.</p>
</section>
<section class="panel" id="detection-evidence">
  <div class="panel-head">
    <h2>Per-repo evidence</h2>
    <div class="form-actions">
      <a id="detection-export" class="button" href="/runs/{{ run.id }}/export?format=detections">Export evidence CSV</a>
      <a class="button" href="/runs/{{ run.id }}/export?format=json">Export JSON</a>
      <a class="button" href="/runs/{{ run.id }}/export?format=csv">Export CSV</a>
    </div>
  </div>
  {% for repo in detection.repos %}
  <details id="detection-repo-{{ repo.repo_id }}">
    <summary>{{ repo.full_name }} · {{ repo.agents | join(", ") or "no signals" }}{% if repo.unavailable %} · unavailable{% endif %}</summary>
    {% if repo.notes %}<p class="muted">{{ repo.notes | join("; ") }}</p>{% endif %}
    {% for channel, hits in repo.channels.items() %}
      {% if hits %}
      <h4>{{ channel }}</h4>
      <ul>
        {% for hit in hits %}<li><strong>{{ hit.agent }}</strong> — {{ hit.summary }}</li>{% endfor %}
      </ul>
      {% endif %}
    {% endfor %}
  </details>
  {% endfor %}
  {% if not detection.repos %}<p class="muted">No repos were scanned.</p>{% endif %}
</section>
{% endif %}
{% endblock %}
```

- [ ] **Step 5: Wire `src/serve/app.py`**

Add `detect_runner_factory: Callable[[Engine], Runner] | None = None,` to the `create_app` signature (after `runner_factory`). After `runner_for` (…:408), add:

```python
    def detect_runner_for() -> Runner:
        def build() -> Runner:
            if detect_runner_factory is not None:
                return detect_runner_factory(engine_for())
            from serve.detect import build_detect_runner

            return build_detect_runner(engine_for())

        return cast(Runner, loaders.get("detect_runner", build))
```

Replace the resume branch (`:855-868`) with:

```python
        if row.get("kind") == "detect":
            submit_runner = detect_runner_for()
        else:
            submit_runner = runner_for()
```

After `register_corpora(application, engine_factory=engine_for)` add:

```python
    from serve.detect import register_detect

    register_detect(
        application,
        engine_factory=engine_for,
        executor_factory=executor_for,
        runner_factory=detect_runner_for,
    )
```

(Import `register_detect` at module top with the other `register_*` imports instead of inline if preferred; either way `app.py` must not import `serve.detect` before `serve.pages`.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_routes.py tests/contract/test_resume.py -q`
Expected: PASS (7 + existing resume tests).

- [ ] **Step 7: Commit**

```bash
git add src/serve/detect_spec.py src/serve/detect.py src/serve/templates/detect_list.html src/serve/templates/detect_options.html src/serve/templates/detect_detail.html src/serve/templates/partials/detect_estimate.html src/serve/templates/partials/detect_status.html src/serve/app.py tests/contract/test_detect_routes.py tests/contract/test_resume.py
git commit -m "feat: detect spec, routes, and console options page"
```

---

## Task 10: Console wiring, evidence export, golden

**Files:**
- Modify: `src/serve/pages.py` (run_page :1154), `src/serve/templates/base.html` (:43), `run_detail.html` (:44-92), `corpora.html`, `corpus_detail.html`, `src/serve/corpora.py` (list/detail contexts), `src/serve/runs.py` (`_BUNDLE_FILES` :36), `src/serve/app.py` (export route :960), `tests/contract/test_run_detail.py` (:690), `tests/contract/test_corpora.py` (:222)
- Modify: `tests/golden/conftest.py` (seed + `PATH_PARAMS` + `EXTRA_CASES`), `tests/golden/snapshots/*`, `tests/golden/snapshots/openapi.sha256`
- Test: `tests/contract/test_detect_pages.py`

**Interfaces:**
- Consumes: `serve.detect.detect_detail_response`, `serve.detect.latest_detect_for_run`, `serve.detect._pack_versions`.
- Produces: kind-branched run page, Detections nav, wired buttons, populated “Last detection”, `?format=detections` export, golden coverage.

- [ ] **Step 1: Write the failing page tests**

Create `tests/contract/test_detect_pages.py` (copy the `clean`/`make_client`/`csrf_token`/`seed_find_run`/`seed_pack` helpers from `test_detect_routes.py` verbatim — do not import across test modules):

```python
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from serve.app import create_app


@pytest.fixture()
def clean(clean_db):
    return clean_db(
        owners=[{"id": 1, "login": "octo", "type": "User"}],
        repos=[{"id": 1, "node_id": "n1", "full_name": "octo/one", "owner_id": 1, "name": "one", "visibility": "public"}],
    )


def seed_find_run(engine, status="done") -> int:
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, finished_at)"
                " VALUES ('find-hash', '{\"q\": \"rust\"}'::jsonb, '2022-11-28', :status, now())"
                " RETURNING id"
            ),
            {"status": status},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers)"
                " VALUES (:run, 1, 'octo/one', 10)"
            ),
            {"run": run_id},
        )
    return int(run_id)


def seed_pack(engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO trace_packs (version, authors, files, branches, labels)"
                " VALUES ('test-pack',"
                " '[{\"pattern\": \"noreply@anthropic\\\\.com\", \"agent\": \"Claude Code\"}]'::jsonb,"
                " '[{\"pattern\": \"CLAUDE\\\\.md\", \"agent\": \"Claude Code\"}]'::jsonb,"
                " '[{\"pattern\": \"codex/\", \"agent\": \"Codex\"}]'::jsonb,"
                " '[]'::jsonb)"
            )
        )


def make_client(engine):
    def runner_factory(_engine):
        def runner(_run_id, _spec):
            raise AssertionError("find runner must not run in detect page tests")

        return runner

    return TestClient(
        create_app(
            engine=engine,
            runner_factory=runner_factory,
            detect_runner_factory=lambda _engine: (lambda run_id, spec: None),
            runs_root="runs",
            clone_root="clones",
            redis_ping=lambda: True,
            token_present=lambda: True,
        )
    )


def seed_detect_run(engine, source_id: int) -> int:
    with engine.begin() as connection:
        run_id = connection.execute(
            text(
                "INSERT INTO runs (filter_hash, filter_spec, api_version, status, kind, source_run_id, result_summary, finished_at)"
                " VALUES ('detect-hash', '{\"version\": 1, \"kind\": \"detect\", \"source_run_id\": :src,"
                " \"pack_version\": \"test-pack\", \"agents\": null, \"channels\": [\"file\", \"pr_metadata\"],"
                " \"limit\": null, \"windows\": {\"commits\": 100, \"prs\": 100, \"issues\": 100}}'::jsonb,"
                " '2022-11-28', 'done', 'detect', :src,"
                " '{\"repos_scanned\": 1, \"repos_with_signal\": 1, \"repos_unavailable\": 0,"
                " \"agents\": {\"Claude Code\": 1}, \"channels\": {\"file\": 1}, \"pack_version\": \"test-pack\","
                " \"agents_selected\": \"all\", \"windows\": {\"commits\": 100, \"prs\": 100, \"issues\": 100},"
                " \"commit_ratio\": 1.0, \"adoption_level\": \"pervasive\", \"first_signal_at\": \"2026-01-02T00:00:00Z\","
                " \"partial_channels\": {}}'::jsonb, now()) RETURNING id"
            ),
            {"src": source_id},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO run_items (run_id, repo_id, full_name, stargazers, detection)"
                " VALUES (:run, 1, 'octo/one', 10,"
                " '{\"agents\": [\"Claude Code\"], \"channels\": {\"file\": \"ok\"}, \"unavailable\": false,"
                " \"first_signal_at\": \"2026-01-02T00:00:00Z\", \"commit_ratio\": 1.0,"
                " \"adoption_level\": \"pervasive\", \"notes\": []}'::jsonb)"
            ),
            {"run": run_id},
        )
        connection.execute(
            text(
                "INSERT INTO detection_evidence (run_id, repo_id, agent, channel, evidence, pack_version)"
                " VALUES (:run, 1, 'Claude Code', 'file', '{\"path\": \"CLAUDE.md\"}'::jsonb, 'test-pack')"
            ),
            {"run": run_id},
        )
    return int(run_id)


def test_run_page_branches_to_detection_detail(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(f"/runs/{detect_id}")
    assert response.status_code == 200
    assert "Detection" in response.text
    assert "CLAUDE.md" in response.text
    assert "Export evidence CSV" in response.text
    assert "Windowed commit ratio" in response.text


def test_find_run_page_wires_detect_button_and_badge(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(f"/runs/{source}")
    assert f'href="/runs/{source}/detect"' in response.text
    assert f"/runs/{detect_id}" in response.text
    assert "Coming soon" not in response.text


def test_nav_has_detections_link(clean):
    client = make_client(clean)
    response = client.get("/")
    assert 'href="/detections"' in response.text


def test_corpora_pages_wire_detect_and_last_detection(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    with clean.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO corpora (id, name, source_run_id, note, repo_count)"
                " VALUES (1, 'corpus one', :src, NULL, 1)"
            ),
            {"src": source},
        )
    client = make_client(clean)
    listing = client.get("/corpora")
    assert f'href="/runs/{source}/detect"' in listing.text
    assert f"/runs/{detect_id}" in listing.text
    assert "Coming soon" not in listing.text
    detail = client.get("/corpora/1")
    assert f'href="/runs/{source}/detect"' in detail.text


def test_detections_export_renders_evidence_csv(clean):
    source = seed_find_run(clean)
    seed_pack(clean)
    detect_id = seed_detect_run(clean, source)
    client = make_client(clean)
    response = client.get(f"/runs/{detect_id}/export?format=detections")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "full_name,repo_id,agent,channel,evidence,pack_version" in response.text
    assert "Claude Code" in response.text
```

- [ ] **Step 2: Run to verify failure**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_pages.py -q`
Expected: FAIL (run page renders the find template; nav has no link; export rejects `detections`).

- [ ] **Step 3: Implement the wiring**

`src/serve/pages.py` — in `run_page` (after the `row is None` check, before building the table):

```python
        if row["kind"] == "detect":
            from serve.detect import detect_detail_response

            return detect_detail_response(request, engine, row)
```

and in the find-run context dict add:

```python
                "latest_detect": _latest_detect_context(engine, run_id),
```

with a helper at module level:

```python
def _latest_detect_context(engine: Engine, run_id: int) -> dict | None:
    from serve.detect import latest_detect_for_run

    row = latest_detect_for_run(engine, run_id)
    if row is None:
        return None
    summary = row["result_summary"] or {}
    return {"id": row["id"], "status": row["status"], "signals": sum((summary.get("agents") or {}).values())}
```

`src/serve/templates/base.html` — replace the greyed span (line 43):

```html
    <a href="/detections"{% if path.startswith("/detections") %} aria-current="page"{% endif %}>Detections</a>
```

`src/serve/templates/run_detail.html` — replace the disabled button (line 46):

```html
{%- if run.status in ('done', 'partial') %}
    <a id="detect-agent-use" class="button" href="/runs/{{ run.id }}/detect" title="Scans the frozen corpus through GitHub’s API on its own allowance and stores evidence per repo.">Detect agent use</a>
{%- else %}
    <button id="detect-agent-use" class="button" type="button" disabled title="Detection runs on searches that finished (done or partial).">Detect agent use</button>
{%- endif %}
```

replace the “Coming soon.” note (line 86) with:

```html
  <p id="detect-agent-use-note" class="muted">Detect agent use scans the frozen corpus through GitHub’s API on its own allowance and stores evidence per repo.{% if latest_detect %} Latest: <a href="/runs/{{ latest_detect.id }}">detection #{{ latest_detect.id }}</a> — {{ latest_detect.signals }} agent signal(s).{% endif %}</p>
```

`src/serve/corpora.py` — the list route builds `corpora` items; add `"last_detection": _last_detection(engine, item["source_run_id"])` when each item dict is assembled (both the list and the detail context), with a helper:

```python
def _last_detection(engine: Engine, source_run_id: int) -> dict | None:
    from serve.detect import latest_detect_for_run

    row = latest_detect_for_run(engine, source_run_id)
    if row is None:
        return None
    return {"id": row["id"], "status": row["status"]}
```

`corpora.html` — replace the “Last detection” cell (line 38):

```html
          <td>{% if item.last_detection %}<a href="/runs/{{ item.last_detection.id }}">#{{ item.last_detection.id }}</a> <span class="muted">{{ status_label(item.last_detection.status) }}</span>{% else %}<span class="muted" data-no-detection="true">Not yet</span>{% endif %}</td>
```

replace the Detect button (lines 42-43):

```html
              <a id="corpora-detect-{{ item.id }}" class="button" href="/runs/{{ item.source_run_id }}/detect" title="Scans the frozen corpus through GitHub’s API on its own allowance and stores evidence per repo.">Detect</a>
```

and the “Coming soon.” note (lines 59-60) becomes:

```html
  <p class="muted" id="corpora-detect-note">Detect agent use scans the frozen corpus through GitHub’s API on its own allowance and stores evidence per repo.</p>
```

`corpus_detail.html` — replace the disabled button (lines 26-27) with:

```html
    <a id="corpus-detect" class="button" href="/runs/{{ corpus.source_run_id }}/detect" title="Scans the frozen corpus through GitHub’s API on its own allowance and stores evidence per repo.">Detect agent use</a>
```

and the note (lines 37-38) with the same “Coming soon”-free copy.

`src/serve/runs.py`:

```python
_MEDIA_TYPES = {"json": "application/json", "csv": "text/csv", "detections": "text/csv"}
_BUNDLE_FILES = {"json": "bundle.json", "csv": "corpus.csv", "detections": "detections.csv"}
```

`export_bundle` gains, before the json/csv regeneration:

```python
    if format == "detections":
        if path.is_file():
            return _file_chunks(path), _MEDIA_TYPES[format]
        return _detections_chunks(engine, run_id), _MEDIA_TYPES[format]
```

and a regenerator next to `_csv_chunks`:

```python
def _detections_chunks(engine: Engine, run_id: int) -> Iterator[bytes]:
    header_buffer = io.StringIO()
    csv.writer(header_buffer).writerow(
        ["full_name", "repo_id", "agent", "channel", "evidence", "pack_version"]
    )
    yield header_buffer.getvalue().encode("utf-8")
    with engine.connect() as connection:
        rows = connection.execute(
            select(DetectionEvidence, RunItem.full_name)
            .join(RunItem, RunItem.repo_id == DetectionEvidence.repo_id)
            .where(DetectionEvidence.run_id == run_id, RunItem.run_id == run_id)
            .order_by(DetectionEvidence.repo_id, DetectionEvidence.agent, DetectionEvidence.channel)
        ).all()
    for evidence, full_name in rows:
        buffer = io.StringIO()
        csv.writer(buffer).writerow(
            [
                _csv_cell(full_name),
                _csv_cell(evidence.repo_id),
                _csv_cell(evidence.agent),
                _csv_cell(evidence.channel),
                _csv_cell(json.dumps(evidence.evidence, sort_keys=True)),
                _csv_cell(evidence.pack_version),
            ]
        )
        yield buffer.getvalue().encode("utf-8")
```

(import `DetectionEvidence` in `runs.py`). In `app.py`’s export route (:960), extend the whitelist to `("json", "csv", "detections")` and the hint string to `"format must be one of: json, csv, detections"`.

- [ ] **Step 4: Update the existing contract tests**

`tests/contract/test_run_detail.py:690` — replace the disabled-button assertion with:

```python
    assert 'href="/runs/' in body and "Detect agent use" in body and "Coming soon" not in body
```

`tests/contract/test_corpora.py:222-239` — replace the greyed/`DETECT_COPY` expectations with the wired versions: the corpora list and corpus detail now contain `href="/runs/{source}/detect"` and do not contain “Coming soon”.

- [ ] **Step 5: Golden updates**

`tests/golden/conftest.py`:

- Add to `GOLDEN_SEED_SQL`:

```python
    """
    INSERT INTO trace_packs (version, authors, files, branches, labels)
    VALUES ('golden-pack',
            '[{"pattern": "noreply@anthropic\\\\.com", "agent": "Claude Code"}]'::jsonb,
            '[{"pattern": "CLAUDE\\\\.md", "agent": "Claude Code"}]'::jsonb,
            '[{"pattern": "codex/", "agent": "Codex"}]'::jsonb,
            '[]'::jsonb)
    """,
    """
    INSERT INTO runs (id, filter_hash, filter_spec, api_version, status, kind, source_run_id,
                      result_summary, created_at, finished_at, fetched, inserted)
    VALUES (952, 'golden-detect',
            '{"version": 1, "kind": "detect", "source_run_id": 931, "pack_version": "golden-pack",
              "agents": null, "channels": ["file", "pr_metadata"], "limit": null,
              "windows": {"commits": 100, "prs": 100, "issues": 100}}'::jsonb,
            '2022-11-28', 'done', 'detect', 931,
            '{"repos_scanned": 1, "repos_with_signal": 1, "repos_unavailable": 0,
              "agents": {"Claude Code": 1, "Codex": 1}, "channels": {"file": 1, "pr_metadata": 1},
              "pack_version": "golden-pack", "agents_selected": "all",
              "windows": {"commits": 100, "prs": 100, "issues": 100},
              "commit_ratio": 1.0, "adoption_level": "pervasive",
              "first_signal_at": "2026-01-02T00:00:00Z", "partial_channels": {}}'::jsonb,
            '2026-01-02T00:06:00Z', '2026-01-02T00:07:00Z', 1, 1)
    """,
    """
    INSERT INTO detection_evidence (run_id, repo_id, agent, channel, evidence, pack_version)
    VALUES (952, 911, 'Claude Code', 'file', '{"path": "CLAUDE.md"}'::jsonb, 'golden-pack'),
           (952, 911, 'Codex', 'pr_metadata', '{"pr": 7, "commit": "a1", "propagated": true}'::jsonb, 'golden-pack')
    """,
```

- Add to `PATH_PARAMS`:

```python
    "/detections": {},
    "/runs/{run_id}/detect": {"run_id": RUN_A},
    "/runs/{run_id}/detect-estimate": {"run_id": RUN_A},
    "/partials/runs/{run_id}/detect-status": {"run_id": RUN_A},
```

- Add to `EXTRA_CASES`:

```python
    ("runs_detect", "/runs/952", {}),
    ("runs_detect_export", "/runs/952/export?format=detections", {}),
```

- Regenerate snapshots and re-pin OpenAPI:

```powershell
$env:UPDATE_GOLDEN='1'; $env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/golden -q
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/golden/test_openapi_pin.py -q   # prints the expected hash on failure
# write the printed hash into tests/golden/snapshots/openapi.sha256, then re-run
```

- [ ] **Step 6: Run the page + contract tests**

Run: `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest tests/contract/test_detect_pages.py tests/contract/test_run_detail.py tests/contract/test_corpora.py tests/golden -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/serve/pages.py src/serve/corpora.py src/serve/runs.py src/serve/app.py src/serve/templates/base.html src/serve/templates/run_detail.html src/serve/templates/corpora.html src/serve/templates/corpus_detail.html tests/contract/test_detect_pages.py tests/contract/test_run_detail.py tests/contract/test_corpora.py tests/golden/conftest.py tests/golden/snapshots
git commit -m "feat: detection console wiring, evidence export, and golden coverage"
```

---

## Task 11: Documentation, README, and full-suite verification

**Files:**
- Create: `docs/detection-tiers.md`
- Modify: `design/research.md` (D13), `README.md` (detection section :551-560, console routes :456-471), `docs/development-log.md`
- Test: full suite.

**Interfaces:**
- Consumes: everything above.
- Produces: the documented tier boundaries and a green full suite.

- [ ] **Step 1: Write `docs/detection-tiers.md`**

Content (mirror spec §10 + §14):

```markdown
# Detection tiers — what is knowable API-only

The detector replicates the Robbes et al. heuristics (MSR 2026 companion + “Agentic Much?” +
“Agentic Very Much?”). Every signal below is available at the tier named; a run never presents a
shallow tier as a census, and every window is recorded in the run spec and shown in the UI.

## 1. API-only, full

| Signal | Calls | Freshness |
|---|---|---|
| File heuristics (config / rules / guidance; 93 patterns) | tree + contents probes | live at detect time |
| `.gitignore`-hidden agent files | contents | live |
| Guidance-file content (weight, empty-file borderline) | contents (bounded) | live |
| PR head-branch heuristics (20) | shared PR call | live |
| PR label heuristics (4) | shared PR call | live |

## 2. API-only, windowed

| Signal | Window | Cannot tell you |
|---|---|---|
| Commit author/committer identities (79 patterns) | last 100 commits | older history; absence of a signature |
| Co-author trailers + `Generated by:` footers | last 100 commits | casing variants beyond the patterns |
| PR→commit propagation (Codex mechanism) | recent 100 PRs | which commits a human touched inside the PR; squash merges inherit the tag |
| PR metadata (author users, Codex body marker) | recent 100 PRs | closed PRs beyond the window; PR discussions beyond 50 comments |
| Issues/users (assignees, authors, PR commenters) | recent 100 issues | full issue history |
| Generic CI bots (exclusion) | last 100 commits | bots outside the window |
| Commit ratio + adoption level (Experimental/Limited/Consistent/Pervasive) | windowed | the true full-history ratio |
| Adoption date (`first_signal_at`) | windowed | first-ever adoption |

## 3. Clone required

Per-file first-added dates, change counts, line counts; commit size metrics (added/deleted lines,
files involved); diffstats; ground-truth content audit; full-history commit ratio and adoption date;
conventional-commit task classification (feat/fix/docs/...).

## 4. BigQuery required

Full windowed commit history beyond `first:100`; 2025+ PR bodies at scale.

## 5. Pointers

- Community heuristics repository (per-heuristic validity periods, sample trace datasets) — the pack
  versioning preserves validity metadata when present.
- Undetected activity (signing disabled, dotfiles repositories, manual commits, Pi/OpenCode
  unsigned) — detection is an undercount; stated in the UI and export metadata.
- False-positive baseline: ~0.5–1% legitimate FPs, ~3% borderline (two-annotator validation).
```

- [ ] **Step 2: Point `design/research.md` D13 at the doc**

In `design/research.md` D13 (around :89-97), add:

```markdown
- Tier boundary: `docs/detection-tiers.md` (what is knowable API-only vs clone/BigQuery).
```

- [ ] **Step 3: Update README + development log**

- README: replace the “Detection … greyed out” paragraph (:553) with the shipped behavior (entry points on finished searches and corpora, `/detections`, agent selection, eight channels, windowed labels); add `/detections`, `/runs/{id}/detect`, `/runs/{id}/detect-estimate`, `/partials/runs/{id}/detect-status` to the console route table; remove the “tables remain unbuilt” note (:560).
- `docs/development-log.md`: append a dated entry — migration `0016`, eight channels, agent selection, PR→commit propagation, windowed ratio, `detections.csv` export, redaction guarantee.

- [ ] **Step 4: Full-suite verification**

Run:

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m pytest -q --cov=src --cov-report=term-missing
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m ruff check src tests
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m black --check src tests
```

Expected: all green; coverage ≥ 93. If a coverage gap appears in `src/detect`, add focused unit tests for the uncovered branch (do not lower the floor).

- [ ] **Step 5: Live smoke (token-guarded, optional)**

If a token is available, run one detection over a small corpus (top-N 3) from the console and verify: status transitions, per-repo evidence, `detections.csv` export, and audit rows carrying `detect:<channel>` phases.

- [ ] **Step 6: Commit**

```bash
git add docs/detection-tiers.md design/research.md README.md docs/development-log.md
git commit -m "docs: detection tiers, README, and development log"
```

---

## Self-review notes (already applied)

- Every spec §1–§15 requirement maps to a task: data model (T1), packs (T2), attribution/scoping/propagation/noise/redaction (T3), eight channels (T4–T6), estimate (T7), orchestrator + executor + windowed metrics (T8), spec/routes/app/resume (T9), IA wiring + export + golden (T10), tiers doc + verification (T11).
- Interface names are consistent across tasks: `DetectOptions`, `DetectConfig`, `run_detection`, `load_frozen`, `parse_detect_spec`, `ChannelResult`, `Hit`, `detect_*`.
- The dead scaffolding names in `app.py` are satisfied: `detect.orchestrator.run_detection`, `detect.packs.load_frozen`, `serve.detect_spec.parse_detect_spec`.
- Test commands are Windows-PowerShell exact; fixtures use the central `clean_db`; golden steps include `PATH_PARAMS` and OpenAPI re-pin.

