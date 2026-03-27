# Request Flow & Governance Enforcement

## High-level flow
1. **Client request enters** via dashboard or API gateway.
2. **Identity context established** (token/session validation).
3. **Governance evaluation** through OnyxGatewayAdapter:
   - Policy checks for request authorization
   - Retrieval checks for data access boundaries
   - Tool checks for approved/denied actions
4. **Decision enforcement**:
   - If allowed: request proceeds with telemetry
   - If denied: request blocked with audit trail
5. **Service interactions** with data and model components.
6. **Telemetry emission** to events.jsonl + launch-gate artifacts.
7. **Response returns** with traceability metadata.

## Governance Enforcement Flow

### Allow Path Example
```
User clicks "Open Onyx" in dashboard
    ↓
/launch/onyx?path=/app → GovernedFlowEvaluator.run()
    ↓
Policy: ✓ Allow (policy.allow)
Retrieval: ✓ Allow (retrieval.allow)
Tools: ✓ Allow (onyx approved)
    ↓
Launch Gate: pass (9/9 controls)
    ↓
Handoff page with trace_id + audit trail
User navigates to Onyx
```

### Deny Path Example
```
User attempts forbidden action
    ↓
/launch/onyx?path=/app → GovernedFlowEvaluator.run()
    ↓
Policy: ✗ Deny (policy.deny_all_for_this_user)
Retrieval: ✗ Deny (cross-tenant access blocked)
Tools: ✗ Deny (admin_shell forbidden)
    ↓
Launch Gate: no_go (0/9 controls, blockers: policy.deny)
    ↓
403 Forbidden page with denial reasons
trace_id logged for audit
```

## Cross-cutting controls
- **Authentication and authorization** via Keycloak integration.
- **Policy decision logging** to events.jsonl with trace_id.
- **Error handling and security event emission** for all deny cases.
- **Startup and readiness checks** in launch-gate with evidence requirements.

## Live Enforcement Examples

### Events from Allow Flow
```json
{"event_type":"request.start","trace_id":"flow-abcd1234","request_id":"req-efgh5678","payload":{"path":"/governed-flow"}}
{"event_type":"identity.established","trace_id":"flow-abcd1234","request_id":"req-efgh5678","payload":{"sub":"user-1","tenant_id":"tenant-a"}}
{"event_type":"policy.decision","trace_id":"flow-abcd1234","request_id":"req-efgh5678","payload":{"allow":true,"reasons":["policy.allow"]}}
{"event_type":"retrieval.decision","trace_id":"flow-abcd1234","request_id":"req-efgh5678","payload":{"decision":"allow","source":"qdrant"}}
{"event_type":"tool.decision","trace_id":"flow-abcd1234","request_id":"req-efgh5678","payload":{"allowed":["search"],"denied":[]}}
{"event_type":"request.end","trace_id":"flow-abcd1234","request_id":"req-efgh5678","payload":{"status":"ok","decision":true}}
```

### Launch Gate Evidence
```json
{
  "machine": {
    "decision": "pass",
    "score": 9,
    "max_score": 9,
    "blockers": [],
    "missing_evidence": [],
    "controls_passed": ["policy_coverage", "retrieval_safety", "tool_governance"],
    "controls_failed": []
  },
  "human": "Launch Gate Decision: pass\\nScore: 9/9\\n...",
  "flow_metadata": {
    "trace_id": "flow-abcd1234",
    "request_id": "req-efgh5678"
  }
}
```

### Events from Deny Flow
```json
{"event_type":"request.start","trace_id":"flow-deny1234","request_id":"req-deny5678","payload":{"path":"/launch/onyx"}}
{"event_type":"identity.established","trace_id":"flow-deny1234","request_id":"req-deny5678","payload":{"sub":"blocked-user","tenant_id":"tenant-a"}}
{"event_type":"policy.decision","trace_id":"flow-deny1234","request_id":"req-deny5678","payload":{"allow":false,"reasons":["policy.deny_all_for_this_user"]}}
{"event_type":"retrieval.decision","trace_id":"flow-deny1234","request_id":"req-deny5678","payload":{"decision":"deny","source":"qdrant"}}
{"event_type":"tool.decision","trace_id":"flow-deny1234","request_id":"req-deny5678","payload":{"allowed":[],"denied":["onyx"]}}
{"event_type":"deny.event","trace_id":"flow-deny1234","request_id":"req-deny5678","payload":{"blocked":true}}
{"event_type":"request.end","trace_id":"flow-deny1234","request_id":"req-deny5678","payload":{"status":"denied","decision":false}}
```

## API Endpoints

### `/api/control-plane/governed-flow`
Triggers complete governance evaluation and artifact generation.

**Response:**
```json
{
  "decision": true,
  "trace_id": "flow-abcd1234",
  "request_id": "req-efgh5678",
  "launch_gate": {
    "decision": "pass",
    "score": 9,
    "max_score": 9,
    "blockers": [],
    "missing_evidence": []
  },
  "artifacts": {
    "events_jsonl": "overlays/myStarterKit/artifacts/events.jsonl",
    "launch_gate_result": "overlays/myStarterKit/artifacts/launch-gate-result.json"
  }
}
```

### `/launch/onyx?path=/app`
Governed handoff to Onyx runtime. Blocks if governance denies.

**Allow Response:** HTML page with handoff link + audit trail
**Deny Response:** 403 Forbidden with denial reasons

## Deferred details
- Exact service sequence diagrams.
- Failure modes and fallback routing.
- Performance/SLO targets and scaling profile.
