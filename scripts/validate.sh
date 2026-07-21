#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BKN AI Capital — end-to-end validation wrapper.
# Runs the stdlib-only Python validator against the running local stack.
#
#   ./scripts/validate.sh                 # validate http://localhost:8000
#   BKN_BASE_URL=http://host:8000 ./scripts/validate.sh
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "✗ python3 not found on PATH."
  exit 1
fi

exec "$PY" scripts/validate.py
