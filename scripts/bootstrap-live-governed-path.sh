#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/compose/.env.production}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/compose/docker-compose.production.yml}"
STATE_DIR="${STATE_DIR:-$ROOT_DIR/.runtime/live-governed}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "error: $ENV_FILE is missing. Copy compose/.env.production.example to compose/.env.production and replace the placeholder secrets first." >&2
  exit 1
fi

mkdir -p "$STATE_DIR"

read_env_value() {
  local key="$1"
  python - "$ENV_FILE" "$key" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
target = sys.argv[2]

if not env_path.exists():
    raise SystemExit(0)

for raw_line in env_path.read_text(encoding="utf-8").splitlines():
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#") or "=" not in raw_line:
        continue
    key, value = raw_line.split("=", 1)
    if key.strip() != target:
        continue
    print(value.strip())
    raise SystemExit(0)
PY
}

require_value() {
  local label="$1"
  local value="$2"
  if [[ -z "$value" ]]; then
    echo "error: missing required value for ${label}" >&2
    exit 1
  fi
}

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

wait_for_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-90}"
  local i
  for ((i=1; i<=attempts; i+=1)); do
    local code
    code="$(curl -sS -o /dev/null -w '%{http_code}' "$url" || true)"
    if [[ "$code" != "000" ]]; then
      return 0
    fi
    sleep 2
  done
  echo "error: ${name} did not become reachable at ${url}" >&2
  exit 1
}

wait_for_json_http() {
  local name="$1"
  local url="$2"
  local attempts="${3:-90}"
  local i
  for ((i=1; i<=attempts; i+=1)); do
    if curl -sS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "error: ${name} did not return a successful response at ${url}" >&2
  exit 1
}

KEYCLOAK_BOOTSTRAP_DIR="/opt/keycloak/data/bootstrap"
KEYCLOAK_REALM_REMOTE_FILE="${KEYCLOAK_BOOTSTRAP_DIR}/realm-governed-template.json"
KEYCLOAK_MAPPER_REMOTE_FILE="${KEYCLOAK_BOOTSTRAP_DIR}/keycloak-tenant-id-mapper.json"
KEYCLOAK_USER_REMOTE_FILE="${KEYCLOAK_BOOTSTRAP_DIR}/keycloak-live-user.json"

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@" \
    --no-config \
    --server http://127.0.0.1:8080 \
    --realm master \
    --user "$KEYCLOAK_ADMIN" \
    --password "$KEYCLOAK_ADMIN_PASSWORD"
}

vault_exec() {
  compose exec -T vault sh -lc "VAULT_ADDR=http://127.0.0.1:8200 $1"
}

json_has_realm() {
  local realm_name="$1"
  python -c 'import json, sys; payload = json.load(sys.stdin); target = sys.argv[1]; print("yes" if any(item.get("realm") == target for item in payload) else "no")' "$realm_name"
}

json_first_id() {
  python -c 'import json, sys; payload = json.load(sys.stdin); print(payload[0].get("id", "") if isinstance(payload, list) and payload else "")'
}

json_mapper_ids_by_name() {
  local mapper_name="$1"
  python -c 'import json, sys; payload = json.load(sys.stdin); target = sys.argv[1]; [print(item["id"]) for item in payload if item.get("name") == target and item.get("id")]' "$mapper_name"
}

json_bool_field() {
  local field_name="$1"
  python -c 'import json, sys; payload = json.load(sys.stdin); print("yes" if payload.get(sys.argv[1]) else "no")' "$field_name"
}

