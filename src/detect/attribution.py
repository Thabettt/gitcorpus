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

AMBIGUOUS = frozenset(
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

_BOUNDARY = r"(?<![A-Za-z0-9_-])(?:{})(?![A-Za-z0-9_-])"

_LINE_PREFIX = r"[ \t>*•\-\U0001F300-\U0001FAFF\u2600-\u27BF]*"

_TRAILER_TOKENS = (
    "co-authored-by|authored-by|author|committer|signed-off-by|assisted-by|"
    "co-developed-by|developed-by|generated-by|written-by|ai-assisted"
)
_TRAILER_LINE = re.compile(rf"^{_LINE_PREFIX}(?:{_TRAILER_TOKENS}):[ \t]*(.*)$", re.IGNORECASE)

_FOOTER_VERBS = (
    "generated|created|written|made|built|assisted|co-authored|authored|powered|developed"
)
_FOOTER_LINE = re.compile(
    rf"^{_LINE_PREFIX}(?:{_FOOTER_VERBS})\b.{{0,40}}?\b(?:with|by|using)\b", re.IGNORECASE
)

_GENERIC_TOKEN_LINE = re.compile(rf"^{_LINE_PREFIX}([A-Za-z][A-Za-z0-9_-]*):[ \t]*(.*)$")
_PROSE_TOKENS = frozenset(
    {"note", "warning", "fix", "fixes", "todo", "example", "update", "changes"}
)


def is_ambiguous(pattern: str) -> bool:
    return pattern.lower() in AMBIGUOUS


def boundary_wrap(pattern: str) -> str:
    return _BOUNDARY.format(pattern)


_BOT_SUFFIX = re.compile(r"(?:\[bot\]|-bot)$", re.IGNORECASE)
_NOREPLY = re.compile(r"^(?:\d+\+)?(?P<login>[^@+]+)@users\.noreply\.github\.com$", re.IGNORECASE)


def _normalize_login(value: str) -> str:
    return _BOT_SUFFIX.sub("", (value or "").strip()).lower()


def _email_login(value: str) -> str:
    address = (value or "").strip()
    match = _NOREPLY.match(address)
    if match is not None:
        return _normalize_login(match.group("login"))
    return _normalize_login(address.split("@", 1)[0])


def _is_multi_token(pattern: str) -> bool:
    plain = re.sub(r"\\(.)", r"\1", pattern)
    return " " in plain or "\t" in plain or "-" in plain


def _trailer_lines(message: str) -> list[str]:
    lines = message.split("\n")
    last_blank = -1
    for index, line in enumerate(lines):
        if not line.strip():
            last_blank = index
    extracts: list[str] = []
    for index, line in enumerate(lines):
        if _TRAILER_LINE.match(line) or _FOOTER_LINE.match(line):
            extracts.append(line)
        elif last_blank >= 0 and index > last_blank:
            token = _GENERIC_TOKEN_LINE.match(line)
            if token is not None and token.group(1).lower() not in _PROSE_TOKENS:
                extracts.append(line)
    return extracts


@dataclass(frozen=True)
class Hit:
    agent: str
    channel: str
    evidence: dict


@dataclass(frozen=True)
class IdentityPattern:
    regex: re.Pattern[str]
    agent: str
    multi: bool = False


@dataclass(frozen=True)
class IdentityChannel:
    email: tuple[IdentityPattern, ...]
    login_substring: tuple[IdentityPattern, ...]
    login_exact: tuple[IdentityPattern, ...]
    name: tuple[IdentityPattern, ...]
    ambiguous: tuple[tuple[str, re.Pattern[str], str], ...]


@dataclass(frozen=True)
class ChannelRegex:
    regex: re.Pattern[str] | None
    names: Mapping[str, str]
    identity: IdentityChannel | None = None


def _build_identity(patterns: Sequence[Pattern]) -> IdentityChannel:
    email: list[IdentityPattern] = []
    login_substring: list[IdentityPattern] = []
    login_exact: list[IdentityPattern] = []
    name: list[IdentityPattern] = []
    ambiguous: list[tuple[str, re.Pattern[str], str]] = []
    for pattern in patterns:
        raw = pattern.pattern
        if is_ambiguous(raw):
            ambiguous.append(
                (raw.lower(), re.compile(boundary_wrap(raw), re.IGNORECASE), pattern.agent)
            )
            continue
        multi = _is_multi_token(raw)
        if "@" in raw:
            email.append(IdentityPattern(re.compile(raw, re.IGNORECASE), pattern.agent))
        name.append(
            IdentityPattern(re.compile(boundary_wrap(raw), re.IGNORECASE), pattern.agent, multi)
        )
        if multi:
            login_substring.append(
                IdentityPattern(re.compile(boundary_wrap(raw), re.IGNORECASE), pattern.agent, True)
            )
        else:
            login_exact.append(IdentityPattern(re.compile(raw, re.IGNORECASE), pattern.agent))
    return IdentityChannel(
        email=tuple(email),
        login_substring=tuple(login_substring),
        login_exact=tuple(login_exact),
        name=tuple(name),
        ambiguous=tuple(ambiguous),
    )


def redact_emails(text: str) -> str:
    return _EMAIL.sub("<email>", text)


def _snippet(text: str, start: int, end: int) -> str:
    return redact_emails(text[max(0, start - 30) : end + 70])[:100]


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


def build_channel_regex(
    patterns: Sequence[Pattern],
    *,
    is_files: bool = False,
    is_authors: bool = False,
) -> ChannelRegex:
    identity = _build_identity(patterns) if is_authors else None
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
        if is_authors and is_ambiguous(raw):
            raw = boundary_wrap(raw)
        groups.setdefault(name, []).append(raw)
    if not groups:
        return ChannelRegex(regex=None, names={}, identity=identity)
    parts = [f"(?P<{name}>{'|'.join(pats)})" for name, pats in groups.items()]
    flags = re.IGNORECASE if is_authors else 0
    return ChannelRegex(regex=re.compile("|".join(parts), flags), names=names, identity=identity)


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
        author_patterns = _selected(pack.authors, agents)
        cached = {
            "file": build_channel_regex(_selected(pack.files, agents), is_files=True),
            "author": build_channel_regex(author_patterns, is_authors=True),
            "author_email": build_channel_regex(
                tuple(pattern for pattern in author_patterns if "@" in pattern.pattern),
                is_authors=True,
            ),
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


def _login_agents(identity: IdentityChannel, login: str) -> list[str]:
    normalized = _normalize_login(login)
    agents: list[str] = []
    for pattern in identity.login_substring:
        if pattern.regex.search(login) and pattern.agent not in agents:
            agents.append(pattern.agent)
    for pattern in identity.login_exact:
        if pattern.regex.fullmatch(normalized) and pattern.agent not in agents:
            agents.append(pattern.agent)
    for word, _regex, agent in identity.ambiguous:
        if normalized == word and agent not in agents:
            agents.append(agent)
    return agents


def _match_values(
    channel: ChannelRegex,
    values: Iterable[str],
    *,
    name: str,
    key: str,
) -> list[Hit]:
    if channel.regex is None and channel.identity is None:
        return []
    hits: list[Hit] = []
    for value in values:
        if not value:
            continue
        if channel.identity is not None:
            for agent in _login_agents(channel.identity, value):
                hits.append(Hit(agent, name, {key: value[:300], "match": value[:100]}))
            continue
        if channel.regex is None:
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


def _match_identity_entries(
    identity: IdentityChannel,
    entries: Iterable[Mapping[str, object]],
    *,
    name: str,
) -> list[Hit]:
    hits: list[Hit] = []
    for entry in entries:
        commit = str(entry.get("commit") or "")
        login = str(entry.get("login") or "")
        email = str(entry.get("email") or "")
        person = str(entry.get("name") or "")
        matched: dict[str, str] = {}

        if email:
            for pattern in identity.email:
                if pattern.regex.search(email):
                    matched.setdefault(pattern.agent, "email")
            email_login = _email_login(email)
            for word, _regex, agent in identity.ambiguous:
                if email_login == word:
                    matched.setdefault(agent, "email")

        if login:
            normalized = _normalize_login(login)
            for pattern in identity.login_substring:
                if pattern.regex.search(login):
                    matched.setdefault(pattern.agent, "login")
            for pattern in identity.login_exact:
                if pattern.regex.fullmatch(normalized):
                    matched.setdefault(pattern.agent, "login")
            for word, _regex, agent in identity.ambiguous:
                if normalized == word:
                    matched.setdefault(agent, "login")

        if person:
            name_agents: list[str] = []
            multi_agents: set[str] = set()
            for pattern in identity.name:
                if pattern.regex.search(person):
                    if pattern.agent not in name_agents:
                        name_agents.append(pattern.agent)
                    if pattern.multi:
                        multi_agents.add(pattern.agent)
            corroborated = set(matched) | multi_agents
            for _word, regex, agent in identity.ambiguous:
                if agent in corroborated and regex.search(person):
                    matched.setdefault(agent, "name")
            for agent in name_agents:
                matched.setdefault(agent, "name")

        for agent, field in matched.items():
            hits.append(Hit(agent, name, {"login": login, "commit": commit, "field": field}))
    return hits


def _match_identity_fields(
    channel: ChannelRegex,
    entries: Iterable[Mapping[str, object]],
    *,
    name: str,
) -> list[Hit]:
    if channel.identity is not None:
        return _match_identity_entries(channel.identity, entries, name=name)
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
    channels = matchers_for(pack, agents)
    channel = channels["author"]
    if channel.regex is None:
        return []
    email_channel = channels["author_email"]
    hits: list[Hit] = []
    seen: set[tuple[str, str]] = set()
    for commit, message in messages:
        if not message or is_noise_commit(message):
            continue
        extracts = _trailer_lines(message)
        has_email = "@" in message
        if not extracts and not has_email:
            continue
        snippets: dict[str, str] = {}
        tier1_email = False
        for line in extracts:
            for match in channel.regex.finditer(line):
                if match.lastgroup is None:
                    continue
                if "@" in match.group():
                    tier1_email = True
                snippets.setdefault(
                    channel.names[match.lastgroup], _snippet(line, match.start(), match.end())
                )
        if has_email and not tier1_email and email_channel.regex is not None:
            for match in email_channel.regex.finditer(message):
                if match.lastgroup is None:
                    continue
                agent = email_channel.names[match.lastgroup]
                if agent in snippets:
                    continue
                snippets[agent] = _snippet(message, match.start(), match.end())
        for agent, snippet in snippets.items():
            key = (commit, agent)
            if key in seen:
                continue
            seen.add(key)
            hits.append(Hit(agent, "commit_trailer", {"commit": commit, "snippet": snippet}))
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
