#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export CONTROL_PLANE_HOST="${CONTROL_PLANE_HOST:-0.0.0.0}"
export CONTROL_PLANE_PORT="${CONTROL_PLANE_PORT:-3000}"

exec python -m backend.api_gateway.server
