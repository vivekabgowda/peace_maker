#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BKN AI Capital — one-command local shutdown.
#
#   ./scripts/dev-down.sh          # stop and remove containers (keep data)
#   ./scripts/dev-down.sh --purge  # also delete volumes (Postgres/Redis/n8n data)
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

PURGE=0
for arg in "$@"; do
  case "$arg" in
    --purge|-v) PURGE=1 ;;
  esac
done

if [ "$PURGE" -eq 1 ]; then
  echo "→ Stopping the stack and removing volumes (all local data will be lost)…"
  docker compose down --volumes --remove-orphans
else
  echo "→ Stopping the stack (data volumes preserved)…"
  docker compose down --remove-orphans
fi
echo "✓ Stopped."
