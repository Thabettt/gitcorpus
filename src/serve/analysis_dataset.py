"""One immutable, eligibility-aware view of a frozen detection run.

The analysis previously repeated the same JSON and evidence predicates in many
queries.  This module loads the small per-repository state and the compact
distinct evidence-facet table once.  Every downstream estimand therefore uses
the same missingness, channel-completeness, owner, and agent-set definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

KNOWN_CHANNELS = frozenset(
    {
        "file",
        "author",
        "branch",
        "label",
        "bot",
        "commit_trailer",
        "pr_metadata",
        "issue",
        "content",
    }
)
#: ``Generic`` is a shared marker, never a scored agent.
GENERIC_AGENT = "Generic"
NON_BOT_CHANNELS = KNOWN_CHANNELS - {"bot"}
BEHAVIORAL_CHANNELS = frozenset({"author", "commit_trailer", "pr_metadata"})
HISTORY_CHANNELS = frozenset({"author", "commit_trailer"})
CHANNEL_FAMILIES = {
    "file": "structural",
    "content": "structural",
    "branch": "structural",
    "author": "commit",
    "commit_trailer": "commit",
    "pr_metadata": "collaboration",
    "label": "collaboration",
    "issue": "collaboration",
}


def _canonical_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(sorted({item for item in value if isinstance(item, str) and item.strip()}))


def _channels(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {
        str(channel): str(status)
        for channel, status in value.items()
        if channel in KNOWN_CHANNELS and isinstance(status, str)
    }


def _bounded_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    return numeric if 0.0 <= numeric <= 1.0 else None


def _optional_bool(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _optional_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


@dataclass(frozen=True)
class AnalysisRepo:
    repo_id: int | None
    owner_id: int | None
    owner_type: str | None
    country_iso: str
    language: str
    stars: int | None
    commit_count: int | None
    repo_created_at: datetime | None
    detection_present: bool
    readable: bool
    complete_channels: bool
    channels: dict[str, str]
    agents: tuple[str, ...]
    evidence_channels: frozenset[str]
    evidence_agents: tuple[str, ...]
    evidence_families: frozenset[str]
    structural_signal: bool
    file_observed: bool
    commit_ratio: float | None
    history_coverage: float | None
    history_complete: bool | None
    first_signal_at: str | None
    history_metadata: bool = False
    generic_markers: tuple[str, ...] = ()

    @property
    def broad_signal(self) -> bool:
        return bool(self.evidence_channels)

    @property
    def behavioral_signal(self) -> bool:
        return bool(self.evidence_channels & BEHAVIORAL_CHANNELS)

    @property
    def corroborated_signal(self) -> bool:
        return len(self.evidence_families) >= 2

    @property
    def strict_signal(self) -> bool:
        return self.behavioral_signal or self.corroborated_signal

    @property
    def structural_only(self) -> bool:
        return self.structural_signal and not self.behavioral_signal


@dataclass(frozen=True)
class AnalysisDataset:
    run_id: int
    selected_channels: tuple[str, ...]
    channel_selection_source: str
    rows: tuple[AnalysisRepo, ...]

    @property
    def file_applicable(self) -> bool:
        return "file" in self.selected_channels

    @property
    def history_applicable(self) -> bool:
        return bool(set(self.selected_channels) & HISTORY_CHANNELS)

    @property
    def history_recorded(self) -> bool:
        """Whether this run's detection documents record history coverage at all.

        Runs produced before the history-coverage fields existed have no key, so a
        0% rate would describe missing metadata rather than zero coverage.
        """
        return any(row.history_metadata for row in self.rows)

    @property
    def strict_applicable(self) -> bool:
        selected = set(self.selected_channels) & NON_BOT_CHANNELS
        families = {
            CHANNEL_FAMILIES[channel] for channel in selected if channel in CHANNEL_FAMILIES
        }
        return bool(selected & BEHAVIORAL_CHANNELS) or len(families) >= 2


def _run_channels(engine: Engine, run_id: int) -> tuple[tuple[str, ...], str]:
    with engine.connect() as connection:
        raw = connection.execute(
            text("SELECT filter_spec->'channels' FROM runs WHERE id = :run"),
            {"run": run_id},
        ).scalar()
    channels = _canonical_strings(raw)
    if channels:
        return tuple(channel for channel in channels if channel in KNOWN_CHANNELS), "run_spec"
    return (), "legacy_inferred"


def _facet_maps(engine: Engine, run_id: int) -> tuple[dict[int, set[str]], dict[int, set[str]]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT repo_id, agent, channel FROM detection_repo_filters"
                " WHERE run_id = :run ORDER BY repo_id, agent, channel"
            ),
            {"run": run_id},
        ).mappings()
        channels: dict[int, set[str]] = {}
        agents: dict[int, set[str]] = {}
        saw_facets = False
        for row in rows:
            saw_facets = True
            repo_id = int(row["repo_id"])
            channel = str(row["channel"])
            agent = str(row["agent"])
            if channel != "bot" and agent != GENERIC_AGENT:
                channels.setdefault(repo_id, set()).add(channel)
                agents.setdefault(repo_id, set()).add(agent)

        # A pre-0018 or hand-built fixture can have evidence without compact
        # facets. Fall back only when the run has no facets at all; normal large
        # runs never scan the multi-million-row evidence table here.
        if (
            not saw_facets
            and connection.execute(
                text("SELECT EXISTS (SELECT 1 FROM detection_evidence WHERE run_id = :run)"),
                {"run": run_id},
            ).scalar()
        ):
            fallback = connection.execute(
                text(
                    "SELECT DISTINCT repo_id, agent, channel FROM detection_evidence"
                    " WHERE run_id = :run AND channel <> 'bot'"
                ),
                {"run": run_id},
            ).mappings()
            for row in fallback:
                repo_id = int(row["repo_id"])
                agent = str(row["agent"])
                if agent == GENERIC_AGENT:
                    continue
                channels.setdefault(repo_id, set()).add(str(row["channel"]))
                agents.setdefault(repo_id, set()).add(agent)
    return channels, agents


def _structural_repos(engine: Engine, run_id: int) -> set[int]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT DISTINCT repo_id FROM detection_evidence"
                " WHERE run_id = :run AND channel = 'file'"
                " AND COALESCE(evidence->>'source', 'tree') <> 'gitignore'"
            ),
            {"run": run_id},
        )
        return {int(row[0]) for row in rows}


def load_analysis_dataset(engine: Engine, run_id: int) -> AnalysisDataset:
    """Load one consistent analysis view for ``run_id``.

    Detection metadata is used first, followed only by the frozen source-run
    snapshot. Mutable repository metadata is consulted solely to map the frozen
    repository id to its owner.
    """

    selected_channels, selection_source = _run_channels(engine, run_id)
    facet_channels, facet_agents = _facet_maps(engine, run_id)
    structural_repos = _structural_repos(engine, run_id)
    with engine.connect() as connection:
        raw_rows = connection.execute(
            text(
                "SELECT i.repo_id, r.owner_id, o.type AS owner_type,"
                " COALESCE(i.country_iso, o.country_iso, '??') AS country_iso,"
                " COALESCE(NULLIF(btrim(i.language), ''),"
                "          NULLIF(btrim(s.language), ''), 'Unknown') AS language,"
                " COALESCE(i.stargazers, s.stargazers) AS stars,"
                " COALESCE(i.commit_count, s.commit_count,"
                "   CASE WHEN jsonb_typeof(s.virtuals->'commit_count') = 'number'"
                "     AND (s.virtuals->>'commit_count') ~ '^[0-9]+$'"
                "     AND (s.virtuals->>'commit_count')::numeric <= 2147483647"
                "   THEN (s.virtuals->>'commit_count')::integer ELSE NULL END) AS commit_count,"
                " COALESCE(i.repo_created_at, s.repo_created_at) AS repo_created_at,"
                " i.detection"
                " FROM run_items i"
                " JOIN runs dr ON dr.id = i.run_id"
                " LEFT JOIN run_items s"
                "   ON s.run_id = dr.source_run_id AND s.repo_id = i.repo_id"
                " LEFT JOIN repos r ON r.id = i.repo_id"
                " LEFT JOIN owners o ON o.id = r.owner_id"
                " WHERE i.run_id = :run ORDER BY i.id"
            ),
            {"run": run_id},
        ).mappings()
        rows: list[AnalysisRepo] = []
        inferred_channels: set[str] = set()
        pending: list[dict[str, Any]] = []
        for raw in raw_rows:
            document = raw["detection"] if isinstance(raw["detection"], dict) else None
            channel_statuses = _channels(document.get("channels") if document else None)
            inferred_channels.update(channel_statuses)
            pending.append({**dict(raw), "document": document, "channels": channel_statuses})

    if not selected_channels:
        selected_channels = tuple(sorted(inferred_channels))

    for raw in pending:
        document = raw["document"]
        channel_statuses = raw["channels"]
        unavailable = bool(document.get("unavailable")) if document else False
        readable = document is not None and not unavailable
        if selection_source == "run_spec":
            complete = (
                readable
                and bool(selected_channels)
                and all(channel_statuses.get(channel) == "ok" for channel in selected_channels)
            )
        else:
            complete = (
                readable
                and bool(channel_statuses)
                and all(status == "ok" for status in channel_statuses.values())
            )
        repo_id = int(raw["repo_id"]) if raw["repo_id"] is not None else None
        evidence_channels = frozenset(facet_channels.get(repo_id, set()))
        families = frozenset(
            CHANNEL_FAMILIES[channel]
            for channel in evidence_channels
            if channel in CHANNEL_FAMILIES
        )
        rows.append(
            AnalysisRepo(
                repo_id=repo_id,
                owner_id=int(raw["owner_id"]) if raw["owner_id"] is not None else None,
                owner_type=str(raw["owner_type"]) if raw["owner_type"] is not None else None,
                country_iso=str(raw["country_iso"]),
                language=str(raw["language"]),
                stars=_optional_nonnegative_int(raw["stars"]),
                commit_count=_optional_nonnegative_int(raw["commit_count"]),
                repo_created_at=raw["repo_created_at"],
                detection_present=document is not None,
                readable=readable,
                complete_channels=complete,
                channels=channel_statuses,
                agents=tuple(
                    agent
                    for agent in _canonical_strings(document.get("agents") if document else None)
                    if agent != GENERIC_AGENT
                ),
                generic_markers=_canonical_strings(
                    document.get("generic_markers") if document else None
                ),
                evidence_channels=evidence_channels,
                evidence_agents=tuple(sorted(facet_agents.get(repo_id, set()))),
                evidence_families=families,
                structural_signal=repo_id in structural_repos,
                file_observed=(
                    readable
                    and "file" in selected_channels
                    and channel_statuses.get("file") == "ok"
                ),
                commit_ratio=_bounded_float(document.get("commit_ratio") if document else None),
                history_coverage=_bounded_float(
                    document.get("history_coverage") if document else None
                ),
                history_complete=_optional_bool(
                    document.get("history_complete") if document else None
                ),
                first_signal_at=(
                    str(document["first_signal_at"])
                    if document and document.get("first_signal_at")
                    else None
                ),
                history_metadata=bool(document) and "history_coverage" in document,
            )
        )

    return AnalysisDataset(
        run_id=run_id,
        selected_channels=selected_channels,
        channel_selection_source=selection_source,
        rows=tuple(rows),
    )
