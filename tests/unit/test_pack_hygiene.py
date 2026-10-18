from __future__ import annotations

import csv
import re
from pathlib import Path

from detect.attribution import build_channel_regex
from detect.packs import load_pack_file, pack_digest

ROOT = Path(__file__).resolve().parents[2]
AUTHORS_CSV = ROOT / "packs" / "patterns" / "authors.csv"
PACK_FILE = ROOT / "packs" / "2026-10-19.json"


def read_author_patterns(path: Path) -> list[tuple[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            ((row.get("pattern") or "").strip(), (row.get("subtype") or "").strip())
            for row in csv.DictReader(handle)
            if (row.get("pattern") or "").strip()
        ]


def test_author_patterns_compile_and_escape_metacharacters():
    rows = read_author_patterns(AUTHORS_CSV)
    assert rows
    for pattern, _agent in rows:
        re.compile(pattern)
        for index, char in enumerate(pattern):
            if char in "([.":
                assert index > 0 and pattern[index - 1] == "\\", (
                    f"unescaped {char!r} in {pattern!r}"
                )


def test_new_pack_matches_factory_droid_bot_literally():
    pack = load_pack_file(PACK_FILE)
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


def test_bare_codex_and_codex_email_are_each_present_once():
    patterns = [pattern for pattern, _agent in read_author_patterns(AUTHORS_CSV)]
    assert patterns.count("Codex") == 1
    assert patterns.count(r"codex@openai\.com") == 1
    assert "codex@openai.com" not in patterns


def test_pack_file_has_79_authors_and_a_stable_digest():
    pack = load_pack_file(PACK_FILE)
    assert pack.version == "2026-10-19"
    assert len(pack.authors) == 79
    assert len({(pattern.pattern, pattern.agent) for pattern in pack.authors}) == 79
    assert pack_digest(pack) == pack_digest(load_pack_file(PACK_FILE))
