from __future__ import annotations

from .test_strict_live_shared import live_stack


def test_strict_live_dify_handoff_passes_with_runtime_specific_governance(live_stack) -> None:
    token = live_stack.mint_access_token()

    response = live_stack.launch(path="/apps", token=token, runtime="dify", mcp_server="mcp_server.dashboard_control_plane")
    assert response.status_code == 200
    assert "Governance Status:</strong> ✓ Approved" in response.text
    assert "Evidence mode: <code>live</code>" in response.text

    summary = live_stack.fetch_json_artifact("governed-flow-summary.json")
    runtime_proof = live_stack.fetch_json_artifact("dify-runtime-proof.json")
    tool_evidence = live_stack.fetch_json_artifact("tool-evidence.json")

    assert summary["evidence_mode"] == "live"
    assert summary["identity"]["live"] is True
    assert summary["policy"]["engine"] == "opa"
    assert summary["policy"]["allow"] is True
    assert summary["launch_gate"]["decision"] == "pass"
    assert summary["handoff_allowed"] is True
    assert summary["decision"] is True
    assert summary["runtime_target"] == "dify"
    assert runtime_proof["runtime_key"] == "dify"
    assert runtime_proof["runtime_class"] == "autonomous_agents"
    assert runtime_proof["requested_path"] == "/apps"
    assert summary["runtime_proof"]["artifact"].endswith("dify-runtime-proof.json")

    assert tool_evidence["runtime_target"] == "dify"
    assert tool_evidence["mcp_governance_required"] is True
    assert tool_evidence["mcp_governed"] is True
    assert tool_evidence["mcp_server"] == "mcp_server.dashboard_control_plane"


def test_strict_live_dify_handoff_denies_unapproved_mcp_server(live_stack) -> None:
    token = live_stack.mint_access_token()

    response = live_stack.launch(path="/apps", token=token, runtime="dify", mcp_server="mcp_server.unapproved")
    assert response.status_code == 403
    assert "policy.mcp_server_not_allowed:mcp_server.unapproved" in response.text

    summary = live_stack.fetch_json_artifact("governed-flow-summary.json")
    assert "policy.mcp_server_not_allowed:mcp_server.unapproved" in summary["reasons"]
