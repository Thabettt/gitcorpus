from __future__ import annotations

import csv
import hashlib
import io
import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection, Engine

from lib.gh_client import API_VERSION
from store.models import Owner, Repo, RunItem, Runs

_LOOKUP_BATCH = 5000
_INSERT_BATCH = 2000
_NAME_KEYS = ("full_name", "repo", "repository", "name")
_ID_KEYS = ("repo_id", "id")
_STARS_KEYS = ("stargazers", "stars")


class RepoImportError(ValueError):
    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


@dataclass(frozen=True)
class ParsedRepo:
    full_name: str
    repo_id: int | None
    stargazers: int | None


@dataclass(frozen=True)
class ParsedRepos:
    rows: tuple[ParsedRepo, ...]
    skipped: int


def _optional_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = int(float(text))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _first_int(record: Mapping, keys: Iterable[str]) -> int | None:
    for key in keys:
        if key in record:
            parsed = _optional_int(record.get(key))
            if parsed is not None:
                return parsed
    return None


def _collect(records: Iterable[object]) -> ParsedRepos:
    rows: list[ParsedRepo] = []
    seen: set[str] = set()
    skipped = 0
    for record in records:
        if not isinstance(record, Mapping):
            skipped += 1
            continue
        full_name = ""
        for key in _NAME_KEYS:
            candidate = record.get(key)
            if isinstance(candidate, str) and candidate.strip():
                full_name = candidate.strip()
                break
        parts = full_name.split("/")
        if len(parts) != 2 or not all(part.strip() for part in parts):
            skipped += 1
            continue
        key = full_name.lower()
        if key in seen:
            skipped += 1
            continue
        seen.add(key)
        rows.append(
            ParsedRepo(
                full_name=full_name,
                repo_id=_first_int(record, _ID_KEYS),
                stargazers=_first_int(record, _STARS_KEYS),
            )
        )
    if not rows:
        raise RepoImportError(
            "no usable rows found",
            "Every row needs a full_name (owner/repo) in a full_name or repo field.",
        )
    return ParsedRepos(rows=tuple(rows), skipped=skipped)


def parse_repo_csv(raw: bytes | str) -> ParsedRepos:
    text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else raw
    reader = csv.DictReader(io.StringIO(text))
    columns = {
        original.strip().lower(): original for original in (reader.fieldnames or []) if original
    }
    name_keys = [key for key in _NAME_KEYS if key in columns]
    if not name_keys:
        raise RepoImportError(
            "the CSV needs a full_name or repo column",
            "Export a corpus from a search, or provide rows like owner/repo with an"
            " optional stars/stargazers column.",
        )

    def normalized(record: Mapping) -> dict:
        normalized_record = {}
        for column, original in columns.items():
            value = record.get(original)
            normalized_record[column] = value
        return normalized_record

    return _collect(normalized(record) for record in reader)


def parse_repo_json(raw: bytes | str) -> ParsedRepos:
    text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else raw
    try:
        document = json.loads(text)
    except ValueError as exc:
        raise RepoImportError(
            "the file is not valid JSON",
            "Use this app's search export (its items array) or a JSON array of"
            " {full_name, stars} objects.",
        ) from exc
    if isinstance(document, Mapping):
        items = document.get("items")
        if not isinstance(items, list):
            raise RepoImportError(
                "the JSON needs an items list",
                "This app's search export has an items array; export one from a run"
                " and upload that file.",
            )
        records: Iterable[Mapping] = items
    elif isinstance(document, list):
        records = document
    else:
        raise RepoImportError("the JSON must be an object or an array")
    return _collect(records)


def parse_repo_file(name: str, raw: bytes | str) -> ParsedRepos:
    stripped = raw.lstrip()
    marker = stripped[:1]
    looks_json = marker in (b"{", b"[") if isinstance(marker, bytes) else marker in ("{", "[")
    if name.lower().endswith(".json") or looks_json:
        return parse_repo_json(raw)
    return parse_repo_csv(raw)


def _synthetic_floor(connection: Connection, model) -> int | None:
    floor = connection.scalar(select(func.min(model.id)))
    return int(floor) if floor is not None else None


def _next_synthetic(floor: int | None) -> int:
    return min(floor - 1, -1) if floor is not None else -1


