from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path

from sqlalchemy import insert, select
from sqlalchemy.engine import Engine

from store.models import TracePack

CHANNEL_FILES = ("authors.csv", "files.csv", "branches.csv", "labels.csv", "bots.csv")
DEFAULT_GENERIC_WEIGHTS = {"AGENTS.md": 0.3}
DEFAULT_EXCLUSIONS = ("CONVENTIONS.md",)
GENERIC_AGENT = "Generic"
GENERIC_AGENT_URL = "https://agents.md"
SCHEMA_V2_SOURCE = "catalogue.json"

LIFECYCLE_STATUSES = frozenset(
    {
        "current",
        "deprecated",
        "legacy",
        "retired",
        "compatibility",
        "optional",
        "recovery-only",
        "anomalous",
        "unsafe/rejected",
    }
)
EVIDENCE_SEMANTICS = frozenset(
    {
        "configuration",
        "activity",
        "authorship",
        "generated_code",
        "review_participation",
        "orchestration",
        "historical_lineage",
        "recovery_checkpoint",
        "ambiguous_lineage",
        "rejected_noise",
    }
)
FAMILY_CATEGORIES = frozenset(
    {
        "active",
        "legacy-only",
        "watch",
        "adjacent",
        "excluded",
        "pseudo",
        "negative-control",
        "ambiguous",
    }
)
RULE_CHANNELS = frozenset(
    {
        "file",
        "workflow",
        "author",
        "committer",
        "co_author",
        "custom_trailer",
        "branch",
        "hidden_ref",
        "label",
        "bot",
        "pr_author",
        "pr_reviewer",
        "pr_commenter",
        "issue_author",
        "issue_assignee",
        "issue_commenter",
        "merge_request",
        "service_account",
    }
)
IDENTITY_CHANNELS = frozenset({"author", "committer", "co_author"})

# Detection channels: the per-repo heuristics a run can select. This is the
# universe across every pack; each pack exposes only the subset it can feed
# (``Pack.channels()``), so the console and the run spec never offer a channel
# the chosen pack cannot produce evidence for.
DETECTION_CHANNELS = (
    "file",
    "author",
    "branch",
    "hidden_ref",
    "label",
    "bot",
    "commit_trailer",
    "pr_metadata",
    "issue",
)
# The schema-v1 channel contract (packs 2026-10-14 and 2026-10-19). The flat
# matcher applies the author list to commit identities, co-author trailers,
# PR authors, and issue participants; branches/labels also feed PR metadata.
V1_CHANNELS = (
    "file",
    "author",
    "branch",
    "label",
    "bot",
    "commit_trailer",
    "pr_metadata",
    "issue",
)
# Schema-v2 rule channels behind each detection channel. A detection channel is
# offered for a v2 pack only when at least one enabled positive rule feeds it
# (``bot`` also counts its rejection rules: they classify CI/release noise and
# keep it out of the commit-ratio denominator).
V2_CHANNEL_SOURCES: Mapping[str, frozenset[str]] = {
    "file": frozenset({"file", "workflow"}),
    "author": frozenset({"author", "committer"}),
    "branch": frozenset({"branch"}),
    "hidden_ref": frozenset({"hidden_ref"}),
    "label": frozenset({"label"}),
    "bot": frozenset({"bot"}),
    "commit_trailer": frozenset({"co_author", "custom_trailer"}),
    "pr_metadata": frozenset(
        {"pr_author", "pr_reviewer", "pr_commenter", "merge_request", "service_account"}
    ),
    "issue": frozenset({"issue_author", "issue_assignee", "issue_commenter", "service_account"}),
}
# Channels a pack supports but that start unchecked because they cost extra
# requests per repository.
OPT_IN_CHANNELS = frozenset({"hidden_ref"})


class PackConflict(ValueError):
    pass


@dataclass(frozen=True)
class RuleSemantics:
    evidence: str = "activity"
    layer: str = "executor"
    role: str | None = None
    counts_as_repository_presence: bool = True
    counts_as_current_presence: bool = True
    counts_as_activity: bool = True
    counts_as_authorship: bool = False
    counts_as_generated_code: bool = False
    counts_in_current_ratio: bool = False
    counts_as_historical_attribution: bool = False

    def metric_eligibility(self) -> dict[str, bool]:
        return {
            "repository_presence": self.counts_as_repository_presence,
            "current_presence": self.counts_as_current_presence,
            "activity": self.counts_as_activity,
            "authorship": self.counts_as_authorship,
            "generated_code": self.counts_as_generated_code,
            "current_commit_ratio": self.counts_in_current_ratio,
            "historical_attribution": self.counts_as_historical_attribution,
        }


