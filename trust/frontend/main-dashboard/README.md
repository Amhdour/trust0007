# Main Dashboard

This frontend is the dashboard-first homepage for the repository.

- It is served by `backend/api_gateway/server.py`.
- It also serves a separate client-facing explanation layer at `/client-overview`.
- Shared dashboard labels and section metadata live in `contracts/control-plane-dashboard.json`.
- Current primary product surface is **Onyx governed RAG launch readiness**.
- A top-level **Launch Decision Header** now presents decision, runtime, evidence mode, top blocker, required action, and last-proven timestamp.
- A first-class **RAG Proof Chain** now renders: Identity → Policy → Retrieval Boundary → Source Boundary → Secrets → Telemetry → Launch Gate.
- A **Live Onyx Project** panel now explains folder mapping and runtime wiring:
  - `/onyx` = runtime source
  - `/trust` = trust control plane
  - `/trust/frontend/main-dashboard` = reviewer dashboard
  - `/trust/backend/api_gateway` = dashboard/API gateway
  - `/trust/launch-gate` = launch readiness gate
  - `/trust/evidence` = evidence artifacts
  - `/trust/policies` = policy-as-code controls
  - `/trust/telemetry` = telemetry + audit readiness
- A **Download Launch Gate Packet** control exports a deterministic JSON evidence bundle from the current dashboard state.
- Evidence mode is rendered with explicit badges: `LIVE`, `PARTIAL`, `DEMO`, `SAMPLE`, `UNKNOWN`.
- Audience modes are available for Executive, Security Reviewer, Operator, and Evidence/API reading paths.
- It now foregrounds a plain-language first layer, a compact command summary, a dominant live-vs-demo mode banner, a short reading guide, lighter summary-first reviewer sections, and deeper technical drilldowns.
- The homepage consumes `/api/control-plane/overview` for posture and evidence panels and `/api/control-plane/live-log` for recent activity.
- The client overview page reuses the same overview payload and the reviewer allow/deny artifacts, but presents them as simple visuals for non-technical audiences.
- The hero includes direct governed live workspace links for Onyx and an Onyx Agent compatibility link. Agent/MCP/tool-governance capabilities are visible only as deferred/future scope, not as active current RAG launch claims.
- The adjacent access-requirements panel explains that the deployment must already provide a valid Keycloak-backed browser session or bearer token.
- Drill-through links are expected to point at raw repo artifacts exposed by the API gateway under `/raw/...`.

## Live Onyx Project panel

- `/onyx` is the **root-level** Onyx governed RAG runtime source.
- `/trust` is the **root-level** Trust control-plane folder.
- `/onyx` and `/trust` are sibling project folders at repository root (the panel does not imply `/onyx` is inside `/trust`).
- `/trust/frontend/main-dashboard` is the reviewer dashboard served by `backend/api_gateway/server.py`.
- The panel makes folder locations explicit so reviewers can quickly see where runtime, policy, evidence, telemetry, and launch-gate components live.
- The panel shows runtime status plus evidence mode, and does **not** imply live connectivity unless evidence mode is `LIVE`.

## Scope for this pass

### Active
- Onyx RAG readiness
- Governed launch gates
- Retrieval and source-boundary proof
- Runtime guardrails, secrets posture, telemetry, auditability, incident readiness

### Deferred / not current RAG launch scope
- Dify Agent
- Autonomous-agent runtime governance
- MCP hardening
- Tool authorization / agent identity / capability escalation / HITL tool confirmation
