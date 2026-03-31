# Strict Live Proof Matrix

This document defines when the repo is allowed to claim that the strict live governed path is proven.

Fast supporting links:

- reviewer landing page: [reviewer-fast-path.md](/workspaces/beta011/docs/reviewer-fast-path.md)
- visual proof guide: [dashboard-visual-proof.md](/workspaces/beta011/docs/dashboard-visual-proof.md)
- reviewer evidence bundle: [reviewer_evidence_bundle.json](/workspaces/beta011/evidence/reviewer_evidence_bundle.json)

## Acceptance criteria

A live-mode governed handoff is considered proven only if:

1. identity is resolved from live Keycloak-compatible HTTP interaction
2. policy is decided through live OPA HTTP interaction
3. retrieval is executed through live Qdrant HTTP interaction
4. secret access is executed through Vault HTTP interaction when required
5. trace correlation is complete
6. launch-gate uses live evidence
7. the final allow or deny is reflected in artifacts and the dashboard

## Proof matrix

| Scenario | Endpoint exercised | Expected result | Primary proof test | Reviewer artifact | Dashboard signal |
| --- | --- | --- | --- | --- | --- |
| Live pass | `/launch/onyx?path=/app&mode=live` | allow | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_passes_through_http_dependency_chain` | `evidence/reviewer/inspectable-live-runtime/allowed-flow.json` | `Latest handoff=ALLOW`, `Evidence mode=LIVE`, `Readiness=GO` |
| Missing bearer token | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[identity missing token]` | `evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json` | `Identity result=DENY` |
| Invalid bearer token | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[identity invalid token]` | `evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json` | `Identity result=DENY` |
| Missing tenant claim | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[identity tenant missing]` | `evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json` | `Identity result=DENY` |
| Keycloak unreachable | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[identity keycloak unreachable]` | `evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json` | `Identity result=DENY` |
| OPA unreachable | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[opa unreachable]` | `evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json` | `Latest policy result=DENY` |
| OPA explicit deny | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[opa deny]` | `evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json` | `Latest policy result=DENY` |
| Qdrant unavailable | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[qdrant unavailable]` | `evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json` | `Latest retrieval result=DENY` |
| Qdrant empty result | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[qdrant empty result]` | `evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json` | `Latest retrieval result=DENY` |
| Cross-tenant retrieval filtered | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[cross-tenant retrieval]` | `evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json` | `Latest retrieval result=DENY` |
| Vault unavailable | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[vault unavailable]` | `evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json` | `Secret fetched=no` |
| Secret key missing | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[secret key missing]` | `evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json` | `Secret fetched=no` |
| Invalid secret reference | `/launch/onyx?path=/app&mode=live` | deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[invalid secret reference]` | `evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json` | `Secret fetched=no` |
| Trace incomplete / missing live evidence | `/launch/onyx?path=/app&mode=live` | no-go / deny | `tests/integration/test_strict_live_http_end_to_end.py::test_strict_live_handoff_fails_closed_for_dependency_breaks[trace incomplete]` | `evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json` | `Trace complete=no`, `Missing evidence>0`, `Latest handoff=DENY` |

## What is proven now

- The strict live governed path is exercised through the real control-plane HTTP boundary.
- Keycloak, OPA, Qdrant, and Vault participate as HTTP-level dependencies in the tested live path.
- Each major dependency can fail closed and block Onyx handoff.
- The dashboard exposes live mode, latest dependency posture, launch-gate status, and latest handoff result.
- Reviewer artifacts include one passing live flow and dependency-specific failure examples.
- Unauthenticated requests or bearer tokens without the required `openid` scope still fail closed at the identity boundary.

## What is not yet fully proven

- “The governed live path is proven” is the right claim. It is stronger and more precise than saying the entire project or every supporting service is fully live-ready.
- In containerized local setups where Onyx runs outside the compose network, runtime-local health proof can remain partial even when the governed live chain is passing. That is why `onyx-runtime-proof.json` can still show runtime-visibility caveats while the live launch gate is passing.
- The local Keycloak tenant mapper used by the bootstrap flow is intentionally development-only. It is a local single-tenant proof aid, not a production tenant-claim strategy.

## What remains supporting or future

- Envoy is still supporting rather than mandatory in the proved request path.
- Grafana is a supporting drill-down surface, not a fail-closed dependency.
- Langfuse is active as an observability destination, but the strict live path does not fail closed on Langfuse reachability.
- gVisor and Superset remain future or optional depth.
