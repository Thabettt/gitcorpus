"""Attribute an ``AGENTS.md`` file to a coding agent from its contents.

``AGENTS.md`` is a shared format, not a product fingerprint.  A file that merely
mentions ``Cursor`` or ``Codex`` is usually describing a tool it supports, not
declaring that it is written for that tool.  A 100-file sample showed that:

* 42% of files never name a product at all;
* bare mentions agree with detection only 12-98% of the time depending on the
  product (``Cursor`` in "move the cursor" is a common false positive);
* only files with an explicit addressee ("you are Claude Code", "read by both
  Claude Code and opencode", "# Claude Code Guidelines") carry usable signal.

This module therefore implements a deliberately narrow, precision-first rule
set.  It returns an agent only when exactly one agent is *addressed* by the
file.  Multi-agent files and bare mentions return no attribution; they are
recorded as shared markers instead.

The classifier is a fallback for repositories that have no other named-agent
evidence.  It must never be used to add agents on top of a repository that is
already attributed through a product-owned path, commit identity, branch or PR.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

CONTENT_CHANNEL = "content"
CLASSIFIER_VERSION = "agents-md-v1"
MAX_CONTENT_BYTES = 200_000

#: Agent names and the tokens that identify them.  Tokens are intentionally
#: stricter than the pack patterns: bare ambiguous words (``claude``, ``cursor``,
#: ``gemini``, ``sweep``) are only accepted inside an ownership/address cue.
_AGENT_TOKENS: dict[str, tuple[str, ...]] = {
    "Claude Code": (
        r"claude\s+code",
        r"claude\.md",
        r"\.claude/",
        r"claude\.local\.md",
        r"claude\s+(?:cli|-p\b|--print)",
    ),
    "Codex": (
        r"(?<![A-Za-z0-9_-])codex(?![A-Za-z0-9_-])",
        r"\.codex/",
        r"codex-rs",
    ),
    "Cursor": (
        r"\.cursor/",
        r"\.cursorrules\b",
        r"cursor\s+rules",
        r"cursor\s+(?:ide|agent|cli|tasks?|chat|composer)",
        r"(?<![A-Za-z0-9_-])Cursor(?![A-Za-z0-9_-])",
    ),
    "Copilot": (
        r"(?<![A-Za-z0-9_-])copilot(?![A-Za-z0-9_-])",
        r"copilot-instructions",
    ),
    "Gemini": (
        r"gemini\s+cli",
        r"gemini\.md",
        r"\.gemini/",
        r"(?<![A-Za-z0-9_-])Gemini(?![A-Za-z0-9_-])",
    ),
    "Opencode": (
        r"(?<![A-Za-z0-9_-])opencode(?![A-Za-z0-9_-])",
        r"\.opencode/",
    ),
    "Aider": (r"(?<![A-Za-z0-9_-])aider(?![A-Za-z0-9_-])", r"\.aider"),
    "Windsurf": (
        r"(?<![A-Za-z0-9_-])windsurf(?![A-Za-z0-9_-])",
        r"\.windsurf",
    ),
    "Cline": (r"(?<![A-Za-z0-9_-])cline(?![A-Za-z0-9_-])", r"\.cline"),
    "Roo Code": (r"roo\s+code", r"\.roo/"),
    "Kiro": (r"(?<![A-Za-z0-9_-])kiro(?![A-Za-z0-9_-])", r"\.kiro/"),
    "Junie": (r"(?<![A-Za-z0-9_-])junie(?![A-Za-z0-9_-])", r"\.junie"),
    "Qwen Coder": (r"(?<![A-Za-z0-9_-])qwen(?![A-Za-z0-9_-])", r"\.qwen/"),
    "Goose": (r"(?<![A-Za-z0-9_-])goose(?![A-Za-z0-9_-])", r"\.goosehints"),
    "Warp": (r"warp\.dev", r"(?<![A-Za-z0-9_-])warp\s+(?:terminal|agent)"),
    "Devin": (r"devin\.ai", r"(?<![A-Za-z0-9_-])Devin(?![A-Za-z0-9_-])"),
    "Amp": (r"sourcegraph\.com/amp", r"(?<![A-Za-z0-9_-])amp\s+(?:agent|cli)"),
    "Kilo Code": (r"kilo\s+code", r"\.kilocode"),
    "Serena": (r"(?<![A-Za-z0-9_-])serena(?![A-Za-z0-9_-])",),
    "Taskmaster": (r"(?<![A-Za-z0-9_-])taskmaster(?![A-Za-z0-9_-])",),
    "Tessl": (r"(?<![A-Za-z0-9_-])tessl(?![A-Za-z0-9_-])",),
    "AmazonQ": (r"amazon\s*q\b", r"\.amazonq/"),
    "ChatGPT": (r"chatgpt",),
    "SpecKit": (r"spec\s*kit", r"\.specify/"),
    "Letta Code": (r"(?<![A-Za-z0-9_-])letta(?![A-Za-z0-9_-])",),
    "Mistral Vibe": (r"mistral\s+vibe", r"\.vibe/"),
    "Factory Droid": (r"factory\s+droid", r"\.factory/droids"),
    "Codebuddy": (r"codebuddy",),
    "Trae": (r"(?<![A-Za-z0-9_-])trae(?![A-Za-z0-9_-])", r"\.trae/"),
    "Augment Code": (r"augment\s+code", r"\.augment/"),
    "Plandex": (r"(?<![A-Za-z0-9_-])plandex(?![A-Za-z0-9_-])",),
    "Qodo": (r"(?<![A-Za-z0-9_-])qodo(?![A-Za-z0-9_-])",),
    "Rulesync": (r"rulesync",),
    "Verdent": (r"(?<![A-Za-z0-9_-])verdent(?![A-Za-z0-9_-])",),
    "Langchain Open SWE": (r"open[- ]swe\b",),
    "Sentry Seer": (r"sentry\s+seer",),
    "Microsoft Amplifier": (r"microsoft\s+amplifier",),
    "Baidu Comate": (r"(?<![A-Za-z0-9_-])comate(?![A-Za-z0-9_-])",),
    "Alibaba Lingma": (r"(?<![A-Za-z0-9_-])lingma(?![A-Za-z0-9_-])",),
    "Brokk": (r"(?<![A-Za-z0-9_-])brokk(?![A-Za-z0-9_-])",),
    "Sourcery": (r"(?<![A-Za-z0-9_-])sourcery(?![A-Za-z0-9_-])",),
    "GPT-Engineer": (r"gpt[- ]engineer",),
    "Deepsource": (r"(?<![A-Za-z0-9_-])deepsource(?![A-Za-z0-9_-])",),
    "Coderabbit": (r"(?<![A-Za-z0-9_-])coderabbit(?![A-Za-z0-9_-])",),
    "Jules": (r"(?<![A-Za-z0-9_-])jules(?![A-Za-z0-9_-])",),
    "Zed": (r"zed\.dev", r"(?<![A-Za-z0-9_-])zed\s+(?:editor|ide|agent|acp)"),
    "Codegen": (r"codegen\.com", r"(?<![A-Za-z0-9_-])codegen\s+(?:agent|cli)"),
}

#: Cues that make a product the addressee rather than the subject.  The capture
#: group is the text that should name exactly one agent.
_CUES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("you-are", re.compile(r"\byou\s+are\s+(?:an?\s+|the\s+)?([^\n.]{0,140})", re.I)),
    (
        "read-by",
        re.compile(r"\b(?:read|loaded|consumed|used)\s+by\s+([^\n.]{0,160})", re.I),
    ),
    (
        "written-for",
        re.compile(r"\b(?:written|made|intended|designed)\s+for\s+([^\n.]{0,140})", re.I),
    ),
    (
        "instructions-for",
        re.compile(
            r"\b(?:guidance|instructions?|rules?|guidelines|notes|context)"
            r"\s+(?:for|aimed\s+at)\s+([^\n.]{0,160})",
            re.I,
        ),
    ),
    (
        "this-file-for",
        re.compile(
            r"\bthis\s+(?:file|document|repo|repository|project)\s+(?:is|are)\s+"
            r"(?:for|written\s+for|intended\s+for)\s+([^\n.]{0,140})",
            re.I,
        ),
    ),
    (
        "agent-specific",
        re.compile(r"\b([A-Za-z][\w .+-]{1,30}?)[- ]specific\b", re.I),
    ),
    (
        "when-using",
        re.compile(
            r"\b(?:when|if)\s+(?:you\s+(?:are\s+)?)?(?:using|running|working\s+(?:in|with))"
            r"\s+([^\n.]{0,120})",
            re.I,
        ),
    ),
    (
        "reads-this",
        re.compile(
            r"\b([A-Za-z][\w .+-]{1,30}?)\s+(?:reads?|uses?|loads?|consumes?)\s+this\s+"
            r"(?:file|document)\b",
            re.I,
        ),
    ),
)

_TITLE = re.compile(r"^\s*#{1,2}\s*(.+)$")
_TITLE_CUE = re.compile(
    r"\b(guidelines?|instructions?|rules?|guide|notes|context|development|project\s+rules)\b",
    re.I,
)
_NEGATION = re.compile(r"\b(?:not|never|no\s+longer|don't|do\s+not|isn't|aren't)\b", re.I)
#: Phrases that mean "a list of agents", not "this file belongs to one agent".
_MULTI = re.compile(
    r"\b(?:any\s+other|other\s+agents?|or\s+whatever|such\s+as|e\.g\.|including|"
    r"and\s+many|etc\.|all\s+(?:coding\s+)?agents|any\s+(?:coding\s+)?agent|"
    r"whichever|whichever\s+agent|both\b)",
    re.I,
)
#: ``cursor`` is a common programming noun, not only the product.
_CURSOR_NOISE = re.compile(
    r"\b(?:pointer|mouse|caret|text\s+cursor|scroll|cursor\s+(?:position|movement|move|warp|"
    r"follows|blink)|ref\s+cursor|record\s*cursor|reconciliation_cursor|cursor\.rs|"
    r"has_cursor|window\s+cursor)\b",
    re.I,
)

_PATTERNS = {
    agent: tuple(re.compile(token, re.I) for token in tokens)
    for agent, tokens in _AGENT_TOKENS.items()
}


@dataclass(frozen=True)
class ContentSignal:
    agent: str
    cue: str
    snippet: str
    confidence: str


@dataclass(frozen=True)
class ContentAttribution:
    agents: tuple[str, ...]
    signals: tuple[ContentSignal, ...]
    version: str = CLASSIFIER_VERSION

    @property
    def attributed(self) -> bool:
        return bool(self.agents)


def _agents_in(window: str, known: frozenset[str]) -> list[str]:
    found: list[str] = []
    for agent, patterns in _PATTERNS.items():
        if agent not in known:
            continue
        if any(pattern.search(window) for pattern in patterns):
            found.append(agent)
    if "Cursor" in found and _CURSOR_NOISE.search(window):
        found.remove("Cursor")
    return found


def _title_agents(title: str, known: frozenset[str]) -> list[str]:
    lowered = title.lower()
    # A file whose own heading is the product's native filename is the
    # strongest content signal available: it is a copy/symlink of that file.
    if "claude.md" in lowered and "Claude Code" in known:
        return ["Claude Code"]
    if "gemini.md" in lowered and "Gemini" in known:
        return ["Gemini"]
    found = _agents_in(title, known)
    if not found:
        return []
    if _MULTI.search(title):
        return []
    if _TITLE_CUE.search(title) or len(title) <= 40:
        return found
    return []


def classify_agents_md(text: str, known_agents: Iterable[str] | None = None) -> ContentAttribution:
    """Return the single agent an ``AGENTS.md`` file is addressed to, if any.

    ``known_agents`` limits the result to agents present in the active pack.
    Bare product mentions never produce an attribution.
    """

    known = frozenset(known_agents) if known_agents is not None else frozenset(_PATTERNS)
    known &= frozenset(_PATTERNS)
    if not known or not text:
        return ContentAttribution((), ())

    text = text.lstrip("\ufeff")[:MAX_CONTENT_BYTES]
    signals: dict[str, list[ContentSignal]] = {}

    for line in text.splitlines()[:10]:
        match = _TITLE.match(line)
        if match is None:
            continue
        title = match.group(1).strip()
        for agent in _title_agents(title, known):
            signals.setdefault(agent, []).append(
                ContentSignal(agent, "title", title[:160], "medium")
            )
        break

    for cue, pattern in _CUES:
        for match in pattern.finditer(text):
            window = match.group(1).strip()
            prefix = text[max(0, match.start() - 30) : match.start()]
            suffix = text[match.end() : match.end() + 40]
            if _NEGATION.search(prefix):
                continue
            found = _agents_in(window, known)
            if not found:
                continue
            # A list of agents is shared evidence, not attribution.  Record the
            # mention so the caller can see why the file stayed unattributed.
            if _MULTI.search(window) or _MULTI.search(suffix) or len(found) > 1:
                continue
            confidence = "high" if cue in {"you-are", "read-by", "written-for"} else "medium"
            signals.setdefault(found[0], []).append(
                ContentSignal(found[0], cue, window[:160], confidence)
            )

    # Exactly one addressed agent is the only safe attribution.
    if len(signals) != 1:
        return ContentAttribution((), ())
    agent, found = next(iter(signals.items()))
    return ContentAttribution((agent,), tuple(found[:3]))


def attributed_agents(text: str, known_agents: Iterable[str] | None = None) -> tuple[str, ...]:
    """Convenience wrapper used by the detection channel."""

    return classify_agents_md(text, known_agents).agents
