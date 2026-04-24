from __future__ import annotations

from .interfaces import SandboxAuditSink, SandboxExecutor, SandboxPolicyEvaluator
from .schemas import SandboxExecutionRequest, SandboxExecutionResult


class SandboxingDecisionEngine:
    """Decision and handoff layer for risky execution sandboxing.

    Focuses on decision logic and integration points, not runtime sandbox deployment.
    """

    def __init__(
        self,
        policy_evaluator: SandboxPolicyEvaluator,
        executor: SandboxExecutor,
        audit_sink: SandboxAuditSink,
    ) -> None:
        self._policy = policy_evaluator
        self._executor = executor
        self._audit = audit_sink

    def decide_and_execute(self, request: SandboxExecutionRequest) -> SandboxExecutionResult:
        decision = self._policy.evaluate(request)

        self._audit.emit(
            "sandbox.decision",
            {
                "request_id": request.request_id,
                "tenant_id": request.tenant_id,
                "mode": decision.mode,
                "reasons": decision.reasons,
                "risk_score": decision.risk_score,
                "policy_ref": decision.policy_ref,
            },
        )

        if decision.mode == "deny":
            return SandboxExecutionResult(
                executed=False,
                mode="deny",
                reasons=decision.reasons,
                metadata={"policy_ref": decision.policy_ref},
            )

        execution_output = self._executor.execute(request, mode=decision.mode)

        self._audit.emit(
            "sandbox.execute",
            {
                "request_id": request.request_id,
                "tenant_id": request.tenant_id,
                "mode": decision.mode,
                "output_keys": sorted(list(execution_output.keys())),
            },
        )

        return SandboxExecutionResult(
            executed=True,
            mode=decision.mode,
            reasons=decision.reasons,
            metadata={"policy_ref": decision.policy_ref, "handoff": "executor"},
        )
