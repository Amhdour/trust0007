# Request Flow & Governance Enforcement

This document describes the governed runtime path in both `demo` and `live` modes.

- `demo` mode exists for local iteration and fallback proof.
- `live` mode is the strict governed path. In live mode, `/launch/onyx` fails closed unless live identity, live policy, live retrieval, conditional live secret access, trace correlation, and launch-gate evidence all succeed.

See `docs/upstream-usage-matrix.md` and `docs/live-vs-demo-matrix.md` for the strict activation model.

## High-level flow

1. Client request enters via dashboard or API gateway.
2. Identity context is established.
3. Governance evaluation runs.
4. Trace correlation is recorded.
5. Launch-gate evaluates the current evidence set.
6. Handoff is allowed or denied.
7. Response returns with traceability metadata and artifacts.

## Demo mode

- Identity may be repo-local fallback identity.
- Policy may be repo-local evaluation.
- Retrieval may use seeded fallback behavior.
- Launch-gate may summarize demo/sample evidence.

Demo mode is useful for fast iteration, but it is not equivalent to the strict live governed path.

## Live mode

In live mode, governed handoff to `/launch/onyx` requires this order:

1. Keycloak-backed bearer token or session cookie is resolved into normalized identity.
   The local strict-live smoke path requests `openid email profile` scope so Keycloak `userinfo` can participate. Without `openid`, identity should fail closed.
2. OPA receives the live policy input and returns an auditable decision.
3. Retrieval executes against the configured live backend and passes tenant, trust, and provenance checks.
4. Required runtime secret access succeeds through Vault-backed secret retrieval.
5. Tool governance is recorded under the same trace and session context.
6. Live evidence artifacts are written.
7. Launch-gate evaluates the live evidence set.
8. Only then is the governed handoff to Onyx allowed.

If any required dependency fails, the flow fails closed.

## Allow path example

```text
User clicks Open Chat
  ->
/launch/onyx?path=/app&mode=live
  ->
Identity: Keycloak-backed identity resolved
Policy: OPA allow
Retrieval: Qdrant-backed retrieval allowed
Secret: Vault-backed runtime secret fetched
Trace: correlated
Launch gate: pass
  ->
Governed handoff approved
```

## Deny path examples

```text
Missing bearer token in live mode
  ->
Identity: deny
Launch gate: no_go
  ->
403 denied handoff
```

```text
Bearer token valid but no session correlation
  ->
Identity: live
Policy: allow
Retrieval: allow
Secret: allow
Trace: incomplete
Launch gate: no_go
  ->
403 denied handoff
```

## Live evidence artifacts

Live or demo governed-flow runs can write:

- `overlays/myStarterKit/artifacts/events.jsonl`
- `overlays/myStarterKit/artifacts/identity-evidence.json`
- `overlays/myStarterKit/artifacts/policy-evidence.json`
- `overlays/myStarterKit/artifacts/retrieval-evidence.json`
- `overlays/myStarterKit/artifacts/secret-evidence.json`
- `overlays/myStarterKit/artifacts/trace-correlation.json`
- `overlays/myStarterKit/artifacts/governed-flow-summary.json`
- `overlays/myStarterKit/artifacts/launch-gate-result.json`

These artifacts are what the dashboard should prefer whenever live mode is enabled and recent governed-flow evidence exists.

## API endpoints

### `/api/control-plane/governed-flow`

Triggers complete governance evaluation and artifact generation.

Supported query options:

- `mode=demo|live`
- `secret_required=true`

### `/launch/onyx?path=/app`

Governed handoff to the Onyx runtime.

- `mode=demo`: fallback/demo behavior allowed.
- `mode=live`: strict fail-closed governed handoff.

## Reviewer note

Do not describe live identity, live OPA, live retrieval, live secret access, or live-evidence launch-gate as active unless the artifacts above were produced by the governed flow being reviewed.

Local development note:

- The staging bootstrap maps `tenant_id` from a real Keycloak user attribute into token and userinfo claims. The control-plane default tenant env var is only a fallback for non-live demo flows.
