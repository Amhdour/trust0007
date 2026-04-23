from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.runtime_repair.api import diagnose_lane, execute_lane, plan_lane
from backend.runtime_repair.diagnostics.base import DiagnosticContext, RuntimeRouteConfig
from backend.runtime_repair.diagnostics.onyx import OnyxDiagnosticAdapter
from backend.runtime_repair.diagnostics.onyx import OnyxDiagnosticAdapter
from backend.runtime_repair.enums import FailureCategory, RemediationStatus, RepairMode, RuntimeLane, Severity
from backend.runtime_repair.models import DiagnosticFinding, new_id
from backend.runtime_repair.orchestrator import GovernedRuntimeRepairOrchestrator
from backend.runtime_repair.policies import RepairPolicyEngine
from backend.runtime_repair.remediations.actions import action_catalog


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(root: Path, relative: str, payload: dict) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_jsonl(root: Path, relative: str, records: list[dict]) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")


def _seed_artifacts(
    root: Path,
    *,
    lane: str = "onyx",
    runtime_proof: dict | None = None,
    tool: dict | None = None,
    retrieval: dict | None = None,
    identity: dict | None = None,
    launch_decision: str = "pass",
) -> None:
    ts = _now()
    _write_json(root, "overlays/myStarterKit/artifacts/identity-evidence.json", identity or {"authenticated": True, "timestamp": ts, "tenant_id": "tenant-a", "actor_id": "actor-a"})
    _write_json(root, "overlays/myStarterKit/artifacts/policy-evidence.json", {"allow": True, "engine_reachable": True, "timestamp": ts, "reason_codes": ["policy.allow"]})
    _write_json(root, "overlays/myStarterKit/artifacts/retrieval-evidence.json", retrieval or {"allow": True, "timestamp": ts, "source": "qdrant", "reason_codes": ["retrieval.allow"]})
    _write_json(root, "overlays/myStarterKit/artifacts/secret-evidence.json", {"required": True, "fetched": True, "backend_available": True, "timestamp": ts})
    _write_json(root, "overlays/myStarterKit/artifacts/tool-evidence.json", tool or {"mcp_governed": lane == "onyx", "denied_tools": [], "allowed_tools": ["onyx"], "timestamp": ts})
    _write_json(root, "overlays/myStarterKit/artifacts/trace-correlation.json", {"complete": True, "timestamp": ts, "trace_id": "trace-a"})
    _write_json(root, "overlays/myStarterKit/artifacts/launch-gate-result.json", {"generated_at": ts, "machine": {"decision": launch_decision, "blockers": [], "missing_evidence": []}})
    _write_json(root, "overlays/myStarterKit/artifacts/governed-flow-summary.json", {"timestamp": ts, "runtime_target": lane, "trace_id": "trace-a", "tenant_id": "tenant-a", "actor_id": "actor-a", "evidence_mode": "live"})
    _write_jsonl(root, "overlays/myStarterKit/artifacts/events.jsonl", [{"timestamp": ts, "event_type": "handoff", "payload": {"runtime_target": lane}}])
    _write_jsonl(root, "overlays/myStarterKit/artifacts/audit-records.jsonl", [{"timestamp": ts, "event_type": "handoff", "runtime_id": lane, "tenant_id": "tenant-a"}])
    proof = runtime_proof or {
        "generated_at": ts,
        "requested_path": "/app" if lane == "onyx" else "/apps",
        "handoff_allowed": True,
        "evidence_mode": "live",
        "continuity": {"status": "path_activity_observed", "label": "Path activity seen"},
    }
    _write_json(root, f"overlays/myStarterKit/artifacts/{lane}-runtime-proof.json", proof)


def _ctx(root: Path, prober=None) -> DiagnosticContext:
    return DiagnosticContext(
        tenant_id="tenant-a",
        actor_id="actor-a",
        correlation_id="corr-a",
        root=root,
        environment="dev",
        prober=prober,
    )


def test_domain_model_serialization_uses_explicit_enums() -> None:
    finding = DiagnosticFinding(
        finding_id=new_id("finding"),
        lane=RuntimeLane.ONYX,
        tenant_id="tenant-a",
        runtime_id="onyx",
        severity=Severity.HIGH,
        category=FailureCategory.CONTINUITY,
        title="Continuity missing",
        detail="Proof missing after governed handoff.",
        evidence_used=["proof.json"],
        correlation_id="corr-a",
        actor_id="actor-a",
        decision_id="decision-a",
    )

    payload = finding.to_dict()

    assert payload["lane"] == "onyx"
    assert payload["severity"] == "HIGH"
    assert payload["category"] == "CONTINUITY"
    assert payload["remediation_status"] == "not_planned"


def test_onyx_diagnostic_distinguishes_local_reachable_public_unreachable_and_missing_continuity(tmp_path: Path) -> None:
    _seed_artifacts(
        tmp_path,
        runtime_proof={
            "generated_at": _now(),
            "requested_path": "/app",
            "handoff_allowed": True,
            "evidence_mode": "live",
            "continuity": {"status": "no_runtime_activity", "label": "No activity"},
        },
    )
    adapter = OnyxDiagnosticAdapter(
        RuntimeRouteConfig(
            lane=RuntimeLane.ONYX,
            runtime_id="onyx",
            label="Onyx",
            default_path="/app",
            local_base_url="http://local",
            public_base_url="https://public",
            expected_routes=["/app"],
            proof_path="overlays/myStarterKit/artifacts/onyx-runtime-proof.json",
        )
    )

    report = adapter.diagnose(_ctx(tmp_path, prober=lambda url: url.startswith("http://local")))
    reason_codes = {reason for finding in report.findings for reason in finding.reason_codes}

    assert "reachability.local_ok_public_unreachable" in reason_codes
    assert "continuity.missing_after_allowed_handoff" in reason_codes


