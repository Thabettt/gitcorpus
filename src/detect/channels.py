from __future__ import annotations

import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import quote

import httpx

from detect.attribution import (
    Hit,
    dedupe_hits,
    hit_from_rule,
    is_noise_commit,
    match_author_identities,
    match_bots,
    match_commit_messages,
    match_files,
    match_hidden_refs,
    match_issue_participants,
    match_pr_authors,
    match_pr_metadata,
    propagate_pr_commits,
)
from detect.content_attribution import CONTENT_CHANNEL, classify_agents_md
from detect.packs import Pack
from detect.structured import content_candidates, declared_literal_paths, evaluate_file_rules
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
_GRAPHQL_BODY_ATTEMPTS = 3
_GRAPHQL_RETRY_BASE_SECONDS = 0.5
_PR_FALLBACK_PAGE_SIZES = (50, 25, 10)
_RETRYABLE_HTTP_STATUSES = frozenset({401, 403, 408, 409, 425, 429, 500, 502, 503, 504})


class FailureKind(StrEnum):
    PERMANENT = "permanent"
    RETRYABLE = "retryable"


@dataclass(frozen=True)
class ChannelResult:
    hits: tuple[Hit, ...] = ()
    status: str = "ok"  # ok | partial | unavailable | skipped
    note: str | None = None
    stats: Mapping[str, object] = field(default_factory=dict)
    failure_kind: FailureKind | None = None


@dataclass(frozen=True)
class _GraphQLResponse:
    payload: dict | None
    status: str
    note: str | None
    failure_kind: FailureKind | None = None


def _http_failure_kind(status: int) -> FailureKind:
    if status in _RETRYABLE_HTTP_STATUSES or status >= 500:
        return FailureKind.RETRYABLE
    return FailureKind.PERMANENT


def _merge_failure_kind(
    current: FailureKind | None, incoming: FailureKind | None
) -> FailureKind | None:
    if FailureKind.RETRYABLE in (current, incoming):
        return FailureKind.RETRYABLE
    return incoming or current


def _fault_note(exc: Exception) -> str:
    note = f"{type(exc).__name__}: {exc}"
    if len(note) > _FAULT_NOTE_LIMIT:
        note = note[:_FAULT_NOTE_LIMIT]
    return note


def _raw_text(
    deps: Deps,
    url: str,
    *,
    ref: str | None = None,
    on_response: OnResponse,
    byte_limit: int | None = None,
) -> tuple[str | None, str | None, FailureKind | None]:
    if ref is not None:
        url = f"{url}?ref={quote(ref)}"
    headers = dict(_RAW_ACCEPT)
    if byte_limit is not None:
        headers["Range"] = f"bytes=0-{max(0, byte_limit - 1)}"
    response = request_with_retry(
        deps.client,
        "GET",
        url,
        extra_headers=headers,
        limiter=deps.limiter,
        token_id=deps.token_fp,
        on_response=on_response,
    )
    if response.status_code == 404:
        return None, None, None
    if response.status_code == 206 and byte_limit is not None:
        return None, f"content exceeds {byte_limit}-byte cap", FailureKind.PERMANENT
    if response.status_code != 200:
        return None, f"HTTP {response.status_code}", _http_failure_kind(response.status_code)
    return response.text, None, None


def _gitignore_paths(
    deps: Deps, full_name: str, *, ref: str | None = None, on_response: OnResponse
) -> tuple[tuple[str, ...], str | None, FailureKind | None]:
    text, error, failure_kind = _raw_text(
        deps,
        f"{API_BASE}/repos/{full_name}/contents/.gitignore",
        ref=ref,
        on_response=on_response,
    )
    if text is None:
        return (), error, failure_kind
    lines = tuple(
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )
    return lines, None, None


def _literal_candidates(pack: Pack) -> tuple[str, ...]:
    if pack.schema_version >= 2:
        return declared_literal_paths(pack)
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
) -> tuple[tuple[str, ...], str | None, FailureKind | None]:
    found: list[str] = []
    last_error: str | None = None
    failure_kind: FailureKind | None = None
    for candidate in _literal_candidates(pack)[:_TRUNCATED_PROBE_LIMIT]:
        if candidate in presence.paths or candidate.rsplit("/", 1)[-1] in pack.exclusions:
            continue
        text, error, probe_failure = _raw_text(
            deps,
            f"{API_BASE}/repos/{full_name}/contents/{candidate}",
            ref=ref,
            on_response=on_response,
        )
        if error is None and text is not None:
            found.append(candidate)
        elif error is not None:
            last_error = error
            failure_kind = _merge_failure_kind(failure_kind, probe_failure)
    return tuple(found), last_error, failure_kind


