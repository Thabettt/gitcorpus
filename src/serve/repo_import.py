from __future__ import annotations

import csv
import hashlib
import io
import json
from dataclasses import dataclass

from sqlalchemy import func, insert, select
from sqlalchemy.engine import Connection, Engine

from lib.gh_client import API_VERSION
from store.models import Owner, Repo, RunItem, Runs

MAX_IMPORT_ROWS = 25000
_BATCH_SIZE = 2000


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


def _normalized_columns(fieldnames: list[str] | None) -> dict[str, str]:
    return {name.strip().lower(): name for name in fieldnames or [] if name}


def _pick(columns: dict[str, str], *names: str) -> str | None:
    for name in names:
        if name in columns:
            return columns[name]
    return None


def _optional_int(value: object) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = int(float(text))
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def parse_repo_csv(raw: bytes | str) -> ParsedRepos:
    text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, bytes) else raw
    reader = csv.DictReader(io.StringIO(text))
    columns = _normalized_columns(reader.fieldnames)
    name_column = _pick(columns, "full_name", "repo", "repository", "name")
    if name_column is None:
        raise RepoImportError(
            "the CSV needs a full_name or repo column",
            "Export a corpus from a search, or provide rows like owner/repo with an"
            " optional stars/stargazers column.",
        )
    id_column = _pick(columns, "id")
    stars_column = _pick(columns, "stargazers", "stars")
    rows: list[ParsedRepo] = []
    seen: set[str] = set()
    skipped = 0
    for record in reader:
        full_name = str(record.get(name_column) or "").strip()
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
                repo_id=_optional_int(record.get(id_column)) if id_column else None,
                stargazers=_optional_int(record.get(stars_column)) if stars_column else None,
            )
        )
        if len(rows) > MAX_IMPORT_ROWS:
            raise RepoImportError(
                f"the CSV has more than {MAX_IMPORT_ROWS:,} repos",
                "Split the file or run a search instead; large lists are better built"
                " through discovery.",
            )
    if not rows:
        raise RepoImportError(
            "no usable rows found",
            "Every row needs a full_name (owner/repo) in a full_name or repo column.",
        )
    return ParsedRepos(rows=tuple(rows), skipped=skipped)


def _synthetic_floor(connection: Connection, model) -> int | None:
    floor = connection.scalar(select(func.min(model.id)))
    return int(floor) if floor is not None else None


def _next_synthetic(floor: int | None) -> int:
    return min(floor - 1, -1) if floor is not None else -1


def _ensure_owners(connection: Connection, logins: set[str]) -> dict[str, int]:
    wanted = {login.strip().lower(): login.strip() for login in logins if login.strip()}
    if not wanted:
        return {}
    existing = {
        str(login).lower(): int(owner_id)
        for login, owner_id in connection.execute(
            select(Owner.login, Owner.id).where(Owner.login.in_(list(wanted.values())))
        )
    }
    missing = sorted(set(wanted) - set(existing))
    if missing:
        next_id = _next_synthetic(_synthetic_floor(connection, Owner))
        rows = [
            {"id": next_id - index, "login": wanted[login], "type": "User"}
            for index, login in enumerate(missing)
        ]
        connection.execute(insert(Owner), rows)
        existing.update({str(row["login"]).lower(): int(row["id"]) for row in rows})
    return existing


def _ensure_repos(
    connection: Connection, parsed_rows: tuple[ParsedRepo, ...], owner_ids: dict[str, int]
) -> dict[str, int]:
    wanted = {row.full_name.lower(): row.full_name for row in parsed_rows}
    existing = {
        str(full_name).lower(): int(repo_id)
        for full_name, repo_id in connection.execute(
            select(Repo.full_name, Repo.id).where(Repo.full_name.in_(list(wanted.values())))
        )
    }
    missing_names = sorted(set(wanted) - set(existing))
    if not missing_names:
        return existing
    candidate_ids = [row.repo_id for row in parsed_rows if row.repo_id is not None]
    taken_ids: set[int] = set()
    if candidate_ids:
        taken_ids = {
            int(repo_id)
            for (repo_id,) in connection.execute(select(Repo.id).where(Repo.id.in_(candidate_ids)))
        }
    next_id = _next_synthetic(_synthetic_floor(connection, Repo))
    rows: list[dict] = []
    for full_name_key in missing_names:
        source = next(row for row in parsed_rows if row.full_name.lower() == full_name_key)
        repo_id = (
            source.repo_id
            if source.repo_id is not None and source.repo_id not in taken_ids
            else None
        )
        if repo_id is None:
            repo_id = next_id
            next_id -= 1
        taken_ids.add(repo_id)
        owner_login = source.full_name.partition("/")[0].lower()
        owner_id = owner_ids.get(owner_login)
        if owner_id is None:
            continue
        rows.append(
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
        existing[full_name_key] = repo_id
    for start in range(0, len(rows), _BATCH_SIZE):
        connection.execute(insert(Repo), rows[start : start + _BATCH_SIZE])
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
        items: list[dict] = []
        for row in parsed.rows:
            repo_id = repo_ids.get(row.full_name.lower())
            if repo_id is None:
                continue
            items.append(
                {
                    "run_id": run_id,
                    "repo_id": repo_id,
                    "full_name": row.full_name,
                    "stargazers": row.stargazers,
                }
            )
        for start in range(0, len(items), _BATCH_SIZE):
            connection.execute(insert(RunItem), items[start : start + _BATCH_SIZE])
    return run_id
