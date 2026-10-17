# Fast, Zero-Loss Git Detection — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make git-mode detection reach the fastest achievable speed with byte-identical evidence — eliminating the `tree:0` repair storm, the per-PR spawn storm, and all permanent repo-loss failure paths.

**Architecture:** One-line transport fix (`--filter=tree:0` → `--filter=blob:none`); a batched `cat-file --batch` walker replacing per-PR `git rev-list` spawns (exact set semantics, spawn fallback, verify-sample self-healing); failure taxonomy + fleet-wide circuit breaker + post-sweep retry wave; `read_commits` integrity fix; unavailable reporting; environment runbook knobs.

**Tech Stack:** Python 3.12, git CLI, pytest, SQLAlchemy/PostgreSQL, FastAPI templates (Jinja2). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-10-17-fast-zero-loss-detection-design.md`

## Global Constraints

- Python 3.12+, stdlib + existing pinned deps only. No API-mode changes. No PR-count caps, no `--depth` semantics change.
- Line length 100 (ruff E,F,I,UP,B + black). Tests: pytest; unit tests must not require network/DB unless using existing fixtures (`clean_db`, `TEST_DATABASE_URL`).
- Evidence equality is byte-defined: `detection_evidence` rows and `run_items.detection` JSONB must be identical (modulo timestamps) versus run 93 baselines for replayed repos.
- Gates are fail-closed: no production run until Tasks 12's gates pass.
- Existing pinned test expectations that encode the OLD behavior are updated in the same task as the behavior change.
- Commit after every task with a `detect:` prefix message.

## File Structure (created/modified)

| File | Responsibility |
|---|---|
| `src/detect/gitio.py` (modify) | filter fix; askpass env; failure classifier; `retry_call(retryable=...)`; `walk_pr_shas` shim |
| `src/detect/repo_walk.py` (create) | batched walker: cat-file pipe, shallow grafts, ordered walk, fallback, verify sample |
| `src/detect/breaker.py` (create) | `CircuitBreaker` over local or mp-shared values |
| `src/detect/local_channels.py` (modify) | use `walk_windows`; drop walk pool params; `read_commits` partial |
| `src/detect/git_orchestrator.py` (modify) | breaker + retry wave wiring; failure_class; unavailable summary; scan_root; deletion pool |
| `src/detect/orchestrator.py` (modify) | `_failed_scan(..., failure_class=...)` |
| `src/enrich/cloner.py` (modify) | askpass env |
| `src/serve/detect.py` (modify) | `GITCORPUS_CLONES_ROOT`; honest estimator |
| `src/serve/templates/detect_detail.html` (modify) | Unavailable section |
| `src/serve/templates/partials/detect_estimate.html` (modify) | hours display |
| tests + `scripts/verify_walk_equivalence.py`, `scripts/verify_detection_replay.py` (create) | gates |

---

### Task 1: Branch + transport fix (`tree:0` → `blob:none`)

**Files:**
- Modify: `src/detect/gitio.py:350`
- Test: `tests/unit/test_gitio.py:400,433`

**Interfaces:**
- Consumes: nothing.
- Produces: unchanged public API; fetch argv now uses `--filter=blob:none`.

- [ ] **Step 1: Create the feature branch**

```bash
git checkout -b detect-fast-zero-loss
git log --oneline -3
```

- [ ] **Step 2: Update the pinned tests to the new expectation (they must fail after the fix)**

In `tests/unit/test_gitio.py`, in `test_fetch_pr_refs_requests_the_ls_remote_snapshot_explicitly` replace `"--filter=tree:0",` with `"--filter=blob:none",`; in `test_fetch_pr_refs_chunks_large_ref_sets` replace the final assertion:

```python
    assert all("--depth" in call and "--filter=blob:none" in call for call in fetches)
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/unit/test_gitio.py -q -k fetch_pr_refs`
Expected: 2 failures showing `--filter=tree:0` in the actual argv.

- [ ] **Step 4: Apply the one-line fix**

In `src/detect/gitio.py` inside `fetch_pr_refs` replace the line:

```python
            "--filter=tree:0",
```

with:

```python
            "--filter=blob:none",
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/unit/test_gitio.py -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/detect/gitio.py tests/unit/test_gitio.py
git commit -m "detect: fetch PR refs with blob:none (tree:0 caused promisor repair storms)"
```

---

### Task 2: Askpass hardening + failure classifier (C3 part 1)

**Files:**
- Modify: `src/detect/gitio.py` (`git_env`, new `classify_git_failure`)
- Modify: `src/enrich/cloner.py:176-181` (`_git_env`)
- Test: `tests/unit/test_gitio.py`, `tests/unit/test_cloner.py`

**Interfaces:**
- Produces: `classify_git_failure(exc: BaseException) -> str` in `"dead" | "transient" | "local" | "fatal"`; `git_env()`/`_git_env()` include `GIT_ASKPASS == ""` and `SSH_ASKPASS == ""`.

- [ ] **Step 1: Write failing tests**

In `tests/unit/test_gitio.py` extend `test_git_env_disables_maintenance_and_optional_locks` with:

```python
    assert env["GIT_ASKPASS"] == ""
    assert env["SSH_ASKPASS"] == ""
    assert env["GIT_TERMINAL_PROMPT"] == "0"
```

Append new tests at the end of `tests/unit/test_gitio.py`:

```python
@pytest.mark.parametrize(
    ("stderr", "expected"),
    [
        ("fatal: repository 'https://github.com/o/r/' not found", "dead"),
        ("fatal: could not read Username for 'https://github.com': terminal prompts disabled", "dead"),
        ("fatal: Authentication failed for 'https://github.com/o/r.git/'", "dead"),
        ("fatal: unable to access 'https://github.com/o/r.git/': Could not resolve host: github.com", "transient"),
        ("fatal: unable to access 'https://github.com/o/r.git/': Failed to connect to github.com port 443", "transient"),
        ("error: RPC failed; curl 56 Recv failure: Connection was reset", "transient"),
        ("fatal: unable to access 'https://github.com/o/r.git/': Operation timed out", "transient"),
        ("fatal: unable to access 'https://github.com/o/r.git/': The requested URL returned error: 502", "transient"),
        ("fatal: Unable to create '.../.git/index.lock': File exists", "local"),
        ("fatal: destination path 'x' already exists and is not an empty directory", "local"),
        ("something unexpected happened", "fatal"),
    ],
)
def test_classify_git_failure_table(stderr, expected):
    assert gitio.classify_git_failure(GitError(["git", "clone"], 128, stderr)) == expected


def test_classify_git_failure_reads_timeouts_as_transient():
    assert gitio.classify_git_failure(subprocess.TimeoutExpired(["git", "fetch"], 600)) == "transient"
