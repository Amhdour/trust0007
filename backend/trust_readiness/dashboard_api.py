from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import load_runtime_policy_bundle, repo_root
from .evidence import load_evidence_bundle
from .incidents import active_incident_controls, load_incident_controls
from .policy_engine import PolicyAsCodeEngine
from .readiness import compute_fleet_readiness, compute_runtime_readiness
from .runtime_registry import runtime_descriptor, runtime_descriptors


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _policy_engine(root: Path | None = None) -> PolicyAsCodeEngine:
    resolved_root = repo_root(root)
    policy_path = resolved_root / "policies/control-plane/default-governance-policy.json"
    if policy_path.exists():
        return PolicyAsCodeEngine.from_file(policy_path)
    bundle = load_runtime_policy_bundle(resolved_root)
    from .policy_engine import MachineReadablePolicy

    return PolicyAsCodeEngine(
        MachineReadablePolicy(
            policy_id="runtime-policy-bundle",
            version=str(bundle.document.get("policy_metadata", {}).get("bundle_version", "runtime")),
            document=bundle.document,
            source_path=bundle.relative_path,
        )
    )


def build_fleet_overview(root: Path | None = None) -> dict[str, Any]:
    readiness = compute_fleet_readiness(root)
    runtimes = {runtime.runtime_id: runtime for runtime in runtime_descriptors()}
    return {
        "page": "Fleet Overview",
        "generated_at": _now(),
        "runtimes": [
            {
                **runtimes[item.runtime_id].to_dict(),
                "readiness": item.to_dict(),
                "active_incidents": active_incident_controls(root, runtime_id=item.runtime_id),
            }
            for item in readiness
        ],
        "summary": {
            "runtime_count": len(readiness),
            "ready_count": sum(1 for item in readiness if item.launch_allowed),
            "blocked_count": sum(1 for item in readiness if not item.launch_allowed),
            "fail_closed_default": True,
        },
    }


def build_runtime_readiness_page(root: Path | None = None, *, runtime_id: str = "") -> dict[str, Any]:
    if runtime_id:
        readiness = [compute_runtime_readiness(root, runtime_id=runtime_id)]
    else:
        readiness = compute_fleet_readiness(root)
    return {
        "page": "Runtime Readiness",
        "generated_at": _now(),
        "states": [item.to_dict() for item in readiness],
        "state_model": [
            "READY",
            "READY_WITH_EXCEPTIONS",
            "BLOCKED",
            "DEGRADED",
            "UNDER_REVIEW",
            "INCIDENT_MODE",
        ],
        "contract": "Every state is computed from evidence signals, launch gates, and active incident controls.",
    }


def build_retrieval_boundary_posture(root: Path | None = None) -> dict[str, Any]:
    policy = load_runtime_policy_bundle(repo_root(root)).document
    bundle = load_evidence_bundle(root)
    retrieval_policy = policy.get("retrieval", {})
    return {
        "page": "Retrieval Boundary Posture",
        "generated_at": _now(),
        "runtime_id": "onyx",
        "tenant_allowed_sources": retrieval_policy.get("tenant_allowed_sources", {}),
        "source_trust_labels": retrieval_policy.get("source_trust_labels", {}),
        "required_provenance_fields": retrieval_policy.get("required_provenance_fields", []),
        "latest_decision": {
            "allow": bool(bundle.retrieval.get("allow", False)),
            "source": bundle.retrieval.get("source", ""),
            "backend": bundle.retrieval.get("backend", ""),
            "filters": bundle.retrieval.get("filters", {}),
            "reason_codes": bundle.retrieval.get("reason_codes", []),
            "result_count": bundle.retrieval.get("result_count", 0),
        },
        "controls": [
            "tenant/source boundary",
            "source classification",
            "purpose binding",
            "trust label filtering",
            "provenance requirements",
            "quarantine filtering",
        ],
    }


