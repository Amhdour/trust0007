#!/usr/bin/env bash
set -euo pipefail

REALM_FILE="${1:-adapters/identity/realm-dev-template.json}"
KEYCLOAK_CONTAINER="${KEYCLOAK_CONTAINER:-keycloak}"
KEYCLOAK_URL="${KEYCLOAK_URL:-http://localhost:8080}"
KEYCLOAK_ADMIN="${KEYCLOAK_ADMIN:-admin}"
KEYCLOAK_ADMIN_PASSWORD="${KEYCLOAK_ADMIN_PASSWORD:-change-me}"

if [[ ! -f "$REALM_FILE" ]]; then
  echo "error: realm file not found: $REALM_FILE" >&2
  exit 1
fi

# Requires docker + kcadm.sh in the running keycloak container.
# Development helper only.
docker exec "$KEYCLOAK_CONTAINER" /opt/keycloak/bin/kcadm.sh config credentials \
  --server "$KEYCLOAK_URL" \
  --realm master \
  --user "$KEYCLOAK_ADMIN" \
  --password "$KEYCLOAK_ADMIN_PASSWORD"

docker cp "$REALM_FILE" "$KEYCLOAK_CONTAINER":/tmp/realm-import.json

docker exec "$KEYCLOAK_CONTAINER" /opt/keycloak/bin/kcadm.sh create realms \
  -f /tmp/realm-import.json || true

echo "Realm import attempted (existing realm errors are ignored in this dev helper)."
