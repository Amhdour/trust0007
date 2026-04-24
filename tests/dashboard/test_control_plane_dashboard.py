import json
from pathlib import Path
import tempfile

import backend.posture_service.service as posture_service_module
from backend.integration_adapter.repository import (
    list_upstream_component_paths,
    load_dashboard_contract,
    load_runtime_policy_bundle,
    load_upstream_usage_inventory,
)
from backend.api_gateway.server import _resolve_static_path
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
    assert 'id="hero-eyebrow"' in html
    assert 'id="homepage-panels-root"' in html
    assert 'id="trust-scorecard-root"' in html
    assert 'id="secondary-context-root"' in html
    assert 'id="live-runtime-link"' in html
    assert 'id="view-evidence-link"' in html
    assert "Open Onyx" in html
    assert "Open Onyx Agent" in html
    assert "/launch/onyx?path=/app&mode=live&view=embedded" in html
    assert "/launch/onyx/agent?mode=live&view=embedded" in html
    assert 'id="tab-strip"' in html
    assert 'id="dashboard-root"' in html
    assert "payload.title" in js
    assert "payload.readiness" in js
    assert "payload.trust_proof" in js
    assert "payload.security_posture" in js
    assert "renderHomepagePanels" in js
    assert "renderTrustScorecard" in js
    assert "renderSecondaryContext" in js
    assert "renderDecisionHero" in js
    assert "renderDrilldownTabs" in js
    assert "ACTIVE_DRILLDOWN_SECTION_IDS" in js
    assert "AI Trust & Security Control Plane" in js
    assert "Safety checks" in js
    assert "Security snapshot" in js
    assert "readiness.decision" in js
    assert "trustProof.identity_proven" in js
    assert "security.blocked_actions_count" in js
    assert "/api/control-plane/overview" in js


def test_client_overview_assets_exist_and_reuse_real_dashboard_signals() -> None:
    html = Path("frontend/main-dashboard/client-overview.html").read_text(encoding="utf-8")
    js = Path("frontend/main-dashboard/client-overview.js").read_text(encoding="utf-8")
    css = Path("frontend/main-dashboard/client-overview.css").read_text(encoding="utf-8")

    assert 'id="traffic-summary-root"' in html
    assert 'id="process-root"' in html
    assert 'id="examples-root"' in html
    assert "/api/control-plane/overview" in js
    assert "/raw/evidence/reviewer/inspectable-live-runtime/allowed-flow.json" in js
    assert "/raw/evidence/reviewer/inspectable-live-runtime/denied-flow.json" in js
    assert "evidence_freshness" in js
    assert "reviewer_evidence_bundle" in js
    assert ".comparison-grid" in css
    assert ".gauge" in css


