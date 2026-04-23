# AI Trust & Security Stack Architecture Spec

## 1) Current activation model

The repo should be read in tiers instead of as one flat chain:

- **Active now**
  - Dashboard homepage and repo-owned control-plane services
  - Governed handoff into Onyx (RAG) and Onyx Agentic (MCP/Tools) as runtime lanes behind the dashboard
  - Langfuse-backed runtime visibility when traces are available
  - Strict live governed path through Keycloak, OPA, Qdrant, and conditional Vault access
- **Platform dependencies with partial wiring**
  - Envoy
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
- Provide a secure runtime path for AI requests through identity, policy, governance, audit, and evidence controls.
- Separate **control-plane decisions** from **runtime-plane execution**.
- Emit evidence continuously for post-request assurance and launch-gate decisions.

## 3) Runtime path the repo proves today

- User lands on the repo-owned dashboard first.
- In demo mode, the control plane can still run with repo-local fallback governance.
- In live mode, governed handoff to `/launch/{runtime}` requires:
  - Keycloak-backed identity
  - live OPA policy evaluation
  - runtime-specific controls (Onyx retrieval/data-boundary checks, Onyx Agent tool/MCP controls)
  - conditional Vault-backed secret access
  - trace-correlated evidence and launch-gate approval
- Evidence is captured in repo-owned artifacts first, including explicit audit records, and augmented with Langfuse activity when available.

Envoy, Grafana, Superset, and gVisor remain important to the broader platform story, but they should only be described as active runtime dependencies where the repo proves that depth.

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
- **CP2 Identity/session establishment**: Keycloak-backed bearer token or session resolution is mandatory in live governed mode.
- **CP3 Ingress enforcement**: Envoy is the intended ingress chokepoint, but current governed handoffs do not require it.
- **CP4 Runtime governance**: myStarterKit enforces trust/security controls before/through reasoning.
- **CP5 Policy decision**: OPA is the mandatory decision engine in live governed mode.
- **CP6 Secret retrieval gate**: Vault-backed secret access is a conditional mandatory dependency for secret-requiring governed operations.
- **CP7 Retrieval gate**: Qdrant-backed retrieval is a mandatory live dependency for the strict governed handoff path.
- **CP8 Risky execution sandboxing**: gVisor remains future isolation depth, not a proven current path.
- **CP9 Continuous evidence emission**: repo-owned artifacts and explicit audit records throughout the request lifecycle, with optional Langfuse export/supporting visibility.
- **CP10 Post-request assurance**: Grafana/Superset views consumed by launch-gate and evidence workflows.

## 6) Data flow summary

- User lands on the dashboard first.
- In live mode, the dashboard server resolves live identity from Keycloak-compatible session or bearer token state.
- The control plane sends a live policy input to OPA and fails closed if OPA is unreachable or denies.
- The governed flow executes retrieval against Qdrant and fails closed if retrieval evidence is missing or invalid.
- Secret-requiring operations call Vault-backed secret access and fail closed on missing secret evidence.
- Launch-gate evaluates the live evidence set before the handoff is approved.
- Response and runtime metadata return through the dashboard-owned control plane.
- Telemetry, policy decisions, and evaluations are emitted to file-backed artifacts and can be exported onward to Langfuse.

## 7) Policy flow summary

- Policy context assembled from request, identity/session claims, action intent, tool metadata, and runtime state.
- In live mode, OPA is the mandatory policy decision point for the governed path.
- Final decision governs whether Onyx can continue, call tools, read secrets, retrieve data, or execute in sandbox.
- Policy decision outcomes are logged as evidence signals with trace and session correlation.

## 8) Evidence flow summary

- During request: identity, policy, retrieval, secret, tool, audit, handoff, and launch-gate events are emitted to repo-owned artifacts under `overlays/myStarterKit/artifacts/`.
- Post request: those artifacts are summarized into dashboard sections and can be exported onward to Langfuse/Grafana drill-downs.
- In live mode, launch-gate consumes the live governed-flow evidence set and does not silently substitute demo artifacts.
