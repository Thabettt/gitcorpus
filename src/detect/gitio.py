from __future__ import annotations

import base64
import contextlib
import json
import os
import random
import re
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, cast
from urllib.parse import urlparse

from lib import cancellation
from lib.batching import chunked

if TYPE_CHECKING:
    import httpx

_CANCEL_POLL = 0.1
_STDERR_LIMIT = 200
LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%cI%x1f%B%x1e"
_UNIT = "\x1f"
_RECORD = "\x1e"
_MERGE_PR = re.compile(r"Merge pull request #(?P<pr>\d+) from (?P<owner>[^/\s]+)/(?P<head>\S+)")
_MERGE_LOCAL = re.compile(r"Merge branch '(?P<head>[^']+)'")
_SHOW_BATCH = 600
_PR_FETCH_CHUNK_REFS = 2000
_LS_REMOTE_TIMEOUT = 120.0
_PR_CHUNK_TIMEOUT = 600.0
_PR_REFS_SNAPSHOT = ".gitcorpus-pr-refs.json"
_PR_SNAPSHOT_VERSION = 1
_MONSTER_PR_THRESHOLD = 500
_GATE_POLL_SECONDS = 0.5
_REMOTE_REFS_TIMEOUT = 30.0
_LS_REFS_USER_AGENT = "git/2.47.1"


def _configured_tokens() -> list[str]:
    from lib.gh_client import load_tokens

    return load_tokens()


def _auth_payload(token: str) -> str:
    return base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")


def _basic_auth_value(token: str) -> str:
    return f"Authorization: Basic {_auth_payload(token)}"


def _scrub_secrets(text: str) -> str:
    for token in _configured_tokens():
        text = text.replace(_auth_payload(token), "<redacted>")
        text = text.replace(token, "<redacted>")
    return text


class GitError(RuntimeError):
    def __init__(self, argv: Sequence[str], returncode: int, stderr: str) -> None:
        stderr = _scrub_secrets(stderr)
        message = (
            f"{' '.join(str(part) for part in argv)} -> exit {returncode}: {stderr[:_STDERR_LIMIT]}"
        )
        super().__init__(message)
        self.argv = tuple(str(part) for part in argv)
        self.returncode = returncode
        self.stderr = stderr


class RemoteRefsUnavailable(RuntimeError):
    """ls-refs could not be completed for a transient reason (no clone to fall back on)."""


@dataclass
class RemoteRefs:
    pr_refs: dict[int, str]
    head_refs: dict[str, str]


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
    # Authenticating HTTPS traffic lifts GitHub's per-IP anonymous-clone
    # throttling; the header rides GIT_CONFIG_* (never argv) and failure output
    # is scrubbed, so the token cannot leak into logs or notes.
    tokens = _configured_tokens()
    if tokens:
        env["GIT_CONFIG_COUNT"] = "3"
        # Scoped to github.com: a bare http.extraHeader would attach the token
        # to every HTTPS remote the process touches.
        env["GIT_CONFIG_KEY_2"] = "http.https://github.com/.extraHeader"
        env["GIT_CONFIG_VALUE_2"] = _basic_auth_value(tokens[0])
    return env


def git_error_tail(exc: BaseException) -> str:
    """Last non-empty stderr line of a git failure, capped for notes."""
    stderr = _scrub_secrets(getattr(exc, "stderr", "") or "")
    line = next((text.strip() for text in reversed(stderr.splitlines()) if text.strip()), "")
    if not line:
        line = _scrub_secrets(str(exc))
    return line[:160]


