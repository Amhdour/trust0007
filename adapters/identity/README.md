# Identity Adapter

This directory holds identity integration artifacts for Keycloak and downstream policy/runtime use.

Contents:
- `claims-mapping.example.yaml`: example token claim to internal-context mapping.
- `realm-dev-template.json`: local-development realm import template.
- `interfaces.py`: identity-provider contract for governed flows.
- `schemas.py`: normalized identity request/result models.
- `keycloak.py`: Keycloak-compatible userinfo-backed identity resolution.

The repo still supports demo fallback mode, but live governed flows should resolve identity from Keycloak-backed bearer token or session state and fail closed when live identity is required.
