from __future__ import annotations

import re
import subprocess
import time
from collections.abc import Mapping
from dataclasses import replace

from detect import phase_metrics
from detect.attribution import (
    Hit,
    dedupe_hits,
    hit_from_rule,
    is_noise_commit,
    match_author_identities,
    match_bots,
    match_branches,
    match_commit_messages,
    match_files,
    match_hidden_refs,
)
from detect.channels import ChannelResult
from detect.content_attribution import CONTENT_CHANNEL, classify_agents_md
from detect.gitio import (
    CommitRecord,
    GitError,
    GitRepo,
    fetch_blobs,
    fetch_hidden_ref_records,
    fetch_pr_refs,
    git_error_tail,
    list_hidden_refs,
    list_tree_entries,
    newest_pr_refs,
    parse_merge_branches,
    read_commits,
    read_log,
    read_pr_refs_snapshot,
    remote_refs,
    resolve_head,
    retry_call,
)
from detect.packs import Pack
from detect.repo_walk import RepoWalkSession, WalkAnomaly, walk_windows_with_records
from detect.structured import content_candidates, evaluate_file_rules
from enrich.trees_first import FilePresence
from lib.cancellation import RunCancelled

CONTENT_PROBE_LIMIT = 5
_GIT_FAILURES = (GitError, subprocess.TimeoutExpired)
_NOREPLY = re.compile(r"^(?:\d+\+)?(?P<login>[^@+]+)@users\.noreply\.github\.com$")


def _login_from_email(email: str) -> str:
    match = _NOREPLY.match(email or "")
    return match.group("login") if match else ""


def _person(record: CommitRecord, name: str, email: str, role: str) -> dict[str, str]:
    return {
        "login": _login_from_email(email),
        "name": name,
        "email": email,
        "commit": record.sha,
        "role": role,
        "observed_at": record.committed_at,
    }


def _entries(record: CommitRecord) -> tuple[dict[str, str], dict[str, str]]:
    return (
        _person(record, record.author_name, record.author_email, "author"),
        _person(record, record.committer_name, record.committer_email, "committer"),
    )


def _session_blob_contents(
    session: RepoWalkSession, paths: list[str], by_path: Mapping[str, str]
) -> dict[str, str | None] | None:
    """Blob contents via the shared session, or None when a fallback is needed."""
    contents: dict[str, str | None] = {}
    try:
        for path in paths:
            if path == ".gitignore" and path not in by_path:
                contents[path] = None
                continue
            data = session.blob(f"HEAD:{path}")
            if data is None:
                return None
            contents[path] = data.decode("utf-8", errors="replace")
    except RunCancelled:
        raise
    except Exception:
        return None
    return contents


def detect_files_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    session: RepoWalkSession | None = None,
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
    generic_paths = sorted(
        path for path in paths if path.rsplit("/", 1)[-1] in pack.generic_weights
    )[:CONTENT_PROBE_LIMIT]
    probe_order = sorted(
        {hit.evidence["path"] for hit in hits if hit.evidence.get("source") == "tree"}
    )[:CONTENT_PROBE_LIMIT]
    structured_paths: tuple[str, ...] = ()
    candidate_capped = False
    if pack.schema_version >= 2:
        structured_paths, candidate_capped = content_candidates(pack, paths)
        probe_order = list(structured_paths)
    requested = list(dict.fromkeys([".gitignore", *probe_order, *generic_paths]))
    contents: dict[str, str | None] | None = None
    if session is not None:
        contents = _session_blob_contents(session, requested, by_path)
    if contents is None:
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
        contents = repo.read_blobs(requested)
    ignore_text = contents.get(".gitignore")
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
    for path in [*probe_paths, *generic_paths]:
        text = contents.get(path)
        if text is None:
            continue
        for hit in hits:
            if hit.evidence.get("path") == path:
                hit.evidence.update({"size": len(text), "empty": not text.strip()})
    content_diagnostics: list[dict[str, object]] = []
    if pack.schema_version >= 2:
        bounded_contents: dict[str, str | None] = {}
        for path in structured_paths:
            text = contents.get(path)
            if text is None:
                bounded_contents[path] = None
                content_diagnostics.append(
                    {"path": path, "kind": "fetch_failure", "note": "blob unavailable"}
                )
            elif len(text.encode("utf-8")) > pack.content_byte_limit:
                bounded_contents[path] = None
                content_diagnostics.append(
                    {
                        "path": path,
                        "kind": "parse_failure",
                        "note": f"content exceeds {pack.content_byte_limit}-byte cap",
                    }
                )
            else:
                bounded_contents[path] = text
        structured_matches, predicate_diagnostics = evaluate_file_rules(
            pack, paths, bounded_contents, source="tree", agents=agents
        )
        hits = [
            hit
            for hit in hits
            if not (hit.rule_id is not None and hit.evidence.get("source") == "tree")
        ]
        for matched in structured_matches:
            hit = hit_from_rule(
                matched.rule,
                "file",
                matched.evidence,
                forge="local",
                role=matched.rule.semantics.role or "repository_file",
            )
            if hit is not None:
                hits.append(hit)
        content_diagnostics.extend(item.as_dict() for item in predicate_diagnostics)
    if pack.schema_version < 2:
        known = frozenset(pack.agents) if agents is None else frozenset(agents)
        for path in generic_paths:
            text = contents.get(path)
            if not text or not text.strip():
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
        status="partial" if candidate_capped else "ok",
        note=(
            "local clone; tree + .gitignore; structured candidate cap "
            f"{pack.content_candidate_limit}"
            if candidate_capped
            else "local clone; tree + .gitignore"
        ),
        stats={
            "content_candidates": len(structured_paths),
            "content_candidate_cap_reached": candidate_capped,
            "content_diagnostics": tuple(content_diagnostics),
        },
    )


