from __future__ import annotations

from telemetry.schemas import TelemetryEvent

from .schemas import LangfuseRecord

from telemetry.constants import INTERNAL_ONLY_EVENT_TYPES

TRACE_START_EVENTS = {"request.start"}
TRACE_END_EVENTS = {"request.end"}


def _sanitize_payload(payload: dict) -> dict:
    sanitized = {}
    for k, v in payload.items():
        # Keep internal-only details out of external observability export.
        if k.startswith("internal_"):
            continue
        sanitized[k] = v
    return sanitized


def map_to_langfuse_record(event: TelemetryEvent) -> LangfuseRecord:
    record_type = "trace" if event.event_type in TRACE_START_EVENTS | TRACE_END_EVENTS else "span"
    observation_id = f"{event.request_id}:{event.event_type}:{event.timestamp}"

    return LangfuseRecord(
        record_type=record_type,
        trace_id=event.trace_id,
        observation_id=observation_id,
        name=event.event_type,
        metadata={
            "request_id": event.request_id,
            "tenant_id": event.tenant_id,
            "severity": event.severity,
            "timestamp": event.timestamp,
            "payload": _sanitize_payload(event.payload),
        },
    )
