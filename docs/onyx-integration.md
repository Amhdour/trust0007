# Onyx Gateway Adapter Integration (myStarterKit Controls)

## Purpose
`adapters/onyx_gateway_adapter/` provides a boundary adapter that accepts normalized runtime requests and applies governance checks without depending on upstream Onyx internals.

## Role in this repository
- Onyx is the primary sample runtime platform for real integration testing.
- The dashboard is still the main product entrypoint.
- The in-repo demo is the fallback path when the upstream Onyx stack is unavailable.

## Responsibilities implemented
- Accept normalized request input from runtime (`NormalizedRequest`).
- Invoke policy checks (`PolicyChecker`).
- Invoke retrieval checks (`RetrievalChecker`).
- Invoke tool decision checks (`ToolDecisionChecker`).
- Emit telemetry events (`TelemetryEmitter`).
- Return normalized decision output (`NormalizedDecision`).

## Interfaces
- `PolicyChecker.check_policy(request) -> PolicyDecision`
- `RetrievalChecker.check_retrieval(request) -> RetrievalDecision`
- `ToolDecisionChecker.check_tools(request) -> ToolDecision`
- `TelemetryEmitter.emit(event) -> None`

These interfaces are intentionally minimal and stable for local-development integration.

## Typed schemas
Defined dataclass schemas:
- `NormalizedRequest`
- `PolicyDecision`
- `RetrievalDecision`
- `ToolDecision`
- `TelemetryEvent`
- `NormalizedDecision`

## Decision semantics
The adapter returns `allow=true` only when:
1. policy check allows,
2. retrieval check allows,
3. no tools are denied.

Any failed check results in deny with aggregated reasons.

## Independence from upstream Onyx internals
- Adapter only consumes normalized DTOs and interfaces.
- No import or coupling to upstream `upstream/onyx` modules.
- Integration point can be attached by a thin runtime wrapper.

## Runtime proof after handoff
- `/launch/onyx` is the governed entry point into the runtime plane.
- `/api/control-plane/live-session` reports whether the local dev-only session cookie is currently valid for the embedded workspace.
- `/auth/live-session/start` is a dev-only control-plane helper that mints a local `kc_access_token` cookie and redirects back into a governed live handoff.
- `/auth/live-session/end` clears that cookie and returns the browser to the dashboard.
- `/launch/onyx?path=/app&mode=live&view=embedded` is the dashboard-owned live workspace view for that same governed entry point.
- A successful or denied handoff now writes `overlays/myStarterKit/artifacts/onyx-runtime-proof.json`.
- That artifact summarizes:
  - the requested Onyx path,
  - the governed trace and session identifiers,
  - runtime reachability after the handoff decision,
  - the latest visible Onyx runtime activity, and
  - whether current runtime activity can be tied back to the governed path.

This keeps the proof model honest: the control plane proves the launch decision first, then records what was visible at the runtime edge afterward.

## Readiness contract
- `scripts/start-onyx-lite.sh` remains the supported way to start the local runtime quickly.
- Runtime readiness is treated separately from governance approval.
- A handoff can be approved while readiness is still degraded, and the runtime proof artifact should show that difference clearly.
- The embedded live workspace only frames Onyx when the public runtime target is reachable; otherwise it stays in the control-plane shell and explains what still needs to be started, exposed, or retried.
- The live-session helper is intentionally labeled as dev-only so the local browser path does not get mistaken for a production auth flow.

## Guardrails for future changes
- Keep governance logic in repo-owned adapters and evaluators, not inside upstream Onyx modules.
- Prefer new proof artifacts, traces, and dashboard signals over invasive upstream customization.
- If deeper Onyx integration is needed later, keep the contract at the normalized request/decision boundary.

## Test coverage
`tests/adapter/test_onyx_gateway_adapter.py` includes:
- happy path allow scenario,
- deny path scenario,
- telemetry emission assertions.
