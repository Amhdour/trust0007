#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ "$#" -gt 0 ]]; then
  ENV_FILES=("$@")
else
  ENV_FILES=("$ROOT_DIR/compose/.env.production" "$ROOT_DIR/.env.live")
fi

for ENV_FILE in "${ENV_FILES[@]}"; do
  if [[ ! -f "$ENV_FILE" ]]; then
    echo "error: live env file not found: $ENV_FILE" >&2
    exit 1
  fi
done

set -a
eval "$(
  python - "${ENV_FILES[@]}" <<'PY'
from pathlib import Path
import shlex
import sys

for raw_path in sys.argv[1:]:
    env_path = Path(raw_path)
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        print(f"export {key}={shlex.quote(value.strip())}")
PY
)"
set +a

required_vars=(
  CONTROL_PLANE_GOVERNANCE_MODE
  CONTROL_PLANE_ENVIRONMENT_MODE
  CONTROL_PLANE_ONYX_SECRET_PATH
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

placeholder_token_values=(
  "replace-with-non-dev-token"
  "replace-me"
  "change-me"
  "changeme"
)

is_placeholder_token() {
  local value="$1"
  local placeholder
  for placeholder in "${placeholder_token_values[@]}"; do
    if [[ "$value" == "$placeholder" ]]; then
      return 0
    fi
  done
  return 1
}

resolve_token_file_on_host() {
  local token_file="$1"
  if [[ -f "$token_file" ]]; then
    printf '%s\n' "$token_file"
    return 0
  fi

  if [[ "$token_file" == /run/control-plane/bootstrap-state/* ]]; then
    printf '%s/.runtime/live-governed/%s\n' "$ROOT_DIR" "${token_file##*/}"
    return 0
  fi

  return 1
}

vault_token="${CONTROL_PLANE_VAULT_TOKEN:-${VAULT_TOKEN:-}}"
vault_token_file="${CONTROL_PLANE_VAULT_TOKEN_FILE:-${VAULT_TOKEN_FILE:-}}"

if [[ -n "$vault_token" ]] && is_placeholder_token "$vault_token"; then
  vault_token=""
fi

if [[ -z "$vault_token" && -n "$vault_token_file" ]]; then
  host_token_file="$(resolve_token_file_on_host "$vault_token_file" || true)"
  if [[ -z "$host_token_file" || ! -f "$host_token_file" ]]; then
    echo "error: live Vault token file not found: ${vault_token_file}" >&2
    exit 1
  fi
  vault_token="$(<"$host_token_file")"
fi

if [[ -z "$vault_token" ]] || is_placeholder_token "$vault_token"; then
  echo "error: set CONTROL_PLANE_VAULT_TOKEN or a valid CONTROL_PLANE_VAULT_TOKEN_FILE before live verification" >&2
  exit 1
fi

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

printf 'live env verification passed:'
for ENV_FILE in "${ENV_FILES[@]}"; do
  printf ' %s' "$ENV_FILE"
done
printf '\n'
