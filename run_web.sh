#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR/web" || exit 1
PY="$DIR/venv/bin/python"
[ -x "$PY" ] || PY="python3"
exec "$PY" -m uvicorn app:app --host 0.0.0.0 --port "${PORT:-8080}" --reload
