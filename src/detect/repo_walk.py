from __future__ import annotations

import contextlib
import heapq
import os
import random
import re
import subprocess
import threading
import time
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path

from detect.gitio import CommitRecord, GitRepo, git_binary, git_env
from lib import cancellation

# Environment knob: percentage of order-dependent walks that are additionally
# verified against a real `git rev-list`. Off by default; each `walk_windows`
# call spends at most `_VERIFY_MAX_PER_REPO` spawns on non-exhausted windows.
_VERIFY_ENV = "GITCORPUS_WALK_VERIFY_PCT"
_MAX_MISMATCHES = 3
_VERIFY_MAX_PER_REPO = 2

# A lazy fetch can stall behind a network round trip forever; the watchdog
# bounds both a single batch operation and the whole repository walk.
_OP_TIMEOUT_ENV = "GITCORPUS_CATFILE_OP_TIMEOUT_SECONDS"
_REPO_TIMEOUT_ENV = "GITCORPUS_CATFILE_REPO_TIMEOUT_SECONDS"
_DEFAULT_OP_TIMEOUT = 60.0
_DEFAULT_REPO_TIMEOUT = 180.0

_HDR = re.compile(r"^([0-9a-f]{40}) (commit|tree|blob|tag) (\d+)$")
_SHA = re.compile(r"[0-9a-f]{40}")
_IDENT = re.compile(rb"^(.*?) <(.*?)> (\d+) ([+-]\d{4})$")

_state: dict[str, object] = {"checked": 0, "mismatches": 0, "disabled": False}
_spawns = threading.local()


def cat_file_spawns() -> int:
    """Cat-file children spawned on this thread (per-repo phase diagnostics)."""
    return int(getattr(_spawns, "count", 0))


class WalkAnomaly(RuntimeError):
    """The in-process walk cannot proceed; the caller must fall back."""


def verification_summary() -> dict[str, object]:
    return dict(_state)


def reset_verification() -> None:
    _state.update({"checked": 0, "mismatches": 0, "disabled": False})


def _verify_pct() -> int:
    raw = os.environ.get(_VERIFY_ENV, "0")
    try:
        value = int(raw)
    except ValueError:
        return 0
    return max(0, min(100, value))


def _decode(data: bytes, encoding: str) -> str:
    try:
        return data.decode(encoding, errors="replace")
    except LookupError:
        return data.decode("utf-8", errors="replace")


def _split_ident(oid: str, raw: bytes, encoding: str) -> tuple[str, str, int, str]:
    match = _IDENT.match(raw)
    if match is None:
        raise WalkAnomaly(f"commit {oid} has a malformed ident: {raw[:80]!r}")
    name = _decode(match.group(1).rstrip(b" \t\n\r"), encoding)
    email = _decode(match.group(2), encoding)
    return name, email, int(match.group(3)), match.group(4).decode("ascii")


def _committed_at(epoch: int, tz: str) -> str:
    offset = int(tz[1:3]) * 60 + int(tz[3:5])
    if tz[0] == "-":
        offset = -offset
    try:
        when = datetime.fromtimestamp(epoch + offset * 60, tz=UTC)
    except (OverflowError, OSError, ValueError) as exc:
        raise WalkAnomaly(f"committer epoch {epoch} is out of range") from exc
    stamp = (
        f"{when.year:04d}-{when.month:02d}-{when.day:02d}"
        f"T{when.hour:02d}:{when.minute:02d}:{when.second:02d}"
    )
    if offset == 0:
        return stamp + "Z"
    sign = "-" if offset < 0 else "+"
    hours, minutes = divmod(abs(offset), 60)
    return f"{stamp}{sign}{hours:02d}:{minutes:02d}"


