from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePosixPath

import yaml

from detect.packs import Pack, Pattern

_MAX_REGEX_LENGTH = 2_000


@dataclass(frozen=True)
class StructuredMatch:
    rule: Pattern
    evidence: Mapping[str, object]


@dataclass(frozen=True)
class PredicateDiagnostic:
    rule_id: str
    path: str | None
    kind: str
    note: str

    def as_dict(self) -> dict[str, object]:
        return {
            "rule_id": self.rule_id,
            "path": self.path,
            "kind": self.kind,
            "note": self.note,
        }


def _flags(case_sensitive: bool) -> int:
    return 0 if case_sensitive else re.IGNORECASE


def _compile(pattern: str, *, case_sensitive: bool) -> re.Pattern[str]:
    if len(pattern) > _MAX_REGEX_LENGTH:
        raise ValueError("regex exceeds the 2000-character safety limit")
    return re.compile(pattern, _flags(case_sensitive))


def _path_spec(condition: Mapping[str, object]) -> Mapping[str, object] | None:
    raw = condition.get("path")
    if isinstance(raw, str):
        return {"regex": raw}
    return raw if isinstance(raw, Mapping) else None


def path_matches(path: str, spec: Mapping[str, object]) -> bool:
    """Apply explicit, repository-relative path semantics.

    A directory never matches descendants unless ``descendants`` is true, and
    root anchoring never appears implicitly. Repository trees supply file paths;
    directory rules infer a directory only from an explicitly requested prefix.
    """

    normalized = path.replace("\\", "/").lstrip("/")
    case_sensitive = bool(spec.get("case_sensitive", True))
    candidate = normalized if case_sensitive else normalized.lower()
    kind = str(spec.get("kind") or "file")
    root = bool(spec.get("root", False))
    descendants = bool(spec.get("descendants", False))
    exact_leaf = spec.get("exact_leaf")
    if exact_leaf is not None:
        leaf = PurePosixPath(normalized).name
        expected = str(exact_leaf)
        if not case_sensitive:
            leaf, expected = leaf.lower(), expected.lower()
        if leaf != expected:
            return False
    if root and "/" in normalized:
        return False

    literal = spec.get("equals")
    if literal is not None:
        expected = str(literal).replace("\\", "/").lstrip("/")
        if not case_sensitive:
            expected = expected.lower()
        if kind == "directory":
            if candidate == expected:
                return True
            return descendants and candidate.startswith(expected.rstrip("/") + "/")
        return candidate == expected

    regex = spec.get("regex")
    if regex is None:
        return False
    matcher = _compile(str(regex), case_sensitive=case_sensitive)
    if kind == "directory" and descendants:
        prefixes = [str(PurePosixPath(normalized).parent)]
        parent = PurePosixPath(normalized).parent
        prefixes.extend(str(ancestor) for ancestor in parent.parents)
        return any(matcher.fullmatch(prefix) is not None for prefix in prefixes)
    return matcher.search(normalized) is not None


def _condition_path_matches(condition: Mapping[str, object], paths: Sequence[str]) -> list[str]:
    spec = _path_spec(condition)
    if spec is None:
        return []
    return [path for path in paths if path_matches(path, spec)]


def _walk_conditions(expression: Mapping[str, object]) -> Iterable[Mapping[str, object]]:
    if _path_spec(expression) is not None:
        yield expression
    for key in ("allOf", "anyOf"):
        children = expression.get(key)
        if isinstance(children, Sequence) and not isinstance(children, (str, bytes)):
            for child in children:
                if isinstance(child, Mapping):
                    yield from _walk_conditions(child)
    relationship = expression.get("relationship")
    if isinstance(relationship, Mapping):
        for key in ("left", "right"):
            child = relationship.get(key)
            if isinstance(child, Mapping):
                yield from _walk_conditions(child)


def _has_content(expression: Mapping[str, object]) -> bool:
    if isinstance(expression.get("content"), Mapping):
        return True
    for key in ("allOf", "anyOf"):
        children = expression.get(key)
        if isinstance(children, Sequence) and not isinstance(children, (str, bytes)):
            if any(_has_content(child) for child in children if isinstance(child, Mapping)):
                return True
    relationship = expression.get("relationship")
    if isinstance(relationship, Mapping):
        return any(
            _has_content(child)
            for key in ("left", "right")
            if isinstance((child := relationship.get(key)), Mapping)
        )
    return False


