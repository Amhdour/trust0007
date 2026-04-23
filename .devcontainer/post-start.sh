#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BOOT_MODE="${CODEX_DEVCONTAINER_BOOT_MODE:-auto}" # auto|live|local
LIVE_ENV_FILE="${ENV_FILE:-$ROOT_DIR/.env.live}"
LIVE_BASE_ENV_FILE="${LIVE_BASE_ENV_FILE:-$ROOT_DIR/compose/.env.production}"
LIVE_COMPOSE_PROJECT_NAME="${LIVE_COMPOSE_PROJECT_NAME:-trust0007_live}"
LIVE_CONTROL_PLANE_BASE_URL="${CONTROL_PLANE_BASE_URL:-http://127.0.0.1:3000}"

STATE_DIR="$ROOT_DIR/.devcontainer/.control-plane"
LOCK_FILE="$STATE_DIR/start.lock"
LOCAL_PID_FILE="$STATE_DIR/control-plane.pid"
LOCAL_LOG_FILE="$STATE_DIR/control-plane.log"
LIVE_LOG_FILE="$STATE_DIR/live-bootstrap.log"
LIVE_STAMP_FILE="$STATE_DIR/live-bootstrap.last-success"

mkdir -p "$STATE_DIR"

if [[ -n "${ENV_FILES:-}" ]]; then
  IFS=":" read -r -a LIVE_ENV_FILES <<<"$ENV_FILES"
else
  LIVE_ENV_FILES=()
  if [[ -f "$LIVE_BASE_ENV_FILE" ]]; then
    LIVE_ENV_FILES+=("$LIVE_BASE_ENV_FILE")
  fi
  if [[ -f "$LIVE_ENV_FILE" && "$LIVE_ENV_FILE" != "$LIVE_BASE_ENV_FILE" ]]; then
    LIVE_ENV_FILES+=("$LIVE_ENV_FILE")
  fi
fi

if [[ -n "${COMPOSE_FILES:-}" ]]; then
  IFS=":" read -r -a LIVE_COMPOSE_FILES <<<"$COMPOSE_FILES"
elif [[ -n "${COMPOSE_FILE:-}" ]]; then
  IFS=":" read -r -a LIVE_COMPOSE_FILES <<<"$COMPOSE_FILE"
else
  LIVE_COMPOSE_FILES=(
    "$ROOT_DIR/compose/docker-compose.production.yml"
    "$ROOT_DIR/compose/docker-compose.live.yml"
  )
fi

join_by_colon() {
  local IFS=":"
  echo "$*"
}

live_env_available() {
  local env_file
  for env_file in "${LIVE_ENV_FILES[@]}"; do
    if [[ -f "$env_file" ]]; then
      return 0
    fi
  done
  return 1
}

compose_live() {
  local args=()
  local env_file compose_file
  for env_file in "${LIVE_ENV_FILES[@]}"; do
    args+=(--env-file "$env_file")
  done
  args+=(-p "$LIVE_COMPOSE_PROJECT_NAME")
  for compose_file in "${LIVE_COMPOSE_FILES[@]}"; do
    args+=(-f "$compose_file")
  done
  docker compose "${args[@]}" "$@"
}

is_dashboard_healthy() {
  curl --silent --show-error --fail --max-time 2 "$LIVE_CONTROL_PLANE_BASE_URL/api/health" >/dev/null
}

wait_for_dashboard_health() {
  local attempts="${1:-15}"
  local delay_seconds="${2:-2}"
  local try=1

  while (( try <= attempts )); do
    if is_dashboard_healthy; then
      return 0
    fi
    sleep "$delay_seconds"
    ((try += 1))
  done

  return 1
}

live_services_running() {
  local running
  running="$(compose_live ps --services --filter status=running 2>/dev/null || true)"
  local required_services=(
    control_plane
    keycloak
    opa
    qdrant
    vault
    onyx_runtime
    dify_runtime
  )
  local service
  for service in "${required_services[@]}"; do
    if ! grep -qx "$service" <<<"$running"; then
      return 1
    fi
  done
  return 0
}

live_evidence_ready() {
  python - "$LIVE_CONTROL_PLANE_BASE_URL" <<'PY'
from __future__ import annotations

import json
import sys
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

base = sys.argv[1].rstrip("/")
required = [
    "governed-flow-summary.json",
    "identity-evidence.json",
    "policy-evidence.json",
    "retrieval-evidence.json",
    "secret-evidence.json",
    "launch-gate-result.json",
    "onyx-runtime-proof.json",
    "dify-runtime-proof.json",
]
def fetch(name: str) -> dict:
    url = f"{base}/raw/overlays/myStarterKit/artifacts/{quote(name)}"
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))

try:
    for name in required:
        fetch(name)
    summary = fetch("governed-flow-summary.json")
except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ValueError):
    raise SystemExit(1)

if summary.get("evidence_mode") != "live":
    raise SystemExit(1)
if summary.get("handoff_allowed") is not True:
    raise SystemExit(1)
if summary.get("launch_gate", {}).get("decision") != "pass":
    raise SystemExit(1)
PY
}

live_stack_ready() {
  live_services_running && is_dashboard_healthy && live_evidence_ready
}