def test_static_router_supports_client_overview_entrypoint() -> None:
    assert _resolve_static_path("/client-overview").name == "client-overview.html"


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

    assert payload["mode_banner"]["label"] in {"LIVE GOVERNED MODE", "GOVERNED DEMO MODE", "DEMO FALLBACK MODE"}
    assert payload["mode_banner"]["status_label"] in {"Live proof", "Review only"}
    assert payload["mode_banner"]["disclosure_label"]
    if payload["mode_banner"]["label"] != "LIVE GOVERNED MODE":
        assert payload["mode_banner"]["status"] == "neutral"
    chip_labels = {chip["display_label"] for chip in payload["mode_banner"]["chips"]}
    assert {
        "Proof source",
        "Decision shown",
        "Baseline posture",
    } <= chip_labels
    assert ("Latest run posture" in chip_labels) or ("Fresh governed run" in chip_labels)
    assert payload["mode_banner"]["display_detail"].startswith("Source:")
    assert "Latest decision:" in payload["mode_banner"]["display_detail"]
    assert "Baseline posture:" in payload["mode_banner"]["display_detail"]
    assert len(payload["command_center"]["cards"]) >= 4
    assert {card["id"] for card in payload["command_center"]["cards"]} >= {
        "readiness",
        "latest_handoff",
        "top_failing_control",
        "evidence_freshness",
    }
    assert payload["command_center"]["latest_request"]["title"]
    assert payload["command_center"]["flagship_proof"]["title"] == "Denied governed runtime handoff (Onyx example)"
    assert payload["command_center"]["incident_banner"]["visible"] is True
    assert payload["command_center"]["incident_banner"]["status"] in {"healthy", "warning", "critical"}
    assert payload["command_center"]["incident_banner"]["title"]
    assert payload["command_center"]["incident_banner"]["facts"]
    assert len(payload["command_center"]["risk_strip"]["items"]) == 4
    assert payload["command_center"]["risk_strip"]["items"][0]["trend"]["label"]
    assert payload["command_center"]["risk_strip"]["items"][1]["trend"]["label"]
    assert any(item["label"] == "Last good run" for item in payload["command_center"]["risk_strip"]["items"])
    assert payload["command_center"]["cards"][0]["meta_badges"]
    assert payload["command_center"]["next_action"]["title"]
    assert payload["command_center"]["next_action"]["primary_action"]["label"]
    assert payload["command_center"]["next_action"]["steps"]
    assert payload["command_center"]["next_action"]["change"]["label"]
    assert len(payload["command_center"]["walkthrough"]) == 4
    assert payload["command_center"]["walkthrough"][0]["label"] == "Start with posture"
    assert payload["command_center"]["example_compare"]["approved"]["title"]
    assert payload["command_center"]["example_compare"]["blocked"]["title"]
    assert payload["command_center"]["freshness_bar"]["items"][0]["label"] == "Updated"
    assert payload["command_center"]["presentation_summary"]["export_text"]
    assert len(payload["command_center"]["proof_pipeline"]["steps"]) == 6
    assert payload["mode_banner"]["consequences"]
    assert len(payload["audience_paths"]) == 2
    assert len(payload["operator_briefing"]) == 5
    assert len(payload["kpis"]) >= 10
    assert payload["readiness_panel"]["status_label"] in {"GO", "CONDITIONAL", "NO-GO"}
    assert payload["data_mode"]["label"]
    assert payload["readiness"]["decision"] in {"GO", "CONDITIONAL_GO", "NO_GO"}
    assert isinstance(payload["readiness"]["readiness_score"], int)
    assert payload["readiness"]["latest_handoff_decision"] in {"ALLOW", "DENY"}
    assert set(payload["trust_proof"]) >= {
        "identity_proven",
        "policy_proven",
        "retrieval_proven",
        "tool_governance_proven",
        "audit_proven",
        "evidence_freshness",
        "launch_report_available",
        "governed_flow_summary_available",
        "reviewer_bundle_available",
    }
    assert set(payload["security_posture"]) >= {
        "denied_events_count",
        "blocked_actions_count",
        "confirmation_required_count",
        "retrieval_denials_count",
        "tool_denials_count",
        "failing_controls",
        "residual_risk_count",
    }
    assert set(payload["onyx_security_readiness"]) >= {
        "provider",
        "system",
        "component_type",
        "environment",
        "generated_at",
        "overall_status",
        "overall_score",
        "risk_summary",
        "capabilities",
        "launch_gate_decision",
        "message",
    }


def test_dashboard_payload_includes_runtime_summary_and_stack_health() -> None:
    payload = build_control_plane_dashboard()

    runtime_summary = payload["command_center"]["runtime_summary"]
    stack_health = payload["stack_health"]

    assert runtime_summary["title"] == "Governed runtime status (Onyx spotlight)"
    assert runtime_summary["actions"]
    assert any(item["label"] == "Reachability" for item in runtime_summary["items"])
    assert any(item["label"] == "Continuity" for item in runtime_summary["items"])
    assert stack_health["label"]
    assert stack_health["groups"]
    assert any(group["title"] == "Core governed path" for group in stack_health["groups"])
    assert stack_health["action"]["href"] == "/raw/scripts/check-project-health.sh"
    assert payload["runtime_portfolio"]["runtimes"]
    assert {item["id"] for item in payload["runtime_portfolio"]["runtimes"]} >= {"onyx", "onyx-agent"}
    runtime_portfolio = {item["runtime_key"]: item for item in payload["runtime_portfolio"]["runtimes"]}
    assert runtime_portfolio["onyx"]["runtime_class"] == "rag"
    assert runtime_portfolio["onyx_agent"]["runtime_class"] == "tool_governance"
    assert runtime_portfolio["onyx"]["launch_route"]
    assert runtime_portfolio["onyx"]["launch_href"]
    assert runtime_portfolio["onyx"]["evidence_href"]
    assert runtime_portfolio["onyx"]["primary_controls"]


