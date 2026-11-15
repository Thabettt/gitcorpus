"""Release gate for every schema-v2 trace pack in ``packs/``.

A pack may never drop a rule of the pack before it without a rejection-ledger
entry, and every pack built under the 2026-11-15 method must account for each
Agentic Much? heuristic and declare provenance on each positive rule. This is
the check that would have stopped 2026-11-14 from silently losing surfaces.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / "packs"
# Packs released before the provenance contract existed.
PROVENANCE_FROM = "2026-11-15"


def _load_gate():
    spec = importlib.util.spec_from_file_location(
        "check_trace_pack", ROOT / "scripts" / "check_trace_pack.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _v2_packs() -> list[tuple[str, dict]]:
    packs = []
    for path in sorted(PACKS.glob("*.json")):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", path.stem):
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if int(doc.get("schema_version") or 1) >= 2:
            packs.append((path.stem, doc))
    return packs


PACK_IDS = [version for version, _doc in _v2_packs()]


@pytest.mark.parametrize("version", PACK_IDS)
def test_pack_passes_release_gate(version):
    gate = _load_gate()
    packs = dict(_v2_packs())
    ordered = sorted(packs)
    index = ordered.index(version)
    previous = packs[ordered[index - 1]] if index > 0 else None
    mapping = PACKS / "sources" / version / "baseline-mapping.csv"
    errors = gate.static_checks(
        packs[version],
        previous,
        mapping if mapping.exists() else None,
        require_provenance=version >= PROVENANCE_FROM,
    )
    assert errors == []


def test_packs_from_the_provenance_method_carry_a_baseline_mapping():
    for version in PACK_IDS:
        if version >= PROVENANCE_FROM:
            assert (PACKS / "sources" / version / "baseline-mapping.csv").exists(), version