```

In `tests/unit/test_cloner.py` add (match the file's existing import style; it already imports from `enrich.cloner`):

```python
def test_cloner_git_env_disables_askpass_prompts():
    from enrich.cloner import _git_env

    env = _git_env()
    assert env["GIT_ASKPASS"] == ""
    assert env["SSH_ASKPASS"] == ""
    assert env["GIT_TERMINAL_PROMPT"] == "0"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python -m pytest tests/unit/test_gitio.py tests/unit/test_cloner.py -q -k "env or classify"`
Expected: FAIL (`GIT_ASKPASS` missing; `classify_git_failure` undefined).

- [ ] **Step 3: Implement**

In `src/detect/gitio.py` add to `git_env()` after `GIT_OPTIONAL_LOCKS`:

```python
    # Never let git surface an askpass dialog: empty values are skipped by git,
    # and GIT_TERMINAL_PROMPT=0 blocks the terminal fallback, so auth-required
    # operations fail fast and clean instead of blocking a scan worker.
    env["GIT_ASKPASS"] = ""
    env["SSH_ASKPASS"] = ""
```

Add after `git_error_tail`:

```python
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
```

In `src/enrich/cloner.py` `_git_env()` add the same two lines after `GIT_TERMINAL_PROMPT`:

```python
    env["GIT_ASKPASS"] = ""
    env["SSH_ASKPASS"] = ""
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python -m pytest tests/unit/test_gitio.py tests/unit/test_cloner.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/detect/gitio.py src/enrich/cloner.py tests/unit/test_gitio.py tests/unit/test_cloner.py
git commit -m "detect: classify git failures and disable askpass dialogs"
```

---

### Task 3: `retry_call(retryable=...)` + CircuitBreaker module (C3 part 2)

**Files:**
- Modify: `src/detect/gitio.py` (`retry_call`)
- Create: `src/detect/breaker.py`
- Test: `tests/unit/test_gitio.py`, `tests/unit/test_breaker.py` (create)

**Interfaces:**
- Produces: `retry_call(fn, *, attempts=4, base_delay=1.0, sleep=..., jitter=..., retryable: Callable[[BaseException], bool] | None = None)` — when `retryable` returns False the first failure re-raises immediately. `breaker.CircuitBreaker(consecutive, trips, cooldown_until, *, trip_after=5, base_cooldown=30.0, max_cooldown=600.0, clock=time.monotonic, sleep=time.sleep)` with `record_success()`, `record_failure()`, `wait_if_open()`; `breaker.local_values()`; consumers create mp values with their own context.

- [ ] **Step 1: Write failing tests**

In `tests/unit/test_gitio.py` append:

```python
def test_retry_call_skips_retries_when_the_failure_is_not_retryable():
    calls: list[int] = []
    sleeps: list[float] = []

    def failing() -> str:
        calls.append(1)
        raise GitError(["git", "clone"], 128, "fatal: repository not found")

    with pytest.raises(GitError):
        retry_call(
            failing,
            attempts=4,
            base_delay=1.0,
            sleep=sleeps.append,
            jitter=lambda: 0.0,
            retryable=lambda exc: classify_git_failure(exc) != "dead",
        )
    assert len(calls) == 1
    assert sleeps == []
```

Create `tests/unit/test_breaker.py`:

```python
from __future__ import annotations

import pytest

from detect.breaker import CircuitBreaker, local_values
from lib.cancellation import RunCancelled


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make(clock, sleeps, **overrides):
    return CircuitBreaker(
        *local_values(),
        trip_after=3,
        base_cooldown=10.0,
        max_cooldown=40.0,
        clock=clock,
        sleep=sleeps.append,
        **overrides,
    )


def test_breaker_does_not_pause_below_the_threshold():
    clock, sleeps = FakeClock(), []
    breaker = make(clock, sleeps)
    breaker.record_failure()
    breaker.record_failure()
    breaker.wait_if_open()
    assert sleeps == []


def test_breaker_trips_after_consecutive_failures_and_escalates():
    clock, sleeps = FakeClock(), []

    def advancing_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    breaker = CircuitBreaker(
        *local_values(),
        trip_after=3,
        base_cooldown=10.0,
        max_cooldown=40.0,
        clock=clock,
        sleep=advancing_sleep,
    )
    breaker.record_failure()
    breaker.record_failure()
    breaker.wait_if_open()  # below threshold: no pause
    assert sleeps == []
    breaker.record_failure()  # trips: first cooldown = 10s
    breaker.wait_if_open()
    assert abs(sum(sleeps) - 10.0) < 0.6
    before_escalation = len(sleeps)
    breaker.record_failure()  # 4th consecutive: escalate to 20s
    breaker.wait_if_open()
    assert abs(sum(sleeps[before_escalation:]) - 20.0) < 1.2


def test_breaker_success_resets_everything():
    clock, sleeps = FakeClock(), []
    breaker = make(clock, sleeps)
    breaker.record_failure()
    breaker.record_failure()
    breaker.record_success()
    breaker.record_failure()
    breaker.wait_if_open()
    assert sleeps == []


def test_breaker_wait_is_interruptible_by_cancellation():
    from lib import cancellation

    clock, sleeps = FakeClock(), []
    breaker = make(clock, sleeps)
    for _ in range(3):
        breaker.record_failure()
    token = cancellation.bind(lambda: True)
    try:
        with pytest.raises(RunCancelled):
            breaker.wait_if_open()
    finally:
        cancellation.reset(token)


def test_breaker_wait_sleeps_until_the_cooldown_expires():
    clock, sleeps = FakeClock(), []

    def advancing_sleep(seconds: float) -> None:
        sleeps.append(seconds)
        clock.now += seconds

    breaker = CircuitBreaker(
        *local_values(), trip_after=1, base_cooldown=5.0, clock=clock, sleep=advancing_sleep
    )
    breaker.record_failure()
    breaker.wait_if_open()
    assert clock.now >= 1005.0
    assert sleeps  # it actually waited
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python -m pytest tests/unit/test_gitio.py tests/unit/test_breaker.py -q`
Expected: FAIL (`retryable` kwarg + module missing).

- [ ] **Step 3: Implement**

In `src/detect/gitio.py`, extend `retry_call`:

```python
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
```

Create `src/detect/breaker.py`:

```python
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from lib import cancellation


class Value(Protocol):
    value: float


class _LocalValue:
    def __init__(self, initial: float = 0.0) -> None:
        self.value = initial


def local_values() -> tuple[Value, Value, Value]:
    """Three plain slots for single-process use (tests, threads path)."""
    return _LocalValue(), _LocalValue(), _LocalValue()


def _increment(value: Value) -> float:
    lock_factory = getattr(value, "get_lock", None)
    if lock_factory is None:
        value.value += 1
        return value.value
    with lock_factory():
        value.value += 1
        return value.value