def _probe_content(
    deps: Deps,
    full_name: str,
    path: str,
    *,
    ref: str | None = None,
    on_response: OnResponse,
    byte_limit: int | None = None,
) -> tuple[dict, str | None, str | None, FailureKind | None]:
    text, error, failure_kind = _raw_text(
        deps,
        f"{API_BASE}/repos/{full_name}/contents/{path}",
        ref=ref,
        on_response=on_response,
        byte_limit=byte_limit,
    )
    if error is not None or text is None:
        return {}, None, error, failure_kind
    if byte_limit is not None and len(text.encode("utf-8")) > byte_limit:
        return {}, None, f"content exceeds {byte_limit}-byte cap", FailureKind.PERMANENT
    return {"size": len(text), "empty": not text.strip()}, text, None, None


def detect_files(
    deps: Deps,
    full_name: str,
    pack: Pack,
    *,
    ref: str | None = None,
    agents: frozenset[str] | None = None,
    on_response: OnResponse = None,
    fast: bool = False,
) -> ChannelResult:
    """Detect file-channel evidence over the GitHub API.

    ``fast`` skips content reads for rules on broad path patterns (every
    workflow or compose file); targeted single-file content rules still run.
    """
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
        failure_kind: FailureKind | None = None
        probed_path_set: set[str] = set()
        hits = list(match_files(pack, presence, agents))
        if presence.truncated:
            status = "partial"
            notes.append("tree truncated; literal-path probes used")
            probed_paths, probe_error, probe_failure = _probe_missing_paths(
                deps, full_name, pack, presence, ref=ref, on_response=on_response
            )
            if probe_error is not None:
                notes.append(f"literal probes: {probe_error}")
                failure_kind = _merge_failure_kind(failure_kind, probe_failure)
            if probed_paths:
                probed_path_set.update(probed_paths)
                probed_presence = FilePresence(
                    repo_full_name=full_name,
                    paths=frozenset(probed_paths),
                    truncated=False,
                    source="contents",
                )
                hits.extend(match_files(pack, probed_presence, agents))
                presence = FilePresence(
                    repo_full_name=full_name,
                    paths=frozenset(set(presence.paths) | set(probed_paths)),
                    truncated=True,
                    source="tree",
                )
        ignored, ignore_error, ignore_failure = _gitignore_paths(
            deps, full_name, ref=ref, on_response=on_response
        )
        if ignore_error is not None:
            status = "partial"
            notes.append(f"gitignore: {ignore_error}")
            failure_kind = _merge_failure_kind(failure_kind, ignore_failure)
        elif ignored:
            ignored_presence = FilePresence(
                repo_full_name=full_name,
                paths=frozenset(ignored),
                truncated=False,
                source="gitignore",
            )
            hits.extend(match_files(pack, ignored_presence, agents))
        hits = dedupe_hits(hits)
        hit_paths = sorted(
            {hit.evidence["path"] for hit in hits if hit.evidence.get("source") == "tree"}
        )[:_CONTENT_PROBE_LIMIT]
        generic_paths = sorted(
            path for path in presence.paths if path.rsplit("/", 1)[-1] in pack.generic_weights
        )[:_CONTENT_PROBE_LIMIT]
        structured_paths: tuple[str, ...] = ()
        candidate_capped = False
        if pack.schema_version >= 2:
            structured_paths, candidate_capped = content_candidates(
                pack, presence.paths, targeted_only=fast
            )
            if candidate_capped:
                status = "partial"
                notes.append(
                    f"structured content candidate cap reached ({pack.content_candidate_limit})"
                )
            content_paths = [
                *structured_paths,
                *(path for path in generic_paths if path not in structured_paths),
            ]
        else:
            content_paths = [*hit_paths, *(path for path in generic_paths if path not in hit_paths)]
        fetched: list[tuple[str, str]] = []
        content_diagnostics: list[dict[str, object]] = []
        for path in content_paths:
            info, text, content_error, content_failure = _probe_content(
                deps,
                full_name,
                path,
                ref=ref,
                on_response=on_response,
                byte_limit=pack.content_byte_limit if pack.schema_version >= 2 else None,
            )
            if content_error is not None:
                status = "partial"
                notes.append(f"content {path}: {content_error}")
                failure_kind = _merge_failure_kind(failure_kind, content_failure)
                content_diagnostics.append(
                    {
                        "path": path,
                        "kind": (
                            "parse_failure" if "byte cap" in content_error else "fetch_failure"
                        ),
                        "note": content_error,
                    }
                )
            if not info:
                continue
            if text is not None:
                fetched.append((path, text))
            for hit in hits:
                if hit.evidence.get("path") == path:
                    hit.evidence.update(info)
        if pack.schema_version >= 2:
            structured_matches, predicate_diagnostics = evaluate_file_rules(
                pack,
                presence.paths,
                dict(fetched),
                source="tree",
                agents=agents,
            )
            hits = [
                hit
                for hit in hits
                if not (
                    hit.rule_id is not None and hit.evidence.get("source") in {"tree", "contents"}
                )
            ]
            for matched in structured_matches:
                evidence = dict(matched.evidence)
                if evidence.get("path") in probed_path_set:
                    evidence["source"] = "contents"
                hit = hit_from_rule(
                    matched.rule,
                    "file",
                    evidence,
                    forge="github",
                    role=matched.rule.semantics.role or "repository_file",
                )
                if hit is not None:
                    hits.append(hit)
            content_diagnostics.extend(item.as_dict() for item in predicate_diagnostics)
        if pack.schema_version < 2:
            known = frozenset(pack.agents) if agents is None else frozenset(agents)
            for path, text in fetched:
                if path.rsplit("/", 1)[-1] not in pack.generic_weights or not text.strip():
                    continue
                attribution = classify_agents_md(text, known)
                for signal in attribution.signals:
                    hits.append(
                        Hit(
                            signal.agent,
                            CONTENT_CHANNEL,
                            {
                                "path": path,
                                "source": "tree",
                                "marker": path.rsplit("/", 1)[-1],
                                "cue": signal.cue,
                                "snippet": signal.snippet,
                                "confidence": signal.confidence,
                                "classifier": attribution.version,
                            },
                        )
                    )
        hits = dedupe_hits(hits)
        return ChannelResult(
            hits=tuple(hits),
            status=status,
            note="; ".join(notes) or None,
            stats={
                "content_candidates": len(structured_paths),
                "content_scan": "fast" if fast else "full",
                "content_candidate_cap_reached": candidate_capped,
                "content_diagnostics": tuple(content_diagnostics),
            },
            failure_kind=failure_kind,
        )
    except RequestFailed as exc:
        if exc.status == 404:
            return ChannelResult(
                status="unavailable",
                note="repo not found",
                failure_kind=FailureKind.PERMANENT,
            )
        return ChannelResult(
            status="partial",
            note=f"tree: {exc.message}",
            failure_kind=_http_failure_kind(exc.status),
        )
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return ChannelResult(
            status="partial",
            note=_fault_note(exc),
            failure_kind=FailureKind.RETRYABLE,
        )


