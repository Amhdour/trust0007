from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.trust_readiness.incidents import append_incident_control
from backend.trust_readiness.readiness import compute_runtime_readiness


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_ready_artifacts(root: Path, *, runtime_id: str = "onyx") -> Path:
    artifacts = root / "overlays/myStarterKit/artifacts"
    now = datetime.now(timezone.utc).isoformat()
    common = {
        "timestamp": now,
        "trace_id": "flow-1",
        "request_id": "req-1",
        "session_id": "session-1",
        "actor_id": "user-1",
        "tenant_id": "tenant-dashboard",
    }
    _write(artifacts / "identity-evidence.json", {**common, "authenticated": True, "live": True, "source": "keycloak_userinfo"})
    _write(artifacts / "policy-evidence.json", {**common, "allow": True, "engine": "opa", "engine_reachable": True})
    _write(
        artifacts / "retrieval-evidence.json",
        {**common, "allow": True, "mode": "allow", "source": "qdrant", "backend_verified": True, "result_count": 1},
    )
    _write(artifacts / "secret-evidence.json", {**common, "required": False, "fetched": False, "backend_available": True})
    _write(
        artifacts / "tool-evidence.json",
        {
            **common,
            "runtime_target": runtime_id,
            "requested_tools": [runtime_id],
            "allowed_tools": [runtime_id],
            "denied_tools": [],
            "mcp_governance_required": runtime_id == "onyx",
            "mcp_governed": runtime_id != "onyx" or True,
            "mcp_server": "mcp_server.dashboard_control_plane" if runtime_id == "onyx" else "",
        },
    )
    _write(artifacts / "trace-correlation.json", {**common, "complete": True})
    _write(
        artifacts / "launch-gate-result.json",
        {"machine": {"decision": "pass", "score": 10, "max_score": 10, "blockers": [], "missing_evidence": []}},
    )
    _write(artifacts / "governed-flow-summary.json", {**common, "runtime_target": runtime_id, "handoff_allowed": True})
    (artifacts / "events.jsonl").write_text(
        json.dumps({"timestamp": now, "event_type": "request.start", "trace_id": "flow-1", "request_id": "req-1"}) + "\n",
        encoding="utf-8",
    )
    (artifacts / "audit-records.jsonl").write_text(
        json.dumps(
            {
                "timestamp": now,
                "trace_id": "flow-1",
                "request_id": "req-1",
                "runtime_target": runtime_id,
                "stage": "handoff",
                "action": f"{runtime_id}.handoff",
                "tenant_id": "tenant-dashboard",
                "actor_id": "user-1",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return artifacts


def test_runtime_readiness_computes_ready_with_exceptions_for_optional_eval_gap(tmp_path: Path) -> None:
    _seed_ready_artifacts(tmp_path)

    readiness = compute_runtime_readiness(tmp_path, runtime_id="onyx")

    assert readiness.launch_allowed is True
    assert readiness.state.value == "READY_WITH_EXCEPTIONS"
    assert readiness.score == 100
    assert {signal.signal_id for signal in readiness.signals} >= {"identity_health", "retrieval_boundary", "launch_gate"}


def test_active_incident_control_forces_incident_mode(tmp_path: Path) -> None:
    _seed_ready_artifacts(tmp_path, runtime_id="onyx")
    append_incident_control(
        root=tmp_path,
        runtime_id="onyx",
        control_type="tool_disable",
        tenant_id="tenant-dashboard",
        actor_id="secops-1",
        reason="Disable external write tools during investigation.",
        tool_id="email.send",
    )

    readiness = compute_runtime_readiness(tmp_path, runtime_id="onyx")

    assert readiness.state.value == "INCIDENT_MODE"
    assert readiness.launch_allowed is False
    assert "tool_disable" in readiness.blockers