@dataclass(frozen=True)
class Family:
    id: str
    name: str
    url: str = ""
    category: str = "active"
    status: str = "current"
    kind: str = "executor"
    aliases: tuple[str, ...] = ()
    predecessors: tuple[str, ...] = ()
    successors: tuple[str, ...] = ()
    variants: tuple[str, ...] = ()
    rollup_family: str | None = None
    cohort: str | None = None
    matcher_generation: str | None = None
    note: str | None = None

    @property
    def active(self) -> bool:
        return self.category == "active"


@dataclass(frozen=True)
class Pattern:
    """One lifecycle-aware rule.

    ``pattern`` and ``agent`` remain the first two fields so every v1 caller and
    frozen pack keeps loading unchanged. Schema-v2 rules fill the remaining
    fields and use ``match`` for predicates that are richer than one regex.
    """

    pattern: str
    agent: str
    id: str = ""
    family_id: str = ""
    family_name: str = ""
    channel: str = ""
    surface: str = ""
    forge: str = "any"
    observed_as: str | None = None
    variant: str | None = None
    aliases: tuple[str, ...] = ()
    predecessors: tuple[str, ...] = ()
    successors: tuple[str, ...] = ()
    rollup_family: str | None = None
    lifecycle: str = "current"
    valid_from: str | None = None
    valid_until: str | None = None
    validity_note: str | None = None
    default_state: str = "default-on"
    evidence_strength: str = "strong"
    collision_risk: str = "low"
    provenance: Mapping[str, object] = field(default_factory=dict)
    semantics: RuleSemantics = field(default_factory=RuleSemantics)
    match: Mapping[str, object] = field(default_factory=dict)
    roles: tuple[str, ...] = ()
    enabled: bool = True
    disposition: str = "positive"
    note: str | None = None

    @property
    def canonical_family_id(self) -> str:
        return self.rollup_family or self.family_id

    @property
    def display_name(self) -> str:
        return self.family_name or self.agent


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
    schema_version: int = 1
    families: tuple[Family, ...] = ()
    rules: tuple[Pattern, ...] = ()
    rejections: tuple[Pattern, ...] = ()
    catalogue: Mapping[str, object] = field(default_factory=dict)
    content_byte_limit: int = 131_072
    content_candidate_limit: int = 64

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "generic_weights", dict(self.generic_weights or DEFAULT_GENERIC_WEIGHTS)
        )
        object.__setattr__(self, "exclusions", frozenset(self.exclusions or DEFAULT_EXCLUSIONS))
        object.__setattr__(self, "catalogue", dict(self.catalogue or {}))
        if self.schema_version >= 2 and self.rules:
            object.__setattr__(
                self,
                "authors",
                tuple(rule for rule in self.rules if rule.channel in IDENTITY_CHANNELS),
            )
            object.__setattr__(
                self,
                "files",
                tuple(rule for rule in self.rules if rule.channel in {"file", "workflow"}),
            )
            object.__setattr__(
                self, "branches", tuple(rule for rule in self.rules if rule.channel == "branch")
            )
            object.__setattr__(
                self, "labels", tuple(rule for rule in self.rules if rule.channel == "label")
            )
            object.__setattr__(
                self, "bots", tuple(rule for rule in self.rules if rule.channel == "bot")
            )

    def roster(self) -> tuple[str, ...]:
        """Every agent name this pack can attribute evidence to.

        This is exactly the set a run may select: selecting the whole roster is
        equivalent to selecting nothing (scan for everything). For schema v2 it
        is every family owning at least one enabled positive rule, so verified
        legacy-only families stay selectable and are never silently dropped by
        an explicit "select all".
        """
        if self.schema_version >= 2:
            owned = {rule.display_name for rule in self.rules if self._positive(rule)}
            return tuple(sorted((name for name in owned if name), key=str.casefold))
        names = {
            pattern.agent for pattern in (*self.authors, *self.files, *self.branches, *self.labels)
        }
        names.add(GENERIC_AGENT)
        return tuple(sorted(names, key=str.casefold))

    def roster_categories(self) -> dict[str, str]:
        """Catalogue category per roster name (``active`` for schema v1)."""
        if self.schema_version < 2:
            return {name: "active" for name in self.roster()}
        by_name = {family.name: family.category for family in self.families}
        return {name: by_name.get(name, "active") for name in self.roster()}

    def channels(self) -> tuple[str, ...]:
        """The detection channels this pack can produce evidence for, in order."""
        if self.schema_version < 2:
            return V1_CHANNELS
        positive = {rule.channel for rule in self.rules if self._positive(rule)}
        noise = {rule.channel for rule in (*self.rules, *self.rejections) if rule.channel == "bot"}
        used = positive | noise
        return tuple(
            channel
            for channel in DETECTION_CHANNELS
            if V2_CHANNEL_SOURCES.get(channel, frozenset()) & used
        )

    def default_channels(self) -> tuple[str, ...]:
        return tuple(channel for channel in self.channels() if channel not in OPT_IN_CHANNELS)

    @staticmethod
    def _positive(rule: Pattern) -> bool:
        return (
            rule.enabled and rule.disposition == "positive" and rule.lifecycle != "unsafe/rejected"
        )

    def rules_for(self, *channels: str, include_rejections: bool = False) -> tuple[Pattern, ...]:
        if self.schema_version < 2:
            legacy = {
                "author": self.authors,
                "committer": self.authors,
                "co_author": self.authors,
                "file": self.files,
                "workflow": self.files,
                "branch": self.branches,
                "label": self.labels,
                "bot": self.bots,
            }
            items: list[Pattern] = []
            for channel in channels:
                items.extend(legacy.get(channel, ()))
            unique: list[Pattern] = []
            seen: set[tuple[str, str]] = set()
            for item in items:
                key = (item.pattern, item.agent)
                if key not in seen:
                    seen.add(key)
                    unique.append(item)
            return tuple(unique)
        wanted = set(channels)
        items = [rule for rule in self.rules if rule.enabled and rule.channel in wanted]
        if include_rejections:
            items.extend(
                rule for rule in self.rejections if rule.enabled and rule.channel in wanted
            )
        return tuple(items)

    def family(self, family_id: str) -> Family | None:
        return next((family for family in self.families if family.id == family_id), None)

    def hidden_ref_namespaces(self) -> tuple[str, ...]:
        namespaces: set[str] = set()
        for rule in self.rules_for("hidden_ref"):
            raw = str(rule.match.get("regex") or rule.pattern)
            match = re.match(r"^\^?refs/([A-Za-z0-9._-]+)", raw)
            if match is not None:
                namespaces.add(f"refs/{match.group(1)}/")
        return tuple(sorted(namespaces))

    @property
    def requires_comment_bodies(self) -> bool:
        return any(
            rule.match.get("body") or rule.match.get("text")
            for rule in self.rules
            if rule.channel in {"pr_commenter", "issue_commenter", "pr_reviewer"}
        )


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


