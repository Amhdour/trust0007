# Governance Overlay (Local)

This directory hosts additive governance integration assets that connect runtime components to policy, telemetry, and readiness controls without changing upstream repositories.

## Domains

- `identity/`: Keycloak claims and principal mapping contracts.
- `ingress/`: Envoy mediation and policy-invocation integration contracts.
- `runtime/`: Onyx runtime governance and control hooks.
- `policy/`: myStarterKit/OPA composition contracts.
- `secrets/`: Vault wiring contracts and path conventions.
- `retrieval/`: Qdrant retrieval guardrail integration.
- `observability/`: Langfuse and audit event mapping overlays.
- `readiness/`: launch-gate evidence and decision contracts.

Each domain is intentionally additive and must remain free of hardcoded secrets.
