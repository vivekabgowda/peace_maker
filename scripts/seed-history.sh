#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BKN AI Capital — seed historical candles (advisory-only, market data).
#
# The Scanner / Recommendations (Alpha Engine) need stored *daily* history for
# the benchmark plus daily+intraday candles for the names they rank. This is a
# one-time (per-day-refreshable) backfill from Zerodha's Historical Data API.
#
# PREREQUISITES:
#   1. You are on the latest code (git pull) and the stack is rebuilt/up.
#   2. You have refreshed today's Kite token:  bash scripts/zerodha-login.sh
#      (backfill needs a valid token; it uses the Historical Chart data add-on.)
#
# USAGE:
#   bash scripts/seed-history.sh
#
# Overrides (optional):
#   BKN_SEED_BENCHMARK   default "NIFTY"
#   BKN_SEED_SYMBOLS     default "RELIANCE TCS INFY HDFCBANK ICICIBANK SBIN"
#   BKN_SEED_DAILY_DAYS  default 400   (calendar days of 1d history)
#   BKN_SEED_INTRA_DAYS  default 45    (calendar days of 5m history)
# ---------------------------------------------------------------------------
set -euo pipefail

BASE="${BKN_API_BASE:-http://localhost:8000/api/v1}"
EMAIL="${BKN_ADMIN_EMAIL:-admin@example.com}"
PASS="${BKN_ADMIN_PASSWORD:-ChangeMe!123}"
BENCHMARK="${BKN_SEED_BENCHMARK:-NIFTY}"
SYMBOLS="${BKN_SEED_SYMBOLS:-RELIANCE TCS INFY HDFCBANK ICICIBANK SBIN}"
DAILY_DAYS="${BKN_SEED_DAILY_DAYS:-400}"
INTRA_DAYS="${BKN_SEED_INTRA_DAYS:-45}"

_login() {
  curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))"
}

_iso_days_ago() {
  python3 -c "from datetime import datetime,timedelta,timezone;print((datetime.now(timezone.utc)-timedelta(days=int('$1'))).strftime('%Y-%m-%dT%H:%M:%S'))"
}
_now_iso() {
  python3 -c "from datetime import datetime,timezone;print(datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S'))"
}
_urlenc() { python3 -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$1"; }

echo "→ Signing in…"
TOKEN="$(_login)"
[ -z "$TOKEN" ] && { echo "✗ Platform login failed (is the stack up?)"; exit 1; }

# Confirm a valid Zerodha token exists before we start.
STATUS="$(curl -s "$BASE/broker/status" -H "Authorization: Bearer $TOKEN")"
if ! echo "$STATUS" | python3 -c "import sys,json;sys.exit(0 if json.load(sys.stdin).get('token_valid') else 1)" 2>/dev/null; then
  echo "✗ No valid Zerodha token. Run:  bash scripts/zerodha-login.sh   then re-run this."
  echo "  status: $STATUS"
  exit 1
fi

END="$(_now_iso)"
START_1D="$(_iso_days_ago "$DAILY_DAYS")"
START_5M="$(_iso_days_ago "$INTRA_DAYS")"

backfill() {
  local sym="$1" tf="$2" start="$3"
  local esym; esym="$(_urlenc "$sym")"
  local resp
  resp="$(curl -s -X POST "$BASE/broker/historical/backfill?symbol=$esym&timeframe=$tf&start=$start&end=$END" \
    -H "Authorization: Bearer $TOKEN")"
  echo "  $sym [$tf]: $resp"
}

echo "→ Benchmark $BENCHMARK (1d, ${DAILY_DAYS}d)…"
backfill "$BENCHMARK" 1d "$START_1D"

echo "→ Watchlist (1d ${DAILY_DAYS}d + 5m ${INTRA_DAYS}d)…"
for s in $SYMBOLS; do
  backfill "$s" 1d "$START_1D"
  backfill "$s" 5m "$START_5M"
done

echo "✓ Backfill done. Reload the Scanner — it should now run."
echo "  (If it still says 'benchmark ... has no daily history', the index symbol"
echo "   differs — check GET $BASE/market/... or tell me and we'll adjust BKN_SEED_BENCHMARK.)"
