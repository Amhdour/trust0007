# Trust & Security Readiness Platform

This repo is a dashboard-first trust operating layer for governed Onyx and Onyx Agent deployments. It is not a chat UI. The control plane decides whether a runtime is allowed to launch, what it may access, what tools it may call, and which evidence proves the decision.

## Repo Assessment

Current architecture:

- `backend/api_gateway` serves the dashboard, governed launch routes, raw evidence, and JSON control-plane APIs.
- `backend/governance_flow_evaluator.py` orchestrates identity, policy, retrieval, secrets, tool governance, audit records, telemetry, and launch-gate evidence.
- `adapters/identity`, `adapters/policy`, `adapters/retrieval`, `adapters/secrets`, `adapters/tools`, and `adapters/onyx_gateway_adapter` isolate runtime dependency concerns.
- `launch-gate/` evaluates control evidence into pass, conditional, or no-go launch decisions.
- `backend/trust_readiness/` is the typed product layer for runtime readiness states, policy-as-code decisions, evidence bundles, incident controls, and dashboard page contracts.
- `frontend/main-dashboard/` consumes the dashboard/control-plane payloads.

Strengths:

- Fail-closed governed flow exists and is tested for identity, OPA policy, retrieval, Vault-backed secrets, tool governance, trace correlation, audit records, and launch gates.
- Onyx and Onyx Agent launch routes are control-plane owned (`/launch/onyx`, `/launch/onyx/agent`) rather than direct runtime links.
- Evidence artifacts are structured, replayable, and tied to trace/request/session/tenant identifiers.

Current gaps addressed in this iteration:

- Readiness states are now typed as `READY`, `READY_WITH_EXCEPTIONS`, `BLOCKED`, `DEGRADED`, `UNDER_REVIEW`, and `INCIDENT_MODE`.
- Onyx Agent MCP/tool authorization now has a first-class governed lane model.
- Dashboard backend pages now have page-specific JSON contracts.
- Policy-as-code now includes deterministic, deny-by-default decision traces for readiness APIs and tests.

Prototype versus production-ready:

- Production-oriented: governed handoff spine, fail-closed launch gates, audit JSONL design, evidence correlation, OPA/Vault/Qdrant/Keycloak live paths, runtime readiness schemas, dashboard contracts.
- Prototype/local-development: single-file JSONL audit storage, file-backed incident controls, local policy persistence, static dashboard frontend, and environment-owned production ingress/secret rotation/monitoring.

Prioritized transformation plan:

1. Preserve the current governed-flow evaluator as the enforcement spine.
2. Add typed readiness, evidence, incident, policy, and runtime-lane modules.
3. Expose page-specific dashboard APIs for operators and reviewers.
4. Promote Onyx and Onyx Agent into explicit governed launch lanes with separate risk models.
5. Expand tests around policy decisions, readiness states, degraded mode, incidents, and mocked runtime adapters.
6. Replace local JSONL/file storage with append-only durable storage in production.
7. Attach live eval/red-team CI results as first-class readiness evidence.

## Product Modules

1. Control Plane / Dashboard: `backend/api_gateway/server.py`, `backend/posture_service/service.py`, `backend/trust_readiness/dashboard_api.py`
2. Identity & Authorization: `adapters/identity/`
3. Policy Engine: `adapters/policy/`, `policies/`, `backend/trust_readiness/policy_engine.py`
4. Retrieval Security: `adapters/retrieval/`, `backend/trust_readiness/launch_lanes.py`
5. Agent Tool Authorization / MCP Hardening: `adapters/tools/`, `backend/trust_readiness/launch_lanes.py`
6. Telemetry / Audit / Evidence: `telemetry/`, `backend/trust_readiness/evidence.py`, `backend/evidence_service/`
7. Launch Gates: `launch-gate/`, `backend/launch_gate_service/`, `backend/trust_readiness/readiness.py`
8. Incident Readiness: `backend/trust_readiness/incidents.py`

## Readiness State Model

