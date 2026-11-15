"""Regression tests for trace pack 2026-11-15.

The static checks read only JSON/CSV. The behaviour checks need the schema-v2
matcher (``detect.structured``) and are skipped where it is not present.
"""

from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / "packs" / "2026-11-15.json"
MAPPING = ROOT / "packs" / "sources" / "2026-11-15" / "baseline-mapping.csv"
BASELINE = ROOT / "packs" / "patterns"


def _pack_doc() -> dict:
    return json.loads(PACK.read_text(encoding="utf-8"))


def _mapping() -> list[dict]:
    with MAPPING.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_every_agentic_much_heuristic_is_mapped_or_ledgered():
    doc = _pack_doc()
    ids = {r["id"] for r in doc["rules"]} | {r["id"] for r in doc["rejections"]}
    rows = _mapping()
    baseline = 0
    for name in ("authors", "files", "branches", "labels", "bots"):
        with (BASELINE / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
            baseline += sum(1 for _ in csv.DictReader(handle))
    assert len(rows) == baseline
    for row in rows:
        targets = [t for t in row["rules"].split() if t not in {"noise", "ledger"}]
        assert row["outcome"], row
        assert row["rules"].strip(), row
        assert all(t in ids for t in targets), row


def test_rejected_heuristics_point_at_rejection_entries():
    doc = _pack_doc()
    rejection_ids = {r["id"] for r in doc["rejections"]}
    for row in _mapping():
        if row["outcome"] == "rejected":
            assert row["rules"] in rejection_ids, row


def test_every_positive_rule_declares_cohort_and_validation():
    for rule in _pack_doc()["rules"]:
        if rule.get("disposition") == "positive":
            assert rule["provenance"]["cohort"] in {
                "agentic-much-baseline",
                "2026-11-14",
                "extended",
            }, rule["id"]
            assert "status" in rule["provenance"]["validation"], rule["id"]


v2 = pytest.mark.skipif(
    importlib.util.find_spec("detect.structured") is None,
    reason="schema-v2 matcher not present in this checkout",
)


@pytest.fixture
def pack():
    from detect.packs import load_pack_file

    return load_pack_file(PACK)


def _file_agents(pack, path):
    from detect.attribution import match_files
    from enrich.trees_first import FilePresence

    presence = FilePresence("o/r", frozenset([path]), False, "tree")
    return {hit.agent for hit in match_files(pack, presence) if hit.is_positive}


@v2
@pytest.mark.parametrize(
    ("path", "agent"),
    [
        (".claude/", "Claude Code"),  # truncated-tree directory probe
        ("apps/web/.claude/settings.json", "Claude Code"),  # nested config
        ("packages/x/CLAUDE.md", "Claude Code"),
        ("GEMINI.md", "Google Antigravity / Gemini Code Assist"),
        (".clinerules/00-rules.md", "Cline"),
        (".specify/memory/constitution.md", "SpecKit"),  # adjacent, recorded
    ],
)
def test_file_evidence_restored(pack, path, agent):
    assert agent in _file_agents(pack, path)


@v2
def test_cursor_md_stays_rejected(pack):
    assert "Cursor" not in _file_agents(pack, "docs/harnesses/CURSOR.md")


@v2
def test_trailers_and_negative_controls(pack):
    from detect.attribution import match_commit_messages

    messages = [
        ("c1", "fix\n\nCo-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>"),
        ("c2", "fix\n\nCo-authored-by: Cursor Agent <cursoragent@cursor.com>"),
        ("c3", "fix\n\nCo-authored-by: Claude Shannon <claude@shannon.org>"),
        (
            "c4",
            "fix\n\nCo-authored-by: Copilot Autofix powered by AI "
            "<62310815+github-advanced-security[bot]@users.noreply.github.com>",
        ),
    ]
    hits = match_commit_messages(pack, messages)
    by_commit = {}
    for hit in hits:
        by_commit.setdefault(hit.evidence["commit"], []).append(hit)
    assert {h.agent for h in by_commit["c1"]} == {"Claude Code"}
    assert {h.agent for h in by_commit["c2"]} == {"Cursor"}
    assert "c3" not in by_commit
    autofix = by_commit["c4"]
    assert {h.variant for h in autofix} == {"Copilot Autofix"}
    assert not any(h.metric_eligibility.get("repository_presence") for h in autofix)


@v2
def test_agent_pull_requests(pack):
    from detect.attribution import match_pr_authors, match_pr_metadata

    prs = [
        {
            "number": 1,
            "headRefName": "jules/fix-1",
            "labels": [],
            "body": "",
            "author": "google-labs-jules",
        },
        {
            "number": 2,
            "headRefName": "copilot/fix-2",
            "labels": [],
            "body": "",
            "author": "Copilot",
        },
        {
            "number": 3,
            "headRefName": "feature",
            "labels": ["codex"],
            "body": "",
            "author": "someone",
        },
    ]
    hits = match_pr_metadata(pack, prs) + match_pr_authors(pack, prs)
    agents = {(hit.agent, hit.evidence.get("pr")) for hit in hits}
    assert ("Jules", 1) in agents
    assert ("Copilot", 2) in agents
    assert ("Codex", 3) in agents
