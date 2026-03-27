import json
from pathlib import Path


def test_grafana_dashboard_spec_has_required_panels() -> None:
    spec = json.loads(Path("telemetry/dashboards/grafana/operational-dashboard-spec.json").read_text())
    panel_titles = {p["title"] for p in spec["panels"]}

    assert "Deny Rate" in panel_titles
    assert "Fallback Rate" in panel_titles
    assert "Tool Execution Attempts" in panel_titles
    assert "Retrieval Decision Mix" in panel_titles
    assert "Incident Signals" in panel_titles


def test_sample_events_jsonl_schema_shape() -> None:
    required = {"event_type", "trace_id", "request_id", "timestamp", "tenant_id", "severity", "payload"}
    lines = Path("telemetry/exports/sample_events.jsonl").read_text().strip().splitlines()
    assert len(lines) > 0

    for line in lines:
        obj = json.loads(line)
        assert set(obj.keys()) == required


def test_event_schema_required_fields_present() -> None:
    schema = json.loads(Path("telemetry/exports/event_schema.json").read_text())
    required = set(schema["required"])
    assert {"event_type", "trace_id", "request_id", "payload"}.issubset(required)
