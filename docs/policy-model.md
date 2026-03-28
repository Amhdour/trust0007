# OPA Policy Model

This document describes the current policy model implemented under `policies/rego/` and the runtime policy bundle consumed by the local control-plane server.

## Scope
This phase defines policy logic and tests only. It does **not** integrate with Envoy yet.

## Decision contract
Main rule: `data.umbrella.policy.decision`

Decision output fields:
- `allow` (bool)
- `default_deny` (bool)
- `fallback_to_rag` (bool)
- `kill_switch` (bool)
- `reasons` (sorted string array)

## Implemented policy controls
- Tool allowlist
- Confirmation-required tools
- Forbidden tools
- Argument-level tool validation
- Forbidden request fields
- Retrieval source allowlist
- Tenant restrictions
- Tenant role constraints
- Path-specific Onyx surface controls
- Retrieval trust-label and provenance requirements
- Default deny behavior
- Fallback-to-RAG decision
- Kill switch override

## Runtime bundle preference
- Preferred runtime source: `overlays/myStarterKit/policies/bundles/default/policy.json`
- Fallback runtime source: `policies/runtime-policy-fallback.json`
- The dashboard and governed-flow artifacts now surface which source was used at runtime.

## Files
- Policy logic: `policies/rego/policy.rego`
- Tests: `policies/tests/policy_test.rego`
- Example inputs/decisions: `policies/examples/*.json`

## Example evaluation
```bash
opa eval -f pretty -d policies/rego/policy.rego -i policies/examples/input-allow.json "data.umbrella.policy.decision"
```

Run tests:
```bash
opa test policies/rego policies/tests -v
```
