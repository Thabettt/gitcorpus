from __future__ import annotations

from pathlib import Path

from detect.attribution import (
    AMBIGUOUS,
    CODEX_PR_BODY_MARKER,
    Hit,
    adoption_level,
    build_channel_regex,
    clear_matcher_cache,
    dedupe_hits,
    is_ambiguous,
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
from detect.packs import Pack, Pattern, load_pack_file
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

ROOT = Path(__file__).resolve().parents[2]
PACK_2026_10_19 = load_pack_file(ROOT / "packs" / "2026-10-19.json")


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


def test_ambiguous_membership_is_case_insensitive():
    assert AMBIGUOUS == frozenset(
        {
            "aider",
            "claude",
            "copilot",
            "cline",
            "junie",
            "cursor",
            "coderabbit",
            "chatgpt",
            "roomote",
            "codex",
        }
    )
    assert is_ambiguous("Cursor") and is_ambiguous("cursor")
    assert not is_ambiguous("cursoragent")


def test_commit_message_prose_traps_do_not_match():
    hits = match_commit_messages(
        PACK_2026_10_19,
        [
            ("t1", "fix: push declined due to branch protection"),
            ("t2", "refactor: rename assoc_cursor to cursor_id"),
            ("t3", "refactor(aider): move the aider launcher"),
            ("t4", "fix: raider subsystem crash"),
        ],
    )
    assert hits == []


def test_commit_messages_case_insensitive_trailers_match():
    cases = [
        ("Co-authored-by: Cursor", "Cursor"),
        ("Generated with Cursor", "Cursor"),
        ("Generated with CodeRabbit", "Coderabbit"),
        ("Generated with Junie", "Junie"),
        ("Generated with Roomote", "Roo Code"),
        ("Built with Aider", "Aider"),
        ("Generated with Cline", "Cline"),
        ("generated with claude code", "Claude Code"),
        ("Generated with Codex", "Codex"),
        ("Co-authored-by: factory-droid[bot]", "Factory Droid"),
    ]
    for index, (message, agent) in enumerate(cases):
        hits = match_commit_messages(PACK_2026_10_19, [(f"c{index}", message)])
        assert [(h.agent, h.channel) for h in hits] == [(agent, "commit_trailer")], message


def test_commit_message_footer_in_second_to_last_paragraph_matches():
    message = (
        "msg\n\n"
        "🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\n"
        "Co-Authored-By: Claude <noreply@anthropic.com>"
    )
    hits = match_commit_messages(PACK_2026_10_19, [("c1", message)])
    assert [(h.agent, h.channel) for h in hits] == [("Claude Code", "commit_trailer")]


def test_quoted_and_bulleted_footer_lines_match():
    hits = match_commit_messages(
        PACK_2026_10_19,
        [("c1", "> Co-authored-by: Cursor"), ("c2", "- Generated with Aider")],
    )
    assert [(h.agent, h.evidence["commit"]) for h in hits] == [("Cursor", "c1"), ("Aider", "c2")]


def test_human_name_in_a_trailer_value_does_not_match_claude():
    hits = match_commit_messages(
        PACK_2026_10_19, [("c1", "Co-authored-by: Jean-Claude Van Damme <jc@x.com>")]
    )
    assert hits == []


def test_commit_message_email_only_salvage_matches():
    hits = match_commit_messages(
        PACK_2026_10_19, [("c1", "contact noreply@anthropic.com for help")]
    )
    assert [(h.agent, h.channel) for h in hits] == [("Claude Code", "commit_trailer")]
    assert "<email>" in hits[0].evidence["snippet"]
    assert "noreply@anthropic.com" not in str(hits[0].evidence)


def test_generic_token_in_prose_does_not_match():
    hits = match_commit_messages(PACK_2026_10_19, [("c1", "Note: cursor position was wrong")])
    assert hits == []


def test_generic_token_lines_require_a_blank_line_separated_trailer_block():
    assert match_commit_messages(PACK_2026_10_19, [("c1", "Jira: cursor position")]) == []
    hits = match_commit_messages(PACK_2026_10_19, [("c2", "feat: work\n\nTracker: Cursor")])
    assert [(h.agent, h.channel) for h in hits] == [("Cursor", "commit_trailer")]


def test_commit_message_prefers_the_tier1_snippet():
    message = "Generated with Cursor\n\ncontact cursoragent@cursor.com for help"
    hits = match_commit_messages(PACK_2026_10_19, [("c1", message)])
    assert [(h.agent, h.evidence["snippet"]) for h in hits] == [("Cursor", "Generated with Cursor")]


def test_commit_message_emits_at_most_one_hit_per_commit_and_agent():
    message = (
        "feat: x\n\n"
        "Generated with Cursor\n\n"
        "Co-authored-by: Cursor <cursoragent@cursor.com>\n"
        "Co-authored-by: Cursor"
    )
    hits = match_commit_messages(PACK_2026_10_19, [("c1", message), ("c1", message)])
    assert [(h.agent, h.channel) for h in hits] == [("Cursor", "commit_trailer")]
