from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from .schemas import RetrievalDocument, RetrievalRequest


class RetrievalPolicyEvaluator(ABC):
    @abstractmethod
    def evaluate(self, request: RetrievalRequest) -> dict:
        """Return policy response dict with fields: allow, mode, reasons."""


class RetrievalBackend(ABC):
    @abstractmethod
    def search(self, request: RetrievalRequest) -> Iterable[RetrievalDocument]:
        """Return candidate retrieval documents for the request."""


class RetrievalTelemetry(ABC):
    @abstractmethod
    def emit(self, event_type: str, payload: dict) -> None:
        """Emit retrieval security telemetry event."""


class InMemoryRetrievalTelemetry(RetrievalTelemetry):
    def __init__(self) -> None:
        self.events: List[dict] = []

    def emit(self, event_type: str, payload: dict) -> None:
        self.events.append({"event_type": event_type, "payload": payload})
