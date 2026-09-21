#!/usr/bin/env bash
# start-ngrok.sh — expose local Kids Town (port 9123) via ngrok.
#
# Required:  NGROK_AUTHTOKEN in the environment (never commit it).
# Optional:  NGROK_DOMAIN — reserved/static hostname. Example only (do not treat
#            as a secret, and do not commit tokens):
#              moody-faction-spoken.ngrok-free.dev
#            When unset, ngrok assigns a random free URL.
#
# Usage:
#   export NGROK_AUTHTOKEN=...
#   export NGROK_DOMAIN=moody-faction-spoken.ngrok-free.dev   # optional
#   ./scripts/start-ngrok.sh
#   ./scripts/start-ngrok.sh --help
#
# Prints the public https URL once the tunnel is up, then stays in the foreground.

set -euo pipefail

usage() {
  cat <<'EOF'
start-ngrok.sh — tunnel http://127.0.0.1:9123 to a public ngrok URL

Usage:
  export NGROK_AUTHTOKEN=xxxxxxxx        # required; never commit
  export NGROK_DOMAIN=example.ngrok-free.dev   # optional reserved domain
  ./scripts/start-ngrok.sh
  ./scripts/start-ngrok.sh -h|--help

When NGROK_DOMAIN is set:
  ngrok http 9123 --domain="$NGROK_DOMAIN"
Otherwise:
  ngrok http 9123          # random free URL

Example reserved domain (documentation only, not a token):
  moody-faction-spoken.ngrok-free.dev

The script reads NGROK_AUTHTOKEN from the environment only. It does not write
credentials into the repo or into a committed config file.
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

PORT=9123

if [[ -z "${NGROK_AUTHTOKEN:-}" ]]; then
  echo "error: NGROK_AUTHTOKEN is not set." >&2
  echo "  export NGROK_AUTHTOKEN=...   # from the ngrok dashboard; never commit" >&2
  exit 1
fi

if ! command -v ngrok >/dev/null 2>&1; then
  echo "error: ngrok is not on PATH. Install https://ngrok.com/download then retry." >&2
  exit 1
fi

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "error: python3 not found (needed to read the ngrok local API)" >&2
  exit 1
fi

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

if ! port_busy "$PORT"; then
  echo "warning: nothing is listening on $PORT. Start the app first:" >&2
  echo "  ./scripts/start-app.sh" >&2
fi

mkdir -p "$ROOT/logs"
NGROK_LOG="${NGROK_LOG:-$ROOT/logs/ngrok.log}"
: >"$NGROK_LOG"

# Env token only — do not `ngrok config add-authtoken` (that writes ~/.config).
cmd=(ngrok http "$PORT" --log=stdout --log-format=logfmt)
if [[ -n "${NGROK_DOMAIN:-}" ]]; then
  echo "Using reserved domain $NGROK_DOMAIN"
  cmd+=(--domain="$NGROK_DOMAIN")
else
  echo "No NGROK_DOMAIN set; requesting a random free URL"
fi
echo "Running: ${cmd[*]}"

"${cmd[@]}" >>"$NGROK_LOG" 2>&1 &
NGROK_PID=$!
cleanup() {
  if kill -0 "$NGROK_PID" 2>/dev/null; then
    kill "$NGROK_PID" 2>/dev/null || true
    wait "$NGROK_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

read_public_url() {
  "$PYTHON" -c '
import json, sys, urllib.request
try:
    with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1) as r:
        data = json.load(r)
except Exception:
    sys.exit(1)
urls = [t.get("public_url") or "" for t in (data.get("tunnels") or [])]
https = [u for u in urls if u.startswith("https://")]
picked = (https[0] if https else (urls[0] if urls else ""))
if not picked:
    sys.exit(1)
print(picked)
'
}

url=""
for _ in $(seq 1 40); do
  if ! kill -0 "$NGROK_PID" 2>/dev/null; then
    echo "error: ngrok exited before the tunnel came up. Last log lines:" >&2
    tail -n 20 "$NGROK_LOG" >&2 || true
    exit 1
  fi
  if url="$(read_public_url 2>/dev/null)"; then
    break
  fi
  url=""
  sleep 0.25
done

if [[ -z "$url" ]]; then
  echo "error: timed out waiting for ngrok public URL (inspect $NGROK_LOG and http://127.0.0.1:4040)" >&2
  tail -n 20 "$NGROK_LOG" >&2 || true
  exit 1
fi

echo
echo "Public URL: $url"
echo "Kids UI:    ${url%/}/kids/"
echo "Health:     ${url%/}/api/health"
echo "ngrok log:  $NGROK_LOG"
echo
echo "Leave this process running. Ctrl+C stops the tunnel."

# Keep the tunnel in the foreground; trap will stop ngrok on exit.
wait "$NGROK_PID"
# If ngrok exits on its own, surface that as failure.
exit 1
