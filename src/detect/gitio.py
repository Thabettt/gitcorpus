from __future__ import annotations

import contextlib
import os
import random
import re
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, cast

from lib import cancellation
from lib.batching import chunked

_CANCEL_POLL = 0.1
_STDERR_LIMIT = 200
LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%cI%x1f%B%x1e"
_UNIT = "\x1f"
_RECORD = "\x1e"
_MERGE_PR = re.compile(r"Merge pull request #(?P<pr>\d+) from (?P<owner>[^/\s]+)/(?P<head>\S+)")
_MERGE_LOCAL = re.compile(r"Merge branch '(?P<head>[^']+)'")
_SHOW_BATCH = 600
_PR_FETCH_CHUNK_REFS = 500
_LS_REMOTE_TIMEOUT = 120.0
_PR_CHUNK_TIMEOUT = 600.0
_WALK_WORKERS = 8


class GitError(RuntimeError):
    def __init__(self, argv: Sequence[str], returncode: int, stderr: str) -> None:
        message = (
            f"{' '.join(str(part) for part in argv)} -> exit {returncode}: {stderr[:_STDERR_LIMIT]}"
        )
        super().__init__(message)
        self.argv = tuple(str(part) for part in argv)
        self.returncode = returncode
        self.stderr = stderr


def git_env() -> dict[str, str]:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    # Scans fetch thousands of objects; auto-gc/repack maintenance on every
    # fetch would storm the disk, and optional locks are pure overhead here.
    env["GIT_OPTIONAL_LOCKS"] = "0"
    # Never let git surface an askpass dialog: empty values are skipped by git,
    # and GIT_TERMINAL_PROMPT=0 blocks the terminal fallback, so auth-required
    # operations fail fast and clean instead of blocking a scan worker.
    env["GIT_ASKPASS"] = ""
    env["SSH_ASKPASS"] = ""
    env["GIT_CONFIG_COUNT"] = "2"
    env["GIT_CONFIG_KEY_0"] = "gc.auto"
    env["GIT_CONFIG_VALUE_0"] = "0"
    env["GIT_CONFIG_KEY_1"] = "maintenance.auto"
    env["GIT_CONFIG_VALUE_1"] = "false"
    return env


def git_error_tail(exc: BaseException) -> str:
    """Last non-empty stderr line of a git failure, capped for notes."""
    stderr = getattr(exc, "stderr", "") or ""
    line = next((text.strip() for text in reversed(stderr.splitlines()) if text.strip()), "")
    if not line:
        line = str(exc)
    return line[:160]


_DEAD_PHRASES = (
    "not found",
    "could not read username",
    "authentication failed",
    "returned error: 404",
    "returned error: 401",
    "returned error: 403",
)
_TRANSIENT_PHRASES = (
    "could not resolve host",
    "couldn't connect to server",
    "failed to connect",
    "connection was reset",
    "connection reset",
    "operation timed out",
    "timed out",
    "early eof",
    "rpc failed",
    "returned error: 500",
    "returned error: 502",
    "returned error: 503",
    "returned error: 504",
)
_LOCAL_PHRASES = (
    "index.lock",
    "cannot lock",
    "unable to create",
    "already exists and is not an empty directory",
    "permission denied",
    "no space left",
)


def classify_git_failure(exc: BaseException) -> str:
    """Map a git/subprocess failure to a retry policy class.

    dead      — the repository is gone or private; retrying cannot help.
    transient — network/DNS/server trouble; pause via the breaker, retry later.
    local     — lock/disk/permission trouble; retry inline as before.
    fatal     — unknown; fail fast and record.
    """
    if isinstance(exc, subprocess.TimeoutExpired):
        return "transient"
    stderr = ""
    if isinstance(exc, GitError):
        stderr = exc.stderr or ""
    haystack = f"{stderr}\n{exc}".lower()
    if any(phrase in haystack for phrase in _DEAD_PHRASES):
        return "dead"
    if any(phrase in haystack for phrase in _TRANSIENT_PHRASES):
        return "transient"
    if any(phrase in haystack for phrase in _LOCAL_PHRASES):
        return "local"
    return "fatal"


