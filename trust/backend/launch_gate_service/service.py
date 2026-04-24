from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import (
    load_latest_governed_flow_launch_gate,
    load_latest_governed_flow_summary,
    load_launch_report,
    load_sample_events,
    repo_root,
)


def _load_launch_gate_module(root: Path):
    module_path = root / "launch-gate/evaluator.py"
    spec = importlib.util.spec_from_file_location("dashboard_launch_gate_evaluator", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load launch gate evaluator from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _map_status(raw_status: str) -> str:
    if raw_status == "pass":
        return "go"
    if raw_status in {"conditional_pass", "conditional_go"}:
        return "conditional"
    return "no-go"


def build_launch_gate_summary(root: Path | None = None) -> dict[str, Any]:
    resolved_root = repo_root(root)
    launch_gate_module = _load_launch_gate_module(resolved_root)
    governed_flow_summary = load_latest_governed_flow_summary(resolved_root)
    governed_launch_gate = load_latest_governed_flow_launch_gate(resolved_root)
    governance_mode = os.environ.get("CONTROL_PLANE_GOVERNANCE_MODE", "demo").strip().lower() or "demo"
    if governed_flow_summary and str(governed_flow_summary.get("evidence_mode", "")).lower() == "live":
        machine = governed_launch_gate.get("machine", {})
        live_findings = governed_flow_summary.get("launch_gate", {}).get("findings", [])
        return {
            "status": _map_status(str(machine.get("decision", governed_flow_summary.get("launch_gate", {}).get("decision", "no_go")))),
            "readiness_score": int(governed_flow_summary.get("launch_gate", {}).get("score_percent", 0)),
            "control_coverage": governed_flow_summary.get("launch_gate", {}).get("control_coverage", "0/0"),
            "missing_controls": list(machine.get("missing_evidence", [])),
            "failed_tests": 0,
            "residual_risks": list(governed_flow_summary.get("launch_gate", {}).get("residual_risks", [])),
            "decision_engine": machine,
            "findings": live_findings,
            "evidence_mode": str(governed_flow_summary.get("evidence_mode", "live")),
        }
    if governance_mode == "live":
        computed = launch_gate_module.evaluate_launch_gate(
            evidence={},
            controls=launch_gate_module.live_controls(secret_required=False, retrieval_required=False),
        )
        findings = [
            {
                "control": control.control_id,
                "status": "fail",
                "reason": "missing_live_evidence",
            }
            for control in launch_gate_module.live_controls(secret_required=False, retrieval_required=False)
        ]
        return {
            "status": _map_status(computed.decision),
            "readiness_score": 0,
            "control_coverage": f"{len(computed.controls_passed)}/{len(findings)}",
            "missing_controls": list(computed.missing_evidence),
            "failed_tests": 0,
            "residual_risks": ["live_evidence_missing_for_launch_gate"],
            "decision_engine": computed.to_machine_readable(),
            "findings": findings,
            "evidence_mode": "live",
        }

    events = load_sample_events(resolved_root)
    launch_report = load_launch_report(resolved_root)
    event_types = {str(event.get("event_type", "")) for event in events}
    evidence = {event_type: True for event_type in event_types if event_type}
    computed = launch_gate_module.evaluate_launch_gate(
        evidence=evidence,
        controls=launch_gate_module.default_controls(),
    )

    findings = launch_report.get("findings", [])
    pass_points = 0.0
    for finding in findings:
        status = finding.get("status")
        if status == "pass":
            pass_points += 1.0
        elif status == "conditional_pass":
            pass_points += 0.5
    total_findings = len(findings) or 1
    readiness_score = round((pass_points / total_findings) * 100)

    return {
        "status": _map_status(str(launch_report.get("status", "no_go"))),
        "readiness_score": readiness_score,
        "control_coverage": f"{len([f for f in findings if f.get('status') == 'pass'])}/{len(findings)}",
        "missing_controls": [
            finding.get("control", "")
            for finding in findings
            if finding.get("status") not in {"pass"}
        ],
        "failed_tests": 0,
        "residual_risks": launch_report.get("remediation", []),
        "decision_engine": computed.to_machine_readable(),
        "findings": findings,
        "evidence_mode": "demo",
    }
