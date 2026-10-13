from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from detect.packs import (
    PackConflict,
    build_pack_from_dir,
    freeze_pack,
    load_frozen,
    pack_from_document,
    pack_to_document,
)


def write_csv(path: Path, header: str, rows: list[str]) -> None:
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


def make_src(tmp_path: Path) -> Path:
    src = tmp_path / "patterns"
    src.mkdir()
    write_csv(
        src / "tools.csv",
        "name,url",
        ["Claude Code,https://claude.com", "Cursor,https://cursor.com"],
    )
    write_csv(src / "authors.csv", "pattern,type,subtype", ["noreply@anthropic.com,AI,Claude Code"])
    write_csv(
        src / "files.csv",
        "pattern,type,subtype",
        ["CLAUDE.md,AI_FILE,Claude Code", ".cursor/,AI_FILE,Cursor"],
    )
    write_csv(src / "branches.csv", "pattern,type,subtype", ["claude/,AI-PR,Claude Code"])
    write_csv(src / "labels.csv", "pattern,type,subtype", ["ai-generated,AI-PR,Generic"])
    write_csv(src / "bots.csv", "pattern,type,subtype", [r"dependabot\[bot\],Bot,dependabot"])
    return src


def test_build_pack_from_dir_maps_all_channels(tmp_path):
    pack = build_pack_from_dir(make_src(tmp_path), version="2026-10-02-test")
    assert pack.version == "2026-10-02-test"
    assert pack.agents["Claude Code"] == "https://claude.com"
    assert pack.agents["Generic"] == "https://agents.md"  # pseudo-agent is always in the roster
    assert pack.files[0].pattern == "CLAUDE.md"
    assert pack.files[0].agent == "Claude Code"
    assert pack.bots[0].agent == "dependabot"
    assert pack.generic_weights == {"AGENTS.md": 0.3}
    assert pack.exclusions == frozenset({"CONVENTIONS.md"})


def test_document_roundtrip(tmp_path):
    pack = build_pack_from_dir(make_src(tmp_path), version="v1")
    assert pack_from_document(pack_to_document(pack)) == pack


def test_freeze_is_immutable(clean_db, tmp_path):
    engine = clean_db()
    pack = build_pack_from_dir(make_src(tmp_path), version="v1")
    freeze_pack(engine, pack)
    # trace_packs stores patterns only; the agents name->url map is not persisted
    assert load_frozen(engine, "v1") == replace(pack, agents={})
    with pytest.raises(PackConflict):
        freeze_pack(engine, replace(pack, generic_weights={"AGENTS.md": 0.1}))


def test_missing_channel_file_is_rejected(tmp_path):
    src = make_src(tmp_path)
    (src / "labels.csv").unlink()
    with pytest.raises(ValueError, match="labels.csv"):
        build_pack_from_dir(src, version="v1")
