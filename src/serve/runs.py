from __future__ import annotations

import csv
import io
import json
import os
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable, Iterator, Mapping
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine, Row
from sqlalchemy.engine.row import RowMapping
from starlette.responses import StreamingResponse

from enrich.cloner import (
    PROGRESS_NAME,
    CloneEstimate,
    CloneMode,
    CloneProgress,
    GitRunner,
    clone_repos,
    estimate_clone,
    estimate_clone_from_totals,
    free_disk_mb,
)
from lib.deadlines import clone_timeout_seconds
from serve.countries import country_name, income_group
from serve.executor import _CSV_HEADER, EVIDENCE_CSV_HEADER, _csv_cell, evidence_csv_row
from store.models import Owner, Repo, RunItem, Runs

_MEDIA_TYPES = {
    "json": "application/json",
    "csv": "text/csv",
    "detections": "text/csv",
    "detections-json": "application/json",
    "comparison": "text/csv",
}
_BUNDLE_FILES = {"json": "bundle.json", "csv": "corpus.csv", "detections": "detections.csv"}

INTEGRATED_CSV_HEADER = [
    "full_name",
    "owner_login",
    "stack",
    "primary_language",
    "stars",
    "commits",
    "authored_commits",
    "commit_ratio",
    "country",
    "country_iso",
    "geo_confidence",
    "income_group",
    "agentic_present",
    "commit_adoption",
    "adoption_level",
    "agents_found",
    "current_agents",
    "configured_agents",
    "primary_agent",
    "agent_count",
    "current_agent_count",
    "configured_agent_count",
    "channels_count",
    "channels_fired",
    "evidence_count",
    "evidence_semantics",
    "has_file_evidence",
    "has_commit_trailer_evidence",
    "has_pr_metadata_evidence",
    "has_author_evidence",
    "has_branch_evidence",
    "has_agents_md",
    "review_participation_count",
    "orchestration_only_count",
    "legacy_markers_count",
    "recovery_checkpoint_count",
    "ambiguous_lineage_count",
    "historical_only_count",
    "authored_commits_by_agent",
    "first_signal_at",
    "created_at",
    "oldest_scanned_commit_at",
    "last_signal_at",
    "repo_created_at",
    "pushed_at",
    "first_signal_month",
    "first_signal_days_ago",
    "repo_age_days",
    "age_at_adoption_days",
    "days_since_push",
    "is_active_last_90d",
    "history_coverage",
    "history_complete",
    "is_archived",
    "license_spdx",
]

_AGENTIC_LEVELS = {"experimental", "limited", "consistent", "pervasive"}


