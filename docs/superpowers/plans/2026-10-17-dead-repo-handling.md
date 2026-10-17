# Plan: dead/private repos — skip + "unavailable" report (2026-10-17)

Context (detection run 93): cloning a repo deleted/privatized since discovery returns 401/404.
Git then requests credentials; if the serve environment carries `GIT_ASKPASS`/`SSH_ASKPASS`,
a Git-for-Windows askpass dialog pops and blocks that clone (1800s timeout, retried up to 4x).
`GIT_TERMINAL_PROMPT=0` in `gitio.git_env()` does not suppress askpass.

## Changes (to execute later)

1. Harden `src/detect/gitio.py::git_env()` and `src/enrich/cloner.py::_git_env()`:
   set `GIT_ASKPASS=""` and `SSH_ASKPASS=""` so auth-needing git ops fail instantly, no dialog.
   (Verified locally: empty askpass var + terminal prompts disabled → clean
   `fatal: could not read Username ... terminal prompts disabled`, no popup.)
2. Classify clone failures in `src/detect/git_orchestrator.py` (`_scan_one` clone path):
   match stderr for `Repository not found` / `could not read Username` / `Authentication failed`
   → skip retries (pointless + slow), mark the repo `unavailable` with reason `deleted_or_private`.
3. Surface it: `RunPayload.result_summary["unavailable"] = [{full_name, reason}]`, plus a minimal
   "Unavailable" section on the detect run page / `detections.csv`. Full report feature: later.

## Tests

- unit: git env contains empty `GIT_ASKPASS`/`SSH_ASKPASS`; stderr classifier matches sample messages;
  auth-class errors are not retried.
- integration: fake clone raising auth error → scan skipped, counted `unavailable`, run continues.
