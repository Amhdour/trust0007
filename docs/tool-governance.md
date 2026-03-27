# Tool & Integration Governance Controls

## Scope
Local-development, policy-driven governance layer for tool/integration actions.

## Components
- `adapters/tools/policy_model.py`: policy evaluator + static policy configuration.
- `adapters/tools/engine.py`: governance orchestration engine.
- `adapters/tools/interfaces.py`: policy/executor/audit interfaces.
- `adapters/tools/schemas.py`: typed schemas for requests, decisions, and audit events.

## Supported controls
- Tool allowlist.
- Confirmation-required tools.
- Forbidden tools.
- Forbidden arguments/fields.
- Rate-limit placeholders (`rate_limit_hint`, `rate_limit_key`).
- High-risk action classification (`risk_level`).
- Audit events for allow, deny, confirm, execute.

## Policy-driven model
The engine does not hardcode governance decisions.

- `ToolPolicyEvaluator` decides `allow` / `deny` / `confirm_required`.
- `ToolExecutor` performs business logic only after policy allows execution.
- `ToolAuditSink` records governance lifecycle events.

This keeps business logic separate from policy logic.

## Decision flow
1. Receive `ToolActionRequest`.
2. Evaluate policy.
3. Emit audit event for deny/confirm/allow.
4. If allowed, execute tool and emit execute audit event.
5. Return normalized `ToolExecutionResult`.

## Notes
- Rate limiting is represented as policy hints/placeholders in this phase.
- Not production-hardening; local development baseline only.