def _tuple_strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(str(item) for item in value)


def _semantics_from_document(raw: object) -> RuleSemantics:
    doc = raw if isinstance(raw, Mapping) else {}
    return RuleSemantics(
        evidence=str(doc.get("evidence") or "activity"),
        layer=str(doc.get("layer") or "executor"),
        role=str(doc["role"]) if doc.get("role") is not None else None,
        counts_as_repository_presence=bool(doc.get("counts_as_repository_presence", True)),
        counts_as_current_presence=bool(doc.get("counts_as_current_presence", True)),
        counts_as_activity=bool(doc.get("counts_as_activity", True)),
        counts_as_authorship=bool(doc.get("counts_as_authorship", False)),
        counts_as_generated_code=bool(doc.get("counts_as_generated_code", False)),
        counts_in_current_ratio=bool(
            doc.get("counts_in_current_ratio", doc.get("counts_in_commit_ratio", False))
        ),
        counts_as_historical_attribution=bool(doc.get("counts_as_historical_attribution", False)),
    )


def _semantics_document(semantics: RuleSemantics) -> dict[str, object]:
    return {
        "evidence": semantics.evidence,
        "layer": semantics.layer,
        "role": semantics.role,
        "counts_as_repository_presence": semantics.counts_as_repository_presence,
        "counts_as_current_presence": semantics.counts_as_current_presence,
        "counts_as_activity": semantics.counts_as_activity,
        "counts_as_authorship": semantics.counts_as_authorship,
        "counts_as_generated_code": semantics.counts_as_generated_code,
        "counts_in_current_ratio": semantics.counts_in_current_ratio,
        "counts_as_historical_attribution": semantics.counts_as_historical_attribution,
    }


