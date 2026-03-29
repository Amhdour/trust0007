# AI Trust & Security Stack Architecture Spec

## 1) Current activation model

The repo should be read in tiers instead of as one flat chain:

- **Active now**
  - Dashboard homepage and repo-owned control-plane services
  - Governed handoff into Onyx
  - Langfuse-backed runtime visibility when traces are available
- **Platform dependencies with partial wiring**
  - Keycloak
  - Envoy
  - OPA
  - Vault
  - Qdrant
  - Grafana
- **Optional / future depth**
  - Superset
  - gVisor
- **Reference-only vendored snapshots**
  - Keycloak Quickstarts
  - OPA Envoy Plugin
  - Langfuse Python SDK

See `docs/upstream-usage-matrix.md` and `evidence/upstream_usage.inventory.json` for the strict classification used by the dashboard.

## 2) Architecture intent

- Make the dashboard the visible product and operational control tower.
- Provide a secure runtime path for AI requests through identity, policy, and governance controls.
- Separate **control-plane decisions** from **runtime-plane execution**.
- Emit evidence continuously for post-request assurance and launch-gate decisions.

## 3) Runtime path the repo proves today

- User lands on the repo-owned dashboard first.
- The control plane evaluates governance locally from the runtime policy bundle.
- Approved requests hand off to Onyx through `/launch/onyx`.
- Evidence is captured in repo-owned artifacts and augmented with Langfuse activity when available.

Keycloak, Envoy, OPA, Vault, Qdrant, Grafana, Superset, and gVisor remain important to the platform story, but they should only be described as active runtime dependencies where the repo proves that depth.

## 4) Trust boundaries

1. **Dashboard boundary** (client/user -> control-plane homepage)
   - Boundary crossing: operators land on the custom dashboard first.
   - Primary controls: posture aggregation, role-based entry points, drill-down routing into underlying modules.

2. **Identity boundary** (dashboard -> Keycloak)
   - Boundary crossing: dashboard requests session and tenant context when live identity wiring is enabled.
   - Primary controls: authentication, token issuance, tenant-aware claims.

3. **Ingress/runtime boundary** (Envoy -> Onyx runtime)
   - Boundary crossing: authenticated requests enter application reasoning/runtime when Envoy is in-path.
   - Primary controls: ingress enforcement, JWT validation, and route policy once that bridge is fully activated.

4. **Policy boundary** (Onyx/myStarterKit <-> OPA)
   - Boundary crossing: policy queries and decisions.
   - Primary controls: explicit allow/deny decisions, policy context validation, and policy-language portability.

5. **Secret boundary** (Onyx/tooling <-> Vault)
   - Boundary crossing: access to protected credentials or keys.
   - Primary controls: least-privilege secret retrieval, short-lived access, auditable access paths.

6. **Data boundary** (Onyx/tooling <-> Qdrant)
   - Boundary crossing: retrieval of embeddings/documents for RAG workflows.
   - Primary controls: retrieval authorization, scoped indexes/collections, query/result observability.

7. **Sandbox boundary** (Onyx/tooling <-> gVisor, optional)
   - Boundary crossing: risky code/tool execution into isolated runtime.
   - Primary controls: syscall/process isolation and constrained execution profile.

8. **Evidence boundary** (all services -> Langfuse -> Grafana/Superset -> launch gate)
   - Boundary crossing: operational/security/evaluation telemetry into evidence systems and reviewer artifacts.
   - Primary controls: trace completeness, immutable-ish audit trails, KPI/alert visibility.

## 5) Core control points

- **CP1 Dashboard control tower**: custom homepage summarizes posture, alerts, traces, and readiness.
- **CP2 Identity/session establishment**: Keycloak is the intended identity authority, but live dashboard enforcement is still partly stubbed.
- **CP3 Ingress enforcement**: Envoy is the intended ingress chokepoint, but current governed handoffs do not require it.
- **CP4 Runtime governance**: myStarterKit enforces trust/security controls before/through reasoning.
- **CP5 Policy decision**: current decisions are local to the repo-owned control plane; OPA remains the policy-language and sidecar bridge.
- **CP6 Secret retrieval gate**: Vault is available as a conditional secret backend when wiring is completed.
- **CP7 Retrieval gate**: Qdrant is the intended governed retrieval backend, but current demo retrieval is still seeded.
- **CP8 Risky execution sandboxing**: gVisor remains future isolation depth, not a proven current path.
- **CP9 Continuous evidence emission**: Langfuse telemetry throughout request lifecycle.
- **CP10 Post-request assurance**: Grafana/Superset views consumed by launch-gate and evidence workflows.

## 6) Data flow summary

- User lands on the dashboard first.
- Identity and ingress integrations may be layered in, but the current repo-owned handoff path is centered on the dashboard server.
- Onyx runtime receives request and context.
- Onyx/myStarterKit conditionally accesses:
  - Vault (secrets), only when that integration is enabled.
  - Qdrant (retrieval), only when that integration is enabled.
  - gVisor (sandbox), only in a future isolated execution path.
- Response and runtime metadata return through ingress path and are summarized back into the dashboard.
- Telemetry, policy decisions, and evaluations are emitted to Langfuse continuously.

## 7) Policy flow summary

- Policy context assembled from request, identity/session claims, action intent, and runtime state.
- myStarterKit applies local governance policies first (where configured).
- OPA currently provides policy-language portability and optional sidecar depth more than mandatory live decisioning.
- Final decision governs whether Onyx can continue, call tools, read secrets, retrieve data, or execute in sandbox.
- Policy decision outcomes are logged as evidence signals.

## 8) Evidence flow summary

- During request: traces, policy decisions, retrieval/tool events, and security-relevant state emitted to Langfuse.
- Post request: Langfuse outputs feed operational and evidence drill-down views in Grafana/Superset.
- Launch-gate consumes these evidence views/signals and the dashboard summarizes readiness back into one homepage.
