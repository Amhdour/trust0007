from __future__ import annotations

from pathlib import Path

from backend.trust_readiness.dashboard_api import (
    build_evidence_audit_page,
    build_fleet_overview,
    build_launch_gates_page,
    build_retrieval_boundary_posture,
    build_runtime_readiness_page,
    build_tool_mcp_authorization_posture,
)
from backend.trust_readiness.launch_lanes import OnyxAgentGovernanceLane, GovernedLaunchRequest, OnyxGovernanceLane
from backend.trust_readiness.policy_engine import PolicyAsCodeEngine
from tests.trust_readiness.test_readiness_and_incidents import _seed_ready_artifacts


POLICY_PATH = Path("policies/control-plane/default-governance-policy.json")


def test_governed_onyx_lane_denies_retrieval_boundary_violation(tmp_path: Path) -> None:
    _seed_ready_artifacts(tmp_path, runtime_id="onyx")
    lane = OnyxGovernanceLane(PolicyAsCodeEngine.from_file(POLICY_PATH))

    plan = lane.plan_launch(
        GovernedLaunchRequest(
            runtime_id="onyx",
            tenant_id="tenant-dashboard",
            actor_id="user-1",
            requested_path="/app",
            auth_mode="per_user_auth",
            purpose="runtime_handoff",
            retrieval_source="incident-runbooks",
            source_classification="internal",
            actor_clearance="internal",
        ),
        root=tmp_path,
    )

    assert plan.allow is False
    assert "retrieval.source_not_allowed:incident-runbooks" in plan.explanation.reason_codes


def test_governed_onyx_lane_denies_unapproved_mcp_server(tmp_path: Path) -> None:
    _seed_ready_artifacts(tmp_path, runtime_id="onyx")
    lane = OnyxAgentGovernanceLane(PolicyAsCodeEngine.from_file(POLICY_PATH))

    plan = lane.plan_launch(
        GovernedLaunchRequest(
            runtime_id="onyx",
            tenant_id="tenant-dashboard",
            actor_id="user-1",
            requested_path="/apps",
            auth_mode="per_user_auth",
            purpose="runtime_handoff",
            mcp_server="mcp_server.unapproved",
            tool_id="onyx",
            tool_risk="low",
        ),
        root=tmp_path,
    )

    assert plan.allow is False
    assert "policy.mcp_server_not_allowed:mcp_server.unapproved" in plan.explanation.reason_codes


def test_dashboard_pages_expose_typed_contracts(tmp_path: Path) -> None:
    _seed_ready_artifacts(tmp_path, runtime_id="onyx")

    assert build_fleet_overview(tmp_path)["page"] == "Fleet Overview"
    assert build_runtime_readiness_page(tmp_path)["state_model"]
    assert build_retrieval_boundary_posture(tmp_path)["controls"]
    assert build_tool_mcp_authorization_posture(tmp_path)["risk_classes"]
    assert build_launch_gates_page(tmp_path)["policy_trace"]["decision_id"]
    assert build_evidence_audit_page(tmp_path)["audit"]["append_only_design"] is True