def _family_from_document(raw: Mapping[str, object]) -> Family:
    return Family(
        id=str(raw["id"]),
        name=str(raw["name"]),
        url=str(raw.get("url") or ""),
        category=str(raw.get("category") or "active"),
        status=str(raw.get("status") or "current"),
        kind=str(raw.get("kind") or "executor"),
        aliases=_tuple_strings(raw.get("aliases")),
        predecessors=_tuple_strings(raw.get("predecessors")),
        successors=_tuple_strings(raw.get("successors")),
        variants=_tuple_strings(raw.get("variants")),
        rollup_family=(str(raw["rollup_family"]) if raw.get("rollup_family") is not None else None),
        cohort=str(raw["cohort"]) if raw.get("cohort") is not None else None,
        matcher_generation=(
            str(raw["matcher_generation"]) if raw.get("matcher_generation") is not None else None
        ),
        note=str(raw["note"]) if raw.get("note") is not None else None,
    )


def _family_document(family: Family) -> dict[str, object]:
    return {
        "id": family.id,
        "name": family.name,
        "url": family.url,
        "category": family.category,
        "status": family.status,
        "kind": family.kind,
        "aliases": list(family.aliases),
        "predecessors": list(family.predecessors),
        "successors": list(family.successors),
        "variants": list(family.variants),
        "rollup_family": family.rollup_family,
        "cohort": family.cohort,
        "matcher_generation": family.matcher_generation,
        "note": family.note,
    }


def _rule_from_document(raw: Mapping[str, object]) -> Pattern:
    confidence = raw.get("confidence") if isinstance(raw.get("confidence"), Mapping) else {}
    lifecycle = raw.get("lifecycle") if isinstance(raw.get("lifecycle"), Mapping) else {}
    lineage = raw.get("lineage") if isinstance(raw.get("lineage"), Mapping) else {}
    match = raw.get("match") if isinstance(raw.get("match"), Mapping) else {}
    regex = str(match.get("regex") or raw.get("pattern") or "")
    family_name = str(raw.get("family_name") or raw.get("agent") or "")
    return Pattern(
        pattern=regex,
        agent=family_name,
        id=str(raw.get("id") or ""),
        family_id=str(raw.get("family_id") or raw.get("family") or ""),
        family_name=family_name,
        channel=str(raw.get("channel") or ""),
        surface=str(raw.get("surface") or ""),
        forge=str(raw.get("forge") or "any"),
        observed_as=(str(raw["observed_as"]) if raw.get("observed_as") is not None else None),
        variant=str(raw["variant"]) if raw.get("variant") is not None else None,
        aliases=_tuple_strings(lineage.get("aliases", raw.get("aliases"))),
        predecessors=_tuple_strings(lineage.get("predecessors", raw.get("predecessors"))),
        successors=_tuple_strings(lineage.get("successors", raw.get("successors"))),
        rollup_family=(
            str(lineage.get("rollup_family") or raw.get("rollup_family"))
            if lineage.get("rollup_family") is not None or raw.get("rollup_family") is not None
            else None
        ),
        lifecycle=str(lifecycle.get("status") or raw.get("lifecycle") or "current"),
        valid_from=(
            str(lifecycle["valid_from"]) if lifecycle.get("valid_from") is not None else None
        ),
        valid_until=(
            str(lifecycle["valid_until"]) if lifecycle.get("valid_until") is not None else None
        ),
        validity_note=(
            str(lifecycle["uncertainty"]) if lifecycle.get("uncertainty") is not None else None
        ),
        default_state=str(raw.get("default_state") or "default-on"),
        evidence_strength=str(confidence.get("class") or raw.get("evidence_strength") or "strong"),
        collision_risk=str(confidence.get("collision_risk") or raw.get("collision_risk") or "low"),
        provenance=(
            dict(raw.get("provenance") or {}) if isinstance(raw.get("provenance"), Mapping) else {}
        ),
        semantics=_semantics_from_document(raw.get("semantics")),
        match=dict(match),
        roles=_tuple_strings(raw.get("roles")),
        enabled=bool(raw.get("enabled", True)),
        disposition=str(raw.get("disposition") or "positive"),
        note=str(raw["note"]) if raw.get("note") is not None else None,
    )