write_rendered_realm() {
  local source_file="$1"
  local output_file="$2"
  local realm_name="$3"
  local control_plane_url="$4"
  python - "$source_file" "$output_file" "$realm_name" "$control_plane_url" <<'PY'
import json
from pathlib import Path
from urllib.parse import urlparse
import sys

source_file = Path(sys.argv[1])
output_file = Path(sys.argv[2])
realm_name = sys.argv[3]
control_plane_url = sys.argv[4]

payload = json.loads(source_file.read_text(encoding="utf-8"))
payload["realm"] = realm_name

parsed = urlparse(control_plane_url)
origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "http://localhost:3000"

for client in payload.get("clients", []):
    if client.get("clientId") != "control-plane-web":
        continue
    client["redirectUris"] = [f"{origin}/*"]
    client["webOrigins"] = [origin]

output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

write_rendered_user() {
  local output_file="$1"
  local username="$2"
  local password="$3"
  local tenant_id="$4"
  python - "$output_file" "$username" "$password" "$tenant_id" <<'PY'
import json
from pathlib import Path
import sys

output_file = Path(sys.argv[1])
username = sys.argv[2]
password = sys.argv[3]
tenant_id = sys.argv[4]

payload = {
    "username": username,
    "enabled": True,
    "emailVerified": True,
    "firstName": "Governed",
    "lastName": "Live Admin",
    "email": f"{username}@example.local",
    "credentials": [{"type": "password", "value": password, "temporary": False}],
    "attributes": {"tenant_id": [tenant_id]},
}

output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY
}

read_json_value() {
  local file_path="$1"
  local expression="$2"
  python - "$file_path" "$expression" <<'PY'
import json
from pathlib import Path
import sys

payload = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
expression = sys.argv[2]

if expression == "root_token":
    print(payload.get("root_token", ""))
elif expression == "unseal_key":
    keys = payload.get("unseal_keys_b64", [])
    print(keys[0] if keys else "")
PY
}

ensure_role() {
  local role_name="$1"
  if ! kcadm get "roles/${role_name}" -r "$KEYCLOAK_REALM" >/dev/null 2>&1; then
    kcadm create roles -r "$KEYCLOAK_REALM" -s "name=${role_name}" >/dev/null
  fi
}

apply_tenant_mapper() {
  local client_id="$1"
  local client_uuid
  local clients_json
  local mappers_json

  clients_json="$(kcadm get clients -r "$KEYCLOAK_REALM" -q clientId="$client_id")"
  client_uuid="$(printf '%s' "$clients_json" | json_first_id)"
  if [[ -z "$client_uuid" ]]; then
    echo "error: unable to find Keycloak client ${client_id} in realm ${KEYCLOAK_REALM}" >&2
    exit 1
  fi

  mappers_json="$(kcadm get "clients/${client_uuid}/protocol-mappers/models" -r "$KEYCLOAK_REALM")"
  while IFS= read -r mapper_id; do
    [[ -n "$mapper_id" ]] || continue
    kcadm delete "clients/${client_uuid}/protocol-mappers/models/${mapper_id}" -r "$KEYCLOAK_REALM" >/dev/null
  done < <(printf '%s' "$mappers_json" | json_mapper_ids_by_name "tenant_id")
  kcadm create "clients/${client_uuid}/protocol-mappers/models" -r "$KEYCLOAK_REALM" -f "$KEYCLOAK_MAPPER_REMOTE_FILE" >/dev/null
}

KEYCLOAK_ADMIN="${KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME:-${KEYCLOAK_ADMIN:-$(read_env_value KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME)}}"
KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD:-${KEYCLOAK_ADMIN_PASSWORD:-$(read_env_value KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD)}}"
KEYCLOAK_HOST_PORT="${KEYCLOAK_HOST_PORT:-$(read_env_value KEYCLOAK_HOST_PORT)}"
KEYCLOAK_HOST_PORT="${KEYCLOAK_HOST_PORT:-18080}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-$(read_env_value KEYCLOAK_REALM)}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-umbrella}"
SMOKE_CLIENT_ID="${SMOKE_CLIENT_ID:-$(read_env_value SMOKE_CLIENT_ID)}"
SMOKE_CLIENT_ID="${SMOKE_CLIENT_ID:-governed-smoke-client}"
WEB_CLIENT_ID="${WEB_CLIENT_ID:-$(read_env_value WEB_CLIENT_ID)}"
WEB_CLIENT_ID="${WEB_CLIENT_ID:-control-plane-web}"
LIVE_USERNAME="${LIVE_USERNAME:-$(read_env_value LIVE_USERNAME)}"
LIVE_USERNAME="${LIVE_USERNAME:-governed-live-admin}"
LIVE_PASSWORD="${LIVE_PASSWORD:-$(read_env_value LIVE_PASSWORD)}"
TENANT_ID="${TENANT_ID:-$(read_env_value TENANT_ID)}"
TENANT_ID="${TENANT_ID:-tenant-stage}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-$(read_env_value CONTROL_PLANE_QDRANT_COLLECTION)}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-governed_docs}"
CONTROL_PLANE_BASE_URL="${CONTROL_PLANE_BASE_URL:-$(read_env_value CONTROL_PLANE_BASE_URL)}"
CONTROL_PLANE_BASE_URL="${CONTROL_PLANE_BASE_URL:-http://localhost:3000}"
REALM_TEMPLATE="${REALM_TEMPLATE:-$ROOT_DIR/adapters/identity/realm-governed-template.json}"
MAPPER_FILE="${MAPPER_FILE:-$ROOT_DIR/adapters/identity/keycloak-tenant-id-mapper.json}"
VAULT_INIT_FILE="${VAULT_INIT_FILE:-$STATE_DIR/vault-init.json}"

