from pathlib import Path

from backend.activity_service.service import build_stack_health_snapshot


def test_stack_health_snapshot_distinguishes_core_and_optional_services() -> None:
    payload = build_stack_health_snapshot(
        Path("."),
        service_snapshot={
            "control_plane": {"state": "running", "status_text": "Up 2 minutes"},
            "db": {"state": "running", "status_text": "Up 2 minutes (healthy)"},
            "keycloak": {"state": "running", "status_text": "Up 2 minutes"},
            "opa": {"state": "running", "status_text": "Up 2 minutes"},
            "qdrant": {"state": "running", "status_text": "Up 2 minutes"},
            "vault": {"state": "running", "status_text": "Up 2 minutes"},
            "langfuse": {"state": "running", "status_text": "Up 2 minutes"},
            "envoy": {"state": "exited", "status_text": "Exited (255) 5 minutes ago"},
            "grafana": {"state": "running", "status_text": "Up 2 minutes"},
            "superset": {"state": "restarting", "status_text": "Restarting (1) 10 seconds ago"},
        },
    )

    assert payload["status"] == "warning"
    assert payload["counts"]["core_healthy"] == 7
    assert payload["counts"]["optional_healthy"] == 1
    assert payload["groups"][0]["title"] == "Core governed path"
    assert payload["groups"][1]["title"] == "Optional sidecars"
    assert any(item["service"] == "envoy" and item["status"] == "warning" for item in payload["groups"][1]["items"])


def test_stack_health_snapshot_reports_missing_core_services_as_critical() -> None:
    payload = build_stack_health_snapshot(Path("."), service_snapshot={})

    assert payload["status"] == "critical"
    assert payload["counts"]["core_healthy"] == 0
    assert any(item["service"] == "control_plane" and item["status"] == "critical" for item in payload["groups"][0]["items"])