def _walked_record(
    session: RepoWalkSession, walked: Mapping[str, CommitRecord], sha: str
) -> CommitRecord:
    record = walked.get(sha)
    if record is None:
        record = session.record(sha)
    if record is None:
        raise WalkAnomaly(f"commit {sha} is missing")
    return record


def detect_history_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    limit: int = 100,
    session: RepoWalkSession | None = None,
) -> dict[str, ChannelResult]:
    keys = ("author", "commit_trailer", "bot")
    records: tuple[CommitRecord, ...] | None = None
    if session is not None:
        try:
            shas, walked = session.window(resolve_head(repo), limit)
            records = tuple(_walked_record(session, walked, sha) for sha in shas)
        except RunCancelled:
            raise
        except Exception:
            records = None
    if records is None:
        try:
            records = read_log(repo, limit=limit)
        except _GIT_FAILURES:
            return {
                key: ChannelResult(status="unavailable", note="empty repository") for key in keys
            }
    identities: list[dict[str, str]] = []
    bot_candidates: list[dict[str, str]] = []
    messages: list[tuple[str, str, str]] = []
    committed_at: dict[str, str] = {}
    for record in records:
        author_entry, committer_entry = _entries(record)
        bot_candidates.extend((author_entry, committer_entry))
        if record.committed_at:
            committed_at[record.sha] = record.committed_at
        if is_noise_commit(record.message):
            continue
        messages.append((record.sha, record.message, record.committed_at))
        identities.extend((author_entry, committer_entry))
    author_hits = match_author_identities(pack, identities, agents, forge="local")
    trailer_hits = match_commit_messages(pack, messages, agents, forge="local")
    bot_hits = match_bots(pack, bot_candidates, agents, forge="local")
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
    commit_oids = {sha for sha, _message, _observed_at in messages} - bot_oids
    ai_oids &= commit_oids
    human_oids = commit_oids - ai_oids
    stats: dict[str, object] = {
        "commits": len(commit_oids),
        "window_commits": len(records),
        "total_commits": None,
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
    gate: object | None = None,
    refs: Mapping[int, str] | None = None,
    gate_reserved: bool = False,
    session: RepoWalkSession | None = None,
    pr_limit: int | None = None,
) -> ChannelResult:
    empty_stats = {"propagated_oids": (), "commenter_entries": (), "created_at": {}}
    resumed_note = ""
    metrics = phase_metrics.current()

    def fetch_and_list() -> dict[int, str]:
        return fetch_pr_refs(
            repo,
            depth=depth,
            gate=gate,
            refs=refs,
            gate_reserved=gate_reserved,
            limit=pr_limit,
        )

    try:
        refs = retry_call(fetch_and_list, attempts=attempts, base_delay=retry_delay)
    except _GIT_FAILURES as exc:
        # A snapshot is a resume path only: after a failed fresh fetch it
        # keeps the channel alive, but a successful fetch always wins.
        snapshot = read_pr_refs_snapshot(repo)
        if not snapshot:
            return ChannelResult(
                status="partial",
                note=f"pull refs fetch failed: {git_error_tail(exc)}",
                stats=empty_stats,
            )
        refs = newest_pr_refs(snapshot, pr_limit)
        resumed_note = f"resumed from persisted PR ref snapshot: {git_error_tail(exc)}"
        if metrics is not None:
            metrics.refs_count = len(refs)
    if not refs:
        return ChannelResult(status="ok", note="no pull requests found", stats=empty_stats)
    walk_started = time.monotonic()
    walk_failures: dict[int, str] = {}

    def record_walk_failure(number: int, exc: BaseException) -> None:
        walk_failures[number] = git_error_tail(exc)

    try:
        walks, walked_records = walk_windows_with_records(
            repo,
            refs,
            depth=depth,
            session=session,
            on_failure=record_walk_failure,
        )
    except _GIT_FAILURES as exc:
        if metrics is not None:
            metrics.walk_ms = phase_metrics.elapsed_ms(walk_started)
        return ChannelResult(
            status="partial",
            note=f"pull refs walk failed: {git_error_tail(exc)}",
            stats=empty_stats,
        )
    sha_to_pr: dict[str, int] = {}
    for number in sorted(walks):
        for sha in walks[number]:
            sha_to_pr.setdefault(sha, number)
    records = {sha: walked_records[sha] for sha in sha_to_pr if sha in walked_records}
    missing = [sha for sha in sorted(sha_to_pr) if sha not in walked_records]
    if missing:
        try:
            records.update(read_commits(repo, missing))
        except _GIT_FAILURES as exc:
            if metrics is not None:
                metrics.walk_ms = phase_metrics.elapsed_ms(walk_started)
            return ChannelResult(
                status="partial",
                note=f"commit read failed: {git_error_tail(exc)}",
                stats=empty_stats,
            )
    if metrics is not None:
        metrics.walk_ms = phase_metrics.elapsed_ms(walk_started)
    hits: list[Hit] = []
    for sha, number in sorted(sha_to_pr.items(), key=lambda item: (item[1], item[0])):
        record = records.get(sha)
        if record is None:
            continue
        matches = match_author_identities(pack, list(_entries(record)), agents, forge="local")
        matches += match_commit_messages(
            pack, [(sha, record.message, record.committed_at)], agents, forge="local"
        )
        for hit in dedupe_hits(matches):
            if hit.rule_id and not (
                hit.metric_eligibility.get("authorship")
                or hit.metric_eligibility.get("generated_code")
            ):
                continue
            hits.append(
                replace(
                    hit,
                    channel="pr_metadata",
                    evidence={"pr": number, "commit": sha, "propagated": True},
                )
            )
    hits = dedupe_hits(hits)
    propagated = tuple(sorted({hit.evidence["commit"] for hit in hits}))
    note = f"local PR refs; depth {depth}"
    if pr_limit is not None:
        note = f"local PR refs (newest {pr_limit}); depth {depth}"
    if resumed_note:
        note = f"{note}; {resumed_note}"
    if walk_failures:
        number, detail = next(iter(walk_failures.items()))
        note = f"{note}; {len(walk_failures)} PR walk(s) failed (e.g. #{number}: {detail})"
    return ChannelResult(
        hits=tuple(hits),
        status="partial" if walk_failures else "ok",
        note=note,
        stats={
            **empty_stats,
            "propagated_oids": propagated,
            "ratio_propagated_oids": tuple(
                sorted(
                    {
                        hit.evidence["commit"]
                        for hit in hits
                        if pack.schema_version < 2
                        or hit.metric_eligibility.get("current_commit_ratio")
                    }
                )
            ),
        },
    )


