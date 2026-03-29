# Control Plane vs Runtime Plane

This document describes logical placement, not equal activation depth. For current repo-backed status, see `docs/upstream-usage-matrix.md`.

## Control plane

The control plane governs **what is allowed** and **under which conditions**.
In this repo, it is also the primary visible product entry: the reviewer/operator lands on the dashboard first and sees whether access to Onyx is allowed, why, and with what evidence.

### Components in control plane
- Keycloak (identity assertions and session context when live identity wiring is enabled)
- Envoy (ingress enforcement and routing policy when the ingress bridge is enabled)
- myStarterKit governance layer (runtime governance intent)
- OPA (policy-language authority and mandatory live decision engine on the strict governed path)
- myStarterKit launch gate (evidence-driven readiness/launch decisions)

### Control-plane outputs
- Allow/deny decisions
- Action constraints (tool scopes, retrieval limits, secret-access conditions)
- Readiness/launch gating decisions

## Runtime plane

The runtime plane executes the request path and tool/data interactions.
In this repo, Onyx is the governed runtime plane behind dashboard-controlled handoffs rather than the primary visible homepage.

### Components in runtime plane
- Onyx runtime (reasoning/orchestration)
- Vault access path (when secret integration is enabled)
- Qdrant retrieval path (when live retrieval integration is enabled)
- gVisor sandbox path (when risky execution isolation is implemented)

### Runtime-plane outputs
- Response artifacts
- Tool execution results
- Retrieval outputs
- Runtime execution state

## Evidence plane (cross-cutting)

Evidence flows across both planes.

- Langfuse collects traces, evaluations, and policy/control events.
- Grafana and optional Superset views expose evidence drill-downs.
- Launch gate consumes evidence to influence future control-plane decisions.

## Policy flow across planes

1. Control plane establishes identity and policy context.
2. Runtime plane requests action authorization as needed.
3. Control plane returns policy decision/constraints.
4. Runtime plane executes or blocks action based on policy.
5. Evidence plane records decision and execution outcomes.
