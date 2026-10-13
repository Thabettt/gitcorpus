from __future__ import annotations

import httpx

from detect.channels import detect_files
from detect.packs import Pack, Pattern
from discover.pipeline import Deps

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
    labels=(Pattern("ai-generated", "Claude Code"), Pattern("^amp$", "Amp")),
    bots=(Pattern(r"dependabot\[bot\]", "dependabot"),),
    generic_weights={"AGENTS.md": 0.3},
    exclusions=frozenset({"CONVENTIONS.md"}),
)


def make_deps(handler) -> Deps:
    return Deps(
        client=httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
        engine=None,
    )


def tree_response(paths: list[str], *, truncated: bool = False) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "truncated": truncated,
            "tree": [{"path": path, "type": "blob"} for path in paths],
        },
    )


def test_detect_files_matches_tree_gitignore_and_probes_content():
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        if request.url.path == "/repos/octo/repo/git/trees/main":
            return tree_response(["CLAUDE.md", ".cursor/rules/x.md", "AGENTS.md", "CONVENTIONS.md"])
        if request.url.path == "/repos/octo/repo/contents/.gitignore":
            return httpx.Response(200, text=".cursor/\n# comment\n")
        if request.url.path.startswith("/repos/octo/repo/contents/"):
            return httpx.Response(200, text="# guidance\n")
        raise AssertionError(request.url)

    result = detect_files(make_deps(handler), "octo/repo", PACK, ref="main")
    assert result.status == "ok"
    by_path = {(h.agent, h.evidence["path"]): h for h in result.hits}
    assert ("Claude Code", "CLAUDE.md") in by_path
    assert ("Cursor", ".cursor/rules/x.md") in by_path
    assert ("Generic", "AGENTS.md") in by_path
    assert ("Claude Code", "CONVENTIONS.md") not in by_path
    assert ("Cursor", ".cursor/") in by_path
    assert by_path[("Cursor", ".cursor/")].evidence["source"] == "gitignore"
    assert by_path[("Claude Code", "CLAUDE.md")].evidence["size"] == len("# guidance\n")
    assert by_path[("Claude Code", "CLAUDE.md")].evidence["empty"] is False


def test_detect_files_truncated_tree_probes_literal_paths():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octo/repo/git/trees/main":
            return tree_response(["src/a.py"], truncated=True)
        if request.url.path == "/repos/octo/repo/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/repos/octo/repo/contents/CLAUDE.md":
            return httpx.Response(200, text="# x\n")
        if request.url.path.startswith("/repos/octo/repo/contents/"):
            return httpx.Response(404)
        raise AssertionError(request.url)

    result = detect_files(make_deps(handler), "octo/repo", PACK, ref="main")
    assert result.status == "partial"
    assert [h.evidence["path"] for h in result.hits] == ["CLAUDE.md"]
    assert "truncated" in (result.note or "")


def test_detect_files_unavailable_repo():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"message": "Not Found"})

    result = detect_files(make_deps(handler), "octo/gone", PACK, ref="main")
    assert result.status == "unavailable"
    assert result.hits == ()
