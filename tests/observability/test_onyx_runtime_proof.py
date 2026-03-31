from pathlib import Path

from backend.activity_service.service import build_onyx_runtime_proof


def test_runtime_proof_marks_matching_requested_path_activity() -> None:
    snapshot = {
        "entries": [
            {
                "timestamp": "2026-03-31T10:00:00+00:00",
                "source": "onyx",
                "source_label": "Onyx Web",
                "event_type": "Onyx web request",
                "summary": "GET /app?chatMode=search -> 200",
                "severity": "info",
                "status": "neutral",
            }
        ],
        "sources": {"onyx": "connected"},
    }

    proof = build_onyx_runtime_proof(
        Path("."),
        requested_path="/app?chatMode=search",
        trace_id="trace-123",
        session_id="session-123",
        activity_snapshot=snapshot,
    )

    assert proof["requested_path_activity_observed"] is True
    assert proof["requested_path_activity_count"] == 1
    assert proof["continuity"]["status"] == "path_activity_observed"
    assert proof["matched_activity"]["summary"] == "GET /app?chatMode=search -> 200"


def test_runtime_proof_reports_when_no_recent_onyx_activity_exists() -> None:
    snapshot = {
        "entries": [],
        "sources": {"onyx": "docker socket unavailable"},
    }

    proof = build_onyx_runtime_proof(
        Path("."),
        requested_path="/app",
        trace_id="trace-456",
        session_id="session-456",
        activity_snapshot=snapshot,
    )

    assert proof["activity_observed"] is False
    assert proof["continuity"]["status"] == "no_runtime_activity"
    assert proof["activity_source_status"] == "docker socket unavailable"
