# Request Sequence Spec

This sequence is the intended full-stack design. In the current repo, some stages are partial or optional rather than mandatory path elements. See `docs/upstream-usage-matrix.md`.

## Per-request sequence

1. **Identity/session established**
   - Keycloak validates/establishes identity context for caller/session when live IAM wiring is enabled.
2. **Envoy ingress**
   - Envoy receives request, applies ingress controls, and forwards to Onyx runtime when the ingress bridge is enabled.
3. **Onyx request intake**
   - Onyx receives prompt/request + identity/session context.
4. **myStarterKit governance controls**
   - Overlay applies trust/security checks on input, intent, and planned actions.
5. **Policy decision (myStarterKit and/or OPA)**
   - Action/tool/data access policy decision is evaluated.
6. **Conditional Vault access**
   - Only if required for requested operation/tool and the secret backend is wired.
7. **Conditional Qdrant retrieval**
   - Only if retrieval/RAG context is needed and live retrieval is enabled.
8. **Onyx runtime continuation**
   - Reasoning/tool orchestration continues under active controls.
9. **myStarterKit action guardrails**
   - Tool and integration actions are verified/enforced before execution.
10. **Conditional gVisor sandboxing**
   - Risky execution paths run in sandbox when that isolation path is implemented.
11. **Continuous telemetry/evidence emission**
   - Trace, eval, policy, and control-point events emitted throughout.
12. **Response completion**
   - Final output returned through ingress path.

## Post-request sequence

1. Langfuse collects traces/evaluations.
2. Grafana and optional Superset present operational and trust views.
3. myStarterKit launch gate consumes evidence for future launch/readiness decisions.
