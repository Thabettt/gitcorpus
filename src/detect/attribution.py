from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime

from detect.packs import Pack, Pattern
from detect.structured import evaluate_file_rules
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
        return match.group("login")
    return address.split("@", 1)[0]


def _is_multi_token(pattern: str) -> bool:
    plain = re.sub(r"\\(.)", r"\1", pattern)
    return " " in plain or "\t" in plain or "-" in plain


def _trailer_lines(message: str) -> list[tuple[str, bool]]:
    lines = message.split("\n")
    last_blank = -1
    for index, line in enumerate(lines):
        if not line.strip():
            last_blank = index
    extracts: list[tuple[str, bool]] = []
    for index, line in enumerate(lines):
        if _TRAILER_LINE.match(line) or _FOOTER_LINE.match(line):
            extracts.append((line, False))
        elif last_blank >= 0 and index > last_blank:
            token = _GENERIC_TOKEN_LINE.match(line)
            if token is not None and token.group(1).lower() not in _PROSE_TOKENS:
                extracts.append((line, True))
    return extracts


@dataclass(frozen=True)
class StructuredTrailer:
    token: str
    value: str
    line: str
    line_number: int
    location: str = "trailer"
    name: str | None = None
    email: str | None = None


_STRUCTURED_TRAILER = re.compile(r"^(?P<token>[A-Za-z][A-Za-z0-9-]*):[ \t]*(?P<value>.*?)\s*$")
_IDENTITY_VALUE = re.compile(r"^(?P<name>.*?)\s*<(?P<email>[^<>\s]+@[^<>\s]+)>\s*$")


def parse_structured_trailers(message: str) -> tuple[StructuredTrailer, ...]:
    """Parse only the final Git trailer block, never token-looking prose."""

    lines = message.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    if not lines:
        return ()
    parsed_reversed: list[StructuredTrailer] = []
    index = len(lines) - 1
    while index >= 0:
        match = _STRUCTURED_TRAILER.match(lines[index])
        if match is None:
            break
        value = match.group("value")
        identity = _IDENTITY_VALUE.fullmatch(value)
        parsed_reversed.append(
            StructuredTrailer(
                token=match.group("token"),
                value=value,
                line=lines[index],
                line_number=index + 1,
                name=(identity.group("name").strip() if identity is not None else None),
                email=(identity.group("email") if identity is not None else None),
            )
        )
        index -= 1
    if not parsed_reversed:
        return ()
    # A trailer block is either the whole message or separated from prose by a
    # blank line. This rejects `Herder-Session:` embedded in an ordinary paragraph.
    if index >= 0 and lines[index].strip():
        return ()
    return tuple(reversed(parsed_reversed))


@dataclass(frozen=True)
class Hit:
    agent: str
    channel: str
    evidence: dict
    family_id: str | None = None
    family_name: str | None = None
    observed_as: str | None = None
    variant: str | None = None
    rule_id: str | None = None
    rule_lifecycle: str | None = None
    evidence_semantics: str | None = None
    forge: str | None = None
    role: str | None = None
    confidence: str | None = None
    provenance_ref: str | None = None
    is_current: bool | None = None
    is_historical: bool | None = None
    metric_eligibility: Mapping[str, bool] = None  # type: ignore[assignment]
    explanatory_note: str | None = None
    is_positive: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "metric_eligibility", dict(self.metric_eligibility or {}))

    def storage_fields(self) -> dict[str, object]:
        return {
            "agent": self.agent,
            "channel": self.channel,
            "evidence": self.evidence,
            "family_id": self.family_id,
            "family_name": self.family_name,
            "observed_as": self.observed_as,
            "variant": self.variant,
            "rule_id": self.rule_id,
            "rule_lifecycle": self.rule_lifecycle,
            "evidence_semantics": self.evidence_semantics,
            "forge": self.forge,
            "role": self.role,
            "confidence": self.confidence,
            "provenance_ref": self.provenance_ref,
            "is_current": self.is_current,
            "is_historical": self.is_historical,
            "metric_eligibility": dict(self.metric_eligibility) or None,
            "explanatory_note": self.explanatory_note,
        }