def detect_hidden_refs(
    deps: Deps,
    full_name: str,
    pack: Pack,
    *,
    agents: frozenset[str] | None = None,
    on_response: OnResponse = None,
) -> ChannelResult:
    namespaces = pack.hidden_ref_namespaces()
    if not namespaces:
        return ChannelResult(status="skipped", note="pack declares no hidden-ref namespaces")
    refs: list[dict[str, object]] = []
    diagnostics: list[dict[str, object]] = []
    status = "ok"
    failure_kind: FailureKind | None = None
    for namespace in namespaces:
        prefix = namespace.removeprefix("refs/").rstrip("/")
        response = request_with_retry(
            deps.client,
            "GET",
            f"{API_BASE}/repos/{full_name}/git/matching-refs/{quote(prefix, safe='/')}",
            limiter=deps.limiter,
            token_id=deps.token_fp,
            on_response=on_response,
        )
        if response.status_code == 404:
            continue
        if response.status_code != 200:
            status = "partial"
            kind = _http_failure_kind(response.status_code)
            failure_kind = _merge_failure_kind(failure_kind, kind)
            diagnostics.append(
                {
                    "namespace": namespace,
                    "kind": "fetch_failure",
                    "note": f"HTTP {response.status_code}",
                }
            )
            continue
        payload = audit.cached_json(response)
        if payload is None:
            try:
                payload = response.json()
            except ValueError:
                payload = None
        if not isinstance(payload, list):
            status = "partial"
            diagnostics.append(
                {
                    "namespace": namespace,
                    "kind": "parse_failure",
                    "note": "matching-refs response was not an array",
                }
            )
            continue
        for item in payload:
            if len(refs) >= pack.content_candidate_limit:
                break
            if not isinstance(item, Mapping):
                continue
            object_data = item.get("object")
            if not isinstance(object_data, Mapping):
                continue
            ref_name = str(item.get("ref") or "")
            sha = str(object_data.get("sha") or "")
            if ref_name.startswith(namespace) and sha:
                refs.append(
                    {
                        "ref": ref_name,
                        "commit": sha,
                        "reachability": "github_matching_ref",
                    }
                )
    scoped_rules = [
        rule
        for rule in pack.rules_for("hidden_ref")
        if isinstance(rule.match.get("identity"), Mapping)
    ]
    if scoped_rules:
        for entry in refs:
            ref_name = str(entry["ref"])
            needs_identity = any(
                re.fullmatch(str(rule.match.get("regex") or rule.pattern), ref_name)
                for rule in scoped_rules
            )
            if not needs_identity:
                continue
            response = request_with_retry(
                deps.client,
                "GET",
                f"{API_BASE}/repos/{full_name}/git/commits/{entry['commit']}",
                limiter=deps.limiter,
                token_id=deps.token_fp,
                on_response=on_response,
            )
            if response.status_code != 200:
                status = "partial"
                diagnostics.append(
                    {
                        "ref": ref_name,
                        "kind": "fetch_failure",
                        "note": f"commit HTTP {response.status_code}",
                    }
                )
                failure_kind = _merge_failure_kind(
                    failure_kind, _http_failure_kind(response.status_code)
                )
                continue
            try:
                commit = response.json()
            except ValueError:
                commit = None
            if not isinstance(commit, Mapping):
                diagnostics.append(
                    {"ref": ref_name, "kind": "parse_failure", "note": "invalid commit JSON"}
                )
                continue
            for role in ("author", "committer"):
                identity = commit.get(role)
                if isinstance(identity, Mapping):
                    entry[f"{role}_name"] = str(identity.get("name") or "")
                    entry[f"{role}_email"] = str(identity.get("email") or "")
                    if role == "committer" and identity.get("date"):
                        entry["observed_at"] = str(identity["date"])
    hits = match_hidden_refs(pack, refs, agents, forge="github")
    return ChannelResult(
        hits=tuple(hits),
        status=status,
        note="targeted GitHub hidden-ref namespaces",
        stats={"refs": len(refs), "diagnostics": tuple(diagnostics)},
        failure_kind=failure_kind,
    )


