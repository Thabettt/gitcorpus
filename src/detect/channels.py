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


def _gitignore_paths(
    deps: Deps, full_name: str, *, on_response: OnResponse
) -> tuple[tuple[str, ...], str | None]:
    text, error = _raw_text(
        deps, f"{API_BASE}/repos/{full_name}/contents/.gitignore", on_response=on_response
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
        probed_paths = _probe_missing_paths(
            deps, full_name, pack, presence, on_response=on_response
        )
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
        {hit.evidence["path"] for hit in hits if hit.evidence.get("source") == "tree"}
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
