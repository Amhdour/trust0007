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
    echo "error: remote Onyx env file not found: $ENV_FILE" >&2
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

use_local_onyx="${CONTROL_PLANE_USE_LOCAL_ONYX:-false}"
use_local_onyx="$(printf '%s' "$use_local_onyx" | tr '[:upper:]' '[:lower:]')"

if [[ "$use_local_onyx" == "true" || "$use_local_onyx" == "1" || "$use_local_onyx" == "yes" ]]; then
  echo "remote Onyx verification skipped: CONTROL_PLANE_USE_LOCAL_ONYX=true"
  exit 0
fi

base_url="${CONTROL_PLANE_ONYX_BASE_URL:-}"
api_url="${CONTROL_PLANE_ONYX_API_BASE_URL:-}"

if [[ -z "$base_url" ]]; then
  echo "error: CONTROL_PLANE_ONYX_BASE_URL must be set for remote Onyx mode" >&2
  exit 1
fi
if [[ -z "$api_url" ]]; then
  echo "error: CONTROL_PLANE_ONYX_API_BASE_URL must be set for remote Onyx mode" >&2
  exit 1
fi

if [[ "$base_url" == *"/workspaces/"* || "$base_url" == *"/workspaces/trust0007/upstream/onyx"* ]]; then
  echo "error: CONTROL_PLANE_ONYX_BASE_URL must be an HTTPS URL, not a filesystem path: $base_url" >&2
  exit 1
fi
if [[ "$api_url" == *"/workspaces/"* || "$api_url" == *"/workspaces/trust0007/upstream/onyx"* ]]; then
  echo "error: CONTROL_PLANE_ONYX_API_BASE_URL must be an HTTPS URL, not a filesystem path: $api_url" >&2
  exit 1
fi

python - "$base_url" "$api_url" <<'PY'
import sys
from urllib.parse import urlparse

base_url, api_url = sys.argv[1], sys.argv[2]
for name, value in (("CONTROL_PLANE_ONYX_BASE_URL", base_url), ("CONTROL_PLANE_ONYX_API_BASE_URL", api_url)):
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SystemExit(f"error: {name} must be a valid HTTP(S) URL: {value}")
    host = parsed.hostname or ""
    if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        raise SystemExit(f"error: {name} cannot point to localhost in remote mode: {value}")
PY

onyx_token="${CONTROL_PLANE_ONYX_API_TOKEN:-${ONYX_API_TOKEN:-}}"

request_headers=("-H" "Accept: application/json")
if [[ -n "$onyx_token" ]]; then
  request_headers+=("-H" "Authorization: Bearer ${onyx_token}")
fi

if ! curl -fsS --max-time 10 "${request_headers[@]}" "$api_url" >/dev/null; then
  echo "error: unable to reach CONTROL_PLANE_ONYX_API_BASE_URL: $api_url" >&2
  echo "hint: ensure the Onyx Codespace port is forwarded and visible to this Codespace (Public or Organization)." >&2
  exit 1
fi

echo "remote Onyx verification passed: $api_url"