require_value "KEYCLOAK_BOOTSTRAP_ADMIN_PASSWORD" "$KEYCLOAK_ADMIN_PASSWORD"
require_value "LIVE_PASSWORD" "$LIVE_PASSWORD"

RENDERED_REALM_FILE="$STATE_DIR/realm-governed.rendered.json"
RENDERED_USER_FILE="$STATE_DIR/keycloak-live-user.rendered.json"

write_rendered_realm "$REALM_TEMPLATE" "$RENDERED_REALM_FILE" "$KEYCLOAK_REALM" "$CONTROL_PLANE_BASE_URL"
write_rendered_user "$RENDERED_USER_FILE" "$LIVE_USERNAME" "$LIVE_PASSWORD" "$TENANT_ID"

echo "Starting staging-style governed dependency services..."
compose up -d keycloak_db db keycloak vault qdrant opa langfuse grafana superset envoy

wait_for_http "Keycloak" "http://127.0.0.1:${KEYCLOAK_HOST_PORT}/health/ready"
wait_for_http "Vault" "http://127.0.0.1:8200/v1/sys/health"
wait_for_json_http "Qdrant" "http://127.0.0.1:6333/collections"
wait_for_json_http "OPA" "http://127.0.0.1:8181/v1/data"

echo "Initializing or unsealing Vault..."
vault_status_json="$(vault_exec 'vault status -format=json || true')"
if [[ -z "$vault_status_json" ]]; then
  echo "error: vault status did not return JSON output" >&2
  exit 1
fi
vault_initialized="$(printf '%s' "$vault_status_json" | json_bool_field initialized)"
vault_sealed="$(printf '%s' "$vault_status_json" | json_bool_field sealed)"

if [[ "$vault_initialized" != "yes" ]]; then
  vault_init_json="$(vault_exec 'vault operator init -key-shares=1 -key-threshold=1 -format=json')"
  printf '%s\n' "$vault_init_json" > "$VAULT_INIT_FILE"
fi

if [[ -f "$VAULT_INIT_FILE" ]]; then
  VAULT_TOKEN="${VAULT_TOKEN:-$(read_json_value "$VAULT_INIT_FILE" root_token)}"
  VAULT_UNSEAL_KEY="${VAULT_UNSEAL_KEY:-$(read_json_value "$VAULT_INIT_FILE" unseal_key)}"
fi

require_value "VAULT_TOKEN" "${VAULT_TOKEN:-}"
require_value "VAULT_UNSEAL_KEY" "${VAULT_UNSEAL_KEY:-}"

if [[ "$vault_sealed" == "yes" ]]; then
  vault_exec "vault operator unseal ${VAULT_UNSEAL_KEY}" >/dev/null
fi

vault_exec "VAULT_TOKEN=${VAULT_TOKEN} vault secrets enable -path=secret kv-v2 >/dev/null 2>&1 || true"
vault_exec "VAULT_TOKEN=${VAULT_TOKEN} vault kv put secret/runtime/${TENANT_ID}/onyx api_token=runtime-secret >/dev/null"
vault_exec "VAULT_TOKEN=${VAULT_TOKEN} vault kv put secret/runtime/${TENANT_ID}/governed-flow api_token=runtime-secret >/dev/null"

echo "Copying Keycloak bootstrap assets into the container..."
compose exec -T keycloak sh -lc "mkdir -p ${KEYCLOAK_BOOTSTRAP_DIR}"
compose cp "$RENDERED_REALM_FILE" "keycloak:${KEYCLOAK_REALM_REMOTE_FILE}" >/dev/null
compose cp "$MAPPER_FILE" "keycloak:${KEYCLOAK_MAPPER_REMOTE_FILE}" >/dev/null
compose cp "$RENDERED_USER_FILE" "keycloak:${KEYCLOAK_USER_REMOTE_FILE}" >/dev/null

