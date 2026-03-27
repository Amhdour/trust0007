# Request Sequence Spec

## Per-request sequence

1. **Identity/session established**
   - Keycloak validates/establishes identity context for caller/session.
2. **Envoy ingress**
   - Envoy receives request, applies ingress controls, forwards to Onyx runtime.
3. **Onyx request intake**
   - Onyx receives prompt/request + identity/session context.
4. **myStarterKit governance controls**
   - Overlay applies trust/security checks on input, intent, and planned actions.
5. **Policy decision (myStarterKit and/or OPA)**
   - Action/tool/data access policy decision is evaluated.
6. **Conditional Vault access**
   - Only if required for requested operation/tool.
7. **Conditional Qdrant retrieval**
   - Only if retrieval/RAG context is needed.
8. **Onyx runtime continuation**
   - Reasoning/tool orchestration continues under active controls.
9. **myStarterKit action guardrails**
   - Tool and integration actions are verified/enforced before execution.
10. **Conditional gVisor sandboxing**
   - Risky execution paths run in sandbox when required.
11. **Continuous telemetry/evidence emission**
   - Trace, eval, policy, and control-point events emitted throughout.
12. **Response completion**
   - Final output returned through ingress path.

## Post-request sequence

1. Langfuse collects traces/evaluations.
2. Grafana/Superset present operational and trust views.
3. myStarterKit launch gate consumes evidence for future launch/readiness decisions.