_HISTORY_QUERY = """
query($owner: String!, $name: String!, $limit: Int!) {
  repository(owner: $owner, name: $name) {
    defaultBranchRef { name }
    object(expression: "HEAD") {
      ... on Commit {
        history(first: $limit) {
          totalCount
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
  rateLimit { cost limit used remaining resetAt }
}
"""


def _graphql(
    deps: Deps, query: str, variables: dict, *, on_response: OnResponse
) -> _GraphQLResponse:
    last_note = "malformed graphql payload"
    for attempt in range(_GRAPHQL_BODY_ATTEMPTS):
        response = request_with_retry(
            deps.client,
            "POST",
            f"{API_BASE}/graphql",
            json_body={"query": query, "variables": variables},
            limiter=deps.limiter,
            token_id=deps.token_fp,
            on_response=on_response,
            max_attempts=3,
        )
        if response.status_code != 200:
            return _GraphQLResponse(
                None,
                "partial",
                f"HTTP {response.status_code}",
                _http_failure_kind(response.status_code),
            )
        payload = audit.cached_json(response)
        if payload is None:
            try:
                payload = response.json()
            except ValueError:
                payload = None
        if not isinstance(payload, dict):
            last_note = "malformed graphql payload"
        elif payload.get("errors"):
            if _graphql_repo_not_found(payload):
                return _GraphQLResponse(
                    payload,
                    "unavailable",
                    "repo not found",
                    FailureKind.PERMANENT,
                )
            last_note = "graphql errors"
            if not _retryable_graphql_errors(payload):
                return _GraphQLResponse(
                    payload,
                    "partial",
                    last_note,
                    FailureKind.PERMANENT,
                )
        else:
            return _GraphQLResponse(payload, "ok", None)
        if attempt + 1 < _GRAPHQL_BODY_ATTEMPTS:
            time.sleep(_GRAPHQL_RETRY_BASE_SECONDS * (2**attempt))
    return _GraphQLResponse(
        payload if isinstance(payload, dict) else None,
        "partial",
        last_note,
        FailureKind.RETRYABLE,
    )


def _graphql_repo_not_found(payload: Mapping[str, object]) -> bool:
    data = payload.get("data")
    if isinstance(data, Mapping) and data.get("repository") is not None:
        return False
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return False
    for error in errors:
        if not isinstance(error, Mapping):
            continue
        kind = str(error.get("type") or error.get("code") or "").upper()
        message = str(error.get("message") or "").lower()
        if kind == "NOT_FOUND" or "could not resolve to a repository" in message:
            return True
    return False


def _retryable_graphql_errors(payload: Mapping[str, object]) -> bool:
    errors = payload.get("errors")
    if not isinstance(errors, list):
        return False
    text = " ".join(
        str(error.get("message") or error.get("type") or error.get("code") or "")
        for error in errors
        if isinstance(error, Mapping)
    ).lower()
    markers = (
        "rate limit",
        "rate_limited",
        "timeout",
        "timed out",
        "internal",
        "service unavailable",
        "something went wrong",
        "execution error",
    )
    return any(marker in text for marker in markers)