class CircuitBreaker:
    """Fleet-wide pause when consecutive transient failures cross a threshold.

    Shared across scan processes by passing ``multiprocessing`` values created
    from the same context; ``time.monotonic`` is machine-wide on supported
    platforms so a cooldown deadline written by one process gates all of them.
    """

    def __init__(
        self,
        consecutive: Value,
        trips: Value,
        cooldown_until: Value,
        *,
        trip_after: int = 5,
        base_cooldown: float = 30.0,
        max_cooldown: float = 600.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._consecutive = consecutive
        self._trips = trips
        self._cooldown_until = cooldown_until
        self._trip_after = trip_after
        self._base_cooldown = base_cooldown
        self._max_cooldown = max_cooldown
        self._clock = clock
        self._sleep = sleep

    def record_success(self) -> None:
        self._consecutive.value = 0
        self._trips.value = 0
        self._cooldown_until.value = 0.0

    def record_failure(self) -> None:
        count = _increment(self._consecutive)
        if count < self._trip_after:
            return
        trips = _increment(self._trips)
        cooldown = min(self._base_cooldown * (2 ** (trips - 1)), self._max_cooldown)
        self._cooldown_until.value = self._clock() + cooldown

    def wait_if_open(self) -> None:
        while True:
            remaining = self._cooldown_until.value - self._clock()
            if remaining <= 0:
                return
            cancellation.check()
            self._sleep(min(0.5, remaining))
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python -m pytest tests/unit/test_gitio.py tests/unit/test_breaker.py -q`
Expected: all pass. (`test_breaker_trips_after_consecutive_failures_and_escalates` sums sleeps over at most 40 s — with `wait_if_open` sleeping `min(0.5, remaining)` against a fake clock, `advancing_sleep` is only wired in the dedicated test; here `sleeps.append` records 0.5 increments, so assert `sum(sleeps) >= 10.0` requires the fake clock to advance — pass `sleep` that advances in this test by wiring `advancing_sleep` too.)

- [ ] **Step 5: Commit**

```bash
git add src/detect/gitio.py src/detect/breaker.py tests/unit/test_gitio.py tests/unit/test_breaker.py
git commit -m "detect: add retryable retries and a fleet-wide circuit breaker"
```

---

### Task 4: Wire breaker, retry wave, and failure classes into git detection (C3 part 3)

**Files:**
- Modify: `src/detect/git_orchestrator.py`
- Modify: `src/detect/orchestrator.py` (`_failed_scan`)
- Test: `tests/unit/test_git_orchestrator.py`

**Interfaces:**
- Consumes: `gitio.classify_git_failure`, `gitio.retry_call(retryable=...)`, `breaker.CircuitBreaker`.
- Produces: `_failed_scan(candidate, exc, *, failure_class=None)`; failed docs carry `failure_class`; transient failures get one post-sweep retry in both scheduler paths.

- [ ] **Step 1: Write failing tests**

Append to `tests/unit/test_git_orchestrator.py`:

```python
def test_dead_repo_fails_fast_without_retries(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )
    attempts: list[str] = []

    def clone(full_name: str, dest: Path) -> None:
        attempts.append(full_name)
        if full_name == "octo/two":
            raise GitError(["git", "clone"], 128, "fatal: repository 'https://github.com/octo/two/' not found")
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1, retry_delay=0.0),
        clone_fn=clone,
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )
    assert attempts.count("octo/two") == 1  # dead class: no inline retries
    reasons = payload.result_summary["unavailable_reasons"]
    assert reasons == {"dead": 1}
    entry = payload.result_summary["unavailable_repos"][0]
    assert entry["full_name"] == "octo/two" and entry["reason"] == "dead"


def test_transient_failure_gets_one_post_sweep_retry(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )
    attempts: list[str] = []

    def clone(full_name: str, dest: Path) -> None:
        attempts.append(full_name)
        if full_name == "octo/two" and attempts.count("octo/two") == 1:
            raise GitError(["git", "clone"], 128, "fatal: unable to access 'x': Could not resolve host: github.com")
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(
            scan_root=str(tmp_path / "clones"), workers=1, attempts=1, retry_delay=0.0
        ),
        clone_fn=clone,
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )
    assert attempts.count("octo/two") == 2  # first try + retry wave
    assert payload.result_summary["repos_unavailable"] == 0
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python -m pytest tests/unit/test_git_orchestrator.py -q -k "dead_repo or post_sweep"`
Expected: FAIL (`unavailable_reasons` key missing; `octo/two` attempted once with inline retries).

- [ ] **Step 3: Implement**

In `src/detect/orchestrator.py` update `_failed_scan`:

```python
def _failed_scan(
    candidate: Mapping, exc: Exception, *, failure_class: str | None = None
) -> _RepoScan:
    note = f"{type(exc).__name__}: {exc}"
    if len(note) > _FAILURE_NOTE_LIMIT:
        note = note[:_FAILURE_NOTE_LIMIT]
    return _RepoScan(
        repo_id=int(candidate["repo_id"]),
        full_name=str(candidate["full_name"]),
        stargazers=candidate["stargazers"],
        hits=[],
        results={},
        pr_result=None,
        history_stats={},
        document={
            "agents": [],
            "channels": {},
            "unavailable": True,
            "failure_class": failure_class,
            "first_signal_at": None,
            "commit_ratio": None,
            "adoption_level": "none",
            "notes": [note],
        },
    )
```

In `src/detect/git_orchestrator.py`:

1. imports: `from detect.gitio import GitRepo, classify_git_failure, clone_lean, retry_call` and
   `from detect.breaker import CircuitBreaker, local_values`.
2. `_scan_one` clone call gains the dead-class retry gate:

```python
        retry_call(
            clone_attempt,
            attempts=cfg.attempts,
            base_delay=cfg.retry_delay,
            retryable=lambda exc: classify_git_failure(exc) != "dead",
        )
```

3. `_scan_worker_main` gains `breaker_values: tuple` in its args; build the breaker once:

```python
    breaker = CircuitBreaker(*breaker_values)
```

   Scheduling loop: add `breaker.wait_if_open()` as the first statement of the inner
   `while not exhausted and len(in_flight) < threads:` loop, add `retry_candidates: list[Mapping] = []`
   and `wave = 1` before `pending = iter(slice_candidates)`, and replace the pending-exhaustion branch:

```python
                candidate = next(pending, None)
                if candidate is None:
                    if wave == 1 and retry_candidates:
                        wave = 2
                        pending = iter(retry_candidates)
                        retry_candidates = []
                        continue
                    exhausted = True
                    break
```

   Result handling branch:

```python
            try:
                scan = future.result()
            except RunCancelled:
                raise
            except Exception as exc:
                failure_class = classify_git_failure(exc)
                if failure_class == "transient":
                    breaker.record_failure()
                    if wave == 1:
                        retry_candidates.append(candidate)
                scan = _failed_scan(candidate, exc, failure_class=failure_class)
                failure = f"{scan.full_name}: {scan.document['notes'][0]}"
            else:
                breaker.record_success()
