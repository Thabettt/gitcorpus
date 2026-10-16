from __future__ import annotations

import os
import re
import subprocess
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from lib import cancellation
from lib.batching import chunked

_CANCEL_POLL = 0.1
_STDERR_LIMIT = 200
LOG_FORMAT = "%H%x1f%an%x1f%ae%x1f%cn%x1f%ce%x1f%cI%x1f%B%x1e"
_UNIT = "\x1f"
_RECORD = "\x1e"
_MERGE_PR = re.compile(r"Merge pull request #(?P<pr>\d+) from (?P<owner>[^/\s]+)/(?P<head>\S+)")
_MERGE_LOCAL = re.compile(r"Merge branch '(?P<head>[^']+)'")
_SHOW_BATCH = 200


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
    return env


def _terminate(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate()


def run_git(argv: Sequence[str], *, cwd: Path | str, timeout: float | None = None) -> str:
    process = subprocess.Popen(
        ["git", *argv],
        cwd=str(cwd),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=git_env(),
        text=True,
        encoding="utf-8",
        errors="replace",
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
        raise GitError(["git", *argv], process.returncode, stderr or "")
    return stdout or ""


@dataclass
class GitRepo:
    dest: Path
    timeout: float | None = None

    def git(self, *args: str) -> str:
        return run_git(args, cwd=self.dest, timeout=self.timeout)


def clone_lean(full_name: str, dest: Path, *, depth: int, timeout: float | None = None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    run_git(
        [
            "clone",
            "--quiet",
            "--single-branch",
            "--no-checkout",
            f"--depth={depth}",
            "--filter=blob:none",
            f"https://github.com/{full_name}.git",
            str(dest),
        ],
        cwd=dest.parent,
        timeout=timeout,
    )


def list_tree(repo: GitRepo) -> tuple[str, ...]:
    output = repo.git("ls-tree", "-r", "--name-only", "HEAD")
    return tuple(line for line in output.splitlines() if line)


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
    output = repo.git("log", "-n", str(limit), f"--format={LOG_FORMAT}", "HEAD")
    return parse_log(output)


def fetch_pr_refs(repo: GitRepo, *, depth: int) -> None:
    repo.git(
        "fetch",
        "--quiet",
        "--depth",
        str(depth),
        "--filter=tree:0",
        "--no-tags",
        "origin",
        "+refs/pull/*/head:refs/gc/pr/*",
    )


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
    repo: GitRepo, refs: Mapping[int, str], *, depth: int
) -> dict[int, tuple[str, ...]]:
    walks: dict[int, tuple[str, ...]] = {}
    for number, sha in sorted(refs.items()):
        output = repo.git("rev-list", "-n", str(depth), sha)
        walks[number] = tuple(line for line in output.splitlines() if line)
    return walks


def read_commits(repo: GitRepo, shas: Sequence[str]) -> dict[str, CommitRecord]:
    records: dict[str, CommitRecord] = {}
    for batch in chunked(list(shas), _SHOW_BATCH):
        output = repo.git("show", "-s", f"--format={LOG_FORMAT}", *batch)
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
