from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from detect.gitio import GitError

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "verify_walk_equivalence.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("verify_walk_equivalence", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gate_skips_a_head_it_cannot_resolve(tmp_path, monkeypatch, capsys):
    gate = _load_gate()
    repo = tmp_path / "owner__repo"
    (repo / ".git").mkdir(parents=True)

    class FakeRepo:
        def __init__(self, dest):
            self.dest = dest

        def git(self, *args, **kwargs):
            raise GitError(list(args), 128, "fatal: ambiguous argument 'HEAD'")

    monkeypatch.setattr(gate, "GitRepo", FakeRepo)
    monkeypatch.setattr(gate, "clone_lean", lambda *args, **kwargs: None)
    monkeypatch.setattr(gate, "fetch_pr_refs", lambda repo, depth: {})
    monkeypatch.setattr(gate, "walk_windows", lambda repo, refs, depth: {})
    monkeypatch.setattr(
        sys, "argv", ["verify_walk_equivalence.py", "owner/repo", "--root", str(tmp_path)]
    )

    assert gate.main() == 0
    assert "head=skipped" in capsys.readouterr().out


def test_gate_fails_when_the_head_walk_fails(tmp_path, monkeypatch, capsys):
    gate = _load_gate()
    repo = tmp_path / "owner__repo"
    (repo / ".git").mkdir(parents=True)

    class FakeRepo:
        def __init__(self, dest):
            self.dest = dest

        def git(self, *args, **kwargs):
            assert args[:2] == ("rev-parse", "HEAD")
            return "deadbeef\n"

    def fake_walk(repo, refs, depth):
        if refs == {0: "deadbeef"}:
            raise GitError(["cat-file"], 128, "fatal: bad object deadbeef")
        return {}

    monkeypatch.setattr(gate, "GitRepo", FakeRepo)
    monkeypatch.setattr(gate, "clone_lean", lambda *args, **kwargs: None)
    monkeypatch.setattr(gate, "fetch_pr_refs", lambda repo, depth: {})
    monkeypatch.setattr(gate, "walk_windows", fake_walk)
    monkeypatch.setattr(
        sys, "argv", ["verify_walk_equivalence.py", "owner/repo", "--root", str(tmp_path)]
    )

    assert gate.main() == 1
    assert "head=error" in capsys.readouterr().out


def test_gate_fails_when_the_head_truth_cannot_be_read(tmp_path, monkeypatch, capsys):
    gate = _load_gate()
    repo = tmp_path / "owner__repo"
    (repo / ".git").mkdir(parents=True)

    class FakeRepo:
        def __init__(self, dest):
            self.dest = dest

        def git(self, *args, **kwargs):
            if args[:2] == ("rev-parse", "HEAD"):
                return "deadbeef\n"
            raise GitError(list(args), 128, "fatal: bad object deadbeef")

    def fake_walk(repo, refs, depth):
        return {0: ("s1",)} if refs == {0: "deadbeef"} else {}

    monkeypatch.setattr(gate, "GitRepo", FakeRepo)
    monkeypatch.setattr(gate, "clone_lean", lambda *args, **kwargs: None)
    monkeypatch.setattr(gate, "fetch_pr_refs", lambda repo, depth: {})
    monkeypatch.setattr(gate, "walk_windows", fake_walk)
    monkeypatch.setattr(
        sys, "argv", ["verify_walk_equivalence.py", "owner/repo", "--root", str(tmp_path)]
    )

    assert gate.main() == 1
    assert "head=error" in capsys.readouterr().out
