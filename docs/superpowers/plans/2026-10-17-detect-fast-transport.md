# Detect fast transport — Phase 1–3 implementation plan (2026-10-17)

**Goal:** execute the accepted optimization report (verified against HEAD `32b7c86`) inside the
existing detection pipeline, with byte-identical evidence and the existing gates as the proof:
kill walk-verify spawns, fold commit reads into the walker, restore `tree:0` PR fetches behind
the probed guards, then auth + fleet pacing.

**Branch / worktree:** `detect-fast-transport` at `C:\Users\Abdul\AppData\Local\Temp\opencode\gitcrawl-fast`
(main repo: `C:\Users\Abdul\OneDrive\Documents\Projects\gitcrawl`). Run all commands from the worktree
with the main repo's venv: `C:\Users\Abdul\OneDrive\Documents\Projects\gitcrawl\.venv\Scripts\python.exe`.

**Baseline (captured before any change, `scripts/verify_walk_equivalence.py` on current code):**

| repo | clone | fetch | walk | verify(250) | mismatches |
|---|---|---|---|---|---|
| rust-stdx/stdx (44 tips) | 1.4s | 4.5s | 0.47s | 3.1s | 0 |
| xybrid-ai/xybrid (592 tips) | 2.0s | 20.6s | 6.69s | 26.4s | 0 |
| PerryTS/perry (8,014 tips) | 2.4s | 202.8s | 77.05s | 21.5s | 0 |

Total 370.8s, checked=544, mismatches=0.

## Global constraints (bind every task)

1. **Exactness is non-negotiable.** Same commits, same refs, same blobs, byte-for-byte identical
   evidence rows and `CommitRecord` values. The two gates (`scripts/verify_walk_equivalence.py`,
   `scripts/verify_detection_replay.py`) are the arbiters; the controller runs them after Phase 1
   and Phase 2.
2. **No new dependencies.** stdlib + existing requirements only.
3. **Windows-first.** No argv-length assumptions; use tempfile `stdin` (the existing `fetch_blobs`
   pattern at `src/detect/gitio.py:427-453`).
4. **TDD.** Every behavior change gets a failing test first (RED), implemented minimal (GREEN);
   bounded tests per task (`pytest tests/unit/<files> -q`); full suite only at the very end.
5. **Style:** ruff + black (line length 100), follow existing module patterns; no comments beyond
   the existing documentation style.
6. **Do not regress fallback paths:** any code path that uses a real `git rev-list` spawn
   (replace refs, alternates, `WalkAnomaly`, mismatch substitution) must keep working and must
   backfill `CommitRecord`s via the existing `read_commits`.
7. `GIT_NO_LAZY_FETCH=1` is scoped to the PR fetch command only — never global in `git_env()`;
   the `read_blobs` lazy fallback (`src/detect/gitio.py:278-279`) must keep working.

## Phase 1

### Task 1: Verify sampling — never spawn on exhausted walks, default off, bounded cap

**Files:** `src/detect/repo_walk.py`, `tests/unit/test_repo_walk.py`.

- `_verify_pct()` default changes from `"10"` to `"0"` (env `GITCORPUS_WALK_VERIFY_PCT` still wins,
  clamped 0–100).
- New constant `_VERIFY_MAX_PER_REPO = 2`. When `pct > 0`, at most **2 actual `rev-list` spawns per
  `walk_windows` call** (per repo), regardless of tip count. Tips beyond the budget walk unverified.
- Exhausted-before-depth walks (`len(window) < depth`) are **never** verification candidates under
  any `pct`: they are set-exact by construction (covered instead by the `GITCORPUS_WALK_VERIFY_PCT=100`
  tests, which still exercise the sampler).
- Mismatch semantics unchanged: substitute the truth result, self-heal, disable the in-process path
  after `_MAX_MISMATCHES` (3). `verification_summary()` counts only real spawns.
- Update `README.md` env table line for `GITCORPUS_WALK_VERIFY_PCT` (default `0`, bounded cap,
  exhausted walks exempt).

**Acceptance tests (RED first):**
- exhausted walk + `pct=100` → zero `rev-list` spawns.
- env unset → default is 0 → order-dependent walks spawn nothing.
- `pct=100` + 3 order-dependent tips → exactly 2 spawns.
- mismatch substitution + disable-after-3 still tested (keep/adapt the existing tests; never weaken).

### Task 2: Walk each unique tip SHA once

**Files:** `src/detect/repo_walk.py`, `tests/unit/test_repo_walk.py`.

- In `walk_windows`, group `refs: Mapping[int, str]` by tip SHA before walking: each unique tip is
  walked once and its window tuple is assigned to every PR number sharing that tip. Applies to both
  the in-process path and the fallback (`_fallback`) path.
- Results must be identical (same dict content) to today for all callers.

**Acceptance tests (RED first):**
- fake repo counting `rev-list` calls: `refs={1: A, 2: A, 3: B}` → 2 fallback calls, both windows correct.
- in-process path: duplicate tips produce identical windows for each PR number (real scratch repo).