def is_targeted_path(condition: Mapping[str, object]) -> bool:
    """True when a content condition names one specific file rather than a broad glob.

    Targeted: a literal path, an exact leaf name, or a root-anchored pattern
    (``orca.yaml``, ``.pr_agent.toml``). Broad: patterns such as
    ``.github/workflows/*.yml`` or ``**/compose*.yml`` that match many ordinary
    files in most repositories, so reading them costs one API call per file.
    """

    spec = _path_spec(condition)
    if spec is None:
        return False
    return bool(
        spec.get("equals") is not None or spec.get("exact_leaf") is not None or spec.get("root")
    )


def content_candidates(
    pack: Pack, paths: Iterable[str], *, targeted_only: bool = False
) -> tuple[tuple[str, ...], bool]:
    """Paths whose content a declared rule needs to read.

    ``targeted_only`` (API fast mode) skips content conditions on broad path
    patterns; see :func:`is_targeted_path`.
    """

    ordered = tuple(sorted({path.replace("\\", "/").lstrip("/") for path in paths}))
    candidates: set[str] = set()

    def admit(condition: Mapping[str, object]) -> None:
        if targeted_only and not is_targeted_path(condition):
            return
        candidates.update(_condition_path_matches(condition, ordered))

    for rule in pack.rules_for("file", "workflow"):
        if not _has_content(rule.match):
            continue
        for condition in _walk_conditions(rule.match):
            if isinstance(condition.get("content"), Mapping):
                admit(condition)
        # A common path-plus-content shape keeps content at the rule root.
        if isinstance(rule.match.get("content"), Mapping):
            admit(rule.match)
    capped = tuple(sorted(candidates)[: pack.content_candidate_limit])
    return capped, len(candidates) > len(capped)


def declared_literal_paths(pack: Pack) -> tuple[str, ...]:
    """Return only paths a rule declares exactly enough for safe Contents probes."""

    literals: set[str] = set()
    for rule in pack.rules_for("file", "workflow"):
        for condition in _walk_conditions(rule.match):
            spec = _path_spec(condition)
            if spec is None:
                continue
            if spec.get("equals") is not None:
                literals.add(str(spec["equals"]).lstrip("/"))
                continue
            regex = str(spec.get("regex") or "")
            if not (regex.startswith("^") and regex.endswith("$")):
                continue
            body = regex[1:-1]
            variants = [body]
            if "ya?ml" in body:
                variants = [body.replace("ya?ml", "yaml"), body.replace("ya?ml", "yml")]
            for variant in variants:
                # Exact escaped punctuation is safe; any remaining regex
                # operator means this is not one literal repository path.
                plain = re.sub(r"\\([.\\-])", r"\1", variant)
                if re.search(r"[\[\](){}+*?|^$]", plain):
                    continue
                literals.add(plain)
    return tuple(sorted(literals))


def _lookup_path(value: object, raw_path: str) -> tuple[bool, object]:
    if raw_path in ("$", ""):
        return True, value
    if not raw_path.startswith("$."):
        return False, None
    current: object = value
    for part in raw_path[2:].split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
            continue
        return False, None
    return True, current


def _recursive_values(value: object, key: str) -> Iterable[object]:
    if isinstance(value, Mapping):
        for child_key, child in value.items():
            if str(child_key) == key:
                yield child
            yield from _recursive_values(child, key)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _recursive_values(child, key)


def _predicate_matches(parsed: object, text: str, predicate: Mapping[str, object]) -> bool:
    kind = str(predicate.get("type") or "path")
    if kind in {"workflow_uses", "container_image"}:
        key = "uses" if kind == "workflow_uses" else "image"
        values = [str(value) for value in _recursive_values(parsed, key)]
        expected = predicate.get("equals")
        regex = predicate.get("regex")
        if expected is not None:
            return any(value == str(expected) for value in values)
        if regex is not None:
            matcher = _compile(
                str(regex), case_sensitive=bool(predicate.get("case_sensitive", True))
            )
            return any(matcher.fullmatch(value) is not None for value in values)
        return False
    if kind == "text":
        value: object = text
        exists = True
    else:
        raw_path = str(
            predicate.get("path")
            or predicate.get("json_path")
            or predicate.get("yaml_path")
            or predicate.get("toml_path")
            or "$"
        )
        exists, value = _lookup_path(parsed, raw_path)
    if "exists" in predicate and bool(predicate["exists"]) != exists:
        return False
    if not exists:
        return False
    if "equals" in predicate and value != predicate["equals"]:
        return False
    if "starts_with" in predicate and not str(value).startswith(str(predicate["starts_with"])):
        return False
    if "contains" in predicate:
        needle = predicate["contains"]
        if isinstance(value, Mapping):
            if needle not in value:
                return False
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            if needle not in value:
                return False
        elif str(needle) not in str(value):
            return False
    if "regex" in predicate:
        matcher = _compile(
            str(predicate["regex"]), case_sensitive=bool(predicate.get("case_sensitive", True))
        )
        mode = str(predicate.get("mode") or "search")
        if mode == "fullmatch":
            if matcher.fullmatch(str(value)) is None:
                return False
        elif matcher.search(str(value)) is None:
            return False
    return True


