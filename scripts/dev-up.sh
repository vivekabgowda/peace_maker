#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BKN AI Capital — one-command local startup (macOS / Linux, Docker Desktop).
#
#   ./scripts/dev-up.sh            # build, start, wait for health, print URLs
#   ./scripts/dev-up.sh --logs     # start, then tail logs in the foreground
#
# Brings up Postgres(+TimescaleDB), Redis, the API, the market feed, the
# frontend, and n8n. Database migrations run automatically inside the backend
# container on startup (alembic upgrade head).
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

FOLLOW_LOGS=0
for arg in "$@"; do
  case "$arg" in
    --logs) FOLLOW_LOGS=1 ;;
  esac
done

if ! docker info >/dev/null 2>&1; then
  echo "✗ Docker is not running. Start Docker Desktop and retry."
  exit 1
fi

if [ ! -f .env ]; then
  echo "→ No .env found — creating one from infra/env/.env.dev.example"
  cp infra/env/.env.dev.example .env
fi

echo "→ Building and starting the stack (migrations run automatically)…"
# --wait blocks until every service with a healthcheck is healthy (or fails).
docker compose up --build --detach --wait --wait-timeout 240 || {
  echo "✗ One or more services did not become healthy. Recent state + logs:"
  docker compose ps
  docker compose logs --tail=40
  exit 1
}

cat <<'EOF'

✓ BKN AI Capital is up.

  Frontend            http://localhost:3000
  Diagnostics page    http://localhost:3000/diagnostics
  API (docs)          http://localhost:8000/docs
  API health          http://localhost:8000/api/v1/health/ready
  Diagnostics (API)   http://localhost:8000/api/v1/health/diagnostics
  Feed health         http://localhost:8001/health/live
  n8n (automation)    http://localhost:5678

  Paper trading       POST http://localhost:8000/api/v1/paper/orders
  Analytics summary   GET  http://localhost:8000/api/v1/analytics/summary
  Weekly report       GET  http://localhost:8000/api/v1/analytics/reports/latest?kind=weekly

  Validate end-to-end:  ./scripts/validate.sh
  Stop the stack:       ./scripts/dev-down.sh
EOF

if [ "$FOLLOW_LOGS" -eq 1 ]; then
  echo
  echo "→ Tailing logs (Ctrl-C to stop; the stack keeps running)…"
  docker compose logs -f
fi
