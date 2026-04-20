# Reviewer Fast Path

This page is the fastest audit route. For full operator flow, use [reviewer-runbook.md](reviewer-runbook.md).

## 30-second path

1. Proof contract: [strict-live-proof-matrix.md](strict-live-proof-matrix.md)
2. Runtime-lane strict-live tests:
   - [../tests/integration/test_strict_live_onyx_end_to_end.py](../tests/integration/test_strict_live_onyx_end_to_end.py)
   - [../tests/integration/test_strict_live_dify_end_to_end.py](../tests/integration/test_strict_live_dify_end_to_end.py)
3. Passing artifact: [../evidence/reviewer/inspectable-live-runtime/allowed-flow.json](../evidence/reviewer/inspectable-live-runtime/allowed-flow.json)
4. Denied artifact example: [../evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json](../evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json)
5. Launch-gate no-go artifact: [../evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json](../evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json)

## What to confirm quickly

- Dashboard shows **live governed** evidence mode when validating live claims.
- Onyx and Dify runtime lanes both appear in reviewer-visible sections.
- Passing and denied evidence can be traced from dashboard signals to JSON artifacts.
- Dify MCP governance deny reason (`policy.mcp_server_not_allowed:*`) is present in denied path.

## See A Pass


- Onyx pass test: `test_strict_live_onyx_handoff_passes_through_real_stack`
- Dify pass test: `test_strict_live_dify_handoff_passes_with_runtime_specific_governance`
- Visual cues guide: [dashboard-visual-proof.md](dashboard-visual-proof.md)

## See A Deny


- Onyx fail-closed checks (identity/OPA/retrieval/secret): `test_strict_live_onyx_end_to_end.py`
- Dify MCP deny check: `test_strict_live_dify_handoff_denies_unapproved_mcp_server`
- Artifact set: [../evidence/reviewer/inspectable-live-runtime/](../evidence/reviewer/inspectable-live-runtime/)

## Claim boundary

- Proven now: governed live handoff path for Onyx + Dify with evidence-backed launch-gate behavior.
- Not implied: always-on public production hosting; that remains environment-specific.