def _person_entry(
    person: object, *, commit: str, role: str = "author", observed_at: str = ""
) -> dict[str, str]:
    if not isinstance(person, Mapping):
        return {
            "login": "",
            "name": "",
            "email": "",
            "commit": commit,
            "role": role,
            "observed_at": observed_at,
        }
    user = person.get("user")
    login = ""
    if isinstance(user, Mapping) and user.get("login"):
        login = str(user["login"])
    return {
        "login": login,
        "name": str(person.get("name") or ""),
        "email": str(person.get("email") or ""),
        "commit": commit,
        "role": role,
        "observed_at": observed_at,
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
        outcome = _graphql(
            deps,
            _HISTORY_QUERY,
            {"owner": owner, "name": name, "limit": limit},
            on_response=on_response,
        )
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return {
            key: ChannelResult(
                status="partial",
                note=_fault_note(exc),
                failure_kind=FailureKind.RETRYABLE,
            )
            for key in ("author", "commit_trailer", "bot")
        }
    payload, status, note = outcome.payload, outcome.status, outcome.note
    if payload is None:
        return {
            key: ChannelResult(
                status=status,
                note=note,
                failure_kind=outcome.failure_kind,
            )
            for key in ("author", "commit_trailer", "bot")
        }
    repository = (payload.get("data") or {}).get("repository")
    if repository is None:
        if status != "ok":
            return {
                key: ChannelResult(
                    status=status,
                    note=note,
                    failure_kind=outcome.failure_kind,
                )
                for key in ("author", "commit_trailer", "bot")
            }
        return {
            key: ChannelResult(
                status="unavailable",
                note="repo not found",
                failure_kind=FailureKind.PERMANENT,
            )
            for key in ("author", "commit_trailer", "bot")
        }
    history = (repository.get("object") or {}).get("history") or {}
    nodes = history.get("nodes") or []
    total_raw = history.get("totalCount")
    total_commits = (
        total_raw
        if isinstance(total_raw, int) and not isinstance(total_raw, bool) and total_raw >= 0
        else None
    )
    identities: list[dict[str, str]] = []
    bot_candidates: list[dict[str, str]] = []
    messages: list[tuple[str, str, str]] = []
    committed_at: dict[str, str] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            continue
        oid = str(node.get("oid") or "")
        message = str(node.get("message") or "")
        observed_at = str(node.get("committedDate") or "")
        if observed_at:
            committed_at[oid] = observed_at
        author_entry = _person_entry(
            node.get("author"), commit=oid, role="author", observed_at=observed_at
        )
        committer_entry = _person_entry(
            node.get("committer"), commit=oid, role="committer", observed_at=observed_at
        )
        bot_candidates.extend((author_entry, committer_entry))
        if is_noise_commit(message):
            continue
        messages.append((oid, message, observed_at))
        identities.extend((author_entry, committer_entry))
    author_hits = match_author_identities(pack, identities, agents)
    trailer_hits = match_commit_messages(pack, messages, agents)
    bot_hits = match_bots(pack, bot_candidates)
    author_oids = {
        hit.evidence.get("commit")
        for hit in author_hits
        if pack.schema_version < 2 or hit.metric_eligibility.get("current_commit_ratio")
    }
    trailer_oids = {
        hit.evidence.get("commit")
        for hit in trailer_hits
        if pack.schema_version < 2 or hit.metric_eligibility.get("current_commit_ratio")
    }
    ai_oids = author_oids | trailer_oids
    bot_oids = {hit.evidence.get("commit") for hit in bot_hits}
    commit_oids = {oid for oid, _message, _observed_at in messages} - bot_oids
    ai_oids &= commit_oids
    human_oids = commit_oids - ai_oids
    stats: dict[str, object] = {
        "commits": len(commit_oids),
        "window_commits": len(nodes),
        "total_commits": total_commits,
        "commit_oids": tuple(sorted(commit_oids)),
        "author_oids": tuple(sorted(str(oid) for oid in author_oids if oid in commit_oids)),
        "trailer_oids": tuple(sorted(str(oid) for oid in trailer_oids if oid in commit_oids)),
        "ai_oids": tuple(sorted(str(oid) for oid in ai_oids if oid)),
        "human_oids": tuple(sorted(str(oid) for oid in human_oids if oid)),
        "committed_at": committed_at,
        "authored_oids": tuple(
            sorted(
                {
                    str(hit.evidence.get("commit"))
                    for hit in (*author_hits, *trailer_hits)
                    if hit.evidence.get("commit")
                    and (pack.schema_version < 2 or hit.metric_eligibility.get("authorship"))
                }
            )
        ),
        "historical_oids": tuple(
            sorted(
                {
                    str(hit.evidence.get("commit"))
                    for hit in (*author_hits, *trailer_hits)
                    if hit.evidence.get("commit") and hit.is_historical
                }
            )
        ),
    }
    return {
        "author": ChannelResult(
            hits=tuple(author_hits),
            status=status,
            note=note,
            stats=stats,
            failure_kind=outcome.failure_kind,
        ),
        "commit_trailer": ChannelResult(
            hits=tuple(trailer_hits),
            status=status,
            note=note,
            stats=stats,
            failure_kind=outcome.failure_kind,
        ),
        "bot": ChannelResult(
            hits=tuple(bot_hits),
            status=status,
            note="window: last 100 commits; generic bot evidence only",
            failure_kind=outcome.failure_kind,
        ),
    }


_PR_QUERY = """
query(
  $owner: String!, $name: String!, $limit: Int!, $after: String,
  $commentBodies: Boolean!, $reviews: Boolean!
) {
  repository(owner: $owner, name: $name) {
    pullRequests(first: $limit, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number
        createdAt
        headRefName
        bodyText
        author { login }
        labels(first: 20) { nodes { name } }
        comments(first: 50) { nodes { author { login } bodyText @include(if: $commentBodies) } }
        reviews(first: 50) @include(if: $reviews) {
          nodes { author { login } state bodyText @include(if: $commentBodies) }
        }
        commits(first: 100) {
          nodes { commit { oid author { user { login } } } }
        }
      }
    }
  }
  rateLimit { cost limit used remaining resetAt }
}
"""

# Hybrid (git + PR metadata) mode: the clone already holds every commit, so the
# API is asked only for what git cannot see — PR descriptions, authors, head
# branch names, labels and creation dates. No commits, comments or reviews, so
# a 100-PR window stays about one GraphQL point.
_PR_METADATA_QUERY = """
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
      }
    }
  }
  rateLimit { cost limit used remaining resetAt }
}
"""

_ISSUE_QUERY = """
query($owner: String!, $name: String!, $limit: Int!, $commentBodies: Boolean!) {
  repository(owner: $owner, name: $name) {
    issues(first: $limit, orderBy: {field: CREATED_AT, direction: DESC}) {
      nodes {
        number
        createdAt
        author { login }
        assignees(first: 10) { nodes { login } }
        comments(first: 50) { nodes { author { login } bodyText @include(if: $commentBodies) } }
      }
    }
  }
  rateLimit { cost limit used remaining resetAt }
}
"""


def _login(value: object) -> str:
    if not isinstance(value, Mapping):
        return ""
    return str(value.get("login") or "")


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
                "author": _login(author),
                "labels": [
                    str(label.get("name"))
                    for label in (node.get("labels") or {}).get("nodes") or []
                    if isinstance(label, Mapping)
                ],
                "comments": [
                    {
                        "login": _login(comment.get("author")),
                        "body": str(comment.get("bodyText") or ""),
                    }
                    for comment in (node.get("comments") or {}).get("nodes") or []
                    if isinstance(comment, Mapping)
                ],
                "reviews": [
                    {
                        "login": _login(review.get("author")),
                        "body": str(review.get("bodyText") or ""),
                        "state": str(review.get("state") or ""),
                    }
                    for review in (node.get("reviews") or {}).get("nodes") or []
                    if isinstance(review, Mapping)
                ],
                "commits": [
                    {
                        "oid": str((commit.get("commit") or {}).get("oid") or ""),
                        "author": _login(
                            ((commit.get("commit") or {}).get("author") or {}).get("user")
                        ),
                    }
                    for commit in (node.get("commits") or {}).get("nodes") or []
                    if isinstance(commit, Mapping)
                ],
            }
        )
    return prs, "ok", None


