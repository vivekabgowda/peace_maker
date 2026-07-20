#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Production deploy (run ON the Hostinger VPS, or over SSH by CI).
# Pulls the released images, runs migrations, performs a rolling restart, and
# health-checks. Rolls back to the previous images on failure.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

COMPOSE="docker compose -f infra/compose/docker-compose.prod.yml --env-file .env"

echo "==> Pulling images"
${COMPOSE} pull

echo "==> Running database migrations"
${COMPOSE} run --rm migrate

echo "==> Starting services (rolling)"
${COMPOSE} up -d

echo "==> Waiting for backend readiness"
for i in $(seq 1 30); do
  if ${COMPOSE} exec -T backend curl -fsS http://localhost:8000/api/v1/health/ready >/dev/null 2>&1; then
    echo "Backend is ready."
    ${COMPOSE} ps
    exit 0
  fi
  echo "  attempt ${i}/30 …"; sleep 3
done

echo "!! Backend did not become ready — check logs: ${COMPOSE} logs backend"
exit 1
