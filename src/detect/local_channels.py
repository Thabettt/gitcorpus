from __future__ import annotations

import re

from detect.attribution import (
    dedupe_hits,
    is_noise_commit,
    match_author_identities,
    match_bots,
    match_commit_messages,
    match_files,
)
from detect.channels import ChannelResult
from detect.gitio import CommitRecord, GitError, GitRepo, list_tree, read_blob, read_log
from detect.packs import Pack
from enrich.trees_first import FilePresence

CONTENT_PROBE_LIMIT = 5
_NOREPLY = re.compile(r"^(?:\d+\+)?(?P<login>[^@+]+)@users\.noreply\.github\.com$")


def _login_from_email(email: str) -> str:
    match = _NOREPLY.match(email or "")
    return match.group("login") if match else ""


def _person(record: CommitRecord, name: str, email: str) -> dict[str, str]:
    return {"login": _login_from_email(email), "name": name, "email": email, "commit": record.sha}


def _entries(record: CommitRecord) -> tuple[dict[str, str], dict[str, str]]:
    return (
        _person(record, record.author_name, record.author_email),
        _person(record, record.committer_name, record.committer_email),
    )


def detect_files_local(
    repo: GitRepo, pack: Pack, agents: frozenset[str] | None = None
) -> ChannelResult:
    try:
        paths = list_tree(repo)
    except GitError:
        return ChannelResult(status="unavailable", note="empty repository")
    presence = FilePresence(
        repo_full_name="", paths=frozenset(paths), truncated=False, source="tree"
    )
    hits = list(match_files(pack, presence, agents))
    ignore_text = read_blob(repo, ".gitignore")
    if ignore_text:
        ignored = tuple(
            line.strip()
            for line in ignore_text.splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
        if ignored:
            hits.extend(
                match_files(
                    pack,
                    FilePresence("", frozenset(ignored), False, "gitignore"),
                    agents,
                )
            )
    hits = dedupe_hits(hits)
    probe_paths = sorted(
        {hit.evidence["path"] for hit in hits if hit.evidence.get("source") == "tree"}
    )[:CONTENT_PROBE_LIMIT]
    for path in probe_paths:
        text = read_blob(repo, path)
        if text is None:
            continue
        for hit in hits:
            if hit.evidence.get("path") == path:
                hit.evidence.update({"size": len(text), "empty": not text.strip()})
    return ChannelResult(hits=tuple(hits), status="ok", note="local clone; tree + .gitignore")


def detect_history_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    limit: int = 100,
) -> dict[str, ChannelResult]:
    keys = ("author", "commit_trailer", "bot")
    try:
        records = read_log(repo, limit=limit)
    except GitError:
        return {key: ChannelResult(status="unavailable", note="empty repository") for key in keys}
    identities: list[dict[str, str]] = []
    bot_candidates: list[dict[str, str]] = []
    messages: list[tuple[str, str]] = []
    committed_at: dict[str, str] = {}
    for record in records:
        author_entry, committer_entry = _entries(record)
        bot_candidates.extend((author_entry, committer_entry))
        if record.committed_at:
            committed_at[record.sha] = record.committed_at
        if is_noise_commit(record.message):
            continue
        messages.append((record.sha, record.message))
        identities.extend((author_entry, committer_entry))
    author_hits = match_author_identities(pack, identities, agents)
    trailer_hits = match_commit_messages(pack, messages, agents)
    bot_hits = match_bots(pack, bot_candidates, agents)
    ai_oids = {hit.evidence.get("commit") for hit in (*author_hits, *trailer_hits)}
    bot_oids = {hit.evidence.get("commit") for hit in bot_hits}
    commit_oids = {sha for sha, _ in messages} - bot_oids
    human_oids = commit_oids - ai_oids
    stats: dict[str, object] = {
        "commits": len(commit_oids),
        "ai_oids": tuple(sorted(str(oid) for oid in ai_oids if oid)),
        "human_oids": tuple(sorted(str(oid) for oid in human_oids if oid)),
        "committed_at": committed_at,
    }
    note = f"window: last {limit} commits"
    return {
        "author": ChannelResult(hits=tuple(author_hits), status="ok", note=note, stats=stats),
        "commit_trailer": ChannelResult(
            hits=tuple(trailer_hits), status="ok", note=note, stats=stats
        ),
        "bot": ChannelResult(
            hits=tuple(bot_hits),
            status="ok",
            note="generic bot evidence only (QA; never counted as adoption)",
        ),
    }