def _parse_content(text: str, content: Mapping[str, object]) -> object:
    format_name = str(content.get("format") or "text").lower()
    if format_name == "json":
        return json.loads(text)
    if format_name == "yaml":
        return yaml.safe_load(text)
    if format_name == "toml":
        return tomllib.loads(text)
    if format_name == "text":
        return text
    raise ValueError(f"unsupported declared content format {format_name!r}")


def _content_result(
    rule: Pattern,
    path: str,
    text: str | None,
    content: Mapping[str, object],
    *,
    byte_limit: int,
) -> tuple[bool, PredicateDiagnostic | None]:
    if text is None:
        return False, None
    cap = min(int(content.get("max_bytes") or byte_limit), byte_limit)
    encoded = text.encode("utf-8")
    if len(encoded) > cap:
        return False, PredicateDiagnostic(
            rule.id, path, "parse_failure", f"content exceeds declared {cap}-byte cap"
        )
    try:
        parsed = _parse_content(text, content)
    except (
        ValueError,
        TypeError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
        yaml.YAMLError,
    ) as exc:
        return False, PredicateDiagnostic(rule.id, path, "parse_failure", type(exc).__name__)
    predicates = content.get("predicates") or []
    if not isinstance(predicates, Sequence) or isinstance(predicates, (str, bytes)):
        return False, PredicateDiagnostic(
            rule.id, path, "parse_failure", "predicates must be an array"
        )
    mode = str(content.get("mode") or "all")
    results = [
        _predicate_matches(parsed, text, predicate)
        for predicate in predicates
        if isinstance(predicate, Mapping)
    ]
    minimum = int(content.get("minMatches") or (1 if mode == "any" else len(results)))
    matched = sum(results) >= minimum
    if not matched:
        return False, PredicateDiagnostic(
            rule.id, path, "predicate_failure", f"{sum(results)}/{minimum} predicates matched"
        )
    return True, None


def _same_stem(
    relationship: Mapping[str, object], paths: Sequence[str]
) -> tuple[bool, tuple[str, ...]]:
    directory = str(relationship.get("directory") or "").strip("/")
    left_suffix = str(relationship.get("left_suffix") or "")
    right_suffix = str(relationship.get("right_suffix") or "")
    left: dict[str, str] = {}
    right: dict[str, str] = {}
    prefix = f"{directory}/" if directory else ""
    for path in paths:
        if not path.startswith(prefix):
            continue
        leaf = path[len(prefix) :]
        if "/" in leaf:
            continue
        if left_suffix and leaf.endswith(left_suffix):
            left[leaf[: -len(left_suffix)]] = path
        if right_suffix and leaf.endswith(right_suffix):
            right[leaf[: -len(right_suffix)]] = path
    stems = sorted(set(left) & set(right))
    if not stems:
        return False, ()
    stem = stems[0]
    return True, (left[stem], right[stem])


def _same_tree(
    relationship: Mapping[str, object], paths: Sequence[str]
) -> tuple[bool, tuple[str, ...]]:
    required = relationship.get("paths") or []
    if not isinstance(required, Sequence) or isinstance(required, (str, bytes)):
        return False, ()
    case_sensitive = bool(relationship.get("case_sensitive", True))
    available = set(paths if case_sensitive else (path.lower() for path in paths))
    expected = [str(path).lstrip("/") for path in required]
    compared = expected if case_sensitive else [path.lower() for path in expected]
    return all(path in available for path in compared), tuple(expected)


def _relationship(
    relationship: Mapping[str, object], paths: Sequence[str]
) -> tuple[bool, tuple[str, ...]]:
    kind = str(relationship.get("type") or "")
    if kind == "same_stem":
        return _same_stem(relationship, paths)
    if kind == "same_tree":
        return _same_tree(relationship, paths)
    return False, ()


