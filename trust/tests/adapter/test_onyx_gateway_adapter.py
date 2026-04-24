from adapters.onyx_gateway_adapter.adapter import OnyxGatewayAdapter
from adapters.onyx_gateway_adapter.interfaces import (
    PolicyChecker,
    RetrievalChecker,
    ToolDecisionChecker,
)
from adapters.onyx_gateway_adapter.schemas import (
    NormalizedRequest,
    PolicyDecision,
    RetrievalDecision,
    ToolDecision,
)
from adapters.onyx_gateway_adapter.telemetry import InMemoryTelemetryEmitter


class StubPolicyAllow(PolicyChecker):
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        return PolicyDecision(allow=True, reasons=[])


class StubPolicyDeny(PolicyChecker):
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        return PolicyDecision(allow=False, reasons=["policy denied request"])


class StubRetrievalAllow(RetrievalChecker):
    def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
        return RetrievalDecision(allow=True, reasons=[])


class StubToolAllow(ToolDecisionChecker):
    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        return ToolDecision(allowed_tools=request.requested_tools, denied_tools=[], reasons=[])


class StubToolDeny(ToolDecisionChecker):
    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        return ToolDecision(
            allowed_tools=[],
            denied_tools=request.requested_tools,
            reasons=["tool denied by governance"],
        )


def make_request() -> NormalizedRequest:
    return NormalizedRequest(
        request_id="req-1",
        tenant_id="tenant-a",
        user_id="user-1",
        prompt="Summarize latest incidents",
        requested_tools=["search"],
        retrieval_needed=True,
        retrieval_source="qdrant",
        metadata={"trace_id": "trace-1"},
    )


def test_happy_path_allow() -> None:
    emitter = InMemoryTelemetryEmitter()
    adapter = OnyxGatewayAdapter(
        policy_checker=StubPolicyAllow(),
        retrieval_checker=StubRetrievalAllow(),
        tool_checker=StubToolAllow(),
        telemetry_emitter=emitter,
    )

    result = adapter.evaluate(make_request())

    assert result.allow is True
    assert result.reasons == []
    assert result.allowed_tools == ["search"]
    assert result.denied_tools == []
    assert [e.event_type for e in emitter.events] == [
        "adapter.request.received",
        "adapter.decision",
    ]


def test_deny_path() -> None:
    emitter = InMemoryTelemetryEmitter()
    adapter = OnyxGatewayAdapter(
        policy_checker=StubPolicyDeny(),
        retrieval_checker=StubRetrievalAllow(),
        tool_checker=StubToolDeny(),
        telemetry_emitter=emitter,
    )

    result = adapter.evaluate(make_request())

    assert result.allow is False
    assert "policy denied request" in result.reasons
    assert "tool denied by governance" in result.reasons
    assert result.denied_tools == ["search"]
    assert emitter.events[-1].event_type == "adapter.decision"
