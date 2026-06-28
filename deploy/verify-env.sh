#!/bin/bash
# Check .env + Supabase tables — VPS: bash deploy/verify-env.sh
set -euo pipefail

ENV_FILE="${1:-/root/hassanaiagent/.env}"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

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
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY is empty"
  exit 1
fi

len=${#SRK}
if [[ "$len" -lt 120 ]]; then
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY too short ($len chars) — truncated"
  exit 1
fi

if [[ "$SRK" == *">"* ]] || [[ "$SRK" == *"PASTE_"* ]]; then
  echo "ERROR: SUPABASE_SERVICE_ROLE_KEY still placeholder or has >"
  exit 1
fi

dots=$(grep -o '\.' <<< "$SRK" | wc -l)
if [[ "$dots" -ne 2 ]]; then
  echo "ERROR: JWT must have exactly 2 dots"
  exit 1
fi

echo "OK:   SUPABASE_SERVICE_ROLE_KEY length=$len"

if [[ -z "$GEM" ]] || [[ "$GEM" == *"PASTE_"* ]]; then
  echo "WARN: GEMINI_API_KEY not set — add in Settings or .env"
else
  echo "OK:   GEMINI_API_KEY set"
fi

echo ""
echo "==> Restarting hassan-ai"
sudo systemctl restart hassan-ai
sleep 2

echo ""
echo "==> Health check"
HEALTH=$(curl -sf "http://127.0.0.1:8080/api/health" || true)
if [[ -z "$HEALTH" ]]; then
  echo "ERROR: No response from /api/health"
  echo "Run: journalctl -u hassan-ai -n 30 --no-pager"
  exit 1
fi

echo "$HEALTH" | python3 -m json.tool

STORAGE=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('chat_storage',''))")
READY=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('supabase_ready', False))")
ERR=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('supabase_error',''))")

echo ""
if [[ "$STORAGE" != "supabase" ]] || [[ "$READY" != "True" ]]; then
  echo "ERROR: Supabase tables NOT ready (still on SQLite)."
  echo "Reason: $ERR"
  echo ""
  echo "FIX — run SQL once in Supabase Dashboard:"
  echo "  https://supabase.com/dashboard/project/nbfzdezmvggmmvhkkvbt/sql/new"
  echo ""
  echo "Paste contents of: $APP_DIR/supabase/setup_all.sql"
  echo "Or on VPS: cat $APP_DIR/supabase/setup_all.sql"
  echo ""
  echo "After SQL succeeds, run again:"
  echo "  bash deploy/verify-env.sh"
  exit 1
fi

echo "All checks passed — chat memory is on Supabase."
