#!/usr/bin/env bash
set -Eeuo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRUST_DIR="$REPO_ROOT/trust"

cd "$TRUST_DIR"

BOOT_MODE="${TRUST_CODESPACE_BOOT_MODE:-local}"
LOG_DIR="$TRUST_DIR/.devcontainer/.control-plane"
LOG_FILE="$LOG_DIR/codespace-start.log"
PID_FILE="$LOG_DIR/control-plane.pid"

mkdir -p "$LOG_DIR"

health_url="${CONTROL_PLANE_HEALTH_URL:-http://127.0.0.1:3000/api/health}"

is_healthy() {
  curl --silent --show-error --fail --max-time 2 "$health_url" >/dev/null 2>&1
}

if is_healthy; then
  echo "Trust Control Plane is already running: http://127.0.0.1:3000"
  exit 0
fi

if [[ "${BOOT_MODE}" == "none" ]]; then
  echo "TRUST_CODESPACE_BOOT_MODE=none; not auto-starting services."
  echo "Manual run: cd trust && make up-dev"
  exit 0
fi

if [[ "${BOOT_MODE}" == "compose" || "${BOOT_MODE}" == "live" ]]; then
  echo "Starting full Docker Compose stack..."
  make up-dev
  echo "Trust dashboard: http://127.0.0.1:3000"
  exit 0
fi

echo "Starting lightweight local control plane..."

if [[ -f "$PID_FILE" ]]; then
  old_pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$old_pid" ]] && kill -0 "$old_pid" 2>/dev/null; then
    echo "Existing control-plane process still running with PID $old_pid"
    exit 0
  fi
fi

nohup bash scripts/start-control-plane.sh >"$LOG_FILE" 2>&1 &
pid="$!"
echo "$pid" > "$PID_FILE"

for attempt in $(seq 1 30); do
  if is_healthy; then
    echo "Trust Control Plane ready: http://127.0.0.1:3000"
    exit 0
  fi

  if ! kill -0 "$pid" 2>/dev/null; then
    echo "Control Plane exited early. Recent logs:" >&2
    tail -n 80 "$LOG_FILE" >&2 || true
    exit 1
  fi

  sleep 2
done

echo "Control Plane is still starting."
echo "Logs: $LOG_FILE"
echo "Manual check: curl $health_url"
