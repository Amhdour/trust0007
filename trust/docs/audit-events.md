# Audit Events Reference

## Event lifecycle (typical)
1. `request.start`
2. `identity.established`
3. `policy.decision`
4. `retrieval.decision`
5. `secret.access`
6. `tool.decision`
7. `tool.execution_attempt` (if applicable)
8. `launch_gate.evaluated`
9. `handoff.decision`
10. `confirmation.required` (conditional)
11. `deny.event` (conditional)
12. `fallback.event` (conditional)
13. `incident.signal` (conditional/high-severity)
14. `request.end`

## Event semantics
- `request.start`: ingress/runtime accepted a request context.
- `identity.established`: identity/session claims resolved.
- `policy.decision`: control-plane authorization result.
- `retrieval.decision`: retrieval security allow/deny/degrade outcome.
- `tool.decision`: governance allow/deny/confirm decision for tool action.
- `tool.execution_attempt`: tool execution invoked (or attempted).
- `confirmation.required`: user/operator confirmation required before action.
- `deny.event`: policy/governance blocked an action.
- `fallback.event`: controlled fallback path selected (e.g., RAG-only).
- `incident.signal`: anomaly/security condition requiring investigation.
- `request.end`: terminal request outcome emitted.

## Minimum required fields
All events must include:
- `trace_id`
- `request_id`
- `event_type`
- `timestamp`

Recommended:
- `tenant_id`
- `severity`
- structured `payload`

## Storage and transport
- Use JSONL as local canonical artifact format.
- Prefer `overlays/myStarterKit/artifacts/audit-records.jsonl` for reviewer-facing audit coverage when a governed flow has run.
- Keep PII/secret data out of payloads.
- Ensure forward compatibility for Langfuse and dashboard ingestion.
