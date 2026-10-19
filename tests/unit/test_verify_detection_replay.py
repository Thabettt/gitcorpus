from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_detection_replay.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("verify_detection_replay", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_MODULE = _load_script()


def test_replay_parser_defaults_pack_version_to_none():
    args = _MODULE.build_parser().parse_args(["--run-id", "99"])
    assert args.run_id == 99
    assert args.pack_version is None
    assert args.sample == "random"


def test_replay_parser_accepts_a_pack_version_override():
    args = _MODULE.build_parser().parse_args(["--run-id", "99", "--pack-version", "2026-10-19"])
    assert args.pack_version == "2026-10-19"


def test_replay_diff_keys_reports_the_union_of_mismatched_keys():
    assert _MODULE._diff_keys({"a": 1, "b": 2}, {"a": 1, "c": 3}) == ["b", "c"]


def test_replay_diff_keys_is_empty_when_documents_match():
    assert _MODULE._diff_keys({"agents": ["a"]}, {"agents": ["a"]}) == []
