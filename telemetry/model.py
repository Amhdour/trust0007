from __future__ import annotations

from typing import Any, Dict, Iterable, List

from .constants import REQUIRED_EVENT_TYPES, SENSITIVE_KEYS
from .schemas import TelemetryEvent


def _sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if str(k).lower() in SENSITIVE_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = _sanitize_payload(v)
        return out
    if isinstance(value, list):
        return [_sanitize_payload(v) for v in value]
    return value


class EventModel:
    """Consistent telemetry/audit event creation and validation model."""

    def __init__(self, allowed_event_types: Iterable[str] = REQUIRED_EVENT_TYPES) -> None:
        self._allowed = set(allowed_event_types)

    def create(
        self,
        event_type: str,
        trace_id: str,
        request_id: str,
        payload: Dict,
        tenant_id: str = "",
        severity: str = "info",
    ) -> TelemetryEvent:
        if event_type not in self._allowed:
            raise ValueError(f"unknown event_type: {event_type}")
        if not trace_id:
            raise ValueError("trace_id is required")
        if not request_id:
            raise ValueError("request_id is required")

        return TelemetryEvent(
            event_type=event_type,
            trace_id=trace_id,
            request_id=request_id,
            tenant_id=tenant_id,
            severity=severity,
            payload=_sanitize_payload(payload),
        )

    def required_event_types(self) -> List[str]:
        return list(REQUIRED_EVENT_TYPES)
