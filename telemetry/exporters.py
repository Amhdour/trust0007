from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from .schemas import TelemetryEvent


class TelemetryExporter(ABC):
    @abstractmethod
    def export(self, events: Iterable[TelemetryEvent]) -> None:
        """Export events to an external backend."""


class LangfuseExporterStub(TelemetryExporter):
    """Placeholder exporter integration point for future Langfuse export."""

    def export(self, events: Iterable[TelemetryEvent]) -> None:
        # Integration stub: map TelemetryEvent -> Langfuse SDK spans/events.
        # Intentionally no-op in this phase.
        _ = list(events)