def build_tool_mcp_authorization_posture(root: Path | None = None) -> dict[str, Any]:
    policy = load_runtime_policy_bundle(repo_root(root)).document
    bundle = load_evidence_bundle(root)
    tools = policy.get("tools", {})
    dify_controls = policy.get("runtime_controls", {}).get("dify", {})
    return {
        "page": "Tool/MCP Authorization Posture",
        "generated_at": _now(),
        "runtime_id": "dify",
        "mcp_allowed_servers": dify_controls.get("mcp_allowed_servers", []),
        "allowed_tools": tools.get("allowed_tools", []),
        "approval_required_tools": sorted(set(tools.get("confirmation_required_tools", [])) | set(dify_controls.get("approval_required_tools", []))),
        "approval_required_actions": dify_controls.get("approval_required_actions", []),
        "latest_decision": {
            "requested_tools": bundle.tool.get("requested_tools", []),
            "allowed_tools": bundle.tool.get("allowed_tools", []),
            "denied_tools": bundle.tool.get("denied_tools", []),
            "mcp_server": bundle.tool.get("mcp_server", ""),
            "mcp_governed": bundle.tool.get("mcp_governed", False),
            "reason_codes": bundle.tool.get("reason_codes", []),
        },
        "risk_classes": {
            "low": "read-only or bounded local actions",
            "medium": "state-changing internal actions",
            "high": "external write, destructive, privileged, or irreversible actions",
        },
    }


def build_launch_gates_page(root: Path | None = None) -> dict[str, Any]:
    bundle = load_evidence_bundle(root)
    engine = _policy_engine(root)
    freshness = {}
    for name, path in bundle.evidence_refs().items():
        doc = getattr(bundle, name, {}) if hasattr(bundle, name) else {}
        if isinstance(doc, dict):
            freshness[name] = "fresh" if doc else "stale"
    trace = engine.evaluate_launch_gate(
        {
            "freshness": freshness,
            "telemetry_healthy": bool(bundle.events),
            "audit_healthy": bool(bundle.audit_records) and bool(bundle.trace.get("complete", False)),
            "human_approval_required": False,
            "human_approved": False,
        }
    )
    return {
        "page": "Launch Gates",
        "generated_at": _now(),
        "latest_gate": bundle.launch_gate,
        "policy_trace": trace.to_dict(),
        "runtime_states": [item.to_dict() for item in compute_fleet_readiness(root)],
    }


def build_evidence_audit_page(root: Path | None = None) -> dict[str, Any]:
    bundle = load_evidence_bundle(root)
    return {
        "page": "Evidence & Audit",
        "generated_at": _now(),
        "bundle": bundle.to_bundle(),
        "audit": {
            "append_only_design": True,
            "record_count": len(bundle.audit_records),
            "path": bundle.evidence_refs()["audit"],
            "latest_records": bundle.audit_records[-25:],
        },
        "timeline": bundle.timeline()[:100],
    }


def build_incidents_page(root: Path | None = None) -> dict[str, Any]:
    controls = load_incident_controls(root)
    return {
        "page": "Incidents",
        "generated_at": _now(),
        "active_controls": active_incident_controls(root),
        "all_controls": controls,
        "supported_actions": [
            "emergency_revoke",
            "runtime_quarantine",
            "tool_disable",
            "retrieval_isolation",
            "break_glass",
        ],
        "degraded_mode": {
            "fail_closed": True,
            "behavior": "Mandatory unhealthy dependencies block launch; optional or non-runtime signals produce review/degraded states.",
        },
    }


def build_exceptions_waivers_page(root: Path | None = None) -> dict[str, Any]:
    bundle = load_evidence_bundle(root)
    return {
        "page": "Exceptions / Waivers",
        "generated_at": _now(),
        "waivers": bundle.exceptions_waivers,
        "requirements": [
            "tenant_id",
            "runtime_id",
            "control_id",
            "approver_id",
            "reason",
            "expires_at",
            "compensating_control",
        ],
        "policy": "Waivers may explain READY_WITH_EXCEPTIONS but do not override incident mode or hard launch blockers.",
    }
