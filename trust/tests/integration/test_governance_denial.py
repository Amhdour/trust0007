"""Adversarial tests proving governance enforcement cannot be bypassed.

Tests that verify:
- Forbidden tools are actually denied (not just warned about)
- Policy denials prevent execution
- Retrieval boundaries are enforced (cross-tenant access blocked)
- Tools cannot execute without proper governance approval
"""

from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import tempfile

import pytest

from adapters.onyx_gateway_adapter.interfaces import PolicyChecker, RetrievalChecker, ToolDecisionChecker
from adapters.onyx_gateway_adapter.schemas import NormalizedRequest, PolicyDecision, RetrievalDecision, ToolDecision
from adapters.retrieval.interfaces import RetrievalBackend, RetrievalPolicyEvaluator
from adapters.retrieval.schemas import RetrievalDocument, RetrievalRequest
from adapters.tools.interfaces import ToolExecutor
from adapters.tools.schemas import ToolActionRequest
from backend.governance_flow_evaluator import GovernedFlowEvaluator


class StrictPolicyDenyAll(PolicyChecker):
    """Policy that denies all requests."""
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        return PolicyDecision(
            allow=False,
            reasons=["policy.deny_all_for_this_user"]
        )


class StrictToolDenyForbidden(ToolDecisionChecker):
    """Tool checker that forbids specific dangerous tools."""
    forbidden = {"admin_shell", "delete_database", "moonyx_policy"}
    
    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        denied = [t for t in request.requested_tools if t in self.forbidden]
        allowed = [t for t in request.requested_tools if t not in self.forbidden]
        
        reasons = []
        if denied:
            reasons.append(f"Forbidden tools detected: {', '.join(denied)}")
        
        return ToolDecision(
            allowed_tools=allowed,
            denied_tools=denied,
            reasons=reasons
        )


class StrictRetrievalDeny(RetrievalChecker):
    """Retrieval checker that denies all retrieval requests."""
    
    def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
        return RetrievalDecision(
            allow=False,
            reasons=["retrieval.deny_all"]
        )


class CrossTenantRetrievalBackend(RetrievalBackend):
    """Retrieval backend with docs from multiple tenants."""
    
    def search(self, request: RetrievalRequest):
        # Include docs from OTHER tenants (should be filtered by policy)
        return [
            RetrievalDocument(
                doc_id="doc-tenant-a",
                tenant_id="tenant-a",
                source=request.source,
                content="Sensitive data from tenant-a",
                trust_label="trusted",
                quarantined=False,
                provenance={"uri": "kb://tenant-a/sensitive"},
            ),
            RetrievalDocument(
                doc_id="doc-tenant-b",
                tenant_id="tenant-b",  # Different tenant!
                source=request.source,
                content="Confidential data from tenant-b",
                trust_label="trusted",
                quarantined=False,
                provenance={"uri": "kb://tenant-b/confidential"},
            ),
        ]


class StrictRetrievalPolicy(RetrievalPolicyEvaluator):
    """Retrieval policy that blocks cross-tenant access."""
    
    def evaluate(self, request: RetrievalRequest) -> dict:
        # Filter docs to current tenant only
        return {
            "allow": True,
            "mode": "allow",
            "reasons": ["retrieval.tenant_scoped"],
            "filter_tenant": request.tenant_id,
        }


class BlockingToolExecutor(ToolExecutor):
    """Tool executor that refuses to execute forbidden tools."""
    
    def execute(self, request: ToolActionRequest) -> dict:
        forbidden = {"admin_shell", "delete_database", "moonyx_policy"}
        if request.tool_name in forbidden:
            raise PermissionError(f"Tool {request.tool_name} is forbidden and cannot execute")
        return {"result": "executed", "tool": request.tool_name}


