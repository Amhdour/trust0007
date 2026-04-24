# Trust Boundary Model

This model defines trust boundaries for the umbrella AI Trust & Security stack and the minimum controls required at each boundary.

## Boundary 1: User/Client Boundary
- **Assets**: user identity claims, session identifiers, prompts/inputs, response payloads.
- **Inbound data**: raw client requests, auth headers/tokens, metadata (IP, user-agent).
- **Outbound data**: HTTP responses, error codes/messages, correlation IDs.
- **Assumptions**: client network is untrusted; user input may be malicious.
- **Failure modes**: spoofed client identity, injection payloads, replayed requests, abusive traffic.
- **Minimum controls**: TLS, request size/rate limits, input validation, replay defenses, correlation IDs.

## Boundary 2: IdP/Session Boundary (Keycloak)
- **Assets**: tokens, session state, realm/client configs, role/group claims.
- **Inbound data**: credentials/assertions, token introspection requests, session lifecycle events.
- **Outbound data**: signed tokens, introspection results, user/role claims.
- **Assumptions**: signing keys are protected; token TTL is enforced.
- **Failure modes**: token forgery, stale/revoked token acceptance, privilege escalation via claims drift.
- **Minimum controls**: strong signing keys, short token lifetimes, revocation checks, audience/issuer validation.

## Boundary 3: Ingress/Proxy Boundary (Envoy)
- **Assets**: routing policy, mTLS/TLS config, authz/authn integration config.
- **Inbound data**: authenticated/unauthenticated HTTP traffic, identity metadata.
- **Outbound data**: normalized routed requests, access logs, rejected responses.
- **Assumptions**: Envoy is the mandatory ingress chokepoint.
- **Failure modes**: bypass routes, header spoofing, authz misconfiguration, insecure upstream hops.
- **Minimum controls**: default-deny routes, header sanitization, upstream TLS/mTLS, centralized access logs.

## Boundary 4: Runtime Boundary (Onyx Runtime)
- **Assets**: prompts, runtime context, model/tool orchestration state, outputs.
- **Inbound data**: routed requests + identity/session context.
- **Outbound data**: model/tool calls, responses, runtime events.
- **Assumptions**: runtime executes only after ingress + governance checks.
- **Failure modes**: prompt injection success, unsafe action planning, data leakage in outputs.
- **Minimum controls**: request policy hooks, context sanitization, output filtering/redaction, action allowlists.

## Boundary 5: Governance Overlay Boundary (myStarterKit)
- **Assets**: guardrail configs, governance policy packs, launch-gate decisions.
- **Inbound data**: runtime intent, action plans, policy context, evidence signals.
- **Outbound data**: allow/deny/constraint decisions, enforcement events.
- **Assumptions**: governance checks run before high-risk actions.
- **Failure modes**: bypassed hooks, misconfigured guardrails, stale governance rules.
- **Minimum controls**: mandatory pre-action hooks, versioned policy config, fail-closed behavior.

## Boundary 6: Policy Engine Boundary (OPA)
- **Assets**: rego policies, decision logs, policy bundles.
- **Inbound data**: policy queries with identity/action/resource context.
- **Outbound data**: decision payload (allow/deny/constraints), decision telemetry.
- **Assumptions**: policies are authoritative for enforced decisions.
- **Failure modes**: policy drift, bundle load failure, permissive defaults.
- **Minimum controls**: signed/versioned bundles, decision logging, default-deny fallback, policy unit tests.

## Boundary 7: Secrets Boundary (Vault)
- **Assets**: secrets, encryption keys, lease/token metadata.
- **Inbound data**: authenticated secret read/write/renew requests.
- **Outbound data**: leased secret material, audit events, lease status.
- **Assumptions**: secrets are fetched only on explicit need.
- **Failure modes**: over-broad secret access, long-lived credentials, secret exfiltration.
- **Minimum controls**: least privilege policies, dynamic/short-lived secrets, audit logging, secret redaction.

## Boundary 8: Retrieval Boundary (Qdrant)
- **Assets**: vector collections, embeddings, retrieval metadata.
- **Inbound data**: retrieval queries, filters, tenant/index context.
- **Outbound data**: retrieved vectors/documents/scores.
- **Assumptions**: retrieval is tenant-scoped and policy-constrained.
- **Failure modes**: cross-tenant data exposure, unbounded recall, inference leakage.
- **Minimum controls**: tenant scoping, query constraints, collection ACLs, retrieval audit events.

## Boundary 9: Tool Execution Boundary
- **Assets**: tool credentials, integration endpoints, action plans/results.
- **Inbound data**: tool invocation requests and parameters.
- **Outbound data**: tool results, side effects, integration logs.
- **Assumptions**: all tool invocations are policy-gated.
- **Failure modes**: unauthorized side effects, SSRF-like abuse, unsafe argument injection.
- **Minimum controls**: tool allowlists, per-tool auth scopes, parameter validation, egress controls.

## Boundary 10: Sandbox Boundary (gVisor, optional)
- **Assets**: isolated execution environment, sandbox policy profile.
- **Inbound data**: risky code/tool execution payloads.
- **Outbound data**: constrained execution results + sandbox telemetry.
- **Assumptions**: sandbox is used for risk-elevated execution paths.
- **Failure modes**: sandbox bypass, privilege escalation, noisy-neighbor/resource exhaustion.
- **Minimum controls**: isolation defaults, syscall restrictions, resource quotas, sandbox event logging.

## Boundary 11: Observability Boundary (Langfuse)
- **Assets**: traces, evaluations, policy events, runtime metadata.
- **Inbound data**: telemetry events from runtime/control components.
- **Outbound data**: trace/eval datasets, evidence feeds, APIs.
- **Assumptions**: telemetry integrity is required for trust decisions.
- **Failure modes**: missing traces, tampered telemetry, PII leakage in logs.
- **Minimum controls**: schema validation, immutable event IDs, retention/PII policies, ingest health alerts.

## Boundary 12: Dashboard/Reporting Boundary (Grafana/Superset)
- **Assets**: dashboards, alerts, trust/security reports.
- **Inbound data**: observability datasets and metrics.
- **Outbound data**: visualizations, alerts, exported reports, launch-gate inputs.
- **Assumptions**: dashboards are decision-support, not policy-authoritative.
- **Failure modes**: stale data, misinterpreted metrics, unauthorized dashboard access.
- **Minimum controls**: RBAC, data freshness SLOs, audit trails for dashboard changes, alert tuning.
