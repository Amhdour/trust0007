from pathlib import Path

from backend.activity_service.service import build_onyx_workspace_activity


def test_workspace_activity_groups_direct_correlated_and_other_runtime_events() -> None:
    snapshot = {
        "poll_interval_ms": 5000,
        "entries": [
            {
                "timestamp": "2026-04-01T10:03:00+00:00",
                "source": "onyx",
                "source_label": "Onyx Web",
                "event_type": "Onyx web request",
                "summary": "GET /app -> 200",
                "severity": "info",
                "status": "neutral",
            },
            {
                "timestamp": "2026-04-01T10:02:00+00:00",
                "source": "langfuse",
                "source_label": "Langfuse Trace",
                "event_type": "Langfuse trace",
                "summary": "Trace captured: governed workspace",
                "severity": "info",
                "status": "neutral",
                "trace_id": "trace-123",
                "request_id": "session-123",
            },
            {
                "timestamp": "2026-04-01T10:01:00+00:00",
                "source": "onyx",
                "source_label": "Onyx API",
                "event_type": "Onyx API request",
                "summary": "GET /api/tool -> 200",
                "severity": "info",
                "status": "neutral",
            },
            {
                "timestamp": "2026-04-01T10:00:00+00:00",
                "source": "langfuse",
                "source_label": "Langfuse Session",
                "event_type": "Langfuse session",
                "summary": "Session recorded in Langfuse: session-1",
                "severity": "info",
                "status": "neutral",
                "request_id": "session-123",
            },
        ],
        "sources": {"onyx": "connected", "langfuse": "connected"},
    }

    payload = build_onyx_workspace_activity(
        Path("."),
        requested_path="/app",
        trace_id="trace-123",
        session_id="session-123",
        limit=4,
        activity_snapshot=snapshot,
    )

    assert payload["summary"]["status"] == "healthy"
    assert payload["counts"]["current_surface"] == 1
    assert payload["counts"]["correlated"] == 2
    assert payload["counts"]["other_runtime"] == 1
    assert payload["groups"][0]["entries"][0]["scope"] == "current_surface"
    assert payload["groups"][1]["entries"][0]["trace_match"] is True
    assert payload["groups"][2]["entries"][0]["summary"] == "GET /api/tool -> 200"


def test_workspace_activity_reports_when_no_runtime_visibility_exists() -> None:
    payload = build_onyx_workspace_activity(
        Path("."),
        requested_path="/app",
        trace_id="trace-456",
        session_id="session-456",
        limit=4,
        activity_snapshot={"entries": [], "sources": {"onyx": "docker socket unavailable", "langfuse": "Langfuse API keys not configured"}},
    )

    assert payload["summary"]["status"] == "critical"
    assert payload["counts"]["current_surface"] == 0
    assert payload["counts"]["correlated"] == 0
    assert payload["counts"]["other_runtime"] == 0
    assert payload["sources"]["onyx"] == "docker socket unavailable"
