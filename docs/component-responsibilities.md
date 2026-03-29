# Component Responsibilities

This document describes the intended responsibility of each major component plus its current activation status in this repo.

## Onyx runtime
- Status: `used_now`
- Role: governed runtime target behind dashboard-controlled handoffs.
- Why it stays active: it is the only upstream runtime the repo actively proves through tests, handoff flows, and reviewer evidence.

## Langfuse
- Status: `used_now`
- Role: evidence-plane trace destination and live runtime activity source.
- Why it stays active: it adds runtime trace visibility that the dashboard can consume directly.

## Keycloak
- Status: `partially_used`
- Role: intended identity and session authority.
- Current gap: live JWT or session enforcement is not yet wired into the dashboard request path.

## Envoy
- Status: `partially_used`
- Role: intended ingress chokepoint and authz bridge.
- Current gap: the current governed `/launch/onyx` path does not depend on Envoy.

## myStarterKit governance overlay
- Status: repo-owned, active
- Role: local trust and security control layer over runtime behavior.
- Why it stays central: it is where this repo adds differentiated governance value rather than relying on upstream presence alone.

## OPA
- Status: `partially_used`
- Role: policy-language anchor and optional sidecar decision engine.
- Current gap: live handoff decisions are still made in the repo-owned control-plane server.

## Vault
- Status: `partially_used`
- Role: conditional secret backend.
- Current gap: no dashboard-visible secret-access telemetry or reviewer evidence depends on it yet.

## Qdrant
- Status: `partially_used`
- Role: intended governed retrieval backend.
- Current gap: current retrieval flows still use seeded demo data rather than a proven live Qdrant bridge.

## Grafana
- Status: `partially_used`
- Role: operational drill-down destination.
- Current gap: it complements the homepage, but the homepage remains the primary reviewer surface.

## Superset
- Status: `optional_future`
- Role: future evidence analytics destination.
- Current gap: no current dashboard signal or reviewer artifact depends on it.

## gVisor (optional)
- Status: `optional_future`
- Role: future isolation boundary for risky execution.
- Current gap: sandbox decision logic exists, but no live gVisor-backed execution path is implemented.

## myStarterKit launch gate
- Consumes evidence signals to permit/restrict/block deployments or launch readiness.

For the full per-component inventory, see `docs/upstream-usage-matrix.md`.
