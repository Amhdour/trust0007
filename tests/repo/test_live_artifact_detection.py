from __future__ import annotations

import json
from pathlib import Path

from backend.integration_adapter.repository import has_live_governed_flow_artifacts


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
        {"evidence_mode": "live", "generated_at": "2026-04-20T10:00:00+00:00"},
    )

    assert has_live_governed_flow_artifacts(tmp_path) is True