def _parse_raw_commit(oid: str, raw: bytes) -> tuple[tuple[str, ...], int, CommitRecord]:
    """Parse one raw commit object into (parents, committer epoch, record).

    Only the header block (before the first blank line) is scanned; header
    continuation lines (``gpgsig``, ``mergetag``) are skipped so they can
    never inject false fields.
    """
    header, _sep, body = raw.partition(b"\n\n")
    parents: list[str] = []
    idents: dict[bytes, bytes] = {}
    encoding = "utf-8"
    for line in header.split(b"\n"):
        if line.startswith(b" "):
            continue
        key, _space, value = line.partition(b" ")
        if key == b"parent":
            sha = value.decode("ascii", errors="replace")
            if _SHA.fullmatch(sha):
                parents.append(sha)
        elif key == b"author" or key == b"committer":
            idents[key] = value
        elif key == b"encoding":
            encoding = value.decode("ascii", errors="replace").strip()
    author = _split_ident(oid, idents.get(b"author", b""), encoding)
    committer = _split_ident(oid, idents.get(b"committer", b""), encoding)
    record = CommitRecord(
        sha=oid,
        author_name=author[0],
        author_email=author[1],
        committer_name=committer[0],
        committer_email=committer[1],
        committed_at=_committed_at(committer[2], committer[3]),
        message=_decode(body, encoding).rstrip("\n"),
    )
    return tuple(parents), committer[2], record


