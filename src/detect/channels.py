from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from detect.attribution import (
    Hit,
    dedupe_hits,
    is_noise_commit,
    match_author_identities,
    match_bots,
    match_commit_messages,
    match_files,
)
from detect.packs import Pack
from discover.pipeline import Deps
from enrich.trees_first import FilePresence, fetch_tree
from lib import audit
from lib.gh_client import (
    API_BASE,
    PartialResultsError,
    RequestFailed,
    ThrottledError,
    request_with_retry,
)

OnResponse = Callable[[httpx.Response, float], None] | None

_CONTENT_PROBE_LIMIT = 5
_TRUNCATED_PROBE_LIMIT = 20
_FAULT_NOTE_LIMIT = 200
_RAW_ACCEPT = {"Accept": "application/vnd.github.raw+json"}


@dataclass(frozen=True)
class ChannelResult:
    hits: tuple[Hit, ...] = ()
    status: str = "ok"  # ok | partial | unavailable | skipped
    note: str | None = None
    stats: Mapping[str, object] = field(default_factory=dict)


def _fault_note(exc: Exception) -> str:
    note = f"{type(exc).__name__}: {exc}"
    if len(note) > _FAULT_NOTE_LIMIT:
        note = note[:_FAULT_NOTE_LIMIT]
    return note


def _raw_text(
    deps: Deps, url: str, *, ref: str | None = None, on_response: OnResponse
) -> tuple[str | None, str | None]:
    if ref is not None:
        url = f"{url}?ref={quote(ref)}"
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


def _gitignore_paths(
    deps: Deps, full_name: str, *, ref: str | None = None, on_response: OnResponse
) -> tuple[tuple[str, ...], str | None]:
    text, error = _raw_text(
        deps,
        f"{API_BASE}/repos/{full_name}/contents/.gitignore",
        ref=ref,
        on_response=on_response,
    )
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
    ref: str | None = None,
    on_response: OnResponse,
) -> tuple[str, ...]:
    found: list[str] = []
    for candidate in _literal_candidates(pack)[:_TRUNCATED_PROBE_LIMIT]:
        if candidate in presence.paths or candidate.rsplit("/", 1)[-1] in pack.exclusions:
            continue
        text, error = _raw_text(
            deps,
            f"{API_BASE}/repos/{full_name}/contents/{candidate}",
            ref=ref,
            on_response=on_response,
        )
        if error is None and text is not None:
            found.append(candidate)
    return tuple(found)


def _probe_content(
    deps: Deps,
    full_name: str,
    path: str,
    *,
    ref: str | None = None,
    on_response: OnResponse,
) -> dict:
    text, error = _raw_text(
        deps,
        f"{API_BASE}/repos/{full_name}/contents/{path}",
        ref=ref,
        on_response=on_response,
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
        status = "ok"
        notes: list[str] = []
        hits = list(match_files(pack, presence, agents))
        if presence.truncated:
            status = "partial"
            notes.append("tree truncated; literal-path probes used")
            probed_paths = _probe_missing_paths(
                deps, full_name, pack, presence, ref=ref, on_response=on_response
            )
            if probed_paths:
                probed_presence = FilePresence(
                    repo_full_name=full_name,
                    paths=frozenset(probed_paths),
                    truncated=False,
                    source="contents",
                )
                hits.extend(match_files(pack, probed_presence, agents))
        ignored, ignore_error = _gitignore_paths(deps, full_name, ref=ref, on_response=on_response)
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
            {hit.evidence["path"] for hit in hits if hit.evidence.get("source") == "tree"}
        )[:_CONTENT_PROBE_LIMIT]
        for path in content_paths:
            info = _probe_content(deps, full_name, path, ref=ref, on_response=on_response)
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
    except RequestFailed as exc:
        if exc.status == 404:
            return ChannelResult(status="unavailable", note="repo not found")
        return ChannelResult(status="partial", note=f"tree: {exc.message}")
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return ChannelResult(status="partial", note=_fault_note(exc))


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
    try:
        payload, status, note = _graphql(
            deps,
            _HISTORY_QUERY,
            {"owner": owner, "name": name, "limit": limit},
            on_response=on_response,
        )
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return {
            key: ChannelResult(status="partial", note=_fault_note(exc))
            for key in ("author", "commit_trailer", "bot")
        }
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
    bot_candidates: list[dict[str, str]] = []
    messages: list[tuple[str, str]] = []
    committed_at: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        oid = str(node.get("oid") or "")
        message = str(node.get("message") or "")
        if node.get("committedDate"):
            committed_at[oid] = str(node["committedDate"])
        author_entry = _person_entry(node.get("author"), commit=oid)
        committer_entry = _person_entry(node.get("committer"), commit=oid)
        bot_candidates.extend((author_entry, committer_entry))
        if is_noise_commit(message):
            continue
        messages.append((oid, message))
        identities.extend((author_entry, committer_entry))
    author_hits = match_author_identities(pack, identities, agents)
    trailer_hits = match_commit_messages(pack, messages, agents)
    bot_hits = match_bots(pack, bot_candidates)
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
        "author": ChannelResult(hits=tuple(author_hits), status=status, note=note, stats=stats),
        "commit_trailer": ChannelResult(
            hits=tuple(trailer_hits), status=status, note=note, stats=stats
        ),
        "bot": ChannelResult(
            hits=tuple(bot_hits),
            status=status,
            note="window: last 100 commits; generic bot evidence only",
        ),
    }