def _days_between(a_iso: str | None, b: datetime | str | None) -> str | int:
    def parse(x):
        if not x:
            return None
        if isinstance(x, datetime):
            return x
        try:
            return datetime.fromisoformat(str(x).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    da = parse(a_iso)
    db = parse(b)
    if not da or not db:
        return ""
    if da.tzinfo is None:
        da = da.replace(tzinfo=UTC)
    if db.tzinfo is None:
        db = db.replace(tzinfo=UTC)
    return int((db - da).total_seconds() // 86400)


def _pipe_join(values) -> str:
    if not values:
        return ""
    return "|".join(sorted({str(v) for v in values if v}))


DETECT_REPO_CSV_HEADER = [
    "repo_id",
    "full_name",
    "stargazers",
    "repo_created_at",
    "commit_count",
    "pushed_at",
    "archived",
    "language",
    "license_spdx",
    "country_iso",
    "geo_confidence",
    "country",
    "has_signal",
    "unavailable",
    "failure_class",
    "adoption_level",
    "commit_ratio",
    "history_window_commits",
    "history_eligible_commits",
    "total_commits",
    "history_coverage",
    "history_complete",
    "first_signal_at",
    "agents",
    "ever_observed",
    "currently_configured",
    "current_activity",
    "historical_activity",
    "authored_commits",
    "review_participation",
    "orchestration_only",
    "legacy_markers",
    "recovery_checkpoint",
    "ambiguous_lineage",
    "evidence_rows",
    "signal_rows",
    "bot_rows",
    "file_rows",
    "content_rows",
    "author_rows",
    "branch_rows",
    "label_rows",
    "commit_trailer_rows",
    "pr_metadata_rows",
    "issue_rows",
    "hidden_ref_rows",
]

EVIDENCE_BATCH_ROWS = 1000
DETECT_REPO_BATCH_ROWS = 1000

_UNFINISHED_STATUSES = ("queued", "running")


class RunNotReadyError(Exception):
    def __init__(self, run_id: int, status: str) -> None:
        super().__init__(f"run {run_id} is {status}; exports unlock when it finishes")
        self.run_id = run_id
        self.status = status


def run_bundle_dir(runs_root: str, filter_hash: str, run_id: int) -> Path:
    return Path(runs_root) / filter_hash / str(run_id)


def bundle_file(runs_root: str, filter_hash: str, run_id: int, format: str) -> Path:
    return run_bundle_dir(runs_root, filter_hash, run_id) / _BUNDLE_FILES[format]


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if not isinstance(value, datetime):
        return str(value)
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def latest_run_for_hash(
    engine: Engine, filter_hash: str, *, statuses: tuple[str, ...] | None = None
) -> Row | None:
    statement = select(Runs).where(Runs.filter_hash == filter_hash)
    if statuses is not None:
        statement = statement.where(Runs.status.in_(statuses))
    with engine.connect() as connection:
        return (
            connection.execute(statement.order_by(Runs.created_at.desc(), Runs.id.desc()).limit(1))
            .mappings()
            .one_or_none()
        )


def _row_for_run(engine: Engine, run_id: int) -> RowMapping:
    with engine.connect() as connection:
        row = connection.execute(select(Runs).where(Runs.id == run_id)).mappings().one_or_none()
    if row is None:
        raise KeyError(run_id)
    return row


_SNAPSHOT_COLUMNS = (
    ("pushed_at", RunItem.pushed_at, Repo.pushed_at),
    ("archived", RunItem.archived, Repo.archived),
    ("language", RunItem.language, Repo.language),
    ("license_spdx", RunItem.license_spdx, Repo.license_spdx),
    ("country_iso", RunItem.country_iso, Owner.country_iso),
    ("geo_confidence", RunItem.geo_confidence, Owner.geo_confidence),
)


def _item_rows(
    engine: Engine, run_id: int, *, backfill_metadata: bool = False
) -> list[Mapping[str, object]]:
    # New detection runs carry complete source snapshots. The live fallback is
    # retained only for legacy runs created before those fields were copied.
    columns = [
        RunItem.repo_id,
        RunItem.full_name,
        RunItem.stargazers,
        RunItem.repo_created_at,
        RunItem.commit_count,
    ]
    for name, item_column, live_column in _SNAPSHOT_COLUMNS:
        column = func.coalesce(item_column, live_column) if backfill_metadata else item_column
        columns.append(column.label(name))
    columns.extend((RunItem.virtuals, RunItem.detection))
    statement = select(*columns).select_from(RunItem)
    if backfill_metadata:
        statement = statement.outerjoin(Repo, Repo.id == RunItem.repo_id).outerjoin(
            Owner, Owner.id == Repo.owner_id
        )
    statement = statement.where(RunItem.run_id == run_id).order_by(
        RunItem.stargazers.desc().nullslast(), RunItem.repo_id
    )
    with engine.connect() as connection:
        rows = list(connection.execute(statement).mappings())
    if not backfill_metadata:
        return rows
    resolved = _resolved_negative_ids(engine, run_id)
    return [
        {
            **dict(row),
            "repo_id": _resolved_repo_id(row["repo_id"], row["full_name"], resolved),
        }
        for row in rows
    ]


def _snapshot(row: Mapping[str, object], *, include_detection: bool = False) -> dict:
    snapshot = {
        "repo_id": row["repo_id"],
        "full_name": row["full_name"],
        "stargazers": row["stargazers"],
        "repo_created_at": _iso(row["repo_created_at"]),
        "commit_count": row["commit_count"],
        "pushed_at": _iso(row["pushed_at"]),
        "archived": row["archived"],
        "language": row["language"],
        "license_spdx": row["license_spdx"],
        "country_iso": row["country_iso"],
        "geo_confidence": row["geo_confidence"],
        "country": country_name(row["country_iso"]),
        "virtuals": dict(row["virtuals"] or {}),
    }
    if include_detection:
        snapshot["detection"] = row["detection"]
    return snapshot


def _file_chunks(path: Path, chunk_size: int = 65536) -> Iterator[bytes]:
    with path.open("rb") as handle:
        while True:
            block = handle.read(chunk_size)
            if not block:
                return
            yield block


def _json_chunks(
    engine: Engine, run_row: RowMapping, run_id: int, *, include_detection: bool = False
) -> Iterator[bytes]:
    header = {
        "filter": run_row["filter_spec"],
        "filter_hash": run_row["filter_hash"],
        "run_id": run_id,
        "ran_at": _iso(run_row["finished_at"] or run_row["created_at"]),
        "api_version": run_row["api_version"],
        "total_count": run_row["total_count"],
        "fetched": run_row["fetched"],
        "incomplete": run_row["status"] == "partial",
        "regenerated": True,
    }
    yield b"{"
    for key, value in header.items():
        yield (
            json.dumps(key).encode() + b": " + json.dumps(value, ensure_ascii=False).encode() + b","
        )
    yield b'"items": ['
    first = True
    for row in _item_rows(engine, run_id, backfill_metadata=include_detection):
        chunk = json.dumps(_snapshot(row, include_detection=include_detection), ensure_ascii=False)
        yield chunk.encode() if first else b"," + chunk.encode()
        first = False
    yield b'], "field_stats": {}}'


def _csv_chunks(engine: Engine, run_id: int) -> Iterator[bytes]:
    header_buffer = io.StringIO()
    header_buffer.write("\ufeff")
    csv.writer(header_buffer).writerow(_CSV_HEADER)
    yield header_buffer.getvalue().encode("utf-8")
    for row in _item_rows(engine, run_id):
        buffer = io.StringIO()
        csv.writer(buffer).writerow(
            [
                _csv_cell(row["repo_id"]),
                _csv_cell(row["full_name"]),
                _csv_cell(row["stargazers"]),
                _csv_cell(_iso(row["pushed_at"])),
                _csv_cell(row["archived"]),
                _csv_cell(row["language"]),
                _csv_cell(row["license_spdx"]),
                _csv_cell(row["country_iso"]),
                _csv_cell(row["geo_confidence"]),
                _csv_cell(country_name(row["country_iso"])),
            ]
        )
        yield buffer.getvalue().encode("utf-8")


_EVIDENCE_STREAM_SQL = text(
    "SELECT i.full_name, e.repo_id, e.agent, e.channel, e.evidence, e.detected_at,"
    " COALESCE(i.country_iso, o.country_iso),"
    " e.family_id, e.family_name, e.observed_as, e.variant, e.rule_id, e.rule_lifecycle,"
    " e.evidence_semantics, e.forge, e.role, e.confidence, e.provenance_ref,"
    " e.is_current, e.is_historical, e.metric_eligibility, e.explanatory_note"
    " FROM detection_evidence e"
    " LEFT JOIN run_items i ON i.run_id = e.run_id AND i.repo_id = e.repo_id"
    " LEFT JOIN repos r ON r.id = e.repo_id"
    " LEFT JOIN owners o ON o.id = r.owner_id"
    " WHERE e.run_id = :run"
    " ORDER BY e.repo_id, e.agent, e.channel, e.id"
)


def _resolved_negative_ids(engine: Engine, run_id: int) -> dict[str, int]:
    """Map import placeholder ids (negative) to the real repo id when known.

    CSV imports create repos with negative placeholder ids; later runs that
    hydrated the same repository recorded its real GitHub id in their run
    items. Resolve by full name for the placeholders of this run only;
    placeholders with no known real id are left alone.
    """
    statement = text(
        "SELECT neg.full_name, max(pos.repo_id)"
        " FROM ("
        "   SELECT DISTINCT full_name FROM run_items"
        "   WHERE run_id = :run AND repo_id < 0"
        " ) neg"
        " JOIN run_items pos ON pos.full_name = neg.full_name AND pos.repo_id > 0"
        " GROUP BY neg.full_name"
    )
    with engine.connect() as connection:
        return {str(row[0]): int(row[1]) for row in connection.execute(statement, {"run": run_id})}


def _resolved_repo_id(repo_id: object, full_name: object, resolved: Mapping[str, int]) -> object:
    if not isinstance(repo_id, int) or repo_id >= 0:
        return repo_id
    real = resolved.get(str(full_name)) if full_name is not None else None
    return real if real is not None else repo_id


_DETECT_REPO_STREAM_SQL = text(
    "SELECT i.repo_id, i.full_name, i.stargazers,"
    " COALESCE(i.repo_created_at, r.created_at), i.commit_count,"
    " COALESCE(i.pushed_at, r.pushed_at), COALESCE(i.archived, r.archived),"
    " COALESCE(i.language, r.language), COALESCE(i.license_spdx, r.license_spdx),"
    " COALESCE(i.country_iso, o.country_iso), COALESCE(i.geo_confidence, o.geo_confidence),"
    " i.detection,"
    " COALESCE(c.total_rows, 0), COALESCE(c.signal_rows, 0), COALESCE(c.bot_rows, 0),"
    " COALESCE(c.file_rows, 0), COALESCE(c.content_rows, 0),"
    " COALESCE(c.author_rows, 0), COALESCE(c.branch_rows, 0),"
    " COALESCE(c.label_rows, 0), COALESCE(c.commit_trailer_rows, 0),"
    " COALESCE(c.pr_metadata_rows, 0), COALESCE(c.issue_rows, 0),"
    " COALESCE(c.hidden_ref_rows, 0)"
    " FROM run_items i"
    " LEFT JOIN repos r ON r.id = i.repo_id"
    " LEFT JOIN owners o ON o.id = r.owner_id"
    " LEFT JOIN ("
    "   SELECT repo_id,"
    "     count(*) AS total_rows,"
    "     count(*) FILTER (WHERE channel <> 'bot' AND"
    "       COALESCE((metric_eligibility->>'repository_presence')::boolean, true))"
    "       AS signal_rows,"
    "     count(*) FILTER (WHERE channel = 'bot') AS bot_rows,"
    "     count(*) FILTER (WHERE channel = 'file') AS file_rows,"
    "     count(*) FILTER (WHERE channel = 'content') AS content_rows,"
    "     count(*) FILTER (WHERE channel = 'author') AS author_rows,"
    "     count(*) FILTER (WHERE channel = 'branch') AS branch_rows,"
    "     count(*) FILTER (WHERE channel = 'label') AS label_rows,"
    "     count(*) FILTER (WHERE channel = 'commit_trailer') AS commit_trailer_rows,"
    "     count(*) FILTER (WHERE channel = 'pr_metadata') AS pr_metadata_rows,"
    "     count(*) FILTER (WHERE channel = 'issue') AS issue_rows"
    "    ,count(*) FILTER (WHERE channel = 'hidden_ref') AS hidden_ref_rows"
    "   FROM detection_evidence WHERE run_id = :run GROUP BY repo_id"
    " ) c ON c.repo_id = i.repo_id"
    " WHERE i.run_id = :run"
    " ORDER BY i.stargazers DESC NULLS LAST, i.repo_id"
)


_INTEGRATED_REPO_STREAM_SQL = text(
    "SELECT i.repo_id, i.full_name, i.stargazers,"
    " COALESCE(i.repo_created_at, r.created_at),"
    " i.commit_count,"
    " COALESCE(i.pushed_at, r.pushed_at),"
    " COALESCE(i.archived, r.archived),"
    " COALESCE(i.language, r.language),"
    " COALESCE(i.license_spdx, r.license_spdx),"
    " COALESCE(i.country_iso, o.country_iso),"
    " COALESCE(i.geo_confidence, o.geo_confidence),"
    " i.detection,"
    " COALESCE(c.total_rows, 0),"
    " COALESCE(c.file_rows, 0),"
    " COALESCE(c.author_rows, 0),"
    " COALESCE(c.branch_rows, 0),"
    " COALESCE(c.label_rows, 0),"
    " COALESCE(c.commit_trailer_rows, 0),"
    " COALESCE(c.pr_metadata_rows, 0),"
    " COALESCE(c.issue_rows, 0),"
    " COALESCE(c.bot_rows, 0),"
    " c.semantics,"
    " COALESCE(c.has_agents_md, false),"
    " pa.primary_agent,"
    " aba.authored_by_agent"
    " FROM run_items i"
    " LEFT JOIN repos r ON r.id = i.repo_id"
    " LEFT JOIN owners o ON o.id = r.owner_id"
    " LEFT JOIN ("
    "   SELECT repo_id,"
    "     count(*) AS total_rows,"
    "     count(*) FILTER (WHERE channel = 'file') AS file_rows,"
    "     count(*) FILTER (WHERE channel = 'author') AS author_rows,"
    "     count(*) FILTER (WHERE channel = 'branch') AS branch_rows,"
    "     count(*) FILTER (WHERE channel = 'label') AS label_rows,"
    "     count(*) FILTER (WHERE channel = 'commit_trailer') AS commit_trailer_rows,"
    "     count(*) FILTER (WHERE channel = 'pr_metadata') AS pr_metadata_rows,"
    "     count(*) FILTER (WHERE channel = 'issue') AS issue_rows,"
    "     count(*) FILTER (WHERE channel = 'bot') AS bot_rows,"
    "     string_agg(DISTINCT NULLIF(evidence_semantics, ''), '|') AS semantics,"
    "     bool_or(channel = 'file' AND COALESCE(evidence->>'path','')"
    "       LIKE '%%AGENTS.md') AS has_agents_md"
    "   FROM detection_evidence WHERE run_id = :run GROUP BY repo_id"
    " ) c ON c.repo_id = i.repo_id"
    " LEFT JOIN ("
    "   SELECT DISTINCT ON (repo_id) repo_id, family_name AS primary_agent"
    "   FROM ("
    "     SELECT repo_id, family_name, count(*) AS cnt"
    "     FROM detection_evidence"
    "     WHERE run_id = :run"
    "       AND COALESCE(family_name,'') NOT IN ('', 'Generic', 'Rejected/noise')"
    "     GROUP BY repo_id, family_name"
    "   ) z"
    "   ORDER BY repo_id, cnt DESC, family_name"
    " ) pa ON pa.repo_id = i.repo_id"
    " LEFT JOIN ("
    "   SELECT repo_id, jsonb_object_agg(family_name, cnt) AS authored_by_agent"
    "   FROM ("
    "     SELECT repo_id, family_name, count(*) AS cnt"
    "     FROM detection_evidence"
    "     WHERE run_id = :run AND channel = 'commit_trailer'"
    "       AND COALESCE(family_name,'') NOT IN ('', 'Generic')"
    "     GROUP BY repo_id, family_name"
    "   ) z GROUP BY repo_id"
    " ) aba ON aba.repo_id = i.repo_id"
    " WHERE i.run_id = :run"
    " ORDER BY i.stargazers DESC NULLS LAST, i.repo_id"
)


def _detections_chunks(
    engine: Engine, run_id: int, *, batch_rows: int = EVIDENCE_BATCH_ROWS
) -> Iterator[bytes]:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    csv.writer(buffer).writerow(EVIDENCE_CSV_HEADER)
    yield buffer.getvalue().encode("utf-8")
    resolved = _resolved_negative_ids(engine, run_id)
    with engine.connect() as connection:
        result = connection.execution_options(stream_results=True).execute(
            _EVIDENCE_STREAM_SQL, {"run": run_id}
        )
        for partition in result.partitions(max(1, batch_rows)):
            buffer.seek(0)
            buffer.truncate(0)
            writer = csv.writer(buffer)
            for row in partition:
                writer.writerow(
                    evidence_csv_row(
                        {
                            "full_name": row[0],
                            "repo_id": _resolved_repo_id(row[1], row[0], resolved),
                            "agent": row[2],
                            "channel": row[3],
                            "evidence": row[4],
                            "detected_at": row[5],
                            "country_iso": row[6],
                            "family_id": row[7],
                            "family_name": row[8],
                            "observed_as": row[9],
                            "variant": row[10],
                            "rule_id": row[11],
                            "rule_lifecycle": row[12],
                            "evidence_semantics": row[13],
                            "forge": row[14],
                            "role": row[15],
                            "confidence": row[16],
                            "provenance_ref": row[17],
                            "is_current": row[18],
                            "is_historical": row[19],
                            "metric_eligibility": row[20],
                            "explanatory_note": row[21],
                        }
                    )
                )
            yield buffer.getvalue().encode("utf-8")


def _detection_json_object(row, repo_id: object) -> dict:
    return {
        "repo_id": repo_id,
        "full_name": row[0],
        "agent": row[2],
        "channel": row[3],
        "detected_at": _iso(row[5]),
        "evidence": row[4],
        "country_iso": row[6],
        "country": country_name(row[6]),
        "family_id": row[7],
        "family_name": row[8],
        "observed_as": row[9],
        "variant": row[10],
        "rule_id": row[11],
        "rule_lifecycle": row[12],
        "evidence_semantics": row[13],
        "forge": row[14],
        "role": row[15],
        "confidence": row[16],
        "provenance_ref": row[17],
        "is_current": row[18],
        "is_historical": row[19],
        "metric_eligibility": row[20],
        "explanatory_note": row[21],
    }


def _detections_json_chunks(
    engine: Engine, run_id: int, *, batch_rows: int = EVIDENCE_BATCH_ROWS
) -> Iterator[bytes]:
    yield b"["
    resolved = _resolved_negative_ids(engine, run_id)
    with engine.connect() as connection:
        result = connection.execution_options(stream_results=True).execute(
            _EVIDENCE_STREAM_SQL, {"run": run_id}
        )
        first = True
        for partition in result.partitions(max(1, batch_rows)):
            objects = [
                json.dumps(
                    _detection_json_object(row, _resolved_repo_id(row[1], row[0], resolved)),
                    ensure_ascii=False,
                )
                for row in partition
            ]
            if not objects:
                continue
            joined = (b"" if first else b",") + b",".join(part.encode("utf-8") for part in objects)
            first = False
            yield joined
    yield b"]"


def _detect_repo_cells(row, resolved_ids: Mapping[str, int]) -> list[str]:
    document = row[11] if isinstance(row[11], dict) else {}
    agents = document.get("agents") or []
    cells = [
        _csv_cell(_resolved_repo_id(row[0], row[1], resolved_ids)),
        _csv_cell(row[1]),
        _csv_cell(row[2]),
        _csv_cell(_iso(row[3])),
        _csv_cell(row[4]),
        _csv_cell(_iso(row[5])),
        _csv_cell(row[6]),
        _csv_cell(row[7]),
        _csv_cell(row[8]),
        _csv_cell(row[9]),
        _csv_cell(row[10]),
        _csv_cell(country_name(row[9])),
        _csv_cell(bool(agents)),
        _csv_cell(bool(document.get("unavailable", False))),
        _csv_cell(document.get("failure_class")),
        _csv_cell(document.get("adoption_level")),
        _csv_cell(document.get("commit_ratio")),
        _csv_cell(document.get("history_window_commits")),
        _csv_cell(document.get("history_eligible_commits")),
        _csv_cell(document.get("total_commits")),
        _csv_cell(document.get("history_coverage")),
        _csv_cell(document.get("history_complete")),
        _csv_cell(document.get("first_signal_at")),
        _csv_cell("|".join(str(agent) for agent in agents)),
        _csv_cell("|".join(str(value) for value in document.get("ever_observed") or [])),
        _csv_cell("|".join(str(value) for value in document.get("currently_configured") or [])),
        _csv_cell("|".join(str(value) for value in document.get("current_activity") or [])),
        _csv_cell("|".join(str(value) for value in document.get("historical_activity") or [])),
        _csv_cell(document.get("authored_commits")),
        _csv_cell("|".join(str(value) for value in document.get("review_participation") or [])),
        _csv_cell("|".join(str(value) for value in document.get("orchestration_only") or [])),
        _csv_cell("|".join(str(value) for value in document.get("legacy_markers") or [])),
        _csv_cell("|".join(str(value) for value in document.get("recovery_checkpoint") or [])),
        _csv_cell("|".join(str(value) for value in document.get("ambiguous_lineage") or [])),
    ]
    cells.extend(_csv_cell(value) for value in row[12:24])
    return cells


def _detect_repo_chunks(
    engine: Engine, run_id: int, *, batch_rows: int = DETECT_REPO_BATCH_ROWS
) -> Iterator[bytes]:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    csv.writer(buffer).writerow(DETECT_REPO_CSV_HEADER)
    yield buffer.getvalue().encode("utf-8")
    resolved = _resolved_negative_ids(engine, run_id)
    with engine.connect() as connection:
        result = connection.execution_options(stream_results=True).execute(
            _DETECT_REPO_STREAM_SQL, {"run": run_id}
        )
        for partition in result.partitions(max(1, batch_rows)):
            buffer.seek(0)
            buffer.truncate(0)
            writer = csv.writer(buffer)
            for row in partition:
                writer.writerow(_detect_repo_cells(row, resolved))
            yield buffer.getvalue().encode("utf-8")


def _comparison_chunks(
    engine: Engine, run_id: int, *, stack: str = "", batch_rows: int = DETECT_REPO_BATCH_ROWS
) -> Iterator[bytes]:
    buffer = io.StringIO()
    buffer.write("\ufeff")
    csv.writer(buffer).writerow(INTEGRATED_CSV_HEADER)
    yield buffer.getvalue().encode("utf-8")
    now = datetime.now(UTC)
    stack_label = (stack or "").strip()
    with engine.connect() as connection:
        result = connection.execution_options(stream_results=True).execute(
            _INTEGRATED_REPO_STREAM_SQL, {"run": run_id}
        )
        for partition in result.partitions(max(1, batch_rows)):
            buffer.seek(0)
            buffer.truncate(0)
            writer = csv.writer(buffer)
            for row in partition:
                writer.writerow(_integrated_row_cells(row, stack_label, now))
            yield buffer.getvalue().encode("utf-8")


def _integrated_row_cells(row, stack_label: str, now: datetime) -> list:
    full_name = str(row[1] or "").strip()
    stargazers = row[2]
    repo_created_at = _iso(row[3])
    pushed_at = _iso(row[5])
    archived = bool(row[6]) if row[6] is not None else False
    language = row[7]
    license_spdx = row[8]
    country_iso = (row[9] or "").strip().upper()
    geo_conf = (row[10] or "").strip()
    document = row[11] if isinstance(row[11], dict) else {}

    total_rows = int(row[12] or 0)
    file_rows = int(row[13] or 0)
    author_rows = int(row[14] or 0)
    branch_rows = int(row[15] or 0)
    label_rows = int(row[16] or 0)
    commit_trailer_rows = int(row[17] or 0)
    pr_metadata_rows = int(row[18] or 0)
    issue_rows = int(row[19] or 0)
    bot_rows = int(row[20] or 0)
    semantics_raw = row[21] or ""
    has_agents_md = bool(row[22])
    primary_agent = row[23] or ""
    authored_by_agent = row[24] if isinstance(row[24], dict) else {}

    adoption_level = (document.get("adoption_level") or "none").strip().lower() or "none"
    commit_adoption = "agentic" if adoption_level in _AGENTIC_LEVELS else "none"
    agentic_present = "true" if bool(document.get("agents") or []) else "false"

    ever_observed = list(document.get("agents") or [])
    currently_configured = list(document.get("currently_configured") or [])
    current_activity = list(document.get("current_activity") or [])
    historical_activity = list(document.get("historical_activity") or [])

    review_cnt = len(document.get("review_participation") or [])
    orches_cnt = len(document.get("orchestration_only") or [])
    legacy_cnt = len(document.get("legacy_markers") or [])
    recov_cnt = len(document.get("recovery_checkpoint") or [])
    amb_cnt = len(document.get("ambiguous_lineage") or [])
    cur_set = set(current_activity)
    hist_only = sum(1 for a in historical_activity if a not in cur_set)

    country = country_name(country_iso) if country_iso else ""
    inc_grp = income_group(country_iso) if country_iso else ""

    channels = {
        "file": file_rows,
        "author": author_rows,
        "branch": branch_rows,
        "label": label_rows,
        "commit_trailer": commit_trailer_rows,
        "pr_metadata": pr_metadata_rows,
        "issue": issue_rows,
        "bot": bot_rows,
    }
    channels_fired = [k for k, v in channels.items() if v > 0]

    first_signal = _iso(document.get("first_signal_at")) or ""
    history_coverage = document.get("history_coverage")
    history_complete = document.get("history_complete")
    commit_ratio = document.get("commit_ratio")
    authored_commits = document.get("authored_commits")
    commits = row[4] if row[4] is not None else document.get("total_commits")

    age_days = _days_between(repo_created_at, now) if repo_created_at else ""
    age_at_adoption_days = (
        _days_between(repo_created_at, first_signal) if (repo_created_at and first_signal) else ""
    )
    days_since_push = _days_between(pushed_at, now) if pushed_at else ""
    is_active_last_90d = "1" if isinstance(days_since_push, int) and days_since_push <= 90 else "0"

    owner_login = full_name.split("/", 1)[0].lower() if "/" in full_name else full_name.lower()
    aba_json = json.dumps(authored_by_agent, separators=(",", ":")) if authored_by_agent else ""

    return [
        _csv_cell(full_name),
        _csv_cell(owner_login),
        _csv_cell(stack_label or language),
        _csv_cell(language),
        _csv_cell(stargazers),
        _csv_cell(commits),
        _csv_cell(authored_commits),
        _csv_cell(commit_ratio),
        _csv_cell(country),
        _csv_cell(country_iso),
        _csv_cell(geo_conf),
        _csv_cell(inc_grp),
        _csv_cell(agentic_present),
        _csv_cell(commit_adoption),
        _csv_cell(adoption_level),
        _csv_cell(_pipe_join(ever_observed)),
        _csv_cell(_pipe_join(current_activity)),
        _csv_cell(_pipe_join(currently_configured)),
        _csv_cell(primary_agent),
        _csv_cell(len(ever_observed)),
        _csv_cell(len(current_activity)),
        _csv_cell(len(currently_configured)),
        _csv_cell(len(channels_fired)),
        _csv_cell(_pipe_join(channels_fired)),
        _csv_cell(total_rows),
        _csv_cell(semantics_raw),
        _csv_cell("true" if file_rows > 0 else "false"),
        _csv_cell("true" if commit_trailer_rows > 0 else "false"),
        _csv_cell("true" if pr_metadata_rows > 0 else "false"),
        _csv_cell("true" if author_rows > 0 else "false"),
        _csv_cell("true" if branch_rows > 0 else "false"),
        _csv_cell("true" if has_agents_md else "false"),
        _csv_cell(review_cnt),
        _csv_cell(orches_cnt),
        _csv_cell(legacy_cnt),
        _csv_cell(recov_cnt),
        _csv_cell(amb_cnt),
        _csv_cell(hist_only),
        _csv_cell(aba_json),
        _csv_cell(first_signal),
        _csv_cell(first_signal),
        _csv_cell(""),
        _csv_cell(""),
        _csv_cell(repo_created_at or ""),
        _csv_cell(pushed_at or ""),
        _csv_cell(first_signal[:7] if first_signal else ""),
        _csv_cell(_days_between(first_signal, now) if first_signal else ""),
        _csv_cell(age_days),
        _csv_cell(age_at_adoption_days),
        _csv_cell(days_since_push),
        _csv_cell(is_active_last_90d),
        _csv_cell(history_coverage if history_coverage is not None else ""),
        _csv_cell("true" if history_complete else "false"),
        _csv_cell("true" if archived else "false"),
        _csv_cell(license_spdx or ""),
    ]


def export_bundle(
    engine: Engine, run_id: int, *, format: str, stack: str = "", runs_root: str = "runs"
) -> tuple[Iterator[bytes], str]:
    if format not in _MEDIA_TYPES:
        raise ValueError(
            "format",
            "format must be one of: json, csv, detections, detections-json, comparison",
        )
    run_row = _row_for_run(engine, run_id)
    if run_row["kind"] == "detect":
        if run_row["status"] in _UNFINISHED_STATUSES:
            raise RunNotReadyError(int(run_id), str(run_row["status"]))
        if format == "detections":
            return _detections_chunks(engine, run_id), _MEDIA_TYPES[format]
        if format == "detections-json":
            return _detections_json_chunks(engine, run_id), _MEDIA_TYPES[format]
        if format == "comparison":
            return _comparison_chunks(engine, run_id, stack=stack), _MEDIA_TYPES[format]
        if format == "json":
            return (
                _json_chunks(engine, run_row, run_id, include_detection=True),
                _MEDIA_TYPES[format],
            )
        return _detect_repo_chunks(engine, run_id), _MEDIA_TYPES[format]
    if format in _BUNDLE_FILES:
        path = bundle_file(runs_root, run_row["filter_hash"], run_id, format)
        if path.is_file():
            return _file_chunks(path), _MEDIA_TYPES[format]
    if format == "detections":
        return _detections_chunks(engine, run_id), _MEDIA_TYPES[format]
    if format == "detections-json":
        return _detections_json_chunks(engine, run_id), _MEDIA_TYPES[format]
    if format == "json":
        return _json_chunks(engine, run_row, run_id), _MEDIA_TYPES[format]
    return _csv_chunks(engine, run_id), _MEDIA_TYPES[format]


_FILENAME_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _pack_segment(run_row: Row) -> str:
    """`-<pack version>` for detect export filenames, sanitized, when known.

    The evidence exports no longer repeat run_id/pack_version on every row;
    the filename identifies both instead.
    """
    spec = run_row["filter_spec"]
    pack = spec.get("pack_version") if isinstance(spec, dict) else None
    if not pack:
        return ""
    clean = _FILENAME_UNSAFE.sub("-", str(pack)).strip("-._")
    return f"-{clean[:40]}" if clean else ""


def export_run(
    engine: Engine, run_id: int, *, format: str = "json", stack: str = "", runs_root: str = "runs"
) -> StreamingResponse:
    if format not in _MEDIA_TYPES:
        raise ValueError(
            "format",
            "format must be one of: json, csv, detections, detections-json, comparison",
        )
    run_row = _row_for_run(engine, run_id)
    detect = run_row["kind"] == "detect"
    regenerated = detect or format not in _BUNDLE_FILES
    if not regenerated:
        regenerated = not bundle_file(runs_root, run_row["filter_hash"], run_id, format).is_file()
    chunks, media_type = export_bundle(
        engine, run_id, format=format, stack=stack, runs_root=runs_root
    )
    if detect:
        stem = f"gitcorpus-detect-{run_id}{_pack_segment(run_row)}"
        filename = {
            "detections": f"{stem}-evidence.csv",
            "detections-json": f"{stem}-evidence.json",
            "csv": f"{stem}-repos.csv",
            "json": f"{stem}.json",
            "comparison": f"{stem}-comparison.csv",
        }.get(format, f"{stem}.csv")
    else:
        filename = f"gitcorpus-{run_row['filter_hash']}-{run_id}.{format}"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    if regenerated:
        headers["X-Gitcorpus-Regenerated"] = "true"
    return StreamingResponse(chunks, media_type=media_type, headers=headers)


class CloneRegistry:
    def __init__(
        self,
        *,
        max_entries: int = 100,
        ttl_seconds: float = 3600.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._entries: OrderedDict[int, CloneProgress] = OrderedDict()
        self._touched: dict[int, float] = {}
        self._cancels: dict[int, threading.Event] = {}
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._clock = clock

    def _evict_locked(self, now: float) -> None:
        for run_id in list(self._entries):
            progress = self._entries[run_id]
            if progress.status == "running":
                continue
            if now - self._touched.get(run_id, now) >= self._ttl:
                del self._entries[run_id]
                self._touched.pop(run_id, None)
        while len(self._entries) > self._max_entries:
            evicted = False
            for run_id in list(self._entries):
                if self._entries[run_id].status != "running":
                    del self._entries[run_id]
                    self._touched.pop(run_id, None)
                    evicted = True
                    break
            if not evicted:
                break

    def get(self, run_id: int) -> CloneProgress | None:
        with self._lock:
            now = self._clock()
            self._evict_locked(now)
            progress = self._entries.get(run_id)
            if progress is None:
                return None
            self._entries.move_to_end(run_id)
            self._touched[run_id] = now
            return progress

    def set(self, run_id: int, progress: CloneProgress) -> None:
        with self._lock:
            now = self._clock()
            self._entries[run_id] = progress
            self._entries.move_to_end(run_id)
            self._touched[run_id] = now
            self._evict_locked(now)

    def claim(
        self, run_id: int, factory: Callable[[], CloneProgress]
    ) -> tuple[CloneProgress, bool]:
        with self._lock:
            now = self._clock()
            self._evict_locked(now)
            existing = self._entries.get(run_id)
            if existing is not None and existing.status == "running":
                self._entries.move_to_end(run_id)
                self._touched[run_id] = now
                return existing, False
            progress = factory()
            self._entries[run_id] = progress
            self._entries.move_to_end(run_id)
            self._touched[run_id] = now
            self._evict_locked(now)
            return progress, True

    def set_cancel(self, run_id: int, event: threading.Event) -> None:
        with self._lock:
            self._cancels[run_id] = event

    def clear_cancel(self, run_id: int) -> None:
        with self._lock:
            self._cancels.pop(run_id, None)

    def cancel(self, run_id: int) -> bool:
        with self._lock:
            event = self._cancels.get(run_id)
        if event is None:
            return False
        event.set()
        return True


_EMIT_INTERVAL_SECONDS = 0.25


class _PersistedProgress(CloneProgress):
    def __init__(
        self,
        path: Path,
        *,
        now: Callable[[], float] = time.monotonic,
        emit_interval: float = _EMIT_INTERVAL_SECONDS,
        **values: object,
    ) -> None:
        super().__init__(**values)
        self._path = path
        self._now = now
        self._emit_interval = emit_interval
        self._last_emit = float("-inf")

    def emit(self, *, force: bool = False) -> None:
        moment = self._now()
        if not force and moment - self._last_emit < self._emit_interval:
            return
        self._last_emit = moment
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temp = self._path.with_suffix(".tmp")
        temp.write_text(json.dumps(asdict(self), ensure_ascii=False), encoding="utf-8")
        for attempt in range(5):
            try:
                os.replace(temp, self._path)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02)


def _count_run_items(engine: Engine, run_id: int) -> int:
    with engine.connect() as connection:
        count = connection.scalar(
            select(func.count()).select_from(RunItem).where(RunItem.run_id == run_id)
        )
    return int(count or 0)


def _run_totals(engine: Engine, run_id: int) -> tuple[int, int]:
    with engine.connect() as connection:
        count, size_kb = connection.execute(
            select(func.count(), func.coalesce(func.sum(Repo.size_kb), 0))
            .select_from(RunItem)
            .outerjoin(Repo, Repo.id == RunItem.repo_id)
            .where(RunItem.run_id == run_id)
        ).one()
    return int(count or 0), int(size_kb or 0)


def clone_estimate_for_run(
    engine: Engine,
    run_id: int,
    *,
    limit: int | None,
    mode: CloneMode,
    dest_root: str = "clones",
    low_disk_threshold_mb: float = 2048.0,
    disk_free_mb: float | None = None,
) -> CloneEstimate:
    if disk_free_mb is None:
        disk_free_mb = free_disk_mb(dest_root)
    if limit is None:
        repos, size_kb = _run_totals(engine, run_id)
        _row_for_run(engine, run_id)  # preserve KeyError semantics
        return estimate_clone_from_totals(
            repos,
            size_kb,
            mode=mode,
            disk_free_mb=disk_free_mb,
            low_disk_threshold_mb=low_disk_threshold_mb,
        )
    if limit < 0:
        raise ValueError("limit", "limit must be >= 0")
    return estimate_clone(
        engine,
        run_id,
        limit=limit,
        mode=mode,
        disk_free_mb=disk_free_mb,
        low_disk_threshold_mb=low_disk_threshold_mb,
    )


def progress_payload(progress: CloneProgress) -> dict:
    return asdict(progress)


def _progress_int(value: object, default: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return default
    return value


def _progress_errors(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def read_clone_progress(
    engine: Engine,
    run_id: int,
    *,
    registry: CloneRegistry,
    runs_root: str = "runs",
) -> CloneProgress:
    tracked = registry.get(run_id)
    if tracked is not None:
        return tracked
    row = _row_for_run(engine, run_id)
    path = run_bundle_dir(runs_root, row["filter_hash"], run_id) / PROGRESS_NAME
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            data = None
        if isinstance(data, dict):
            errors = _progress_errors(data.get("errors"))
            status = data.get("status")
            current = data.get("current")
            return CloneProgress(
                status=status if isinstance(status, str) else "done",
                total=_progress_int(data.get("total")),
                completed=_progress_int(data.get("completed")),
                failed=_progress_int(data.get("failed")),
                current=current if isinstance(current, str) else None,
                errors=errors,
                error_count=_progress_int(data.get("error_count"), default=len(errors)),
            )
    return CloneProgress(status="done", total=0, completed=0, failed=0)


def cancel_clone(
    engine: Engine,
    run_id: int,
    *,
    registry: CloneRegistry,
    runs_root: str = "runs",
) -> CloneProgress:
    progress = read_clone_progress(engine, run_id, registry=registry, runs_root=runs_root)
    if progress.status == "running":
        registry.cancel(run_id)
    return progress


def start_clone(
    engine: Engine,
    run_id: int,
    *,
    limit: int,
    mode: CloneMode,
    registry: CloneRegistry,
    runs_root: str = "runs",
    dest_root: str = "clones",
    git_runner: GitRunner | None = None,
    clone_timeout: float | None = None,
    cancel_event: threading.Event | None = None,
) -> CloneProgress:
    row = _row_for_run(engine, run_id)
    bundle_dir = run_bundle_dir(runs_root, row["filter_hash"], run_id)

    def create_progress() -> CloneProgress:
        return _PersistedProgress(
            bundle_dir / PROGRESS_NAME,
            status="running",
            total=0,
            completed=0,
            failed=0,
        )

    progress, claimed = registry.claim(run_id, create_progress)
    if not claimed:
        return progress
    progress.total = min(limit, _count_run_items(engine, run_id)) if limit > 0 else 0
    if limit <= 0:
        progress.status = "done"
        progress.emit(force=True)
        return progress
    timeout = clone_timeout if clone_timeout is not None else clone_timeout_seconds()
    event = cancel_event if cancel_event is not None else threading.Event()
    registry.set_cancel(run_id, event)
    worker = threading.Thread(
        target=_clone_worker,
        args=(
            engine,
            run_id,
            limit,
            mode,
            dest_root,
            git_runner,
            progress,
            registry,
            timeout,
            event,
        ),
        daemon=True,
    )
    worker.start()
    return progress


def _clone_worker(
    engine: Engine,
    run_id: int,
    limit: int,
    mode: CloneMode,
    dest_root: str,
    git_runner: GitRunner | None,
    progress: CloneProgress,
    registry: CloneRegistry,
    clone_timeout: float,
    cancel_event: threading.Event,
) -> None:
    try:
        clone_repos(
            engine,
            run_id,
            limit=limit,
            mode=mode,
            dest_root=dest_root,
            git_runner=git_runner,
            progress=progress,
            clone_timeout=clone_timeout,
            cancel_event=cancel_event,
        )
    except Exception as exc:
        progress.status = "failed"
        progress.current = None
        progress.error_count += 1
        progress.errors.append(f"{type(exc).__name__}: {exc}"[:300])
    finally:
        registry.clear_cancel(run_id)
        progress.emit(force=True)
