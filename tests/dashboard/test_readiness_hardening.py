from __future__ import annotations

from datetime import datetime, timedelta, timezone

import backend.posture_service.service as posture_service_module
from backend.posture_service.service import build_control_plane_dashboard


def _ts(hours_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat()


def _configure_common(monkeypatch, *, evidence_mode: str = "live", retrieval_live: bool = True, runtime_ready: bool = True) -> None:
    monkeypatch.setattr(posture_service_module, "has_live_governed_flow_artifacts", lambda root: evidence_mode == "live")
    monkeypatch.setattr(
        posture_service_module,
        "validate_live_governed_flow_artifacts",
        lambda root: {"valid": evidence_mode == "live", "reasons": []},
    )
    monkeypatch.setattr(posture_service_module, "_event_feed", lambda root: ([
        {"event_type": "policy.decision", "payload": {"allow": True}, "trace_id": "trace-1"},
        {"event_type": "handoff.decision", "payload": {"allow": True}, "trace_id": "trace-1"},
    ], "Governed events", "overlays/myStarterKit/artifacts/events.jsonl"))
    monkeypatch.setattr(posture_service_module, "load_latest_governed_flow_summary", lambda root: {
        "generated_at": _ts(),
        "trace_id": "trace-1",
        "session_id": "sess-1",
        "tenant_id": "tenant-a",
        "requested_path": "/app",
        "evidence_mode": evidence_mode,
        "handoff_allowed": True,
        "dependency_status": {
            "identity": {"authenticated": True, "live": evidence_mode == "live", "source": "keycloak_userinfo"},
            "policy": {"allow": True, "engine": "opa"},
            "retrieval": {"allow": retrieval_live, "live_backend": retrieval_live},
            "secret": {"mandatory": True, "fetched": True},
            "trace": {"complete": True},
        },
        "launch_gate": {"decision": "pass", "missing_evidence": [], "findings": [], "score_percent": 96},
    })
    monkeypatch.setattr(posture_service_module, "load_latest_governed_request_feed", lambda root: [{
        "timestamp": _ts(),
        "trace_id": "trace-1",
        "session_id": "sess-1",
        "tenant_id": "tenant-a",
        "runtime_target": "onyx",
        "evidence_mode": evidence_mode,
        "identity_authenticated": True,
        "policy_allow": True,
        "retrieval_allow": retrieval_live,
        "handoff_allowed": True,
        "reason_codes": ["policy.allow"],
    }])
    monkeypatch.setattr(posture_service_module, "load_latest_identity_evidence", lambda root: {"live": evidence_mode == "live", "authenticated": True, "captured_at": _ts()})
    monkeypatch.setattr(posture_service_module, "load_latest_policy_evidence", lambda root: {"allow": True, "engine": "opa", "engine_reachable": True, "captured_at": _ts()})
    monkeypatch.setattr(posture_service_module, "load_latest_retrieval_evidence", lambda root: {"allow": retrieval_live, "live_backend": retrieval_live, "backend_verified": retrieval_live, "captured_at": _ts()})
    monkeypatch.setattr(posture_service_module, "load_latest_secret_evidence", lambda root: {"required": True, "fetched": True, "captured_at": _ts()})
    monkeypatch.setattr(posture_service_module, "load_latest_trace_correlation", lambda root: {"complete": True, "trace_id": "trace-1", "session_id": "sess-1", "timestamp": _ts()})
    monkeypatch.setattr(posture_service_module, "load_latest_audit_records", lambda root: [{"stage": "handoff", "trace_id": "trace-1"}])
    monkeypatch.setattr(posture_service_module, "build_launch_gate_summary", lambda root: {
        "status": "go" if retrieval_live else "no-go",
        "readiness_score": 96 if retrieval_live else 45,
        "control_coverage": "6/6" if retrieval_live else "4/6",
        "findings": [],
        "residual_risks": [],
        "generated_at": _ts(),
    })
    monkeypatch.setattr(posture_service_module, "build_activity_snapshot", lambda root, limit=12: {"entries": [], "counts": {}, "sources": {"onyx": "connected"}})
    monkeypatch.setattr(posture_service_module, "load_latest_onyx_runtime_proof", lambda root: {
        "continuity": {"status": "path_activity_observed" if runtime_ready else "no_runtime_activity", "label": "Path activity seen" if runtime_ready else "No activity", "detail": "continuity"},
        "reachability": {"status": "local_and_public_ready" if runtime_ready else "runtime_unreachable", "label": "Runtime reachable" if runtime_ready else "Runtime unreachable", "detail": "reachability"},
        "matched_activity": {"summary": "GET /app -> 200" if runtime_ready else "none"},
        "requested_path": "/app",
    })


def test_control_status_semantics_and_demo_provenance(monkeypatch) -> None:
    _configure_common(monkeypatch, evidence_mode="demo", retrieval_live=False, runtime_ready=False)
    payload = build_control_plane_dashboard()

    controls = {item["control"]: item["status"] for item in payload["trust_proof"]["controls"]}
    assert controls["Identity"] == "DEMO_ONLY"
    assert controls["Retrieval"] in {"MISSING_PROOF", "DEMO_ONLY"}
    assert controls["Evidence provenance"] == "DEMO_ONLY"
    assert payload["readiness"]["decision"] == "NO_GO"


def test_onyx_unreachable_is_top_level_blocker(monkeypatch) -> None:
    _configure_common(monkeypatch, evidence_mode="live", retrieval_live=True, runtime_ready=False)
    payload = build_control_plane_dashboard()

    reasons = [item["label"] for item in payload["readiness"]["top_blockers"]]
    assert any("Onyx runtime" in reason for reason in reasons)
    assert payload["readiness"]["decision"] == "NO_GO"
    runtime_status = {item["runtime_key"]: item["status"] for item in payload["runtime_portfolio"]["runtimes"]}
    assert runtime_status["onyx"] in {"warning", "critical"}
    assert runtime_status["dify"] == "healthy"


def test_healthy_live_configuration_can_reach_go(monkeypatch) -> None:
    _configure_common(monkeypatch, evidence_mode="live", retrieval_live=True, runtime_ready=True)
    payload = build_control_plane_dashboard()

    assert payload["readiness"]["decision"] == "GO"
    assert payload["readiness"]["readiness_score"] >= 85
    assert payload["trust_proof"]["freshness_sla"]["fresh_hours"] == posture_service_module.DEFAULT_FRESH_HOURS


def test_freshness_sla_classification_is_explicit() -> None:
    assert posture_service_module._format_age_bucket(_ts(hours_ago=1))[1] == "fresh"
    assert posture_service_module._format_age_bucket(_ts(hours_ago=posture_service_module.DEFAULT_FRESH_HOURS + 1))[1] == "stale"
    assert posture_service_module._format_age_bucket(_ts(hours_ago=posture_service_module.DEFAULT_STALE_HOURS + 1))[1] == "expired"
