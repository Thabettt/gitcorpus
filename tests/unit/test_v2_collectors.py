from __future__ import annotations

from pathlib import Path

import httpx

from detect.channels import detect_files, detect_hidden_refs
from detect.gitio import GitError, GitRepo
from detect.gitlab import collect_gitlab_repository
from detect.local_channels import detect_hidden_refs_local
from detect.packs import Family, Pack, Pattern, RuleSemantics, load_pack_file
from detect.structured import content_candidates
from discover.pipeline import Deps

ROOT = Path(__file__).resolve().parents[2]
PACK = load_pack_file(ROOT / "packs" / "2026-11-14.json")


def _deps(handler) -> Deps:
    return Deps(
        client=httpx.Client(
            transport=httpx.MockTransport(handler), base_url="https://api.github.com"
        ),
        engine=None,
    )


def _tree(paths: list[str]) -> httpx.Response:
    return httpx.Response(
        200,
        json={"truncated": False, "tree": [{"path": path, "type": "blob"} for path in paths]},
    )


def test_api_file_collector_fetches_only_declared_candidates_with_a_byte_range():
    seen: list[tuple[str, str | None]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.path, request.headers.get("range")))
        if request.url.path == "/repos/octo/repo/git/trees/main":
            return _tree(["src/app.py", "t3.json"])
        if request.url.path == "/repos/octo/repo/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/repos/octo/repo/contents/t3.json":
            return httpx.Response(200, text='{"$schema":"https://t3.codes/schema/t3.json"}')
        raise AssertionError(request.url)

    result = detect_files(_deps(handler), "octo/repo", PACK, ref="main")
    assert result.status == "ok"
    assert any(hit.rule_id == "t3-code.project-config" for hit in result.hits)
    assert not any("src/app.py" in path for path, _range in seen)
    content_request = next(item for item in seen if item[0].endswith("/contents/t3.json"))
    assert content_request[1] == "bytes=0-131071"
    assert result.stats["content_candidates"] == 1


def test_schema_v2_shared_agents_md_never_becomes_vendor_attribution():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octo/repo/git/trees/main":
            return _tree(["AGENTS.md"])
        if request.url.path == "/repos/octo/repo/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/repos/octo/repo/contents/AGENTS.md":
            return httpx.Response(200, text="# Claude Code Guidelines\n")
        raise AssertionError(request.url)

    result = detect_files(_deps(handler), "octo/repo", PACK, ref="main")
    assert [(hit.family_id, hit.channel) for hit in result.hits] == [("generic", "file")]


def test_api_file_collector_separates_fetch_parse_and_predicate_failures():
    mode = "fetch"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octo/repo/git/trees/main":
            return _tree(["t3.json"])
        if request.url.path == "/repos/octo/repo/contents/.gitignore":
            return httpx.Response(404)
        if request.url.path == "/repos/octo/repo/contents/t3.json":
            if mode == "fetch":
                return httpx.Response(422)
            if mode == "parse":
                return httpx.Response(200, text="{")
            return httpx.Response(200, text='{"$schema":"https://example.test"}')
        raise AssertionError(request.url)

    fetch = detect_files(_deps(handler), "octo/repo", PACK, ref="main")
    assert {item["kind"] for item in fetch.stats["content_diagnostics"]} == {"fetch_failure"}
    mode = "parse"
    parse = detect_files(_deps(handler), "octo/repo", PACK, ref="main")
    assert "parse_failure" in {item["kind"] for item in parse.stats["content_diagnostics"]}
    mode = "predicate"
    predicate = detect_files(_deps(handler), "octo/repo", PACK, ref="main")
    assert "predicate_failure" in {item["kind"] for item in predicate.stats["content_diagnostics"]}


_PR_AGENT_WORKFLOW = """
on: pull_request
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: the-pr-agent/pr-agent@main
"""


def _broad_content_handler(seen: list[str]):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        seen.append(path)
        if path == "/repos/octo/repo/git/trees/main":
            return _tree(
                [
                    "t3.json",
                    ".github/workflows/ci.yml",
                    ".github/workflows/review.yml",
                    "docker-compose.yml",
                ]
            )
        if path == "/repos/octo/repo/contents/.gitignore":
            return httpx.Response(404)
        if path == "/repos/octo/repo/contents/t3.json":
            return httpx.Response(200, text='{"$schema":"https://t3.codes/schema/t3.json"}')
        if path == "/repos/octo/repo/contents/.github/workflows/review.yml":
            return httpx.Response(200, text=_PR_AGENT_WORKFLOW)
        if path.startswith("/repos/octo/repo/contents/"):
            return httpx.Response(200, text="services: {}\n")
        raise AssertionError(request.url)

    return handler


def test_full_mode_reads_every_broad_pattern_content_candidate():
    seen: list[str] = []
    result = detect_files(_deps(_broad_content_handler(seen)), "octo/repo", PACK, ref="main")
    contents = {path for path in seen if "/contents/" in path}
    assert "/repos/octo/repo/contents/.github/workflows/ci.yml" in contents
    assert "/repos/octo/repo/contents/docker-compose.yml" in contents
    assert any(hit.rule_id == "pr-agent.workflow-action" for hit in result.hits)
    assert result.stats["content_scan"] == "full"


def test_fast_mode_skips_broad_reads_but_keeps_targeted_file_rules():
    seen: list[str] = []
    result = detect_files(
        _deps(_broad_content_handler(seen)), "octo/repo", PACK, ref="main", fast=True
    )
    contents = {path for path in seen if "/contents/" in path}
    assert contents == {
        "/repos/octo/repo/contents/.gitignore",
        "/repos/octo/repo/contents/t3.json",
    }
    rule_ids = {hit.rule_id for hit in result.hits}
    assert "t3-code.project-config" in rule_ids
    # An unread file can never satisfy a content predicate: no false positive.
    assert "pr-agent.workflow-action" not in rule_ids
    assert result.status == "ok"
    assert result.stats["content_scan"] == "fast"


