from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from detect.attribution import (
    match_author_identities,
    match_bots,
    match_branches,
    match_commit_messages,
    match_files,
    match_hidden_refs,
    match_pr_authors,
    parse_structured_trailers,
)
from detect.packs import (
    PackConflict,
    build_pack_from_dir,
    freeze_pack,
    load_frozen,
    load_pack_file,
    pack_digest,
    pack_from_document,
    pack_to_document,
)
from detect.structured import (
    content_candidates,
    evaluate_file_rules,
    path_matches,
    relationship_matches,
)
from enrich.trees_first import FilePresence

ROOT = Path(__file__).resolve().parents[2]
PACK_PATH = ROOT / "packs" / "2026-11-14.json"
SOURCE_PATH = ROOT / "packs" / "sources" / "2026-11-14" / "catalogue.json"
PACK = load_pack_file(PACK_PATH)


def _presence(*paths: str) -> FilePresence:
    return FilePresence("o/r", frozenset(paths), False, "tree")


def _structured(paths: list[str], contents: dict[str, str | None]):
    matches, diagnostics = evaluate_file_rules(PACK, paths, contents)
    return {match.rule.id: match for match in matches}, diagnostics


def test_pack_channel_support_tracks_the_catalogue_rules():
    # `issue` has no positive rules in this pack, so it is not offered; every
    # other channel has at least one enabled rule (bot: noise rejections).
    assert PACK.channels() == (
        "file",
        "author",
        "branch",
        "hidden_ref",
        "label",
        "bot",
        "commit_trailer",
        "pr_metadata",
    )
    assert "hidden_ref" not in PACK.default_channels()


def test_roster_is_every_family_with_a_positive_rule():
    # Selecting the whole roster must equal an unfiltered scan, so verified
    # legacy-only families (historical evidence) are selectable too.
    owners = {
        rule.display_name for rule in PACK.rules if rule.enabled and rule.disposition == "positive"
    }
    assert set(PACK.roster()) == owners
    categories = PACK.roster_categories()
    assert {"Brokk", "Continue", "Sweep", "GPT-Engineer"} <= {
        name for name, category in categories.items() if category == "legacy-only"
    }
    assert sum(category == "active" for category in categories.values()) == 78


def test_packs_are_independent():
    older = load_pack_file(ROOT / "packs" / "2026-10-19.json")
    assert older.channels() == (
        "file",
        "author",
        "branch",
        "label",
        "bot",
        "commit_trailer",
        "pr_metadata",
        "issue",
    )
    assert len(older.roster()) == 62
    assert "hidden_ref" not in older.channels()
    assert "Zoo Code" not in older.roster() and "Zoo Code" in PACK.roster()


def test_each_pack_builds_only_from_its_own_source_directory():
    sources = ROOT / "packs" / "sources"
    for version in ("2026-10-19", "2026-11-14"):
        built = build_pack_from_dir(sources / version, version=version)
        assert pack_digest(built) == pack_digest(load_pack_file(ROOT / "packs" / f"{version}.json"))
    with pytest.raises(ValueError, match="different pack"):
        build_pack_from_dir(sources / "2026-10-19", version="2026-11-14")


def test_pack_is_a_deterministic_complete_schema_v2_snapshot():
    built = build_pack_from_dir(SOURCE_PATH.parent, version="2026-11-14")
    assert pack_to_document(built) == pack_to_document(PACK)
    assert pack_from_document(pack_to_document(PACK)) == PACK
    assert pack_digest(built) == pack_digest(PACK)
    assert PACK.catalogue == {
        "normalized_incumbents": 47,
        "additions": 25,
        "current_matcher_detectable": 72,
        "v2_activated": 6,
        "active_total": 78,
        "legacy_only": 6,
        "watch": 5,
        "adjacent": 12,
        "excluded": 4,
        "folded_variants": 1,
        "pseudo_families": 1,
        "negative_controls": 1,
        "ambiguous_lineages": 1,
    }
    assert SOURCE_PATH.exists()
    assert not list(SOURCE_PATH.parent.glob("*.csv"))
    active_ids = {family.id for family in PACK.families if family.category == "active"}
    assert active_ids <= {rule.family_id for rule in PACK.rules}