def _rule_document(rule: Pattern) -> dict[str, object]:
    match = dict(rule.match)
    if not match and rule.pattern:
        match["regex"] = rule.pattern
    return {
        "id": rule.id,
        "family_id": rule.family_id or None,
        "family_name": rule.family_name or rule.agent or None,
        "channel": rule.channel,
        "surface": rule.surface,
        "forge": rule.forge,
        "observed_as": rule.observed_as,
        "variant": rule.variant,
        "match": match,
        "lineage": {
            "aliases": list(rule.aliases),
            "predecessors": list(rule.predecessors),
            "successors": list(rule.successors),
            "rollup_family": rule.rollup_family,
        },
        "lifecycle": {
            "status": rule.lifecycle,
            "valid_from": rule.valid_from,
            "valid_until": rule.valid_until,
            "uncertainty": rule.validity_note,
        },
        "default_state": rule.default_state,
        "confidence": {
            "class": rule.evidence_strength,
            "collision_risk": rule.collision_risk,
        },
        "provenance": dict(rule.provenance),
        "semantics": _semantics_document(rule.semantics),
        "roles": list(rule.roles),
        "enabled": rule.enabled,
        "disposition": rule.disposition,
        "note": rule.note,
    }


def _build_v1_pack(src: Path, *, version: str) -> Pack:
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


def _build_v2_pack(src: Path, *, version: str) -> Pack:
    document = json.loads((src / SCHEMA_V2_SOURCE).read_text(encoding="utf-8"))
    if not isinstance(document, Mapping):
        raise ValueError(f"{SCHEMA_V2_SOURCE} must contain an object")
    source_version = str(document.get("version") or version)
    if source_version != version:
        raise ValueError(
            f"source pack version {source_version!r} does not match requested version {version!r}"
        )
    families = tuple(
        _family_from_document(item)
        for item in document.get("families") or []
        if isinstance(item, Mapping)
    )
    rules = tuple(
        _rule_from_document(item)
        for item in document.get("rules") or []
        if isinstance(item, Mapping)
    )
    rejections = tuple(
        _rule_from_document(item)
        for item in document.get("rejections") or []
        if isinstance(item, Mapping)
    )
    agents = {family.name: family.url for family in families if family.url}
    agents.setdefault(GENERIC_AGENT, GENERIC_AGENT_URL)
    pack = Pack(
        version=version,
        agents=agents,
        authors=(),
        files=(),
        branches=(),
        labels=(),
        bots=(),
        generic_weights={
            str(key): float(value)
            for key, value in dict(document.get("generic_weights") or {}).items()
        },
        exclusions=frozenset(str(item) for item in document.get("exclusions") or []),
        schema_version=2,
        families=families,
        rules=rules,
        rejections=rejections,
        catalogue=(
            dict(document.get("catalogue") or {})
            if isinstance(document.get("catalogue"), Mapping)
            else {}
        ),
        content_byte_limit=int(document.get("content_byte_limit") or 131_072),
        content_candidate_limit=int(document.get("content_candidate_limit") or 64),
    )
    validate_pack(pack)
    return pack


def build_pack_from_dir(src: Path, *, version: str) -> Pack:
    """Build one pack from its own source directory.

    Each pack version owns ``packs/sources/<version>/``: flat CSVs for schema v1
    or ``catalogue.json`` for schema v2. Sources are never shared between
    versions, so rebuilding one pack cannot pick up another pack's inputs.
    """
    src = Path(src)
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", src.name) and src.name != version:
        raise ValueError(
            f"source directory {src.name!r} belongs to a different pack than {version!r}"
        )
    if (src / SCHEMA_V2_SOURCE).exists() and (src / "tools.csv").exists():
        raise ValueError(f"{src} mixes schema-v1 CSVs and a schema-v2 {SCHEMA_V2_SOURCE}")
    if (src / SCHEMA_V2_SOURCE).exists():
        return _build_v2_pack(src, version=version)
    return _build_v1_pack(src, version=version)


