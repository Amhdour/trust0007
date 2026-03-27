import json
from pathlib import Path

from backend.integration_adapter.repository import load_dashboard_contract
from backend.launch_gate_service.service import build_launch_gate_summary
from backend.posture_service.service import build_control_plane_dashboard


def test_dashboard_sections_follow_required_order() -> None:
    payload = build_control_plane_dashboard()
    contract = load_dashboard_contract()

    assert [section["title"] for section in payload["sections"]] == [
        section["title"] for section in contract["sections"]
    ]


def test_dashboard_tabs_match_control_plane_story() -> None:
    payload = build_control_plane_dashboard()
    contract = load_dashboard_contract()

    assert [tab["label"] for tab in payload["tabs"]] == [tab["label"] for tab in contract["tabs"]]


def test_frontend_assets_exist_for_dashboard_homepage() -> None:
    html = Path("frontend/main-dashboard/index.html").read_text(encoding="utf-8")
    js = Path("frontend/main-dashboard/app.js").read_text(encoding="utf-8")

    assert 'id="hero-title"' in html
    assert 'id="hero-copy"' in html
    assert "payload.title" in js
    assert "payload.landing_steps" in js
    assert "/api/control-plane/overview" in js


def test_dashboard_payload_uses_shared_contract_fields() -> None:
    payload = build_control_plane_dashboard()
    contract = load_dashboard_contract()

    assert payload["title"] == contract["title"]
    assert payload["subtitle"] == contract["subtitle"]
    assert payload["hero_copy"] == contract["hero_copy"]
    assert payload["landing_steps"] == contract["landing_steps"]


def test_launch_gate_summary_maps_existing_report() -> None:
    summary = build_launch_gate_summary()

    assert summary["status"] == "conditional"
    assert summary["readiness_score"] > 0
    assert "risky_config_defaults_disabled" in summary["missing_controls"]


def test_dashboard_links_fallback_to_local_artifacts_when_overlay_is_missing() -> None:
    payload = build_control_plane_dashboard()

    source_hrefs = {source["label"]: source["href"] for source in payload["sources"]}
    assert source_hrefs["Policy bundle"] == "/raw/policies/runtime-policy-fallback.json"
    assert source_hrefs["Reviewer evidence bundle"] == "/raw/evidence/reviewer_evidence_bundle.json"

    entry_points = next(section for section in payload["sections"] if section["id"] == "entry-points")
    link_items = []
    for block in entry_points["blocks"]:
        if block["type"] == "links":
            link_items.extend(block["items"])

    links = {item["label"]: item for item in link_items}
    assert links["Review Policies"]["href"].endswith("/raw/policies/runtime-policy-fallback.json")
    assert links["Review Evidence Pack"]["href"].endswith("/raw/evidence/reviewer_evidence_bundle.json")
    assert links["Review Evals"]["href"].endswith("/raw/docs/langfuse-integration.md")
    assert links["Admin / Tenant Settings"]["href"].endswith("/raw/docs/keycloak-integration.md")


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
