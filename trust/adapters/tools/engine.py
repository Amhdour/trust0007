from __future__ import annotations

from .interfaces import ToolAuditSink, ToolExecutor, ToolPolicyEvaluator
from .schemas import AuditEvent, ToolActionRequest, ToolExecutionResult


class ToolGovernanceEngine:
    """Policy-driven governance layer for tool/integration actions.

    Keeps policy logic (ToolPolicyEvaluator) separate from business logic
    execution (ToolExecutor).
    """

    def __init__(
        self,
        policy_evaluator: ToolPolicyEvaluator,
        executor: ToolExecutor,
        audit_sink: ToolAuditSink,
    ) -> None:
        self._policy = policy_evaluator
        self._executor = executor
        self._audit = audit_sink

    def evaluate(self, request: ToolActionRequest) -> ToolExecutionResult:
        decision = self._policy.evaluate(request)

        if decision.status == "deny":
            self._audit.emit(
                AuditEvent(
                    event_type="deny",
                    request_id=request.request_id,
                    tenant_id=request.tenant_id,
                    tool_name=request.tool_name,
                    payload={
                        "reasons": decision.reason_codes,
                        "risk_level": decision.risk_level,
                        "rate_limit_hint": decision.rate_limit_hint,
                    },
                )
            )
            return ToolExecutionResult(
                executed=False,
                status="deny",
                output={},
                reason_codes=decision.reason_codes,
            )

        if decision.status == "confirm_required":
            self._audit.emit(
                AuditEvent(
                    event_type="confirm",
                    request_id=request.request_id,
                    tenant_id=request.tenant_id,
                    tool_name=request.tool_name,
                    payload={
                        "reasons": decision.reason_codes,
                        "risk_level": decision.risk_level,
                        "rate_limit_hint": decision.rate_limit_hint,
                    },
                )
            )
            return ToolExecutionResult(
                executed=False,
                status="confirm_required",
                output={},
                reason_codes=decision.reason_codes,
            )

        self._audit.emit(
            AuditEvent(
                event_type="allow",
                request_id=request.request_id,
                tenant_id=request.tenant_id,
                tool_name=request.tool_name,
                payload={
                    "risk_level": decision.risk_level,
                    "rate_limit_hint": decision.rate_limit_hint,
                    "rate_limit_key": decision.rate_limit_key,
                },
            )
        )

        output = self._executor.execute(request)

        self._audit.emit(
            AuditEvent(
                event_type="execute",
                request_id=request.request_id,
                tenant_id=request.tenant_id,
                tool_name=request.tool_name,
                payload={
                    "output_keys": sorted(list(output.keys())),
                    "risk_level": decision.risk_level,
                },
            )
        )

        return ToolExecutionResult(
            executed=True,
            status="allow",
            output=output,
            reason_codes=decision.reason_codes,
        )