```

4. `_run_git_detection_processes`: create shared values from the spawn context and pass them:

```python
    breaker_values = (
        mp_context.Value("d", 0.0),
        mp_context.Value("d", 0.0),
        mp_context.Value("d", 0.0),
    )
```
   (add `breaker_values` to the `args=` tuple; move its creation before the worker loop.)

5. Single-process path in `run_git_detection`: build `breaker = CircuitBreaker(*local_values())`, add
   `breaker.wait_if_open()` at the top of its scheduling loop, mirror the `wave`/`retry_candidates`
   logic inside `scan_repo` handling (on `future.result()` exception: classify, record, append when
   `wave == 1`; on success: `record_success()`), and reset `pending`/`exhausted` exactly as in the mp path.

6. Retry-wave dedupe: a retried repo produces a failed scan message and later a successful one, so
   `scans` can hold both. Immediately before `summary = _summary(scans, spec, pack)` in
   `run_git_detection`, collapse duplicates keeping the last attempt:

```python
    by_repo: dict[int, _RepoScan] = {}
    for scan in scans:
        by_repo[scan.repo_id] = scan
    scans = [by_repo[key] for key in sorted(by_repo)]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python -m pytest tests/unit/test_git_orchestrator.py tests/unit/test_breaker.py -q`
Expected: all pass, including the pre-existing retry test (`connection reset` is transient → inline retries unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/detect/git_orchestrator.py src/detect/orchestrator.py tests/unit/test_git_orchestrator.py
git commit -m "detect: classify failures, gate retries, add fleet-wide breaker and retry wave"
```

---

### Task 5: `read_commits` integrity fix (C4)

**Files:**
- Modify: `src/detect/local_channels.py:209-211`
- Test: `tests/unit/test_detect_local_channels.py`

**Interfaces:**
- Produces: `detect_pr_commits_local` returns `partial` with `note="commit read failed: ..."` when
  commit reads fail — never empty-evidence `ok`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_detect_local_channels.py`:

```python
def test_detect_pr_commits_local_reports_a_commit_read_failure_as_partial():
    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "for-each-ref":
            return "refs/gc/pr/7 aaa\n"
        if args[0] == "rev-list":
            return "s1\n"
        if args[0] == "log":
            raise GitError(list(args), 128, "fatal: bad object")
        return None

    result = detect_pr_commits_local(FakeRepo(handler), PACK, retry_delay=0.0)
    assert result.status == "partial"
    assert result.note == "commit read failed: fatal: bad object"
    assert result.stats["propagated_oids"] == ()
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv\Scripts\python -m pytest tests/unit/test_detect_local_channels.py -q -k commit_read`
Expected: FAIL (status is `ok`).

- [ ] **Step 3: Implement**

In `src/detect/local_channels.py` replace:

```python
    try:
        records = read_commits(repo, sorted(sha_to_pr))
    except GitError:
        records = {}
```

with:

```python
    try:
        records = read_commits(repo, sorted(sha_to_pr))
    except _GIT_FAILURES as exc:
        return ChannelResult(
            status="partial",
            note=f"commit read failed: {git_error_tail(exc)}",
            stats=empty_stats,
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python -m pytest tests/unit/test_detect_local_channels.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/detect/local_channels.py tests/unit/test_detect_local_channels.py
git commit -m "detect: surface PR commit-read failures as partial instead of empty ok"
```

---

### Task 6: Unavailable reporting (C5)

**Files:**
- Modify: `src/detect/git_orchestrator.py` (`run_git_detection` summary)
- Modify: `src/serve/templates/detect_detail.html`
- Test: `tests/unit/test_git_orchestrator.py`, golden suite

**Interfaces:**
- Produces: `result_summary["unavailable_repos"] = [{"full_name","reason"}]` sorted by name;
  `result_summary["unavailable_reasons"] = {"<class>": count}`; template section keyed off
  `detection.summary.unavailable_reasons`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_git_orchestrator.py`:

```python
def test_unavailable_repos_listed_with_reasons(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )

    def clone(full_name: str, dest: Path) -> None:
        if full_name == "octo/two":
            raise RuntimeError("clone failed")
        dest.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)
    payload = run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1, attempts=1, retry_delay=0.0),
        clone_fn=clone,
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )
    assert payload.result_summary["unavailable_repos"] == [
        {"full_name": "octo/two", "reason": "fatal"}
    ]
    assert payload.result_summary["unavailable_reasons"] == {"fatal": 1}
```

- [ ] **Step 2: Run test to verify failure**

Run: `.venv\Scripts\python -m pytest tests/unit/test_git_orchestrator.py -q -k unavailable_repos_listed`
Expected: FAIL (KeyError `unavailable_repos`).

- [ ] **Step 3: Implement the summary in `run_git_detection`**

Before `warnings.extend(failures)`:

```python
    unavailable = sorted(
        (
            {
                "full_name": scan.full_name,
                "reason": scan.document.get("failure_class") or "channel_unavailable",
            }
            for scan in scans
            if scan.document.get("unavailable")
        ),
        key=lambda row: row["full_name"],
    )
    reasons: dict[str, int] = {}
    for entry in unavailable:
        reasons[entry["reason"]] = reasons.get(entry["reason"], 0) + 1
    summary["unavailable_repos"] = unavailable
    summary["unavailable_reasons"] = dict(sorted(reasons.items()))
```

- [ ] **Step 4: Add the template section**

In `src/serve/templates/detect_detail.html`, immediately before `<div id="detection-filters" class="filter-row">`:

```html
  {% if detection.summary.unavailable_reasons %}
  <details class="evidence-repo" id="detection-unavailable">
    <summary>Unavailable repos · {{ detection.summary.unavailable_repos | length }}</summary>
    <div class="evidence-body">
      <p class="muted">
        {% for reason, count in detection.summary.unavailable_reasons.items() %}{{ reason }}: {{ count }}{% if not loop.last %} · {% endif %}{% endfor %}
      </p>
      <ul class="muted">
        {% for entry in detection.summary.unavailable_repos[:200] %}<li>{{ entry.full_name }} — {{ entry.reason }}</li>{% endfor %}
      </ul>
    </div>
  </details>
  {% endif %}
```

- [ ] **Step 5: Run tests + goldens**

Run: `.venv\Scripts\python -m pytest tests/unit/test_git_orchestrator.py tests/golden -q`
If a golden detect-detail snapshot fails because of the new section, regenerate deliberately:
`$env:UPDATE_GOLDEN="1"; .venv\Scripts\python -m pytest tests/golden -q` then `git diff` the snapshot to confirm only the additive section changed.

- [ ] **Step 6: Commit**

```bash
git add src/detect/git_orchestrator.py src/serve/templates/detect_detail.html tests/unit/test_git_orchestrator.py tests/golden
git commit -m "detect: list unavailable repos with machine-readable reasons in the run summary"
```

---

### Task 7: The batched walker — `src/detect/repo_walk.py` (C2 part 1)

**Files:**
- Create: `src/detect/repo_walk.py`
- Test: `tests/unit/test_repo_walk.py` (create)

**Interfaces:**
- Consumes: `gitio.GitRepo`, `gitio.git_env`, `lib.cancellation`.
- Produces: `walk_windows(repo: GitRepo, refs: Mapping[int, str], *, depth: int) -> dict[int, tuple[str, ...]]`;
  `verification_summary() -> {"checked": int, "mismatches": int, "disabled": bool}`; `reset_verification()`;
  `WalkAnomaly`. Env `GITCORPUS_WALK_VERIFY_PCT` (default 0, clamped 0–100, at most 2 spawns per call;
  exhausted-before-depth walks are exempt, since they are exact regardless of ordering). Order-dependent
  walks are verify-sampled, mismatches are substituted with the true result, and after 3 mismatches the
  process permanently falls back to spawns.

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_repo_walk.py`:

```python
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from detect.gitio import GitError, GitRepo
from detect.repo_walk import reset_verification, verification_summary, walk_windows

needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Jane",
    "GIT_AUTHOR_EMAIL": "jane@example.com",
    "GIT_COMMITTER_NAME": "Jane",
    "GIT_COMMITTER_EMAIL": "jane@example.com",
}


