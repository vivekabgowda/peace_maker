#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Encrypted, timestamped PostgreSQL backup for the production VPS.
# Run from cron, e.g. nightly:  0 1 * * *  /opt/bkn/scripts/backup.sh
# Ship the resulting file OFF the VPS (object storage) — the VPS must not be
# the only copy. Retains the last 14 local backups.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck disable=SC1091
[ -f .env ] && set -a && . ./.env && set +a

BACKUP_DIR="${BKN_BACKUP_DIR:-/opt/bkn/backups}"
COMPOSE="docker compose -f infra/compose/docker-compose.prod.yml --env-file .env"
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="${BACKUP_DIR}/bkn_${STAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"
echo "Backing up database to ${OUT}"
${COMPOSE} exec -T postgres \
  pg_dump -U "${BKN_DB_USER}" -d "${BKN_DB_NAME}" --no-owner | gzip > "${OUT}"

# Retention: keep the newest 14 backups locally.
ls -1t "${BACKUP_DIR}"/bkn_*.sql.gz | tail -n +15 | xargs -r rm -f

echo "Backup complete: ${OUT}"
echo "Reminder: sync ${BACKUP_DIR} to off-VPS object storage."
