# Onyx + Trust Production Integration Checklist

Use this checklist to connect:

- **Onyx** as the AI/RAG runtime.
- **Trust** as the governance, security, readiness, launch-gate, and evidence control plane.

---

## 1) Topology and reachability

- [ ] Onyx API is reachable from Trust (`CONTROL_PLANE_ONYX_API_BASE_URL`).
- [ ] Onyx web/base URL is reachable from Trust (`CONTROL_PLANE_ONYX_BASE_URL`).
- [ ] Cross-environment networking is explicitly allowed (`CONTROL_PLANE_EXTERNAL_REACHABLE=true`).
- [ ] Local-target bypasses are disabled for production (`CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS=false`).
- [ ] HTTPS/TLS termination is defined and certificate rotation is documented.

## 2) Identity and authN/authZ

- [ ] Trust has a runtime credential path configured (`CONTROL_PLANE_ONYX_SECRET_PATH`).
- [ ] Runtime secret key name is configured (`CONTROL_PLANE_RUNTIME_SECRET_KEY`).
- [ ] Onyx service credential is least-privilege (scoped token, non-admin).
- [ ] Keycloak (or equivalent IdP) role mapping is tested for all launch lanes.
- [ ] Agent/tool authorization policy is tested for allow + deny cases.

## 3) Policy and launch-gate controls

- [ ] Runtime policy schema validates.
- [ ] Governance policy bundle is loaded and enforced.
- [ ] Launch-gate blocker thresholds are defined for each capability lane:
  - `/launch/onyx/chat`
  - `/launch/onyx/search`
  - `/launch/onyx/agent`
  - `/launch/onyx/mcp`
  - `/launch/onyx/admin`
- [ ] Fail-closed behavior is verified when any critical dependency is down.

## 4) Secrets and dependency health

- [ ] Vault (or equivalent secret manager) path exists and rotates on schedule.
- [ ] Trust health checks fail fast when secret retrieval fails.
- [ ] OPA policy engine is reachable and policy decisions are auditable.
- [ ] Qdrant/vector dependency health is visible to gate scoring.
- [ ] Langfuse/observability dependency health is visible to gate scoring.

## 5) Telemetry, audit, and evidence

- [ ] Trust dashboard shows Onyx Security Readiness with non-`UNKNOWN` status.
- [ ] Evidence artifacts are generated and retained per policy.
- [ ] Decision logs capture identity, policy, retrieval, tool, and gate outcomes.
- [ ] Alerting exists for `BLOCKED` spikes and repeated `UNKNOWN` transitions.
- [ ] Clock sync/timezone consistency is validated across components.

## 6) Pre-launch verification workflow

Run before opening runtime access:

```bash
make verify-remote-onyx
make verify-live
make preflight-onyx-trust
```

Then confirm dashboard + evidence:

- [ ] Onyx Security Readiness panel is populated.
- [ ] Gate decision matches expected policy posture (`APPROVED` / `CONDITIONAL` / `BLOCKED`).
- [ ] Evidence records include current run identifiers and timestamps.

## 7) Test coverage expectations

- [ ] Unit tests for policy evaluators and adapters.
- [ ] Integration tests for governed flow and denial flow.
- [ ] Live end-to-end tests for strict launch-gate enforcement.
- [ ] Dashboard tests for readiness rendering + degraded mode handling.
- [ ] Incident drills for Onyx unreachable, Vault unavailable, OPA unavailable.

## 8) Operational hardening suggestions

- [ ] Add a single `make check-fast` target for local contributors.
- [ ] Add CI gating that blocks merges on schema/policy drift.
- [ ] Publish SLOs for readiness API and launch-gate decision latency.
- [ ] Define rollback playbooks for policy regression and auth outage.
- [ ] Record RACI for security approvals and launch override authority.

---

## Recommended “go-live” definition

Proceed only when all of these are true:

1. `make verify-remote-onyx` passes.
2. `make verify-live` passes.
3. Dashboard readiness is populated (not `UNKNOWN`).
4. Evidence generation is current and complete.
5. Fail-closed deny path is verified in a controlled test.
