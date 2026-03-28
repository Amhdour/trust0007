"""Integration test for the governed flow evaluator in the control plane.

This test verifies that:
1. GovernedFlowEvaluator can be instantiated with demo checkers
2. The evaluator produces a complete flow with all governance decisions
3. Artifacts are written to the overlay directory
4. Launch-gate evaluation produces the expected decision
"""

from __future__ import annotations

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


class StubPolicyAllow(PolicyChecker):
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        return PolicyDecision(allow=True, reasons=["policy.allow"])


class StubRetrievalAllow(RetrievalChecker):
    def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
        return RetrievalDecision(allow=True, reasons=["retrieval.allow"])


class StubToolAllow(ToolDecisionChecker):
    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        return ToolDecision(allowed_tools=request.requested_tools, denied_tools=[], reasons=[])


class StubRetrievalBackend(RetrievalBackend):
    def search(self, request: RetrievalRequest):
        return [
            RetrievalDocument(
                doc_id="test-doc-1",
                tenant_id=request.tenant_id,
                source=request.source,
                content="Test retrieval document.",
                trust_label="trusted",
                quarantined=False,
                provenance={"uri": "kb://test-doc-1"},
            )
        ]


class StubRetrievalPolicy(RetrievalPolicyEvaluator):
    def evaluate(self, request: RetrievalRequest) -> dict:
        return {"allow": True, "mode": "allow", "reasons": []}


class StubToolExecutor(ToolExecutor):
    def execute(self, request: ToolActionRequest) -> dict:
        return {"result": "executed", "tool": request.tool_name}


def test_governed_flow_happy_path():
    """Test a complete governed flow with all controls passing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        evaluator = GovernedFlowEvaluator(
            policy_checker=StubPolicyAllow(),
            retrieval_checker=StubRetrievalAllow(),
            tool_checker=StubToolAllow(),
            retrieval_backend=StubRetrievalBackend(),
            retrieval_policy=StubRetrievalPolicy(),
            tool_executor=StubToolExecutor(),
            artifact_dir=artifact_dir,
        )

        result = evaluator.run(
            user_id="test-user",
            tenant_id="test-tenant",
            prompt="Test query",
            requested_tools=["search"],
            retrieval_source="qdrant",
            retrieval_needed=True,
        )

        # Verify flow decision
        assert result.decision is True
        assert result.trace_id.startswith("flow-")
        assert result.request_id.startswith("req-")

        # Verify launch-gate passed
        assert result.launch_gate_decision == "pass"
        assert result.launch_gate_score > 0
        assert len(result.launch_gate_blockers) == 0

        # Verify artifacts were written
        assert "events_jsonl" in result.artifacts
        assert "launch_gate_result" in result.artifacts

        # Verify artifact files exist
        events_file = artifact_dir / "events.jsonl"
        gate_file = artifact_dir / "launch-gate-result.json"

        assert events_file.exists()
        assert gate_file.exists()

        # Verify events were recorded
        events = [json.loads(line) for line in events_file.read_text().splitlines()]
        assert len(events) > 0
        event_types = {e["event_type"] for e in events}
        assert "request.start" in event_types
        assert "identity.established" in event_types
        assert "policy.decision" in event_types
        assert "request.end" in event_types

        # Verify launch-gate artifact structure
        gate_data = json.loads(gate_file.read_text())
        assert "machine" in gate_data
        assert "human" in gate_data
        assert "flow_metadata" in gate_data
        assert gate_data["machine"]["decision"] == "pass"


def test_governed_flow_with_policy_deny():
    """Test governed flow when policy checker denies."""

    class StubPolicyDeny(PolicyChecker):
        def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
            return PolicyDecision(allow=False, reasons=["policy.denied"])

    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)

        evaluator = GovernedFlowEvaluator(
            policy_checker=StubPolicyDeny(),
            retrieval_checker=StubRetrievalAllow(),
            tool_checker=StubToolAllow(),
            retrieval_backend=StubRetrievalBackend(),
            retrieval_policy=StubRetrievalPolicy(),
            tool_executor=StubToolExecutor(),
            artifact_dir=artifact_dir,
        )

        result = evaluator.run(
            user_id="test-user",
            tenant_id="test-tenant",
            prompt="Test query",
            requested_tools=["search"],
            retrieval_source="qdrant",
            retrieval_needed=True,
        )

        # Flow decision should be false when policy denies
        assert result.decision is False

        # Launch-gate should show conditional status due to missing evidence
        assert result.launch_gate_decision in ["conditional_go", "no_go"]


def test_governed_flow_artifact_to_overlay_path():
    """Test that default artifact directory is overlay path."""
    evaluator = GovernedFlowEvaluator(
        policy_checker=StubPolicyAllow(),
        retrieval_checker=StubRetrievalAllow(),
        tool_checker=StubToolAllow(),
        retrieval_backend=StubRetrievalBackend(),
        retrieval_policy=StubRetrievalPolicy(),
        tool_executor=StubToolExecutor(),
        artifact_dir=None,  # Use default
    )

    # Check that the artifact dir is set to overlay path
    expected_overlay_dir = Path(__file__).resolve().parents[2] / "overlays" / "myStarterKit" / "artifacts"
    assert evaluator._artifact_dir == expected_overlay_dir


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