def _paged_pr_payload(
    deps: Deps,
    owner: str,
    name: str,
    *,
    limit: int,
    page_size: int,
    comment_bodies: bool,
    reviews: bool,
    on_response: OnResponse,
) -> _GraphQLResponse:
    nodes: list[object] = []
    seen_numbers: set[object] = set()
    cursor: str | None = None
    repository_fields: dict[str, object] | None = None
    while len(nodes) < limit:
        requested = min(page_size, limit - len(nodes))
        outcome = _graphql(
            deps,
            _PR_QUERY,
            {
                "owner": owner,
                "name": name,
                "limit": requested,
                "after": cursor,
                "commentBodies": comment_bodies,
                "reviews": reviews,
            },
            on_response=on_response,
        )
        payload = outcome.payload
        if payload is None or outcome.status != "ok":
            return outcome
        data = payload.get("data")
        repository = data.get("repository") if isinstance(data, Mapping) else None
        if repository is None:
            return _GraphQLResponse(payload, "ok", None)
        if not isinstance(repository, Mapping):
            return _GraphQLResponse(
                None,
                "partial",
                "malformed graphql repository",
                FailureKind.RETRYABLE,
            )
        repository_fields = dict(repository)
        connection = repository.get("pullRequests")
        if not isinstance(connection, Mapping):
            return _GraphQLResponse(
                None,
                "partial",
                "malformed graphql pullRequests",
                FailureKind.RETRYABLE,
            )
        page_nodes = connection.get("nodes")
        if not isinstance(page_nodes, list):
            return _GraphQLResponse(
                None,
                "partial",
                "malformed graphql PR nodes",
                FailureKind.RETRYABLE,
            )
        for node in page_nodes:
            number = node.get("number") if isinstance(node, Mapping) else None
            marker = number if number is not None else id(node)
            if marker in seen_numbers:
                continue
            seen_numbers.add(marker)
            nodes.append(node)
            if len(nodes) >= limit:
                break
        page_info = connection.get("pageInfo")
        if not isinstance(page_info, Mapping) or not page_info.get("hasNextPage"):
            break
        next_cursor = page_info.get("endCursor")
        if not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor:
            return _GraphQLResponse(
                None,
                "partial",
                "invalid graphql PR cursor",
                FailureKind.RETRYABLE,
            )
        cursor = next_cursor
    if repository_fields is None:
        return _GraphQLResponse(
            None,
            "partial",
            "missing graphql repository",
            FailureKind.RETRYABLE,
        )
    repository_fields["pullRequests"] = {"nodes": nodes[:limit]}
    return _GraphQLResponse({"data": {"repository": repository_fields}}, "ok", None)


