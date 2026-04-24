from __future__ import annotations

from .interfaces import PolicyChecker, RetrievalChecker, TelemetryEmitter, ToolDecisionChecker
from .schemas import NormalizedDecision, NormalizedRequest, TelemetryEvent


class OnyxGatewayAdapter:
    """Adapter layer between runtime requests and governance controls.

    Design goal: remain independent of upstream Onyx internals by accepting
    already-normalized request objects and returning normalized decisions.
    """

    def __init__(
        self,
        policy_checker: PolicyChecker,
        retrieval_checker: RetrievalChecker,
        tool_checker: ToolDecisionChecker,
        telemetry_emitter: TelemetryEmitter,
    ) -> None:
        self._policy_checker = policy_checker
        self._retrieval_checker = retrieval_checker
        self._tool_checker = tool_checker
        self._telemetry_emitter = telemetry_emitter

    def evaluate(self, request: NormalizedRequest) -> NormalizedDecision:
        self._telemetry_emitter.emit(
            TelemetryEvent(
                event_type="adapter.request.received",
                request_id=request.request_id,
                tenant_id=request.tenant_id,
                payload={"requested_tools": request.requested_tools, "retrieval_needed": request.retrieval_needed},
            )
        )

        policy_result = self._policy_checker.check_policy(request)
        retrieval_result = self._retrieval_checker.check_retrieval(request)
        tool_result = self._tool_checker.check_tools(request)

        reasons = []
        reasons.extend(policy_result.reasons)
        reasons.extend(retrieval_result.reasons)
        reasons.extend(tool_result.reasons)

        allow = (
            policy_result.allow
            and retrieval_result.allow
            and len(tool_result.denied_tools) == 0
        )

        decision = NormalizedDecision(
            allow=allow,
            reasons=reasons,
            policy_allow=policy_result.allow,
            retrieval_allow=retrieval_result.allow,
            allowed_tools=tool_result.allowed_tools,
            denied_tools=tool_result.denied_tools,
        )

        self._telemetry_emitter.emit(
            TelemetryEvent(
                event_type="adapter.decision",
                request_id=request.request_id,
                tenant_id=request.tenant_id,
                payload={
                    "allow": decision.allow,
                    "reasons": decision.reasons,
                    "policy_allow": decision.policy_allow,
                    "retrieval_allow": decision.retrieval_allow,
                    "allowed_tools": decision.allowed_tools,
                    "denied_tools": decision.denied_tools,
                },
            )
        )

        return decision
