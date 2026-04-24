from __future__ import annotations

from datetime import datetime, timezone

import backend.posture_service.service as posture_service_module
from backend.posture_service.service import build_control_plane_dashboard


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _healthy_live_summary() -> dict:
    timestamp = _now()
    return {
        "generated_at": timestamp,
        "trace_id": "trace-live-1",
        "request_id": "req-live-1",
        "session_id": "sess-live-1",
        "tenant_id": "tenant-a",
        "actor_id": "dashboard-user",
        "requested_path": "/app",
        "evidence_mode": "live",
        "handoff_allowed": True,
        "decision": True,
        "reasons": ["policy.allow"],
        "dependency_status": {
            "identity": {"authenticated": True, "live": True, "source": "keycloak_userinfo"},
            "policy": {"allow": True, "engine": "opa"},
            "retrieval": {"allow": True, "live_backend": True},
            "secret": {"mandatory": True, "fetched": True},
            "trace": {"complete": True},
        },
        "launch_gate": {
            "decision": "pass",
            "missing_evidence": [],
            "findings": [],
            "score_percent": 100,
        },
    }


def test_dashboard_reaches_go_for_healthy_live_configuration(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")
    monkeypatch.setattr(posture_service_module, "_event_feed", lambda root, governance_mode="": ([
        {"event_type": "policy.decision", "payload": {"allow": True}, "trace_id": "trace-live-1"},
        {"event_type": "retrieval.decision", "payload": {"decision": "allow"}, "trace_id": "trace-live-1"},
        {"event_type": "tool.decision", "payload": {"allowed": ["onyx"], "denied": []}, "trace_id": "trace-live-1"},
        {"event_type": "handoff.decision", "payload": {"allow": True}, "trace_id": "trace-live-1"},
    ], "Live governed flow artifacts", "overlays/myStarterKit/artifacts/events.jsonl"))
    monkeypatch.setattr(posture_service_module, "has_live_governed_flow_artifacts", lambda root: True)
    monkeypatch.setattr(
        posture_service_module,
        "validate_live_governed_flow_artifacts",
        lambda root: {"valid": True, "reasons": []},
    )
    monkeypatch.setattr(posture_service_module, "load_latest_governed_flow_summary", lambda root: _healthy_live_summary())
    monkeypatch.setattr(posture_service_module, "load_latest_governed_request_feed", lambda root: [{
        "timestamp": _now(),
        "trace_id": "trace-live-1",
        "session_id": "sess-live-1",
        "tenant_id": "tenant-a",
        "runtime_target": "onyx",
        "evidence_mode": "live",
        "identity_authenticated": True,
        "policy_allow": True,
        "retrieval_allow": True,
        "handoff_allowed": True,
        "reason_codes": ["policy.allow"],
        "artifact_refs": {"governed_flow_summary": "overlays/myStarterKit/artifacts/governed-flow-summary.json"},
    }])
    monkeypatch.setattr(posture_service_module, "load_latest_identity_evidence", lambda root: {"live": True, "authenticated": True, "captured_at": _now()})
    monkeypatch.setattr(posture_service_module, "load_latest_policy_evidence", lambda root: {"allow": True, "engine": "opa", "engine_reachable": True, "captured_at": _now()})
    monkeypatch.setattr(posture_service_module, "load_latest_retrieval_evidence", lambda root: {"allow": True, "live_backend": True, "backend_verified": True, "captured_at": _now()})
    monkeypatch.setattr(posture_service_module, "load_latest_secret_evidence", lambda root: {"required": True, "fetched": True, "captured_at": _now()})
    monkeypatch.setattr(posture_service_module, "load_latest_trace_correlation", lambda root: {"complete": True, "trace_id": "trace-live-1", "session_id": "sess-live-1"})
    monkeypatch.setattr(posture_service_module, "load_latest_audit_records", lambda root: [{"stage": "handoff", "trace_id": "trace-live-1"}])
    monkeypatch.setattr(posture_service_module, "build_launch_gate_summary", lambda root: {
        "status": "go",
        "readiness_score": 100,
        "control_coverage": "6/6",
        "findings": [],
        "residual_risks": [],
        "generated_at": _now(),
    })
    monkeypatch.setattr(posture_service_module, "build_activity_snapshot", lambda root, limit=12: {
            "generated_at": _now(),
        "entries": [
            {
                    "timestamp": _now(),
                "source": "onyx",
                "source_label": "Onyx Web",
                "event_type": "Onyx web request",
                "summary": "GET /app -> 200",
                "severity": "info",
                "status": "neutral",
            }
        ],
        "counts": {"combined": 1, "onyx": 1, "langfuse": 0, "alerts": 0, "langfuse_traces": 0, "langfuse_sessions": 0},
        "sources": {"onyx": "connected", "langfuse": "connected"},
        "poll_interval_ms": 5000,
        "source_href": "/api/control-plane/live-log?limit=50",
    })
    monkeypatch.setattr(
        posture_service_module,
        "_build_artifact_inventory",
        lambda root: ([], {"fresh": 9, "stale": 0, "expired": 0, "missing": 0}),
    )
    monkeypatch.setattr(posture_service_module, "load_latest_onyx_runtime_proof", lambda root: {
        "continuity": {"status": "path_activity_observed", "label": "Path activity seen", "detail": "Recent Onyx activity matched requested path."},
        "reachability": {"status": "local_and_public_ready", "label": "Runtime reachable", "detail": "Local and public targets responded."},
        "matched_activity": {"summary": "GET /app -> 200"},
        "requested_path": "/app",
    })

    payload = build_control_plane_dashboard()

    assert payload["readiness"]["decision"] == "GO"
    assert payload["readiness"]["evidence_mode"] == "live"
    assert payload["trust_proof"]["identity_proven"] is True
    assert payload["trust_proof"]["policy_proven"] is True
    assert payload["trust_proof"]["retrieval_proven"] is True
    assert "development defaults" not in payload["readiness"]["top_blocker"].lower()
    runtime_summary_items = {item["label"]: item for item in payload["command_center"]["runtime_summary"]["items"]}
    assert runtime_summary_items["Reachability"]["value"] == "Runtime reachable"
    assert runtime_summary_items["Continuity"]["value"] == "Path activity seen"
    onyx = next(item for item in payload["runtime_portfolio"]["runtimes"] if item["runtime_key"] == "onyx")
    assert onyx["status"] == "healthy"


def test_dashboard_remains_fail_closed_when_critical_proof_missing(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")
    summary = _healthy_live_summary()
    summary["dependency_status"]["retrieval"]["allow"] = False
    summary["dependency_status"]["retrieval"]["live_backend"] = False
    summary["launch_gate"] = {
        "decision": "no_go",
        "missing_evidence": ["retrieval.live_backend"],
        "findings": [{"control": "live_retrieval", "status": "fail", "summary": "Retrieval proof missing"}],
        "score_percent": 42,
    }
    monkeypatch.setattr(posture_service_module, "load_latest_governed_flow_summary", lambda root: summary)
    monkeypatch.setattr(posture_service_module, "build_launch_gate_summary", lambda root: {
        "status": "no-go",
        "readiness_score": 42,
        "control_coverage": "4/6",
        "findings": [{"control": "live_retrieval", "status": "fail", "summary": "Retrieval proof missing"}],
        "residual_risks": ["missing:retrieval.live_backend"],
        "generated_at": _now(),
    })
    monkeypatch.setattr(posture_service_module, "load_latest_retrieval_evidence", lambda root: {"allow": False, "live_backend": False})

    payload = build_control_plane_dashboard()

    assert payload["readiness"]["decision"] == "NO_GO"
    assert payload["trust_proof"]["retrieval_proven"] is False


def test_onyx_health_does_not_mask_critical_onyx_runtime_failure(monkeypatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")
    monkeypatch.setattr(posture_service_module, "load_latest_governed_flow_summary", lambda root: _healthy_live_summary())
    monkeypatch.setattr(posture_service_module, "build_launch_gate_summary", lambda root: {
        "status": "go",
        "readiness_score": 100,
        "control_coverage": "6/6",
        "findings": [],
        "residual_risks": [],
        "generated_at": _now(),
    })
    monkeypatch.setattr(posture_service_module, "load_latest_onyx_runtime_proof", lambda root: {
        "continuity": {"status": "no_runtime_activity", "label": "No recent activity", "detail": "No activity."},
        "reachability": {"status": "runtime_unreachable", "label": "Runtime not reachable", "detail": "Onyx down."},
        "requested_path": "/app",
    })

    payload = build_control_plane_dashboard()

    assert payload["readiness"]["decision"] == "NO_GO"
    assert any(blocker["label"].lower().startswith("onyx runtime") for blocker in payload["readiness"]["top_blockers"])
