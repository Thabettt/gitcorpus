from __future__ import annotations

from pathlib import Path

from detect.gitio import GitError, GitRepo
from detect.local_channels import detect_files_local, detect_history_local
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
        super().__init__(Path("."))
        self._handler = handler

    def git(self, *args: str) -> str:
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


def test_detect_files_local_matches_tree_gitignore_and_probes_content():
    files = ["CLAUDE.md", ".cursor/rules/x.md", "AGENTS.md", "CONVENTIONS.md"]
    blobs = {".gitignore": ".cursor/\n# comment\n", "CLAUDE.md": "# guidance\n"}

    def handler(args):
        if args[0] == "ls-tree":
            return "".join(f"{path}\n" for path in files)
        if args[0] == "show":
            return blobs.get(args[1][5:])
        return None

    result = detect_files_local(FakeRepo(handler), PACK)
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