def validate_pack(pack: Pack) -> None:
    if pack.schema_version < 2:
        return
    family_ids = [family.id for family in pack.families]
    if len(family_ids) != len(set(family_ids)):
        raise ValueError("duplicate canonical family id")
    family_names = [family.name for family in pack.families]
    if len(family_names) != len(set(family_names)):
        raise ValueError("duplicate canonical family name")
    for family in pack.families:
        if family.category not in FAMILY_CATEGORIES:
            raise ValueError(f"family {family.id}: unknown category {family.category!r}")
    known = set(family_ids)
    rule_ids: set[str] = set()
    signatures: set[str] = set()
    for rule in (*pack.rules, *pack.rejections):
        if not rule.id:
            raise ValueError("schema-v2 rules require stable ids")
        if rule.id in rule_ids:
            raise ValueError(f"duplicate rule id: {rule.id}")
        rule_ids.add(rule.id)
        if rule.channel not in RULE_CHANNELS:
            raise ValueError(f"rule {rule.id}: unknown channel {rule.channel!r}")
        if rule.lifecycle not in LIFECYCLE_STATUSES:
            raise ValueError(f"rule {rule.id}: unknown lifecycle {rule.lifecycle!r}")
        if rule.semantics.evidence not in EVIDENCE_SEMANTICS:
            raise ValueError(
                f"rule {rule.id}: unknown evidence semantics {rule.semantics.evidence!r}"
            )
        if rule.disposition == "positive" and rule.family_id not in known:
            raise ValueError(f"rule {rule.id}: unknown family {rule.family_id!r}")
        if rule.rollup_family is not None and rule.rollup_family not in known:
            raise ValueError(f"rule {rule.id}: unknown rollup family {rule.rollup_family!r}")
        if rule.valid_from and rule.valid_until and rule.valid_from > rule.valid_until:
            raise ValueError(f"rule {rule.id}: invalid lifecycle interval")
        signature = json.dumps(
            [rule.family_id, rule.channel, rule.forge, rule.match, rule.pattern],
            sort_keys=True,
            separators=(",", ":"),
        )
        if rule.disposition == "positive" and signature in signatures:
            raise ValueError(f"duplicate positive rule: {rule.id}")
        signatures.add(signature)

    active = [family for family in pack.families if family.category == "active"]
    incumbents = [family for family in active if family.cohort == "incumbent"]
    additions = [family for family in active if family.cohort == "addition"]
    v2 = [family for family in active if family.cohort == "v2"]
    current_matcher = [family for family in active if family.matcher_generation == "current"]
    expected = {
        "normalized_incumbents": len(incumbents),
        "additions": len(additions),
        "current_matcher_detectable": len(current_matcher),
        "v2_activated": len(v2),
        "active_total": len(active),
    }
    for key, value in expected.items():
        declared = pack.catalogue.get(key)
        if declared is not None and declared != value:
            raise ValueError(f"catalogue {key} declares {declared}, computed {value}")


def pack_to_document(pack: Pack) -> dict:
    if pack.schema_version < 2:

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
    return {
        "schema_version": 2,
        "version": pack.version,
        "catalogue": dict(pack.catalogue),
        "families": [_family_document(family) for family in pack.families],
        "rules": [_rule_document(rule) for rule in pack.rules],
        "rejections": [_rule_document(rule) for rule in pack.rejections],
        "generic_weights": dict(pack.generic_weights),
        "exclusions": sorted(pack.exclusions),
        "content_byte_limit": pack.content_byte_limit,
        "content_candidate_limit": pack.content_candidate_limit,
    }


