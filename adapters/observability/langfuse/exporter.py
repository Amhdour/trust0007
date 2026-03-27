from __future__ import annotations

from typing import Iterable, List, Protocol

from telemetry.schemas import TelemetryEvent

from .mapper import INTERNAL_ONLY_EVENT_TYPES, map_to_langfuse_record
from .schemas import LangfuseRecord


class LangfuseClientLike(Protocol):
    def ingest(self, record: dict) -> None:
        ...


class LangfuseEventExporter:
    """Exports telemetry events as Langfuse-friendly trace/span records.

    This exporter intentionally keeps internal audit-only event types out of
    external export by default.
    """

    def __init__(self, client: LangfuseClientLike, include_internal: bool = False) -> None:
        self._client = client
        self._include_internal = include_internal

    def export(self, events: Iterable[TelemetryEvent]) -> List[LangfuseRecord]:
        exported: List[LangfuseRecord] = []
        for event in events:
            if not self._include_internal and event.event_type in INTERNAL_ONLY_EVENT_TYPES:
                continue
            record = map_to_langfuse_record(event)
            self._client.ingest(
                {
                    "type": record.record_type,
                    "trace_id": record.trace_id,
                    "observation_id": record.observation_id,
                    "name": record.name,
                    "metadata": record.metadata,
                }
            )
            exported.append(record)
        return exported
