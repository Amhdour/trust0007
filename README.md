# AI Trust & Security Stack Control Plane

This repository is now shaped as a **dashboard-first control plane** for an AI Trust & Security platform built around upstream projects and `myStarterKit`.

The homepage is a repo-owned **Trust & Security Operations Dashboard for RAG and Autonomous Agents**. Onyx is treated as a governed runtime module behind that dashboard instead of the primary visible entry.

## Design intent

- Lead with the dashboard, then identity/session, then governed AI runtime, then evidence/analytics.
- Treat `upstream/*` as third-party source of truth.
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
- `upstream/`: pinned submodules for Keycloak, Envoy, Onyx, OPA, Vault, Qdrant, optional gVisor, Langfuse, Grafana, and Superset.
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