def _commit(dest: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=dest, check=True, env=ENV)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=dest, check=True, env=ENV)


def _repo(tmp_path: Path, commits: int) -> Path:
    dest = tmp_path / "r"
    dest.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=dest, check=True, env=ENV)
    for index in range(commits):
        (dest / "f.txt").write_text(f"{index}\n", encoding="utf-8")
        _commit(dest, f"feat: c{index}")
    return dest


@needs_git
def test_walk_windows_matches_rev_list_exactly(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 30)
    heads = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest, check=True, env=ENV, capture_output=True, text=True
    ).stdout.strip()
    refs = {7: heads}
    result = walk_windows(GitRepo(dest), refs, depth=100)
    truth = subprocess.run(
        ["git", "rev-list", "-n", "100", heads], cwd=dest, check=True, env=ENV, capture_output=True, text=True
    ).stdout.split()
    assert set(result[7]) == set(truth)
    assert verification_summary()["mismatches"] == 0


@needs_git
def test_walk_windows_selects_the_same_deep_prefix_as_rev_list(tmp_path, monkeypatch):
    monkeypatch.setenv("GITCORPUS_WALK_VERIFY_PCT", "100")
    reset_verification()
    dest = _repo(tmp_path, 25)
    heads = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=dest, check=True, env=ENV, capture_output=True, text=True
    ).stdout.strip()
    result = walk_windows(GitRepo(dest), {1: heads}, depth=10)
    truth = subprocess.run(
        ["git", "rev-list", "-n", "10", heads], cwd=dest, check=True, env=ENV, capture_output=True, text=True
    ).stdout.split()
    assert result[1] == tuple(truth)


@needs_git
def test_walk_windows_respects_shallow_grafts(tmp_path):
    origin = _repo(tmp_path / "origin", 20)
    clone = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "-q", "--depth", "5", origin.as_uri(), str(clone)], check=True, env=ENV
    )
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=clone, check=True, env=ENV, capture_output=True, text=True
    ).stdout.strip()
    result = walk_windows(GitRepo(clone), {3: head}, depth=100)
    truth = subprocess.run(
        ["git", "rev-list", "-n", "100", head], cwd=clone, check=True, env=ENV, capture_output=True, text=True
    ).stdout.split()
    assert result[3] == tuple(truth)
    assert len(result[3]) == 5  # the graft caps it


def test_walk_windows_falls_back_to_rev_list_without_a_repo(tmp_path):
    class FakeRepo(GitRepo):
        def __init__(self):
            super().__init__(tmp_path / "not-a-repo")

        def git(self, *args, timeout=None, stdin=None):
            assert args[:2] == ("rev-list", "-n")
            return "s1\ns2\n"

    result = walk_windows(FakeRepo(), {9: "aaa"}, depth=100)
    assert result == {9: ("s1", "s2")}


def test_walk_windows_returns_empty_for_no_refs(tmp_path):
    assert walk_windows(GitRepo(tmp_path), {}, depth=100) == {}
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python -m pytest tests/unit/test_repo_walk.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `src/detect/repo_walk.py`**

```python
from __future__ import annotations

import contextlib
import heapq
import os
import random
import re
import subprocess
from collections.abc import Mapping, Sequence
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
        self._process = subprocess.Popen(
            ["git", "cat-file", "--batch"],
            cwd=str(dest),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=git_env(),
        )

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
        if self._process.stdin is not None:
            with contextlib.suppress(OSError, ValueError):
                self._process.stdin.close()
        if self._process.poll() is None:
            self._process.kill()
        with contextlib.suppress(OSError):
            self._process.communicate()


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
        line.strip() for line in shallow_file.read_text(encoding="utf-8").splitlines() if line.strip()
    )


def _verify(repo: GitRepo, sha: str, depth: int, shas: tuple[str, ...], pct: int) -> tuple[str, ...]:
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
            cat = CatFileBatch(Path(repo.dest))
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
```

Note: `Sequence` import is unused — drop it while implementing (ruff will flag).

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python -m pytest tests/unit/test_repo_walk.py -q`
Expected: all pass. If the deep-prefix test mismatches, stop and debug the ordering against
`git rev-list` before proceeding — do not weaken the assertion.

- [ ] **Step 5: Commit**

```bash
git add src/detect/repo_walk.py tests/unit/test_repo_walk.py
git commit -m "detect: batched cat-file walker with exact-order walk, fallback, and verify sampling"
```

---

### Task 8: Integrate the walker, remove the walk pool (C2 part 2)

**Files:**
- Modify: `src/detect/gitio.py` (`walk_pr_shas` shim; remove pool machinery)
- Modify: `src/detect/local_channels.py` (`detect_pr_commits_local` signature + call)
- Modify: `src/detect/git_orchestrator.py` (drop walk_pool plumbing; add walk stats to field_stats)
- Test: `tests/unit/test_gitio.py`, `tests/unit/test_detect_local_channels.py`, `tests/unit/test_git_orchestrator.py`

**Interfaces:**
- Consumes: `repo_walk.walk_windows`.
- Produces: `walk_pr_shas(repo, refs, *, depth, workers=1, pool=None)` shim (params retained for
  compatibility, ignored); `detect_pr_commits_local(repo, pack, agents=None, *, depth=100,
  attempts=4, retry_delay=1.0)`.

- [ ] **Step 1: Update pinned tests to the new contract (they must fail before implementation)**

- `tests/unit/test_gitio.py`: replace `test_walk_pr_shas_reads_each_ref` and
  `test_walk_pr_shas_parallel_matches_sequential` with a single shim test:

```python
def test_walk_pr_shas_delegates_to_the_batched_walker(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        "detect.repo_walk.walk_windows",
        lambda repo, refs, *, depth: calls.append((repo, dict(refs), depth)) or {7: ("s1",)},
    )
    result = walk_pr_shas(FakeRepo(lambda args: None), {7: "aaa"}, depth=5)
    assert result == {7: ("s1",)}
    assert calls and calls[0][2] == 5
