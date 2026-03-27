import json
from pathlib import Path

from backend.launch_gate_service.service import build_launch_gate_summary
from backend.posture_service.service import build_control_plane_dashboard


def test_dashboard_sections_follow_required_order() -> None:
    payload = build_control_plane_dashboard()

    assert [section["title"] for section in payload["sections"]] == [
        "Global Security Posture",
        "Live Runtime Activity",
        "Retrieval Security View",
        "Tool and MCP Control View",
        "AI Traces and Evals",
        "Audit and Replay",
        "Launch Gate and Readiness",
        "Entry Points",
    ]


def test_dashboard_tabs_match_control_plane_story() -> None:
    payload = build_control_plane_dashboard()

    assert [tab["label"] for tab in payload["tabs"]] == [
        "Overview",
        "Runtime",
        "Retrieval",
        "Tools & MCP",
        "Policies",
        "Evals",
        "Audit & Replay",
        "Launch Gate",
        "Evidence Pack",
        "Chat / Agents",
    ]


def test_frontend_assets_exist_for_dashboard_homepage() -> None:
    html = Path("frontend/main-dashboard/index.html").read_text(encoding="utf-8")
    js = Path("frontend/main-dashboard/app.js").read_text(encoding="utf-8")

    assert "Trust &amp; Security Operations Dashboard for RAG and Autonomous Agents" in html
    assert "/api/control-plane/overview" in js


def test_launch_gate_summary_maps_existing_report() -> None:
    summary = build_launch_gate_summary()

    assert summary["status"] == "conditional"
    assert summary["readiness_score"] > 0
    assert "risky_config_defaults_disabled" in summary["missing_controls"]


def test_contract_files_present() -> None:
    for contract_path in (
        "contracts/posture.schema.json",
        "contracts/audit.schema.json",
        "contracts/eval.schema.json",
        "contracts/launch-gate.schema.json",
        "contracts/tools.inventory.schema.json",
        "contracts/retrieval.schema.json",
    ):
        payload = json.loads(Path(contract_path).read_text(encoding="utf-8"))
        assert payload["type"] == "object"