def _fetch_pr_payload(
    deps: Deps,
    owner: str,
    name: str,
    *,
    limit: int,
    comment_bodies: bool,
    reviews: bool,
    on_response: OnResponse,
) -> _GraphQLResponse:
    outcome = _graphql(
        deps,
        _PR_QUERY,
        {
            "owner": owner,
            "name": name,
            "limit": limit,
            "after": None,
            "commentBodies": comment_bodies,
            "reviews": reviews,
        },
        on_response=on_response,
    )
    if outcome.payload is not None and outcome.status == "ok":
        return outcome
    if outcome.status == "unavailable":
        return outcome
    original = outcome
    for page_size in _PR_FALLBACK_PAGE_SIZES:
        paged = _paged_pr_payload(
            deps,
            owner,
            name,
            limit=limit,
            page_size=page_size,
            comment_bodies=comment_bodies,
            reviews=reviews,
            on_response=on_response,
        )
        if paged.payload is not None and paged.status == "ok":
            return paged
    return original


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
        outcome = _fetch_pr_payload(
            deps,
            owner,
            name,
            limit=limit,
            comment_bodies=pack.requires_comment_bodies,
            # Reviews feed only schema-v2 reviewer rules; v1 packs keep their
            # original query cost and evidence.
            reviews=pack.schema_version >= 2,
            on_response=on_response,
        )
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return ChannelResult(
            status="partial",
            note=_fault_note(exc),
            failure_kind=FailureKind.RETRYABLE,
        )
    payload, gql_status, gql_note = outcome.payload, outcome.status, outcome.note
    if payload is None:
        return ChannelResult(
            status=gql_status,
            note=gql_note,
            failure_kind=outcome.failure_kind,
        )
    prs, status, note = _prs_from_payload(payload)
    if status == "unavailable":
        if gql_status != "ok":
            return ChannelResult(
                status=gql_status,
                note=gql_note,
                failure_kind=outcome.failure_kind,
            )
        return ChannelResult(
            status=status,
            note=note,
            failure_kind=FailureKind.PERMANENT,
        )
    if gql_status != "ok":
        status, note = "partial", gql_note
    else:
        note = "window: most recent 100 PRs"
    hits = match_pr_metadata(pack, prs, agents, forge="github") + match_pr_authors(
        pack, prs, agents, forge="github"
    )
    if channels is not None:
        hits = [hit for hit in hits if hit.channel in channels]
    propagated = propagate_pr_commits(hits, prs)
    commenter_entries = tuple(
        {
            "login": str(comment.get("login") or ""),
            "number": pr["number"],
            "role": "pr_commenter",
            **({"body": comment["body"]} if comment.get("body") else {}),
            **({"observed_at": pr["createdAt"]} if pr.get("createdAt") else {}),
        }
        for pr in prs
        for comment in pr.get("comments") or []
        if isinstance(comment, Mapping) and comment.get("login")
    ) + tuple(
        {
            "login": str(review.get("login") or ""),
            "number": pr["number"],
            "role": "pr_reviewer",
            **({"body": review["body"]} if review.get("body") else {}),
            **({"observed_at": pr["createdAt"]} if pr.get("createdAt") else {}),
        }
        for pr in prs
        for review in pr.get("reviews") or []
        if isinstance(review, Mapping) and review.get("login")
    )
    return ChannelResult(
        hits=tuple(dedupe_hits([*hits, *propagated])),
        status=status,
        note=note,
        failure_kind=outcome.failure_kind,
        stats={
            "propagated_oids": tuple(sorted({h.evidence["commit"] for h in propagated})),
            "ratio_propagated_oids": tuple(
                sorted(
                    {
                        h.evidence["commit"]
                        for h in propagated
                        if pack.schema_version < 2
                        or h.metric_eligibility.get("current_commit_ratio")
                    }
                )
            ),
            "commenter_entries": commenter_entries,
            "created_at": {pr["number"]: pr["createdAt"] for pr in prs if pr.get("createdAt")},
        },
    )


