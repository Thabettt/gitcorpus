# Detection Correctness Minimal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the two cheap accuracy defects found in run 101 and extend the walk-equivalence gate to default-branch `HEAD`, without changing walker output or scan speed.

**Architecture:** Two small production changes plus one verification-script change. `first_signal_at` excludes the `bot` channel; PR walking reports per-tip failures through an optional callback so one broken PR cannot discard the whole `pr_metadata` channel; the gate also compares a `HEAD` window against `rev-list`. Existing callers and walker order stay unchanged.

**Tech Stack:** Python 3.12, pytest, git CLI, existing `detect` modules.

**Spec:** `docs/findings/2026-10-21-detection-optimization-plan-highlights.md`; source assessment: `C:\Users\Abdul\Downloads\gitcorpus-detection-system-analysis-and-optimization-plan.md`.

## Global Constraints

- Accuracy first: every change must preserve all currently correct detections.
- Do not change walk order, `_walk_one`, `_fallback` selection, matcher patterns, pack contents, database schema, or API shapes.
- Do not add environment variables or new persisted fields.
- `on_failure` must be optional; all existing `walk_windows` and `walk_windows_with_records` callers must keep working unchanged.
- Every production behavior change starts with a failing test.
- Use `.venv\Scripts\python.exe -m pytest` for tests.
- Commit only after the targeted tests and the relevant regression tests pass.

## File Structure

- `src/detect/orchestrator.py` — owns `_first_signal_at` and the repo document. Task 1.
- `tests/unit/test_detect_orchestrator.py` — owns the first-signal unit tests. Task 1.
- `src/detect/repo_walk.py` — owns per-tip walking. Task 2 adds failure reporting.
- `src/detect/local_channels.py` — owns `pr_metadata` channel assembly. Task 2 consumes failures and returns `partial`.
- `tests/unit/test_detect_local_channels.py` — owns PR channel behavior. Task 2 adds the end-to-end regression test and updates existing walk fakes.
- `scripts/verify_walk_equivalence.py` — owns the walk gate. Task 3 adds `HEAD`.

---

### Task 1: Exclude Bot Hits From `first_signal_at`

**Files:**
- Modify: `src/detect/orchestrator.py:212-225`
- Test: `tests/unit/test_detect_orchestrator.py:256-277`

**Interfaces:**
- Consumes: `_RepoScan.hits`, `_RepoScan.history_stats`, `_RepoScan.pr_result`, `_BOT_CHANNEL`.
- Produces: no signature change; `_first_signal_at(scan) -> str | None` ignores every `Hit` whose `channel == "bot"`.

- [ ] **Step 1: Write the failing test**

Add this test after `test_first_signal_at_uses_the_earliest_parsed_instant_for_mixed_offsets`:

```python
def test_first_signal_at_ignores_bot_channel_hits():
    from detect.attribution import Hit
    from detect.orchestrator import _RepoScan

    scan = _RepoScan(
        repo_id=1,
        full_name="octo/one",
        stargazers=1,
        hits=[
            Hit("dependabot", "bot", {"commit": "a1", "pr": 7}),
            Hit("Claude Code", "commit_trailer", {"commit": "a2"}),
        ],
        results={},
        pr_result=ChannelResult(stats={"created_at": {7: "2025-01-01T00:00:00Z"}}),
        history_stats={
            "committed_at": {
                "a1": "2025-01-01T00:00:00Z",
                "a2": "2026-01-02T00:00:00Z",
            }
        },
    )
    assert orchestrator_module._first_signal_at(scan) == "2026-01-02T00:00:00Z"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_detect_orchestrator.py::test_first_signal_at_ignores_bot_channel_hits -v
```

Expected: FAIL because the current function returns `"2025-01-01T00:00:00Z"` from the bot hit.

- [ ] **Step 3: Write the minimal implementation**

Replace `_first_signal_at` with:

```python
def _first_signal_at(scan: _RepoScan) -> str | None:
    signal_hits = [hit for hit in scan.hits if hit.channel != _BOT_CHANNEL]
    dates: list[str] = []
    committed = scan.history_stats.get("committed_at") or {}
    for hit in signal_hits:
        oid = hit.evidence.get("commit")
        if oid is not None and oid in committed:
            dates.append(str(committed[oid]))
    if scan.pr_result is not None:
        created = scan.pr_result.stats.get("created_at") or {}
        for hit in signal_hits:
            number = hit.evidence.get("pr")
            if number is not None and number in created:
                dates.append(str(created[number]))
    return min(dates, key=_instant) if dates else None
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_detect_orchestrator.py::test_first_signal_at_ignores_bot_channel_hits tests/unit/test_detect_orchestrator.py::test_first_signal_at_uses_the_earliest_parsed_instant_for_mixed_offsets -v
```

Expected: PASS for both tests.

- [ ] **Step 5: Commit**

```powershell
git add src/detect/orchestrator.py tests/unit/test_detect_orchestrator.py
git commit -m "detect: ignore bot hits for first_signal_at"
```

---

### Task 2: Isolate Per-PR Walk Failures

**Files:**
- Modify: `src/detect/repo_walk.py:488-555`
- Modify: `src/detect/local_channels.py:262-312`
- Modify: `tests/unit/test_detect_local_channels.py:433-497`
- Modify: `tests/unit/test_repo_walk.py:1-25`
- Test: `tests/unit/test_detect_local_channels.py` (new test after `test_detect_pr_commits_local_degrades_a_walk_failure_to_partial`)
- Test: `tests/unit/test_repo_walk.py` (new no-callback regression test after `test_fallback_walks_each_unique_tip_once`)

**Interfaces:**
- Consumes: `walk_windows_with_records(repo, refs, *, depth, session=None)` and `git_error_tail(exc)`.
- Produces: `walk_windows_with_records(..., on_failure: Callable[[int, BaseException], None] | None = None)`; failed PR numbers are reported without aborting successful PRs. `detect_pr_commits_local` returns `status="partial"` when any PR walk failed and retains hits from successful PRs.

- [ ] **Step 1: Write the failing test**

Add this test after `test_detect_pr_commits_local_degrades_a_walk_failure_to_partial`:

```python
def test_detect_pr_commits_local_keeps_good_prs_when_one_walk_fails(tmp_path):
    def handler(args):
        if args[0] == "ls-remote":
            return "aaa\trefs/pull/7/head\nbbb\trefs/pull/9/head\n"
        if args[0] == "fetch":
            return ""
        if args[0] == "rev-list":
            if args[-1] == "bbb":
                raise GitError(list(args), 128, "fatal: bad object bbb")
            return "s1\n"
        if args[0] == "log":
            return _PR_LOG
        return None

    result = detect_pr_commits_local(
        FakeRepo(handler, dest=_repo_dir(tmp_path)), PACK, depth=100, retry_delay=0.0
    )
    assert result.status == "partial"
    assert {(hit.evidence["pr"], hit.evidence["commit"]) for hit in result.hits} == {(7, "s1")}
    assert "1 PR walk(s) failed (e.g. #9: fatal: bad object bbb)" in (result.note or "")
```

Add this regression test to `tests/unit/test_repo_walk.py` after `test_fallback_walks_each_unique_tip_once`:

```python
def test_walk_windows_still_raises_without_a_failure_callback(tmp_path):
    class FakeRepo(GitRepo):
        def __init__(self):
            super().__init__(tmp_path / "not-a-repo")

        def git(self, *args, timeout=None, stdin=None, env_extra=None):
            raise GitError(list(args), 128, "fatal: bad object")

    with pytest.raises(GitError):
        walk_windows(FakeRepo(), {7: "aaa"}, depth=100)
```

Update the test import in `tests/unit/test_repo_walk.py` to:

```python
from detect.gitio import CommitRecord, GitError, GitRepo, read_commits
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_detect_local_channels.py::test_detect_pr_commits_local_keeps_good_prs_when_one_walk_fails -v
```

Expected: FAIL because the current outer `except _GIT_FAILURES` returns `partial` with `hits == ()`.

- [ ] **Step 3: Add the optional failure callback to the walker**

Modify `src/detect/repo_walk.py`:

Change the import lines to:

```python
from collections.abc import Callable, Iterable, Mapping
```

```python
from detect.gitio import CommitRecord, GitError, GitRepo, git_binary, git_env
```

Add this helper immediately before `walk_windows`:

```python
def _report_walk_failure(
    numbers: list[int],
    exc: BaseException,
    on_failure: Callable[[int, BaseException], None] | None,
) -> None:
    if on_failure is None:
        raise exc
    for number in numbers:
        on_failure(number, exc)
```

Change the `walk_windows_with_records` signature to:

```python
def walk_windows_with_records(
    repo: GitRepo,
    refs: Mapping[int, str],
    *,
    depth: int,
    session: RepoWalkSession | None = None,
    on_failure: Callable[[int, BaseException], None] | None = None,
) -> tuple[dict[int, tuple[str, ...]], dict[str, CommitRecord]]:
```

In the replace-refs/alternates branch, change the per-tip block to:

```python
        for sha, numbers in grouped.items():
            try:
                shas = _fallback(repo, sha, depth)
            except (GitError, subprocess.TimeoutExpired) as exc:
                _report_walk_failure(numbers, exc, on_failure)
                continue
            for number in numbers:
                fallback_results[number] = shas
        return fallback_results, {}
```

In the main per-tip loop, wrap the existing body with a failure boundary:

```python
        for sha, numbers in grouped.items():
            try:
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
            except (GitError, subprocess.TimeoutExpired) as exc:
                _report_walk_failure(numbers, exc, on_failure)
                continue
            for number in numbers:
                results[number] = shas
```

Do not change `walk_windows`, `_fallback`, or the verification logic.

- [ ] **Step 4: Consume failures in the PR channel**

Modify `src/detect/local_channels.py` inside `detect_pr_commits_local`:

Before the walk `try` block, add:

```python
    walk_failures: dict[int, str] = {}

    def record_walk_failure(number: int, exc: BaseException) -> None:
        walk_failures[number] = git_error_tail(exc)
```

Replace the walk call with:

```python
        walks, walked_records = walk_windows_with_records(
            repo,
            refs,
            depth=depth,
            session=session,
            on_failure=record_walk_failure,
        )
```

Before the final `return ChannelResult`, add:

```python
    if walk_failures:
        number, detail = next(iter(walk_failures.items()))
        note = f"{note}; {len(walk_failures)} PR walk(s) failed (e.g. #{number}: {detail})"
```

Change the final status line to:

```python
        status="partial" if walk_failures else "ok",
```

- [ ] **Step 5: Update existing test fakes and the old whole-walk note assertion**

In `tests/unit/test_detect_local_channels.py`, update the two `fake_walk` definitions and the `exploding_walk` definition to accept the keyword:

```python
    def fake_walk(repo, refs, *, depth, session=None, on_failure=None):
```

```python
    def exploding_walk(repo, refs, *, depth, session=None, on_failure=None):
```

Do not change their bodies.

Update `test_detect_pr_commits_local_degrades_a_walk_failure_to_partial` so it asserts the new per-tip note:

```python
    assert result.status == "partial"
    assert "1 PR walk(s) failed (e.g. #7: fatal: bad object aaa)" in (result.note or "")
    assert result.stats["propagated_oids"] == ()
```

- [ ] **Step 6: Run the targeted test and the PR-channel regression tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_detect_local_channels.py -q
```

Expected: PASS for the whole file, including the new test, the updated whole-walk note test, and the existing fake-walk tests.

- [ ] **Step 7: Run the walker regression suite**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_repo_walk.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add src/detect/repo_walk.py src/detect/local_channels.py tests/unit/test_detect_local_channels.py tests/unit/test_repo_walk.py
git commit -m "detect: isolate per-PR walk failures"
```

---

### Task 3: Extend the Walk Gate to `HEAD` and Run the Accuracy Gates

**Files:**
- Modify: `scripts/verify_walk_equivalence.py:38-72`

**Interfaces:**
- Consumes: `walk_windows(repo, {0: head}, depth=...)`, `repo.git("rev-parse", "HEAD")`, `repo.git("rev-list", "-n", depth, head)`.
- Produces: every checked repo also reports a `HEAD` comparison; the process exits nonzero on any PR or `HEAD` mismatch.

