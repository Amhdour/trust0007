#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ONYX_COMPOSE_DIR="$ROOT_DIR/upstream/onyx/deployment/docker_compose"
USE_LOCAL_ONYX="${CONTROL_PLANE_USE_LOCAL_ONYX:-false}"

if [[ "${USE_LOCAL_ONYX,,}" != "true" ]]; then
  echo "error: local Onyx startup is disabled by default." >&2
  echo "hint: set CONTROL_PLANE_USE_LOCAL_ONYX=true to use upstream/onyx for local development." >&2
  exit 1
fi

if [[ ! -f "$ONYX_COMPOSE_DIR/docker-compose.yml" ]]; then
  echo "error: upstream/onyx is not available at $ONYX_COMPOSE_DIR" >&2
  echo "hint: use remote Onyx by setting CONTROL_PLANE_ONYX_BASE_URL and CONTROL_PLANE_ONYX_API_BASE_URL." >&2
  exit 1
fi

cd "$ONYX_COMPOSE_DIR"
docker compose up -d
