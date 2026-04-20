# Strict Live Proof Matrix

This document defines when the repo can claim that the strict live governed path is proven.

Supporting links:

- reviewer runbook: [reviewer-runbook.md](reviewer-runbook.md)
- reviewer landing page: [reviewer-fast-path.md](reviewer-fast-path.md)
- visual proof guide: [dashboard-visual-proof.md](dashboard-visual-proof.md)
- reviewer evidence bundle: [../evidence/reviewer_evidence_bundle.json](../evidence/reviewer_evidence_bundle.json)

## Acceptance criteria

A live governed handoff is proven only when all of the following are true on the same flow:

1. identity resolves from live Keycloak-compatible HTTP interaction
2. policy decision resolves through live OPA interaction
3. retrieval or tool/MCP governance checks run for the selected runtime lane
4. required secret access succeeds when needed
5. trace correlation is complete
6. launch-gate evaluates live evidence
7. final allow/deny is reflected in artifacts and dashboard sections

## Runtime-specific strict-live tests

- Onyx lane: `tests/integration/test_strict_live_onyx_end_to_end.py`
- Dify lane: `tests/integration/test_strict_live_dify_end_to_end.py`
- Mocked dependency fail-closed checks: `tests/integration/test_live_governed_runtime_dependencies.py`

## Proof matrix

| Runtime lane | Scenario | Endpoint exercised | Expected result | Primary test | Key artifact |
| --- | --- | --- | --- | --- | --- |
| Onyx | Live pass | `/launch/onyx?path=/app&mode=live` | allow | `test_strict_live_onyx_handoff_passes_through_real_stack` | `allowed-flow.json` + `onyx-runtime-proof.json` |
| Onyx | Identity deny (missing/invalid token) | `/launch/onyx?path=/app&mode=live` | deny | `test_strict_live_onyx_handoff_denies_without_token`, `test_strict_live_onyx_handoff_denies_with_invalid_token` | `identity-evidence.json` |
| Onyx | OPA unreachable | `/launch/onyx?path=/app&mode=live` | deny | `test_strict_live_onyx_handoff_fails_closed_when_opa_is_unavailable` | `policy-evidence.json` |
| Onyx | Retrieval backend unavailable | `/launch/onyx?path=/app&mode=live` | deny | `test_strict_live_onyx_handoff_fails_closed_when_qdrant_is_unavailable` | `retrieval-evidence.json` |
| Onyx | Vault unavailable | `/launch/onyx?path=/app&mode=live` | deny | `test_strict_live_onyx_handoff_fails_closed_when_vault_is_unavailable` | `secret-evidence.json` |
| Dify | Live pass with governed MCP | `/launch/dify?path=/apps&mode=live&mcp=mcp_server.dashboard_control_plane` | allow | `test_strict_live_dify_handoff_passes_with_runtime_specific_governance` | `dify-runtime-proof.json` + `tool-evidence.json` |
| Dify | MCP deny (unapproved server) | `/launch/dify?path=/apps&mode=live&mcp=mcp_server.unapproved` | deny | `test_strict_live_dify_handoff_denies_unapproved_mcp_server` | `governed-flow-summary.json` reason codes |

## What is proven now

- Strict live governance is exercised through the real control-plane HTTP boundary.
- Onyx and Dify runtime lanes have explicit dedicated strict-live tests.
- Dify lane includes explicit tool/MCP governed allow and deny coverage.
- Dependency failures are fail-closed and visible in both artifacts and dashboard state.

## What is not yet fully proven

- “Governed live path is proven” is the accurate claim; it is narrower than claiming every supporting component is production complete.
- Local containerized setups can pass governance while still having runtime-local visibility caveats.
- Externally reachable always-on production hosting is environment-specific and not bundled by default.

## What remains supporting or future

- Envoy, Grafana, and Langfuse are supporting depth in the current proof story.
- Superset and gVisor remain optional/future depth.
