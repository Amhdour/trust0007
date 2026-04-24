from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .schemas import AuditEvent, ToolActionRequest, ToolDecision


class ToolPolicyEvaluator(ABC):
    @abstractmethod
    def evaluate(self, request: ToolActionRequest) -> ToolDecision:
        """Evaluate governance policy for a tool action request."""


class ToolExecutor(ABC):
    @abstractmethod
    def execute(self, request: ToolActionRequest) -> dict:
        """Execute the requested tool action (business logic side)."""


class ToolAuditSink(ABC):
    @abstractmethod
    def emit(self, event: AuditEvent) -> None:
        """Emit governance audit event."""


class InMemoryAuditSink(ToolAuditSink):
    def __init__(self) -> None:
        self.events: List[AuditEvent] = []

    def emit(self, event: AuditEvent) -> None:
        self.events.append(event)
