# AI Trust & Security Stack Control Plane

This repository is now shaped as a **dashboard-first control plane** for an AI Trust & Security platform built around upstream projects and `myStarterKit`.

The homepage is a repo-owned **Trust & Security Operations Dashboard for RAG and Autonomous Agents**. Onyx is treated as a governed runtime module behind that dashboard instead of the primary visible entry.

Suggested short repository description:
`Dashboard-first AI Trust & Security Stack Control Plane for governed AI runtime launch readiness, policy enforcement, evidence integrity, and auditable Onyx handoffs.`

## Design intent

- Lead with the dashboard, then identity/session, then governed AI runtime, then evidence/analytics.
- Treat `upstream/*` as vendored third-party source snapshots.
- Treat `overlays/myStarterKit` as the governance overlay baseline.
- Keep local platform logic additive in:
  - `frontend/`
  - `backend/`
  - `contracts/`
  - `apps/`
  - `infra/`
  - `evidence/`
  - `overlays/`
  - `adapters/`
  - `policies/`
  - `telemetry/`
  - `launch-gate/`
  - `compose/`
  - `docs/`
  - `scripts/`

## Current structure snapshot

- `frontend/main-dashboard/`: custom control-plane homepage and navigation shell.
- `backend/`: dashboard API gateway, posture aggregation, evidence, launch-gate, and integration services.
- `contracts/`: JSON schemas for posture, retrieval, tools inventory, eval, audit, and launch-gate views.
- `apps/`: logical runtime/governance grouping for Onyx and myStarterKit.
- `infra/`: logical mapping for identity, policy, retrieval, telemetry, and evidence systems.
- `evidence/`: dashboard-owned evidence export area.
- `upstream/`: vendored copies of Keycloak, Envoy, Onyx, OPA, Vault, Qdrant, optional gVisor, Langfuse, Grafana, and Superset sources.
- `overlays/myStarterKit/`: governance-overlay submodule.
- `overlays/governance-overlay/`: local, additive overlay contracts and integration wiring (this repo).
- `adapters/`: Python adapters for policy/runtime/retrieval/secrets/sandbox/observability bridges.
- `policies/`: OPA policy bundles and tests.
- `telemetry/`: event schema, sinks, exporters, and dashboard artifacts.
- `launch-gate/`: evidence-based readiness evaluator.
- `compose/`: local development stack definitions.
- `.devcontainer/`: Codespaces/devcontainer setup.

## Phase status

Execution plan tracking and phase notes are stored under `docs/phases/`.

## Homepage Information Architecture

The homepage is now optimized to answer the reviewer questions in under 10 seconds:

- What is protected: asset and protection coverage across surfaces, tenants, roles, retrieval sources, tools, MCP servers, and the governed Onyx runtime.
- What was blocked: denied retrievals, denied tool attempts, confirmation-required actions, and blocked `/launch/onyx` handoffs.
- Why it was blocked: surfaced reason codes, policy source, policy path, trace IDs, tenants, actors, and surfaces.
- What evidence exists: reviewer bundles, governed flow traces, launch-gate outputs, telemetry exports, and replay-ready artifacts.
- Is the system launch-ready: dominant launch gate panel with readiness status, control-family summaries, top failing controls, and residual risks.

See `docs/control-plane-dashboard-homepage.md` for the homepage structure, data sources, and real-versus-demo notes.

## Quickstart

Run the minimal in-repo demo:

```bash
make demo
```

Validate the primary runtime integration target:

```bash
make test-onyx-target
```

Test governance enforcement (live artifacts + handoff blocking):

```bash
make test-governance
```

Run the full test suite:

```bash
make test
```

Serve the local control-plane dashboard API/UI shell:

```bash
make serve-dashboard
```

## Development vs Production Simulation

**Development stack** (current default):
```bash
docker-compose -f compose/docker-compose.yml up
```
- Keycloak/Vault in dev mode
- Localhost-only service exposure
- Development defaults for rapid iteration

**Production simulation** (hardened stack):
```bash
docker-compose -f compose/docker-compose.prod-sim.yml up
```
- Keycloak/Vault in production mode
- Security hardening (read-only filesystems, no-new-privileges)
- Proper initialization requirements
- External certificate/trust store support

## Upstream integration model

Not every vendored upstream under `upstream/` is an equally active part of the current architecture.

- Active now: Onyx and Langfuse materially contribute to the current governed runtime or evidence path.
- Partially used: Keycloak, Envoy, OPA, Vault, Qdrant, and Grafana are present through containers, policy, adapters, or bridge configs, but some are not yet mandatory request-path dependencies.
- Optional future: Superset and gVisor stay in scope only as future analytics or isolation depth.
- Reference only: supporting snapshots such as Keycloak Quickstarts, the OPA Envoy Plugin, and the Langfuse Python SDK are retained for implementation reference, not for active architecture claims.

See `docs/upstream-usage-matrix.md` for the reviewer-facing explanation and `evidence/upstream_usage.inventory.json` for the machine-readable inventory surfaced by the dashboard.

## Runtime Testing Model

- `Onyx` is the primary sample runtime platform for real integration testing in this repo.
- The in-repo demo is the fast fallback path when the upstream Onyx stack is not running.
- The dashboard remains the product entrypoint, and Onyx is the governed runtime reached behind it.
- **Governance enforcement** is now live: `/launch/onyx` blocks denied requests with audit trails.