def _ensure_owners(connection: Connection, logins: set[str]) -> dict[str, int]:
    wanted = {login.strip().lower(): login.strip() for login in logins if login.strip()}
    if not wanted:
        return {}
    existing: dict[str, int] = {}
    values = list(wanted.values())
    for start in range(0, len(values), _LOOKUP_BATCH):
        existing.update(
            {
                str(login).lower(): int(owner_id)
                for login, owner_id in connection.execute(
                    select(Owner.login, Owner.id).where(
                        Owner.login.in_(values[start : start + _LOOKUP_BATCH])
                    )
                )
            }
        )
    missing = sorted(set(wanted) - set(existing))
    next_id = _next_synthetic(_synthetic_floor(connection, Owner))
    pending: list[dict] = []
    for login in missing:
        pending.append({"id": next_id, "login": wanted[login], "type": "User"})
        existing[login] = next_id
        next_id -= 1
        if len(pending) >= _INSERT_BATCH:
            connection.execute(insert(Owner), pending)
            pending = []
    if pending:
        connection.execute(insert(Owner), pending)
    return existing


def _ensure_repos(
    connection: Connection, parsed_rows: tuple[ParsedRepo, ...], owner_ids: dict[str, int]
) -> dict[str, int]:
    sources = {row.full_name.lower(): row for row in parsed_rows}
    existing: dict[str, int] = {}
    keys = list(sources)
    for start in range(0, len(keys), _LOOKUP_BATCH):
        names = [sources[key].full_name for key in keys[start : start + _LOOKUP_BATCH]]
        existing.update(
            {
                str(full_name).lower(): int(repo_id)
                for full_name, repo_id in connection.execute(
                    select(Repo.full_name, Repo.id).where(Repo.full_name.in_(names))
                )
            }
        )
    missing_keys = sorted(set(sources) - set(existing))
    if not missing_keys:
        return existing
    candidate_ids = [row.repo_id for row in parsed_rows if row.repo_id is not None]
    taken_ids: set[int] = set()
    for start in range(0, len(candidate_ids), _LOOKUP_BATCH):
        taken_ids.update(
            int(repo_id)
            for (repo_id,) in connection.execute(
                select(Repo.id).where(Repo.id.in_(candidate_ids[start : start + _LOOKUP_BATCH]))
            )
        )
    next_id = _next_synthetic(_synthetic_floor(connection, Repo))
    pending: list[dict] = []
    for key in missing_keys:
        source = sources[key]
        repo_id = (
            source.repo_id
            if source.repo_id is not None and source.repo_id not in taken_ids
            else None
        )
        if repo_id is None:
            repo_id = next_id
            next_id -= 1
        taken_ids.add(repo_id)
        owner_id = owner_ids.get(source.full_name.partition("/")[0].lower())
        if owner_id is None:
            continue
        pending.append(
            {
                "id": repo_id,
                "node_id": f"import:{source.full_name}",
                "full_name": source.full_name,
                "owner_id": owner_id,
                "name": source.full_name.partition("/")[2],
                "visibility": "public",
                "stargazers": source.stargazers or 0,
            }
        )
        existing[key] = repo_id
        if len(pending) >= _INSERT_BATCH:
            connection.execute(insert(Repo), pending)
            pending = []
    if pending:
        connection.execute(insert(Repo), pending)
    return existing


def _spec_hash(spec: dict) -> str:
    canonical = json.dumps(spec, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def import_repos_as_run(engine: Engine, parsed: ParsedRepos, *, name: str) -> int:
    spec = {
        "gitcorpus_filter": 1,
        "q": f"import: {name[:200]}",
        "import": {"rows": len(parsed.rows), "skipped": parsed.skipped},
    }
    with engine.begin() as connection:
        owner_ids = _ensure_owners(
            connection, {row.full_name.partition("/")[0] for row in parsed.rows}
        )
        repo_ids = _ensure_repos(connection, parsed.rows, owner_ids)
        run_id = int(
            connection.execute(
                insert(Runs)
                .values(
                    filter_hash=_spec_hash(spec),
                    filter_spec=spec,
                    api_version=API_VERSION,
                    kind="find",
                    status="done",
                    total_count=len(parsed.rows),
                    fetched=len(parsed.rows),
                    inserted=len(parsed.rows),
                    started_at=func.now(),
                    finished_at=func.now(),
                )
                .returning(Runs.id)
            ).scalar_one()
        )
        pending: list[dict] = []
        for row in parsed.rows:
            repo_id = repo_ids.get(row.full_name.lower())
            if repo_id is None:
                continue
            pending.append(
                {
                    "run_id": run_id,
                    "repo_id": repo_id,
                    "full_name": row.full_name,
                    "stargazers": row.stargazers,
                }
            )
            if len(pending) >= _INSERT_BATCH:
                connection.execute(insert(RunItem), pending)
                pending = []
        if pending:
            connection.execute(insert(RunItem), pending)
    return run_id