def test_schema_v2_freeze_roundtrip_and_metadata_immutability(clean_db):
    engine = clean_db()
    pack = replace(PACK, version="v2-freeze-test")
    freeze_pack(engine, pack)
    assert load_frozen(engine, "v2-freeze-test") == pack
    changed_rule = replace(pack.rules[0], note="different immutable content")
    with pytest.raises(PackConflict):
        freeze_pack(engine, replace(pack, rules=(changed_rule, *pack.rules[1:])))


def test_frozen_predecessor_file_hashes_are_pinned():
    expected = {
        "2026-10-14.json": "ce83792c19c29f1fe231c96753a7fe18079398a35c24c287fbb9bc00e801ee73",
        "2026-10-19.json": "4258d1d9a84617eae286c00b3742b303663375230a291f0697268f34b447ab2c",
    }
    for name, digest in expected.items():
        assert hashlib.sha256((ROOT / "packs" / name).read_bytes()).hexdigest() == digest


def test_path_semantics_are_explicit():
    assert path_matches("t3.json", {"regex": r"^t3\.json$", "root": True})
    assert not path_matches("nested/t3.json", {"regex": r"^t3\.json$", "root": True})
    assert not path_matches("T3.json", {"regex": r"^t3\.json$", "case_sensitive": True})
    assert path_matches(
        ".abacusai/hooks/pre.py",
        {"equals": ".abacusai/hooks", "kind": "directory", "descendants": True},
    )
    assert not path_matches(
        ".abacusai/hooks/pre.py",
        {"equals": ".abacusai/hooks", "kind": "directory", "descendants": False},
    )


def test_orca_requires_root_path_plus_parsed_product_key():
    matches, _ = _structured(["orca.yaml"], {})
    assert "orca.project-config" not in matches
    matches, diagnostics = _structured(["orca.yaml"], {"orca.yaml": "name: chemistry\n"})
    assert "orca.project-config" not in matches
    assert any(item.kind == "predicate_failure" for item in diagnostics)
    matches, _ = _structured(
        ["orca.yaml"], {"orca.yaml": "worktree:\n  sharedDirectories:\n    - node_modules\n"}
    )
    rule = matches["orca.project-config"].rule
    assert rule.semantics.evidence == "orchestration"
    assert rule.semantics.counts_as_authorship is False
    assert rule.semantics.counts_in_current_ratio is False
    nested, _ = _structured(["nested/orca.yaml"], {"nested/orca.yaml": "defaultTabs: []\n"})
    assert "orca.project-config" not in nested


def test_t3_requires_the_exact_json_schema():
    wrong, diagnostics = _structured(
        ["t3.json"], {"t3.json": '{"$schema":"https://example.test/t3.json"}'}
    )
    assert "t3-code.project-config" not in wrong
    assert any(item.rule_id == "t3-code.project-config" for item in diagnostics)
    right, _ = _structured(
        ["t3.json"], {"t3.json": '{"$schema":"https://t3.codes/schema/t3.json"}'}
    )
    assert "t3-code.project-config" in right
    malformed, diagnostics = _structured(["t3.json"], {"t3.json": "{"})
    assert "t3-code.project-config" not in malformed
    assert any(item.kind == "parse_failure" for item in diagnostics)


def test_github_agentic_workflows_require_pair_or_lock_metadata():
    markdown, _ = _structured([".github/workflows/review.md"], {})
    assert not {
        "github-agentic-workflows.same-stem",
        "github-agentic-workflows.metadata-lock",
    } & set(markdown)
    paired, _ = _structured(
        [".github/workflows/review.md", ".github/workflows/review.lock.yml"], {}
    )
    assert "github-agentic-workflows.same-stem" in paired
    metadata, _ = _structured(
        [".github/workflows/lone.lock.yml"],
        {".github/workflows/lone.lock.yml": "# gh-aw-metadata: v1\nname: generated\n"},
    )
    assert "github-agentic-workflows.metadata-lock" in metadata


