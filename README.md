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
make up-dev
make test-live-stack
```

Use the dashboard to launch governed capability lanes and inspect evidence artifacts under `overlays/myStarterKit/artifacts/`.