- [ ] **Step 1: Add the `HEAD` check to the gate**

In `scripts/verify_walk_equivalence.py`, after the PR verification loop and before `t_verify = ...`, add:

```python
        head = repo.git("rev-parse", "HEAD")
        head_walk = walk_windows(repo, {0: head}, depth=args.depth)[0]
        head_truth = tuple(repo.git("rev-list", "-n", str(args.depth), head).split())
        checked += 1
        head_mismatch = set(head_walk) != set(head_truth)
        if head_mismatch:
            mismatch += 1
            local_mismatch += 1
            print(
                f"MISMATCH {full_name} HEAD:"
                f" walked={len(head_walk)} truth={len(head_truth)}"
            )
```

Change the summary print to include the `HEAD` result:

```python
        print(
            f"{full_name}: tips={len(tips)} verified={len(sampled)} mismatches={local_mismatch}"
            f" head={'MISMATCH' if head_mismatch else 'ok'}"
            f" clone={t_clone:.1f}s fetch={t_fetch:.1f}s walk={t_walk:.2f}s verify={t_verify:.1f}s",
            flush=True,
        )
```

- [ ] **Step 2: Run the walker unit tests**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/unit/test_repo_walk.py -q
```

Expected: PASS.

- [ ] **Step 3: Run the walk-equivalence gate on the fixed smoke set**

Run:

```powershell
.venv\Scripts\python.exe scripts\verify_walk_equivalence.py PerryTS/perry xybrid-ai/xybrid rust-stdx/stdx apache/sedona-db ubugeeei-prod/vize warpfront/hipfire voidzero-dev/vite-task agent-sh/agnix gemwalletcom/wallet syswonder/robonix jdx/mr-boxington dsx-ai-factory/infra-controller
```

Expected: final line `checked=<n> mismatches=0`; each repo line contains `head=ok`.

If a mismatch appears, stop and report the repo, PR/`HEAD`, walked count, and truth count. Do not change the walker in this task.

- [ ] **Step 4: Run the replay gate**

Run only when the database and run 101 are available. Run 101 is the near-current
baseline (same source run 87, stored pack `2026-10-19`); run 99 predates the
October 19 detection rewrite and is not a valid baseline for current `HEAD`.

```powershell
.venv\Scripts\python.exe scripts\verify_detection_replay.py --run-id 101 --limit 120
```

Expected: `first_signal_at` may differ where the stored signal came only from
bot-channel hits; that is the intended bot-filter change. Treat new `channels`,
`notes`, `agents`, or `commit_ratio` drift as investigation signals. Replay is a
live-drift detector, not a zero-mismatch gate. Record the final counts in the
task notes.

- [ ] **Step 5: Commit**

```powershell
git add scripts/verify_walk_equivalence.py
git commit -m "test: verify HEAD walk equivalence"
```

---

## Out of Scope

These items are intentionally excluded from this minimal plan:

- `A-2` CSV shape: not a bug; the 23-column/3,036,007-row run-101 CSV is exact.
- `A-3` lazy-fetch changes: current scoping is intentional; the `git show` fallback depends on it.
- `A-4` air-gap mirroring: the product is live-only.
- `A-6` resume skipping: live refs drift, so skipping repos mixes epochs.
- Re-listing and retrying a failed PR tip after a walk failure: this plan contains the channel-wide loss and reports the failed PR, but does not attempt single-tip recovery.
- Broad matcher hardening: confirmed residual false positives are small and need a separate targeted audit.
- Full 400-artifact × 2-annotator audit.
- Any speed optimization. Validate the gates first; speed changes need phase metrics and a separate plan.

## Definition of Done

- [ ] Bot-only hits no longer set `first_signal_at`.
- [ ] One failed PR tip no longer discards successful PR hits; the channel is `partial` and names an example failed PR.
- [ ] `walk_windows` still raises on a failed tip when no failure callback is supplied.
- [ ] The walk gate checks default-branch `HEAD` and the smoke set reports zero mismatches.
- [ ] Targeted tests and `tests/unit/test_repo_walk.py` pass.
- [ ] No changes to walk order, matchers, pack, schema, or API shapes.
