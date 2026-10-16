from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from detect.packs import Pack, Pattern
from enrich.trees_first import FilePresence

CODEX_PR_BODY_MARKER = "https://chatgpt.com/codex/tasks"

_EMAIL = re.compile(r"<[^<>\s]+@[^<>\s]+>|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

_NOISE_PATTERNS = (
    re.compile(r"^Merge "),
    re.compile(r"^Revert "),
    re.compile(r"^chore(\(.+\))?: (bump|release|version)\b", re.IGNORECASE),
    re.compile(r"^v?\d+\.\d+\.\d+\s*$"),
    re.compile(r"\[skip ci\]", re.IGNORECASE),
)


@dataclass(frozen=True)
class Hit:
    agent: str
    channel: str
    evidence: dict


@dataclass(frozen=True)
class ChannelRegex:
    regex: re.Pattern[str] | None
    names: Mapping[str, str]


def redact_emails(text: str) -> str:
    return _EMAIL.sub("<email>", text)


def is_noise_commit(message: str) -> bool:
    first = (message or "").split("\n", 1)[0].strip()
    return any(pattern.search(first) for pattern in _NOISE_PATTERNS)


def adoption_level(ratio: float | None) -> str:
    if ratio is None:
        return "none"
    if ratio < 0.01:
        return "experimental"
    if ratio < 0.05:
        return "limited"
    if ratio < 0.20:
        return "consistent"
    return "pervasive"


def _sanitize(name: str) -> str:
    return re.sub(r"\W+", "_", name)


def _selected(patterns: Sequence[Pattern], agents: frozenset[str] | None) -> tuple[Pattern, ...]:
    if agents is None:
        return tuple(patterns)
    return tuple(pattern for pattern in patterns if pattern.agent in agents)


def build_channel_regex(patterns: Sequence[Pattern], *, is_files: bool = False) -> ChannelRegex:
    groups: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for pattern in patterns:
        name = _sanitize(pattern.agent)
        names.setdefault(name, pattern.agent)
        raw = pattern.pattern
        if is_files:
            if "." in raw and "\\." not in raw:
                raw = raw.replace(".", "\\.")
            if not raw.startswith("(?:^|/)") and not raw.startswith("^"):
                raw = "(?:^|/)" + raw
        groups.setdefault(name, []).append(raw)
    if not groups:
        return ChannelRegex(regex=None, names={})
    parts = [f"(?P<{name}>{'|'.join(pats)})" for name, pats in groups.items()]
    return ChannelRegex(regex=re.compile("|".join(parts)), names=names)


_MATCHER_CACHE: dict[str, dict[str, ChannelRegex]] = {}


def clear_matcher_cache() -> None:
    _MATCHER_CACHE.clear()


def _cache_key(pack: Pack, agents: frozenset[str] | None) -> str:
    suffix = "*" if agents is None else ",".join(sorted(agents))
    content = (pack.files, pack.authors, pack.branches, pack.labels, pack.bots)
    return f"{pack.version}|{hash(content)}|{suffix}"


def matchers_for(pack: Pack, agents: frozenset[str] | None = None) -> dict[str, ChannelRegex]:
    key = _cache_key(pack, agents)
    cached = _MATCHER_CACHE.get(key)
    if cached is None:
        cached = {
            "file": build_channel_regex(_selected(pack.files, agents), is_files=True),
            "author": build_channel_regex(_selected(pack.authors, agents)),
            "branch": build_channel_regex(_selected(pack.branches, agents)),
            "label": build_channel_regex(_selected(pack.labels, agents)),
            "bot": build_channel_regex(pack.bots),
        }
        _MATCHER_CACHE[key] = cached
    return cached


def _generic_weight(pack: Pack, path: str) -> float | None:
    for pattern in pack.files:
        key = pattern.pattern.replace("\\", "")
        if key in pack.generic_weights and re.search(f"(?:^|/){pattern.pattern}", path):
            return pack.generic_weights[key]
    return None


def match_files(
    pack: Pack,
    presence: FilePresence,
    agents: frozenset[str] | None = None,
) -> list[Hit]:
    channel = matchers_for(pack, agents)["file"]
    if channel.regex is None:
        return []
    hits: list[Hit] = []
    for path in sorted(presence.paths):
        if path.rsplit("/", 1)[-1] in pack.exclusions or path in pack.exclusions:
            continue
        for match in channel.regex.finditer(path):
            if match.lastgroup is None:
                continue
            evidence: dict = {"path": path, "source": presence.source}
            weight = _generic_weight(pack, path)
            if weight is not None:
                evidence["generic"] = True
                evidence["weight"] = weight
            hits.append(Hit(channel.names[match.lastgroup], "file", evidence))
    return dedupe_hits(hits)


def _match_values(
    channel: ChannelRegex,
    values: Iterable[str],
    *,
    name: str,
    key: str,
) -> list[Hit]:
    if channel.regex is None:
        return []
    hits: list[Hit] = []
    for value in values:
        if not value:
            continue
        for match in channel.regex.finditer(value):
            if match.lastgroup is None:
                continue
            hits.append(
                Hit(
                    channel.names[match.lastgroup],
                    name,
                    {key: value[:300], "match": match.group()[:100]},
                )
            )
    return hits


def _match_identity_fields(
    channel: ChannelRegex,
    entries: Iterable[Mapping[str, object]],
    *,
    name: str,
) -> list[Hit]:
    if channel.regex is None:
        return []
    hits: list[Hit] = []
    for entry in entries:
        commit = str(entry.get("commit") or "")
        login = str(entry.get("login") or "")
        for field in ("login", "name", "email"):
            value = str(entry.get(field) or "")
            if not value:
                continue
            for match in channel.regex.finditer(value):
                if match.lastgroup is None:
                    continue
                hits.append(
                    Hit(
                        channel.names[match.lastgroup],
                        name,
                        {"login": login, "commit": commit, "field": field},
                    )
                )
    return hits


def match_author_identities(
    pack: Pack, entries: Iterable[Mapping[str, object]], agents: frozenset[str] | None = None
) -> list[Hit]:
    channel = matchers_for(pack, agents)["author"]
    return dedupe_hits(_match_identity_fields(channel, entries, name="author"))


def match_bots(
    pack: Pack, entries: Iterable[Mapping[str, object]], agents: frozenset[str] | None = None
) -> list[Hit]:
    channel = matchers_for(pack, agents)["bot"]
    return dedupe_hits(_match_identity_fields(channel, entries, name="bot"))


def match_commit_messages(
    pack: Pack, messages: Iterable[tuple[str, str]], agents: frozenset[str] | None = None
) -> list[Hit]:
    channel = matchers_for(pack, agents)["author"]
    if channel.regex is None:
        return []
    hits: list[Hit] = []
    for commit, message in messages:
        if not message or is_noise_commit(message):
            continue
        for match in channel.regex.finditer(message):
            if match.lastgroup is None:
                continue
            window = message[max(0, match.start() - 30) : match.end() + 70]
            snippet = redact_emails(window)[:100]
            hits.append(
                Hit(
                    channel.names[match.lastgroup],
                    "commit_trailer",
                    {"commit": commit, "snippet": snippet},
                )
            )
    return dedupe_hits(hits)


def match_branches(
    pack: Pack, branches: Iterable[str], agents: frozenset[str] | None = None
) -> list[Hit]:
    return _match_values(
        matchers_for(pack, agents)["branch"], branches, name="branch", key="branch"
    )


def match_labels(
    pack: Pack, labels: Iterable[str], agents: frozenset[str] | None = None
) -> list[Hit]:
    return _match_values(matchers_for(pack, agents)["label"], labels, name="label", key="label")


def match_pr_metadata(
    pack: Pack, prs: Iterable[Mapping[str, object]], agents: frozenset[str] | None = None
) -> list[Hit]:
    hits: list[Hit] = []
    for pr in prs:
        number = pr.get("number")
        head = str(pr.get("headRefName") or "")
        labels = [str(x) for x in pr.get("labels") or []]
        body = str(pr.get("body") or "")
        for hit in match_branches(pack, [head] if head else [], agents):
            hits.append(
                Hit(
                    hit.agent,
                    "branch",
                    {"pr": number, "head": head, "match": hit.evidence["match"]},
                )
            )
        for hit in match_labels(pack, labels, agents):
            hits.append(
                Hit(
                    hit.agent,
                    "label",
                    {"pr": number, "label": hit.evidence["label"], "match": hit.evidence["match"]},
                )
            )
        if body and CODEX_PR_BODY_MARKER in body and (agents is None or "Codex" in agents):
            hits.append(
                Hit("Codex", "pr_metadata", {"pr": number, "snippet": CODEX_PR_BODY_MARKER})
            )
    return dedupe_hits(hits)


def match_pr_authors(
    pack: Pack, prs: Iterable[Mapping[str, object]], agents: frozenset[str] | None = None
) -> list[Hit]:
    channel = matchers_for(pack, agents)["author"]
    hits: list[Hit] = []
    for pr in prs:
        login = str(pr.get("author") or "")
        if not login:
            continue
        for hit in _match_values(channel, [login], name="pr_metadata", key="author"):
            hits.append(Hit(hit.agent, "pr_metadata", {"pr": pr.get("number"), "author": login}))
    return dedupe_hits(hits)


def match_issue_participants(
    pack: Pack, entries: Iterable[Mapping[str, object]], agents: frozenset[str] | None = None
) -> list[Hit]:
    channel = matchers_for(pack, agents)["author"]
    hits: list[Hit] = []
    for entry in entries:
        login = str(entry.get("login") or "")
        if not login:
            continue
        for hit in _match_values(channel, [login], name="issue", key="login"):
            hits.append(
                Hit(
                    hit.agent,
                    "issue",
                    {
                        "login": login,
                        "number": entry.get("number"),
                        "role": entry.get("role"),
                    },
                )
            )
    return dedupe_hits(hits)


def propagate_pr_commits(hits: Iterable[Hit], prs: Iterable[Mapping[str, object]]) -> list[Hit]:
    by_number = {pr.get("number"): pr for pr in prs}
    agents_by_pr: dict[object, set[str]] = {}
    for hit in hits:
        number = hit.evidence.get("pr")
        if number is not None:
            agents_by_pr.setdefault(number, set()).add(hit.agent)
    propagated: list[Hit] = []
    for number, agents in agents_by_pr.items():
        pr = by_number.get(number)
        if pr is None:
            continue
        author = str(pr.get("author") or "")
        if not author:
            continue
        for commit in pr.get("commits") or []:
            if not isinstance(commit, Mapping):
                continue
            oid = str(commit.get("oid") or "")
            if not oid or str(commit.get("author") or "") != author:
                continue
            for agent in sorted(agents):
                propagated.append(
                    Hit(agent, "pr_metadata", {"pr": number, "commit": oid, "propagated": True})
                )
    return dedupe_hits(propagated)


def dedupe_hits(hits: Iterable[Hit]) -> list[Hit]:
    seen: set[str] = set()
    unique: list[Hit] = []
    for hit in hits:
        key = json.dumps(
            [hit.agent, hit.channel, hit.evidence], sort_keys=True, separators=(",", ":")
        )
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique
