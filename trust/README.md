# Onyx Trust & Security Readiness Control Plane

**Onyx-native governance for RAG and agentic workflows with fail-closed launch gates, policy-as-code, and evidence-backed runtime approvals.**

This repository is a production-oriented consulting artifact for delivering AI Trust & Security Readiness engineering to enterprise teams running Onyx-based retrieval and autonomous agent capabilities.

## Platform positioning

This control plane is built to deliver three client offers:

- **Layer Retrofit**: add governance, controls, and evidence to existing Onyx deployments.
- **Secure Starter Kits**: provision an opinionated Onyx-native baseline with policy, telemetry, and launch governance.
- **Launch Gates**: enforce fail-closed readiness approvals before runtime access.

## Onyx-native architecture

The repository now operates as a **single runtime model** with governed capability lanes:

- `/launch/onyx/chat`
- `/launch/onyx/search`
- `/launch/onyx/agent`
- `/launch/onyx/mcp`
- `/launch/onyx/admin`

The control plane evaluates identity, policy, retrieval boundaries, tool/MCP authorization, secret health, telemetry integrity, and launch-gate evidence **before** any runtime handoff.

## Control families

- **Retrieval Security & Data Boundaries**
- **Agent Identity & Tool Authorization**
- **Policy-as-Code & Runtime Guardrails**
- **MCP Hardening**
- **Telemetry, Auditability & Evidence Integrity**
- **Incident Readiness**
- **Fail-Closed Launch Gate Approval**

## Repository structure

- `backend/` – control-plane APIs, governance evaluator, readiness and repair services.
- `adapters/` – identity, retrieval, tool, policy, and observability integration adapters.
- `policies/` – policy-as-code baseline and test fixtures.
- `overlays/` – governed client overlays and runtime policy bundles.
- `evidence/` – launch-gate evidence contracts and generated artifacts.
- `docs/` – architecture, runbooks, readiness models, and operator guidance.
- `tests/` – policy, integration, dashboard, runtime-repair, and launch-gate tests.

## Launch-gate discipline

In `live` mode, governed Onyx handoff is denied unless all required controls pass:

1. identity resolution and role checks
2. policy-as-code decision checks
3. retrieval boundary enforcement
4. tool/MCP authorization checks for agentic actions
5. secrets/runtime dependency health
6. telemetry and audit evidence integrity
7. launch-gate scoring and blocker validation

## Quick start

```bash
make help
make up-dev
make test-live-stack
```

Use the dashboard to launch governed capability lanes and inspect evidence artifacts under `overlays/myStarterKit/artifacts/`.
`make up-dev` now also brings up a local `onyx_runtime` service on port `3010`, and the dashboard's **Onyx Security Readiness** panel is wired to that runtime (`/api/security/readiness`) for immediate visibility in Codespaces.

If you open the repository from root, you can run the same commands via the root wrapper Makefile (`make help`, `make test`, `make up-dev`).

## Using remote Onyx from another GitHub Codespace

1. Start your Onyx stack in a separate Codespace.
2. Forward the Onyx web/API port in that Onyx Codespace.
3. Set the forwarded port visibility so this trust0007 Codespace can reach it (typically **Public** or **Organization**).
4. Copy the forwarded HTTPS URL ending in `.app.github.dev`.
5. Configure this repository with:
   - `CONTROL_PLANE_ONYX_BASE_URL`
   - `CONTROL_PLANE_ONYX_API_BASE_URL`
6. Run:

```bash
make verify-remote-onyx
make verify-live
pytest -q tests/integration/test_strict_live_onyx_end_to_end.py
```

Example environment values:

```bash
CONTROL_PLANE_ONYX_BASE_URL=https://your-onyx-codespace-port.app.github.dev
CONTROL_PLANE_ONYX_API_BASE_URL=https://your-onyx-codespace-port.app.github.dev/api
CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS=false
CONTROL_PLANE_EXTERNAL_REACHABLE=true
CONTROL_PLANE_ONYX_SECRET_PATH=secret/data/runtime/tenant-stage/onyx
CONTROL_PLANE_RUNTIME_SECRET_KEY=api_token
CONTROL_PLANE_USE_LOCAL_ONYX=false
```

## Onyx Security Readiness Integration

`trust0007` can consume security-readiness telemetry from `onyx007` (`GET <ONYX_BASE_URL>/api/security/readiness`) and render launch-readiness for secure RAG/agent runtime rollout.

- The dashboard now includes an **Onyx Security Readiness** panel with launch-gate decisioning (`APPROVED`, `CONDITIONAL`, `BLOCKED`, `UNKNOWN`), risk summary, capability badges, category gates, detailed checks, evidence, and remediations.
- The integration is provider-oriented (`provider=onyx`) so additional runtimes can be added without hard-coding the entire dashboard around Onyx.
- If Onyx is unreachable, the panel degrades safely to `unknown` status and keeps the rest of the dashboard functional.

## Run Onyx + Trust together (recommended wiring)

Yes — the intended operating model is:

- **Onyx** = AI/RAG runtime system.
- **Trust** = governance, policy, launch-gate, and evidence control plane.

To see Onyx status in the Trust dashboard:

1. Run Onyx and ensure it is externally reachable from the Trust environment.
2. Set these Trust environment values:
   - `CONTROL_PLANE_ONYX_BASE_URL`
   - `CONTROL_PLANE_ONYX_API_BASE_URL`
   - `CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS=false`
   - `CONTROL_PLANE_EXTERNAL_REACHABLE=true`
3. Ensure runtime secret pointers are configured:
   - `CONTROL_PLANE_ONYX_SECRET_PATH`
   - `CONTROL_PLANE_RUNTIME_SECRET_KEY`
4. Verify connectivity before launch:

```bash
make verify-remote-onyx
make verify-live
make preflight-onyx-trust
```

If both verification commands pass, open the Trust dashboard and validate the **Onyx Security Readiness** panel is populated (instead of `UNKNOWN`) with checks/evidence from the remote Onyx runtime.

For a complete pre-production checklist, see `docs/onyx-trust-production-checklist.md`.