```

- `tests/unit/test_detect_local_channels.py`: in
  `test_detect_pr_commits_local_maps_commits_to_prs_and_dedupes`, drop `walk_workers=2` from the call.
  Rewrite its handler so the walk step uses the real walker's fallback (the FakeRepo has no `.git`,
  so `walk_windows` falls back to `repo.git("rev-list", ...)` — keep the existing `rev-list` handler,
  and remove the `for-each-ref` dependency by having `list_pr_refs` still answer as before).
- `tests/unit/test_git_orchestrator.py`: `test_run_git_detection_passes_scan_knobs_to_the_pr_channel`
  — update `fake_pr` signature to `(repo, pack, agents, *, depth, attempts, retry_delay)` and drop
  `walk_workers` from the config + assertions.

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python -m pytest tests/unit/test_gitio.py tests/unit/test_detect_local_channels.py tests/unit/test_git_orchestrator.py -q`
Expected: FAIL/errors on the changed contracts.

- [ ] **Step 3: Implement**

`src/detect/gitio.py` — replace the bodies of `walk_pr_shas` (and drop `_WALK_WORKERS`,
`ThreadPoolExecutor` import and pool branches if no longer used):

```python
def walk_pr_shas(
    repo: GitRepo,
    refs: Mapping[int, str],
    *,
    depth: int,
    workers: int = 1,
    pool: ThreadPoolExecutor | None = None,
) -> dict[int, tuple[str, ...]]:
    """Compatibility shim; walks now run in-process via detect.repo_walk."""
    from detect.repo_walk import walk_windows

    return walk_windows(repo, refs, depth=depth)
```

`src/detect/local_channels.py`:

```python
def detect_pr_commits_local(
    repo: GitRepo,
    pack: Pack,
    agents: frozenset[str] | None = None,
    *,
    depth: int = 100,
    attempts: int = 4,
    retry_delay: float = 1.0,
) -> ChannelResult:
```

and the walk call:

```python
    try:
        walks = walk_windows(repo, refs, depth=depth)
    except _GIT_FAILURES as exc:
        return ChannelResult(
            status="partial",
            note=f"pull refs walk failed: {git_error_tail(exc)}",
            stats=empty_stats,
        )
```

(import `from detect.repo_walk import walk_windows`; keep `from detect.gitio import walk_pr_shas`
removed from imports if unused.)

`src/detect/git_orchestrator.py`:
- `_scan_one` signature: drop `walk_pool`; remove its creation in `_scan_worker_main` and the
  single-process path (`walk_pool = ThreadPoolExecutor(...)` lines and their shutdowns).
- The `detect_pr_commits_local(...)` call drops `walk_workers=cfg.walk_workers, walk_pool=walk_pool`.
- Remove `walk_workers` from `GitScanConfig`.
- `field_stats` in the returned payload:

```python
        field_stats={
            "clone": {
                "depth": cfg.depth,
                "keep": cfg.keep,
                "scanned": len(scans),
                "failures": len(failures),
            },
            "walk": repo_walk.verification_summary(),
        },
```

(import `from detect import repo_walk`.)

- [ ] **Step 4: Run the focused suites**

Run: `.venv\Scripts\python -m pytest tests/unit/test_gitio.py tests/unit/test_detect_local_channels.py tests/unit/test_git_orchestrator.py tests/unit/test_repo_walk.py -q`
Expected: all pass. Also run `ruff check src tests` and `black --check src tests` and fix.

- [ ] **Step 5: Commit**

```bash
git add src/detect/gitio.py src/detect/local_channels.py src/detect/git_orchestrator.py tests/unit
git commit -m "detect: walk PR windows in-process; drop the per-PR rev-list spawns and walk pool"
```

---

### Task 9: Clone-root env + background deletion pool (C6)

**Files:**
- Modify: `src/serve/detect.py` (config build + `detect_clone_root` helper)
- Modify: `src/detect/git_orchestrator.py` (deletion pool)
- Test: `tests/unit/test_detect_runner.py`, `tests/unit/test_git_orchestrator.py`

**Interfaces:**
- Produces: `serve.detect.detect_clone_root() -> str` reading `GITCORPUS_CLONES_ROOT` (default
  `"clones"`); per-repo deletions run on a 2-thread pool that drains before the final sweep.

- [ ] **Step 1: Write failing tests**

In `tests/unit/test_detect_runner.py` append (keep its existing import block conventions):

```python
def test_detect_clone_root_env_override(monkeypatch):
    from serve.detect import detect_clone_root

    monkeypatch.delenv("GITCORPUS_CLONES_ROOT", raising=False)
    assert detect_clone_root() == "clones"
    monkeypatch.setenv("GITCORPUS_CLONES_ROOT", r"D:\gitcrawl-clones")
    assert detect_clone_root() == r"D:\gitcrawl-clones"
```

In `tests/unit/test_git_orchestrator.py` append:

```python
def test_per_repo_deletion_does_not_block_the_parent(clean_db, tmp_path, monkeypatch):
    engine = clean_db()
    source_id = seed_source(engine)
    detect_run = create_run(
        engine, {"kind": "detect"}, api_version="2022-11-28", kind="detect", source_run_id=source_id
    )
    removed: list[str] = []

    from detect.git_orchestrator import _remove_tree as real_remove

    def tracking_remove(path):
        removed.append(str(path))
        real_remove(path)

    monkeypatch.setattr("detect.git_orchestrator._remove_tree", tracking_remove)
    monkeypatch.setattr("detect.git_orchestrator.free_disk_mb", lambda path: 10_000.0)

    def clone(full_name: str, dest: Path) -> None:
        dest.mkdir(parents=True, exist_ok=True)

    run_git_detection(
        engine,
        detect_run,
        make_spec(source_id, frozenset({"file"})),
        PACK,
        config=GitScanConfig(scan_root=str(tmp_path / "clones"), workers=1),
        clone_fn=clone,
        repo_factory=lambda dest: FakeRepo(happy_handler),
    )
    assert len(removed) >= 3  # two per-repo dirs plus the final run-dir sweep
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv\Scripts\python -m pytest tests/unit/test_detect_runner.py -q -k clone_root; .venv\Scripts\python -m pytest tests/unit/test_git_orchestrator.py -q -k not_block`
Expected: first FAILS (helper missing); second passes already (count semantics hold) — keep it as a regression net.

