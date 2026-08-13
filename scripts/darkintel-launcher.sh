#!/usr/bin/env bash
set -euo pipefail

HEALTH_URL="http://127.0.0.1:8000/api/v1/health"
APP_URL="http://127.0.0.1:8000"
SCRIPT_PATH="${BASH_SOURCE[0]}"
if command -v readlink >/dev/null 2>&1; then
  SCRIPT_PATH="$(readlink -f "$SCRIPT_PATH" 2>/dev/null || printf '%s' "$SCRIPT_PATH")"
fi
ROOT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")/.." && pwd -P)"
STATE_DIR="${XDG_STATE_HOME:-${HOME}/.local/state}/darkintel"
LOG_FILE="$STATE_DIR/launcher.log"
PID_FILE="$STATE_DIR/server.pid"
LOCK_DIR="$STATE_DIR/launch.lock"

mkdir -p -- "$STATE_DIR"

message() {
  printf 'DarkIntel: %s\n' "$*" >&2
  if command -v notify-send >/dev/null 2>&1; then
    notify-send "DarkIntel" "$*" >/dev/null 2>&1 || true
  elif command -v zenity >/dev/null 2>&1; then
    zenity --error --title="DarkIntel" --text="$*" >/dev/null 2>&1 || true
  fi
}

health_body() {
  if command -v curl >/dev/null 2>&1; then
    curl --silent --show-error --fail --max-time 2 "$HEALTH_URL" 2>/dev/null
  elif command -v wget >/dev/null 2>&1; then
    wget --quiet --timeout=2 --output-document=- "$HEALTH_URL" 2>/dev/null
  else
    return 2
  fi
}

is_darkintel_healthy() {
  local body
  body="$(health_body)" || return 1
  printf '%s' "$body" | grep -Eq '"product"[[:space:]]*:[[:space:]]*"DarkIntel"'
}

port_is_open() {
  (exec 3<>/dev/tcp/127.0.0.1/8000) >/dev/null 2>&1
}

open_browser() {
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$APP_URL" >/dev/null 2>&1 &
    return 0
  fi
  message "DarkIntel is ready at $APP_URL, but xdg-open is unavailable."
}

if ! command -v curl >/dev/null 2>&1 && ! command -v wget >/dev/null 2>&1; then
  message "curl or wget is required to verify the local DarkIntel health endpoint."
  exit 1
fi

if ! mkdir -- "$LOCK_DIR" 2>/dev/null; then
  if is_darkintel_healthy; then
    open_browser
    exit 0
  fi
  if [[ -f "$LOCK_DIR/pid" ]] && ! kill -0 "$(cat "$LOCK_DIR/pid")" 2>/dev/null; then
    rm -f -- "$LOCK_DIR/pid"
    rmdir -- "$LOCK_DIR" 2>/dev/null || true
    mkdir -- "$LOCK_DIR" 2>/dev/null || {
      message "Another DarkIntel launch is already in progress. Try again shortly."
      exit 1
    }
  else
    message "Another DarkIntel launch is already in progress. Try again shortly."
    exit 1
  fi
fi
printf '%s\n' "$$" >"$LOCK_DIR/pid"
trap 'rm -f -- "$LOCK_DIR/pid"; rmdir -- "$LOCK_DIR" 2>/dev/null || true' EXIT

if is_darkintel_healthy; then
  open_browser
  exit 0
fi
if port_is_open; then
  message "Port 8000 is in use by another application. DarkIntel did not start."
  exit 1
fi

PYTHON="$ROOT_DIR/.venv/bin/python"
if [[ ! -x "$PYTHON" ]]; then
  message "Setup is required: create $ROOT_DIR/.venv and install requirements-dev.txt."
  exit 1
fi

FRONTEND_DIR="$ROOT_DIR/dashboard/frontend"
DIST_INDEX="$FRONTEND_DIR/dist/index.html"
BUILD_REQUIRED=0
if [[ ! -f "$DIST_INDEX" ]]; then
  BUILD_REQUIRED=1
elif find "$FRONTEND_DIR/src" "$FRONTEND_DIR/package.json" "$FRONTEND_DIR/package-lock.json" \
    "$FRONTEND_DIR/index.html" -type f -newer "$DIST_INDEX" -print -quit | grep -q .; then
  BUILD_REQUIRED=1
fi

if [[ "$BUILD_REQUIRED" -eq 1 ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    message "Frontend build is required, but npm is unavailable. Install Node.js/npm and try again."
    exit 1
  fi
  if [[ ! -f "$FRONTEND_DIR/package-lock.json" ]]; then
    message "Frontend build is required, but package-lock.json is missing."
    exit 1
  fi
  {
    printf '\n[%s] Building frontend\n' "$(date -Is)"
    cd -- "$FRONTEND_DIR"
    npm ci
    npm run build
  } >>"$LOG_FILE" 2>&1 || {
    message "Frontend build failed. See $LOG_FILE"
    exit 1
  }
fi

{
  printf '\n[%s] Starting DarkIntel from %s\n' "$(date -Is)" "$ROOT_DIR"
  cd -- "$ROOT_DIR"
  nohup "$PYTHON" main.py dashboard --host 127.0.0.1 --port 8000 >>"$LOG_FILE" 2>&1 &
  printf '%s\n' "$!" >"$PID_FILE"
}

for _attempt in $(seq 1 30); do
  if is_darkintel_healthy; then
    open_browser
    exit 0
  fi
  if [[ -f "$PID_FILE" ]] && ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    break
  fi
  sleep 1
done

message "DarkIntel failed to become ready within 30 seconds. See $LOG_FILE"
exit 1
