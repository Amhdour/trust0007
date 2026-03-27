import json
from pathlib import Path

import pytest

from telemetry.model import EventModel, REQUIRED_EVENT_TYPES
from telemetry.sinks import InMemoryEventSink, JsonlEventSink


def test_required_event_types_supported() -> None:
    model = EventModel()
    emitted = []
    for event_type in REQUIRED_EVENT_TYPES:
        ev = model.create(
            event_type=event_type,
            trace_id="trace-1",
            request_id="req-1",
            payload={"k": "v"},
            tenant_id="tenant-a",
        )
        emitted.append(ev)

    assert len(emitted) == len(REQUIRED_EVENT_TYPES)
    assert all(ev.trace_id == "trace-1" for ev in emitted)
    assert all(ev.request_id == "req-1" for ev in emitted)


def test_trace_and_request_required() -> None:
    model = EventModel()
    with pytest.raises(ValueError):
        model.create("request.start", trace_id="", request_id="req-1", payload={})
    with pytest.raises(ValueError):
        model.create("request.start", trace_id="trace-1", request_id="", payload={})


def test_consistent_schema_and_jsonl_output(tmp_path: Path) -> None:
    model = EventModel()
    sink = JsonlEventSink(str(tmp_path / "events.jsonl"))
    mem = InMemoryEventSink()

    ev = model.create(
        event_type="policy.decision",
        trace_id="trace-123",
        request_id="req-123",
        payload={"allow": True},
        tenant_id="tenant-a",
        severity="info",
    )
    sink.emit(ev)
    mem.emit(ev)

    assert len(mem.events) == 1
    assert set(mem.events[0].to_dict().keys()) == {
        "event_type",
        "trace_id",
        "request_id",
        "timestamp",
        "tenant_id",
        "severity",
        "payload",
    }

    line = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()
    decoded = json.loads(line)
    assert decoded["event_type"] == "policy.decision"
    assert decoded["trace_id"] == "trace-123"
    assert decoded["request_id"] == "req-123"


def test_sensitive_payload_fields_are_redacted() -> None:
    model = EventModel()
    ev = model.create(
        event_type="policy.decision",
        trace_id="trace-redact",
        request_id="req-redact",
        payload={"token": "abc", "nested": {"password": "p"}, "ok": 1},
    )
    assert ev.payload["token"] == "[REDACTED]"
    assert ev.payload["nested"]["password"] == "[REDACTED]"
    assert ev.payload["ok"] == 1
