# Upstream Usage Matrix

This document is the repo-wide upstream integration audit for the current checkout. It answers one question strictly: which vendored upstream components materially strengthen the current dashboard-first control plane, and which ones are only platform scaffolding, optional future depth, or reference snapshots.

The machine-readable source of truth lives in `evidence/upstream_usage.inventory.json`. The control-plane API surfaces the same data at `/api/control-plane/upstream-usage`, and the homepage renders it in the Upstream Integration Posture section.

## Audit method

Each upstream component is classified against five reviewer questions:

1. What does it do?
2. Where does it sit in the runtime?
3. Why is it necessary?
4. What governance signal and evidence artifact does it produce today?
5. What control gap appears if it is removed?

If a component cannot answer those questions with repo-backed wiring or evidence, it should be downgraded to `optional_future` or `reference_only`.

## Classification summary

| Classification | Meaning |
| --- | --- |
| `used_now` | Actively contributes to the current governed runtime or evidence path. |
| `partially_used` | Present through containers, configs, adapters, tests, or policy bridges, but not yet a proven mandatory path element. |
| `optional_future` | Kept in scope for future depth only; current reviewer outcomes do not depend on it. |
| `reference_only` | Vendored source snapshot retained for compatibility or implementation reference, not for active architecture claims. |

## Current posture

| Component | Classification | Path status | Where it sits now | Why it stays in scope | Current gap | Recommended action |
| --- | --- | --- | --- | --- | --- | --- |
| Onyx | `used_now` | `mandatory` | Governed runtime behind `/launch/onyx` and the Onyx-lite start script | Only upstream runtime the repo proves through handoff flows, tests, and reviewer evidence | Not part of the default control-plane compose stack | Keep as active runtime dependency |
| Langfuse | `used_now` | `mandatory` | Evidence plane and live activity feed | Gives the dashboard a real runtime observability source | Not every governed-flow artifact is exported into Langfuse yet | Keep as active runtime dependency |
| Keycloak | `partially_used` | `supporting` | Compose service, realm template, and helper scripts | Intended identity and session authority for tenant-aware access | Live JWT validation and session handoff are not in the current request path | Keep as platform dependency, mark snapshot as reference |
| Envoy | `partially_used` | `supporting` | Compose service and local ingress config | Intended ingress chokepoint and future authz bridge | Current `/launch/onyx` flow does not traverse Envoy | Keep as platform dependency, mark snapshot as reference |
| OPA | `partially_used` | `supporting` | Rego policies, tests, optional container, and Envoy example policy | Keeps policy portable and reviewable | Live launch decisions are still local Python decisions | Keep as platform dependency, mark snapshot as reference |
| Vault | `partially_used` | `supporting` | Compose service plus secrets adapter | Keeps a real secret boundary in scope for governed connectors | No live secret fetch or dashboard-visible Vault telemetry yet | Keep as platform dependency, mark snapshot as reference |
| Qdrant | `partially_used` | `supporting` | Compose service and retrieval policy semantics | Retrieval governance is central to the control-plane story | Governed retrieval still uses seeded demo data instead of a live Qdrant client | Keep as platform dependency, mark snapshot as reference |
| Grafana | `partially_used` | `supporting` | Compose service with provisioned dashboards | Useful operational drill-down that complements the homepage | No alert loop or launch dependency is enforced from Grafana today | Keep as platform dependency, mark snapshot as reference |
| Superset | `optional_future` | `optional` | Compose service and analytics scaffolding | Could become useful for historical trust and evidence analytics | No current reviewer workflow depends on it | Mark optional |
| gVisor | `optional_future` | `optional` | Design-only sandbox boundary via repo-owned sandbox logic | Would strengthen isolation for risky execution | No gVisor-backed runtime path or evidence exists | Mark optional |
| Keycloak Quickstarts | `reference_only` | `reference` | Vendored example snapshot only | Helpful reference material for future identity work | No repo-owned runtime logic consumes it | Remove from active claims |
| OPA Envoy Plugin | `reference_only` | `reference` | Vendored plugin snapshot only | Helpful reference material for deeper Envoy authz work | Current stack does not use the plugin in a request path | Remove from active claims |
| Langfuse Python SDK | `reference_only` | `reference` | Vendored SDK snapshot only | Helpful reference material for future direct instrumentation | Repo-owned Langfuse adapters do not import it | Remove from active claims |

## What the repo proves today

- Clearly active:
  - Onyx as the governed runtime target.
  - Langfuse as the live evidence-plane activity source.
- Clearly partial:
  - Keycloak, Envoy, OPA, Vault, Qdrant, and Grafana.
  - These are in scope because they improve trust boundaries, policy portability, secrets posture, retrieval governance, or observability, but they are not all mandatory request-path dependencies yet.
- Clearly optional:
  - Superset and gVisor.
  - Both remain future depth until they produce reviewer-visible outcomes.
- Clearly reference-only:
  - Keycloak Quickstarts, OPA Envoy Plugin, and Langfuse Python SDK.
  - Vendored presence alone is not treated as architecture proof.

## Practical reading

- The runtime the repo proves today is dashboard-first governance plus governed handoff into Onyx.
- The evidence path the repo proves today is repo-owned artifacts plus Langfuse-linked runtime visibility when traces are available.
- Supporting services are kept only where they strengthen a real trust boundary, a real control family, or a credible next integration step.
- The repo should never imply that all vendored upstreams are equally integrated just because they exist under `upstream/`.
