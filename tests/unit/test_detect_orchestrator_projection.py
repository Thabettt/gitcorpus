from __future__ import annotations

from detect.attribution import Hit
from detect.channels import ChannelResult
from detect.orchestrator import _repo_document, _RepoScan, _scan_contribution


def _scan(hits: list[Hit]) -> _RepoScan:
    return _RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=hits,
        results={"file": ChannelResult(status="ok")},
        pr_result=None,
        history_stats={},
    )


def _content_hit(agent: str = "Claude Code") -> Hit:
    return Hit(
        agent,
        "content",
        {
            "path": "AGENTS.md",
            "source": "tree",
            "cue": "title",
            "snippet": "# Claude Code Guidelines",
            "confidence": "medium",
            "classifier": "agents-md-v1",
        },
    )


def test_generic_only_evidence_is_marker_not_agent():
    scan = _scan(
        [
            Hit("Generic", "file", {"path": "AGENTS.md"}),
            Hit("Generic", "author", {"login": "AI Assistant"}),
        ]
    )
    document = _repo_document(scan)
    assert document["agents"] == []
    assert document["generic_markers"] == ["AGENTS.md", "author:AI Assistant"]
    assert document["content_attribution"] == []

    scan.document = document
    contribution = _scan_contribution(scan)
    assert contribution.has_signal is False
    assert contribution.agent_counts == {}
    assert contribution.channel_counts == {}


def test_content_attribution_is_used_only_without_a_named_agent():
    scan = _scan(
        [
            Hit("Generic", "file", {"path": "AGENTS.md"}),
            _content_hit(),
        ]
    )
    document = _repo_document(scan)
    assert document["agents"] == ["Claude Code"]
    assert document["generic_markers"] == ["AGENTS.md"]
    assert document["content_attribution"] == [
        {
            "agent": "Claude Code",
            "path": "AGENTS.md",
            "cue": "title",
            "confidence": "medium",
            "classifier": "agents-md-v1",
        }
    ]

    scan.document = document
    contribution = _scan_contribution(scan)
    assert contribution.has_signal is True
    assert contribution.agent_counts == {"Claude Code": 1}
    assert contribution.channel_counts == {"content": 1}


def test_direct_named_agent_suppresses_content_fallback():
    scan = _scan(
        [
            Hit("Generic", "file", {"path": "AGENTS.md"}),
            Hit("Claude Code", "file", {"path": "CLAUDE.md"}),
            _content_hit("Codex"),
        ]
    )
    document = _repo_document(scan)
    assert document["agents"] == ["Claude Code"]
    assert document["content_attribution"] == []
    assert document["generic_markers"] == ["AGENTS.md"]

    scan.document = document
    contribution = _scan_contribution(scan)
    assert contribution.agent_counts == {"Claude Code": 1}
    assert contribution.channel_counts == {"file": 1}