def _evaluate_condition(
    rule: Pattern,
    condition: Mapping[str, object],
    paths: Sequence[str],
    contents: Mapping[str, str | None],
    *,
    byte_limit: int,
    diagnostics: list[PredicateDiagnostic],
) -> tuple[bool, tuple[str, ...]]:
    relationship = condition.get("relationship")
    if isinstance(relationship, Mapping):
        return _relationship(relationship, paths)

    if "allOf" in condition or "anyOf" in condition:
        key = "allOf" if "allOf" in condition else "anyOf"
        children = condition.get(key)
        if not isinstance(children, Sequence) or isinstance(children, (str, bytes)):
            return False, ()
        outcomes = [
            _evaluate_condition(
                rule,
                child,
                paths,
                contents,
                byte_limit=byte_limit,
                diagnostics=diagnostics,
            )
            for child in children
            if isinstance(child, Mapping)
        ]
        minimum = int(condition.get("minMatches") or (len(outcomes) if key == "allOf" else 1))
        matched = [outcome for outcome in outcomes if outcome[0]]
        evidence_paths = tuple(sorted({path for _, found in matched for path in found}))
        return len(matched) >= minimum, evidence_paths

    matched_paths = _condition_path_matches(condition, paths)
    if not matched_paths:
        return False, ()
    content = condition.get("content")
    if not isinstance(content, Mapping):
        return True, (matched_paths[0],)
    for path in matched_paths:
        matched, diagnostic = _content_result(
            rule, path, contents.get(path), content, byte_limit=byte_limit
        )
        if diagnostic is not None:
            diagnostics.append(diagnostic)
        if matched:
            return True, (path,)
    return False, ()


def evaluate_file_rules(
    pack: Pack,
    paths: Iterable[str],
    contents: Mapping[str, str | None] | None = None,
    *,
    source: str = "tree",
    agents: frozenset[str] | None = None,
) -> tuple[list[StructuredMatch], list[PredicateDiagnostic]]:
    normalized = tuple(sorted({path.replace("\\", "/").lstrip("/") for path in paths}))
    content_map = contents or {}
    matches: list[StructuredMatch] = []
    diagnostics: list[PredicateDiagnostic] = []
    for rule in pack.rules_for("file", "workflow"):
        if agents is not None and rule.display_name not in agents:
            continue
        if _has_content(rule.match) and not content_map:
            continue
        matched, evidence_paths = _evaluate_condition(
            rule,
            rule.match,
            normalized,
            content_map,
            byte_limit=pack.content_byte_limit,
            diagnostics=diagnostics,
        )
        if not matched:
            continue
        evidence: dict[str, object] = {"source": source}
        if len(evidence_paths) == 1:
            evidence["path"] = evidence_paths[0]
        else:
            evidence["paths"] = list(evidence_paths)
        relationship = rule.match.get("relationship")
        if isinstance(relationship, Mapping):
            evidence["relationship"] = relationship.get("type")
        matches.append(StructuredMatch(rule, evidence))
    resolved = {
        str(matched.rule.match["resolves_ambiguity"])
        for matched in matches
        if matched.rule.match.get("resolves_ambiguity") is not None
    }
    if resolved:
        matches = [
            matched
            for matched in matches
            if str(matched.rule.match.get("ambiguous_group") or "") not in resolved
        ]
    return matches, diagnostics


def relationship_matches(
    clauses: Sequence[Mapping[str, object]],
    facts: Sequence[Mapping[str, object]],
    *,
    relationship: str,
    min_matches: int | None = None,
) -> tuple[Mapping[str, object], ...]:
    """Evaluate event conjunctions with one shared relationship key.

    Supported keys are ``commit``, ``pr``, ``ref``, and ``tree``. This helper
    is deliberately data-oriented so forge and local collectors can use the
    same deterministic semantics for allOf/anyOf/minMatches contracts.
    """

    key = {
        "same_commit": "commit",
        "same_pr": "pr",
        "same_ref": "ref",
        "same_tree": "tree",
        "identity_plus_ref": "ref",
        "path_plus_content": "path",
    }.get(relationship)
    if key is None:
        raise ValueError(f"unsupported relationship {relationship!r}")
    groups: dict[object, list[Mapping[str, object]]] = {}
    for fact in facts:
        marker = fact.get(key)
        if marker is not None:
            groups.setdefault(marker, []).append(fact)
    needed = min_matches if min_matches is not None else len(clauses)
    for marker in sorted(groups, key=str):
        group = groups[marker]
        satisfied = 0
        selected: list[Mapping[str, object]] = []
        for clause in clauses:
            candidate = next(
                (
                    fact
                    for fact in group
                    if all(fact.get(name) == value for name, value in clause.items())
                ),
                None,
            )
            if candidate is not None:
                satisfied += 1
                selected.append(candidate)
        if satisfied >= needed:
            return tuple(selected)
    return ()
