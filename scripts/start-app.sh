#!/usr/bin/env bash
# start-app.sh — start the Kids Town Flask backend (backend_v2.py) on port 9123.
#
# Serves /kids/ and /api/health. Uses repo-root .venv when present.
# Refuses to start if 9123 is already bound.
#
# Usage:
#   ./scripts/start-app.sh              # foreground; logs to stdout
#   ./scripts/start-app.sh --background # daemonize; logs to logs/kids-town-app.log
#   ./scripts/start-app.sh --help
#
# Environment:
#   KIDS_TOWN_LOG   log file when --background (default: <repo>/logs/kids-town-app.log)
#
# Never commit .env, tokens, or a machine-local kids_town.db.

set -euo pipefail

usage() {
  cat <<'EOF'
start-app.sh — start Kids Town on http://127.0.0.1:9123

Usage:
  ./scripts/start-app.sh              Foreground (stdout). Ctrl+C stops the app.
  ./scripts/start-app.sh --background Background; log + pid under logs/.
  ./scripts/start-app.sh -h|--help    This help.

Looks for .venv in the repo root and activates it when present.
Entry point: backend_v2.py (same as README). Port: 9123.
Exits with an error if something is already listening on 9123.

UI:     http://127.0.0.1:9123/kids/
Health: http://127.0.0.1:9123/api/health
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

PORT=9123
ENTRY="backend_v2.py"
BACKGROUND=0
if [[ "${1:-}" == "--background" ]]; then
  BACKGROUND=1
  shift
fi
if [[ -n "${1:-}" ]]; then
  echo "error: unknown argument: $1 (try --help)" >&2
  exit 2
fi

if [[ ! -f "$ENTRY" ]]; then
  echo "error: $ENTRY not found in $ROOT (run from the kids-town repo)" >&2
  exit 1
fi

if [[ -f "$ROOT/.venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source "$ROOT/.venv/bin/activate"
  echo "Using virtualenv $ROOT/.venv"
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "error: python3 not found" >&2
  exit 1
fi

if ! "$PYTHON" -c "import flask" >/dev/null 2>&1; then
  echo "error: Flask is not installed for $($PYTHON -c 'import sys; print(sys.executable)')." >&2
  echo "  python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt" >&2
  exit 1
fi

port_busy() {
  "$PYTHON" -c '
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.4)
try:
    busy = s.connect_ex(("127.0.0.1", port)) == 0
finally:
    s.close()
sys.exit(0 if busy else 1)
' "$1"
}

if port_busy "$PORT"; then
  echo "error: port $PORT is already in use; refuse to start a second backend." >&2
  echo "  UI / health would be ambiguous. Stop the other process, then retry." >&2
  if command -v lsof >/dev/null 2>&1; then
    echo "  listeners:" >&2
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >&2 || true
  fi
  exit 1
fi

mkdir -p "$ROOT/logs"
LOG="${KIDS_TOWN_LOG:-$ROOT/logs/kids-town-app.log}"
PIDFILE="$ROOT/logs/kids-town.pid"

wait_health() {
  local i
  for i in $(seq 1 40); do
    if "$PYTHON" -c '
import sys, urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:9123/api/health", timeout=1)
except Exception:
    sys.exit(1)
' >/dev/null 2>&1; then
      return 0
    fi
    sleep 0.25
  done
  return 1
}

echo "Starting $ENTRY on port $PORT (cwd=$ROOT)"

if [[ "$BACKGROUND" -eq 1 ]]; then
  nohup "$PYTHON" "$ENTRY" >>"$LOG" 2>&1 &
  echo $! >"$PIDFILE"
  echo "pid $(cat "$PIDFILE")  log $LOG"
  if wait_health; then
    echo "Ready  http://127.0.0.1:${PORT}/kids/   http://127.0.0.1:${PORT}/api/health"
    exit 0
  fi
  echo "error: backend started but /api/health did not respond; see $LOG" >&2
  exit 1
fi

echo "Logging to stdout. UI http://127.0.0.1:${PORT}/kids/"
exec "$PYTHON" "$ENTRY"
