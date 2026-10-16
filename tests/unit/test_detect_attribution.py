from __future__ import annotations

from detect.attribution import (
    CODEX_PR_BODY_MARKER,
    Hit,
    adoption_level,
    build_channel_regex,
    clear_matcher_cache,
    dedupe_hits,
    is_noise_commit,
    match_author_identities,
    match_branches,
    match_commit_messages,
    match_files,
    match_issue_participants,
    match_labels,
    match_pr_authors,
    match_pr_metadata,
    propagate_pr_commits,
    redact_emails,
)
from detect.packs import Pack, Pattern
from enrich.trees_first import FilePresence

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


def presence(paths, *, source="tree"):
    return FilePresence(
        repo_full_name="o/r", paths=frozenset(paths), truncated=False, source=source
    )


def test_channel_regex_builds_named_groups_and_escapes_file_dots():
    channel = build_channel_regex(PACK.files, is_files=True)
    assert channel.regex is not None
    match = channel.regex.search(".cursor/rules/x.md")
    assert match is not None
    assert channel.names[match.lastgroup] == "Cursor"


def test_match_files_maps_regexes_and_weights():
    hits = match_files(
        PACK,
        presence(["CLAUDE.md", "AGENTS.md", "CONVENTIONS.md", ".cursor/rules/x.md", "claude.md"]),
    )
    by_path = {h.evidence["path"]: h for h in hits}
    assert by_path["CLAUDE.md"].agent == "Claude Code"
    assert by_path[".cursor/rules/x.md"].agent == "Cursor"
    assert by_path["AGENTS.md"].agent == "Generic"
    assert by_path["AGENTS.md"].evidence["generic"] is True
    assert by_path["AGENTS.md"].evidence["weight"] == 0.3
    assert "CONVENTIONS.md" not in by_path
    assert "claude.md" not in by_path  # case-sensitive, like the replication package


def test_matcher_cache_distinguishes_packs_with_the_same_version():
    clear_matcher_cache()
    cursor_only = Pack(
        version="v1",
        agents={"Cursor": "https://cursor.com"},
        authors=(),
        files=(Pattern(r"\.cursor/", "Cursor"),),
        branches=(),
        labels=(),
        bots=(),
        generic_weights={},
        exclusions=frozenset(),
    )
    assert {h.agent for h in match_files(PACK, presence([".cursor/rules/x.md"]))} == {"Cursor"}
    assert {h.agent for h in match_files(cursor_only, presence([".cursor/rules/x.md"]))} == {
        "Cursor"
    }
    assert {h.agent for h in match_files(PACK, presence(["CLAUDE.md"]))} == {"Claude Code"}
    assert match_files(cursor_only, presence(["CLAUDE.md"])) == []


def test_selection_scopes_matching():
    clear_matcher_cache()
    hits = match_files(
        PACK, presence(["CLAUDE.md", ".cursor/rules/x.md"]), agents=frozenset({"Cursor"})
    )
    assert [h.agent for h in hits] == ["Cursor"]
    authors = match_author_identities(
        PACK,
        [{"login": "jane", "name": "Jane", "email": "noreply@anthropic.com", "commit": "c1"}],
        agents=frozenset({"Cursor"}),
    )
    assert authors == []


def test_author_evidence_never_contains_the_identity_value():
    hits = match_author_identities(
        PACK,
        [{"login": "jane", "name": "Jane", "email": "noreply@anthropic.com", "commit": "c1"}],
    )
    assert [(h.agent, h.channel) for h in hits] == [("Claude Code", "author")]
    assert hits[0].evidence == {"login": "jane", "commit": "c1", "field": "email"}


def test_commit_messages_redact_emails_and_skip_noise():
    hits = match_commit_messages(
        PACK,
        [
            ("c1", "fix: x\n\nCo-authored-by: Cursor <cursoragent@x>"),
            ("c2", "Merge branch 'main' into dev"),
            ("c3", "chore: bump version to 1.2.3"),
        ],
    )
    assert [(h.agent, h.evidence["commit"]) for h in hits] == [("Cursor", "c1")]
    assert "cursoragent@x" not in str(hits[0].evidence)
    assert "<email>" in hits[0].evidence["snippet"]
    assert is_noise_commit('Revert "feat: y"')
    assert not is_noise_commit("feat: real work")


def test_branches_labels_and_pr_metadata():
    assert [h.agent for h in match_branches(PACK, ["claude/add-tests"])] == ["Claude Code"]
    assert [h.agent for h in match_labels(PACK, ["ai-generated", "example"])] == ["Claude Code"]
    prs = [
        {
            "number": 7,
            "headRefName": "cursor/fix",
            "labels": [],
            "body": f"task: {CODEX_PR_BODY_MARKER}",
            "author": "cursoragent",
            "commits": [
                {"oid": "a1", "author": "cursoragent"},
                {"oid": "a2", "author": "human"},
            ],
        }
    ]
    hits = match_pr_metadata(PACK, prs)
    assert {(h.agent, h.channel) for h in hits} == {("Cursor", "branch"), ("Codex", "pr_metadata")}
    assert all(h.evidence["pr"] == 7 for h in hits)
    author_hits = match_pr_authors(PACK, prs)
    assert [h.agent for h in author_hits] == ["Cursor"]


def test_propagate_pr_commits_tags_only_the_pr_authors_commits():
    prs = [
        {
            "number": 7,
            "headRefName": "cursor/fix",
            "labels": [],
            "body": "",
            "author": "cursoragent",
            "commits": [
                {"oid": "a1", "author": "cursoragent"},
                {"oid": "a2", "author": "human"},
            ],
        }
    ]
    hits = match_pr_metadata(PACK, prs)
    propagated = propagate_pr_commits(hits, prs)
    assert [(h.agent, h.evidence["commit"]) for h in propagated] == [("Cursor", "a1")]
    assert propagated[0].evidence["propagated"] is True


def test_issue_participants_and_levels():
    entries = [
        {"login": "cursoragent", "number": 12, "role": "assignee"},
        {"login": "jane", "number": 12, "role": "commenter"},
    ]
    hits = match_issue_participants(PACK, entries)
    assert [(h.agent, h.channel, h.evidence["role"]) for h in hits] == [
        ("Cursor", "issue", "assignee")
    ]
    assert adoption_level(0.004) == "experimental"
    assert adoption_level(0.03) == "limited"
    assert adoption_level(0.1) == "consistent"
    assert adoption_level(0.5) == "pervasive"
    assert adoption_level(0.0) == "experimental"
    assert adoption_level(None) == "none"
    assert redact_emails("a <b@c.dev>") == "a <email>"


def test_dedupe_collapses_identical_hits():
    hits = [
        Hit("Claude Code", "file", {"path": "CLAUDE.md"}),
        Hit("Claude Code", "file", {"path": "CLAUDE.md"}),
    ]
    assert dedupe_hits(hits) == [hits[0]]