def _sleep_interruptibly(delay: float) -> None:
    deadline = time.monotonic() + delay
    while True:
        cancellation.check()
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        time.sleep(min(0.25, remaining))


def retry_call[T](
    fn: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
    retryable: Callable[[BaseException], bool] | None = None,
) -> T:
    """Call ``fn`` retrying git failures with exponential jittered backoff.

    ``retryable`` decides per-failure whether another attempt is worth it;
    dead repositories fail fast instead of burning four attempts apiece.
    """
    last: GitError | subprocess.TimeoutExpired | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            return fn()
        except (GitError, subprocess.TimeoutExpired) as exc:
            last = exc
            if retryable is not None and not retryable(exc):
                raise
            if attempt >= attempts:
                raise
            delay = base_delay * (2 ** (attempt - 1)) * (1.0 + jitter())
            if sleep is time.sleep:
                _sleep_interruptibly(delay)
            else:
                sleep(delay)
    raise last or GitError([], 0, "retry_call exhausted without an error")


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate()


def _run_git_process(
    argv: Sequence[str],
    *,
    cwd: Path | str,
    timeout: float | None,
    stdin: BinaryIO | None,
    text: bool,
) -> str | bytes:
    process = subprocess.Popen(
        ["git", *argv],
        cwd=str(cwd),
        stdin=stdin if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_env(),
        text=text,
        **({"encoding": "utf-8", "errors": "replace"} if text else {}),
    )
    deadline = None if timeout is None else time.monotonic() + timeout
    try:
        while True:
            cancellation.check()
            step = _CANCEL_POLL
            if deadline is not None:
                step = min(step, max(0.01, deadline - time.monotonic()))
            try:
                stdout, stderr = process.communicate(timeout=step)
                break
            except subprocess.TimeoutExpired:
                if deadline is not None and time.monotonic() >= deadline:
                    process.kill()
                    process.communicate()
                    raise subprocess.TimeoutExpired(["git", *argv], timeout) from None
    except BaseException:
        _terminate(process)
        raise
    if process.returncode != 0:
        message = stderr.decode("utf-8", errors="replace") if not text else (stderr or "")
        raise GitError(["git", *argv], process.returncode, message)
    return stdout or ("" if text else b"")


def run_git(
    argv: Sequence[str],
    *,
    cwd: Path | str,
    timeout: float | None = None,
    stdin: BinaryIO | None = None,
) -> str:
    return cast(str, _run_git_process(argv, cwd=cwd, timeout=timeout, stdin=stdin, text=True))


def run_git_bytes(
    argv: Sequence[str],
    *,
    cwd: Path | str,
    timeout: float | None = None,
    stdin: BinaryIO | None = None,
) -> bytes:
    return cast(bytes, _run_git_process(argv, cwd=cwd, timeout=timeout, stdin=stdin, text=False))


@dataclass
class GitRepo:
    dest: Path
    timeout: float | None = None
    _log_cache: dict[int, tuple[CommitRecord, ...]] = field(default_factory=dict, repr=False)

    def git(self, *args: str, timeout: float | None = None, stdin: BinaryIO | None = None) -> str:
        return run_git(
            args,
            cwd=self.dest,
            timeout=self.timeout if timeout is None else timeout,
            stdin=stdin,
        )

    def read_blobs(self, paths: Sequence[str]) -> dict[str, str | None]:
        return _read_blobs_batch(self, paths)


