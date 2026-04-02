# Keycloak Scripts (Development)

Scripts in this folder are development helpers for realm import and JWT inspection.

- `dev-import-realm.sh`: import a realm JSON file into local Keycloak container.
- `decode-jwt.sh`: decode JWT payload for local debugging (no signature verification).

Related governed-live bootstrap assets live under `adapters/identity/`:

- `realm-governed-template.json`: production-like realm import template for the governed live stack.
- `keycloak-tenant-id-mapper.json`: user-attribute mapper that projects `tenant_id` into token and userinfo claims.
- `keycloak-dev-live-user.json`: legacy local-development bootstrap user profile.

Important live note:

- The governed live smoke path requires a token with `openid` scope. Without `openid`, Keycloak can issue a bearer token, but `userinfo` will return `403`, and the governed `/launch/onyx?mode=live` handoff will fail closed.
- The repeatable `make smoke-live` flow now targets the host-exposed staging stack directly and checks the same live userinfo path the control plane relies on.
