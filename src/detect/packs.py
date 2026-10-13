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
        names = {
            pattern.agent for pattern in (*self.authors, *self.files, *self.branches, *self.labels)
        }
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
    path.write_text(json.dumps(pack_to_document(pack), indent=2), encoding="utf-8")
    return pack_digest(pack)


def load_pack_file(path: Path) -> Pack:
    return pack_from_document(json.loads(Path(path).read_text(encoding="utf-8")))


def _stored_pack(row: Mapping[str, object]) -> Pack:
    return pack_from_document(
        {
            "version": row["version"],
            # agents are not persisted in trace_packs; version identity is content-based
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
