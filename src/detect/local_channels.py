from __future__ import annotations

import re
import subprocess

from detect.attribution import (
    Hit,
    dedupe_hits,
    is_noise_commit,
    match_author_identities,
    match_bots,
    match_branches,
    match_commit_messages,
    match_files,
)
from detect.channels import ChannelResult
from detect.gitio import (
    CommitRecord,
    GitError,
    GitRepo,
    fetch_blobs,
    fetch_pr_refs,
    git_error_tail,
    list_pr_refs,
    list_tree_entries,
    parse_merge_branches,
    read_blob,
    read_commits,
    read_log,
    retry_call,
    walk_pr_shas,
)
from detect.packs import Pack
from enrich.trees_first import FilePresence

CONTENT_PROBE_LIMIT = 5
_GIT_FAILURES = (GitError, subprocess.TimeoutExpired)
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
        entries = list_tree_entries(repo)
    except _GIT_FAILURES:
        return ChannelResult(status="unavailable", note="empty repository")
    paths = [path for path, _oid in entries]
    by_path = dict(entries)
    presence = FilePresence(
        repo_full_name="", paths=frozenset(paths), truncated=False, source="tree"
    )
    hits = list(match_files(pack, presence, agents))
    probe_order = sorted(
        {hit.evidence["path"] for hit in hits if hit.evidence.get("source") == "tree"}
    )[:CONTENT_PROBE_LIMIT]
    needed: list[str] = []
    ignore_oid = by_path.get(".gitignore")
    if ignore_oid is not None:
        needed.append(ignore_oid)
    for path in probe_order:
        oid = by_path.get(path)
        if oid is not None and oid not in needed:
            needed.append(oid)
    if needed:
        # One round trip for .gitignore plus the content probes; a failure
        # degrades to the per-read lazy fetches rather than losing the channel.
        try:
            fetch_blobs(repo, needed)
        except _GIT_FAILURES:
            pass
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
    except _GIT_FAILURES:
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


def detect_pr_commits_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    depth: int = 100,
    attempts: int = 4,
    retry_delay: float = 1.0,
    walk_workers: int = 8,
) -> ChannelResult:
    empty_stats = {"propagated_oids": (), "commenter_entries": (), "created_at": {}}

    def fetch_and_list() -> dict[int, str]:
        fetch_pr_refs(repo, depth=depth)
        return list_pr_refs(repo)

    try:
        refs = retry_call(fetch_and_list, attempts=attempts, base_delay=retry_delay)
    except _GIT_FAILURES as exc:
        return ChannelResult(
            status="partial",
            note=f"pull refs fetch failed: {git_error_tail(exc)}",
            stats=empty_stats,
        )
    if not refs:
        return ChannelResult(status="ok", note="no pull requests found", stats=empty_stats)
    try:
        walks = walk_pr_shas(repo, refs, depth=depth, workers=walk_workers)
    except _GIT_FAILURES as exc:
        return ChannelResult(
            status="partial",
            note=f"pull refs walk failed: {git_error_tail(exc)}",
            stats=empty_stats,
        )
    sha_to_pr: dict[str, int] = {}
    for number in sorted(walks):
        for sha in walks[number]:
            sha_to_pr.setdefault(sha, number)
    try:
        records = read_commits(repo, sorted(sha_to_pr))
    except GitError:
        records = {}
    hits: list[Hit] = []
    for sha, number in sorted(sha_to_pr.items(), key=lambda item: (item[1], item[0])):
        record = records.get(sha)
        if record is None:
            continue
        matches = match_author_identities(pack, list(_entries(record)), agents)
        matches += match_commit_messages(pack, [(sha, record.message)], agents)
        for hit in dedupe_hits(matches):
            hits.append(
                Hit(hit.agent, "pr_metadata", {"pr": number, "commit": sha, "propagated": True})
            )
    hits = dedupe_hits(hits)
    propagated = tuple(sorted({hit.evidence["commit"] for hit in hits}))
    return ChannelResult(
        hits=tuple(hits),
        status="ok",
        note=f"local PR refs; depth {depth}",
        stats={**empty_stats, "propagated_oids": propagated},
    )


def detect_branch_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    limit: int = 100,
) -> ChannelResult:
    try:
        records = read_log(repo, limit=limit)
    except _GIT_FAILURES:
        return ChannelResult(status="unavailable", note="empty repository")
    pairs = parse_merge_branches((record.sha, record.message) for record in records)
    hits: list[Hit] = []
    for number, head in pairs:
        for hit in match_branches(pack, [head], agents):
            hits.append(
                Hit(
                    hit.agent,
                    "branch",
                    {"pr": number, "head": head, "match": hit.evidence["match"]},
                )
            )
    return ChannelResult(
        hits=tuple(dedupe_hits(hits)),
        status="ok",
        note=f"window: last {limit} commits; merge messages only",
    )