def test_pr_agent_and_qodo_shared_config_resolve_without_double_attribution():
    ambiguous, _ = _structured([".pr_agent.toml"], {".pr_agent.toml": "[config]\nfoo=1\n"})
    assert set(ambiguous) == {"qodo-pr-agent.shared-config"}
    qodo, _ = _structured([".pr_agent.toml"], {".pr_agent.toml": "[review_agent]\nenabled=true\n"})
    assert "qodo.shared-config-specific" in qodo
    assert "qodo-pr-agent.shared-config" not in qodo
    workflow_path = ".github/workflows/pr-agent.yml"
    pr_agent, _ = _structured(
        [".pr_agent.toml", workflow_path],
        {
            ".pr_agent.toml": "[config]\nfoo=1\n",
            workflow_path: (
                "jobs:\n  review:\n    steps:\n" "      - uses: the-pr-agent/pr-agent@v0.31\n"
            ),
        },
    )
    assert "pr-agent.workflow-action" in pr_agent
    assert "qodo-pr-agent.shared-config" not in pr_agent


def test_gitlab_duo_branch_is_forge_scoped_and_not_authorship():
    assert match_branches(PACK, ["duo/fix/bug"], forge="github") == []
    hits = match_branches(PACK, ["duo/fix/bug"], forge="gitlab")
    assert [hit.family_id for hit in hits] == ["gitlab-duo"]
    assert hits[0].forge == "gitlab"
    assert hits[0].evidence_semantics == "orchestration"
    assert hits[0].metric_eligibility["authorship"] is False


def test_herder_uses_structured_trailer_ref_scope_and_corroborating_branch():
    assert parse_structured_trailers("Herder-Session: abc\nprose") == ()
    trailer_hits = match_commit_messages(
        PACK, [("c1", "feat: work\n\nHerder-Session: 01HZX", "2026-11-14T00:00:00Z")]
    )
    assert [hit.rule_id for hit in trailer_hits] == ["herder.session-trailer"]
    assert trailer_hits[0].evidence["trailer_token"] == "Herder-Session"
    assert (
        match_author_identities(
            PACK,
            [
                {
                    "name": "herder",
                    "email": "herder@localhost",
                    "login": "",
                    "commit": "c2",
                    "role": "author",
                }
            ],
        )
        == []
    )
    refs = [
        {
            "ref": "refs/herder/session/turn",
            "commit": "c2",
            "author_name": "herder",
            "author_email": "herder@localhost",
            "reachability": "remote_hidden_ref",
        }
    ]
    ref_hits = match_hidden_refs(PACK, refs)
    assert {hit.rule_id for hit in ref_hits} == {
        "herder.checkpoint-ref",
        "herder.checkpoint-identity",
    }
    branch = match_branches(PACK, ["herder/23456789"])
    assert [hit.rule_id for hit in branch] == ["herder.default-branch"]
    assert branch[0].metric_eligibility["current_presence"] is False


def test_replit_agent_and_deployment_values_remain_distinct():
    agent = match_commit_messages(PACK, [("c1", "feat: checkpoint\n\nReplit-Commit-Author: Agent")])
    assert [hit.rule_id for hit in agent] == ["replit.agent-checkpoint"]
    deployment = match_commit_messages(
        PACK, [("c2", "build: deploy\n\nReplit-Commit-Author: Deployment")]
    )
    assert [hit.rule_id for hit in deployment] == ["replit.deployment-control"]
    assert deployment[0].is_positive is False
    assert all(not value for value in deployment[0].metric_eligibility.values())
    assert match_files(PACK, _presence(".replit")) == []
    assert (
        match_author_identities(
            PACK,
            [
                {
                    "name": "Agent",
                    "email": "agent@replit.com",
                    "login": "",
                    "commit": "c3",
                    "role": "author",
                }
            ],
        )[0].family_id
        == "replit-agent"
    )


