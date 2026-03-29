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
| Onyx | `used_now` | `mandatory` | Governed runtime behind `/launch/onyx` and the Onyx-lite start script | It is the runtime target the control plane is built to govern | Not part of the default control-plane compose stack | Keep as active runtime dependency |
| Keycloak | `used_now` | `mandatory` | Live identity adapter, compose service, realm template, and governed-flow evaluator | Live mode now fails closed unless identity is resolved from Keycloak-backed bearer token or session state | Current implementation uses Keycloak userinfo/session resolution, not a full ingress JWT-validation path yet | Keep as active runtime dependency |
| OPA | `used_now` | `mandatory` | Rego policies, live OPA HTTP client, compose service, and governed-flow evaluator | Live mode now fails closed unless OPA returns a decision for the request | Envoy ext_authz is still future depth rather than the current mandatory path | Keep as active runtime dependency |
| Qdrant | `used_now` | `mandatory` | Live retrieval adapter, compose service, and governed-flow evaluator | Live mode now fails closed unless governed retrieval executes against the configured backend | The current live bridge is filter-backed scroll retrieval rather than a richer vector-search path | Keep as active runtime dependency |
| Vault | `used_now` | `mandatory` | Conditional live secret adapter, compose service, and governed-flow evaluator | Secret-requiring governed operations now fail closed unless Vault-backed secret access succeeds | Conditional dependency only; non-secret flows do not need Vault | Keep as active runtime dependency |
| Langfuse | `used_now` | `supporting` | Evidence plane and live activity feed | It gives the dashboard a real observability destination beyond local files | Not every governed-flow artifact is exported into Langfuse yet, and live mode does not fail closed on Langfuse reachability | Keep as active evidence-plane dependency |
| Envoy | `partially_used` | `supporting` | Compose service and local ingress config | It remains the intended ingress chokepoint for future route-level governance | Current `/launch/onyx` flow does not traverse Envoy | Keep as platform dependency, mark snapshot as reference |
| Grafana | `partially_used` | `supporting` | Compose service with provisioned dashboards | It provides an operator drill-down that complements the homepage | No alert loop or launch dependency is enforced from Grafana today | Keep as platform dependency, mark snapshot as reference |
| Superset | `optional_future` | `optional` | Compose service and analytics scaffolding | Could become useful for historical trust and evidence analytics | No current reviewer workflow depends on it | Mark optional |
| gVisor | `optional_future` | `optional` | Design-only sandbox boundary via repo-owned sandbox logic | Would strengthen isolation for risky execution | No gVisor-backed runtime path or evidence exists | Mark optional |
| Keycloak Quickstarts | `reference_only` | `reference` | Vendored example snapshot only | Helpful reference material for future identity work | No repo-owned runtime logic consumes it | Remove from active claims |
| OPA Envoy Plugin | `reference_only` | `reference` | Vendored plugin snapshot only | Helpful reference material for deeper Envoy authz work | Current stack does not use the plugin in a request path | Remove from active claims |
| Langfuse Python SDK | `reference_only` | `reference` | Vendored SDK snapshot only | Helpful reference material for future direct instrumentation | Repo-owned Langfuse adapters do not import it | Remove from active claims |

## What the repo proves today

- Clearly active and mandatory in the strict live governed path:
  - Onyx as the governed runtime target.
  - Keycloak for live identity establishment.
  - OPA for live policy decisions.
  - Qdrant for live retrieval execution.
  - Vault for secret-requiring governed operations.
- Clearly active and supporting:
  - Langfuse as a live evidence-plane destination and activity source.
- Clearly partial:
  - Envoy and Grafana.
  - Both matter to the platform story, but neither is currently a fail-closed request-path dependency.
- Clearly optional:
  - Superset and gVisor.
  - Both remain future depth until they produce reviewer-visible outcomes.
- Clearly reference-only:
  - Keycloak Quickstarts, OPA Envoy Plugin, and Langfuse Python SDK.
  - Vendored presence alone is not treated as architecture proof.

## Practical reading

- The runtime the repo now proves in `live` mode is dashboard-first governance plus governed handoff into Onyx through live identity, live OPA, live retrieval, conditional live secret access, trace correlation, and launch-gate approval.
- The evidence path the repo proves today is repo-owned artifacts first, with Langfuse-linked runtime visibility as a supporting observability surface rather than the only source of truth.
- Supporting services are kept only where they strengthen a real trust boundary, a real control family, or a credible next integration step.
- The repo should never imply that all vendored upstreams are equally integrated just because they exist under `upstream/`.
