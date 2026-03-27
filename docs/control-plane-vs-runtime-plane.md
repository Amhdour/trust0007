# Control Plane vs Runtime Plane

## Control plane

The control plane governs **what is allowed** and **under which conditions**.

### Components in control plane
- Keycloak (identity assertions and session context)
- Envoy (ingress enforcement and routing policy)
- myStarterKit governance layer (runtime governance intent)
- OPA (policy decision authority)
- myStarterKit launch gate (evidence-driven readiness/launch decisions)

### Control-plane outputs
- Allow/deny decisions
- Action constraints (tool scopes, retrieval limits, secret-access conditions)
- Readiness/launch gating decisions

## Runtime plane

The runtime plane executes the request path and tool/data interactions.

### Components in runtime plane
- Onyx runtime (reasoning/orchestration)
- Vault access path (when secrets are needed)
- Qdrant retrieval path (when retrieval is needed)
- gVisor sandbox path (when risky execution is identified)

### Runtime-plane outputs
- Response artifacts
- Tool execution results
- Retrieval outputs
- Runtime execution state

## Evidence plane (cross-cutting)

Evidence flows across both planes.

- Langfuse collects traces, evaluations, and policy/control events.
- Grafana/Superset expose evidence views.
- Launch gate consumes evidence to influence future control-plane decisions.

## Policy flow across planes

1. Control plane establishes identity and policy context.
2. Runtime plane requests action authorization as needed.
3. Control plane returns policy decision/constraints.
4. Runtime plane executes or blocks action based on policy.
5. Evidence plane records decision and execution outcomes.
