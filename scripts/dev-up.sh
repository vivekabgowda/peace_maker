#!/usr/bin/env bash
# Bring up the local development stack.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "No .env found — creating one from infra/env/.env.dev.example"
  cp infra/env/.env.dev.example .env
fi

docker compose up --build "$@"
