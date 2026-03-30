import json
from pathlib import Path
import tempfile

from backend.integration_adapter.repository import (
    list_upstream_component_paths,
    load_dashboard_contract,
    load_runtime_policy_bundle,
    load_upstream_usage_inventory,
)
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
    assert 'id="briefing-root"' in html
    assert 'id="mode-banner-root"' in html
    assert "payload.title" in js
    assert "payload.landing_steps" in js
    assert "payload.mode_banner" in js
    assert "payload.command_center" in js
    assert "payload.audience_paths" in js
    assert "block.collapsed" in js
    assert "/api/control-plane/overview" in js


def test_dashboard_payload_uses_shared_contract_fields() -> None:
    payload = build_control_plane_dashboard()
    contract = load_dashboard_contract()

    assert payload["title"] == contract["title"]
    assert payload["subtitle"] == contract["subtitle"]
    assert payload["hero_copy"] == contract["hero_copy"]
    assert payload["landing_steps"] == contract["landing_steps"]
    assert payload["repo_description_suggestion"] == contract["repo_description_suggestion"]


def test_dashboard_surfaces_briefing_kpis_and_readiness() -> None:
    payload = build_control_plane_dashboard()

    assert payload["mode_banner"]["label"] in {"LIVE GOVERNED MODE", "DEMO / FALLBACK MODE"}
    assert len(payload["command_center"]["cards"]) >= 5
    assert payload["command_center"]["latest_request"]["title"]
    assert payload["command_center"]["flagship_proof"]["title"] == "Denied /launch/onyx handoff"
    assert payload["mode_banner"]["consequences"]
    assert len(payload["audience_paths"]) == 2
    assert len(payload["operator_briefing"]) == 5
    assert len(payload["kpis"]) >= 10
    assert payload["readiness_panel"]["status_label"] in {"GO", "CONDITIONAL", "NO-GO"}
    assert payload["data_mode"]["label"]


def test_dashboard_tabs_and_sections_have_reviewer_operator_grouping() -> None:
    payload = build_control_plane_dashboard()

    tab_groups = {tab["group_label"] for tab in payload["tabs"]}
    section_groups = {section["group_label"] for section in payload["sections"]}

    assert {"Reviewer View", "Operator Drilldown"} <= tab_groups
    assert {"Reviewer View", "Operator Drilldown"} <= section_groups


def test_dashboard_includes_upstream_integration_posture_section() -> None:
    payload = build_control_plane_dashboard()

    upstream_section = next(section for section in payload["sections"] if section["id"] == "upstream-posture")
    cards_block = next(block for block in upstream_section["blocks"] if block["type"] == "cards")
    table_block = next(block for block in upstream_section["blocks"] if block["type"] == "table")
    links_block = next(block for block in upstream_section["blocks"] if block["type"] == "links")

    labels = {item["label"] for item in cards_block["items"]}
    assert {"Used now", "Partially used", "Inventory coverage", "Mandatory path components"} <= labels
    assert any(row["component"] == "Onyx" and row["classification"] == "used_now" for row in table_block["rows"])
    assert len(table_block["rows"]) <= 5
    assert table_block["collapsed"] is True
    assert any(column["key"] == "path_status" for column in table_block["columns"])
    assert any(item["label"] == "Upstream usage API" for item in links_block["items"])


def test_upstream_usage_inventory_is_machine_readable() -> None:
    inventory = load_upstream_usage_inventory()

    assert inventory["inventory_version"] == 3
    assert inventory["components"]
    assert inventory["audit"]["inventory_covers_all_upstreams"] is True
    assert set(inventory["upstream_paths"]) == set(list_upstream_component_paths())
    assert any(component["component_name"] == "Onyx" for component in inventory["components"])
    assert any(component["classification"] == "reference_only" for component in inventory["components"])
    assert any(component["runtime_path_status"] == "mandatory" for component in inventory["components"])