def _parse_moment(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        try:
            parsed_date = date.fromisoformat(text[:10])
        except ValueError:
            return None
        return datetime(parsed_date.year, parsed_date.month, parsed_date.day, tzinfo=UTC)
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


def _inside_validity(rule: Pattern, observed_at: object) -> bool:
    moment = _parse_moment(observed_at)
    if moment is None:
        return True
    if rule.valid_from:
        start = _parse_moment(rule.valid_from)
        if start is not None and moment < start:
            return False
    if rule.valid_until:
        end = _parse_moment(rule.valid_until)
        if end is not None:
            # Date-only validity is inclusive through that calendar day.
            if len(rule.valid_until) == 10:
                end = end.replace(hour=23, minute=59, second=59, microsecond=999999)
            if moment > end:
                return False
    return True


def _provenance_reference(rule: Pattern) -> str | None:
    source = rule.provenance.get("source_url") or rule.provenance.get("url")
    if source:
        return str(source)
    repository = rule.provenance.get("repository")
    revision = rule.provenance.get("commit") or rule.provenance.get("version")
    path = rule.provenance.get("path")
    if not any((repository, revision, path)):
        return None
    reference = str(repository or "")
    if revision:
        reference += f"@{revision}"
    if path:
        reference += f":{path}"
    return reference or None


def hit_from_rule(
    rule: Pattern,
    channel: str,
    evidence: Mapping[str, object],
    *,
    forge: str,
    role: str | None = None,
    observed_at: object = None,
) -> Hit | None:
    if not _inside_validity(rule, observed_at):
        return None
    historical = rule.lifecycle in {"legacy", "retired"}
    current = rule.lifecycle in {
        "current",
        "deprecated",
        "compatibility",
        "optional",
        "recovery-only",
    }
    positive = rule.disposition == "positive" and rule.lifecycle != "unsafe/rejected"
    metrics = rule.semantics.metric_eligibility()
    if historical:
        metrics["current_presence"] = False
        metrics["current_commit_ratio"] = False
    if rule.lifecycle in {"recovery-only", "anomalous"}:
        metrics["current_commit_ratio"] = False
    if not positive:
        metrics = {key: False for key in metrics}
        current = False
    note = rule.note
    if historical and channel in {"file", "workflow"} and observed_at is None:
        note = "Legacy marker present; current use unknown"
    agent = rule.display_name or rule.observed_as or "Rejected/noise"
    return Hit(
        agent=agent,
        channel=channel,
        evidence=dict(evidence),
        family_id=rule.canonical_family_id or None,
        family_name=rule.display_name or None,
        observed_as=rule.observed_as or rule.display_name or None,
        variant=rule.variant,
        rule_id=rule.id or None,
        rule_lifecycle=rule.lifecycle,
        evidence_semantics=rule.semantics.evidence,
        forge=forge,
        role=role or rule.semantics.role,
        confidence=rule.evidence_strength,
        provenance_ref=_provenance_reference(rule),
        is_current=current,
        is_historical=historical,
        metric_eligibility=metrics,
        explanatory_note=note,
        is_positive=positive,
    )


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
    if ratio is None or ratio == 0.0:
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
    return tuple(pattern for pattern in patterns if pattern.display_name in agents)


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
    content = json.dumps(
        [
            [(rule.pattern, rule.agent, rule.id) for rule in channel]
            for channel in (pack.files, pack.authors, pack.branches, pack.labels, pack.bots)
        ],
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"{pack.version}|{hash(content)}|{suffix}"


def matchers_for(pack: Pack, agents: frozenset[str] | None = None) -> dict[str, ChannelRegex]:
    key = _cache_key(pack, agents)
    cached = _MATCHER_CACHE.get(key)
    if cached is None:
        author_patterns = _selected(pack.authors, agents)
        distinctive_patterns = tuple(
            pattern for pattern in author_patterns if not is_ambiguous(pattern.pattern)
        )
        cached = {
            "file": build_channel_regex(_selected(pack.files, agents), is_files=True),
            "author": build_channel_regex(author_patterns, is_authors=True),
            "author_distinctive": build_channel_regex(distinctive_patterns, is_authors=True),
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
    if pack.schema_version >= 2:
        matches, _diagnostics = evaluate_file_rules(
            pack, presence.paths, source=presence.source, agents=agents
        )
        hits: list[Hit] = []
        for matched in matches:
            evidence = dict(matched.evidence)
            path = evidence.get("path")
            if isinstance(path, str):
                weight = _generic_weight(pack, path)
                if weight is not None:
                    evidence["generic"] = True
                    evidence["weight"] = weight
            hit = hit_from_rule(
                matched.rule,
                "file",
                evidence,
                forge="local" if presence.source == "local" else "any",
            )
            if hit is not None:
                hits.append(hit)
        return dedupe_hits(hits)
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
                if _normalize_login(email_login) == word:
                    matched.setdefault(agent, "email")
            for agent in _login_agents(identity, email_login):
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


def _forge_matches(rule: Pattern, forge: str) -> bool:
    return rule.forge in {"any", forge} or (forge == "local" and rule.forge == "git")


def _rule_selected(rule: Pattern, agents: frozenset[str] | None) -> bool:
    return agents is None or rule.display_name in agents or rule.disposition != "positive"


def _v2_identity_hits(
    pack: Pack,
    entries: Iterable[Mapping[str, object]],
    *,
    agents: frozenset[str] | None,
    forge: str,
) -> list[Hit]:
    rules = pack.rules_for("author", "committer", include_rejections=True)
    hits: list[Hit] = []
    for entry in entries:
        role = str(entry.get("role") or "author")
        for rule in rules:
            if rule.channel != role or not _forge_matches(rule, forge):
                continue
            if not _rule_selected(rule, agents):
                continue
            fields = rule.match.get("fields")
            if isinstance(fields, Mapping):
                matched_fields: list[str] = []
                for field_name, raw_pattern in fields.items():
                    value = str(entry.get(str(field_name)) or "")
                    if not value or re.fullmatch(str(raw_pattern), value, re.IGNORECASE) is None:
                        break
                    matched_fields.append(str(field_name))
                else:
                    field = "+".join(matched_fields)
                    value = ""
                if len(matched_fields) != len(fields):
                    continue
            else:
                field = str(
                    rule.match.get("field") or ("email" if "@" in rule.pattern else "login")
                )
                value = str(entry.get(field) or "")
                if not value:
                    continue
                raw = str(rule.match.get("regex") or rule.pattern)
                mode = str(rule.match.get("mode") or "search")
                matcher = re.compile(raw, re.IGNORECASE)
                matched = matcher.fullmatch(value) if mode == "fullmatch" else matcher.search(value)
                if matched is None:
                    continue
            not_name_regex = rule.match.get("not_name_regex")
            if (
                not_name_regex is not None
                and re.fullmatch(str(not_name_regex), str(entry.get("name") or ""), re.IGNORECASE)
                is not None
            ):
                continue
            evidence = {
                "login": str(entry.get("login") or ""),
                "commit": str(entry.get("commit") or ""),
                "field": field,
            }
            hit = hit_from_rule(
                rule,
                "author",
                evidence,
                forge=forge,
                role=f"commit_{role}",
                observed_at=entry.get("observed_at"),
            )
            if hit is not None:
                hits.append(hit)
    return dedupe_hits(hits)


def match_author_identities(
    pack: Pack,
    entries: Iterable[Mapping[str, object]],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    if pack.schema_version >= 2:
        return _v2_identity_hits(pack, entries, agents=agents, forge=forge)
    channel = matchers_for(pack, agents)["author"]
    return dedupe_hits(_match_identity_fields(channel, entries, name="author"))


def match_bots(
    pack: Pack,
    entries: Iterable[Mapping[str, object]],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    if pack.schema_version >= 2:
        hits: list[Hit] = []
        for entry in entries:
            for rule in pack.rules_for("bot", include_rejections=True):
                if not _forge_matches(rule, forge):
                    continue
                field = str(rule.match.get("field") or "login")
                value = str(entry.get(field) or "")
                if not value:
                    continue
                regex = re.compile(str(rule.match.get("regex") or rule.pattern), re.IGNORECASE)
                if regex.search(value) is None:
                    continue
                hit = hit_from_rule(
                    rule,
                    "bot",
                    {
                        "login": str(entry.get("login") or ""),
                        "commit": str(entry.get("commit") or ""),
                        "field": field,
                    },
                    forge=forge,
                    role=str(entry.get("role") or "automation"),
                    observed_at=entry.get("observed_at"),
                )
                if hit is not None:
                    hits.append(hit)
        return dedupe_hits(hits)
    channel = matchers_for(pack, agents)["bot"]
    return dedupe_hits(_match_identity_fields(channel, entries, name="bot"))


def _message_parts(item: Sequence[str]) -> tuple[str, str, str | None]:
    commit = str(item[0]) if item else ""
    message = str(item[1]) if len(item) > 1 else ""
    observed_at = str(item[2]) if len(item) > 2 and item[2] else None
    return commit, message, observed_at


def _v2_trailer_rule_matches(rule: Pattern, trailer: StructuredTrailer) -> bool:
    token = rule.match.get("token")
    if token is not None and trailer.token.lower() != str(token).lower():
        return False
    value = rule.match.get("value")
    if value is not None and trailer.value != str(value):
        return False
    value_regex = rule.match.get("value_regex")
    if value_regex is not None and re.fullmatch(str(value_regex), trailer.value) is None:
        return False
    name = rule.match.get("name")
    if name is not None and trailer.name != str(name):
        return False
    email = rule.match.get("email")
    if email is not None:
        if trailer.email is None or re.fullmatch(str(email), trailer.email, re.IGNORECASE) is None:
            return False
    line_regex = rule.match.get("line_regex")
    if line_regex is not None and re.fullmatch(str(line_regex), trailer.line) is None:
        return False
    return any(
        key in rule.match
        for key in ("token", "value", "value_regex", "name", "email", "line_regex")
    )


def _v2_message_hits(
    pack: Pack,
    messages: Iterable[Sequence[str]],
    *,
    agents: frozenset[str] | None,
    forge: str,
) -> list[Hit]:
    rules = pack.rules_for("co_author", "custom_trailer", include_rejections=True)
    hits: list[Hit] = []
    seen: set[tuple[str, str]] = set()
    for item in messages:
        commit, message, observed_at = _message_parts(item)
        if not message or is_noise_commit(message):
            continue
        trailers = parse_structured_trailers(message)
        footer_lines = [line for line, _distinctive in _trailer_lines(message)]
        for rule in rules:
            if not _forge_matches(rule, forge):
                continue
            if not _rule_selected(rule, agents):
                continue
            if not _inside_validity(rule, observed_at):
                continue
            matched_trailer = next(
                (trailer for trailer in trailers if _v2_trailer_rule_matches(rule, trailer)), None
            )
            footer_regex = rule.match.get("footer_regex")
            matched_footer = None
            if matched_trailer is None and footer_regex is not None:
                matcher = re.compile(str(footer_regex), re.IGNORECASE)
                matched_footer = next(
                    (line for line in footer_lines if matcher.fullmatch(line.strip()) is not None),
                    None,
                )
            if matched_trailer is None and matched_footer is None:
                continue
            key = (commit, rule.id)
            if key in seen:
                continue
            seen.add(key)
            evidence: dict[str, object] = {"commit": commit}
            role = "co_author" if rule.channel == "co_author" else "commit_metadata"
            if matched_trailer is not None:
                evidence.update(
                    {
                        "trailer_token": matched_trailer.token,
                        "trailer_value": matched_trailer.value[:300],
                        "message_location": matched_trailer.location,
                        "line_number": matched_trailer.line_number,
                    }
                )
                if matched_trailer.name is not None:
                    evidence["co_author_name"] = matched_trailer.name
                if matched_trailer.email is not None:
                    evidence["co_author_email"] = matched_trailer.email
            else:
                evidence.update(
                    {
                        "snippet": redact_emails(str(matched_footer))[:100],
                        "message_location": "footer",
                    }
                )
            hit = hit_from_rule(
                rule,
                "commit_trailer",
                evidence,
                forge=forge,
                role=role,
                observed_at=observed_at,
            )
            if hit is not None:
                hits.append(hit)
    return dedupe_hits(hits)


def match_commit_messages(
    pack: Pack,
    messages: Iterable[Sequence[str]],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    if pack.schema_version >= 2:
        return _v2_message_hits(pack, messages, agents=agents, forge=forge)
    channels = matchers_for(pack, agents)
    channel = channels["author"]
    if channel.regex is None:
        return []
    distinctive_channel = channels["author_distinctive"]
    email_channel = channels["author_email"]
    hits: list[Hit] = []
    seen: set[tuple[str, str]] = set()
    for item in messages:
        commit, message, _observed_at = _message_parts(item)
        if not message or is_noise_commit(message):
            continue
        extracts = _trailer_lines(message)
        has_email = "@" in message
        if not extracts and not has_email:
            continue
        snippets: dict[str, str] = {}
        tier1_email = False
        for line, distinctive_only in extracts:
            matcher = distinctive_channel if distinctive_only else channel
            if matcher.regex is None:
                continue
            for match in matcher.regex.finditer(line):
                if match.lastgroup is None:
                    continue
                if "@" in match.group():
                    tier1_email = True
                snippets.setdefault(
                    matcher.names[match.lastgroup], _snippet(line, match.start(), match.end())
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
    pack: Pack,
    branches: Iterable[str | Mapping[str, object]],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    if pack.schema_version >= 2:
        hits: list[Hit] = []
        for item in branches:
            entry = item if isinstance(item, Mapping) else {"branch": str(item)}
            value = str(entry.get("branch") or entry.get("head") or "")
            if not value:
                continue
            for rule in pack.rules_for("branch", include_rejections=True):
                if not _forge_matches(rule, forge):
                    continue
                if not _rule_selected(rule, agents):
                    continue
                matcher = re.compile(
                    str(rule.match.get("regex") or rule.pattern),
                    0 if bool(rule.match.get("case_sensitive", True)) else re.IGNORECASE,
                )
                match = matcher.search(value)
                if match is None:
                    continue
                evidence: dict[str, object] = {"branch": value, "match": match.group()}
                if entry.get("pr") is not None:
                    evidence["pr"] = entry["pr"]
                hit = hit_from_rule(
                    rule,
                    "branch",
                    evidence,
                    forge=forge,
                    role=str(entry.get("role") or "branch_head"),
                    observed_at=entry.get("observed_at"),
                )
                if hit is not None:
                    hits.append(hit)
        return dedupe_hits(hits)
    return _match_values(
        matchers_for(pack, agents)["branch"], branches, name="branch", key="branch"
    )


def match_labels(
    pack: Pack,
    labels: Iterable[str],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    if pack.schema_version >= 2:
        hits: list[Hit] = []
        for value in labels:
            for rule in pack.rules_for("label", include_rejections=True):
                if not _forge_matches(rule, forge):
                    continue
                if not _rule_selected(rule, agents):
                    continue
                matcher = re.compile(str(rule.match.get("regex") or rule.pattern))
                match = matcher.search(value)
                if match is None:
                    continue
                hit = hit_from_rule(
                    rule,
                    "label",
                    {"label": value, "match": match.group()},
                    forge=forge,
                    role="workflow_label",
                )
                if hit is not None:
                    hits.append(hit)
        return dedupe_hits(hits)
    return _match_values(matchers_for(pack, agents)["label"], labels, name="label", key="label")


def match_hidden_refs(
    pack: Pack,
    refs: Iterable[Mapping[str, object]],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    if pack.schema_version < 2:
        return []
    hits: list[Hit] = []
    for entry in refs:
        ref_name = str(entry.get("ref") or "")
        if not ref_name:
            continue
        for rule in pack.rules_for("hidden_ref", include_rejections=True):
            if not _forge_matches(rule, forge):
                continue
            if not _rule_selected(rule, agents):
                continue
            matcher = re.compile(str(rule.match.get("regex") or rule.pattern))
            if matcher.fullmatch(ref_name) is None:
                continue
            identity = rule.match.get("identity")
            if isinstance(identity, Mapping):
                identity_role = str(identity.get("role") or "author")
                name = str(entry.get(f"{identity_role}_name") or "")
                email = str(entry.get(f"{identity_role}_email") or "")
                expected_name = identity.get("name")
                expected_email = identity.get("email")
                if expected_name is not None and name != str(expected_name):
                    continue
                if (
                    expected_email is not None
                    and re.fullmatch(str(expected_email), email, re.IGNORECASE) is None
                ):
                    continue
            evidence = {
                "ref": ref_name,
                "commit": str(entry.get("commit") or ""),
                "reachability": str(entry.get("reachability") or "remote_hidden_ref"),
            }
            hit = hit_from_rule(
                rule,
                "hidden_ref",
                evidence,
                forge=forge,
                role=rule.semantics.role or "checkpoint_ref",
                observed_at=entry.get("observed_at"),
            )
            if hit is not None:
                hits.append(hit)
    return dedupe_hits(hits)


def match_pr_metadata(
    pack: Pack,
    prs: Iterable[Mapping[str, object]],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    hits: list[Hit] = []
    for pr in prs:
        number = pr.get("number")
        head = str(pr.get("headRefName") or "")
        labels = [str(x) for x in pr.get("labels") or []]
        body = str(pr.get("body") or "")
        branch_entries: list[str | Mapping[str, object]]
        if pack.schema_version >= 2:
            branch_entries = (
                [
                    {
                        "branch": head,
                        "pr": number,
                        "role": "pr_head",
                        "observed_at": pr.get("createdAt"),
                    }
                ]
                if head
                else []
            )
        else:
            branch_entries = [head] if head else []
        for hit in match_branches(pack, branch_entries, agents, forge=forge):
            evidence = {"pr": number, "head": head, "match": hit.evidence["match"]}
            hits.append(replace(hit, evidence=evidence))
        for hit in match_labels(pack, labels, agents, forge=forge):
            evidence = {
                "pr": number,
                "label": hit.evidence["label"],
                "match": hit.evidence["match"],
            }
            hits.append(replace(hit, evidence=evidence))
        if pack.schema_version >= 2 and body:
            for rule in pack.rules_for(
                "pr_author",
                "pr_reviewer",
                "pr_commenter",
                "service_account",
                include_rejections=True,
            ):
                if not _forge_matches(rule, forge):
                    continue
                if not _rule_selected(rule, agents):
                    continue
                body_regex = rule.match.get("body_regex")
                body_contains = rule.match.get("body_contains")
                matched = False
                if body_regex is not None:
                    matched = re.search(str(body_regex), body) is not None
                elif body_contains is not None:
                    matched = str(body_contains) in body
                if not matched:
                    continue
                hit = hit_from_rule(
                    rule,
                    "pr_metadata",
                    {"pr": number, "snippet": str(body_contains or body_regex)[:100]},
                    forge=forge,
                    role=rule.semantics.role or rule.channel,
                    observed_at=pr.get("createdAt"),
                )
                if hit is not None:
                    hits.append(hit)
        if body and CODEX_PR_BODY_MARKER in body and (agents is None or "Codex" in agents):
            # The hard-coded v1 compatibility marker is superseded by a scoped
            # schema-v2 body rule when one exists.
            if pack.schema_version < 2:
                hits.append(
                    Hit("Codex", "pr_metadata", {"pr": number, "snippet": CODEX_PR_BODY_MARKER})
                )
    return dedupe_hits(hits)


def match_pr_authors(
    pack: Pack,
    prs: Iterable[Mapping[str, object]],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    if pack.schema_version >= 2:
        hits: list[Hit] = []
        for pr in prs:
            login = str(pr.get("author") or "")
            if not login:
                continue
            for rule in pack.rules_for("pr_author", "service_account", include_rejections=True):
                if not _forge_matches(rule, forge):
                    continue
                if not _rule_selected(rule, agents):
                    continue
                regex = rule.match.get("login_regex") or rule.match.get("regex") or rule.pattern
                if not regex or re.fullmatch(str(regex), login, re.IGNORECASE) is None:
                    continue
                hit = hit_from_rule(
                    rule,
                    "pr_metadata",
                    {"pr": pr.get("number"), "author": login},
                    forge=forge,
                    role="pr_author" if rule.channel == "pr_author" else "service_account",
                    observed_at=pr.get("createdAt"),
                )
                if hit is not None:
                    hits.append(hit)
        return dedupe_hits(hits)
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
    pack: Pack,
    entries: Iterable[Mapping[str, object]],
    agents: frozenset[str] | None = None,
    *,
    forge: str = "github",
) -> list[Hit]:
    if pack.schema_version >= 2:
        role_channels = {
            "author": "issue_author",
            "issue_author": "issue_author",
            "assignee": "issue_assignee",
            "issue_assignee": "issue_assignee",
            "commenter": "issue_commenter",
            "issue_commenter": "issue_commenter",
            "pr_commenter": "pr_commenter",
            "pr_reviewer": "pr_reviewer",
        }
        hits: list[Hit] = []
        for entry in entries:
            login = str(entry.get("login") or "")
            source_role = str(entry.get("role") or "")
            rule_channel = role_channels.get(source_role)
            if not login or rule_channel is None:
                continue
            for rule in pack.rules_for(rule_channel, "service_account", include_rejections=True):
                if rule.channel not in {rule_channel, "service_account"}:
                    continue
                if not _forge_matches(rule, forge):
                    continue
                if not _rule_selected(rule, agents):
                    continue
                regex = rule.match.get("login_regex") or rule.match.get("regex") or rule.pattern
                body_regex = rule.match.get("body_regex")
                if regex and re.fullmatch(str(regex), login, re.IGNORECASE) is None:
                    continue
                if (
                    body_regex is not None
                    and re.search(str(body_regex), str(entry.get("body") or "")) is None
                ):
                    continue
                hit = hit_from_rule(
                    rule,
                    "issue" if not source_role.startswith("pr_") else "pr_metadata",
                    {
                        "login": login,
                        "number": entry.get("number"),
                        "role": source_role,
                    },
                    forge=forge,
                    role=source_role,
                    observed_at=entry.get("observed_at"),
                )
                if hit is not None:
                    hits.append(hit)
        return dedupe_hits(hits)
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
    hits_by_pr: dict[object, dict[tuple[str, str | None], Hit]] = {}
    for hit in hits:
        number = hit.evidence.get("pr")
        if number is not None:
            if hit.rule_id and not (
                hit.metric_eligibility.get("authorship")
                or hit.metric_eligibility.get("generated_code")
            ):
                continue
            hits_by_pr.setdefault(number, {})[(hit.agent, hit.rule_id)] = hit
    propagated: list[Hit] = []
    for number, source_hits in hits_by_pr.items():
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
            for key in sorted(source_hits):
                source = source_hits[key]
                propagated.append(
                    replace(
                        source,
                        channel="pr_metadata",
                        evidence={"pr": number, "commit": oid, "propagated": True},
                    )
                )
    return dedupe_hits(propagated)


def dedupe_hits(hits: Iterable[Hit]) -> list[Hit]:
    seen: set[str] = set()
    unique: list[Hit] = []
    for hit in hits:
        key = json.dumps(
            [hit.agent, hit.channel, hit.rule_id, hit.evidence],
            sort_keys=True,
            separators=(",", ":"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(hit)
    return unique