def _timeout_seconds(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


class CatFileBatch:
    """One long-lived `git cat-file --batch` process per repository."""

    def __init__(
        self,
        dest: Path,
        *,
        op_timeout: float | None = None,
        repo_timeout: float | None = None,
    ) -> None:
        self._op_timeout = (
            _timeout_seconds(_OP_TIMEOUT_ENV, _DEFAULT_OP_TIMEOUT)
            if op_timeout is None
            else op_timeout
        )
        self._repo_timeout = (
            _timeout_seconds(_REPO_TIMEOUT_ENV, _DEFAULT_REPO_TIMEOUT)
            if repo_timeout is None
            else repo_timeout
        )
        # Lazy fetching is what wedged Run #99: a missing object turned every
        # read into an unbounded network round trip. The walk reads only what
        # the fetch already brought; legitimate object fetches stay elsewhere.
        env = git_env()
        env["GIT_NO_LAZY_FETCH"] = "1"
        try:
            self._process = subprocess.Popen(
                [git_binary(), "cat-file", "--batch"],
                cwd=str(dest),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env=env,
            )
        except OSError as exc:
            raise WalkAnomaly(f"cat-file failed to start: {exc}") from exc
        _spawns.count = cat_file_spawns() + 1
        self._condition = threading.Condition()
        self._op_deadline: float | None = None
        self._repo_deadline = time.monotonic() + self._repo_timeout
        self._timed_out = False
        self._closed = False
        self._watchdog = threading.Thread(
            target=self._watch_for_timeouts,
            name="cat-file-watchdog",
            daemon=True,
        )
        self._watchdog.start()

    def _timeout_message(self) -> str:
        return (
            f"cat-file timed out after {self._op_timeout:g}s for one operation "
            f"or {self._repo_timeout:g}s for the repository"
        )

    def _watch_for_timeouts(self) -> None:
        with self._condition:
            while not self._closed:
                deadlines = [
                    deadline
                    for deadline in (self._op_deadline, self._repo_deadline)
                    if deadline is not None
                ]
                if not deadlines:
                    self._condition.wait()
                    continue
                remaining = min(deadlines) - time.monotonic()
                if remaining > 0:
                    self._condition.wait(timeout=remaining)
                    continue
                if self._timed_out:
                    self._condition.wait()
                    continue
                self._timed_out = True
                if self._process.poll() is None:
                    with contextlib.suppress(OSError):
                        self._process.kill()

    def _start_operation(self) -> None:
        with self._condition:
            if self._timed_out:
                raise WalkAnomaly(self._timeout_message())
            if self._closed:
                raise WalkAnomaly("cat-file batch is closed")
            self._op_deadline = time.monotonic() + self._op_timeout
            self._condition.notify_all()

    def _finish_operation(self) -> None:
        with self._condition:
            self._op_deadline = None
            self._condition.notify_all()

    def _raise_if_timed_out(self) -> None:
        with self._condition:
            timed_out = self._timed_out
        if timed_out:
            raise WalkAnomaly(self._timeout_message())

    def _read_stdout(self, size: int) -> bytes:
        try:
            return self._process.stdout.read(size)
        except (OSError, ValueError) as exc:
            self._raise_if_timed_out()
            raise WalkAnomaly(f"cat-file read failed: {exc}") from exc

    def _readline_stdout(self) -> bytes:
        try:
            return self._process.stdout.readline()
        except (OSError, ValueError) as exc:
            self._raise_if_timed_out()
            raise WalkAnomaly(f"cat-file read failed: {exc}") from exc

    def read(self, request: str) -> tuple[str, bytes] | None:
        """Send one request (an OID or a ``HEAD:<path>`` spec) and read its reply.

        Returns the ``<oid> <type> <size>`` header line plus the object's raw
        body; ``None`` means the object is missing.
        """
        if self._process.stdin is None or self._process.stdout is None:
            raise WalkAnomaly("cat-file pipes unavailable")
        self._start_operation()
        try:
            try:
                self._process.stdin.write(request.encode("utf-8") + b"\n")
                self._process.stdin.flush()
            except (OSError, ValueError) as exc:
                self._raise_if_timed_out()
                raise WalkAnomaly(f"cat-file pipe failed: {exc}") from exc
            header = self._readline_stdout()
            if not header:
                self._raise_if_timed_out()
                raise WalkAnomaly("cat-file stream ended")
            if header.endswith(b" missing\n"):
                return None
            line = header.decode("utf-8", errors="replace").rstrip("\n")
            match = _HDR.match(line)
            if match is None:
                self._raise_if_timed_out()
                raise WalkAnomaly(f"unexpected cat-file header: {header[:80]!r}")
            body = self._read_stdout(int(match.group(3)))
            self._read_stdout(1)
            self._raise_if_timed_out()
            return line, body
        finally:
            self._finish_operation()

    def commit(self, oid: str) -> tuple[tuple[str, ...], int, CommitRecord] | None:
        """Return (parents, committer epoch, record) or None when the object is missing."""
        result = self.read(oid)
        if result is None:
            return None
        header, body = result
        match = _HDR.match(header)
        if match is None or match.group(2) != "commit":
            raise WalkAnomaly(f"object {oid} is not a commit")
        return _parse_raw_commit(oid, body)

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            self._condition.notify_all()
        self._watchdog.join()
        process = self._process
        if process.stdin is not None:
            with contextlib.suppress(OSError, ValueError):
                process.stdin.close()
        if process.poll() is None:
            with contextlib.suppress(OSError):
                process.kill()
        with contextlib.suppress(OSError):
            process.wait()
        if process.stdout is not None:
            with contextlib.suppress(OSError, ValueError):
                process.stdout.close()


def _fallback(repo: GitRepo, sha: str, depth: int) -> tuple[str, ...]:
    output = repo.git(
        "rev-list",
        "-n",
        str(depth),
        sha,
        env_extra={"GIT_NO_LAZY_FETCH": "1"},
    )
    return tuple(line for line in output.splitlines() if line)


def _walk_one(
    cat: CatFileBatch,
    cache: dict[str, tuple[tuple[str, ...], int, CommitRecord]],
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
        parents, _ts, _record = record
        for parent in parents:
            if parent in seen:
                continue
            seen.add(parent)
            parent_record = cache.get(parent)
            if parent_record is None:
                parent_record = cat.commit(parent)
                if parent_record is None:
                    # A parent the promisor clone never fetched is a shallow
                    # boundary, exactly like a graft: stop expanding here.
                    continue
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


class RepoWalkSession:
    """One repository's cat-file child, commit cache, and shallow set.

    Owns a single ``git cat-file --batch`` process (and its watchdog) so every
    channel that reads this repository shares one child and one parsed-commit
    cache. ``window()`` is the walk primitive; ``record()`` and ``blob()``
    serve single-commit and single-path reads on the same child.
    """

    def __init__(self, cat: CatFileBatch, shallow: frozenset[str]) -> None:
        self._cat = cat
        self._shallow = shallow
        self._cache: dict[str, tuple[tuple[str, ...], int, CommitRecord]] = {}

    @classmethod
    def open(cls, repo: GitRepo) -> RepoWalkSession:
        dest = Path(repo.dest)
        shallow = _load_shallow(dest / ".git")
        return cls(CatFileBatch(dest), shallow)

    def window(self, tip: str, depth: int) -> tuple[tuple[str, ...], dict[str, CommitRecord]]:
        """First ``depth`` commits of ``tip`` plus the records parsed for them."""
        shas = _walk_one(self._cat, self._cache, tip, depth, self._shallow)
        return shas, self.records_for(shas)

    def records_for(self, shas: Iterable[str]) -> dict[str, CommitRecord]:
        """Records already in the cache for ``shas``; never reads git."""
        return {sha: self._cache[sha][2] for sha in shas if sha in self._cache}

    def record(self, oid: str) -> CommitRecord | None:
        """One commit's record from the shared cache; ``None`` when missing."""
        entry = self._cache.get(oid)
        if entry is None:
            entry = self._cat.commit(oid)
            if entry is None:
                return None
            self._cache[oid] = entry
        return entry[2]

    def blob(self, request: str) -> bytes | None:
        """Raw bytes for a ``HEAD:<path>`` (or OID) request; ``None`` when missing."""
        result = self._cat.read(request)
        return None if result is None else result[1]

    def close(self) -> None:
        self._cat.close()

    def __enter__(self) -> RepoWalkSession:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


def _verification_due(shas: tuple[str, ...], depth: int, pct: int, budget: int) -> bool:
    """Only non-exhausted windows are sampled, and only within the spawn budget."""
    if budget <= 0 or pct <= 0 or len(shas) < depth:
        return False
    return random.randint(1, 100) <= pct


def _verify(repo: GitRepo, sha: str, depth: int, shas: tuple[str, ...]) -> tuple[str, ...]:
    truth = _fallback(repo, sha, depth)
    _state["checked"] = int(_state["checked"]) + 1
    if set(truth) != set(shas):
        _state["mismatches"] = int(_state["mismatches"]) + 1
        if int(_state["mismatches"]) >= _MAX_MISMATCHES:
            _state["disabled"] = True
        return truth
    return shas


def _group_numbers_by_tip(refs: Mapping[int, str]) -> dict[str, list[int]]:
    """Map each unique tip SHA to its PR numbers, ordered by PR number."""
    grouped: dict[str, list[int]] = {}
    for number, sha in sorted(refs.items()):
        grouped.setdefault(sha, []).append(number)
    return grouped


def walk_windows(
    repo: GitRepo, refs: Mapping[int, str], *, depth: int
) -> dict[int, tuple[str, ...]]:
    """PR tip → first ``depth`` commits, set-identical to per-tip rev-list."""
    windows, _records = walk_windows_with_records(repo, refs, depth=depth)
    return windows


def walk_windows_with_records(
    repo: GitRepo,
    refs: Mapping[int, str],
    *,
    depth: int,
    session: RepoWalkSession | None = None,
) -> tuple[dict[int, tuple[str, ...]], dict[str, CommitRecord]]:
    """PR tip → first ``depth`` commits plus the records parsed from the walk.

    Walks served by ``rev-list`` (fallback/verify substitution) carry no
    records; callers backfill those SHAs through ``read_commits``. A supplied
    ``session`` is reused and never closed by this call.
    """
    if not refs:
        return {}, {}
    grouped = _group_numbers_by_tip(refs)
    git_dir = Path(repo.dest) / ".git"
    alternates = git_dir / "objects" / "info" / "alternates"
    if _has_replace_refs(git_dir) or alternates.exists():
        fallback_results: dict[int, tuple[str, ...]] = {}
        for sha, numbers in grouped.items():
            shas = _fallback(repo, sha, depth)
            for number in numbers:
                fallback_results[number] = shas
        return fallback_results, {}
    pct = _verify_pct()
    verify_budget = _VERIFY_MAX_PER_REPO
    results: dict[int, tuple[str, ...]] = {}
    exact = not bool(_state["disabled"])
    owns_session = session is None
    try:
        if exact and owns_session:
            try:
                session = RepoWalkSession.open(repo)
            except WalkAnomaly:
                exact = False
        for sha, numbers in grouped.items():
            if exact and session is not None:
                try:
                    shas, _ = session.window(sha, depth)
                except WalkAnomaly:
                    shas = _fallback(repo, sha, depth)
                else:
                    if _verification_due(shas, depth, pct, verify_budget):
                        shas = _verify(repo, sha, depth, shas)
                        verify_budget -= 1
                    if _state["disabled"]:
                        exact = False
            else:
                shas = _fallback(repo, sha, depth)
            for number in numbers:
                results[number] = shas
    finally:
        if owns_session and session is not None:
            session.close()
    records: dict[str, CommitRecord] = {}
    if session is not None:
        for shas in results.values():
            records.update(session.records_for(shas))
    return results, records
