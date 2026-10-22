from __future__ import annotations

import inspect
import subprocess
from dataclasses import replace
from pathlib import Path

import detect.phase_metrics as phase_metrics
import detect.repo_walk as repo_walk
from detect.gitio import (
    CommitRecord,
    GitError,
    GitRepo,
    RemoteRefs,
    parse_log,
    read_pr_refs_snapshot,
    write_pr_refs_snapshot,
)
from detect.local_channels import (
    detect_branch_local,
    detect_files_local,
    detect_history_local,
    detect_pr_commits_local,
)
from detect.packs import Pack, Pattern
from detect.repo_walk import WalkAnomaly, reset_verification

PACK = Pack(
    version="v1",
    agents={
        "Claude Code": "https://claude.com",
        "Cursor": "https://cursor.com",
        "Generic": "https://agents.md",
    },
    authors=(Pattern(r"noreply@anthropic\.com", "Claude Code"), Pattern("cursoragent", "Cursor")),
    files=(
        Pattern(r"CLAUDE\.md", "Claude Code"),
        Pattern(r"\.cursor/", "Cursor"),
        Pattern(r"AGENTS\.md", "Generic"),
    ),
    branches=(Pattern("claude/", "Claude Code"), Pattern("cursor/", "Cursor")),
    labels=(Pattern("ai-generated", "Claude Code"),),
    bots=(Pattern(r"dependabot\[bot\]", "dependabot"),),
    generic_weights={"AGENTS.md": 0.3},
    exclusions=frozenset({"CONVENTIONS.md"}),
)


class FakeRepo(GitRepo):
    def __init__(self, handler, dest: Path | None = None):
        super().__init__(dest or Path())
        self._handler = handler
        self.calls: list[tuple[str, ...]] = []
        self.stdins: list[bytes | None] = []
        self.env_extras: list[dict[str, str] | None] = []

    def git(
        self,
        *args: str,
        timeout: float | None = None,
        stdin=None,
        env_extra: dict[str, str] | None = None,
    ) -> str:
        self.calls.append(args)
        self.stdins.append(stdin.read() if stdin is not None else None)
        self.env_extras.append(env_extra)
        result = self._handler(args)
        if result is None:
            raise GitError(list(args), 128, "fake")
        return result

    def read_blobs(self, paths):
        self.calls.append(("read_blobs", *paths))
        return {path: self._handler(("show", f"HEAD:{path}")) for path in paths}