def test_runtime_portfolio_exposes_runtime_specific_launch_and_governance_fields() -> None:
    payload = build_control_plane_dashboard()
    runtime_portfolio = {item["runtime_key"]: item for item in payload["runtime_portfolio"]["runtimes"]}

    onyx = runtime_portfolio["onyx"]
    onyx_agent = runtime_portfolio["onyx_agent"]

    for runtime in (onyx, onyx_agent):
        assert runtime["launch_route"].startswith("/launch/")
        assert runtime["launch_href"].endswith(runtime["launch_route"])
        assert runtime["workspace_href"].startswith("http://") or runtime["workspace_href"].startswith("https://")
        assert runtime["evidence_href"]
        assert runtime["governance_focus"]
        assert runtime["primary_controls"]

    assert onyx["launch_route"].startswith("/launch/onyx?path=/app")
    assert onyx_agent["launch_route"].startswith("/launch/onyx/agent")
    assert any("Retrieval" in control for control in onyx["primary_controls"])
    assert any("MCP" in control or "Tool" in control for control in onyx_agent["primary_controls"])


def test_frontend_runtime_portfolio_has_dual_runtime_fallback_and_link_binding_logic() -> None:
    js = Path("frontend/main-dashboard/app.js").read_text(encoding="utf-8")

    assert "function defaultRuntimePortfolio()" in js
    assert 'runtime_key: "onyx"' in js
    assert 'runtime_key: "onyx"' in js
    assert 'launch_href: "/launch/onyx?path=/app&mode=live&view=embedded"' in js
    assert 'launch_href: "/launch/onyx/agent?mode=live&view=embedded"' in js
    assert "runtimeByKey.get(\"onyx\")?.launch_href" in js
    assert "runtimeByKey.get(\"onyx\")?.launch_href" in js
    assert "liveRuntimeLink.setAttribute(\"href\", onyxChatLaunchHref)" in js
    assert "liveOnyxAgentLink.setAttribute(\"href\", onyxAgentLaunchHref)" in js