### Task 3: Raw commit parser in the walker — one read, zero `git log --no-walk` for walked commits

**Files:** `src/detect/repo_walk.py`, `src/detect/local_channels.py`, `tests/unit/test_repo_walk.py`,
`tests/unit/test_detect_local_channels.py`.

- Parsing (`repo_walk.py`): split raw commit at the first `b"\n\n"` → header block / body block.
  Parse only from the header block; **skip continuation lines starting with `b" "`** (`gpgsig`,
  `mergetag` must never inject false headers). The header block ends at the first blank line; any
  `parent `/`committer `-looking line inside the message body is ignored (fixes the latent
  whole-body regex at current lines 21, 86-87).
- Fields: `parent` lines in order (40-hex validated), `author`/`committer` ident lines
  (`name <email> <epoch> <±HHMM>`; name may contain anything except `<>`), optional `encoding`
  header (decode message with it, fallback `utf-8`, `errors="replace"`), message = body after the
  blank line, `.rstrip("\n")` to match `parse_log`'s `strip("\n")`.
- `committed_at` = `git log` `%cI` byte-for-byte: `YYYY-MM-DDTHH:MM:SS±HH:MM` computed from epoch +
  the commit's own UTC offset (handle date rollover on negative offsets).
- Produce `CommitRecord` (import from `detect.gitio`) directly from the walker. `CatFileBatch`
  cache items become parsed nodes carrying `(parents, committer_epoch, record)`.
- New API `walk_windows_with_records(repo, refs, *, depth) -> tuple[dict[int, tuple[str, ...]], dict[str, CommitRecord]]`;
  `walk_windows` delegates to it and discards records (back-compat for the gate script/tests).
- `detect_pr_commits_local`: call `walk_windows_with_records`; after building `sha_to_pr`, backfill
  **only** missing SHAs via the existing `read_commits` (covers fallback/verify/mismatch paths —
  preserves exactness). Remove the unconditional `read_commits` call for the walked path.
- Keep `read_commits`/`read_log`/`parse_log` (fallback + history/branch channels unchanged).

**Acceptance tests (RED first) — byte-for-byte `CommitRecord` parity vs `parse_log` output from
`git log --no-walk --format=...`:**
- GPG-signed commit (`gpgsig` multi-line header), commit signed via `git commit -S` with a scratch
  GPG key **or** a hand-crafted commit object written with `git hash-object -t commit -w` carrying
  a `gpgsig` header (no GPG install required).
- `encoding ISO-8859-1` commit with non-ASCII message (parity with `git log` re-encode to UTF-8).
- merge commit (2 parents, parent order preserved).
- trailers + multi-line message.
- empty body.
- message containing a line that looks like `parent <40-hex>` (must not be parsed as a parent).
- parity across the same SHAs batched through `read_commits` (one test builds N commits, asserts
  `records_from_walk == read_commits(repo, shas)`).
- `detect_pr_commits_local` happy path spawns `git log` only for missing records (fake repo counts
  `log` invocations — zero for fully-walked sets).

## Phase 2

### Task 4: `tree:0` + destination-less `fetch --stdin` + `GIT_NO_LAZY_FETCH=1`, ls-remote map plumbing, snapshot

**Files:** `src/detect/gitio.py`, `src/detect/local_channels.py`,
`scripts/verify_walk_equivalence.py`, `tests/unit/test_gitio.py`,
`tests/unit/test_detect_local_channels.py`.

Probed on `rust-stdx/stdx` (44 refs): 1.5s / +154KB / 0 ref files / 0 repair packs vs baseline
6.1s / +282KB / 44 ref files. Implement exactly:

- `gitio.py`: thread an optional `env_extra: Mapping[str, str] | None` through `_run_git_process`,
  `run_git`, `run_git_bytes`, and `GitRepo.git`; merge over `git_env()` (never mutate `os.environ`).
- `_PR_FETCH_CHUNK_REFS = 2000` (refspecs now ride `stdin`, no argv ceiling).
- `fetch_pr_refs(repo, *, depth, chunk_refs=None) -> dict[int, str]`:
  - `remote = remote_pr_refs(repo)`; return `{}` when empty (and do not write a snapshot).
  - For each chunk: destination-less refspecs `refs/pull/<n>/head` (no `+`, no `:dst`) written to a
    tempfile, fetched with
    `git fetch --quiet --depth <d> --filter=tree:0 --no-tags --no-write-fetch-head --recurse-submodules=no origin --stdin`
    and `env_extra={"GIT_NO_LAZY_FETCH": "1"}`; tempfile cleanup in `finally` (existing pattern).
  - After **all** chunks succeed: persist the map to `.git/.gitcorpus-pr-refs.json`
    (`{"version": 1, "refs": {"<pr>": "<sha>"}}`, sorted keys, atomic-enough single write) via new
    `write_pr_refs_snapshot(repo, refs)`; return the map.
