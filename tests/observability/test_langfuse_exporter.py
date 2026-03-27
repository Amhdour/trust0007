from adapters.observability.langfuse.exporter import LangfuseEventExporter
from adapters.observability.langfuse.mapper import map_to_langfuse_record
from telemetry.model import EventModel


class StubLangfuseClient:
    def __init__(self) -> None:
        self.records = []

    def ingest(self, record: dict) -> None:
        self.records.append(record)


def test_maps_request_start_to_trace_record() -> None:
    model = EventModel()
    event = model.create(
        event_type="request.start",
        trace_id="trace-1",
        request_id="req-1",
        payload={"path": "/api"},
        tenant_id="tenant-a",
    )

    rec = map_to_langfuse_record(event)

    assert rec.record_type == "trace"
    assert rec.trace_id == "trace-1"
    assert rec.name == "request.start"


def test_maps_policy_decision_to_span_record_and_sanitizes_internal_fields() -> None:
    model = EventModel()
    event = model.create(
        event_type="policy.decision",
        trace_id="trace-2",
        request_id="req-2",
        payload={"allow": True, "internal_rule_id": "r-123"},
        tenant_id="tenant-a",
    )

    rec = map_to_langfuse_record(event)

    assert rec.record_type == "span"
    assert rec.metadata["payload"] == {"allow": True}


def test_exporter_excludes_internal_audit_events_by_default() -> None:
    model = EventModel()
    client = StubLangfuseClient()
    exporter = LangfuseEventExporter(client=client, include_internal=False)

    events = [
        model.create("request.start", "trace-1", "req-1", payload={}),
        model.create("deny.event", "trace-1", "req-1", payload={"reason": "blocked"}),
        model.create("request.end", "trace-1", "req-1", payload={"status": "ok"}),
    ]

    exported = exporter.export(events)

    assert len(exported) == 2
    assert [r.name for r in exported] == ["request.start", "request.end"]
    assert len(client.records) == 2


def test_exporter_can_include_internal_events_when_enabled() -> None:
    model = EventModel()
    client = StubLangfuseClient()
    exporter = LangfuseEventExporter(client=client, include_internal=True)

    events = [
        model.create("incident.signal", "trace-9", "req-9", payload={"signal": "anomaly"}),
    ]

    exported = exporter.export(events)

    assert len(exported) == 1
    assert exported[0].name == "incident.signal"
    assert client.records[0]["name"] == "incident.signal"