def test_targeted_only_candidates_drop_broad_patterns():
    paths = ["t3.json", ".github/workflows/ci.yml", "deploy/compose.yaml"]
    full, _ = content_candidates(PACK, paths)
    fast, _ = content_candidates(PACK, paths, targeted_only=True)
    assert set(full) == set(paths)
    assert fast == ("t3.json",)


def test_api_hidden_refs_enumerate_only_declared_namespaces_and_scope_identity():
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        if "/git/matching-refs/herder" in request.url.path:
            return httpx.Response(
                200,
                json=[
                    {
                        "ref": "refs/herder/session/turn",
                        "object": {"type": "commit", "sha": "a" * 40},
                    }
                ],
            )
        if "/git/matching-refs/" in request.url.path:
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/git/commits/" + "a" * 40):
            return httpx.Response(
                200,
                json={
                    "author": {"name": "herder", "email": "herder@localhost"},
                    "committer": {
                        "name": "herder",
                        "email": "herder@localhost",
                        "date": "2026-11-14T00:00:00Z",
                    },
                },
            )
        raise AssertionError(request.url)

    result = detect_hidden_refs(_deps(handler), "octo/repo", PACK)
    assert result.status == "ok"
    assert {hit.rule_id for hit in result.hits} == {
        "herder.checkpoint-ref",
        "herder.checkpoint-identity",
    }
    namespaces = [path for path in requested if "/git/matching-refs/" in path]
    assert namespaces
    assert all("matching-refs/" in path for path in namespaces)
    assert not any(path.endswith("/git/objects") for path in requested)


def _gitlab_role_pack() -> Pack:
    family = Family("reviewer", "GitLab Reviewer", category="active")
    rule = Pattern(
        r"^duo-service$",
        "GitLab Reviewer",
        id="gitlab.reviewer",
        family_id="reviewer",
        family_name="GitLab Reviewer",
        channel="pr_reviewer",
        forge="gitlab",
        match={"login_regex": r"^duo-service$"},
        semantics=RuleSemantics(
            evidence="review_participation",
            layer="reviewer",
            role="pr_reviewer",
            counts_as_authorship=False,
            counts_as_generated_code=False,
            counts_in_current_ratio=False,
        ),
    )
    return Pack(
        version="gitlab-test",
        agents={"GitLab Reviewer": ""},
        authors=(),
        files=(),
        branches=(),
        labels=(),
        bots=(),
        generic_weights={},
        exclusions=frozenset(),
        schema_version=2,
        families=(family,),
        rules=(rule,),
    )


def test_gitlab_collector_preserves_reviewer_role_without_authorship():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/repository/branches"):
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/merge_requests"):
            return httpx.Response(
                200,
                json=[
                    {
                        "iid": 7,
                        "created_at": "2026-11-14T00:00:00Z",
                        "source_branch": "duo/fix/one",
                        "description": "",
                        "author": {"username": "human"},
                        "reviewers": [{"username": "duo-service"}],
                        "labels": [],
                    }
                ],
            )
        raise AssertionError(request.url)

    client = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="https://gitlab.example/api/v4"
    )
    results = collect_gitlab_repository(
        "group/project",
        _gitlab_role_pack(),
        client=client,
        api_base="https://gitlab.example/api/v4",
    )
    hit = results["issue"].hits[0]
    assert hit.forge == "gitlab"
    assert hit.role == "pr_reviewer"
    assert hit.evidence_semantics == "review_participation"
    assert hit.metric_eligibility["authorship"] is False


def test_gitlab_duo_branch_activates_only_through_gitlab_collection():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/repository/branches"):
            return httpx.Response(200, json=[{"name": "duo/feature/agent"}])
        if request.url.path.endswith("/merge_requests"):
            return httpx.Response(200, json=[])
        raise AssertionError(request.url)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    result = collect_gitlab_repository(
        "group/project", PACK, client=client, api_base="https://gitlab.example/api/v4"
    )
    assert [hit.rule_id for hit in result["branch"].hits] == ["gitlab-duo.branch"]


class _HiddenRepo(GitRepo):
    def __init__(self, dest: Path):
        super().__init__(dest)
        self.calls: list[tuple[str, ...]] = []

    def git(self, *args: str, timeout=None, stdin=None, env_extra=None) -> str:
        self.calls.append(args)
        if args[0] == "ls-remote":
            return f"{'a' * 40}\trefs/herder/session/turn\n"
        if args[0] == "fetch":
            assert stdin is not None
            assert b"refs/herder/session/turn" in stdin.read()
            return ""
        if args[0] == "log":
            return (
                f"{'a' * 40}\x1fherder\x1fherder@localhost\x1fherder\x1f"
                "herder@localhost\x1f2026-11-14T00:00:00Z\x1fcheckpoint\x1e"
            )
        raise GitError(args, 128, "unexpected")


def test_local_hidden_ref_collector_fetches_only_selected_tip_commits(tmp_path):
    (tmp_path / ".git").mkdir()
    repo = _HiddenRepo(tmp_path)
    result = detect_hidden_refs_local(repo, PACK)
    assert result.status == "ok"
    assert {hit.rule_id for hit in result.hits} == {
        "herder.checkpoint-ref",
        "herder.checkpoint-identity",
    }
    ls_remote = next(call for call in repo.calls if call[0] == "ls-remote")
    assert "refs/herder/*" in ls_remote
    assert "refs/*" not in ls_remote
