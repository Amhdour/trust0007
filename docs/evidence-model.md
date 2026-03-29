# Evidence Model

This repo prefers file-backed evidence artifacts first so reviewers can inspect the governed path without relying on an external telemetry system.

## Primary governed-flow artifacts

When a governed flow runs, the control plane can emit:

- `overlays/myStarterKit/artifacts/events.jsonl`
- `overlays/myStarterKit/artifacts/identity-evidence.json`
- `overlays/myStarterKit/artifacts/policy-evidence.json`
- `overlays/myStarterKit/artifacts/retrieval-evidence.json`
- `overlays/myStarterKit/artifacts/secret-evidence.json`
- `overlays/myStarterKit/artifacts/audit-records.jsonl`
- `overlays/myStarterKit/artifacts/trace-correlation.json`
- `overlays/myStarterKit/artifacts/governed-flow-summary.json`
- `overlays/myStarterKit/artifacts/launch-gate-result.json`

## Correlation model

Each governed request should keep these relationships stable:

- `trace_id`: joins the end-to-end governed flow
- `request_id`: identifies the request instance
- `session_id`: links live Keycloak-backed session state when available
- `actor_id`: identifies the acting principal
- `tenant_id`: identifies the governed tenant
- `surface`: identifies the governed surface or path

The dashboard uses those values to render reviewer-facing continuity across identity, policy, retrieval, secret, audit, launch-gate, and handoff stages. If `session_id` is unavailable, the trace artifact should record a precise reason rather than a generic missing state.

## Live-mode mandatory evidence

In `live` mode, a governed handoff should not be treated as valid unless evidence proves:

1. identity was live-derived
2. OPA returned a decision
3. retrieval executed against the configured backend
4. required secret access succeeded when needed
5. trace correlation stayed intact
6. launch-gate evaluated the live evidence set

If required evidence is missing in `live` mode, the launch gate should degrade readiness and the handoff should fail closed.

## Dashboard usage

The homepage reads these artifacts into:

- Identity & Session
- Policy Enforcement
- Retrieval Boundaries
- Secret Access
- Audit & Replay
- Trace Correlation
- Launch Gate
- Onyx Runtime

Langfuse and Grafana remain useful supporting surfaces, but the repo-owned artifacts are the primary reviewer proof path.