def test_abacus_exact_identity_lineage_composite_and_noise_regressions():
    current = match_author_identities(
        PACK,
        [
            {
                "name": "Abacus AI Agent",
                "email": "agent@abacus.ai",
                "login": "abacusai-agent",
                "commit": "c1",
                "role": "author",
                "observed_at": "2026-11-13T00:00:00Z",
            }
        ],
    )
    assert [hit.family_id for hit in current] == ["abacus-ai-agent"]
    assert current[0].metric_eligibility["authorship"] is True
    predecessor = match_author_identities(
        PACK,
        [
            {
                "name": "DeepAgent",
                "email": "agent@abacus.ai",
                "login": "",
                "commit": "c2",
                "role": "author",
                "observed_at": "2025-09-05T00:00:00Z",
            }
        ],
    )
    assert [(hit.family_id, hit.observed_as) for hit in predecessor] == [
        ("abacus-ai-agent", "DeepAgent")
    ]
    assert (
        match_author_identities(
            PACK,
            [
                {
                    "name": "Abacus AI Agent",
                    "email": "noreply@abacus.ai",
                    "login": "",
                    "commit": "c3",
                    "role": "author",
                }
            ],
        )
        == []
    )
    exact_trailer = match_commit_messages(
        PACK,
        [("c4", "feat: x\n\nCo-Authored-By: Abacus AI Agent <noreply@abacus.ai>")],
    )
    assert [hit.rule_id for hit in exact_trailer] == ["abacus.exact-noreply-coauthor"]
    wrong_name = match_commit_messages(
        PACK,
        [("c5", "feat: x\n\nCo-Authored-By: Build Bot <noreply@abacus.ai>")],
    )
    assert wrong_name == []
    release = match_bots(
        PACK,
        [
            {
                "login": "abacus-ai-automation[bot]",
                "name": "",
                "email": "194430910+abacus-ai-automation[bot]@users.noreply.github.com",
                "commit": "r1",
            }
        ],
    )
    assert release
    assert all(hit.is_positive is False and hit.family_id is None for hit in release)


def test_exact_commit_identities_do_not_become_forge_participants():
    prs = [{"number": 1, "author": "agent@abacus.ai", "createdAt": "2026-11-14"}]
    assert match_pr_authors(PACK, prs) == []


def test_legacy_rules_are_ever_observed_but_never_current_ratio_evidence():
    lingma = match_files(PACK, _presence(".lingma/settings.json"))
    assert [hit.rule_id for hit in lingma] == ["qoder.lingma-history"]
    assert lingma[0].is_historical is True
    assert lingma[0].metric_eligibility["current_presence"] is False
    assert lingma[0].metric_eligibility["current_commit_ratio"] is False
    assert lingma[0].explanatory_note == "Legacy marker present; current use unknown"
    opencode = match_author_identities(
        PACK,
        [
            {
                "name": "OpenCode",
                "email": "noreply@opencode.ai",
                "login": "",
                "commit": "old",
                "role": "author",
                "observed_at": "2025-01-01T00:00:00Z",
            }
        ],
    )
    assert opencode[0].is_historical is True
    assert opencode[0].metric_eligibility["authorship"] is True
    assert opencode[0].metric_eligibility["current_commit_ratio"] is False


def test_candidates_and_relationships_are_bounded_and_context_scoped():
    candidates, capped = content_candidates(
        PACK,
        ["src/app.py", "t3.json", "orca.yaml", ".github/workflows/review.yml"],
    )
    assert capped is False
    assert set(candidates) == {"t3.json", "orca.yaml", ".github/workflows/review.yml"}
    facts = [
        {"kind": "identity", "commit": "a", "value": "agent"},
        {"kind": "trailer", "commit": "a", "value": "session"},
        {"kind": "trailer", "commit": "b", "value": "session"},
    ]
    selected = relationship_matches(
        [{"kind": "identity"}, {"kind": "trailer"}],
        facts,
        relationship="same_commit",
    )
    assert {fact["commit"] for fact in selected} == {"a"}
