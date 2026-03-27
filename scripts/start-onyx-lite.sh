#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ONYX_COMPOSE_DIR="$ROOT_DIR/upstream/onyx/deployment/docker_compose"

if [[ ! -d "$ONYX_COMPOSE_DIR" ]]; then
  echo "error: upstream/onyx is not available at $ONYX_COMPOSE_DIR" >&2
  exit 1
fi

cd "$ONYX_COMPOSE_DIR"

if [[ ! -f .env ]]; then
  echo "error: missing $ONYX_COMPOSE_DIR/.env" >&2
  echo "Create it first or let the repository bootstrap generate it." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

host_port="${HOST_PORT:-3000}"
app_url="http://127.0.0.1:${host_port}/"
startup_timeout_seconds="${ONYX_STARTUP_TIMEOUT_SECONDS:-300}"
startup_deadline=$((SECONDS + startup_timeout_seconds))

docker compose \
  -f docker-compose.yml \
  -f docker-compose.onyx-lite.yml \
  -f docker-compose.dev.yml \
  up -d

echo "Waiting for Onyx Lite at ${app_url}"
until curl -fsS -o /dev/null "$app_url"; do
  if (( SECONDS >= startup_deadline )); then
    echo "error: Onyx Lite did not become reachable within ${startup_timeout_seconds}s" >&2
    docker compose \
      -f docker-compose.yml \
      -f docker-compose.onyx-lite.yml \
      -f docker-compose.dev.yml \
      ps >&2
    exit 1
  fi
  sleep 5
done

echo "Onyx Lite is available at ${app_url}"