start_local_control_plane() {
  local port health_url existing_pid
  port="${CONTROL_PLANE_PORT:-3000}"
  health_url="http://127.0.0.1:${port}/api/health"

  is_local_healthy() {
    curl --silent --show-error --fail --max-time 2 "$health_url" >/dev/null
  }

  wait_for_local_health() {
    local attempts="${1:-15}"
    local delay_seconds="${2:-2}"
    local try=1
    while (( try <= attempts )); do
      if is_local_healthy; then
        return 0
      fi
      sleep "$delay_seconds"
      ((try += 1))
    done
    return 1
  }

  if is_local_healthy; then
    echo "Control plane already available at http://127.0.0.1:${port}/"
    return 0
  fi

  if [[ -f "$LOCAL_PID_FILE" ]]; then
    existing_pid="$(cat "$LOCAL_PID_FILE")"
    if [[ -n "$existing_pid" ]] && kill -0 "$existing_pid" 2>/dev/null; then
      if wait_for_local_health 10 2; then
        echo "Control plane became available at http://127.0.0.1:${port}/"
        return 0
      fi

      echo "Control plane process ${existing_pid} is still starting; logs: ${LOCAL_LOG_FILE}"
      return 0
    fi

    rm -f "$LOCAL_PID_FILE"
  fi

  nohup bash "$ROOT_DIR/scripts/start-control-plane.sh" >"$LOCAL_LOG_FILE" 2>&1 &
  local control_plane_pid=$!
  echo "$control_plane_pid" >"$LOCAL_PID_FILE"

  if wait_for_local_health 15 2; then
    echo "Control plane available at http://127.0.0.1:${port}/"
    return 0
  fi

  if kill -0 "$control_plane_pid" 2>/dev/null; then
    echo "Control plane is still starting in the background; logs: ${LOCAL_LOG_FILE}"
    return 0
  fi

  echo "Control plane failed to start; recent log output:" >&2
  tail -n 40 "$LOCAL_LOG_FILE" >&2 || true
  return 1
}

run_live_bootstrap() {
  : >"$LIVE_LOG_FILE"
  echo "Bootstrapping live governed stack (Onyx + Dify). Logs: $LIVE_LOG_FILE"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] bootstrap-live-governed-path: start" >>"$LIVE_LOG_FILE"
  if ! ENV_FILES="$(join_by_colon "${LIVE_ENV_FILES[@]}")" \
    COMPOSE_FILES="$(join_by_colon "${LIVE_COMPOSE_FILES[@]}")" \
    LIVE_COMPOSE_PROJECT_NAME="$LIVE_COMPOSE_PROJECT_NAME" \
    ENV_FILE="$LIVE_ENV_FILE" \
    CONTROL_PLANE_BASE_URL="$LIVE_CONTROL_PLANE_BASE_URL" \
      bash "$ROOT_DIR/scripts/bootstrap-live-governed-path.sh" >>"$LIVE_LOG_FILE" 2>&1; then
    return 1
  fi

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] bootstrap_runtime_evidence: start" >>"$LIVE_LOG_FILE"
  if ! python "$ROOT_DIR/scripts/bootstrap_runtime_evidence.py" \
    --control-plane-base-url "$LIVE_CONTROL_PLANE_BASE_URL" >>"$LIVE_LOG_FILE" 2>&1; then
    return 1
  fi

  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] live bootstrap completed" >>"$LIVE_LOG_FILE"
  date -u +%Y-%m-%dT%H:%M:%SZ >"$LIVE_STAMP_FILE"
}

cleanup_known_port_conflicts() {
  local container_ports
  container_ports="$(docker ps --format '{{.Names}} {{.Ports}}')"
  if grep -Eq '^onyx-web_server-1 .+:3010->' <<<"$container_ports"; then
    echo "Stopping legacy container onyx-web_server-1 to free host port 3010 for compose onyx_runtime."
    docker rm -f onyx-web_server-1 >/dev/null 2>&1 || true
  fi
  if grep -Eq '^onyx-nginx-1 .+:3010->' <<<"$container_ports"; then
    echo "Stopping legacy container onyx-nginx-1 to free host port 3010 for compose onyx_runtime."
    docker rm -f onyx-nginx-1 >/dev/null 2>&1 || true
  fi
  if grep -Eq '^governed-dify-web .+:8088->' <<<"$container_ports"; then
    echo "Stopping legacy container governed-dify-web to free host port 8088 for compose dify_runtime."
    docker rm -f governed-dify-web >/dev/null 2>&1 || true
  fi
}

resolve_boot_mode() {
  case "$BOOT_MODE" in
    live|local)
      echo "$BOOT_MODE"
      ;;
    auto)
      if live_env_available; then
        echo "live"
      else
        echo "local"
      fi
      ;;
    *)
      echo "error: unsupported CODEX_DEVCONTAINER_BOOT_MODE '$BOOT_MODE' (expected auto|live|local)" >&2
      exit 1
      ;;
  esac
}

exec 9>"$LOCK_FILE"
flock 9

selected_mode="$(resolve_boot_mode)"
if [[ "$selected_mode" == "local" ]]; then
  start_local_control_plane
  exit $?
fi

if ! live_env_available; then
  echo "warning: live boot requested but no live env file is available." >&2
  echo "warning: falling back to local control-plane startup." >&2
  start_local_control_plane
  exit $?
fi

if live_stack_ready; then
  echo "Live governed stack already ready at ${LIVE_CONTROL_PLANE_BASE_URL}/"
  if [[ -f "$LIVE_STAMP_FILE" ]]; then
    echo "Last successful live bootstrap: $(cat "$LIVE_STAMP_FILE")"
  fi
  exit 0
fi

cleanup_known_port_conflicts
if run_live_bootstrap && wait_for_dashboard_health 30 2 && live_stack_ready; then
  echo "Live governed stack ready at ${LIVE_CONTROL_PLANE_BASE_URL}/"
  echo "Onyx and Dify runtime evidence refreshed for the dashboard."
  exit 0
fi

echo "Live governed bootstrap failed or remains incomplete. Recent log output:" >&2
tail -n 60 "$LIVE_LOG_FILE" >&2 || true
exit 1
