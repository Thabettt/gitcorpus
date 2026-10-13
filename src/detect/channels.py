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
    match_issue_participants,
    match_pr_authors,
    match_pr_metadata,
    propagate_pr_commits,
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
        if status != "ok":
            return {
                key: ChannelResult(status="partial", note=note)
                for key in ("author", "commit_trailer", "bot")
            }
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
                            ((commit.get("commit") or {}).get("author") or {})
                            .get("user", {})
                            .get("login")
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
    try:
        payload, gql_status, gql_note = _graphql(
            deps, _PR_QUERY, {"owner": owner, "name": name, "limit": limit}, on_response=on_response
        )
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return ChannelResult(status="partial", note=_fault_note(exc))
    if payload is None:
        return ChannelResult(status=gql_status, note=gql_note)
    prs, status, note = _prs_from_payload(payload)
    if status == "unavailable":
        if gql_status != "ok":
            return ChannelResult(status="partial", note=gql_note)
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
    try:
        payload, status, note = _graphql(
            deps,
            _ISSUE_QUERY,
            {"owner": owner, "name": name, "limit": limit},
            on_response=on_response,
        )
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return ChannelResult(status="partial", note=_fault_note(exc))
    if payload is None:
        return ChannelResult(status=status, note=note)
    repository = (payload.get("data") or {}).get("repository")
    if repository is None:
        if status != "ok":
            return ChannelResult(status="partial", note=note)
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
                entries.append(
                    {"login": str(assignee["login"]), "number": number, "role": "assignee"}
                )
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
