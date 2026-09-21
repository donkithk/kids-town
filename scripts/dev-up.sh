#!/usr/bin/env bash
# dev-up.sh — thin wrapper: ensure the app is up on 9123, then start ngrok.
# Equivalent two-step:  ./scripts/start-app.sh   then   ./scripts/start-ngrok.sh
#
# Usage:
#   export NGROK_AUTHTOKEN=...
#   export NGROK_DOMAIN=moody-faction-spoken.ngrok-free.dev   # optional
#   ./scripts/dev-up.sh
#   ./scripts/dev-up.sh --help

set -euo pipefail

usage() {
  cat <<'EOF'
dev-up.sh — start the local app (if needed) and then the ngrok tunnel

Usage:
  export NGROK_AUTHTOKEN=...           # required by start-ngrok.sh
  export NGROK_DOMAIN=...              # optional reserved domain
  ./scripts/dev-up.sh
  ./scripts/dev-up.sh -h|--help

Two-step equivalent:
  ./scripts/start-app.sh               # or --background
  ./scripts/start-ngrok.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi
if [[ -n "${1:-}" ]]; then
  echo "error: unknown argument: $1 (try --help)" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
else
  PYTHON=python
fi

health_ok() {
  "$PYTHON" -c '
import sys, urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:9123/api/health", timeout=1)
except Exception:
    sys.exit(1)
' >/dev/null 2>&1
}

port_busy() {
  "$PYTHON" -c '
import socket, sys
s = socket.socket()
s.settimeout(0.4)
try:
    busy = s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0
finally:
    s.close()
sys.exit(0 if busy else 1)
' "$1"
}

if health_ok; then
  echo "App already healthy on 9123; skipping start-app.sh"
elif port_busy 9123; then
  echo "error: port 9123 is busy but /api/health failed. Stop the other process first." >&2
  exit 1
else
  "$ROOT/scripts/start-app.sh" --background
fi

exec "$ROOT/scripts/start-ngrok.sh"
