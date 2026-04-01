#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT_DIR/compose/.env}"
COMPOSE_FILE="${COMPOSE_FILE:-$ROOT_DIR/compose/docker-compose.yml}"

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

KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN:-$(read_env_value KEYCLOAK_ADMIN)}"
KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-$(read_env_value KEYCLOAK_ADMIN_PASSWORD)}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-change-me}"
KEYCLOAK_HOST_PORT="${KEYCLOAK_HOST_PORT:-$(read_env_value KEYCLOAK_HOST_PORT)}"
KEYCLOAK_HOST_PORT="${KEYCLOAK_HOST_PORT:-18080}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-$(read_env_value KEYCLOAK_REALM)}"
KEYCLOAK_REALM="${KEYCLOAK_REALM:-umbrella-dev}"
KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-$(read_env_value KEYCLOAK_CLIENT_ID)}"
KEYCLOAK_CLIENT_ID="${KEYCLOAK_CLIENT_ID:-dev-web-app}"
LIVE_USERNAME="${LIVE_USERNAME:-$(read_env_value LIVE_USERNAME)}"
LIVE_USERNAME="${LIVE_USERNAME:-live-tenant-admin}"
LIVE_PASSWORD="${LIVE_PASSWORD:-$(read_env_value LIVE_PASSWORD)}"
LIVE_PASSWORD="${LIVE_PASSWORD:-change-me}"
VAULT_DEV_ROOT_TOKEN_ID="${VAULT_DEV_ROOT_TOKEN_ID:-$(read_env_value VAULT_DEV_ROOT_TOKEN_ID)}"
VAULT_TOKEN="${VAULT_TOKEN:-${VAULT_DEV_ROOT_TOKEN_ID:-dev-root-token}}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-$(read_env_value QDRANT_COLLECTION)}"
QDRANT_COLLECTION="${QDRANT_COLLECTION:-governed_docs}"
TENANT_ID="${TENANT_ID:-$(read_env_value TENANT_ID)}"
TENANT_ID="${TENANT_ID:-tenant-dashboard}"

REALM_FILE="${REALM_FILE:-$ROOT_DIR/adapters/identity/realm-dev-template.json}"
MAPPER_FILE="${MAPPER_FILE:-$ROOT_DIR/adapters/identity/keycloak-dev-tenant-id-mapper.json}"
USER_FILE="${USER_FILE:-$ROOT_DIR/adapters/identity/keycloak-dev-live-user.json}"

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

kcadm() {
  compose exec -T keycloak /opt/keycloak/bin/kcadm.sh "$@" \
    --no-config \
    --server http://127.0.0.1:8080 \
    --realm master \
    --user "$KEYCLOAK_ADMIN" \
    --password "$KEYCLOAK_ADMIN_PASSWORD"
}

