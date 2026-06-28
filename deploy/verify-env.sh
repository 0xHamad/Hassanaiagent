#!/bin/bash
# Check .env before restart — run on VPS: bash deploy/verify-env.sh
set -euo pipefail

ENV_FILE="${1:-/root/hassanaiagent/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: $ENV_FILE not found"
  echo "Run: cp deploy/vps.env .env && nano .env"
  exit 1
fi

echo "==> Checking $ENV_FILE"

get_val() {
  grep -E "^${1}=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\r' || true
}

URL=$(get_val SUPABASE_URL)
SRK=$(get_val SUPABASE_SERVICE_ROLE_KEY)
GEM=$(get_val GEMINI_API_KEY)

if [[ -z "$URL" ]]; then
  echo "WARN: SUPABASE_URL is empty — app will use local SQLite"
else
  echo "OK:   SUPABASE_URL=$URL"
fi

if [[ -z "$SRK" ]]; then
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY is empty — paste full JWT from Supabase Dashboard → API"
  exit 1
fi

len=${#SRK}
if [[ "$len" -lt 120 ]]; then
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY too short ($len chars) — key is truncated. Paste FULL key on one line."
  exit 1
fi

if [[ "$SRK" == *">"* ]] || [[ "$SRK" == *"PASTE_"* ]]; then
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY still has placeholder or > character — paste real key"
  exit 1
fi

dots=$(grep -o '\.' <<< "$SRK" | wc -l)
if [[ "$dots" -ne 2 ]]; then
  echo "ERROR: JWT must have exactly 2 dots (header.payload.signature)"
  exit 1
fi

echo "OK:   SUPABASE_SERVICE_ROLE_KEY length=$len"

if [[ -z "$GEM" ]] || [[ "$GEM" == *"PASTE_"* ]]; then
  echo "WARN: GEMINI_API_KEY not set — users must add key in Settings"
else
  echo "OK:   GEMINI_API_KEY set"
fi

echo ""
echo "==> Service status"
systemctl is-active hassan-ai 2>/dev/null || echo "hassan-ai not running"

echo ""
echo "==> Health (after restart)"
curl -sf "http://127.0.0.1:8080/api/health" | python3 -m json.tool 2>/dev/null || {
  echo "Health check failed — run: journalctl -u hassan-ai -n 25 --no-pager"
  exit 1
}

echo ""
echo "All checks passed."
