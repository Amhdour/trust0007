# Component Responsibilities

## Keycloak
- Identity provider for user/service authentication.
- Session/token lifecycle and claims source-of-truth.

## Envoy
- Ingress proxy and edge policy enforcement point.
- Request routing into Onyx runtime.

## Onyx runtime
- Core AI orchestration/reasoning runtime.
- Coordinates tool use, retrieval, and runtime decision paths.

## myStarterKit governance overlay
- Local trust/security control layer over Onyx behavior.
- Enforces request/tool/action guardrails.
- Integrates launch-gate decisions and policy checks.

## OPA
- Centralized policy decision engine.
- Evaluates allow/deny/constraints for runtime actions.

## Vault
- Secrets manager for credentials/keys.
- Accessed only on demand when secret material is required.

## Qdrant
- Retrieval/vector data plane.
- Queried only for retrieval-needed request paths.

## gVisor (optional)
- Runtime sandbox for risky execution.
- Adds isolation boundary for high-risk tool/code actions.

## Langfuse
- Trace/evaluation/audit evidence collection.
- Serves as evidence source for post-request analytics.

## Grafana/Superset
- Visualization and reporting for operational and trust/security evidence.

## myStarterKit launch gate
- Consumes evidence signals to permit/restrict/block deployments or launch readiness.