def pack_from_document(doc: Mapping[str, object]) -> Pack:
    schema_version = int(doc.get("schema_version") or 1)
    if schema_version >= 2:
        families = tuple(
            _family_from_document(item)
            for item in doc.get("families") or []  # type: ignore[union-attr]
            if isinstance(item, Mapping)
        )
        rules = tuple(
            _rule_from_document(item)
            for item in doc.get("rules") or []  # type: ignore[union-attr]
            if isinstance(item, Mapping)
        )
        rejections = tuple(
            _rule_from_document(item)
            for item in doc.get("rejections") or []  # type: ignore[union-attr]
            if isinstance(item, Mapping)
        )
        agents = {family.name: family.url for family in families if family.url}
        agents.setdefault(GENERIC_AGENT, GENERIC_AGENT_URL)
        pack = Pack(
            version=str(doc["version"]),
            agents=agents,
            authors=(),
            files=(),
            branches=(),
            labels=(),
            bots=(),
            generic_weights={
                str(k): float(v)
                for k, v in dict(doc.get("generic_weights") or {}).items()  # type: ignore[union-attr]
            },
            exclusions=frozenset(str(x) for x in (doc.get("exclusions") or [])),  # type: ignore[union-attr]
            schema_version=schema_version,
            families=families,
            rules=rules,
            rejections=rejections,
            catalogue=(
                {str(k): v for k, v in dict(doc.get("catalogue") or {}).items()}  # type: ignore[union-attr]
            ),
            content_byte_limit=int(doc.get("content_byte_limit") or 131_072),
            content_candidate_limit=int(doc.get("content_candidate_limit") or 64),
        )
        validate_pack(pack)
        return pack

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
        generic_weights={
            str(k): float(v)
            for k, v in dict(doc.get("generic_weights") or {}).items()  # type: ignore[union-attr]
        },
        exclusions=frozenset(str(x) for x in (doc.get("exclusions") or [])),  # type: ignore[union-attr]
    )


def pack_digest(pack: Pack) -> str:
    canonical = json.dumps(pack_to_document(pack), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def write_pack_file(pack: Pack, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    document = pack_to_document(pack)
    rendered = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != document:
            raise PackConflict(
                f"pack file {path} already exists with different content; use a new version"
            )
        return pack_digest(pack)
    path.write_text(rendered, encoding="utf-8")
    return pack_digest(pack)


def load_pack_file(path: Path) -> Pack:
    return pack_from_document(json.loads(Path(path).read_text(encoding="utf-8")))


def _stored_pack(row: Mapping[str, object]) -> Pack:
    schema_version = int(row.get("schema_version") or 1)
    if schema_version >= 2:
        document = row.get("document")
        if not isinstance(document, Mapping):
            raise ValueError(f"frozen schema-v2 pack {row['version']!r} has no document")
        return pack_from_document(document)
    return pack_from_document(
        {
            "version": row["version"],
            # v1 agents were never persisted; preserving that behavior keeps old
            # frozen rows and old run rendering byte-compatible.
            "agents": {},
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
            expected = pack if pack.schema_version >= 2 else replace(pack, agents={})
            if _stored_pack(existing) != expected:
                raise PackConflict(
                    f"pack version {pack.version!r} already frozen with different content"
                )
            return
        values: dict[str, object] = {
            "version": pack.version,
            "authors": (
                [{"pattern": item.pattern, "agent": item.agent} for item in pack.authors]
                if pack.schema_version < 2
                else []
            ),
            "files": (
                [{"pattern": item.pattern, "agent": item.agent} for item in pack.files]
                if pack.schema_version < 2
                else []
            ),
            "branches": (
                [{"pattern": item.pattern, "agent": item.agent} for item in pack.branches]
                if pack.schema_version < 2
                else []
            ),
            "labels": (
                [{"pattern": item.pattern, "agent": item.agent} for item in pack.labels]
                if pack.schema_version < 2
                else []
            ),
            "bots": (
                [{"pattern": item.pattern, "agent": item.agent} for item in pack.bots]
                if pack.schema_version < 2
                else []
            ),
            "generic_weights": doc["generic_weights"],
            "exclusions": doc["exclusions"],
            "schema_version": pack.schema_version,
            "document": doc if pack.schema_version >= 2 else None,
        }
        connection.execute(insert(TracePack).values(**values))


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
        print(f"wrote {args.out} sha256={digest}")
        return 0
    from sqlalchemy import create_engine

    engine = create_engine(os.environ["DATABASE_URL"])
    freeze_pack(engine, load_pack_file(Path(args.pack)))
    print("frozen")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