def test_launch_gate_summary_maps_existing_report() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "launch-gate").mkdir(parents=True, exist_ok=True)
        (root / "launch-gate" / "evaluator.py").write_text(
            Path("launch-gate/evaluator.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "launch-gate" / "starter_launch_readiness_report.json").write_text(
            Path("launch-gate/starter_launch_readiness_report.json").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        (root / "telemetry" / "exports").mkdir(parents=True, exist_ok=True)
        (root / "telemetry" / "exports" / "sample_events.jsonl").write_text(
            Path("telemetry/exports/sample_events.jsonl").read_text(encoding="utf-8"),
            encoding="utf-8",
        )

        summary = build_launch_gate_summary(root)

    assert summary["status"] == "conditional"
    assert summary["readiness_score"] > 0
    assert "risky_config_defaults_disabled" in summary["missing_controls"]


def test_dashboard_prefers_overlay_policy_bundle_when_present() -> None:
    payload = build_control_plane_dashboard()

    source_hrefs = {source["label"]: source["href"] for source in payload["sources"]}
    assert source_hrefs["Policy bundle"] == "/raw/overlays/myStarterKit/policies/bundles/default/policy.json"
    assert source_hrefs["Reviewer evidence bundle"] == "/raw/evidence/reviewer_evidence_bundle.json"

    onyx_runtime = next(section for section in payload["sections"] if section["id"] == "entry-points")
    link_items = []
    for block in onyx_runtime["blocks"]:
        if block["type"] == "links":
            link_items.extend(block["items"])

    links = {item["label"]: item for item in link_items}
    assert links["Open Chat"]["href"].endswith("/launch/onyx?path=/app")
    assert links["Open Agents"]["href"].endswith("/launch/onyx?path=/app/agents")
    assert links["Search Knowledge"]["href"].endswith("/launch/onyx?path=/app?chatMode=search")
    assert links["Onyx integration note"]["href"].endswith("/raw/docs/onyx-integration.md")


def test_runtime_policy_bundle_falls_back_when_overlay_is_missing() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        fallback_policy = root / "policies/runtime-policy-fallback.json"
        fallback_policy.parent.mkdir(parents=True, exist_ok=True)
        fallback_policy.write_text('{"tools":{"allowed_tools":["search"]}}', encoding="utf-8")

        bundle = load_runtime_policy_bundle(root)

        assert bundle.source == "fallback"
        assert bundle.relative_path == "policies/runtime-policy-fallback.json"
        assert bundle.document["tools"]["allowed_tools"] == ["search"]


def test_blocked_actions_section_includes_reason_codes() -> None:
    payload = build_control_plane_dashboard()
    blocked = next(section for section in payload["sections"] if section["id"] == "blocked-actions")

    records_block = next(block for block in blocked["blocks"] if block["type"] == "records")
    table_block = next(block for block in blocked["blocks"] if block["type"] == "table")

    assert records_block["items"]
    assert any(column["key"] == "reason" for column in table_block["columns"])
    assert any(column["key"] == "request" for column in table_block["columns"])
    assert any(row["reason"] for row in table_block["rows"])


def test_dashboard_surfaces_flagship_denied_onyx_proof_and_audit_source() -> None:
    payload = build_control_plane_dashboard()

    overview = next(section for section in payload["sections"] if section["id"] == "overview")
    audit = next(section for section in payload["sections"] if section["id"] == "audit-replay")

    overview_record_titles = {
        item["title"]
        for block in overview["blocks"]
        if block["type"] == "records"
        for item in block["items"]
    }
    audit_card_labels = {
        item["label"]
        for block in audit["blocks"]
        if block["type"] == "cards"
        for item in block["items"]
    }

    assert "Flagship denied Onyx handoff proof" in overview_record_titles
    assert "Audit record source" in audit_card_labels


def test_heavy_homepage_tables_are_reduced_to_summary_slices() -> None:
    payload = build_control_plane_dashboard()

    capped_sections = {"governed-requests", "blocked-actions", "upstream-posture", "asset-coverage", "evidence-integrity"}
    for section in payload["sections"]:
        if section["id"] not in capped_sections:
            continue
        for block in section["blocks"]:
            if block["type"] == "table":
                assert len(block["rows"]) <= 5
                assert block["collapsed"] is True
                assert block["summary"]


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


def test_upstream_usage_matrix_doc_exists() -> None:
    matrix = Path("docs/upstream-usage-matrix.md").read_text(encoding="utf-8")

    assert "Upstream Usage Matrix" in matrix
    assert "Onyx" in matrix
    assert "reference_only" in matrix


def test_live_mode_docs_exist() -> None:
    live_demo = Path("docs/live-vs-demo-matrix.md").read_text(encoding="utf-8")
    evidence_model = Path("docs/evidence-model.md").read_text(encoding="utf-8")
    proof_matrix = Path("docs/strict-live-proof-matrix.md").read_text(encoding="utf-8")
    reviewer_fast_path = Path("docs/reviewer-fast-path.md").read_text(encoding="utf-8")
    visual_proof = Path("docs/dashboard-visual-proof.md").read_text(encoding="utf-8")

    assert "live" in live_demo
    assert "demo" in live_demo
    assert "trace_id" in evidence_model
    assert "Acceptance criteria" in proof_matrix
    assert "strict live governed path" in proof_matrix.lower()
    assert "See A Pass" in reviewer_fast_path
    assert "Visual Previews" in visual_proof


def test_visual_proof_assets_exist() -> None:
    assert Path("docs/images/dashboard-live-pass.svg").is_file()
    assert Path("docs/images/dashboard-live-deny.svg").is_file()