- `READY`: all mandatory evidence passes and no incident controls are active.
- `READY_WITH_EXCEPTIONS`: launch is allowed but optional eval, waiver, or review signals remain.
- `BLOCKED`: a mandatory control fails, is missing, or is stale.
- `DEGRADED`: mandatory launch can continue only in reduced capability mode.
- `UNDER_REVIEW`: mandatory evidence needs review before promotion.
- `INCIDENT_MODE`: active incident controls override normal launch state.

Signals include identity health, secret health, policy evaluation, retrieval boundary, connector freshness, MCP/tool authorization, telemetry heartbeat, audit health, eval status, and launch-gate approval.

## Runtime Sequences

Onyx governed RAG lane:

```text
dashboard -> /launch/onyx -> identity -> policy -> retrieval boundary -> secret health -> tool check -> telemetry/audit -> launch gate -> Onyx runtime handoff
```

Onyx Agent governed agent lane:

```text
dashboard -> /launch/onyx/agent -> identity -> policy -> MCP allowlist -> tool risk/approval -> secret health -> telemetry/audit -> launch gate -> Onyx Agent execution plane
```

Incident/degraded mode:

```text
secops action -> incident control record -> readiness recompute -> launch blocked/degraded -> audit evidence -> dashboard incident page
```

## Dashboard APIs

- `/api/fleet/overview`
- `/api/runtime/readiness`
- `/api/runtime/readiness/{runtime_id}`
- `/api/retrieval/boundary-posture`
- `/api/tools/mcp-authorization`
- `/api/launch-gates`
- `/api/evidence-audit`
- `/api/incidents`
- `/api/exceptions-waivers`

## Onyx Integration

Onyx is the governed RAG runtime. The control plane enforces per-tenant source scope, auth-mode awareness, retrieval classification and purpose checks, source trust labels, provenance fields, connector/index freshness, and launch gates before handoff.

Onyx must not be exposed as an unrestricted runtime target in production.

## Onyx Agent Integration

Onyx Agent is the governed agent execution plane. The control plane enforces workflow/app registration metadata, MCP server allowlists, tool allowlists, per-tool risk classification, human approval for privileged/destructive/external-write/high-risk tools, and launch gates before workflow/app handoff.

Onyx Agent must not become a bypass around identity, tool authorization, or audit.

## Local Dev

```bash
make up-dev
pytest -q tests/trust_readiness tests/dashboard tests/launch-gate tests/telemetry tests/retrieval tests/tools
```

## Staging Deployment

```bash
cp .env.live.example .env.live
make bootstrap-live
make verify-live
make up-live
```

Staging proof requires Keycloak, OPA, Qdrant, Vault, reachable Onyx, reachable Onyx Agent, and current governed-flow artifacts.

## Production Hardening

Add external ingress with DNS/TLS, durable append-only audit storage, managed secret rotation, external SIEM/observability sinks, signed policy bundles, tenant-isolated evidence storage, incident-control approvals, eval/red-team CI evidence ingestion, backup/restore, and retention policies.

## Threat Model

Primary threats include cross-tenant retrieval leakage, high-classification access without clearance, stale evidence used for launch approval, unapproved Onyx Agent MCP tools, privileged tool use without approval, runtime handoff without live identity, unhealthy telemetry/audit sinks, and incident controls not overriding launch paths.

Mitigations are fail-closed defaults, explicit decision traces, tenant/source/classification/purpose boundaries, MCP/tool allowlists, high-risk approval requirements, evidence-computed readiness states, append-only audit records, and incident controls that force `INCIDENT_MODE`.

## Roadmap

1. Durable tamper-evident audit/event store.
2. Runtime-specific Onyx Agent activity feed parity with Onyx.
3. Eval/red-team CI ingestion as mandatory launch evidence.
4. Policy bundle signing and promotion workflow.
5. Tenant-scoped evidence retention and legal hold.
6. Incident-control API mutations with approval workflow.
7. Real connector/index freshness probes per Onyx source.
8. Per-tool Onyx Agent execution receipts.
9. Exportable launch decision packets for change advisory boards.
10. Multi-tenant admin UI for waivers, exceptions, and break-glass review.
