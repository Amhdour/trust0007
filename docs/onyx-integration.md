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
- `/api/control-plane/onyx-activity` classifies recent activity into direct Onyx path matches, correlated trace/session observability, and other nearby runtime activity for the current workspace.
- `/launch/onyx?path=/app&mode=live&view=embedded` is the dashboard-owned live workspace view for that same governed entry point.
- The live workspace path now requires a deployment-provided OIDC browser session or an explicit Keycloak-backed bearer token. The dashboard does not mint dev cookies anymore.
- For local/Codespaces previews, set `CONTROL_PLANE_LIVE_FRONT_DOOR_ENABLED=true` to expose `/auth/live/login?next=...`, which mints a Keycloak token using the configured live smoke principal and sets `kc_access_token` before redirecting to the governed launch route.
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

## Guardrails for future changes
- Keep governance logic in repo-owned adapters and evaluators, not inside upstream Onyx modules.
- Prefer new proof artifacts, traces, and dashboard signals over invasive upstream customization.
- If deeper Onyx integration is needed later, keep the contract at the normalized request/decision boundary.

## Test coverage
`tests/adapter/test_onyx_gateway_adapter.py` includes:
- happy path allow scenario,
- deny path scenario,
- telemetry emission assertions.

## Using remote Onyx from another GitHub Codespace

Remote Onyx is the primary integration mode for live verification in this repository.

1. Start Onyx in a separate GitHub Codespace.
2. Forward the Onyx web/API port from that Codespace.
3. Set port visibility so this trust0007 Codespace can access it (**Public** or **Organization**).
4. Copy the forwarded `.app.github.dev` URL.
5. Set:
   - `CONTROL_PLANE_ONYX_BASE_URL=https://your-onyx-codespace-port.app.github.dev`
   - `CONTROL_PLANE_ONYX_API_BASE_URL=https://your-onyx-codespace-port.app.github.dev/api`
6. Verify configuration and governed handoff:

```bash
make verify-remote-onyx
make verify-live
pytest -q tests/integration/test_strict_live_onyx_end_to_end.py
```

Use `CONTROL_PLANE_USE_LOCAL_ONYX=true` only for explicit local dev workflows that rely on `upstream/onyx`.

## Onyx Security Readiness Integration

The dashboard can ingest runtime security-readiness telemetry from an Onyx-compatible provider (`provider=onyx`) so launch decisions remain evidence-backed even when governance checks pass.

### Required environment variables

```bash
ONYX_BASE_URL=http://localhost:3000
ONYX_READINESS_PATH=/api/security/readiness
ONYX_READINESS_TOKEN=
ONYX_READINESS_TIMEOUT_MS=5000
ONYX_READINESS_ENABLED=true
```

- `ONYX_READINESS_TOKEN` is optional; if present the client sends `Authorization: Bearer <token>`.
- `ONYX_READINESS_ENABLED=false` disables remote calls and forces a safe degraded `unknown` readiness result.

### Expected endpoint shape

The endpoint is expected to return:
- system metadata (`system`, `component_type`, `environment`, `generated_at`)
- overall security posture (`overall_status`, `overall_score`)
- detailed checks with severity, status, evidence source/value/details, and recommendation
- risk rollups (`critical/high/medium/low`)
- capabilities (`rag`, `connectors`, `agents`, `mcp`, `tools`)

### Dashboard behavior

The **Onyx Security Readiness** panel (under **Onyx RAG Access**) shows:
- overall readiness status, score, generated timestamp, and environment
- capability badges and risk summary
- launch-gate category mapping across Identity, Retrieval, Connector, Prompt/Context, Agent Tool Auth, MCP, Secrets, Telemetry, and Incident families
- detailed check table (check/category/severity/status/score/evidence source/recommendation)
- evidence summaries and remediation list

If the endpoint is unreachable or invalid, the dashboard does **not** crash. It surfaces:
- `overall_status=unknown`
- `overall_score=0`
- message: `Onyx readiness endpoint unreachable`
- launch gate decision: `UNKNOWN`

### Launch gate decision logic

- **BLOCKED**: any critical check fails, or overall status is `fail`, or score `< 60`
- **CONDITIONAL**: overall status is `warn`, or score is `60-84`, or high-severity warning exists
- **APPROVED**: overall status is `pass`, score `>= 85`, and no critical/high failures
- **UNKNOWN**: endpoint unreachable, payload invalid, or unknown checks exceed threshold

### Example local setup

1. Start the control plane dashboard (`make serve-dashboard`).
2. Start Onyx or a local mock endpoint serving `/api/security/readiness`.
3. Export readiness env vars above.
4. Refresh the dashboard and open **Onyx RAG Access** → **Onyx Security Readiness**.
5. For local validation, use fixtures:
   - `fixtures/onyx-readiness-pass.json`
   - `fixtures/onyx-readiness-fail.json`
