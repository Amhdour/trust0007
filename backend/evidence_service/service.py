from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import load_reviewer_bundle, repo_root


def _raw_link(path: str) -> str:
    return f"/raw/{path}"


def build_evidence_pack_summary(root: Path | None = None) -> dict[str, Any]:
    resolved_root = repo_root(root)
    reviewer_bundle = load_reviewer_bundle(resolved_root)
    blocked = reviewer_bundle.get("blocked_attack_summary", {})
    readiness = reviewer_bundle.get("readiness_verdict", {})

    return {
        "bundle_generated_at": reviewer_bundle.get("generated_at", ""),
        "blocked_attacks": blocked.get("blocked_attacks", []),
        "blocked_count": blocked.get("blocked_count", 0),
        "readiness_status": readiness.get("status", "unknown"),
        "exports": [
            {
                "label": "Reviewer Evidence Bundle",
                "href": _raw_link("overlays/myStarterKit/artifacts/evidence/reviewer/reviewer_evidence_bundle.json"),
                "description": "Consolidated reviewer-ready trust evidence.",
            },
            {
                "label": "Launch Readiness Report",
                "href": _raw_link("overlays/myStarterKit/artifacts/logs/launch_gate/starter_launch_readiness_report.json"),
                "description": "myStarterKit readiness findings and remediation guidance.",
            },
            {
                "label": "Dashboard Ingestion Sample",
                "href": _raw_link("overlays/myStarterKit/artifacts/dashboard/dashboard_ingestion.json"),
                "description": "Export shape used for dashboard-level ingestion and replay views.",
            },
            {
                "label": "Grafana Operational Spec",
                "href": _raw_link("telemetry/dashboards/grafana/operational-dashboard-spec.json"),
                "description": "Operational observability drill-down contract.",
            },
        ],
    }
