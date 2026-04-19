#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.live}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "error: live env file not found: $ENV_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

required_vars=(
  CONTROL_PLANE_GOVERNANCE_MODE
  CONTROL_PLANE_ENVIRONMENT_MODE
  CONTROL_PLANE_VAULT_TOKEN
  CONTROL_PLANE_ONYX_SECRET_PATH
  CONTROL_PLANE_DIFY_SECRET_PATH
  CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS
  CONTROL_PLANE_EXTERNAL_REACHABLE
  CONTROL_PLANE_KEYCLOAK_DEV_MODE
  CONTROL_PLANE_VAULT_DEV_MODE
)

for name in "${required_vars[@]}"; do
  if [[ -z "${!name:-}" ]]; then
    echo "error: required live variable missing: $name" >&2
    exit 1
  fi
done

if [[ "${CONTROL_PLANE_GOVERNANCE_MODE}" != "live" ]]; then
  echo "error: CONTROL_PLANE_GOVERNANCE_MODE must be live" >&2
  exit 1
fi
if [[ "${CONTROL_PLANE_ENVIRONMENT_MODE}" == "dev" || "${CONTROL_PLANE_ENVIRONMENT_MODE}" == "local" ]]; then
  echo "error: CONTROL_PLANE_ENVIRONMENT_MODE must not be dev/local for live verification" >&2
  exit 1
fi
if [[ "${CONTROL_PLANE_KEYCLOAK_DEV_MODE}" == "true" ]]; then
  echo "error: CONTROL_PLANE_KEYCLOAK_DEV_MODE cannot be true in live mode" >&2
  exit 1
fi
if [[ "${CONTROL_PLANE_VAULT_DEV_MODE}" == "true" ]]; then
  echo "error: CONTROL_PLANE_VAULT_DEV_MODE cannot be true in live mode" >&2
  exit 1
fi

echo "live env verification passed: $ENV_FILE"
