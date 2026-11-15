from __future__ import annotations

import re
from pathlib import Path

from detect.attribution import build_channel_regex
from detect.packs import load_pack_file, pack_digest

ROOT = Path(__file__).resolve().parents[2]
OLD_PACK_FILE = ROOT / "packs" / "2026-10-19.json"
PACK_FILE = ROOT / "packs" / "2026-11-14.json"


def test_schema_v2_positive_regexes_compile_and_ids_are_unique():
    pack = load_pack_file(PACK_FILE)
    assert pack.schema_version == 2
    assert len({rule.id for rule in pack.rules}) == len(pack.rules)
    for rule in pack.rules:
        raw = rule.match.get("regex") or rule.pattern
        if raw:
            re.compile(str(raw))


def test_schema_v2_catalogue_counts_and_pseudo_family_are_exact():
    pack = load_pack_file(PACK_FILE)
    active = [family for family in pack.families if family.category == "active"]
    assert len(active) == 78
    assert len([family for family in active if family.cohort == "incumbent"]) == 47
    assert len([family for family in active if family.cohort == "addition"]) == 25
    assert len([family for family in active if family.cohort == "v2"]) == 6
    assert len([family for family in active if family.matcher_generation == "current"]) == 72
    assert [family.name for family in pack.families if family.category == "pseudo"] == ["Generic"]


def test_unsafe_identity_hypotheses_are_rejections_not_positive_rules():
    pack = load_pack_file(PACK_FILE)
    positive = {
        str(rule.match.get("regex") or rule.pattern)
        for rule in pack.rules
        if rule.channel in {"author", "committer"}
    }
    for unsafe in ("Claude", "ChatGPT", "Codex", "cursor", "AI Assistant"):
        assert unsafe not in positive
    rejection_ids = {rule.id for rule in pack.rejections}
    assert "cursor.unsupported-cursor-md" in rejection_ids
    assert "qodo.broad-directory" in rejection_ids
    assert "abacus.release-bot" in rejection_ids


def test_old_pack_matches_factory_droid_bot_literally():
    pack = load_pack_file(OLD_PACK_FILE)
    assert any(
        pattern.pattern == r"factory-droid\[bot\]" and pattern.agent == "Factory Droid"
        for pattern in pack.authors
    )
    assert re.search(r"factory-droid\[bot\]", "factory-droid[bot]") is not None

    channel = build_channel_regex(pack.authors)
    assert channel.regex is not None
    match = channel.regex.search("factory-droid[bot]")
    assert match is not None
    assert channel.names[match.lastgroup] == "Factory Droid"


def test_old_pack_has_79_authors_and_a_stable_roundtrip_digest():
    pack = load_pack_file(OLD_PACK_FILE)
    assert pack.version == "2026-10-19"
    assert len(pack.authors) == 79
    assert len({(pattern.pattern, pattern.agent) for pattern in pack.authors}) == 79
    assert pack_digest(pack) == pack_digest(load_pack_file(OLD_PACK_FILE))
