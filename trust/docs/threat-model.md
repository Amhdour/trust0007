# Threat Model & Trust Boundaries (Trust0007)

## Scope
This model covers the trust control plane (`trust/`) that governs runtime access to Onyx lanes:

- `/launch/onyx`
- `/launch/onyx/agent`

## Primary assets
- Identity tokens and session context
- Runtime secret material (Vault-backed references)
- Policy decisions (OPA/Rego)
- Retrieval constraints and tenant boundaries
- Audit/evidence artifacts under `overlays/myStarterKit/artifacts/`

## Trust boundaries
1. **User/browser → Control plane** (untrusted external input)
2. **Control plane → Identity provider** (authN/authZ assertions)
3. **Control plane → OPA** (policy decision dependency)
4. **Control plane → Retrieval backend (Qdrant)** (data boundary checks)
5. **Control plane → Tool/MCP routing** (agent action authorization)
6. **Control plane → Vault/secret sources** (credential health and runtime secret checks)
7. **Control plane → Onyx runtime** (governed handoff)

## Threats and controls (high-level)
| Threat | Example | Current control |
|---|---|---|
| Identity spoofing | Missing/invalid token in launch request | fail-closed identity gate before runtime handoff |
| Policy bypass | Runtime action without policy decision | OPA policy check required; deny on OPA unavailability |
| Retrieval boundary escape | Cross-tenant query leakage | retrieval boundary enforcement before allow |
| MCP/tool abuse | Unapproved MCP server/tool invocation | allowlist + runtime-specific governance checks |
| Secret misuse | Invalid Vault token/path drift | secret health gate blocks launch when unresolved |
| Evidence tampering/absence | No auditable trail for a launch | launch-gate artifacts and audit records required |

## Assumptions
- Local compose/dev mode may use placeholder secrets and mocked readiness feeds.
- Live claims require non-dev mode, real secrets, and live verifier checks (`make verify-live`).

## Residual risks / next hardening steps
- Add signed provenance for proof-pack bundles.
- Add immutable artifact storage strategy for production deployment.
- Add rate-limits/abuse controls for launch endpoints.
- Add SBOM + dependency policy gate in CI.