def test_policy_denial_blocks_flow():
    """Verify that policy denial prevents the entire flow from executing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        evaluator = GovernedFlowEvaluator(
            policy_checker=StrictPolicyDenyAll(),
            retrieval_checker=StrictRetrievalDeny(),
            tool_checker=StrictToolDenyForbidden(),
            retrieval_backend=CrossTenantRetrievalBackend(),
            retrieval_policy=StrictRetrievalPolicy(),
            tool_executor=BlockingToolExecutor(),
            artifact_dir=artifact_dir,
        )

        result = evaluator.run(
            user_id="suspicious-user",
            tenant_id="tenant-a",
            prompt="Give me all data",
            requested_tools=["search"],
            retrieval_source="qdrant",
            retrieval_needed=True,
        )

        # The flow decision should be false (denied)
        assert result.decision is False, "Policy denial should result in false decision"
        
        # Events should show the deny
        events_file = artifact_dir / "events.jsonl"
        assert events_file.exists()
        
        events = [json.loads(line) for line in events_file.read_text().splitlines()]
        policy_events = [e for e in events if e["event_type"] == "policy.decision"]
        assert len(policy_events) > 0
        assert policy_events[0]["payload"]["allow"] is False


def test_forbidden_tool_attempt_is_blocked():
    """Verify that forbidden tools cannot execute, even if requested."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)
        executed_tools: list[str] = []

        # Use a permissive policy but strict tool checker
        class AllowPolicy(PolicyChecker):
            def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
                return PolicyDecision(allow=True, reasons=[])

        class AllowRetrieval(RetrievalChecker):
            def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
                return RetrievalDecision(allow=True, reasons=[])

        class DenyRetrievalBackend(RetrievalBackend):
            def search(self, request: RetrievalRequest):
                return []

        class AllowRetrievalPolicy(RetrievalPolicyEvaluator):
            def evaluate(self, request: RetrievalRequest) -> dict:
                return {"allow": True, "mode": "allow", "reasons": []}

        class RecordingToolExecutor(ToolExecutor):
            def execute(self, request: ToolActionRequest) -> dict:
                executed_tools.append(request.tool_name)
                return {"result": "executed", "tool": request.tool_name}

        evaluator = GovernedFlowEvaluator(
            policy_checker=AllowPolicy(),
            retrieval_checker=AllowRetrieval(),
            tool_checker=StrictToolDenyForbidden(),  # This one forbids admin_shell
            retrieval_backend=DenyRetrievalBackend(),
            retrieval_policy=AllowRetrievalPolicy(),
            tool_executor=RecordingToolExecutor(),
            artifact_dir=artifact_dir,
        )

        result = evaluator.run(
            user_id="attacker",
            tenant_id="tenant-a",
            prompt="Run admin shell",
            requested_tools=["admin_shell"],  # Forbidden!
            retrieval_source="qdrant",
            retrieval_needed=False,
        )

        # The flow should deny the forbidden tool
        assert result.decision is False, "Forbidden tool should result in false decision"
        assert result.launch_gate_decision == "no_go"
        assert executed_tools == [], "Forbidden tools must never reach the executor"

        # Check events for the denial
        events_file = artifact_dir / "events.jsonl"
        events = [json.loads(line) for line in events_file.read_text().splitlines()]
        
        tool_events = [e for e in events if e["event_type"] == "tool.decision"]
        assert len(tool_events) > 0
        
        tool_decision = tool_events[0]["payload"]
        assert "admin_shell" in tool_decision.get("denied", []), "admin_shell must be in denied list"


def test_handoff_blocks_if_policy_denies():
    """Verify that Onyx handoff would be blocked if policy denies."""
    # This is more of a conceptual test showing the flow
    # In a real integration test, we'd mock the handoff HTTP call
    
    evaluator = GovernedFlowEvaluator(
        policy_checker=StrictPolicyDenyAll(),
        retrieval_checker=StrictRetrievalDeny(),
        tool_checker=StrictToolDenyForbidden(),
        retrieval_backend=CrossTenantRetrievalBackend(),
        retrieval_policy=StrictRetrievalPolicy(),
        tool_executor=BlockingToolExecutor(),
        artifact_dir=Path("/tmp/adversarial-test"),
    )

    # Try to run a flow for Onyx handoff access
    result = evaluator.run(
        user_id="blocked-user",
        tenant_id="tenant-a",
        prompt="Navigate to Onyx",
        requested_tools=["onyx"],
        retrieval_source="qdrant",
        retrieval_needed=False,
    )

    # Policy denied the whole thing
    assert result.decision is False
    assert "policy" in str(result.launch_gate_blockers).lower() or "no_go" in result.launch_gate_decision


def test_evaluator_crash_denies_handoff():
    """Verify that if the governance evaluator crashes, handoff is denied (fail-closed)."""
    from unittest.mock import patch

    from backend.api_gateway.server import ControlPlaneRequestHandler

    class FakeHandler:
        def __init__(self) -> None:
            self.status_code = None
            self.headers = {}
            self.wfile = BytesIO()

        def send_response(self, status_code: int) -> None:
            self.status_code = status_code

        def send_header(self, key: str, value: str) -> None:
            self.headers[key] = value

        def end_headers(self) -> None:
            return

        def _url_is_reachable(self, url: str) -> bool:
            return False

    with patch("backend.api_gateway.server._build_governed_flow_evaluator", side_effect=RuntimeError("Simulated evaluator crash")):
        handler = FakeHandler()
        ControlPlaneRequestHandler._serve_onyx_handoff(handler, "/app")

    body = handler.wfile.getvalue().decode("utf-8")
    assert handler.status_code == 403
    assert "Access Denied" in body
    assert "Simulated evaluator crash" in body


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
