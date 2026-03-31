# Keycloak Scripts (Development)

Scripts in this folder are development helpers for realm import and JWT inspection.

- `dev-import-realm.sh`: import a realm JSON file into local Keycloak container.
- `decode-jwt.sh`: decode JWT payload for local debugging (no signature verification).

Related local-live bootstrap assets live under `adapters/identity/`:

- `realm-dev-template.json`: development realm import template.
- `keycloak-dev-tenant-id-mapper.json`: dev-only Keycloak mapper used by the local live bootstrap. It hardcodes `tenant_id=tenant-dashboard` so a single-tenant local stack can exercise the strict live path without requiring a fuller tenant-attribute pipeline.
- `keycloak-dev-live-user.json`: local bootstrap user profile for the repeatable live smoke test.

Important live note:

- The governed live smoke path requires a token with `openid` scope. Without `openid`, Keycloak can issue a bearer token, but `userinfo` will return `403`, and the governed `/launch/onyx?mode=live` handoff will fail closed.
- The repeatable `make smoke-live` flow runs from the control-plane container so the Keycloak token mint and the control plane's own `userinfo` validation use the same network path.
