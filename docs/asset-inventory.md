# Asset Inventory

## Identity and access assets
- Keycloak realms/clients
- Token signing keys
- Session and claim metadata

## Edge and routing assets
- Envoy route and auth policy config
- TLS/mTLS certificates and trust chains
- Ingress access logs

## Runtime and governance assets
- Onyx runtime context and orchestration state
- myStarterKit governance policies and guardrail configs
- Launch-gate readiness rules

## Policy assets
- OPA rego bundles
- Policy decision logs
- Bundle provenance/version metadata

## Secrets assets
- Vault secret engines
- Dynamic/static credentials
- Lease/token metadata and audit logs

## Retrieval assets
- Qdrant collections/index metadata
- Embeddings and retrieved document fragments
- Retrieval query and result telemetry

## Tool execution assets
- Tool definitions and allowlists
- Integration credentials/scopes
- Tool invocation/result logs

## Sandbox assets
- gVisor runtime policies/profiles
- Sandbox execution logs
- Resource usage and isolation metrics

## Observability and reporting assets
- Langfuse traces/evaluations
- Grafana dashboards/alerts
- Superset datasets/reports

## Asset criticality tags (initial)
- **Tier-0 critical**: identity keys, Vault secrets, policy bundles.
- **Tier-1 high**: runtime context, retrieval data, tool credentials.
- **Tier-2 medium**: dashboards/reports, aggregated telemetry artifacts.
