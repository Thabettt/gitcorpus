#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${GITCORPUS_PORT:-8000}"

echo "stopping gitcorpus server on port $PORT ..."
lsof -ti:"$PORT" | xargs kill -9 2>/dev/null || echo "no server was running on port $PORT"

echo "starting gitcorpus server ..."
exec "$SCRIPT_DIR/start.sh"
