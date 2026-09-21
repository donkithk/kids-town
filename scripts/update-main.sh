#!/usr/bin/env bash
# update-main.sh — reset this checkout to origin/main and restart the demo app.
#
# Safe for a demo machine: kids_town.db (plus WAL/SHM) is copied aside before
# git reset --hard, then restored so player data is not replaced by the
# committed sample DB. requirements.txt is reinstalled only when it changed
# (or when Flask cannot be imported).
#
# Usage:
#   ./scripts/update-main.sh
#   ./scripts/update-main.sh --help
#
# Discards uncommitted code changes. Does not commit the restored DB.

set -euo pipefail

usage() {
  cat <<'EOF'
update-main.sh — fetch + hard-reset to origin/main, keep kids_town.db, restart app

Usage:
  ./scripts/update-main.sh
  ./scripts/update-main.sh -h|--help

Steps (idempotent; safe to re-run):
  1. Copy kids_town.db (+ -wal/-shm) to a temp backup
  2. git fetch origin main && checkout main && git reset --hard origin/main
  3. Restore the backup so the demo DB is not overwritten
  4. pip install -r requirements.txt if the file hash changed or Flask is missing
  5. Stop whatever is listening on 9123, then ./scripts/start-app.sh --background

Does not commit the DB, tokens, or .env. Run from a dedicated demo clone.
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

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "error: $ROOT is not a git checkout" >&2
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

req_hash() {
  if [[ ! -f requirements.txt ]]; then
    echo "missing"
    return 0
  fi
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum requirements.txt | awk '{print $1}'
  else
    shasum -a 256 requirements.txt | awk '{print $1}'
  fi
}

BACKUP_DIR="${TMPDIR:-/tmp}/kids-town-db-preserve"
mkdir -p "$BACKUP_DIR"

backup_db() {
  local f
  for f in kids_town.db kids_town.db-wal kids_town.db-shm; do
    if [[ -e "$ROOT/$f" ]]; then
      cp -a "$ROOT/$f" "$BACKUP_DIR/$f"
      echo "Backed up $f -> $BACKUP_DIR/$f"
    fi
  done
}

restore_db() {
  local f restored=0
  for f in kids_town.db kids_town.db-wal kids_town.db-shm; do
    if [[ -e "$BACKUP_DIR/$f" ]]; then
      cp -a "$BACKUP_DIR/$f" "$ROOT/$f"
      echo "Restored $f from $BACKUP_DIR/$f"
      restored=1
    fi
  done
  if [[ "$restored" -eq 0 ]]; then
    echo "No demo DB backup to restore (fresh checkout is fine)."
  fi
}

pids_on_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
  else
    "$PYTHON" -c '
import os, sys
port = int(sys.argv[1])
# Linux: parse /proc/net/tcp for inode, then map to pid via /proc/*/fd
hexport = format(port, "04X")
inodes = set()
try:
    with open("/proc/net/tcp") as fh:
        next(fh)
        for line in fh:
            parts = line.split()
            if len(parts) < 10:
                continue
            local = parts[1]
            state = parts[3]
            inode = parts[9]
            if state != "0A":
                continue
            if local.split(":")[-1].upper() == hexport:
                inodes.add(inode)
except OSError:
    sys.exit(0)
if not inodes:
    sys.exit(0)
for pid in os.listdir("/proc"):
    if not pid.isdigit():
        continue
    fd_dir = f"/proc/{pid}/fd"
    try:
        for fd in os.listdir(fd_dir):
            try:
                target = os.readlink(os.path.join(fd_dir, fd))
            except OSError:
                continue
            for inode in inodes:
                if target == f"socket:[{inode}]":
                    print(pid)
                    raise StopIteration
    except (OSError, StopIteration):
        pass
' "$port" 2>/dev/null || true
  fi
}

stop_port() {
  local port="$1"
  local pids pid still
  pids="$(pids_on_port "$port" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if [[ -z "$pids" ]]; then
    echo "Nothing listening on $port"
    return 0
  fi
  echo "Stopping PIDs on $port: $pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 1
  still="$(pids_on_port "$port" | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
  if [[ -n "$still" ]]; then
    echo "Force-killing: $still"
    # shellcheck disable=SC2086
    kill -9 $still 2>/dev/null || true
    sleep 0.3
  fi
}

echo "== Backup demo DB =="
backup_db
BEFORE_REQ="$(req_hash)"

echo "== git fetch + reset --hard origin/main =="
git fetch origin main
if git show-ref --verify --quiet refs/heads/main; then
  git checkout main
  git reset --hard origin/main
else
  git checkout -B main origin/main
fi
git status -sb

echo "== Restore demo DB =="
restore_db

AFTER_REQ="$(req_hash)"
NEED_PIP=0
if [[ "$BEFORE_REQ" != "$AFTER_REQ" ]]; then
  echo "requirements.txt changed ($BEFORE_REQ -> $AFTER_REQ)"
  NEED_PIP=1
elif ! "$PYTHON" -c "import flask, flask_cors, bcrypt" >/dev/null 2>&1; then
  echo "Python deps missing; will install requirements.txt"
  NEED_PIP=1
else
  echo "requirements.txt unchanged and Flask imports OK; skip pip"
fi

if [[ "$NEED_PIP" -eq 1 ]]; then
  if [[ ! -f requirements.txt ]]; then
    echo "error: requirements.txt missing after reset" >&2
    exit 1
  fi
  "$PYTHON" -m pip install -r requirements.txt
fi

echo "== Restart app on 9123 =="
stop_port 9123
if [[ -x "$ROOT/scripts/start-app.sh" ]]; then
  "$ROOT/scripts/start-app.sh" --background
else
  echo "warning: scripts/start-app.sh missing on this revision; starting $PYTHON backend_v2.py" >&2
  mkdir -p "$ROOT/logs"
  nohup "$PYTHON" backend_v2.py >>"$ROOT/logs/kids-town-app.log" 2>&1 &
  echo $! >"$ROOT/logs/kids-town.pid"
  echo "pid $!  (no start-app.sh on this revision of main)"
fi

echo "Update complete. Demo DB left unstaged on purpose — do not commit it."
echo "UI: http://127.0.0.1:9123/kids/"
