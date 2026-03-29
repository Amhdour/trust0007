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
- Status: `used_now`
- Role: live identity and session authority for strict governed handoffs.
- Current gap: current live mode resolves Keycloak-backed identity via HTTP session or bearer-token introspection patterns, but Envoy-side JWT enforcement is still future depth.

## Envoy
- Status: `partially_used`
- Role: intended ingress chokepoint and authz bridge.
- Current gap: the current governed `/launch/onyx` path does not depend on Envoy.

## myStarterKit governance overlay
- Status: repo-owned, active
- Role: local trust and security control layer over runtime behavior.
- Why it stays central: it is where this repo adds differentiated governance value rather than relying on upstream presence alone.

## OPA
- Status: `used_now`
- Role: mandatory live policy decision engine for strict governed handoffs.
- Current gap: OPA is now on the request path, but Envoy ext_authz integration is still future depth.

## Vault
- Status: `used_now`
- Role: conditional live secret backend for governed operations that require protected runtime secrets.
- Current gap: Vault is mandatory only for secret-requiring paths, not every governed request.

## Qdrant
- Status: `used_now`
- Role: mandatory live retrieval backend for strict governed handoffs.
- Current gap: the current bridge is a real backend path, but still a narrower filter-backed retrieval flow than a full vector-search integration.

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
