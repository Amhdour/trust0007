# OPA Policy Model (Initial)

This document describes the initial policy model implemented under `policies/rego/`.

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
- Forbidden request fields
- Retrieval source allowlist
- Tenant restrictions
- Default deny behavior
- Fallback-to-RAG decision
- Kill switch override

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
