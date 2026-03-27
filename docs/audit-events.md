# Audit Events Reference

## Event lifecycle (typical)
1. `request.start`
2. `identity.established`
3. `policy.decision`
4. `retrieval.decision`
5. `tool.decision`
6. `tool.execution_attempt` (if applicable)
7. `confirmation.required` (conditional)
8. `deny.event` (conditional)
9. `fallback.event` (conditional)
10. `incident.signal` (conditional/high-severity)
11. `request.end`

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
- Keep PII/secret data out of payloads.
- Ensure forward compatibility for Langfuse and dashboard ingestion.