def _read_blobs_batch(repo: GitRepo, paths: Sequence[str]) -> dict[str, str | None]:
    # One `cat-file --batch` process returns every requested blob in a single
    # round trip; per-blob `git show` calls would pay a process spawn (and on
    # a filtered clone, a lazy fetch) apiece. Any failure degrades to the
    # per-path reads so the caller keeps today's semantics.
    if not paths:
        return {}
    request = "".join(f"HEAD:{path}\n" for path in paths)
    handle = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".git-paths")
    try:
        handle.write(request.encode("utf-8"))
        handle.close()
        with open(handle.name, "rb") as stdin:
            data = run_git_bytes(
                ["cat-file", "--batch"],
                cwd=repo.dest,
                timeout=repo.timeout,
                stdin=stdin,
            )
    except (GitError, subprocess.TimeoutExpired):
        return {path: read_blob(repo, path) for path in paths}
    finally:
        with contextlib.suppress(OSError):
            os.unlink(handle.name)
    results: dict[str, str | None] = {}
    cursor = 0
    try:
        for path in paths:
            end = data.index(b"\n", cursor)
            header = data[cursor:end]
            cursor = end + 1
            if header.endswith(b" missing"):
                results[path] = None
                continue
            size = int(header.rsplit(b" ", 1)[1])
            content = data[cursor : cursor + size]
            cursor += size + 1
            results[path] = content.decode("utf-8", errors="replace")
    except (ValueError, IndexError):
        return {path: read_blob(repo, path) for path in paths}
    return results


def clone_lean(
    full_name: str,
    dest: Path,
    *,
    depth: int,
    timeout: float | None = None,
    url: str | None = None,
) -> None:
    # git resolves the destination relative to the working directory it is
    # started in, so a relative dest would nest inside cwd instead of landing
    # at the requested path. Anchor both to the destination's parent.
    dest = Path(os.path.abspath(dest))
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_git(
        [
            "clone",
            "--quiet",
            "--single-branch",
            "--no-checkout",
            "--no-tags",
            f"--depth={depth}",
            "--filter=blob:none",
            url or f"https://github.com/{full_name}.git",
            str(dest),
        ],
        cwd=dest.parent,
        timeout=timeout,
    )


def list_tree_entries(repo: GitRepo) -> tuple[tuple[str, str], ...]:
    output = repo.git("ls-tree", "-r", "HEAD")
    entries: list[tuple[str, str]] = []
    for line in output.splitlines():
        meta, _, path = line.partition("\t")
        parts = meta.split()
        if len(parts) >= 3 and path:
            entries.append((path, parts[2]))
    return tuple(entries)


def list_tree(repo: GitRepo) -> tuple[str, ...]:
    return tuple(path for path, _oid in list_tree_entries(repo))


def read_blob(repo: GitRepo, path: str) -> str | None:
    try:
        return repo.git("show", f"HEAD:{path}")
    except GitError:
        return None


@dataclass(frozen=True)
class CommitRecord:
    sha: str
    author_name: str
    author_email: str
    committer_name: str
    committer_email: str
    committed_at: str
    message: str


def parse_log(output: str) -> tuple[CommitRecord, ...]:
    records: list[CommitRecord] = []
    for chunk in output.split(_RECORD):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        parts = chunk.split(_UNIT, 6)
        if len(parts) != 7:
            continue
        records.append(CommitRecord(*parts))
    return tuple(records)


def read_log(repo: GitRepo, *, limit: int) -> tuple[CommitRecord, ...]:
    cached = repo._log_cache.get(limit)
    if cached is None:
        output = repo.git("log", "-n", str(limit), f"--format={LOG_FORMAT}", "HEAD")
        cached = parse_log(output)
        repo._log_cache[limit] = cached
    return cached


def remote_pr_refs(repo: GitRepo) -> dict[int, str]:
    output = repo.git(
        "ls-remote", "--refs", "origin", "refs/pull/*/head", timeout=_LS_REMOTE_TIMEOUT
    )
    refs: dict[int, str] = {}
    for line in output.splitlines():
        sha, _, name = line.partition("\t")
        if not sha or not name.startswith("refs/pull/") or not name.endswith("/head"):
            continue
        number = name[len("refs/pull/") : -len("/head")]
        if number.isdigit():
            refs[int(number)] = sha
    return refs


