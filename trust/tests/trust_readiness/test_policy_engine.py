from pathlib import Path

from backend.trust_readiness.policy_engine import PolicyAsCodeEngine


POLICY_PATH = Path("policies/control-plane/default-governance-policy.json")


def test_retrieval_policy_blocks_high_classification_without_matching_clearance() -> None:
    engine = PolicyAsCodeEngine.from_file(POLICY_PATH)

    decision = engine.evaluate_retrieval_access(
        {
            "tenant_id": "tenant-dashboard",
            "source": "qdrant",
            "source_classification": "restricted",
            "actor_clearance": "internal",
            "purpose": "runtime_handoff",
        }
    )

    assert decision.allow is False
    assert "retrieval.clearance_insufficient:restricted" in decision.reason_codes
    assert decision.default_deny is True


def test_tool_policy_blocks_unapproved_mcp_tool_and_requires_privileged_approval() -> None:
    engine = PolicyAsCodeEngine.from_file(POLICY_PATH)

    decision = engine.evaluate_tool_authorization(
        {
            "runtime_id": "onyx",
            "surface": "onyx.apps",
            "mcp_server": "mcp_server.unapproved",
            "tool_id": "onyx_admin",
            "risk": "high",
            "action_type": "external_write",
            "approved": False,
        }
    )

    assert decision.allow is False
    assert "policy.mcp_server_not_allowed:mcp_server.unapproved" in decision.reason_codes
    assert "tool.approval_required:onyx_admin" in decision.reason_codes


def test_launch_gate_policy_blocks_stale_evidence_and_unhealthy_sinks() -> None:
    engine = PolicyAsCodeEngine.from_file(POLICY_PATH)

    decision = engine.evaluate_launch_gate(
        {
            "freshness": {"identity": "fresh", "policy": "stale"},
            "telemetry_healthy": False,
            "audit_healthy": False,
        }
    )

    assert decision.allow is False
    assert "launch.evidence_stale:policy" in decision.reason_codes
    assert "launch.telemetry_unhealthy" in decision.reason_codes
    assert "launch.audit_unhealthy" in decision.reason_codes
