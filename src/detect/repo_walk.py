from __future__ import annotations

import contextlib
import heapq
import os
import random
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

from detect.gitio import GitRepo, git_env
from lib import cancellation

# Environment knob: percentage of order-dependent walks that are additionally
# verified against a real `git rev-list`. Gates run at 100.
_VERIFY_ENV = "GITCORPUS_WALK_VERIFY_PCT"
_MAX_MISMATCHES = 3

_HDR = re.compile(rb"^([0-9a-f]{40}) (commit|tree|blob|tag) (\d+)$")
_PARENT = re.compile(rb"^parent ([0-9a-f]{40})$", re.M)
_COMMITTER_TS = re.compile(rb"^committer [^\n]*> (\d+) [+-]\d{4}$", re.M)

_state: dict[str, object] = {"checked": 0, "mismatches": 0, "disabled": False}


class WalkAnomaly(RuntimeError):
    """The in-process walk cannot proceed; the caller must fall back."""


def verification_summary() -> dict[str, object]:
    return dict(_state)


def reset_verification() -> None:
    _state.update({"checked": 0, "mismatches": 0, "disabled": False})


def _verify_pct() -> int:
    raw = os.environ.get(_VERIFY_ENV, "10")
    try:
        value = int(raw)
    except ValueError:
        return 10
    return max(0, min(100, value))


class CatFileBatch:
    """One long-lived `git cat-file --batch` process per repository."""

    def __init__(self, dest: Path) -> None:
        try:
            self._process = subprocess.Popen(
                ["git", "cat-file", "--batch"],
                cwd=str(dest),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=git_env(),
            )
        except OSError as exc:
            raise WalkAnomaly(f"cat-file failed to start: {exc}") from exc

    def commit(self, oid: str) -> tuple[tuple[str, ...], int] | None:
        """Return (parents, committer epoch) or None when the object is missing."""
        if self._process.stdin is None or self._process.stdout is None:
            raise WalkAnomaly("cat-file pipes unavailable")
        try:
            self._process.stdin.write(oid.encode("ascii") + b"\n")
            self._process.stdin.flush()
        except (OSError, ValueError) as exc:
            raise WalkAnomaly(f"cat-file pipe failed: {exc}") from exc
        header = self._process.stdout.readline()
        if not header:
            raise WalkAnomaly("cat-file stream ended")
        if header.endswith(b" missing\n"):
            return None
        match = _HDR.match(header.rstrip(b"\n"))
        if match is None:
            raise WalkAnomaly(f"unexpected cat-file header: {header[:80]!r}")
        if match.group(2) != b"commit":
            raise WalkAnomaly(f"object {oid} is not a commit")
        size = int(match.group(3))
        body = self._process.stdout.read(size)
        self._process.stdout.read(1)
        parents = tuple(item.group(1).decode() for item in _PARENT.finditer(body))
        timestamp = _COMMITTER_TS.search(body)
        if timestamp is None:
            raise WalkAnomaly(f"commit {oid} has no committer timestamp")
        return parents, int(timestamp.group(1))

    def close(self) -> None:
        process = self._process
        if process.stdin is not None:
            with contextlib.suppress(OSError, ValueError):
                process.stdin.close()
        if process.poll() is None:
            process.kill()
        with contextlib.suppress(OSError):
            process.wait()
        if process.stdout is not None:
            with contextlib.suppress(OSError, ValueError):
                process.stdout.close()


def _fallback(repo: GitRepo, sha: str, depth: int) -> tuple[str, ...]:
    output = repo.git("rev-list", "-n", str(depth), sha)
    return tuple(line for line in output.splitlines() if line)


def _walk_one(
    cat: CatFileBatch,
    cache: dict[str, tuple[tuple[str, ...], int]],
    tip: str,
    depth: int,
    shallow: frozenset[str],
) -> tuple[str, ...]:
    """First ``depth`` commits of ``tip`` in git rev-list default order.

    Default order is reverse chronological (committer date, newest first) with
    lazy parent expansion; equal dates keep insertion order. Parents are read
    when their child is popped, exactly like git's date-ordered commit list.
    """
    heap: list[tuple[int, int, str]] = [(0, 0, tip)]
    seen = {tip}
    out: list[str] = []
    seq = 0
    while heap and len(out) < depth:
        cancellation.check()
        _neg_ts, _seq, oid = heapq.heappop(heap)
        out.append(oid)
        if oid in shallow:
            continue
        record = cache.get(oid)
        if record is None:
            record = cat.commit(oid)
            if record is None:
                raise WalkAnomaly(f"commit {oid} is missing")
            cache[oid] = record
        parents, _ts = record
        for parent in parents:
            if parent in seen:
                continue
            seen.add(parent)
            parent_record = cache.get(parent)
            if parent_record is None:
                parent_record = cat.commit(parent)
                if parent_record is None:
                    raise WalkAnomaly(f"parent {parent} of {oid} is missing")
                cache[parent] = parent_record
            parent_ts = parent_record[1]
            seq += 1
            heapq.heappush(heap, (-parent_ts, seq, parent))
    return tuple(out)


def _has_replace_refs(git_dir: Path) -> bool:
    replace = git_dir / "refs" / "replace"
    if replace.is_dir():
        try:
            next(replace.iterdir())
            return True
        except StopIteration:
            return False
    return False


def _load_shallow(git_dir: Path) -> frozenset[str]:
    shallow_file = git_dir / "shallow"
    if not shallow_file.exists():
        return frozenset()
    return frozenset(
        line.strip()
        for line in shallow_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    )


def _verify(
    repo: GitRepo, sha: str, depth: int, shas: tuple[str, ...], pct: int
) -> tuple[str, ...]:
    if pct <= 0 or random.randint(1, 100) > pct:
        return shas
    truth = _fallback(repo, sha, depth)
    _state["checked"] = int(_state["checked"]) + 1
    if set(truth) != set(shas):
        _state["mismatches"] = int(_state["mismatches"]) + 1
        if int(_state["mismatches"]) >= _MAX_MISMATCHES:
            _state["disabled"] = True
        return truth
    return shas


def walk_windows(
    repo: GitRepo, refs: Mapping[int, str], *, depth: int
) -> dict[int, tuple[str, ...]]:
    """PR tip → first ``depth`` commits, set-identical to per-tip rev-list."""
    if not refs:
        return {}
    git_dir = Path(repo.dest) / ".git"
    alternates = git_dir / "objects" / "info" / "alternates"
    if _has_replace_refs(git_dir) or alternates.exists():
        return {number: _fallback(repo, sha, depth) for number, sha in sorted(refs.items())}
    shallow = _load_shallow(git_dir)
    pct = _verify_pct()
    results: dict[int, tuple[str, ...]] = {}
    exact = not bool(_state["disabled"])
    cache: dict[str, tuple[tuple[str, ...], int]] = {}
    cat: CatFileBatch | None = None
    try:
        if exact:
            try:
                cat = CatFileBatch(Path(repo.dest))
            except WalkAnomaly:
                exact = False
        for number, sha in sorted(refs.items()):
            if exact and cat is not None:
                try:
                    shas = _walk_one(cat, cache, sha, depth, shallow)
                except WalkAnomaly:
                    shas = _fallback(repo, sha, depth)
                else:
                    shas = _verify(repo, sha, depth, shas, pct)
                    if _state["disabled"]:
                        exact = False
            else:
                shas = _fallback(repo, sha, depth)
            results[number] = shas
    finally:
        if cat is not None:
            cat.close()
    return results