def fetch_pr_refs(repo: GitRepo, *, depth: int, chunk_refs: int | None = None) -> None:
    # Size the ref set first, then request exactly those refs in bounded
    # chunks. A single wildcard fetch of a repo with thousands of PRs makes
    # the server build one giant pack; explicit refspecs keep every request
    # bounded, stream sooner, and only retry the failed chunk.
    if chunk_refs is None:
        chunk_refs = _PR_FETCH_CHUNK_REFS
    remote = remote_pr_refs(repo)
    if not remote:
        return
    for numbers in chunked(sorted(remote), chunk_refs):
        refspecs = [f"+refs/pull/{number}/head:refs/gc/pr/{number}" for number in numbers]
        repo.git(
            "fetch",
            "--quiet",
            "--depth",
            str(depth),
            "--filter=blob:none",
            "--no-tags",
            "origin",
            *refspecs,
            timeout=_PR_CHUNK_TIMEOUT,
        )


_FETCH_BLOBS_ARGV = (
    "-c",
    "fetch.negotiationAlgorithm=noop",
    "fetch",
    "origin",
    "--no-tags",
    "--no-write-fetch-head",
    "--recurse-submodules=no",
    "--filter=blob:none",
    "--stdin",
)


def fetch_blobs(repo: GitRepo, oids: Sequence[str]) -> None:
    # The promisor's own object fetch: one round trip for every wanted blob,
    # which GitHub only serves through this --stdin object-want path.
    if not oids:
        return
    handle = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".git-oids")
    try:
        handle.write("\n".join(oids).encode("ascii") + b"\n")
        handle.close()
        with open(handle.name, "rb") as stdin:
            repo.git(*_FETCH_BLOBS_ARGV, stdin=stdin, timeout=_PR_CHUNK_TIMEOUT)
    finally:
        with contextlib.suppress(OSError):
            os.unlink(handle.name)


def list_pr_refs(repo: GitRepo) -> dict[int, str]:
    output = repo.git("for-each-ref", "--format=%(refname) %(objectname)", "refs/gc/pr")
    refs: dict[int, str] = {}
    for line in output.splitlines():
        name, _, sha = line.partition(" ")
        number = name.rpartition("/")[2]
        if number.isdigit() and sha:
            refs[int(number)] = sha
    return refs


def walk_pr_shas(
    repo: GitRepo,
    refs: Mapping[int, str],
    *,
    depth: int,
    workers: int = _WALK_WORKERS,
    pool: ThreadPoolExecutor | None = None,
) -> dict[int, tuple[str, ...]]:
    def walk_one(item: tuple[int, str]) -> tuple[int, tuple[str, ...]]:
        number, sha = item
        output = repo.git("rev-list", "-n", str(depth), sha)
        return number, tuple(line for line in output.splitlines() if line)

    items = sorted(refs.items())
    if pool is not None:
        return dict(pool.map(walk_one, items))
    if workers <= 1 or len(items) <= 1:
        return dict(walk_one(item) for item in items)
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as local:
        return dict(local.map(walk_one, items))


def read_commits(repo: GitRepo, shas: Sequence[str]) -> dict[str, CommitRecord]:
    # `git show` resolves each commit's tree (the diff machinery), which on a
    # --filter=tree:0 fetch means one lazy-fetch round trip per commit. Plain
    # `log --no-walk` reads commit objects only, so it stays local and exact.
    records: dict[str, CommitRecord] = {}
    for batch in chunked(list(shas), _SHOW_BATCH):
        output = repo.git("log", "--no-walk", f"--format={LOG_FORMAT}", *batch)
        for record in parse_log(output):
            records[record.sha] = record
    return records


def parse_merge_branches(
    messages: Iterable[tuple[str | None, str]],
) -> list[tuple[int | None, str]]:
    found: list[tuple[int | None, str]] = []
    for _sha, message in messages:
        first = (message or "").split("\n", 1)[0].strip()
        match = _MERGE_PR.match(first)
        if match:
            found.append((int(match.group("pr")), match.group("head")))
            continue
        match = _MERGE_LOCAL.match(first)
        if match:
            found.append((None, match.group("head")))
    return found