- [ ] **Step 3: Implement**

`src/serve/detect.py` — add near the top (after imports):

```python
def detect_clone_root() -> str:
    return os.environ.get("GITCORPUS_CLONES_ROOT", "clones")
```

(add `import os`; in `build_detect_runner`'s `GitScanConfig(...)` add `scan_root=detect_clone_root(),`).

`src/detect/git_orchestrator.py`:
- In `_run_git_detection_processes`, create `deletion_pool = ThreadPoolExecutor(max_workers=2,
  thread_name_prefix="detect-rm")` at the top; replace `_remove_tree(run_dir / scan.full_name.replace("/", "__"))`
  with `deletion_pool.submit(_remove_tree, run_dir / scan.full_name.replace("/", "__"))`; in `finally`,
  before the final sweep: `deletion_pool.shutdown(wait=True)`, and keep `_remove_tree(run_dir)` after it.
- Single-process path in `run_git_detection`: same pool pattern around its per-scan deletion and
  `shutdown(wait=True)` before its final sweep.

- [ ] **Step 4: Run the suites**

Run: `.venv\Scripts\python -m pytest tests/unit/test_git_orchestrator.py tests/unit/test_detect_runner.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/serve/detect.py src/detect/git_orchestrator.py tests/unit/test_detect_runner.py tests/unit/test_git_orchestrator.py
git commit -m "detect: configurable clones root and non-blocking per-repo deletion"
```

---

### Task 10: Honest estimator (C7)

**Files:**
- Modify: `src/serve/detect.py:683-693`
- Modify: `src/serve/templates/partials/detect_estimate.html`
- Test: `tests/contract/test_detect_pages.py` (adjust if it pins the estimate payload)

**Interfaces:**
- Produces: git estimate keys `hours_low`, `hours_high` (replacing `minutes_low`, `minutes_high`),
  computed as `repos × (4 s … 12 s) / min(workers, 32) / 3600`.

- [ ] **Step 1: Grep for the old keys**

Run: `rg -n "minutes_low|minutes_high" src tests`
Expected: `src/serve/detect.py` + `src/serve/templates/partials/detect_estimate.html` (+ possibly a
contract test). Update every hit as part of this task.

- [ ] **Step 2: Implement the formula**

In `src/serve/detect.py` replace the `git_estimate` dict:

```python
        effective_workers = min(workers, 32)
        git_estimate = {
            "repos": clone_estimate.repos,
            "estimated_mb": round(clone_estimate.estimated_mb, 1),
            "free_mb": round(free_mb, 1),
            "workers": workers,
            "depth": depth,
            "keep": keep,
            "hours_low": round(clone_estimate.repos * 4.0 / effective_workers / 3600.0, 2),
            "hours_high": round(clone_estimate.repos * 12.0 / effective_workers / 3600.0, 2),
            "warnings": list(clone_estimate.warnings),
        }
```

In `src/serve/templates/partials/detect_estimate.html` replace the two `git.minutes_low/high`
references with `git.hours_low`/`git.hours_high` labeled hours (keep surrounding markup style).

- [ ] **Step 3: Run contract + golden suites**

Run: `.venv\Scripts\python -m pytest tests/contract/test_detect_pages.py tests/golden -q`
Regenerate goldens only if the estimate partial snapshot changed: `$env:UPDATE_GOLDEN="1"`, rerun,
`git diff` review.

- [ ] **Step 4: Commit**

```bash
git add src/serve/detect.py src/serve/templates/partials/detect_estimate.html tests
git commit -m "detect: honest git-mode estimate in hours instead of clone-MB minutes"
```

---

### Task 11: Docs + runbook

**Files:**
- Modify: `README.md` (env table + runbook note)
- Modify: `docs/superpowers/plans/2026-10-17-run93-live-evidence.md` (link the new pipeline)

- [ ] **Step 1: README env table** — after `GITCORPUS_DETECT_CONCURRENCY` add:

```markdown
| `GITCORPUS_CLONES_ROOT` | `clones` | Clone root for detection scans. Point this at a non-synced disk (e.g. `D:\gitcrawl-clones`) so OneDrive/backup watchers do not churn the git objects. |
| `GITCORPUS_WALK_VERIFY_PCT` | `0` | Percentage of order-dependent PR windows additionally verified against `git rev-list`; off by default, capped at 2 spawns per `walk_windows` call, and exhausted-before-depth walks are never sampled. Mismatches self-heal and disable the in-process path after 3. Gates/tests set `100`. |
```

- [ ] **Step 2: Commit**

```bash
git add README.md docs/superpowers/plans/2026-10-17-run93-live-evidence.md
git commit -m "docs: detection clone-root and walk-verify knobs"
```

---

### Task 12: Verification gates (fail-closed)

**Files:**
- Create: `scripts/verify_walk_equivalence.py`
- Create: `scripts/verify_detection_replay.py`

- [ ] **Step 1: `scripts/verify_walk_equivalence.py`** — clones a sample of source-run repos
  (blobless depth-100 clone + `blob:none` PR fetch, mirroring production), then for every PR tip
  compares `walk_windows` vs `git rev-list -n 100` sets; exits non-zero on any mismatch; prints stats.
  Full content (adapt import path with `sys.path.insert(0, "src")`):

```python
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from detect.gitio import GitRepo, clone_lean, fetch_pr_refs, list_pr_refs  # noqa: E402
from detect.repo_walk import walk_windows  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repos", nargs="+", help="owner/repo entries to verify")
    parser.add_argument("--depth", type=int, default=100)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1] / "clones" / "verify"))
    args = parser.parse_args()

    mismatch = checked = 0
    for full_name in args.repos:
        dest = Path(args.root) / full_name.replace("/", "__")
        dest.mkdir(parents=True, exist_ok=True)
        started = time.monotonic()
        clone_lean(full_name, dest, depth=args.depth, timeout=1800)
        repo = GitRepo(dest)
        fetch_pr_refs(repo, depth=args.depth)
        refs = list_pr_refs(repo)
        walked = walk_windows(repo, refs, depth=args.depth)
        for number, truth in (
            (number, tuple(repo.git("rev-list", "-n", str(args.depth), sha).split()))
            for number, sha in sorted(refs.items())
        ):
            checked += 1
            if set(walked[number]) != set(truth):
                mismatch += 1
                print(f"MISMATCH {full_name} PR #{number}: walked={len(walked[number])} truth={len(truth)}")
        print(f"{full_name}: {len(refs)} tips verified in {time.monotonic() - started:.1f}s")
    print(f"\nchecked={checked} mismatches={mismatch}")
    return 1 if mismatch else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: `scripts/verify_detection_replay.py`** — replays already-scanned repos from a finished
  run through the CURRENT pipeline and diffs evidence byte-for-byte against the DB:

```python
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine, text  # noqa: E402

from detect.git_orchestrator import GitScanConfig, _scan_one  # noqa: E402
from detect.orchestrator import DetectOptions  # noqa: E402
from detect.packs import load_frozen  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True, help="detect run to replay against")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1] / "clones" / "replay"))
    args = parser.parse_args()

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.connect() as connection:
        run = connection.execute(
            text("SELECT filter_spec, source_run_id FROM runs WHERE id=:id"), {"id": args.run_id}
        ).one()
        spec_row = run[0]
        rows = connection.execute(
            text(
                "SELECT i.full_name, i.detection, i.repo_id FROM run_items i"
                " WHERE i.run_id=:id AND i.detection IS NOT NULL"
                " ORDER BY i.id LIMIT :limit"
            ),
            {"id": args.run_id, "limit": args.limit},
        ).all()
    spec = DetectOptions(
        source_run_id=run[1],
        pack_version=spec_row["pack_version"],
        agents=frozenset(spec_row["agents"]) if spec_row.get("agents") else None,
        channels=frozenset(spec_row["channels"]),
        source="git",
        clone_depth=spec_row.get("clone", {}).get("depth", 100),
        clone_keep=False,
        windows=spec_row.get("windows") or {"commits": 100, "prs": 100, "issues": 100},
    )
    pack = load_frozen(engine, spec.pack_version)
    cfg = GitScanConfig(depth=spec.clone_depth, keep=False, scan_root=args.root, timeout=1800)

    mismatches = 0
    for index, (full_name, stored, repo_id) in enumerate(rows, start=1):
        candidate = {"full_name": full_name, "repo_id": repo_id, "stargazers": None}
        scan = _scan_one(
            Path(args.root) / f"detect-{args.run_id}",
            cfg,
            spec,
            pack,
            frozenset(channel for channel in spec.channels if channel in {
                "file", "author", "branch", "bot", "commit_trailer", "pr_metadata"}),
            candidate,
            clone_one=lambda name, dest: __import__(
                "detect.gitio", fromlist=["clone_lean"]
            ).clone_lean(name, dest, depth=cfg.depth, timeout=cfg.timeout),
            make_repo=lambda dest: __import__("detect.gitio", fromlist=["GitRepo"]).GitRepo(
                dest, timeout=cfg.timeout
            ),
        )
        fresh = scan.document
        if fresh != stored:
            mismatches += 1
            print(f"DIFF {full_name}")
            for key in sorted(set(fresh) | set(stored)):
                if fresh.get(key) != stored.get(key):
                    print(f"  {key}: fresh={fresh.get(key)!r} stored={stored.get(key)!r}")
        if index % 25 == 0:
            print(f"replayed {index}/{len(rows)} mismatches={mismatches}")
    print(f"\nreplayed={len(rows)} mismatches={mismatches}")
    return 1 if mismatches else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

  While implementing, replace the `__import__` lambdas with normal imports
  (`from detect.gitio import GitRepo, clone_lean`) — the plan keeps them inline only to survive copy
  ordering; tidy them before committing.