def detect_pr_metadata(
    deps: Deps,
    full_name: str,
    pack: Pack,
    *,
    limit: int = 100,
    agents: frozenset[str] | None = None,
    on_response: OnResponse = None,
) -> ChannelResult:
    """PR descriptions, authors, head branches and labels — the hybrid-mode sidecar.

    Emits ``branch``, ``label`` and ``pr_metadata`` hits plus ``created_at`` per
    PR number, which dates PR evidence a local clone finds undated. Commit
    propagation is left to the local PR walk, which already holds the commits.
    """
    owner, _, name = full_name.partition("/")
    try:
        outcome = _graphql(
            deps,
            _PR_METADATA_QUERY,
            {"owner": owner, "name": name, "limit": limit},
            on_response=on_response,
        )
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return ChannelResult(
            status="partial", note=_fault_note(exc), failure_kind=FailureKind.RETRYABLE
        )
    if outcome.payload is None:
        return ChannelResult(
            status=outcome.status, note=outcome.note, failure_kind=outcome.failure_kind
        )
    prs, status, note = _prs_from_payload(outcome.payload)
    if status == "unavailable":
        return ChannelResult(
            status=outcome.status if outcome.status != "ok" else status,
            note=outcome.note if outcome.status != "ok" else note,
            failure_kind=outcome.failure_kind or FailureKind.PERMANENT,
        )
    if outcome.status != "ok":
        status, note = "partial", outcome.note
    else:
        note = f"window: most recent {limit} PRs (metadata only)"
    hits = match_pr_metadata(pack, prs, agents, forge="github") + match_pr_authors(
        pack, prs, agents, forge="github"
    )
    return ChannelResult(
        hits=tuple(dedupe_hits(hits)),
        status=status,
        note=note,
        failure_kind=outcome.failure_kind,
        stats={
            "prs": len(prs),
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
        outcome = _graphql(
            deps,
            _ISSUE_QUERY,
            {
                "owner": owner,
                "name": name,
                "limit": limit,
                "commentBodies": pack.requires_comment_bodies,
            },
            on_response=on_response,
        )
    except (PartialResultsError, ThrottledError, httpx.HTTPError) as exc:
        return ChannelResult(
            status="partial",
            note=_fault_note(exc),
            failure_kind=FailureKind.RETRYABLE,
        )
    payload, status, note = outcome.payload, outcome.status, outcome.note
    if payload is None:
        return ChannelResult(
            status=status,
            note=note,
            failure_kind=outcome.failure_kind,
        )
    repository = (payload.get("data") or {}).get("repository")
    if repository is None:
        if status != "ok":
            return ChannelResult(
                status=status,
                note=note,
                failure_kind=outcome.failure_kind,
            )
        return ChannelResult(
            status="unavailable",
            note="repo not found",
            failure_kind=FailureKind.PERMANENT,
        )
    entries: list[dict] = list(extra_entries)
    created_at: dict[object, str] = {}
    for node in (repository.get("issues") or {}).get("nodes") or []:
        if not isinstance(node, Mapping):
            continue
        number = node.get("number")
        if node.get("createdAt"):
            created_at[number] = str(node["createdAt"])
        author = node.get("author")
        observed_at = str(node.get("createdAt") or "")
        if isinstance(author, Mapping) and author.get("login"):
            entries.append(
                {
                    "login": str(author["login"]),
                    "number": number,
                    "role": "author",
                    "observed_at": observed_at,
                }
            )
        for assignee in (node.get("assignees") or {}).get("nodes") or []:
            if isinstance(assignee, Mapping) and assignee.get("login"):
                entries.append(
                    {
                        "login": str(assignee["login"]),
                        "number": number,
                        "role": "assignee",
                        "observed_at": observed_at,
                    }
                )
        for comment in (node.get("comments") or {}).get("nodes") or []:
            comment_author = comment.get("author") if isinstance(comment, Mapping) else None
            if isinstance(comment_author, Mapping) and comment_author.get("login"):
                entries.append(
                    {
                        "login": str(comment_author["login"]),
                        "number": number,
                        "role": "commenter",
                        **(
                            {"body": str(comment.get("bodyText"))}
                            if comment.get("bodyText")
                            else {}
                        ),
                        "observed_at": observed_at,
                    }
                )
    return ChannelResult(
        hits=tuple(match_issue_participants(pack, entries, agents, forge="github")),
        status=status,
        note=note if status != "ok" else "window: most recent 100 issues; PR comments included",
        stats={"created_at": created_at},
        failure_kind=outcome.failure_kind,
    )
