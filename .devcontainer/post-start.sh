#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PORT="${CONTROL_PLANE_PORT:-3000}"
HEALTH_URL="http://127.0.0.1:${PORT}/api/health"
STATE_DIR="$ROOT_DIR/.devcontainer/.control-plane"
LOCK_FILE="$STATE_DIR/start.lock"
PID_FILE="$STATE_DIR/control-plane.pid"
LOG_FILE="$STATE_DIR/control-plane.log"

mkdir -p "$STATE_DIR"

is_healthy() {
  curl --silent --show-error --fail --max-time 2 "$HEALTH_URL" >/dev/null
}

wait_for_health() {
  local attempts="${1:-15}"
  local delay_seconds="${2:-2}"
  local try=1

  while (( try <= attempts )); do
    if is_healthy; then
      return 0
    fi
    sleep "$delay_seconds"
    ((try += 1))
  done

  return 1
}

exec 9>"$LOCK_FILE"
flock 9

if is_healthy; then
  echo "Control plane already available at http://127.0.0.1:${PORT}/"
  exit 0
fi

if [[ -f "$PID_FILE" ]]; then
  existing_pid="$(cat "$PID_FILE")"
  if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
    if wait_for_health 10 2; then
      echo "Control plane became available at http://127.0.0.1:${PORT}/"
      exit 0
    fi

    echo "Control plane process ${existing_pid} is still starting; logs: ${LOG_FILE}"
    exit 0
  fi

  rm -f "$PID_FILE"
fi

nohup bash "$ROOT_DIR/scripts/start-control-plane.sh" >"$LOG_FILE" 2>&1 &
control_plane_pid=$!
echo "$control_plane_pid" >"$PID_FILE"

if wait_for_health 15 2; then
  echo "Control plane available at http://127.0.0.1:${PORT}/"
  exit 0
fi

if kill -0 "$control_plane_pid" 2>/dev/null; then
  echo "Control plane is still starting in the background; logs: ${LOG_FILE}"
  exit 0
fi

echo "Control plane failed to start; recent log output:" >&2
tail -n 40 "$LOG_FILE" >&2 || true
exit 1