- [ ] **Step 3: Run the walk gate** on a real sample (≥ 100 repos spanning PR-count classes). Known
  monster/storm repos to include explicitly:

```bash
.venv\Scripts\python scripts\verify_walk_equivalence.py PerryTS/perry xybrid-ai/xybrid rust-stdx/stdx apache/sedona-db ubugeeei-prod/vize warpfront/hipfire voidzero-dev/vite-task agent-sh/agnix gemwalletcom/wallet syswonder/robonix jdx/mr-boxington dsx-ai-factory/infra-controller
```

  Add ~90 more from the source run:

```bash
.venv\Scripts\python -c "import os,psycopg; c=psycopg.connect(os.environ['DATABASE_URL'].replace('postgresql+psycopg://','postgresql://')); print('\n'.join(r[0] for r in c.execute('SELECT full_name FROM run_items WHERE run_id=87 ORDER BY random() LIMIT 90')))" > %TEMP%\walk_sample.txt
```

  then pass them on the same command line (or loop the script over the file in shell).

  Expected: `mismatches=0`. Any mismatch blocks the rollout and the walker gets debugged (or
  `GITCORPUS_WALK_VERIFY_PCT=100` + `_MAX_MISMATCHES=0` semantics — i.e. spawn-only — is shipped).

- [ ] **Step 4: Run the replay gate** against run 93's preserved rows:

```bash
$env:DATABASE_URL="postgresql+psycopg://gitcorpus:...@localhost:5433/gitcorpus"
.venv\Scripts\python scripts\verify_detection_replay.py --run-id 93 --limit 300
```

  Expected: `mismatches=0`. Investigate every diff; only the `first_signal_at` timestamps and
  `failure_class` additions may differ for failed scans — documents for successfully scanned repos
  must match exactly.

- [ ] **Step 5: Outage drill (manual, documented).** During a small fresh detect run (~50 repos,
  keep=True), block DNS for `github.com` (hosts entry `0.0.0.0 github.com`) for 2 minutes; assert:
  logs show transient classification, workers pause (breaker), then the retry wave / breaker recovery
  scans everything; `repos_unavailable == 0`. Record the run id + observations in
  `docs/superpowers/plans/2026-10-17-run93-live-evidence.md`.

- [ ] **Step 6: Perf gate.** Run `.venv\Scripts\python -m pytest` (full unit) +
  benchmark 200 repos with `scripts/verify_walk_equivalence.py` timing output vs run 93's 13.7/min;
  require per-repo seconds ≤ run-93 average / 5 before launching the full run.

- [ ] **Step 7: Commit**

```bash
git add scripts docs/superpowers/plans/2026-10-17-run93-live-evidence.md
git commit -m "detect: walk-equivalence, replay, outage, and perf verification gates"
```

---

### Task 13: Final full run + close-out

- [ ] **Step 1: Pre-flight** — stop the console on the quiesced machine (`D:\gitcrawl-clones` root
  set, Defender exclusions copied for the new root), ensure single serve instance, rerun `alembic
  upgrade head`, `ruff check`, `black --check`, full pytest.
- [ ] **Step 2: Launch the fresh detect run** on source run 87 with the same pack `2026-10-14`,
  all channels, all agents, depth 100. Watch: `field_stats.walk` verify stats, `unavailable_reasons`
  trends, spawn counts.
- [ ] **Step 3: Acceptance** — corpus time ≤ 3 h; `unavailable_reasons` contains only `dead`;
  evidence count compared against run 93's per-repo rows for overlapping repos (spot-check 50).
- [ ] **Step 4: Archive** results into `docs/superpowers/plans/2026-10-17-run93-live-evidence.md`
  and commit.
