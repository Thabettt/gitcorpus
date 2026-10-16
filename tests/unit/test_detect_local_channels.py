from __future__ import annotations

import subprocess
from pathlib import Path

from detect.gitio import GitError, GitRepo
from detect.local_channels import (
    detect_branch_local,
    detect_files_local,
    detect_history_local,
    detect_pr_commits_local,
)
from detect.packs import Pack, Pattern

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
    def __init__(self, handler):
        super().__init__(Path())
        self._handler = handler
        self.calls: list[tuple[str, ...]] = []
        self.stdins: list[bytes | None] = []

    def git(self, *args: str, timeout: float | None = None, stdin=None) -> str:
        self.calls.append(args)
        self.stdins.append(stdin.read() if stdin is not None else None)
        result = self._handler(args)
        if result is None:
            raise GitError(list(args), 128, "fake")
        return result


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


def test_detect_history_local_empty_repository():
    repo = FakeRepo(lambda args: None if args[0] == "log" else "")
    results = detect_history_local(repo, PACK)
    assert all(result.status == "unavailable" for result in results.values())


_PR_LOG = (
    "s1\x1fClaude\x1fnoreply@anthropic.com\x1fClaude\x1fnoreply@anthropic.com"
    "\x1f2026-02-01T00:00:00+00:00\x1ffeat: pr work\x1e"
    "\ns2\x1fJane\x1fjane@example.com\x1fJane\x1fjane@example.com"
    "\x1f2026-02-02T00:00:00+00:00\x1fhuman work\x1e"
)


def test_detect_pr_commits_local_maps_commits_to_prs_and_dedupes():
    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\nbbb\trefs/pull/9/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "for-each-ref":
            return "refs/gc/pr/7 aaa\nrefs/gc/pr/9 bbb\n"
        if args[0] == "rev-list":
            return {"aaa": "s1\ns2\n", "bbb": "s2\n"}[args[3]]
        if args[0] == "log":
            return _PR_LOG
        return None

    result = detect_pr_commits_local(FakeRepo(handler), PACK, depth=100, walk_workers=2)
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


def test_detect_pr_commits_local_retries_a_transient_fetch_failure():
    fetches: list[int] = []

    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            fetches.append(1)
            if len(fetches) == 1:
                raise GitError(list(args), 128, "fatal: connection reset")
            return ""
        if args[0] == "for-each-ref":
            return "refs/gc/pr/7 aaa\n"
        if args[0] == "rev-list":
            return "s1\n"
        if args[0] == "log":
            return _PR_LOG
        return None

    result = detect_pr_commits_local(FakeRepo(handler), PACK, depth=100, retry_delay=0.0)
    assert result.status == "ok"
    assert len(fetches) == 2
    assert {(h.evidence["pr"], h.evidence["commit"]) for h in result.hits} == {(7, "s1")}


def test_detect_pr_commits_local_reports_the_fetch_error_tail():
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

    result = detect_pr_commits_local(FakeRepo(handler), PACK, retry_delay=0.0)
    assert result.status == "partial"
    assert result.note == (
        "pull refs fetch failed: fatal: unable to access 'https://github.com/o/r.git/':"
        " Failed to connect to github.com"
    )
    assert result.stats["propagated_oids"] == ()
    assert len(fetches) == 4


def test_detect_pr_commits_local_degrades_a_fetch_timeout_to_partial():
    fetches: list[int] = []

    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            fetches.append(1)
            raise subprocess.TimeoutExpired(list(args), timeout=600)
        return None

    result = detect_pr_commits_local(FakeRepo(handler), PACK, retry_delay=0.0)
    assert result.status == "partial"
    assert result.note.startswith("pull refs fetch failed: ")
    assert len(fetches) == 4


def test_detect_pr_commits_local_degrades_a_walk_failure_to_partial():
    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "for-each-ref":
            return "refs/gc/pr/7 aaa\n"
        if args[0] == "rev-list":
            raise GitError(list(args), 128, "fatal: bad object aaa")
        return None

    result = detect_pr_commits_local(FakeRepo(handler), PACK, retry_delay=0.0)
    assert result.status == "partial"
    assert result.note == "pull refs walk failed: fatal: bad object aaa"
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