_DEAD_PHRASES = (
    "not found",
    "could not read username",
    "authentication failed",
    "returned error: 404",
    "returned error: 401",
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
    "returned error: 403",  # anonymous clones: rate limiting, not privacy
    "returned error: 429",
    "returned error: 500",
    "returned error: 502",
    "returned error: 503",
    "returned error: 504",
    "rate limit",
    "abuse detection",
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


_GIT_BINARY: str | None = None


def git_binary() -> str:
    """Resolve the git executable once per process.

    ``shutil.which("git")`` finds the Git-for-Windows cmd shim, which spawns
    the real mingw64 binary as a child; running the sibling directly halves
    the per-invocation spawn cost. Everything else (a POSIX git, a custom
    install) is used as found.
    """
    global _GIT_BINARY
    if _GIT_BINARY is not None:
        return _GIT_BINARY
    override = os.environ.get("GITCORPUS_GIT_BIN")
    if override and Path(override).exists():
        _GIT_BINARY = override
        return override
    found = shutil.which("git")
    if found is not None:
        resolved = Path(found)
        if resolved.parent.name.lower() == "cmd":
            sibling = resolved.parent.parent / "mingw64" / "bin" / "git.exe"
            if sibling.exists():
                _GIT_BINARY = str(sibling)
                return _GIT_BINARY
        _GIT_BINARY = found
        return found
    _GIT_BINARY = "git"
    return "git"


def _run_git_process(
    argv: Sequence[str],
    *,
    cwd: Path | str,
    timeout: float | None,
    stdin: BinaryIO | None,
    text: bool,
    env_extra: Mapping[str, str] | None = None,
) -> str | bytes:
    env = git_env()
    if env_extra:
        env.update(env_extra)
    process = subprocess.Popen(
        [git_binary(), *argv],
        cwd=str(cwd),
        stdin=stdin if stdin is not None else subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
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
    env_extra: Mapping[str, str] | None = None,
) -> str:
    return cast(
        str,
        _run_git_process(
            argv, cwd=cwd, timeout=timeout, stdin=stdin, text=True, env_extra=env_extra
        ),
    )


def run_git_bytes(
    argv: Sequence[str],
    *,
    cwd: Path | str,
    timeout: float | None = None,
    stdin: BinaryIO | None = None,
    env_extra: Mapping[str, str] | None = None,
) -> bytes:
    return cast(
        bytes,
        _run_git_process(
            argv, cwd=cwd, timeout=timeout, stdin=stdin, text=False, env_extra=env_extra
        ),
    )


@dataclass
class GitRepo:
    dest: Path
    timeout: float | None = None
    full_name: str | None = None
    _log_cache: dict[int, tuple[CommitRecord, ...]] = field(default_factory=dict, repr=False)
    _remote_refs_cache: RemoteRefs | None = field(default=None, repr=False)
    _origin_url: str | None = field(default=None, repr=False)

    def git(
        self,
        *args: str,
        timeout: float | None = None,
        stdin: BinaryIO | None = None,
        env_extra: Mapping[str, str] | None = None,
    ) -> str:
        return run_git(
            args,
            cwd=self.dest,
            timeout=self.timeout if timeout is None else timeout,
            stdin=stdin,
            env_extra=env_extra,
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
                env_extra={"GIT_NO_LAZY_FETCH": "1"},
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


_client_local = threading.local()

_LS_REFS_HEADERS = {
    "Content-Type": "application/x-git-upload-pack-request",
    "Accept": "application/x-git-upload-pack-result",
    "Git-Protocol": "version=2",
    "User-Agent": _LS_REFS_USER_AGENT,
}


def _pkt(payload: bytes) -> bytes:
    return f"{len(payload) + 4:04x}".encode("ascii") + payload


# Protocol v2 ls-refs: the command, a delimiter, then one request for the PR
# tips and one for the head refs; the probe verified this against GitHub.
_LS_REFS_BODY = (
    _pkt(b"command=ls-refs\n")
    + b"0001"
    + _pkt(b"peel\n")
    + _pkt(b"ref-prefix refs/pull/\n")
    + _pkt(b"ref-prefix refs/heads/\n")
    + b"0000"
)


def _build_http_client() -> httpx.Client:
    import httpx

    headers: dict[str, str] = {}
    tokens = _configured_tokens()
    if tokens:
        headers["Authorization"] = f"Basic {_auth_payload(tokens[0])}"
    return httpx.Client(headers=headers, timeout=_REMOTE_REFS_TIMEOUT, follow_redirects=True)


def _http_client() -> httpx.Client:
    """One keep-alive client per worker thread, built on first use."""
    client = getattr(_client_local, "client", None)
    if client is None:
        client = _build_http_client()
        _client_local.client = client
    return client


def _is_sha(text: str) -> bool:
    return len(text) == 40 and all(char in "0123456789abcdefABCDEF" for char in text)


def _register_ref(pr_refs: dict[int, str], head_refs: dict[str, str], sha: str, name: str) -> None:
    if name.startswith("refs/pull/") and name.endswith("/head"):
        number = name[len("refs/pull/") : -len("/head")]
        if number.isdigit():
            pr_refs[int(number)] = sha
    elif name.startswith("refs/heads/"):
        head_refs[name] = sha


def _parse_ls_refs(data: bytes) -> RemoteRefs:
    """Parse an ls-refs pkt-line stream; capabilities and ERR payloads are ignored."""
    pr_refs: dict[int, str] = {}
    head_refs: dict[str, str] = {}
    pos = 0
    while pos + 4 <= len(data):
        try:
            length = int(data[pos : pos + 4], 16)
        except ValueError:
            raise ValueError("malformed ls-refs pkt-line length") from None
        pos += 4
        if length <= 2:  # flush 0000, delimiter 0001, response-end 0002
            continue
        if length < 4 or pos + length - 4 > len(data):
            raise ValueError("truncated ls-refs pkt-line")
        payload = data[pos : pos + length - 4]
        pos += length - 4
        parts = payload.decode("utf-8", errors="replace").strip().split()
        if len(parts) >= 2 and _is_sha(parts[0]):
            _register_ref(pr_refs, head_refs, parts[0], parts[1])
    return RemoteRefs(pr_refs=pr_refs, head_refs=head_refs)


def _ls_refs_http(url: str) -> RemoteRefs:
    response = _http_client().post(url, content=_LS_REFS_BODY, headers=_LS_REFS_HEADERS)
    if response.status_code in (401, 404):
        raise GitError(["ls-refs", url], 128, "remote: Repository not found.")
    response.raise_for_status()
    return _parse_ls_refs(response.content)


def _is_github_https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc.lower() == "github.com"


def _upload_pack_url(repo: GitRepo) -> str | None:
    if repo.full_name:
        url = f"https://github.com/{repo.full_name}.git"
    else:
        if repo._origin_url is None:
            repo._origin_url = repo.git("remote", "get-url", "origin").strip()
        url = repo._origin_url
    if not url or not _is_github_https(url):
        return None
    return f"{url.rstrip('/')}/git-upload-pack"


def _ls_remote_refs(repo: GitRepo) -> RemoteRefs:
    output = repo.git(
        "ls-remote",
        "--refs",
        "origin",
        "refs/pull/*/head",
        "refs/heads/*",
        timeout=_LS_REMOTE_TIMEOUT,
    )
    pr_refs: dict[int, str] = {}
    head_refs: dict[str, str] = {}
    for line in output.splitlines():
        sha, _, name = line.partition("\t")
        if sha and name:
            _register_ref(pr_refs, head_refs, sha, name)
    return RemoteRefs(pr_refs=pr_refs, head_refs=head_refs)


def remote_refs(repo: GitRepo) -> RemoteRefs:
    """List pull and head refs, preferring one keep-alive HTTP ls-refs request.

    A 401/404 means the repository is gone and must stay visible to
    ``classify_git_failure`` as dead; every other failure falls back to
    ``git ls-remote`` so callers keep today's behaviour on odd servers.
    """
    if repo._remote_refs_cache is not None:
        return repo._remote_refs_cache
    try:
        url = _upload_pack_url(repo)
    except (GitError, subprocess.TimeoutExpired):
        url = None
    if url is None:
        refs = _ls_remote_refs(repo)
    else:
        try:
            refs = _ls_refs_http(url)
        except GitError:
            raise
        except Exception:
            refs = _ls_remote_refs(repo)
    repo._remote_refs_cache = refs
    return refs


def remote_refs_for(full_name: str) -> RemoteRefs:
    """ls-refs without a clone; used by the scheduler pre-probe.

    Dead repositories raise the same dead ``GitError`` as ``remote_refs``;
    transient failures (transport, server, parse) raise
    ``RemoteRefsUnavailable`` so the caller can submit the repo normally.
    """
    url = f"https://github.com/{full_name}.git/git-upload-pack"
    try:
        return _ls_refs_http(url)
    except GitError:
        raise
    except Exception as exc:
        raise RemoteRefsUnavailable(f"ls-refs failed for {full_name}: {exc}") from exc


def remote_pr_refs(repo: GitRepo) -> dict[int, str]:
    return remote_refs(repo).pr_refs


def write_pr_refs_snapshot(repo: GitRepo, refs: Mapping[int, str]) -> None:
    payload = {
        "version": _PR_SNAPSHOT_VERSION,
        "refs": {str(number): refs[number] for number in sorted(refs)},
    }
    path = Path(repo.dest) / ".git" / _PR_REFS_SNAPSHOT
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_pr_refs_snapshot(repo: GitRepo) -> dict[int, str] | None:
    try:
        payload = json.loads(
            (Path(repo.dest) / ".git" / _PR_REFS_SNAPSHOT).read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != _PR_SNAPSHOT_VERSION:
        return None
    refs = payload.get("refs")
    if not isinstance(refs, dict):
        return None
    snapshot: dict[int, str] = {}
    for number, sha in refs.items():
        if (
            not isinstance(number, str)
            or not number.isdigit()
            or not isinstance(sha, str)
            or not sha
        ):
            return None
        snapshot[int(number)] = sha
    return snapshot


def _acquire_gate(gate: object, *, blocking: bool = True) -> bool:
    """Acquire a fleet gate permit without ignoring a cancelled run.

    ``gate.acquire()`` blocks untended, so a cancelled scan would wait for a
    monster fetch to drain before noticing. Poll in short slices instead and
    check cancellation between them; ``blocking=False`` makes one immediate
    attempt for a caller-owned reservation lane.
    """
    timeout = _GATE_POLL_SECONDS if blocking else 0.0
    while True:
        if gate.acquire(timeout=timeout):
            return True
        if not blocking:
            return False
        cancellation.check()


def fetch_pr_refs(
    repo: GitRepo,
    *,
    depth: int,
    chunk_refs: int | None = None,
    gate: object | None = None,
    refs: Mapping[int, str] | None = None,
    gate_reserved: bool = False,
) -> dict[int, str]:
    # Size the ref set first, then request exactly those refs in bounded
    # chunks. Destination-less refspecs ride --stdin (off the argv ceiling);
    # tree:0 keeps the pack to commit metadata, no-write-fetch-head leaves no
    # ref files behind, and lazy fetching is disabled for the command only so
    # a stalled promisor round trip cannot wedge a chunk. Monster ref sets
    # take the fleet gate one chunk at a time — never across the whole repo —
    # so a wave of giants cannot saturate the link at once and a cancelled
    # wait is noticed between polls; ordinary repos never touch it. Callers
    # that already listed the refs pass them via ``refs`` to skip the round
    # trip entirely; callers that already hold a fleet permit pass
    # ``gate_reserved=True`` so the fetch neither acquires nor releases it.
    if chunk_refs is None:
        chunk_refs = _PR_FETCH_CHUNK_REFS
    remote = dict(refs) if refs is not None else remote_refs(repo).pr_refs
    if not remote:
        # A kept clone must never resume from refs the remote no longer has.
        with contextlib.suppress(OSError):
            (Path(repo.dest) / ".git" / _PR_REFS_SNAPSHOT).unlink()
        return {}
    gated = gate is not None and not gate_reserved and len(remote) > _MONSTER_PR_THRESHOLD
    for numbers in chunked(sorted(remote), chunk_refs):
        if gated:
            _acquire_gate(gate)
        try:
            request = "".join(f"refs/pull/{number}/head\n" for number in numbers)
            handle = tempfile.NamedTemporaryFile("wb", delete=False, suffix=".git-refspecs")
            try:
                handle.write(request.encode("ascii"))
                handle.close()
                with open(handle.name, "rb") as stdin:
                    repo.git(
                        "fetch",
                        "--quiet",
                        "--depth",
                        str(depth),
                        "--filter=tree:0",
                        "--no-tags",
                        "--no-write-fetch-head",
                        "--recurse-submodules=no",
                        "origin",
                        "--stdin",
                        stdin=stdin,
                        timeout=_PR_CHUNK_TIMEOUT,
                        env_extra={"GIT_NO_LAZY_FETCH": "1"},
                    )
            finally:
                with contextlib.suppress(OSError):
                    os.unlink(handle.name)
        finally:
            if gated:
                gate.release()
    try:
        write_pr_refs_snapshot(repo, remote)
    except OSError:
        # The snapshot only aids a later resume; failing to persist it must
        # not sink a fetch whose objects are already in place.
        pass
    return remote


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


def walk_pr_shas(
    repo: GitRepo,
    refs: Mapping[int, str],
    *,
    depth: int,
    workers: int = 1,
    pool: object | None = None,
) -> dict[int, tuple[str, ...]]:
    """Compatibility shim; walks now run in-process via detect.repo_walk.

    ``workers`` and ``pool`` are accepted for callers from the spawn era and
    are ignored: the batched walker needs neither.
    """
    from detect.repo_walk import walk_windows

    return walk_windows(repo, refs, depth=depth)


def read_commits(repo: GitRepo, shas: Sequence[str]) -> dict[str, CommitRecord]:
    # `git show` resolves each commit's tree (the diff machinery), which on a
    # --filter=tree:0 fetch means one lazy-fetch round trip per commit. Plain
    # `log --no-walk` reads commit objects only, so it stays local and exact.
    records: dict[str, CommitRecord] = {}
    for batch in chunked(list(shas), _SHOW_BATCH):
        output = repo.git(
            "log",
            "--no-walk",
            f"--format={LOG_FORMAT}",
            *batch,
            env_extra={"GIT_NO_LAZY_FETCH": "1"},
        )
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
