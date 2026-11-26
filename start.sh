#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

export DATABASE_URL=postgresql+psycopg://gitcorpus:gitcorpus@localhost:5433/gitcorpus
export REDIS_URL=redis://localhost:6379/0
export PYTHONPATH="$SCRIPT_DIR/src"

# Load all variables from .env (GITHUB_TOKEN, GITHUB_TOKENS, etc.) if present.
if [[ -f "$SCRIPT_DIR/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$SCRIPT_DIR/.env"
  set +a
fi

if [[ -z "${GITHUB_TOKEN:-}" && -z "${GITHUB_TOKENS:-}" ]]; then
  echo "ERROR: neither GITHUB_TOKEN nor GITHUB_TOKENS is set. Add one to .env or export it before running."
  exit 1
fi

exec "$SCRIPT_DIR/.venv/bin/python" -m serve
