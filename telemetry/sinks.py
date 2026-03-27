from __future__ import annotations

import json
from pathlib import Path
from typing import List

from .schemas import TelemetryEvent


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: List[TelemetryEvent] = []

    def emit(self, event: TelemetryEvent) -> None:
        self.events.append(event)


class JsonlEventSink:
    """JSONL-friendly sink for local artifacts and future exports."""

    def __init__(self, output_path: str) -> None:
        self._path = Path(output_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event: TelemetryEvent) -> None:
        line = json.dumps(event.to_dict(), separators=(",", ":"), sort_keys=True)
        with self._path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
