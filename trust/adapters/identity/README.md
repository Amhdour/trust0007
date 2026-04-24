# Identity Adapter

This directory holds identity integration artifacts for Keycloak and downstream policy/runtime use.

Contents:
- `claims-mapping.example.yaml`: example token claim to internal-context mapping.
- `realm-governed-template.json`: production-like realm import template for the governed live stack.
- `keycloak-tenant-id-mapper.json`: user-attribute mapper used by the governed live clients.
- `realm-dev-template.json`: local-development realm import template.
- `keycloak-dev-tenant-id-mapper.json`: dev-only hardcoded tenant mapper for local strict-live bootstrap.
- `keycloak-dev-live-user.json`: local bootstrap user profile for repeatable live smoke tests.
- `keycloak-dev-tenant-admin-user.json`: local tenant-admin profile used during manual live bootstrap/debugging.
- `interfaces.py`: identity-provider contract for governed flows.
- `schemas.py`: normalized identity request/result models.
- `keycloak.py`: Keycloak-compatible userinfo-backed identity resolution.

The repo still supports demo fallback mode, but live governed flows should resolve identity from Keycloak-backed bearer token or session state and fail closed when live identity is required.

Local development note:

- `keycloak-tenant-id-mapper.json` is the live-path mapping pattern. It reads `tenant_id` from the user record instead of hardcoding a tenant value into the mapper.
- `keycloak-dev-tenant-id-mapper.json` is now legacy local scaffolding only and should not be used for the staging or production-like governed path.
