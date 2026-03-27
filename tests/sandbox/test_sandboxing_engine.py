from adapters.sandbox.engine import SandboxingDecisionEngine
from adapters.sandbox.interfaces import InMemorySandboxAuditSink, SandboxExecutor
from adapters.sandbox.policy_model import (
    StaticSandboxPolicyEvaluator,
    default_sandbox_policy_config,
)
from adapters.sandbox.schemas import SandboxExecutionRequest


class StubExecutor(SandboxExecutor):
    def __init__(self) -> None:
        self.calls = 0
        self.modes = []

    def execute(self, request: SandboxExecutionRequest, mode: str) -> dict:
        self.calls += 1
        self.modes.append(mode)
        return {"ok": True, "mode": mode}


def mkreq(**kwargs) -> SandboxExecutionRequest:
    base = {
        "request_id": "r1",
        "tenant_id": "tenant-a",
        "action_type": "read_only",
        "tool_name": "search",
        "network_access": False,
        "filesystem_write": False,
        "external_integration": False,
        "code_supplied_by_user": False,
        "policy_context": {},
    }
    base.update(kwargs)
    return SandboxExecutionRequest(**base)


def test_allow_low_risk_execution() -> None:
    audit = InMemorySandboxAuditSink()
    executor = StubExecutor()
    policy = StaticSandboxPolicyEvaluator(default_sandbox_policy_config())
    engine = SandboxingDecisionEngine(policy, executor, audit)

    result = engine.decide_and_execute(mkreq())

    assert result.executed is True
    assert result.mode == "allow"
    assert executor.calls == 1
    assert executor.modes == ["allow"]
    assert [e["event_type"] for e in audit.events] == ["sandbox.decision", "sandbox.execute"]


def test_sandbox_risky_execution() -> None:
    audit = InMemorySandboxAuditSink()
    executor = StubExecutor()
    policy = StaticSandboxPolicyEvaluator(default_sandbox_policy_config())
    engine = SandboxingDecisionEngine(policy, executor, audit)

    result = engine.decide_and_execute(
        mkreq(action_type="code_execution", tool_name="python.exec", code_supplied_by_user=True)
    )

    assert result.executed is True
    assert result.mode == "sandbox"
    assert executor.modes == ["sandbox"]


def test_deny_blocked_action() -> None:
    audit = InMemorySandboxAuditSink()
    executor = StubExecutor()
    policy = StaticSandboxPolicyEvaluator(default_sandbox_policy_config())
    engine = SandboxingDecisionEngine(policy, executor, audit)

    result = engine.decide_and_execute(mkreq(action_type="privilege_escalation"))

    assert result.executed is False
    assert result.mode == "deny"
    assert executor.calls == 0
    assert [e["event_type"] for e in audit.events] == ["sandbox.decision"]
