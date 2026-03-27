from __future__ import annotations

from typing import List

from .interfaces import TelemetryEmitter
from .schemas import TelemetryEvent


class InMemoryTelemetryEmitter(TelemetryEmitter):
    """Development test helper that stores emitted events in memory."""

    def __init__(self) -> None:
        self.events: List[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        self.events.append(event)