echo "Ensuring realm ${KEYCLOAK_REALM} exists..."
realms_json="$(kcadm get realms)"
if [[ "$(printf '%s' "$realms_json" | json_has_realm "$KEYCLOAK_REALM")" != "yes" ]]; then
  kcadm create realms -f "$KEYCLOAK_REALM_REMOTE_FILE" >/dev/null
fi

ensure_role tenant_user
ensure_role tenant_admin

echo "Applying tenant claim mappers to the live clients..."
apply_tenant_mapper "$SMOKE_CLIENT_ID"
apply_tenant_mapper "$WEB_CLIENT_ID"

echo "Ensuring governed live user ${LIVE_USERNAME} exists..."
users_json="$(kcadm get users -r "$KEYCLOAK_REALM" -q username="$LIVE_USERNAME")"
user_uuid="$(printf '%s' "$users_json" | json_first_id)"
if [[ -z "$user_uuid" ]]; then
  kcadm create users -r "$KEYCLOAK_REALM" -f "$KEYCLOAK_USER_REMOTE_FILE" >/dev/null
  users_json="$(kcadm get users -r "$KEYCLOAK_REALM" -q username="$LIVE_USERNAME")"
  user_uuid="$(printf '%s' "$users_json" | json_first_id)"
fi
if [[ -z "$user_uuid" ]]; then
  echo "error: unable to resolve user id for ${LIVE_USERNAME}" >&2
  exit 1
fi

kcadm update "users/${user_uuid}" -r "$KEYCLOAK_REALM" -f "$KEYCLOAK_USER_REMOTE_FILE" >/dev/null
kcadm update "users/${user_uuid}" -r "$KEYCLOAK_REALM" -s "attributes.tenant_id=[\"${TENANT_ID}\"]" >/dev/null
kcadm set-password -r "$KEYCLOAK_REALM" --username "$LIVE_USERNAME" --new-password "$LIVE_PASSWORD" >/dev/null
kcadm add-roles -r "$KEYCLOAK_REALM" --uid "$user_uuid" --rolename tenant_user >/dev/null 2>&1 || true
kcadm add-roles -r "$KEYCLOAK_REALM" --uid "$user_uuid" --rolename tenant_admin >/dev/null 2>&1 || true

echo "Seeding tenant-scoped Qdrant content..."
python - "$QDRANT_COLLECTION" "$TENANT_ID" <<'PY'
import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

collection = sys.argv[1]
tenant_id = sys.argv[2]
base = "http://127.0.0.1:6333"

create_req = Request(
    f"{base}/collections/{collection}",
    data=json.dumps({"vectors": {"size": 1, "distance": "Cosine"}}).encode("utf-8"),
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="PUT",
)
try:
    with urlopen(create_req, timeout=10) as response:
        response.read()
except HTTPError as exc:
    if exc.code != 409:
        raise

points_req = Request(
    f"{base}/collections/{collection}/points?wait=true",
    data=json.dumps(
        {
            "points": [
                {
                    "id": 1001,
                    "vector": [0.1],
                    "payload": {
                        "tenant_id": tenant_id,
                        "source": "qdrant",
                        "content": "Navigate to Onyx path: /app governed launch context",
                        "trust_label": "trusted",
                        "quarantined": False,
                        "provenance": {"uri": "kb://governed-live-launch-doc-1"},
                    },
                }
            ]
        }
    ).encode("utf-8"),
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="PUT",
)
with urlopen(points_req, timeout=10) as response:
    response.read()
PY

echo "Starting live control-plane container..."
CONTROL_PLANE_GOVERNANCE_MODE=live \
CONTROL_PLANE_ENVIRONMENT_MODE=staging \
CONTROL_PLANE_VAULT_TOKEN="$VAULT_TOKEN" \
compose up -d --build control_plane

wait_for_json_http "Control plane" "http://127.0.0.1:3000/api/health"

echo
echo "Live governed staging bootstrap complete."
echo "Control plane: http://127.0.0.1:3000"
echo "Keycloak: http://127.0.0.1:${KEYCLOAK_HOST_PORT}"
echo "Realm: ${KEYCLOAK_REALM}"
echo "User: ${LIVE_USERNAME}"
echo "Tenant: ${TENANT_ID}"
echo "Vault state: ${VAULT_INIT_FILE}"
echo
echo "Next step:"
echo "  python scripts/smoke-live-onyx-handoff.py"
