from __future__ import annotations

import pytest

from detect.content_attribution import (
    CLASSIFIER_VERSION,
    ContentAttribution,
    attributed_agents,
    classify_agents_md,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("# Claude Code Guidelines for Alder\n", ["Claude Code"]),
        ("# CLAUDE.md\n", ["Claude Code"]),
        ("# Project Rules (Codex Agents)\n", ["Codex"]),
        ("You are Claude Code. Follow these rules.\n", ["Claude Code"]),
        ("When using Codex CLI, validate the GUI.\n", ["Codex"]),
    ],
)
def test_classify_agents_md_attributes_one_addressed_agent(text, expected):
    result = classify_agents_md(text)
    assert list(result.agents) == expected
    assert result.version == CLASSIFIER_VERSION
    assert result.signals
    assert all(signal.agent == expected[0] for signal in result.signals)


@pytest.mark.parametrize(
    "text",
    [
        "# Guidance\nRead by Claude Code, Codex, Cursor, or whatever comes next.\n",
        "# Guidance\nThis file is read by both Claude Code and OpenCode.\n",
        "# Guidance\nMove the cursor to the next line and scroll.\n",
        "# Guidance\nSupports installation for Cursor and Copilot.\n",
        "# Guidance\nNo product is named here.\n",
    ],
)
def test_classify_agents_md_rejects_bare_and_multi_agent_mentions(text):
    assert classify_agents_md(text) == ContentAttribution((), ())
    assert attributed_agents(text) == ()


def test_classify_agents_md_limits_results_to_known_agents():
    text = "# Project Rules (Codex Agents)\n"
    assert classify_agents_md(text, {"Codex"}).agents == ("Codex",)
    assert classify_agents_md(text, {"Claude Code"}).agents == ()


def test_classify_agents_md_ignores_cursor_as_a_pointer_noun():
    text = "You are implementing a cursor position tracker.\n"
    assert classify_agents_md(text).agents == ()


def test_classify_agents_md_does_not_match_zed_inside_specialized():
    text = (
        "This file is loaded by trustee's lifecycle system and can morph "
        "into specialized agents.\n"
    )
    assert classify_agents_md(text).agents == ()
