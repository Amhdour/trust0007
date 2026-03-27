# Attack Surfaces

## Primary attack surfaces by boundary

1. **User/Client**
   - Prompt injection, payload smuggling, replay, abuse/flooding.
2. **IdP/Session**
   - Token theft/forgery, weak session invalidation, claim escalation.
3. **Ingress/Proxy**
   - Route bypass, header spoofing, TLS downgrade, WAF/auth gaps.
4. **Runtime**
   - Prompt-to-action escalation, data exfiltration, unsafe output generation.
5. **Governance Overlay**
   - Hook bypass, misordered controls, stale policy metadata.
6. **Policy Engine**
   - Bundle poisoning, default-allow behavior, decision API abuse.
7. **Secrets**
   - Over-broad access, secret sprawl, long-lived token leakage.
8. **Retrieval**
   - Cross-tenant recall, poisoning indexed data, inference leakage.
9. **Tool Execution**
   - Privileged tool misuse, SSRF/egress abuse, unsafe parameterization.
10. **Sandbox**
    - Escape attempts, side-channel probing, resource exhaustion.
11. **Observability**
    - Telemetry tampering, PII overcollection, trace gaps.
12. **Dashboard/Reporting**
    - Report manipulation, stale metrics decisions, unauthorized export.

## Cross-boundary attack chains

- **Identity-to-tool chain**: stolen token -> ingress access -> runtime action -> tool misuse.
- **Prompt-to-secrets chain**: injection -> governance bypass -> secret retrieval misuse.
- **Telemetry-blinding chain**: control bypass -> event suppression -> false confidence in dashboards.

## Minimum mitigations across all surfaces

- Fail-closed control points for authz/policy decisions.
- Strong identity/session validation at ingress and runtime handoff.
- Least privilege for secrets, retrieval, and tools.
- Tamper-evident telemetry with trace completeness checks.
- RBAC + auditability for policy, observability, and dashboard systems.
