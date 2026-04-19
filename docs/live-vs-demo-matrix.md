# Live vs Demo Matrix

This repo keeps both `demo` and `live` governed modes, but they are not equivalent.

## Mode comparison

| Control area | `demo` mode | `live` mode |
| --- | --- | --- |
| Identity | Repo-local fallback identity can be used | Keycloak-backed bearer token or session resolution is mandatory |
| Policy | Repo-local policy evaluator may decide | Live OPA decision is mandatory |
| Retrieval | Seeded/demo retrieval can satisfy the flow | Live Qdrant-backed retrieval is mandatory |
| Secret access | Optional and usually skipped | Vault-backed access is mandatory when the governed operation requires a secret |
| Trace correlation | Helpful but not launch-gate blocking | Missing correlation downgrades live readiness and blocks handoff |
| Launch gate inputs | May summarize demo or sample evidence | Must use live governed-flow artifacts; no silent sample substitution |
| Runtime handoff (`/launch/onyx`, `/launch/dify`) | Can succeed with fallback evidence | Fails closed unless live evidence and launch-gate approval exist |

## How to activate

- `demo` mode
  - default local behavior
  - intended for fast iteration and fallback proof
- `live` mode
  - `CONTROL_PLANE_GOVERNANCE_MODE=live`
  - or `mode=live` on `/api/control-plane/governed-flow`, `/launch/onyx`, and `/launch/dify`

## Reviewer guidance

- Treat `demo` as a repo-local fallback path, not as proof of live enforcement.
- Treat `live` claims as credible only when the dashboard shows live identity, live OPA, live retrieval, conditional live secret access, trace correlation, and live-evidence launch-gate status for the same trace.