def _repo_dir(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _tree(handler_args_value: str):
    def handler(args):
        if args[0] == "ls-tree":
            return handler_args_value
        return None

    return handler


_FILE_OIDS = {
    "CLAUDE.md": "a" * 40,
    ".cursor/rules/x.md": "b" * 40,
    "AGENTS.md": "c" * 40,
    "CONVENTIONS.md": "d" * 40,
    ".gitignore": "e" * 40,
}

_FILE_BLOBS = {
    ".gitignore": ".cursor/\n# comment\n",
    "CLAUDE.md": "# guidance\n",
    ".cursor/rules/x.md": "rules\n",
    "AGENTS.md": "# agents\n",
}


def _files_handler(blobs):
    files = ["CLAUDE.md", ".cursor/rules/x.md", "AGENTS.md", "CONVENTIONS.md", ".gitignore"]

    def handler(args):
        if args[0] == "ls-tree":
            return "".join(f"100644 blob {_FILE_OIDS[path]}\t{path}\n" for path in files)
        if args[0] == "show":
            return blobs.get(args[1][5:])
        if "fetch" in args:
            return ""
        return None

    return handler


class _BlobSession:
    def __init__(self, contents=None, *, error=None):
        self.contents = {
            f"HEAD:{path}": text.encode("utf-8") for path, text in (contents or {}).items()
        }
        self.error = error
        self.requests: list[str] = []

    def blob(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return self.contents.get(request)


def test_detect_files_local_matches_tree_gitignore_and_probes_content():
    files = ["CLAUDE.md", ".cursor/rules/x.md", "AGENTS.md", "CONVENTIONS.md", ".gitignore"]
    blobs = {".gitignore": ".cursor/\n# comment\n", "CLAUDE.md": "# guidance\n"}

    def handler(args):
        if args[0] == "ls-tree":
            return "".join(f"100644 blob {_FILE_OIDS[path]}\t{path}\n" for path in files)
        if args[0] == "show":
            return blobs.get(args[1][5:])
        if "fetch" in args:
            return ""
        return None

    repo = FakeRepo(handler)
    result = detect_files_local(repo, PACK)
    assert result.status == "ok"
    by_key = {(h.agent, h.evidence["path"]): h for h in result.hits}
    assert ("Claude Code", "CLAUDE.md") in by_key
    assert ("Cursor", ".cursor/rules/x.md") in by_key
    assert ("Generic", "AGENTS.md") in by_key
    assert ("Claude Code", "CONVENTIONS.md") not in by_key
    assert ("Cursor", ".cursor/") in by_key
    assert by_key[("Cursor", ".cursor/")].evidence["source"] == "gitignore"
    assert by_key[("Claude Code", "CLAUDE.md")].evidence["size"] == len("# guidance\n")
    assert by_key[("Claude Code", "CLAUDE.md")].evidence["empty"] is False
    batched = [stdin for stdin in repo.stdins if stdin is not None]
    assert len(batched) == 1
    assert set(batched[0].decode().split()) == {
        _FILE_OIDS[".gitignore"],
        _FILE_OIDS[".cursor/rules/x.md"],
        _FILE_OIDS["AGENTS.md"],
        _FILE_OIDS["CLAUDE.md"],
    }


def test_detect_files_local_fetch_failure_falls_back_to_lazy_reads():
    def handler(args):
        if args[0] == "ls-tree":
            return f"100644 blob {'a' * 40}\tCLAUDE.md\n"
        if args[0] == "fetch":
            return None
        if args[0] == "show":
            return "# guidance\n" if args[1] == "HEAD:CLAUDE.md" else None
        return None

    result = detect_files_local(FakeRepo(handler), PACK)
    assert result.status == "ok"
    assert {h.evidence["path"] for h in result.hits} == {"CLAUDE.md"}


def test_detect_files_local_reports_empty_repository():
    result = detect_files_local(FakeRepo(lambda args: None if args[0] == "ls-tree" else ""), PACK)
    assert result.status == "unavailable"


def test_detect_files_local_reads_blobs_through_the_session():
    repo = FakeRepo(_files_handler(_FILE_BLOBS))
    session = _BlobSession(_FILE_BLOBS)
    result = detect_files_local(repo, PACK, session=session)
    baseline = detect_files_local(FakeRepo(_files_handler(_FILE_BLOBS)), PACK)
    assert result == baseline
    assert session.requests == [
        "HEAD:.gitignore",
        "HEAD:.cursor/rules/x.md",
        "HEAD:AGENTS.md",
        "HEAD:CLAUDE.md",
    ]
    assert repo.calls == [("ls-tree", "-r", "HEAD")]


def test_detect_files_local_falls_back_when_the_session_blob_is_missing():
    repo = FakeRepo(_files_handler(_FILE_BLOBS))
    session = _BlobSession()
    result = detect_files_local(repo, PACK, session=session)
    baseline = detect_files_local(FakeRepo(_files_handler(_FILE_BLOBS)), PACK)
    assert result == baseline
    assert session.requests == ["HEAD:.gitignore"]
    assert any(call[0] == "read_blobs" for call in repo.calls)


def test_detect_files_local_falls_back_when_the_session_raises():
    repo = FakeRepo(_files_handler(_FILE_BLOBS))
    session = _BlobSession(error=WalkAnomaly("cat-file wedged"))
    result = detect_files_local(repo, PACK, session=session)
    baseline = detect_files_local(FakeRepo(_files_handler(_FILE_BLOBS)), PACK)
    assert result == baseline
    assert any(call[0] == "read_blobs" for call in repo.calls)


_LOGGED = (
    "a1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
    "\x1f2026-01-02T03:04:05+00:00\x1ffeat: work\n\n"
    "Co-authored-by: Claude <noreply@anthropic.com>\x1e"
    "\na2\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
    "\x1f2026-01-03T00:00:00+00:00\x1ffeat: claude commit\x1e"
    "\na3\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
    "\x1f2026-01-04T00:00:00+00:00\x1fMerge pull request #5 from octo/claude/x\x1e"
    "\na4\x1fdependabot[bot]\x1f49699333+dependabot[bot]@users.noreply.github.com"
    "\x1fdependabot[bot]\x1f49699333+dependabot[bot]@users.noreply.github.com"
    "\x1f2026-01-05T00:00:00+00:00\x1fchore(deps): bump serde\x1e"
)


def test_detect_history_local_author_trailer_bot_and_stats():
    repo = FakeRepo(lambda args: _LOGGED if args[0] == "log" else None)
    results = detect_history_local(repo, PACK, limit=100)
    author, trailer, bot = results["author"], results["commit_trailer"], results["bot"]
    assert {h.evidence["commit"] for h in author.hits} == {"a2"}
    assert trailer.hits and trailer.hits[0].evidence["commit"] == "a1"
    assert {h.agent for h in bot.hits} == {"dependabot"}
    stats = author.stats
    assert stats["commits"] == 2  # a1, a2 — a3 is noise, a4 is a bot
    assert set(stats["ai_oids"]) == {"a1", "a2"}
    assert stats["human_oids"] == ()
    assert stats["committed_at"]["a2"] == "2026-01-03T00:00:00+00:00"


_BOT_AI_OVERLAP_LOG = (
    "b1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
    "\x1f2026-02-01T00:00:00+00:00\x1ffeat: human work\x1e"
    "\nb2\x1fdependabot[bot]\x1f49699333+dependabot[bot]@users.noreply.github.com"
    "\x1fdependabot[bot]\x1f49699333+dependabot[bot]@users.noreply.github.com"
    "\x1f2026-02-02T00:00:00+00:00\x1ffeat: bot work\n\n"
    "Co-authored-by: Claude <noreply@anthropic.com>\x1e"
)


def test_detect_history_local_excludes_bot_ai_overlap_from_ratio():
    repo = FakeRepo(lambda args: _BOT_AI_OVERLAP_LOG if args[0] == "log" else None)
    results = detect_history_local(repo, PACK, limit=100)
    author, trailer, bot = results["author"], results["commit_trailer"], results["bot"]
    assert {h.evidence["commit"] for h in bot.hits} == {"b2"}
    assert {h.evidence["commit"] for h in trailer.hits} == {"b2"}
    stats = author.stats
    assert stats["commits"] == 1
    assert stats["ai_oids"] == ()
    assert stats["human_oids"] == ("b1",)
    assert len(stats["ai_oids"]) + len(stats["human_oids"]) == stats["commits"]


def test_detect_history_local_empty_repository():
    repo = FakeRepo(lambda args: None if args[0] == "log" else "")
    results = detect_history_local(repo, PACK)
    assert all(result.status == "unavailable" for result in results.values())


class _WindowSession:
    def __init__(self, records=(), *, omitted=(), error=None):
        self.records = {record.sha: record for record in records}
        self.shas = tuple(self.records)
        self.omitted = frozenset(omitted)
        self.error = error
        self.window_args: tuple[str, int] | None = None
        self.backfilled: list[str] = []

    def window(self, tip, depth):
        self.window_args = (tip, depth)
        if self.error is not None:
            raise self.error
        walked = {sha: record for sha, record in self.records.items() if sha not in self.omitted}
        return self.shas, walked

    def record(self, sha):
        self.backfilled.append(sha)
        return self.records.get(sha)


def _log_repo():
    return FakeRepo(lambda args: _LOGGED if args[0] == "log" else None)


def test_detect_history_local_matches_read_log_through_a_session_window(monkeypatch):
    records = parse_log(_LOGGED)
    session = _WindowSession(records)
    monkeypatch.setattr("detect.local_channels.resolve_head", lambda repo: "HEADTIP")
    repo = FakeRepo(lambda args: None)
    result = detect_history_local(repo, PACK, limit=100, session=session)
    baseline = detect_history_local(_log_repo(), PACK, limit=100)
    assert result == baseline
    assert session.window_args == ("HEADTIP", 100)
    assert session.backfilled == []
    assert repo.calls == []


def test_detect_history_local_backfills_boundary_records_from_the_session(monkeypatch):
    records = parse_log(_LOGGED)
    session = _WindowSession(records, omitted={records[-1].sha})
    monkeypatch.setattr("detect.local_channels.resolve_head", lambda repo: "HEADTIP")
    result = detect_history_local(FakeRepo(lambda args: None), PACK, limit=100, session=session)
    baseline = detect_history_local(_log_repo(), PACK, limit=100)
    assert result == baseline
    assert session.backfilled == [records[-1].sha]


def test_detect_history_local_falls_back_to_read_log_when_the_window_fails(monkeypatch):
    session = _WindowSession(parse_log(_LOGGED), error=WalkAnomaly("cat-file stream ended"))
    monkeypatch.setattr("detect.local_channels.resolve_head", lambda repo: "HEADTIP")
    repo = _log_repo()
    result = detect_history_local(repo, PACK, limit=100, session=session)
    baseline = detect_history_local(_log_repo(), PACK, limit=100)
    assert result == baseline
    assert any(call[0] == "log" for call in repo.calls)


def test_detect_history_local_falls_back_on_an_unborn_head(monkeypatch):
    def unborn(repo):
        raise GitError(["rev-parse", "HEAD"], 128, "fatal: ambiguous argument 'HEAD'")

    monkeypatch.setattr("detect.local_channels.resolve_head", unborn)
    session = _WindowSession(parse_log(_LOGGED))
    result = detect_history_local(FakeRepo(lambda args: None), PACK, limit=100, session=session)
    assert all(channel.status == "unavailable" for channel in result.values())
    assert session.window_args is None


_PR_LOG = (
    "s1\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
    "\x1f2026-02-01T00:00:00+00:00\x1ffeat: pr work\x1e"
    "\ns2\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
    "\x1f2026-02-02T00:00:00+00:00\x1fhuman work\x1e"
)


def test_detect_pr_commits_local_maps_commits_to_prs_and_dedupes(tmp_path):
    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\nbbb\trefs/pull/9/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "rev-list":
            return {"aaa": "s1\ns2\n", "bbb": "s2\n"}[args[-1]]
        if args[0] == "log":
            return _PR_LOG
        return None

    result = detect_pr_commits_local(FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, depth=100)
    assert result.status == "ok"
    assert {(h.evidence["pr"], h.evidence["commit"]) for h in result.hits} == {(7, "s1")}
    assert all(h.evidence["propagated"] is True for h in result.hits)
    assert result.stats["propagated_oids"] == ("s1",)
    assert result.stats["created_at"] == {}


def test_detect_pr_commits_local_without_refs_is_ok():
    repo = FakeRepo(lambda args: "" if args[0] == "fetch" else "")
    result = detect_pr_commits_local(repo, PACK)
    assert result.status == "ok"
    assert result.hits == ()
    assert result.stats["propagated_oids"] == ()


def test_detect_pr_commits_local_forwards_the_gate(monkeypatch):
    captured: dict[str, object] = {}
    gate = object()

    def fake_fetch(repo, *, depth, gate=None, refs=None, gate_reserved=False):
        captured.update(gate=gate, refs=refs, gate_reserved=gate_reserved)
        return {}

    monkeypatch.setattr("detect.local_channels.fetch_pr_refs", fake_fetch)
    result = detect_pr_commits_local(FakeRepo(lambda args: None), PACK, gate=gate)
    assert captured == {"gate": gate, "refs": None, "gate_reserved": False}
    assert result.status == "ok"
    assert result.note == "no pull requests found"


def test_detect_pr_commits_local_defaults_to_no_gate(monkeypatch):
    captured: dict[str, object] = {}

    def fake_fetch(repo, *, depth, gate=None, refs=None, gate_reserved=False):
        captured.update(gate=gate, refs=refs, gate_reserved=gate_reserved)
        return {}

    monkeypatch.setattr("detect.local_channels.fetch_pr_refs", fake_fetch)
    result = detect_pr_commits_local(FakeRepo(lambda args: None), PACK)
    assert captured == {"gate": None, "refs": None, "gate_reserved": False}
    assert result.status == "ok"


def test_detect_pr_commits_local_forwards_prefetched_refs_and_reserved_gate(monkeypatch):
    captured: dict[str, object] = {}
    gate = object()
    prefetched = {7: "aaa"}

    def fake_fetch(repo, *, depth, gate=None, refs=None, gate_reserved=False):
        captured.update(gate=gate, refs=refs, gate_reserved=gate_reserved)
        return {}

    monkeypatch.setattr("detect.local_channels.fetch_pr_refs", fake_fetch)
    result = detect_pr_commits_local(
        FakeRepo(lambda args: None), PACK, gate=gate, refs=prefetched, gate_reserved=True
    )
    assert captured == {"gate": gate, "refs": prefetched, "gate_reserved": True}
    assert result.status == "ok"


def test_detect_pr_commits_local_passes_the_session_into_the_walk(tmp_path, monkeypatch):
    session = object()
    captured: dict[str, object] = {}
    record = CommitRecord(
        sha="s1",
        author_name="Claude",
        author_email="noreply@anthropic.com",
        committer_name="Claude",
        committer_email="noreply@anthropic.com",
        committed_at="2026-02-01T00:00:00+00:00",
        message="feat: pr work",
    )

    def fake_walk(repo, refs, *, depth, session=None, on_failure=None):
        captured.update(refs=dict(refs), depth=depth, session=session)
        return {7: ("s1",)}, {"s1": record}

    monkeypatch.setattr("detect.local_channels.walk_windows_with_records", fake_walk)
    repo = FakeRepo(lambda args: "" if args[0] == "fetch" else None, dest=_repo_dir(tmp_path))
    result = detect_pr_commits_local(repo, PACK, depth=100, refs={7: "aaa"}, session=session)
    assert captured == {"refs": {7: "aaa"}, "depth": 100, "session": session}
    assert result.status == "ok"
    assert {(hit.evidence["pr"], hit.evidence["commit"]) for hit in result.hits} == {(7, "s1")}
    assert result.stats["propagated_oids"] == ("s1",)


def test_detect_pr_commits_local_records_walk_ms_in_phase_metrics(tmp_path, monkeypatch):
    record = CommitRecord(
        sha="s1",
        author_name="Claude",
        author_email="noreply@anthropic.com",
        committer_name="Claude",
        committer_email="noreply@anthropic.com",
        committed_at="2026-02-01T00:00:00+00:00",
        message="feat: pr work",
    )

    def fake_walk(repo, refs, *, depth, session=None, on_failure=None):
        return {7: ("s1",)}, {"s1": record}

    monkeypatch.setattr("detect.local_channels.walk_windows_with_records", fake_walk)
    metrics = phase_metrics.RepoPhaseMetrics(full_name="octo/one")
    token = phase_metrics.collecting(metrics)
    try:
        repo = FakeRepo(lambda args: "" if args[0] == "fetch" else None, dest=_repo_dir(tmp_path))
        result = detect_pr_commits_local(repo, PACK, depth=100, refs={7: "aaa"})
    finally:
        phase_metrics.reset(token)

    assert result.status == "ok"
    assert isinstance(metrics.walk_ms, float)
    assert metrics.refs_count == 1


def test_detect_pr_commits_local_records_walk_ms_when_the_walk_fails(tmp_path, monkeypatch):
    def exploding_walk(repo, refs, *, depth, session=None, on_failure=None):
        raise GitError(["rev-list"], 128, "fatal: bad object")

    monkeypatch.setattr("detect.local_channels.walk_windows_with_records", exploding_walk)
    metrics = phase_metrics.RepoPhaseMetrics(full_name="octo/one")
    token = phase_metrics.collecting(metrics)
    try:
        repo = FakeRepo(lambda args: "" if args[0] == "fetch" else None, dest=_repo_dir(tmp_path))
        result = detect_pr_commits_local(repo, PACK, depth=100, refs={7: "aaa"})
    finally:
        phase_metrics.reset(token)

    assert result.status == "partial"
    assert isinstance(metrics.walk_ms, float)


def test_local_channels_take_session_as_a_keyword_only_default_none():
    for func in (detect_files_local, detect_history_local, detect_pr_commits_local):
        parameter = inspect.signature(func).parameters["session"]
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is None


def test_detect_pr_commits_local_retries_a_transient_fetch_failure(tmp_path):
    fetches: list[int] = []

    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            fetches.append(1)
            if len(fetches) == 1:
                raise GitError(list(args), 128, "fatal: connection reset")
            return ""
        if args[0] == "rev-list":
            return "s1\n"
        if args[0] == "log":
            return _PR_LOG
        return None

    repo = FakeRepo(handler, dest=_repo_dir(tmp_path))
    result = detect_pr_commits_local(repo, PACK, depth=100, retry_delay=0.0)
    assert result.status == "ok"
    assert len(fetches) == 2
    assert {(h.evidence["pr"], h.evidence["commit"]) for h in result.hits} == {(7, "s1")}
    assert read_pr_refs_snapshot(repo) == {7: "aaa"}


def test_detect_pr_commits_local_reports_the_fetch_error_tail(tmp_path):
    fetches: list[int] = []

    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            fetches.append(1)
            raise GitError(
                list(args),
                128,
                "remote: hangup\nfatal: unable to access 'https://github.com/o/r.git/':"
                " Failed to connect to github.com",
            )
        return None

    result = detect_pr_commits_local(
        FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, retry_delay=0.0
    )
    assert result.status == "partial"
    assert result.note == (
        "pull refs fetch failed: fatal: unable to access 'https://github.com/o/r.git/':"
        " Failed to connect to github.com"
    )
    assert result.stats["propagated_oids"] == ()
    assert len(fetches) == 4


def test_detect_pr_commits_local_degrades_a_fetch_timeout_to_partial(tmp_path):
    fetches: list[int] = []

    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            fetches.append(1)
            raise subprocess.TimeoutExpired(list(args), timeout=600)
        return None

    result = detect_pr_commits_local(
        FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, retry_delay=0.0
    )
    assert result.status == "partial"
    assert result.note.startswith("pull refs fetch failed: ")
    assert len(fetches) == 4


def test_detect_pr_commits_local_degrades_a_walk_failure_to_partial(tmp_path):
    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "rev-list":
            raise GitError(list(args), 128, "fatal: bad object aaa")
        return None

    result = detect_pr_commits_local(
        FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, retry_delay=0.0
    )
    assert result.status == "partial"
    assert "1 PR walk(s) failed (e.g. #7: fatal: bad object aaa)" in (result.note or "")
    assert result.stats["propagated_oids"] == ()


def test_detect_pr_commits_local_keeps_good_prs_when_one_walk_fails(tmp_path):
    log = _PR_LOG + (
        "s3\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
        "\x1f2026-03-01T00:00:00+00:00\x1ffeat: later\x1e"
    )

    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\nbbb\trefs/pull/9/head\nccc\trefs/pull/11/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "rev-list":
            if args[-1] == "bbb":
                raise GitError(list(args), 128, "fatal: bad object bbb")
            return "s1\n" if args[-1] == "aaa" else "s3\n"
        if args[0] == "log":
            return log
        return None

    result = detect_pr_commits_local(
        FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, depth=100, retry_delay=0.0
    )
    assert result.status == "partial"
    assert {(hit.evidence["pr"], hit.evidence["commit"]) for hit in result.hits} == {
        (7, "s1"),
        (11, "s3"),
    }
    assert "1 PR walk(s) failed (e.g. #9: fatal: bad object bbb)" in (result.note or "")


def test_detect_pr_commits_local_reports_a_commit_read_failure_as_partial(tmp_path):
    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "rev-list":
            return "s1\n"
        if args[0] == "log":
            raise GitError(list(args), 128, "fatal: bad object")
        return None

    result = detect_pr_commits_local(
        FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, retry_delay=0.0
    )
    assert result.status == "partial"
    assert result.note == "commit read failed: fatal: bad object"
    assert result.stats["propagated_oids"] == ()


def test_detect_branch_local_parses_merge_messages():
    log = (
        "m1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-03-01T00:00:00+00:00\x1fMerge pull request #123 from octo/claude/fix\x1e"
        "\nm2\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-03-02T00:00:00+00:00\x1fMerge pull request #9 from fork/cursor/tool\x1e"
        "\nm3\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-03-03T00:00:00+00:00\x1ffeat: normal\x1e"
    )
    repo = FakeRepo(lambda args: log if args[0] == "log" else None)
    result = detect_branch_local(repo, PACK, limit=100)
    assert {(h.evidence["pr"], h.evidence["head"]) for h in result.hits} == {
        (123, "claude/fix"),
        (9, "cursor/tool"),
    }
    assert {h.agent for h in result.hits} == {"Claude Code", "Cursor"}


def test_detect_branch_local_matches_remote_head_refs():
    repo = FakeRepo(lambda args: "" if args[0] == "log" else None)
    repo._remote_refs_cache = RemoteRefs(
        pr_refs={},
        head_refs={"refs/heads/claude/fix-tests": "a" * 40, "refs/heads/main": "b" * 40},
    )
    result = detect_branch_local(repo, PACK, limit=100)
    assert result.status == "ok"
    assert result.note == "window: last 100 commits; merge messages + remote branch heads"
    assert [(h.agent, h.evidence) for h in result.hits] == [
        ("Claude Code", {"pr": None, "head": "claude/fix-tests", "match": "claude/"})
    ]


def test_detect_branch_local_merges_merge_message_and_remote_head_evidence():
    log = (
        "m1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-03-01T00:00:00+00:00\x1fMerge pull request #123 from octo/claude/fix\x1e"
    )
    repo = FakeRepo(lambda args: log if args[0] == "log" else None)
    repo._remote_refs_cache = RemoteRefs(pr_refs={}, head_refs={"refs/heads/cursor/tool": "c" * 40})
    result = detect_branch_local(repo, PACK, limit=100)
    assert {(h.evidence["pr"], h.evidence["head"]) for h in result.hits} == {
        (123, "claude/fix"),
        (None, "cursor/tool"),
    }
    assert result.note == "window: last 100 commits; merge messages + remote branch heads"


def test_detect_branch_local_degrades_to_merge_messages_when_listing_fails():
    log = (
        "m1\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
        "\x1f2026-03-01T00:00:00+00:00\x1fMerge pull request #123 from octo/claude/fix\x1e"
    )
    repo = FakeRepo(lambda args: log if args[0] == "log" else None)
    result = detect_branch_local(repo, PACK, limit=100)
    assert result.status == "ok"
    assert result.note == "window: last 100 commits; merge messages only"
    assert {(h.evidence["pr"], h.evidence["head"]) for h in result.hits} == {(123, "claude/fix")}


def test_detect_branch_local_never_raises_when_listing_explodes(monkeypatch):
    def boom(repo):
        raise RuntimeError("boom")

    monkeypatch.setattr("detect.local_channels.remote_refs", boom)
    result = detect_branch_local(FakeRepo(lambda args: "" if args[0] == "log" else None), PACK)
    assert result.status == "ok"
    assert result.hits == ()


def test_detect_branch_local_skips_listing_without_branch_patterns(monkeypatch):
    def boom(repo):
        raise AssertionError("remote_refs must not be called")

    monkeypatch.setattr("detect.local_channels.remote_refs", boom)
    pack = replace(PACK, branches=())
    result = detect_branch_local(FakeRepo(lambda args: "" if args[0] == "log" else None), pack)
    assert result.status == "ok"
    assert result.note == "window: last 100 commits; merge messages only"


_A_TIP = "a1" * 20
_A_PARENT = "a2" * 20
_B_TIP = "b0" * 20
_A_NODES = {
    _A_TIP: (
        (_A_PARENT,),
        200,
        CommitRecord(
            sha=_A_TIP,
            author_name="Jane",
            author_email="jane@example.com",
            committer_name="Jane",
            committer_email="jane@example.com",
            committed_at="2026-02-02T00:00:00Z",
            message="chore: tip",
        ),
    ),
    _A_PARENT: (
        (),
        100,
        CommitRecord(
            sha=_A_PARENT,
            author_name="Claude",
            author_email="noreply@anthropic.com",
            committer_name="Claude",
            committer_email="noreply@anthropic.com",
            committed_at="2026-02-01T00:00:00Z",
            message="feat: pr work",
        ),
    ),
}


class _StubCatFileBatch:
    def __init__(self, nodes):
        self._nodes = nodes

    def commit(self, oid):
        return self._nodes.get(oid)

    def close(self):
        pass


def test_detect_pr_commits_local_reads_no_git_log_when_walker_supplied_records(
    tmp_path, monkeypatch
):
    reset_verification()
    monkeypatch.delenv("GITCORPUS_WALK_VERIFY_PCT", raising=False)
    monkeypatch.setattr(repo_walk, "CatFileBatch", lambda dest: _StubCatFileBatch(_A_NODES))
    logged: list[tuple[str, ...]] = []

    def handler(args):
        if args[0] == "ls-remote":
            return f"{_A_TIP}\trefs/pull/7/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "log":
            logged.append(args)
            return ""
        return None

    result = detect_pr_commits_local(FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, depth=100)
    assert result.status == "ok"
    assert logged == []
    assert {(h.evidence["pr"], h.evidence["commit"]) for h in result.hits} == {(7, _A_PARENT)}
    assert result.stats["propagated_oids"] == (_A_PARENT,)


def test_detect_pr_commits_local_backfills_only_missing_records(tmp_path, monkeypatch):
    reset_verification()
    monkeypatch.delenv("GITCORPUS_WALK_VERIFY_PCT", raising=False)
    monkeypatch.setattr(repo_walk, "CatFileBatch", lambda dest: _StubCatFileBatch(_A_NODES))
    logged: list[tuple[str, ...]] = []

    def handler(args):
        if args[0] == "ls-remote":
            return f"{_A_TIP}\trefs/pull/7/head\n{_B_TIP}\trefs/pull/9/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "rev-list":
            return "c1\nc2\n"
        if args[0] == "log":
            logged.append(args)
            return "".join(
                f"{sha}\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
                f"\x1f2026-02-03T00:00:00Z\x1fbackfilled {sha}\x1e\n"
                for sha in args[3:]
            )
        return None

    result = detect_pr_commits_local(FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, depth=100)
    assert result.status == "ok"
    assert len(logged) == 1
    assert logged[0][3:] == ("c1", "c2")
    assert {(h.evidence["pr"], h.evidence["commit"]) for h in result.hits} == {
        (7, _A_PARENT),
        (9, "c1"),
        (9, "c2"),
    }
    assert result.stats["propagated_oids"] == (_A_PARENT, "c1", "c2")


def test_detect_pr_commits_local_resumes_from_snapshot_after_fetch_failure(tmp_path, monkeypatch):
    reset_verification()
    monkeypatch.delenv("GITCORPUS_WALK_VERIFY_PCT", raising=False)
    monkeypatch.setattr(repo_walk, "CatFileBatch", lambda dest: _StubCatFileBatch(_A_NODES))
    fetches: list[int] = []

    def handler(args):
        if args[0] == "ls-remote":
            return f"{_A_TIP}\trefs/pull/7/head\n"
        if args[0] == "fetch":
            fetches.append(1)
            raise GitError(list(args), 128, "fatal: connection reset by peer")
        return None

    repo = FakeRepo(handler, dest=_repo_dir(tmp_path))
    write_pr_refs_snapshot(repo, {7: _A_TIP})
    result = detect_pr_commits_local(repo, PACK, depth=100, retry_delay=0.0)
    assert len(fetches) == 4
    assert result.status == "ok"
    assert result.note == (
        "local PR refs; depth 100; resumed from persisted PR ref snapshot:"
        " fatal: connection reset by peer"
    )
    assert {(h.evidence["pr"], h.evidence["commit"]) for h in result.hits} == {(7, _A_PARENT)}
    assert result.stats["propagated_oids"] == (_A_PARENT,)


def test_detect_pr_commits_local_prefers_a_successful_fetch_over_the_snapshot(
    tmp_path, monkeypatch
):
    reset_verification()
    monkeypatch.delenv("GITCORPUS_WALK_VERIFY_PCT", raising=False)
    monkeypatch.setattr(repo_walk, "CatFileBatch", lambda dest: _StubCatFileBatch(_A_NODES))

    def handler(args):
        if args[0] == "ls-remote":
            return f"{_B_TIP}\trefs/pull/9/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "rev-list":
            return "c1\n"
        if args[0] == "log":
            return (
                "c1\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
                "\x1f2026-02-03T00:00:00Z\x1fbackfilled c1\x1e\n"
            )
        return None

    repo = FakeRepo(handler, dest=_repo_dir(tmp_path))
    write_pr_refs_snapshot(repo, {7: _A_TIP})
    result = detect_pr_commits_local(repo, PACK, depth=100)
    assert result.status == "ok"
    assert "resumed" not in result.note
    assert {(h.evidence["pr"], h.evidence["commit"]) for h in result.hits} == {(9, "c1")}
    assert read_pr_refs_snapshot(repo) == {9: _B_TIP}
