from adapters.tools.engine import ToolGovernanceEngine
from adapters.tools.interfaces import InMemoryAuditSink, ToolExecutor
from adapters.tools.policy_model import StaticToolPolicyEvaluator, default_policy_config
from adapters.tools.schemas import ToolActionRequest


class StubExecutor(ToolExecutor):
    def __init__(self) -> None:
        self.calls = 0

    def execute(self, request: ToolActionRequest) -> dict:
        self.calls += 1
        return {"ok": True, "tool": request.tool_name}


def make_request(tool_name: str, confirmed: bool = False, arguments=None) -> ToolActionRequest:
    return ToolActionRequest(
        request_id="req-1",
        tenant_id="tenant-a",
        user_id="user-1",
        tool_name=tool_name,
        arguments=arguments or {},
        confirmed=confirmed,
    )


def test_allowlisted_tool_executes_and_audits_allow_execute() -> None:
    audit = InMemoryAuditSink()
    executor = StubExecutor()
    policy = StaticToolPolicyEvaluator(default_policy_config())
    engine = ToolGovernanceEngine(policy, executor, audit)

    result = engine.evaluate(make_request("search"))

    assert result.executed is True
    assert result.status == "allow"
    assert executor.calls == 1
    assert [e.event_type for e in audit.events] == ["allow", "execute"]


def test_forbidden_tool_denied_and_audited() -> None:
    audit = InMemoryAuditSink()
    executor = StubExecutor()
    policy = StaticToolPolicyEvaluator(default_policy_config())
    engine = ToolGovernanceEngine(policy, executor, audit)

    result = engine.evaluate(make_request("shell.exec"))

    assert result.executed is False
    assert result.status == "deny"
    assert "forbidden_tool" in result.reason_codes
    assert executor.calls == 0
    assert [e.event_type for e in audit.events] == ["deny"]


def test_confirmation_required_tool_emits_confirm() -> None:
    audit = InMemoryAuditSink()
    executor = StubExecutor()
    policy = StaticToolPolicyEvaluator(default_policy_config())
    engine = ToolGovernanceEngine(policy, executor, audit)

    result = engine.evaluate(make_request("email.send", confirmed=False))

    assert result.executed is False
    assert result.status == "confirm_required"
    assert "confirmation_required" in result.reason_codes
    assert executor.calls == 0
    assert [e.event_type for e in audit.events] == ["confirm"]


def test_forbidden_argument_denied() -> None:
    audit = InMemoryAuditSink()
    executor = StubExecutor()
    policy = StaticToolPolicyEvaluator(default_policy_config())
    engine = ToolGovernanceEngine(policy, executor, audit)

    result = engine.evaluate(make_request("search", arguments={"password": "x"}))

    assert result.executed is False
    assert result.status == "deny"
    assert "forbidden_arguments" in result.reason_codes


def test_high_risk_classification_and_rate_limit_placeholder_in_audit() -> None:
    audit = InMemoryAuditSink()
    executor = StubExecutor()
    policy = StaticToolPolicyEvaluator(default_policy_config())
    engine = ToolGovernanceEngine(policy, executor, audit)

    result = engine.evaluate(make_request("payment.charge", confirmed=True))

    assert result.executed is True
    allow_event = audit.events[0]
    assert allow_event.event_type == "allow"
    assert allow_event.payload["risk_level"] == "high"
    assert allow_event.payload["rate_limit_hint"] == "5/min"
