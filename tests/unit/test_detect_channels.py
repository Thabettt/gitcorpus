from __future__ import annotations

import json

import httpx

from detect.channels import detect_files, detect_history, detect_issues, detect_prs
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


def history_handler(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/graphql"
    body = json.loads(request.content)
    assert body["variables"]["limit"] == 100
    return httpx.Response(
        200,
        json={
            "data": {
                "repository": {
                    "defaultBranchRef": {"name": "main"},
                    "object": {
                        "history": {
                            "nodes": [
                                {
                                    "oid": "c1",
                                    "committedDate": "2026-01-02T00:00:00Z",
                                    "message": "feat: x\n\nCo-authored-by: Cursor <cursoragent@x>",
                                    "author": {
                                        "name": "Jane",
                                        "email": "noreply@anthropic.com",
                                        "user": {"login": "jane"},
                                    },
                                    "committer": {
                                        "name": "Jane",
                                        "email": "noreply@anthropic.com",
                                        "user": {"login": "jane"},
                                    },
                                },
                                {
                                    "oid": "c2",
                                    "message": "chore: bump",
                                    "author": {
                                        "name": "bot",
                                        "email": "b@x",
                                        "user": {"login": "dependabot[bot]"},
                                    },
                                    "committer": {
                                        "name": "bot",
                                        "email": "b@x",
                                        "user": {"login": "dependabot[bot]"},
                                    },
                                },
                                {
                                    "oid": "c3",
                                    "message": "Merge branch 'main'",
                                    "author": {
                                        "name": "Jane",
                                        "email": "jane@example.com",
                                        "user": {"login": "jane"},
                                    },
                                    "committer": {
                                        "name": "Jane",
                                        "email": "jane@example.com",
                                        "user": {"login": "jane"},
                                    },
                                },
                                {
                                    "oid": "c4",
                                    "message": "fix: human work",
                                    "author": {
                                        "name": "Bob",
                                        "email": "bob@example.com",
                                        "user": {"login": "bob"},
                                    },
                                    "committer": {
                                        "name": "Bob",
                                        "email": "bob@example.com",
                                        "user": {"login": "bob"},
                                    },
                                },
                            ]
                        }
                    },
                }
            }
        },
    )


def test_history_channels_share_one_call_and_compute_window_stats():
    result = detect_history(make_deps(history_handler), "octo/repo", PACK, limit=100)
    assert [h.agent for h in result["author"].hits] == ["Claude Code"]
    assert result["author"].hits[0].evidence == {"login": "jane", "commit": "c1", "field": "email"}
    assert [h.agent for h in result["commit_trailer"].hits] == ["Cursor"]
    assert [h.agent for h in result["bot"].hits] == ["dependabot"]
    stats = result["author"].stats
    assert stats["commits"] == 2  # c1 and c4; c2 is a bot, c3 is noise
    assert set(stats["ai_oids"]) == {"c1"}
    assert set(stats["human_oids"]) == {"c4"}
    assert stats["committed_at"]["c1"] == "2026-01-02T00:00:00Z"


def test_history_matches_committer_only_identity():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/graphql"
        return httpx.Response(
            200,
            json={
                "data": {
                    "repository": {
                        "object": {
                            "history": {
                                "nodes": [
                                    {
                                        "oid": "c1",
                                        "committedDate": "2026-01-02T00:00:00Z",
                                        "message": "feat: human work with an agent committer",
                                        "author": {
                                            "name": "Jane",
                                            "email": "jane@example.com",
                                            "user": {"login": "jane"},
                                        },
                                        "committer": {
                                            "name": "Claude",
                                            "email": "noreply@anthropic.com",
                                            "user": {"login": "claude-agent"},
                                        },
                                    }
                                ]
                            }
                        }
                    }
                }
            },
        )

    result = detect_history(make_deps(handler), "octo/repo", PACK, limit=100)
    hits = result["author"].hits
    assert [(hit.agent, hit.channel) for hit in hits] == [("Claude Code", "author")]
    assert hits[0].evidence == {"login": "claude-agent", "commit": "c1", "field": "email"}
    assert result["author"].stats["ai_oids"] == ("c1",)
    assert result["author"].stats["human_oids"] == ()


def test_history_null_repository_is_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"repository": None}})

    result = detect_history(make_deps(handler), "octo/gone", PACK)
    assert result["author"].status == "unavailable"


