# Run #100 Pre-Flight — Accuracy & Throughput Execution Plan

Source: controller pre-flight audit (2026-10-19), Run #99 post-mortem at
`docs/findings/2026-10-18-run99-detection-analysis.md`, and scratch probes under
`C:\Users\Abdul\AppData\Local\Temp\opencode\gcprobe2\`.

## Global Constraints

1. **Workspace**: all work happens in the worktree
   `C:\Users\Abdul\OneDrive\Documents\Projects\gitcrawl\.worktrees\run100`
   (branch `run100-accuracy-throughput`). Never modify files in the main checkout
   `C:\Users\Abdul\OneDrive\Documents\Projects\gitcrawl` (reading it is fine). Run every
   command with the worktree as the working directory.
2. **Interpreter**: `C:\Users\Abdul\OneDrive\Documents\Projects\gitcrawl\.venv\Scripts\python.exe`.
   `pyproject.toml` sets `pythonpath = ["src"]`, so pytest from the worktree imports worktree code.
3. **Database**: `DATABASE_URL` is already set in the environment (local dev Postgres,
   port 5433, db `gitcorpus`). Read `os.environ["DATABASE_URL"]`; never print credentials.
4. **Accuracy parity**: zero loss on genuine agent signals. Every matcher behavior change must be
   covered by tests taken from the audit probe table. Do not change detection semantics beyond what
   this plan specifies.
5. **Testing**: run only the focused tests covering a task's changed code while iterating and before
   committing. The full suite (pytest/ruff/black/mypy) runs once at the end (V1). This overrides the
   SDD template's "run the full suite once before committing".
6. **Commits**: each implementer commits its own work locally on the branch. Local commits only —
   never push, never amend published work. Do not touch the main checkout's branch.
7. **Dependencies**: do not add third-party packages. `httpx==0.28.1` is already in `requirements.txt`.
8. **Backward compatibility**: keep the pinned interfaces below working; the scripts
   `scripts/verify_walk_equivalence.py` and `scripts/verify_detection_replay.py` call them directly.
9. **No subagents**: implementers and reviewers do this work themselves; the controller owns all
   dispatch and review.

## Interface Pins

- `detect.attribution.AMBIGUOUS`: `frozenset[str]` of lowercase literals
  `{"aider","claude","copilot","cline","junie","cursor","coderabbit","chatgpt","roomote","codex"}`;
  membership tests are case-insensitive.
- Ambiguous-pattern boundary wrap: `(?<![A-Za-z0-9_-])(?:PAT)(?![A-Za-z0-9_-])`.
- `match_commit_messages(pack, messages, agents=None)` — signature unchanged.
- `match_author_identities(pack, entries, agents=None)` — signature unchanged.
- `gitio.RemoteRefs(pr_refs: dict[int, str], head_refs: dict[str, str])` (`head_refs` keys are full
  `refs/heads/...` names). `gitio.remote_refs(repo: GitRepo) -> RemoteRefs`, cached on the `GitRepo`
  instance; raises `GitError` with stderr containing `Repository not found` for HTTP 401/404; falls
  back to `git ls-remote --refs origin refs/pull/*/head refs/heads/*` on any other failure.
- `gitio.remote_refs_for(full_name: str) -> RemoteRefs` — same, no repo/clone required; used by the
  scheduler pre-probe; raises the same dead `GitError`; raises the underlying `httpx` error type
  wrapped in a `RemoteRefsUnavailable` exception for transient failures (scheduler catches it).
- `gitio.git_binary() -> str` — resolved once per process.
- `fetch_pr_refs(repo, *, depth, chunk_refs=None, gate=None, refs=None, gate_reserved=False)` —
  existing keywords keep working.
- `detect_pr_commits_local(..., refs=None, gate=None, gate_reserved=False, session=None)` — mechanism
  args keyword-only with defaults.
- `_scan_one(...)` keeps its current positional signature; new parameters are keyword-only with
  defaults (`prefetched: RemoteRefs | None = None`, `gate_reserved: bool = False`).
- `repo_walk.CatFileBatch(dest, *, op_timeout=None, repo_timeout=None)` and
  `repo_walk.walk_windows(repo, refs, *, depth)` — call-compatible.
- `GitScanConfig.pr_gate_permits: int = 32`, overridable via env `GITCORPUS_PR_GATE` when the serve
  layer constructs configs; the sweep passes it directly.

---

## Task 1: Pack hygiene, escaping, and the 2026-10-19 pack

Files: `packs/patterns/authors.csv`, `packs/2026-10-19.json` (generated), new
`tests/unit/test_pack_hygiene.py`.

Context: audit found the authors channel compiles patterns as raw regex fragments
(`src/detect/attribution.py:83`), which breaks literal patterns: `factory-droid[bot]` and
`abacus-ai-automation[bot]` use a regex character class and can never match their literal logins;
`Codex (gpt-5.2-codex)` and the `Claude (glm-4.x)` family use parens as capture groups; dots are
unescaped; `codex@openai.com` is duplicated; there is no bare `Codex` pattern. Task 2/Task 3 will
match case-insensitively, so an escaped literal `AI Assistant` replaces the intentional regex
`AI [Aa]ssistant`.

Requirements:
1. In `packs/patterns/authors.csv`, escape regex metacharacters so every entry is a literal:
   - all `.` → `\.` (every email), e.g. `aider@aider.chat` → `aider@aider\.chat`;
   - `[` `]` → `\[` `\]`, e.g. `factory-droid[bot]` → `factory-droid\[bot\]` and
     `abacus-ai-automation[bot]` → `abacus-ai-automation\[bot\]`;
   - `(` `)` → `\(` `\)`, e.g. `Codex (gpt-5.2-codex)` → `Codex \(gpt-5\.2-codex\)`, all
     `Claude (glm-4.7)`, `Claude (GLM-4.7)`, `Claude (glm-4.6)`, `Claude (GLM-4.6)`,
     `Claude (kimi-for-coding)`, `Claude (kimi-k2.5)`, `Claude (MiniMax-M2.1)` similarly;
   - `+` in `microsoft-amplifier@users.noreply.github.com` is inside an email; escape as needed.
2. Replace `AI [Aa]assistant` with literal `AI Assistant`.
3. Remove the duplicate `codex@openai.com` row (keep one).
4. Add bare `Codex` with agent `Codex` (needed: `Generated with Codex` matches nothing today).
5. Do NOT add `claude[bot]` / `claude@users.noreply.github.com` rows. Ruling: Task 3's login
   normalization covers `1234+claude[bot]@users.noreply.github.com` via case-insensitive normalized
   equality against the existing `Claude` pattern; a Task 3 test must prove that exact probe case.
6. Build and freeze the new pack:
   - `python -m detect.packs build --src packs/patterns --version 2026-10-19 --out packs/2026-10-19.json`
   - `python -m detect.packs freeze --pack packs/2026-10-19.json` (uses `DATABASE_URL`).
   Do not modify `packs/2026-10-14.json` or `trace_packs` rows for it.
7. Confirm nothing in `src/` hardcodes a pack version (grep shows none), so no code default changes.

Tests (`tests/unit/test_pack_hygiene.py`):
- every author pattern compiles (`re.compile`) and no pattern contains unescaped `(`, `[`, or a bare
  `.` outside a literal context;
- `re.search("factory-droid\\[bot\\]", "factory-droid[bot]")` matches after loading the new pack and
  the built `ChannelRegex` finds it in login `factory-droid[bot]`;
- bare `Codex` present exactly once; `codex@openai.com` present exactly once;
- `load_pack_file(packs/2026-10-19.json)` yields 79 authors (78 unique originals + 1 new bare Codex),
  and its digest is stable across two loads.

Acceptance: focused tests pass; freeze succeeds; `git status` shows only the intended files.

---

## Task 2: Two-tier `match_commit_messages` (trailer scope)

Files: `src/detect/attribution.py`, `tests/unit/test_detect_attribution.py`.

Context: today the author regex runs over the whole message case-sensitively
(`attribution.py:216-238`), producing prose FPs (`decline` → Cline, `assoc_cursor` → Cursor,
`raider` → Aider) and missing capitalized trailers (`Generated with Cursor`). Robbes use
author/co-author trailers and "Generated by" footers; casing varies.

Requirements:
1. Add `AMBIGUOUS` (see Interface Pins) and wrap every ambiguous pattern with the boundary wrap in
   all author-channel compilations. Compile author-channel regexes with `re.IGNORECASE`.
2. Tier 1 — extract trailer/footer lines and run the full author regex over only those lines:
   - allowlisted trailer tokens on any line, line-anchored with optional leading whitespace/quote
     (`>`, `*`, `•`, `-`, emoji): `{co-authored-by, authored-by, author, committer, signed-off-by,
     assisted-by, co-developed-by, developed-by, generated-by, written-by, ai-assisted}` matched as
     `^[ \t>*•\-\U0001F300-\U0001FAFF\u2600-\u27BF]*<TOKEN>:[ \t]*(.*)$` (case-insensitive);
   - attribution footer phrases on any line: optional whitespace/quote/bullet/emoji prefix, then
     `(generated|created|written|made|built|assisted|co-authored|authored|powered|developed)\b`
     with a following `(with|by|using)` within 40 chars — do NOT restrict to the last paragraph
     (Claude Code footers sit above a blank line and squash merges put footers mid-message);
   - generic `Token: value` lines only in the final trailer block (text after the last blank line),
     excluding prose tokens `{note, warning, fix, fixes, todo, example, update, changes}`.
3. Tier 2 — full-message email salvage: a precompiled regex of only the `@` patterns, case-insensitive,
   run over the whole message when Tier 1 produced no email-pattern hit for that message or when the
   message has no extracts at all. Unconventional email mentions must still hit.
4. Fast path: if the message contains no `@` AND no line matches the trailer/footer fast check, return
   `()` before running the agent regex.
5. Emit at most one `commit_trailer` hit per (commit, agent). Prefer the Tier 1 snippet; fall back to
   the Tier 2 snippet. Keep the snippet redaction (`redact_emails`) and 100-char cap.
6. Keep `is_noise_commit` first-line filtering unchanged.

Tests (extend `tests/unit/test_detect_attribution.py`; use values verbatim):
- prose traps no longer match: `"fix: push declined due to branch protection"`,
  `"refactor: rename assoc_cursor to cursor_id"`, `"refactor(aider): move the aider launcher"`,
  `"fix: raider subsystem crash"`;
- case-insensitive trailers match: `Co-authored-by: Cursor` (no email), `Generated with Cursor`,
  `Generated with CodeRabbit`, `Generated with Junie`, `Generated with Roomote`,
  `Built with Aider`, `Generated with Cline`, `generated with claude code`,
  `Generated with Codex` (bare Codex), `Co-authored-by: factory-droid[bot]`;
- footer in second-to-last paragraph: `msg\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)\n\nCo-Authored-By: Claude <noreply@anthropic.com>` hits Claude Code;
- quoted/bulleted footer lines match (`> Co-authored-by: Cursor`, `- Generated with Aider`);
- human name in a trailer value does not match: `Co-authored-by: Jean-Claude Van Damme <jc@x.com>`
  yields no Claude hit;
- email-only salvage: `contact noreply@anthropic.com for help` still yields a Claude Code hit;
- generic token in prose does not match: `Note: cursor position was wrong` → no Cursor hit;
- existing test `test_commit_messages_redact_emails_and_skip_noise` still passes (one Cursor hit,
  snippet contains `<email>`, `cursoragent@x` absent).

Acceptance: focused attribution tests pass; hit count per (commit, agent) is at most one.

---

## Task 3: Identity-field tightening (author/bot channels)

Files: `src/detect/attribution.py`, `tests/unit/test_detect_attribution.py`.

Context: `_match_identity_fields` (`attribution.py:173-199`) substring-matches name/email/login
case-sensitively. Probe FPs: name `Jean-Claude Dupont` → Claude Code; `raider@corp.com` → Aider;
login `decline-cli` → Cline; login `cursor-service` → Cursor. Probe FN: `claude[bot]` noreply email.

Requirements (restructure into one per-entry pass; keep the public signatures):
1. Split patterns into AMBIGUOUS (boundary-wrapped, see Task 2) and distinctive (escaped literals,
   case-insensitive).
2. `email` field:
   - distinctive `@` patterns: case-insensitive literal search in the email value;
   - AMBIGUOUS bare word: matches only when the normalized login equals the pattern
     (case-insensitive equality), where normalized login = the GitHub noreply login after stripping
     a leading `\d+\+`, or the local part when the address is not a noreply.
3. `login` field:
   - normalize by stripping a trailing `[bot]` or `-bot` (case-insensitive), then require
     case-insensitive full equality for AMBIGUOUS and distinctive single-token patterns;
   - distinctive multi-token handles (`copilot-swe-agent`, `devin-ai-integration`) may match by
     boundary-wrapped substring.
4. `name` field:
   - distinctive patterns: case-insensitive boundary-wrapped match;
   - AMBIGUOUS bare word: only when corroborated — the same entry's email or login already matched
     the same agent, OR the name matches one of that agent's multi-token patterns (`Claude Code`,
     `Claude Opus 4.6`, `Kilo Code`, `Roo Code`, …).
5. Apply the login rule to `match_pr_authors` and `match_issue_participants` (both currently call
   `_match_values` on a login string).
6. `match_bots` keeps working (shared helper); bot evidence is not adoption evidence.

Tests (verbatim probe cases):
- FPs now clean: name `Jean-Claude Dupont` (email `jc@corp.fr`) → no Claude Code; name `Claude Bernard`
  → no; email `raider@corp.com` → no Aider; login `raider123` → no; login `decline-cli` → no Cline;
  login `cursor-service` → no Cursor.
- Genuine retained: name `Claude` + email `noreply@anthropic.com` → Claude Code (email field);
  name `Claude Code` + `noreply@anthropic.com` → Claude Code; email
  `1234+claude[bot]@users.noreply.github.com` → Claude Code (new FN fix, proves the Task 1 ruling);
  `aider@users.noreply.github.com` → Aider; login `copilot-swe-agent` → Copilot.

Acceptance: focused tests pass; existing identity tests (`test_author_evidence_never_contains_the_identity_value`
etc.) pass; API-mode login tests still pass.

---

## Task 4: Ratio and `first_signal_at` math

Files: `src/detect/local_channels.py`, `src/detect/channels.py`, `src/detect/orchestrator.py`,
`tests/unit/test_detect_local_channels.py`, `tests/unit/test_detect_orchestrator.py`.

Requirements:
1. In `detect_history_local` (`local_channels.py:145-148`) and its API twin (`channels.py:341-344`),
   intersect AI oids with the bot-subtracted window set: `ai_oids &= commit_oids`. A commit that is
   both bot-authored and AI-trailered must leave both numerator and denominator.
2. Fix `_first_signal_at` (`orchestrator.py:203-216`): pick the minimum by parsed instant
   (`datetime.fromisoformat`, treating `Z` as UTC) while returning the winning original ISO string.
3. Do not change the adoption-level boundaries (`attribution.py:46-55`) or the
   `ratio = len(ai)/(len(ai)+len(human))` formula.

Tests:
- bot+AI overlap commit: `commits` excludes it, `ai_oids` excludes it, ratio denominator excludes it;
- mixed-offset case: `["2025-01-01T00:30:00+03:00", "2024-12-31T23:00:00Z"]` selects
  `2024-12-31T23:00:00Z` (the later instant is NOT returned);
- existing ratio/adoption tests in `test_detect_orchestrator.py` still pass.

Acceptance: focused tests pass.

---

## Task 5: `GIT_NO_LAZY_FETCH` + shallow-boundary walk hardening

Files: `src/detect/repo_walk.py`, `src/detect/gitio.py`, `tests/unit/test_repo_walk.py`,
`tests/unit/test_gitio.py`.

Context: probe proved `git cat-file --batch` lazy-fetches missing objects over the network by
default (1.05 s for a tiny object) and returns `<oid> missing` instantly with
`GIT_NO_LAZY_FETCH=1`. The walker's reads are unbounded, so a stalled lazy fetch wedges the thread
and leaks the child process (Run #99's 44-minute `cat-file` backlog).

Requirements:
1. `CatFileBatch` starts its child with `git_env()` plus `GIT_NO_LAZY_FETCH=1`.
2. `_read_blobs_batch` (`gitio.py:331-337`) runs `cat-file --batch` with
   `env_extra={"GIT_NO_LAZY_FETCH": "1"}`.
3. `read_commits` (`gitio.py:606-615`) passes the same env to its `log --no-walk` batches.
4. `fetch_blobs` and the single-blob `read_blob` fallback keep lazy fetch allowed (they are the
   legitimate object-fetch paths).
5. `_walk_one`: when `cat.commit(parent)` returns `None` for a parent being expanded, treat it as a
   shallow boundary — skip enqueuing it, never raise, never fall back. A missing tip still raises
   `WalkAnomaly`.
6. `_fallback` adds `--exclude-promisor-objects` and runs with `GIT_NO_LAZY_FETCH=1` as well.
7. Update the existing assertion in `tests/unit/test_gitio.py` (currently asserts the walker env does
   NOT set lazy-fetch flags) to assert the walker env DOES set `GIT_NO_LAZY_FETCH=1` while
   `fetch_blobs` does not.

Tests: missing-parent → boundary (no fallback spawn), missing tip → `WalkAnomaly`; fallback argv
contains `--exclude-promisor-objects`; env assertions.

Acceptance: focused tests pass; `scripts/verify_walk_equivalence.py` is expected to still report 0
mismatches (V2).

---

## Task 6: Per-read watchdog timeout on `CatFileBatch`

Files: `src/detect/repo_walk.py`, `tests/unit/test_repo_walk.py`.

Context: even with lazy fetch disabled, a hung pipe would still block forever. User-specified
budgets: 60 s per batch operation, 180 s per repo walk, env-overridable.

Requirements:
1. `CatFileBatch(dest, *, op_timeout=None, repo_timeout=None)`; defaults from
   `GITCORPUS_CATFILE_OP_TIMEOUT_SECONDS` (60) and `GITCORPUS_CATFILE_REPO_TIMEOUT_SECONDS` (180).
2. One daemon watchdog thread per instance: kills the child if an operation exceeds `op_timeout` or
   the instance exceeds `repo_timeout`; sets a timed-out flag so the next `commit()` raises
   `WalkAnomaly("cat-file timed out ...")` (the kill unblocks `readline` with EOF).
3. `close()` stops the watchdog and reaps the child; no thread leaks.
4. Keep the class usable from one thread at a time (per-repo walker owns it).

Tests: with a real child that never answers (e.g. a small Python sleep process substituted for git
via monkeypatch), a 0.2 s op timeout raises `WalkAnomaly` and leaves no live child; normal fast path
unaffected; `close()` idempotent.

Acceptance: focused tests pass.

---

## Task 7: Worker-tree kill + cancellable per-chunk gate

Files: `src/detect/git_orchestrator.py`, `src/detect/gitio.py`, `tests/unit/test_git_orchestrator.py`,
`tests/unit/test_gitio.py`.

Requirements:
1. Add `_kill_tree(pid)` in `git_orchestrator.py`: on Windows `taskkill /F /T /PID <pid>`
   (suppress errors), else `Process.terminate()`. Use it at every worker-terminate site
   (`git_orchestrator.py:410-415`, `:466-472`, `:476-479`).
2. In `gitio.fetch_pr_refs`, make gate waiting cancellable: helper
   `_acquire_gate(gate, *, blocking=True) -> bool` that polls `gate.acquire(timeout=0.5)` and calls
   `cancellation.check()` between polls; raise `RunCancelled` promptly on cancel.
3. Hold the gate per fetch chunk, not across the whole repo: acquire before each chunk
   (`gitio.py:522-543`) and release in a per-chunk `finally`. A repo with >500 refs still counts as
   gated (`_MONSTER_PR_THRESHOLD`, `gitio.py:33,518`).
4. Do not change the non-gated path.

Tests: fake gate records acquire/release pairing per chunk; cancellation while waiting raises
`RunCancelled`; `_kill_tree` builds the expected argv (monkeypatched `subprocess.run`).

Acceptance: focused tests pass.

---

## Task 8: In-process `httpx` keep-alive `ls-refs`

Files: `src/detect/gitio.py`, `tests/unit/test_gitio.py`.

Context: probe showed Protocol v2 `ls-refs` over `httpx` returns byte-identical `{pr_num: sha}`
dicts to `git ls-remote` on 11 repos (0-PR, 47-PR, 55-PR, 503-PR, 1,417-PR, 2,148-PR, 2,553-PR,
8,143-PR, plus 404), at 0.22–0.55 s vs 1.03–1.64 s cold, ~0.25 s with keep-alive. It also lets the
scheduler detect dead repos before cloning.

Requirements:
1. Add `RemoteRefs` dataclass and module-level thread-local `httpx.Client` factory (timeout 30 s,
   `follow_redirects=True`, token auth from `lib.gh_client.load_tokens()` when available,
   `User-Agent: git/2.47.1`).
2. Request body: `command=ls-refs` pkt-line, `0001` delim, `peel`, `ref-prefix refs/pull/`,
   `ref-prefix refs/heads/`, flush; parse SHA lines defensively (ignore `version 2` and `ERR`
   payloads). Return `RemoteRefs(pr_refs, head_refs)` with full `refs/heads/...` keys.
3. `remote_refs(repo)` — URL from `repo.full_name` when set, else `git remote get-url origin`
   (cached on the repo); cache the `RemoteRefs` result on the repo instance. Add
   `full_name: str | None = None` to `GitRepo` and pass it from `git_orchestrator.make_repo`.
4. `remote_refs_for(full_name)` — same client logic without a repo (for Task 10 pre-probe); dead
   statuses raise dead `GitError`; transient failures raise `RemoteRefsUnavailable`.
5. HTTP 401/404 → raise `GitError(["ls-refs", url], 128, "remote: Repository not found.")` so
   `classify_git_failure` returns `dead`.
6. Any other failure (transport, 5xx, parse) → fall back to
   `git ls-remote --refs origin refs/pull/*/head refs/heads/*`, parsed into the same shape.
7. `fetch_pr_refs` uses `remote_refs(repo).pr_refs` instead of `remote_pr_refs(repo)`; keep
   `remote_pr_refs` as a thin wrapper for compatibility.

Tests (use `httpx.MockTransport`; never hit the network in tests): pkt-line parsing (trimmed pkt,
peeled attrs, `version 2` header, empty response); both prefixes requested; 404 → dead `GitError`;
transport error → git fallback (monkeypatched); cache hit does one request;
`fetch_pr_refs(refs=...)` skips listing.

Acceptance: focused tests pass.

---

## Task 9: Branch channel from remote head refs (A4)

Files: `src/detect/local_channels.py`, `tests/unit/test_detect_local_channels.py`.

Requirements:
1. `detect_branch_local` keeps merge-message matching (unchanged) and additionally matches remote
   head refs: `head_refs` from `gitio.remote_refs(repo)`, stripping `refs/heads/` before
   `match_branches`.
2. Evidence shape stays `{"pr", "head", "match"}`; remote-branch evidence uses `"pr": None` and the
   stripped branch name; note text mentions both sources.
3. Failure to list refs degrades to merge-message-only (`status="ok"`, note unchanged style); never
   raise.
4. Do not trigger listing when no branch patterns exist.

Tests: fake repo cache returns head refs `refs/heads/claude/fix-tests` → Claude Code hit with
`pr=None`; merge-message path still yields the old evidence; listing failure falls back.

Acceptance: focused tests pass.

---

## Task 10: Pre-probe + two-lane deque scheduler (B1b)

Files: `src/detect/git_orchestrator.py`, `src/detect/local_channels.py`,
`tests/unit/test_git_orchestrator.py`.

Requirements:
1. In `_scan_worker_main` (multiprocess path only), replace `pending = iter(slice_candidates)` with
   a `collections.deque`. Admission loop:
   - pop left; pre-probe `gitio.remote_refs_for(full_name)`;
   - dead `GitError` → emit a failed scan without cloning (failure_class `dead`) and continue;
   - `RemoteRefsUnavailable` → submit normally with `prefetched=None` (the fetch path will list refs);
   - `len(pr_refs) > 500` and `pr_gate.acquire(blocking=False)` fails → appendleft the candidate with
     its prefetched refs and submit the tail instead (`pending.pop()`); if the monster is the only
     candidate left, submit it anyway (its fetch path blocks on the gate as today);
   - acquired permits are released by `_scan_one` exactly once (pass `gate_reserved=True`).
2. Thread the data: `_scan_one(..., prefetched=None, gate_reserved=False)` →
   `detect_pr_commits_local(..., refs=prefetched, gate=pr_gate, gate_reserved=gate_reserved)`;
   `_scan_one` wraps its body so the reserved permit is released in `finally`.
3. `fetch_pr_refs(..., refs=None, gate_reserved=False)`: when `refs` is given, skip the remote
   listing and use it (snapshot semantics); when `gate_reserved` is true, do not acquire per chunk
   and do not release (the caller owns the permit); otherwise per-chunk gating from Task 7 applies.
4. Pre-probe runs only in the scheduler (production multiprocess path), never inside `_scan_one`, so
   replay and unit fakes stay offline.
5. Keep the wave-2 retry behaviour; prefetched refs survive requeue.
6. Extract the admission decision into a pure helper (`_admit(...)`) that unit tests can drive with
   fakes.

Tests: pure-helper tests (dead skip, transient passthrough, monster requeue + tail pop, last-candidate
fallback); `_scan_one` releases a reserved permit in `finally`; `fetch_pr_refs` honours `refs=`.

Acceptance: focused tests pass; no imports of httpx in paths tests exercise with fakes.

---

## Task 11: Mechanical batch — git binary, cleanup, finalize ETA

Files: `src/detect/gitio.py`, `src/detect/repo_walk.py`, `src/detect/git_orchestrator.py`,
`src/serve/pages.py` (or the exact ETA renderer found), tests as noted.

Requirements (one batch, three independent edits):
1. `gitio.git_binary()`: `GITCORPUS_GIT_BIN` env override if it exists → sibling
   `<git-root>/mingw64/bin/git.exe` when `shutil.which("git")` resolves to the Git-for-Windows cmd
   shim (`<root>/cmd/git.exe`) → `shutil.which("git")` → `"git"`. Cache once per process. Use it in
   `_run_git_process` (`gitio.py:229`) and `CatFileBatch` (`repo_walk.py:129`).
2. Replace `_spawn_rmdir` with `shutil.rmtree(path, ignore_errors=True)` in `_remove_tree`
   (`git_orchestrator.py:76-105`); delete the now-unused helper and its tests; keep the retry loop.
3. Suppress the misleading ETA during the finalize `"writing"` stage: locate the ETA render (search
   `serve/` for the reporter's ETA use with the `"writing"` stage from `serve/executor.py:439`) and
   render no ETA while writing. Add a focused test.

Tests: `git_binary` resolution matrix (env override, shim→mingw64, which fallback) with monkeypatched
`shutil.which`/`Path.exists`; `_remove_tree` removes a temp tree; ETA suppression test.

Acceptance: focused tests pass; no `_spawn_rmdir` references remain.

---

## Task 12: `CatFileBatch` generic reads + HEAD window walk

Files: `src/detect/repo_walk.py`, `src/detect/gitio.py`, `tests/unit/test_repo_walk.py`.

Requirements:
1. Extract a generic `CatFileBatch.read(request: str) -> tuple[str, bytes] | None` supporting both
   OID requests and `HEAD:<path>` requests (the probe confirmed one child serves both); `commit()`
   keeps its behaviour and uses `read()`. `None` means missing.
2. Add `RepoWalkSession` owning one `CatFileBatch`, the commit cache, and the shallow set:
   `RepoWalkSession.open(repo)`, `.window(tip, depth) -> tuple[shas, records]` (set-identical to
   `_walk_one`), `.record(oid)`, `.blob(request)`, `.close()` (idempotent) and a context manager.
3. Refactor `walk_windows_with_records` to use a session internally; public behaviour unchanged
   (fallback/verify logic stays).
4. Add `gitio.resolve_head(repo) -> str` reading `.git/HEAD` (symbolic ref → loose ref file →
   `packed-refs`) with a `git rev-parse HEAD` fallback if parsing fails.

Tests: `read()` on commit OID, blob request, missing request; session window matches the existing
walker on the repo-walk fixtures; `resolve_head` on a temp git dir with loose and packed refs.

Acceptance: focused tests pass; existing repo_walk tests pass.

---

## Task 13: Shared per-repo walk session wiring

Files: `src/detect/local_channels.py`, `src/detect/git_orchestrator.py`,
`tests/unit/test_detect_local_channels.py`, `tests/unit/test_git_orchestrator.py`.

Requirements:
1. `_scan_one` opens one `RepoWalkSession` per repo (lazily; only when file/history/pr channels are
   active) and closes it in `finally`.
2. `detect_files_local(repo, pack, agents=None, *, session=None)`: read `.gitignore`/probe blobs via
   `session.blob("HEAD:<path>")`; on missing/failure fall back to today's `fetch_blobs` + `read_blobs`
   path. Results identical to today.
3. `detect_history_local(..., session=None)`: when a session is present, build the last-`limit` HEAD
   window via `session.window(resolve_head(repo), limit)` and derive the same `CommitRecord`s and
   `committed_at` map as `read_log` (set semantics; do not change stats shape). Fall back to
   `read_log` on any failure.
4. `detect_pr_commits_local(..., session=None)`: pass the session into
   `walk_windows_with_records` so the PR walk reuses the warmed batch/cache.
5. All new parameters keyword-only with defaults; old call sites (replay script, tests) unchanged.
6. Close failures must not mask scan results (suppress in `finally`).

Tests: file-channel blob read via session; history session path equals `read_log` fixture output;
session close called even on channel failure; old path still works when `session=None`.

Acceptance: focused tests pass.

---

## Task 14: Verification tooling — phase metrics, gate permit knob, replay pack override

Files: `src/detect/git_orchestrator.py`, `src/detect/local_channels.py`,
`scripts/verify_detection_replay.py`, tests as noted.

Requirements:
1. `GitScanConfig.pr_gate_permits: int = 32`; `_run_git_detection_processes` uses it for the
   semaphore. When the serve layer builds configs, default from env `GITCORPUS_PR_GATE` if set.
2. Env-gated per-repo phase metrics: when `GITCORPUS_PHASE_METRICS` names a directory, each worker
   appends one JSON line per repo with `full_name`, `probe_ms`, `clone_ms`, `files_ms`, `history_ms`,
   `pr_listing_ms`, `pr_fetch_ms`, `walk_ms`, `total_ms`, `refs_count`, `gated`, `gate_wait_ms`,
   `cat_file_spawns`. No-op when unset; failures to write must not affect scans.
3. `scripts/verify_detection_replay.py`: add optional `--pack-version` to override the run spec's
   pack for matcher-vs-pack delta measurement; default behaviour unchanged. Print a machine-readable
   summary line (counts of diffs by document key) so V3 can aggregate without parsing diffs.

Tests: config default/env; metrics writer appends valid JSON and is silent when unset; replay script
arg parsing (unit-level if covered, else manual invocation check in the task report).

Acceptance: focused tests pass; metrics file parses with `json.loads` per line.

---

## Task 15: Gate-concurrency sweep (32 vs 64 vs 128)

Files: new `scripts/gate_sweep.py`.

Requirements:
1. Select the 200 highest-stargazer repos from the run's candidate source (reuse
   `detect.orchestrator._candidates` with the source run id used by the last full detection run).
2. For each arm in (32, 64, 128): create a scratch run row, run `run_git_detection` with
   `GitScanConfig(depth=100, keep=False, timeout=1800, workers=64, processes=4,
   pr_gate_permits=arm, scan_root=<temp>/gate-<arm>)`, metrics dir per arm; then: delete the arm's
   evidence/items/run rows in a `finally`; count surviving `git.exe` processes via
   `tasklist /FI "IMAGENAME eq git.exe" /FO CSV` (must be 0); record wall time, repos/min, transient
   and 429 counts from the payload warnings/notes, and aggregate phase metrics (median/p90).
3. Write `<temp>/gate-sweep/report.json` and a human-readable summary; do not print credentials.
4. If a single arm exceeds 60 minutes, stop that arm and record the partial result with a note.

This task's own run is the sweep gate: run all three arms and report numbers in the task report.
Ruling: scratch rows in the local dev DB are acceptable and must be cleaned up.

Acceptance: report.json exists with all three arms (or documented partials), cat-file/git process
count 0 after each arm, transient/429 counts recorded.

---

## Verification V1: Full suite

Run once after Task 15, from the worktree:
- `python -m pytest`
- `python -m ruff check src tests scripts`
- `python -m black --check src tests scripts`
- `python -m mypy`
Report exact results. Any failure goes to the fix loop (one implementer dispatch per failure batch,
then scoped re-review).

## Verification V2: Walk equivalence

Run `scripts/verify_walk_equivalence.py` on `PerryTS/perry`, `charmbracelet/glow`, and a 0-PR corpus
repo (e.g. `arianrhodsandlot/asobou`), depth 100, cap default. Requirement: `mismatches=0`; report
elapsed clone/fetch/walk/verify times and any fallback (`rev-list`) activity visible in the output.

## Verification V3: Detection replay

Run `scripts/verify_detection_replay.py --run-id 99` (and `--run-id 93` if the run row exists) with
and without `--pack-version 2026-10-19`; analyze the diff summary: report (a) repos with genuine
signals lost (must be 0 for email/login-backed agents), (b) prose FP drop counts by agent, (c) ratio
and adoption-level deltas, (d) first_signal_at changes. This is read-only against the DB.

## Verification V4: Final whole-branch review

Dispatch the final code review over `git merge-base main HEAD..HEAD` with the ledger's deferred
minors and parked findings attached.
