#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# BKN AI Capital — daily Zerodha Kite login (advisory-only, market data).
#
# Kite access tokens expire every morning (~7:30 AM IST). Run this once before
# the market opens to refresh the stored token, then the feed streams live data
# automatically during market hours.
#
#   bash scripts/zerodha-login.sh
#
# Env overrides (optional): BKN_API_BASE, BKN_ADMIN_EMAIL, BKN_ADMIN_PASSWORD.
# ---------------------------------------------------------------------------
set -euo pipefail

BASE="${BKN_API_BASE:-http://localhost:8000/api/v1}"
EMAIL="${BKN_ADMIN_EMAIL:-admin@example.com}"
PASS="${BKN_ADMIN_PASSWORD:-ChangeMe!123}"

_login() {
  curl -s -X POST "$BASE/auth/login" -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
    | python3 -c "import sys,json;print(json.load(sys.stdin).get('access_token',''))"
}

echo "→ Signing in to the platform…"
TOKEN="$(_login)"
[ -z "$TOKEN" ] && { echo "✗ Platform login failed. Is the stack up?  (make up)"; exit 1; }

URL="$(curl -s "$BASE/broker/zerodha/login-url" -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json;print(json.load(sys.stdin).get('login_url',''))")"
[ -z "$URL" ] && { echo "✗ Could not get the Kite login URL (check BKN_ZERODHA_API_KEY)."; exit 1; }

cat <<EOF

1) Open this URL in your browser and log in to Zerodha (with 2FA):

   $URL

2) After login your browser lands on a localhost page that shows an error —
   that is EXPECTED. Look at the address bar and copy the value of
   'request_token' (the text after 'request_token=' up to the next '&').

EOF

printf "3) Paste the request_token here and press Enter: "
read -r REQUEST_TOKEN
[ -z "$REQUEST_TOKEN" ] && { echo "✗ No request_token entered."; exit 1; }

echo "→ Exchanging it for today's access token…"
TOKEN="$(_login)"  # refresh — the platform token may have expired while logging in
RESP="$(curl -s "$BASE/broker/zerodha/callback?request_token=$REQUEST_TOKEN" \
  -H "Authorization: Bearer $TOKEN")"
echo "$RESP"

if echo "$RESP" | python3 -c "import sys,json;sys.exit(0 if json.load(sys.stdin).get('valid') else 1)" 2>/dev/null; then
  echo "✓ Zerodha connected for today."
else
  echo "⚠ Token exchange did not report valid — see the response above."
  echo "  If it says the token expired, just re-run this script (they last ~2 min)."
  exit 1
fi

echo "→ Restarting the feed to pick up the fresh token…"
docker compose restart feed >/dev/null
echo "✓ Done. During market hours (9:15 AM–3:30 PM IST) the feed connects and"
echo "  streams live data automatically; outside those hours it stays idle."
