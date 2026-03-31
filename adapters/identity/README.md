# Identity Adapter

This directory holds identity integration artifacts for Keycloak and downstream policy/runtime use.

Contents:
- `claims-mapping.example.yaml`: example token claim to internal-context mapping.
- `realm-dev-template.json`: local-development realm import template.
- `keycloak-dev-tenant-id-mapper.json`: dev-only hardcoded tenant mapper for local strict-live bootstrap.
- `keycloak-dev-live-user.json`: local bootstrap user profile for repeatable live smoke tests.
- `keycloak-dev-tenant-admin-user.json`: local tenant-admin profile used during manual live bootstrap/debugging.
- `interfaces.py`: identity-provider contract for governed flows.
- `schemas.py`: normalized identity request/result models.
- `keycloak.py`: Keycloak-compatible userinfo-backed identity resolution.

The repo still supports demo fallback mode, but live governed flows should resolve identity from Keycloak-backed bearer token or session state and fail closed when live identity is required.

Local development note:

- `keycloak-dev-tenant-id-mapper.json` is intentionally a dev-only shortcut. It hardcodes `tenant_id=tenant-dashboard` for the local strict-live bootstrap and should not be treated as a production claim-mapping pattern.
- The repeatable local smoke flow is meant to run from the control-plane network context. That keeps token minting and the live `userinfo` validation path aligned during local strict-live verification.