wait_for_keycloak() {
  local attempts="${1:-60}"
  local i
  for ((i=1; i<=attempts; i+=1)); do
    if compose exec -T keycloak bash -lc 'echo > /dev/tcp/127.0.0.1/8080' >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  echo "error: keycloak did not become reachable inside the container" >&2
  return 1
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

echo "Starting live dependency services..."
compose up -d keycloak opa qdrant vault
wait_for_keycloak

echo "Copying Keycloak bootstrap artifacts into the container..."
compose cp "$REALM_FILE" keycloak:/tmp/realm-dev-template.json >/dev/null
compose cp "$MAPPER_FILE" keycloak:/tmp/keycloak-dev-tenant-id-mapper.json >/dev/null
compose cp "$USER_FILE" keycloak:/tmp/keycloak-dev-live-user.json >/dev/null

echo "Ensuring realm ${KEYCLOAK_REALM} exists..."
realms_json="$(kcadm get realms)"
if [[ "$(printf '%s' "$realms_json" | json_has_realm "$KEYCLOAK_REALM")" != "yes" ]]; then
  kcadm create realms -f /tmp/realm-dev-template.json >/dev/null
fi

echo "Resolving Keycloak client id for ${KEYCLOAK_CLIENT_ID}..."
clients_json="$(kcadm get clients -r "$KEYCLOAK_REALM" -q clientId="$KEYCLOAK_CLIENT_ID")"
client_uuid="$(printf '%s' "$clients_json" | json_first_id)"
if [[ -z "$client_uuid" ]]; then
  echo "error: unable to find Keycloak client ${KEYCLOAK_CLIENT_ID} in realm ${KEYCLOAK_REALM}" >&2
  exit 1
fi

echo "Re-applying dev-only tenant mapper for local live bootstrap..."
mappers_json="$(kcadm get "clients/${client_uuid}/protocol-mappers/models" -r "$KEYCLOAK_REALM")"
while IFS= read -r mapper_id; do
  [[ -n "$mapper_id" ]] || continue
  kcadm delete "clients/${client_uuid}/protocol-mappers/models/${mapper_id}" -r "$KEYCLOAK_REALM" >/dev/null
done < <(printf '%s' "$mappers_json" | json_mapper_ids_by_name "tenant_id")
kcadm create "clients/${client_uuid}/protocol-mappers/models" -r "$KEYCLOAK_REALM" -f /tmp/keycloak-dev-tenant-id-mapper.json >/dev/null

echo "Ensuring live bootstrap user ${LIVE_USERNAME} exists..."
users_json="$(kcadm get users -r "$KEYCLOAK_REALM" -q username="$LIVE_USERNAME")"
user_uuid="$(printf '%s' "$users_json" | json_first_id)"
if [[ -z "$user_uuid" ]]; then
  kcadm create users -r "$KEYCLOAK_REALM" -f /tmp/keycloak-dev-live-user.json >/dev/null
  users_json="$(kcadm get users -r "$KEYCLOAK_REALM" -q username="$LIVE_USERNAME")"
  user_uuid="$(printf '%s' "$users_json" | json_first_id)"
fi
if [[ -z "$user_uuid" ]]; then
  echo "error: unable to resolve user id for ${LIVE_USERNAME}" >&2
  exit 1
fi

kcadm update "users/${user_uuid}" -r "$KEYCLOAK_REALM" -f /tmp/keycloak-dev-live-user.json >/dev/null
kcadm set-password -r "$KEYCLOAK_REALM" --username "$LIVE_USERNAME" --new-password "$LIVE_PASSWORD" >/dev/null
kcadm add-roles -r "$KEYCLOAK_REALM" --uid "$user_uuid" --rolename tenant_user >/dev/null
kcadm add-roles -r "$KEYCLOAK_REALM" --uid "$user_uuid" --rolename tenant_admin >/dev/null

echo "Starting live control-plane container..."
CONTROL_PLANE_GOVERNANCE_MODE=live \
CONTROL_PLANE_ENVIRONMENT_MODE=prod-sim \
CONTROL_PLANE_VAULT_TOKEN="$VAULT_TOKEN" \
compose up -d --no-deps control_plane

echo "Seeding tenant-scoped Qdrant content..."
compose exec -T control_plane python - <<PY
import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

base = "http://qdrant:6333"
collection = "${QDRANT_COLLECTION}"
tenant_id = "${TENANT_ID}"

create_req = Request(
    f"{base}/collections/{collection}",
    data=json.dumps({"vectors": {"size": 1, "distance": "Cosine"}}).encode(),
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
                        "content": "Navigate to Onyx path: /app live launch context",
                        "trust_label": "trusted",
                        "quarantined": False,
                        "provenance": {"uri": "kb://live-launch-doc-1"},
                    },
                }
            ]
        }
    ).encode(),
    headers={"Content-Type": "application/json", "Accept": "application/json"},
    method="PUT",
)
with urlopen(points_req, timeout=10) as response:
    response.read()
PY

echo "Seeding Vault runtime secret..."
compose exec -T vault sh -lc "VAULT_ADDR=http://127.0.0.1:8200 VAULT_TOKEN=${VAULT_TOKEN} vault kv put secret/dev/${TENANT_ID}/runtime api_token=runtime-secret" >/dev/null

echo
echo "Local live bootstrap complete."
echo "Keycloak host port: ${KEYCLOAK_HOST_PORT}"
echo "Live bootstrap user: ${LIVE_USERNAME}"
echo "Tenant: ${TENANT_ID}"
echo
echo "Next step:"
echo "  python scripts/smoke-live-onyx-handoff.py"
