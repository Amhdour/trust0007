# Upstream Usage Matrix

This matrix answers a narrow question: which vendored upstream components are actually shaping the current control-plane runtime, and which ones are only present as platform scaffolding, optional work, or reference snapshots.

The machine-readable source of truth lives in `evidence/upstream_usage.inventory.json`. The dashboard surfaces the same data in the Upstream Integration Posture section and through `/api/control-plane/upstream-usage`.

## Classification summary

| Classification | Meaning |
| --- | --- |
| `used_now` | Actively contributes to the current governed runtime or evidence path. |
| `partially_used` | Present through containers, configs, adapters, tests, or policy bridges, but not yet a proven mandatory path element. |
| `optional_future` | Kept in scope for future depth only; current reviewer outcomes do not depend on it. |
| `reference_only` | Vendored source snapshot retained for compatibility or implementation reference, not for active architecture claims. |

## Current posture

| Component | Classification | Current runtime role | Governance signal | Evidence artifact | Recommended action |
| --- | --- | --- | --- | --- | --- |
| Onyx | `used_now` | Primary governed runtime reached through `/launch/onyx` | Governed handoff allow and deny outcomes | `evidence/reviewer/inspectable-live-runtime/*.json` | Keep as active runtime dependency |
| Langfuse | `used_now` | Live evidence-plane trace destination | Trace and session activity in dashboard live log | `compose/grafana/dashboards/mystarterkit-operational.json` | Keep as active runtime dependency |
| Keycloak | `partially_used` | Identity provider scaffold with realm templates and compose service | Policy models roles and tenants, but not from live Keycloak sessions yet | `adapters/identity/realm-dev-template.json` | Keep as platform dependency, mark snapshot as reference |
| Envoy | `partially_used` | Ingress and `ext_authz` bridge stub | No dedicated dashboard signal yet | `compose/envoy/envoy.local.yaml` | Keep as platform dependency, mark snapshot as reference |
| OPA | `partially_used` | Policy-language anchor and optional sidecar | Policy source and coverage are visible, but live handoff decisions are local | `policies/rego/policy.rego` | Keep as platform dependency, mark snapshot as reference |
| Vault | `partially_used` | Conditional secret backend adapter and container | No dashboard-visible secret access event yet | `docs/vault-integration.md` | Keep as platform dependency, mark snapshot as reference |
| Qdrant | `partially_used` | Intended governed retrieval backend | Retrieval decisions reference source `qdrant` | `overlays/myStarterKit/artifacts/events.jsonl` | Keep as platform dependency, mark snapshot as reference |
| Grafana | `partially_used` | Operational drill-down destination | Operational dashboard spec is linked as evidence | `telemetry/dashboards/grafana/operational-dashboard-spec.json` | Keep as platform dependency, mark snapshot as reference |
| Superset | `optional_future` | Future analytics destination | No dedicated dashboard signal yet | `telemetry/dashboards/superset/evidence-views.yaml` | Mark optional |
| gVisor | `optional_future` | Future isolated execution boundary | Sandbox policy exists, no live gVisor signal | `docs/sandboxing.md` | Mark optional |
| Keycloak Quickstarts | `reference_only` | Example source for future Keycloak work | None | vendored snapshot only | Remove from active claims |
| OPA Envoy Plugin | `reference_only` | Reference source for deeper Envoy authz | None | vendored snapshot only | Remove from active claims |
| Langfuse Python SDK | `reference_only` | Reference SDK for future instrumentation | None | vendored snapshot only | Remove from active claims |

## Practical reading

- The runtime the repo proves today is: dashboard-first governance plus governed handoff into Onyx.
- The evidence path the repo proves today is: repo-owned artifacts plus Langfuse-linked runtime visibility when traces are available.
- Keycloak, Envoy, OPA, Vault, Qdrant, and Grafana remain in scope because they strengthen real trust boundaries, but several of them are not yet mandatory in the current request path.
- Superset and gVisor should stay clearly optional until they produce reviewer-visible outcomes.
- Reference snapshots under `upstream/` should not be described as active architecture just because they are vendored.