def test_history_selection_scopes_matching():
    result = detect_history(
        make_deps(history_handler), "octo/repo", PACK, agents=frozenset({"Cursor"})
    )
    assert result["author"].hits == ()
    assert [h.agent for h in result["commit_trailer"].hits] == ["Cursor"]


def test_history_graphql_errors_with_null_data_is_partial():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": None, "errors": [{"message": "RATE_LIMITED"}]})

    result = detect_history(make_deps(handler), "octo/repo", PACK)
    for key in ("author", "commit_trailer", "bot"):
        assert result[key].status == "partial"
    assert result["author"].note == "graphql errors"


def pr_handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    assert body["variables"]["limit"] == 100
    return httpx.Response(
        200,
        json={
            "data": {
                "repository": {
                    "pullRequests": {
                        "nodes": [
                            {
                                "number": 7,
                                "headRefName": "cursor/fix",
                                "bodyText": "task: https://chatgpt.com/codex/tasks",
                                "author": {"login": "cursoragent"},
                                "labels": {"nodes": [{"name": "ai-generated"}]},
                                "comments": {"nodes": [{"author": {"login": "cursoragent"}}]},
                                "commits": {
                                    "nodes": [
                                        {
                                            "commit": {
                                                "oid": "a1",
                                                "author": {"user": {"login": "cursoragent"}},
                                            }
                                        },
                                        {
                                            "commit": {
                                                "oid": "a2",
                                                "author": {"user": {"login": "human"}},
                                            }
                                        },
                                    ]
                                },
                            }
                        ]
                    }
                }
            }
        },
    )


def test_detect_prs_matches_propagates_and_collects_commenters():
    result = detect_prs(make_deps(pr_handler), "octo/repo", PACK, limit=100)
    assert result.status == "ok"
    pairs = {(h.agent, h.evidence.get("pr")) for h in result.hits}
    assert ("Cursor", 7) in pairs and ("Claude Code", 7) in pairs and ("Codex", 7) in pairs
    propagated = [h for h in result.hits if h.evidence.get("propagated")]
    assert [(h.agent, h.evidence["commit"]) for h in propagated] == [
        ("Claude Code", "a1"),
        ("Codex", "a1"),
        ("Cursor", "a1"),
    ]
    assert result.stats["propagated_oids"] == ("a1",)
    assert result.stats["commenter_entries"] == (
        {"login": "cursoragent", "number": 7, "role": "pr_commenter"},
    )


def issue_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": {
                "repository": {
                    "issues": {
                        "nodes": [
                            {
                                "number": 12,
                                "author": {"login": "jane"},
                                "assignees": {"nodes": [{"login": "cursoragent"}]},
                                "comments": {"nodes": [{"author": {"login": "jane"}}]},
                            }
                        ]
                    }
                }
            }
        },
    )


def test_detect_issues_matches_roles_and_extra_entries():
    result = detect_issues(
        make_deps(issue_handler),
        "octo/repo",
        PACK,
        extra_entries=({"login": "cursoragent", "number": 7, "role": "pr_commenter"},),
    )
    roles = {(h.agent, h.evidence["number"], h.evidence["role"]) for h in result.hits}
    assert roles == {("Cursor", 12, "assignee"), ("Cursor", 7, "pr_commenter")}


def test_detect_prs_unavailable_repo():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": {"repository": None}})

    result = detect_prs(make_deps(handler), "octo/gone", PACK)
    assert result.status == "unavailable"


def test_detect_prs_graphql_errors_with_partial_data_is_partial():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {"repository": {"pullRequests": {"nodes": []}}},
                "errors": [{"message": "RATE_LIMITED"}],
            },
        )

    result = detect_prs(make_deps(handler), "octo/repo", PACK)
    assert result.status == "partial"
    assert result.note == "graphql errors"