def test_onyx_diagnostic_classifies_tool_mcp_policy_violations(tmp_path: Path) -> None:
    _seed_artifacts(
        tmp_path,
        lane="onyx",
        tool={"mcp_governed": True, "denied_tools": ["shell.exec"], "timestamp": _now()},
    )
    adapter = OnyxDiagnosticAdapter(
        RuntimeRouteConfig(
            lane=RuntimeLane.ONYX,
            runtime_id="onyx",
            label="Onyx Agent",
            default_path="/apps",
            local_base_url="http://local",
            public_base_url="http://local",
            expected_routes=["/apps"],
            proof_path="overlays/myStarterKit/artifacts/onyx-agent-runtime-proof.json",
        )
    )

    report = adapter.diagnose(_ctx(tmp_path, prober=lambda url: True))

    assert any(finding.category == FailureCategory.TOOLS_MCP for finding in report.findings)
    assert any("tools_mcp.denied:shell.exec" in finding.reason_codes for finding in report.findings)


def test_repair_policy_allows_safe_reprobe_and_blocks_prod_restart_without_approval() -> None:
    engine = RepairPolicyEngine({"repair_actions": {**RepairPolicyEngine({}).repair_policy}})
    actions = {action.action_id: action for action in action_catalog(RuntimeLane.ONYX)}

    reprobe = engine.evaluate_action(actions["reprobe_routes"], tenant_id="tenant-a", actor_id="actor-a", environment="production")
    restart = engine.evaluate_action(actions["restart_local_service"], tenant_id="tenant-a", actor_id="actor-a", environment="production")
    rotate = engine.evaluate_action(actions["rotate_nonhuman_runtime_credential"], tenant_id="tenant-a", actor_id="actor-a", environment="staging")

    assert reprobe.allow
    assert not restart.allow
    assert "repair.environment_not_allowed:production" in restart.reason_codes
    assert not rotate.allow
    assert any("approval_required" in reason for reason in rotate.reason_codes)


def test_orchestrator_dry_run_records_no_executed_actions(tmp_path: Path) -> None:
    _seed_artifacts(
        tmp_path,
        runtime_proof={
            "generated_at": _now(),
            "requested_path": "/app",
            "handoff_allowed": True,
            "evidence_mode": "live",
            "continuity": {"status": "no_runtime_activity"},
        },
    )
    run = GovernedRuntimeRepairOrchestrator(tmp_path).run(
        RuntimeLane.ONYX,
        mode=RepairMode.DRY_RUN,
        tenant_id="tenant-a",
        actor_id="actor-a",
        prober=lambda url: False,
    )

    assert run.status.value in {"dry_run", "blocked"}
    assert all(result.status != RemediationStatus.EXECUTED for result in run.execution_results)
    assert (tmp_path / "overlays/myStarterKit/artifacts/runtime-repair/repair-runs.json").exists()


def test_quarantine_action_recomputes_lane_as_incident_mode(tmp_path: Path) -> None:
    _seed_artifacts(
        tmp_path,
        runtime_proof={
            "generated_at": _now(),
            "requested_path": "/app",
            "handoff_allowed": True,
            "evidence_mode": "live",
            "continuity": {"status": "no_runtime_activity"},
        },
    )
    run = GovernedRuntimeRepairOrchestrator(tmp_path).run(
        RuntimeLane.ONYX,
        mode=RepairMode.EXECUTE_ACTION,
        tenant_id="tenant-a",
        actor_id="actor-a",
        approved_actions=["quarantine_lane"],
        action_id="quarantine_lane",
        prober=lambda url: False,
    )

    assert any(result.action_id == "quarantine_lane" and result.status == RemediationStatus.EXECUTED for result in run.execution_results)
    assert run.readiness_after["state"] == "INCIDENT_MODE"


def test_launch_gate_contradiction_is_surfaced_as_repair_finding(tmp_path: Path) -> None:
    _seed_artifacts(
        tmp_path,
        identity={"authenticated": False, "timestamp": _now(), "reason_codes": ["identity.missing"]},
        launch_decision="pass",
    )

    report = GovernedRuntimeRepairOrchestrator(tmp_path).diagnose(
        RuntimeLane.ONYX,
        tenant_id="tenant-a",
        actor_id="actor-a",
        prober=lambda url: True,
    )

    assert any(
        finding.category == FailureCategory.LAUNCH_GATE and "launch_gate.contradicts_readiness" in finding.reason_codes
        for finding in report.findings
    )


def test_repair_api_contracts_return_summary_correlation_and_readiness_impact(tmp_path: Path) -> None:
    _seed_artifacts(tmp_path)

    diagnose = diagnose_lane(tmp_path, RuntimeLane.ONYX, {"tenant_id": "tenant-a", "actor_id": "actor-a"})
    plan = plan_lane(tmp_path, RuntimeLane.ONYX, {"tenant_id": "tenant-a", "actor_id": "actor-a"})
    execute = execute_lane(tmp_path, RuntimeLane.ONYX, {"tenant_id": "tenant-a", "actor_id": "actor-a", "dry_run": True})

    for payload in (diagnose, plan, execute):
        assert payload["lane"] == "onyx"
        assert payload["correlation_id"]
        assert payload["summary"]
        assert "readiness_impact" in payload
        assert "audit_refs" in payload
        assert "evidence_refs" in payload
