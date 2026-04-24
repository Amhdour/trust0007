# Onyx Runtime Module

Onyx is treated as a governed runtime module behind the dashboard-first control plane.

- Upstream source: `upstream/onyx/`
- Runtime access path: dashboard -> Keycloak -> Envoy -> Onyx
- Governance path: Onyx -> myStarterKit -> OPA / Vault / Qdrant / gVisor -> Langfuse