def test_fallback_mode_banner_uses_review_only_copy(monkeypatch) -> None:
    monkeypatch.setattr(
        posture_service_module,
        "_event_feed",
        lambda resolved_root: ([], "Sample or fallback events", "telemetry/exports/sample_events.jsonl"),
    )
    monkeypatch.setattr(posture_service_module, "load_latest_governed_flow_summary", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_identity_evidence", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_policy_evidence", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_retrieval_evidence", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_secret_evidence", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_trace_correlation", lambda resolved_root: {})

    payload = build_control_plane_dashboard()
    mode_banner = payload["mode_banner"]
    chip_lookup = {chip["display_label"]: chip["display_value"] for chip in mode_banner["chips"]}

    assert mode_banner["label"] == "DEMO FALLBACK MODE"
    assert mode_banner["status"] == "neutral"
    assert mode_banner["status_label"] == "Review only"
    assert mode_banner["display_label"] == "Review mode: sample proof"
    assert mode_banner["display_summary"] == (
        "This page is using sample or fallback artifacts for review. It is not claiming a fresh governed live run."
    )
    assert mode_banner["display_detail"].startswith("Source: sample or fallback artifacts.")
    assert chip_lookup["Proof source"] == "Sample review artifacts"
    assert chip_lookup["Decision shown"] in {"Allowed", "Blocked"}
    assert chip_lookup["Fresh governed run"] == "Not available"
    assert chip_lookup["Baseline posture"]
    assert "Technical trace" not in chip_lookup
    assert mode_banner["disclosure_label"] == "What this mode means"


def test_live_mode_without_bootstrapped_artifacts_does_not_fall_back_to_demo(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")
    monkeypatch.setattr(
        posture_service_module,
        "_event_feed",
        lambda resolved_root: ([], "Live governed artifacts missing; governed bootstrap has not completed", "overlays/myStarterKit/artifacts/events.jsonl"),
    )
    monkeypatch.setattr(posture_service_module, "load_latest_governed_flow_summary", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_identity_evidence", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_policy_evidence", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_retrieval_evidence", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_secret_evidence", lambda resolved_root: {})
    monkeypatch.setattr(posture_service_module, "load_latest_trace_correlation", lambda resolved_root: {})

    payload = build_control_plane_dashboard()
    mode_banner = payload["mode_banner"]
    chip_lookup = {chip["display_label"]: chip["display_value"] for chip in mode_banner["chips"]}

    assert mode_banner["label"] == "LIVE GOVERNED MODE"
    assert mode_banner["status"] == "warning"
    assert mode_banner["status_label"] == "Live proof"
    assert chip_lookup["Proof source"] == "Live mode awaiting governed artifacts"
    assert "bootstrap path" in mode_banner["display_summary"].lower()


def test_event_feed_refuses_sample_fallback_in_live_mode(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")
    monkeypatch.setattr(posture_service_module, "has_live_governed_flow_artifacts", lambda root: False)
    monkeypatch.setattr(
        posture_service_module,
        "validate_live_governed_flow_artifacts",
        lambda root: {"valid": False, "reasons": ["missing"]},
    )
    monkeypatch.setattr(posture_service_module, "load_sample_events", lambda root: [{"event_type": "sample"}])

    events, label, path = posture_service_module._event_feed(tmp_path)

    assert events == []
    assert "missing" in label.lower()
    assert path == "overlays/myStarterKit/artifacts/events.jsonl"


def test_dashboard_tabs_and_sections_have_reviewer_operator_grouping() -> None:
    payload = build_control_plane_dashboard()

    tab_groups = {tab["group_label"] for tab in payload["tabs"]}
    section_groups = {section["group_label"] for section in payload["sections"]}

    assert {"Homepage Decision", "Evidence Drill-Down"} <= tab_groups
    assert {"Homepage Decision", "Evidence Drill-Down"} <= section_groups


def test_dashboard_sections_match_slim_contract_ids() -> None:
    payload = build_control_plane_dashboard()
    section_ids = {section["id"] for section in payload["sections"]}
    assert section_ids == {
        "launch-gate",
        "entry-points",
        "onyx-agent-access",
        "policy-enforcement",
        "retrieval-boundaries",
        "tool-mcp-governance",
        "audit-replay",
    }


def test_dashboard_regression_homepage_does_not_require_legacy_section_ids(monkeypatch) -> None:
    minimal_contract = {
        "title": "Onyx Readiness Dashboard",
        "subtitle": "Decision surface",
        "hero_copy": "Decision-first",
        "landing_steps": [],
        "repo_description_suggestion": "Decision-first",
        "tabs": [
            {"id": "launch-gate", "label": "Readiness", "group": "reviewer", "group_label": "Homepage Decision"},
            {"id": "audit-replay", "label": "Audit Replay", "group": "operator", "group_label": "Evidence Drill-Down"},
        ],
        "sections": [
            {"id": "launch-gate", "title": "Onyx Readiness", "description": "Readiness detail", "group": "reviewer", "group_label": "Homepage Decision"},
            {"id": "audit-replay", "title": "Audit and Replay", "description": "Audit detail", "group": "operator", "group_label": "Evidence Drill-Down"},
        ],
    }
    monkeypatch.setattr(posture_service_module, "load_dashboard_contract", lambda resolved_root: minimal_contract)

    payload = build_control_plane_dashboard()
    ids = [section["id"] for section in payload["sections"]]
    assert ids == ["launch-gate", "audit-replay"]
    assert "readiness" in payload
    assert "trust_proof" in payload
    assert "security_posture" in payload


def test_upstream_usage_inventory_is_machine_readable() -> None:
    inventory = load_upstream_usage_inventory()

    assert inventory["inventory_version"] == 3
    assert inventory["components"]
    assert "inventory_covers_all_upstreams" in inventory["audit"]
    assert "lock_consistent" in inventory["audit"]
    assert inventory["audit"]["envoy_platform_only_locked"] is True
    assert inventory["audit"]["fingerprints_complete"] is True
    assert set(inventory["upstream_paths"]) == set(list_upstream_component_paths())
    assert inventory["tracking_model"]["lock_path"] == "evidence/upstream.lock.json"
    assert "upstream/superset" in inventory["tracking_model"]["opt_in_checkout_paths"]
    assert inventory["tracking_model"]["total_source_count"] == len(list_upstream_component_paths())
    assert inventory["tracking_model"]["fingerprinted_source_count"] == len(list_upstream_component_paths())
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
    assert "onyx-runtime-proof.json" in source_hrefs["Onyx runtime proof"]
    assert "onyx-agent-runtime-proof.json" in source_hrefs["Onyx Agent runtime proof"]

    onyx_runtime = next(section for section in payload["sections"] if section["id"] == "entry-points")
    link_items = []
    for block in onyx_runtime["blocks"]:
        if block["type"] == "links":
            link_items.extend(block["items"])

    links = {item["label"]: item for item in link_items}
    assert links["Open Onyx Workspace"]["href"].endswith("/launch/onyx?path=/app&mode=live&view=embedded")
    assert links["Open Chat"]["href"].endswith("/launch/onyx?path=/app")
    assert links["Open Agents"]["href"].endswith("/launch/onyx?path=/app/agents")
    assert links["Search Knowledge"]["href"].endswith("/launch/onyx?path=/app?chatMode=search")
    assert links["Open Onyx Agent Apps"]["href"].endswith("/launch/onyx/agent")
    assert links["Open Onyx Agent Workspace"]["href"].endswith("/launch/onyx/agent?mode=live&view=embedded")
    assert "onyx-runtime-proof.json" in links["Latest Onyx runtime proof"]["href"]
    assert "onyx-agent-runtime-proof.json" in links["Latest Onyx Agent runtime proof"]["href"]
    assert links["Onyx integration note"]["href"].endswith("/raw/docs/onyx-integration.md")


def test_dashboard_entry_points_include_runtime_proof_signals() -> None:
    payload = build_control_plane_dashboard()
    onyx_runtime = next(section for section in payload["sections"] if section["id"] == "entry-points")
    cards_block = next(block for block in onyx_runtime["blocks"] if block["type"] == "cards")

    cards = {item["label"]: item for item in cards_block["items"]}

    assert cards["Runtime continuity"]["id"] == "onyx_runtime_continuity"
    assert cards["Runtime continuity"]["value"]
    assert "onyx-runtime-proof.json" in cards["Runtime continuity"]["href"]
    assert cards["Runtime readiness"]["id"] == "onyx_runtime_readiness"
    assert cards["Runtime readiness"]["value"]
    assert "onyx-runtime-proof.json" in cards["Runtime readiness"]["href"]


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


def test_security_posture_surfaces_denial_and_block_counts() -> None:
    payload = build_control_plane_dashboard()
    posture = payload["security_posture"]

    assert posture["denied_events_count"] >= 0
    assert posture["blocked_actions_count"] >= 0
    assert posture["confirmation_required_count"] >= 0
    assert posture["retrieval_denials_count"] >= 0
    assert posture["tool_denials_count"] >= 0
    assert posture["residual_risk_count"] >= 0
    assert isinstance(posture["failing_controls"], list)


def test_dashboard_surfaces_flagship_denied_onyx_proof_and_audit_source() -> None:
    payload = build_control_plane_dashboard()

    audit = next(section for section in payload["sections"] if section["id"] == "audit-replay")
    audit_card_labels = {
        item["label"]
        for block in audit["blocks"]
        if block["type"] == "cards"
        for item in block["items"]
    }

    assert payload["command_center"]["flagship_proof"]["title"] == "Denied governed runtime handoff (Onyx example)"
    assert payload["security_posture"]["blocked_actions_count"] >= 0
    assert "Audit record source" in audit_card_labels


def test_removed_legacy_sections_are_not_emitted_on_homepage() -> None:
    payload = build_control_plane_dashboard()
    section_ids = {section["id"] for section in payload["sections"]}
    assert {
        "overview",
        "governed-requests",
        "blocked-actions",
        "upstream-posture",
        "identity-session",
        "secret-access",
        "trace-correlation",
        "asset-coverage",
        "evidence-integrity",
    }.isdisjoint(section_ids)


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
    client_overview = Path("docs/client-overview.md").read_text(encoding="utf-8")

    assert "live" in live_demo
    assert "demo" in live_demo
    assert "trace_id" in evidence_model
    assert "Acceptance criteria" in proof_matrix
    assert "strict live governed path" in proof_matrix.lower()
    assert "See A Pass" in reviewer_fast_path
    assert "Visual Previews" in visual_proof
    assert "/client-overview" in client_overview
    assert "technical dashboard" in client_overview.lower()


def test_visual_proof_assets_exist() -> None:
    assert Path("docs/images/dashboard-live-pass.svg").is_file()
    assert Path("docs/images/dashboard-live-deny.svg").is_file()