- New `read_pr_refs_snapshot(repo) -> dict[int, str] | None` (missing/corrupt → `None`; tolerate
  unknown version).
- `list_pr_refs` is removed once all callers/tests stop using it (YAGNI) — nothing reads
  `refs/gc/pr` anymore.
- `local_channels.detect_pr_commits_local`: `fetch_and_list()` returns `fetch_pr_refs(...)` output
  directly (no `list_pr_refs`). On fetch failure after retries: if a snapshot exists, use it and
  note `"resumed from persisted PR ref snapshot: <err tail>"` on the channel; else keep today's
  `partial` result. Snapshot use is a resume path only — never skip a successful fresh fetch.
- `scripts/verify_walk_equivalence.py`: `refs = fetch_pr_refs(repo, depth=args.depth)`; drop the
  `list_pr_refs` import/call.
- `read_blobs` lazy fallback needs **no change**: `GIT_NO_LAZY_FETCH` is scoped to the fetch call,
  never in `git_env()`.

**Acceptance tests (RED first):**
- argv/stdin shape: fetch command contains `--filter=tree:0`, `--no-write-fetch-head`, `--stdin`,
  `origin`, **no** refspec in argv; refspec file lines are `refs/pull/<n>/head` with LF endings.
- `env_extra` reaching the subprocess (`GIT_NO_LAZY_FETCH=1`) without leaking into `git_env()`.
- chunking honors `_PR_FETCH_CHUNK_REFS = 2000` (counting fake repo).
- `fetch_pr_refs` returns the ls-remote map and writes the snapshot; corrupt snapshot → `None`.
- `list_pr_refs` removal: update/replace its tests.
- `detect_pr_commits_local` uses returned map; snapshot fallback path yields a non-partial channel
  with the note (fake repo).
- keep `read_blobs` fallback test green (no `GIT_NO_LAZY_FETCH` in base env).

## Phase 3

### Task 5: Authenticated git traffic + secret scrubbing

**Files:** `src/detect/gitio.py`, `tests/unit/test_gitio.py`.

- `git_env()`: when a token is configured (`GITHUB_TOKENS` first entry, else `GITHUB_TOKEN` — same
  precedence as `lib.gh_client.load_tokens`), add a third `GIT_CONFIG_*` entry:
  `http.extraHeader = Authorization: Basic base64("x-access-token:<token>")`. Keep `GIT_CONFIG_COUNT=2`
  when no token. Never put the token in argv.
- Scrubbing: helper `_scrub_secrets(text)` replaces every configured token **and** the base64
  `x-access-token:<token>` payload with `<redacted>`; apply to `GitError` stderr/message and to
  `git_error_tail`. Failure notes must never leak credentials.
- Tests: token set → header present (exact base64), count 3; no token → count 2, no header;
  stderr containing token → scrubbed in `GitError` text and `git_error_tail`.

### Task 6: Monster-repo pacing — fleet `BoundedSemaphore(8)` around monster PR fetches

**Files:** `src/detect/gitio.py`, `src/detect/git_orchestrator.py`,
`src/detect/local_channels.py`, `tests/unit/test_gitio.py`,
`tests/unit/test_detect_local_channels.py`, `tests/unit/test_git_orchestrator.py`.

- `gitio.py`: `_MONSTER_PR_THRESHOLD = 500`; `fetch_pr_refs(..., gate=None)` — when `gate` is not
  `None` **and** `len(remote) > _MONSTER_PR_THRESHOLD`, hold the gate across the chunk loop
  (`acquire`/`release` in `try/finally`); ordinary repos never touch the gate.
- `local_channels.detect_pr_commits_local(..., gate=None)` forwards `gate` to `fetch_pr_refs`.
- `git_orchestrator.py`: in `_run_git_detection_processes`, create
  `pr_gate = mp_context.BoundedSemaphore(8)` and pass it to every worker; thread it through
  `_scan_worker_main` → `_scan_one` → `detect_pr_commits_local`. The single-process path
  (non-Windows / injected fakes) passes `gate=None`.
- Tests: fake gate records acquire/release — acquired iff `len(refs) > 500`; `detect_pr_commits_local`
  forwards; orchestrator wiring keeps `gate=None` on the single-process path (bounded checks only,
  no multiprocessing test).

## Verification (controller-run, not implementer tasks)

- **After Task 3 (Phase 1 gate):** `scripts/verify_walk_equivalence.py rust-stdx/stdx xybrid-ai/xybrid PerryTS/perry`
  → mismatches=0; `walk` and `verify` columns must collapse (perry walk ~1s class, verify ~0).
- **After Task 4 (Phase 2 gate):** same walk gate + `scripts/verify_detection_replay.py` against
  run 93 (DB is up) → 0 regressions; fetch column on perry must drop materially.
- **End:** full `pytest` suite once; ruff + black check; final whole-branch review.
