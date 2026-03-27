from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import load_launch_report, load_sample_events, repo_root


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
    if raw_status == "conditional_pass":
        return "conditional"
    return "no-go"


def build_launch_gate_summary(root: Path | None = None) -> dict[str, Any]:
    resolved_root = repo_root(root)
    launch_gate_module = _load_launch_gate_module(resolved_root)
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
    }