def _remote_head_refs(repo: GitRepo) -> dict[str, str] | None:
    """Remote head refs, or None when the listing failed (degrade quietly)."""
    try:
        return remote_refs(repo).head_refs
    except Exception:
        return None


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
    note = f"window: last {limit} commits; merge messages only"
    if pack.branches:
        # Agent-named branches linger on the remote even when nothing was
        # merged, so the head refs catch adoption the merge messages miss.
        head_refs = _remote_head_refs(repo)
        if head_refs is not None:
            for name in sorted(head_refs):
                branch = name.removeprefix("refs/heads/")
                for hit in match_branches(pack, [branch], agents):
                    hits.append(
                        Hit(
                            hit.agent,
                            "branch",
                            {"pr": None, "head": branch, "match": hit.evidence["match"]},
                        )
                    )
            note = f"window: last {limit} commits; merge messages + remote branch heads"
    return ChannelResult(hits=tuple(dedupe_hits(hits)), status="ok", note=note)


def detect_hidden_refs_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
) -> ChannelResult:
    namespaces = pack.hidden_ref_namespaces()
    if not namespaces:
        return ChannelResult(status="skipped", note="pack declares no hidden-ref namespaces")
    try:
        refs = list_hidden_refs(repo, namespaces, limit=pack.content_candidate_limit)
    except _GIT_FAILURES as exc:
        return ChannelResult(status="partial", note=f"hidden refs: {git_error_tail(exc)}")
    entries: list[dict[str, object]] = [
        {"ref": name, "commit": sha, "reachability": "remote_hidden_ref"}
        for name, sha in refs.items()
    ]
    note = "targeted remote hidden-ref namespaces"
    status = "ok"
    identity_rules = [
        rule
        for rule in pack.rules_for("hidden_ref")
        if isinstance(rule.match.get("identity"), Mapping)
    ]
    if identity_rules and refs:
        try:
            records = fetch_hidden_ref_records(repo, refs)
        except _GIT_FAILURES as exc:
            records = {}
            status = "partial"
            note = f"{note}; tip identities unavailable: {git_error_tail(exc)}"
        for entry in entries:
            record = records.get(str(entry["commit"]))
            if record is None:
                continue
            entry.update(
                {
                    "author_name": record.author_name,
                    "author_email": record.author_email,
                    "committer_name": record.committer_name,
                    "committer_email": record.committer_email,
                    "observed_at": record.committed_at,
                }
            )
    return ChannelResult(
        hits=tuple(match_hidden_refs(pack, entries, agents, forge="local")),
        status=status,
        note=note,
        stats={"refs": len(refs), "namespaces": namespaces},
    )
