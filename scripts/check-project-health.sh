#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/compose/docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/compose/.env.production}"
LIVE_COMPOSE_PROJECT_NAME="${LIVE_COMPOSE_PROJECT_NAME:-trust0007_live}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "error: $ENV_FILE is missing. Copy compose/.env.production.example to compose/.env.production first." >&2
  exit 1
fi

compose() {
  docker compose --env-file "$ENV_FILE" -p "$LIVE_COMPOSE_PROJECT_NAME" -f "$COMPOSE_FILE" "$@"
}

required_services=(
  control_plane
  db
  keycloak_db
  keycloak
  opa
  qdrant
  vault
  langfuse
)

printf '\n==> Stack status\n'
running_services="$(compose ps --services --filter status=running)"
for service in "${required_services[@]}"; do
  if ! grep -qx "$service" <<<"$running_services"; then
    echo "error: required service '$service' is not running" >&2
    compose ps -a >&2
    exit 1
  fi
done
compose ps -a

printf '\n==> Dashboard health\n'
curl -sSf http://127.0.0.1:3000/api/health
printf '\n'

printf '\n==> Live smoke\n'
ENV_FILE="$ENV_FILE" python "$ROOT_DIR/scripts/smoke-live-onyx-handoff.py" --control-plane-base-url http://127.0.0.1:3000

printf '\n==> Dual-runtime evidence bootstrap\n'
ENV_FILE="$ENV_FILE" python "$ROOT_DIR/scripts/bootstrap_runtime_evidence.py" --control-plane-base-url http://127.0.0.1:3000

printf '\n==> Focused pytest bundle\n'
pytest -q \
  "$ROOT_DIR/tests/dashboard/test_control_plane_dashboard.py" \
  "$ROOT_DIR/tests/integration/test_strict_live_onyx_end_to_end.py" \
  "$ROOT_DIR/tests/integration/test_live_end_to_end.py" \
  "$ROOT_DIR/tests/observability/test_onyx_workspace_activity.py" \
  "$ROOT_DIR/tests/integration/test_live_end_to_end.py"
