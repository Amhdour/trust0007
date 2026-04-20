from __future__ import annotations

import json
from pathlib import Path

from backend.integration_adapter.repository import has_live_governed_flow_artifacts, validate_live_governed_flow_artifacts


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_live_artifact_detection_rejects_demo_summary(tmp_path: Path) -> None:
    artifacts = tmp_path / "overlays/myStarterKit/artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "events.jsonl").write_text('{"event_type":"request.start"}\n', encoding="utf-8")
    for name in (
        "identity-evidence.json",
        "policy-evidence.json",
        "retrieval-evidence.json",
        "trace-correlation.json",
        "launch-gate-result.json",
        "onyx-runtime-proof.json",
    ):
        _write_json(artifacts / name, {"generated_at": "2026-04-20T10:00:00+00:00"})
    _write_json(
        artifacts / "governed-flow-summary.json",
        {"evidence_mode": "demo", "generated_at": "2026-04-20T10:00:00+00:00"},
    )

    assert has_live_governed_flow_artifacts(tmp_path) is False


def test_live_artifact_detection_accepts_current_live_summary(tmp_path: Path) -> None:
    artifacts = tmp_path / "overlays/myStarterKit/artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "events.jsonl").write_text('{"event_type":"request.start"}\n', encoding="utf-8")
    _write_json(artifacts / "identity-evidence.json", {"generated_at": "2026-04-20T10:00:00+00:00", "authenticated": True, "live": True})
    _write_json(artifacts / "policy-evidence.json", {"generated_at": "2026-04-20T10:00:00+00:00", "allow": True, "engine": "opa", "engine_reachable": True})
    _write_json(
        artifacts / "retrieval-evidence.json",
        {"generated_at": "2026-04-20T10:00:00+00:00", "allow": True, "live_backend": True, "backend_verified": True},
    )
    _write_json(artifacts / "trace-correlation.json", {"generated_at": "2026-04-20T10:00:00+00:00", "complete": True})
    _write_json(artifacts / "launch-gate-result.json", {"generated_at": "2026-04-20T10:00:00+00:00"})
    _write_json(
        artifacts / "onyx-runtime-proof.json",
        {
            "generated_at": "2026-04-20T10:00:00+00:00",
            "reachability": {"status": "local_and_public_ready"},
            "continuity": {"status": "path_activity_observed"},
        },
    )
    _write_json(
        artifacts / "governed-flow-summary.json",
        {"evidence_mode": "live", "generated_at": "2026-04-20T10:00:00+00:00"},
    )

    assert has_live_governed_flow_artifacts(tmp_path) is True


def test_live_artifact_detection_exposes_reason_codes_for_incomplete_live_proof(tmp_path: Path) -> None:
    artifacts = tmp_path / "overlays/myStarterKit/artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "events.jsonl").write_text('{"event_type":"request.start"}\n', encoding="utf-8")
    _write_json(artifacts / "identity-evidence.json", {"generated_at": "2026-04-20T10:00:00+00:00", "authenticated": True, "live": True})
    _write_json(artifacts / "policy-evidence.json", {"generated_at": "2026-04-20T10:00:00+00:00", "allow": True, "engine": "opa", "engine_reachable": True})
    _write_json(
        artifacts / "retrieval-evidence.json",
        {"generated_at": "2026-04-20T10:00:00+00:00", "allow": False, "live_backend": False, "backend_verified": False},
    )
    _write_json(artifacts / "trace-correlation.json", {"generated_at": "2026-04-20T10:00:00+00:00", "complete": True})
    _write_json(artifacts / "launch-gate-result.json", {"generated_at": "2026-04-20T10:00:00+00:00"})
    _write_json(
        artifacts / "onyx-runtime-proof.json",
        {
            "generated_at": "2026-04-20T10:00:00+00:00",
            "reachability": {"status": "runtime_unreachable"},
            "continuity": {"status": "no_runtime_activity"},
        },
    )
    _write_json(artifacts / "governed-flow-summary.json", {"evidence_mode": "live", "generated_at": "2026-04-20T10:00:00+00:00"})

    validation = validate_live_governed_flow_artifacts(tmp_path)
    assert validation["valid"] is False
    assert "retrieval_not_live_verified_allow" in validation["reasons"]
    assert "onyx_runtime_unreachable" in validation["reasons"]
