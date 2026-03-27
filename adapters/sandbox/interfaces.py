from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from .schemas import SandboxDecision, SandboxExecutionRequest


class SandboxPolicyEvaluator(ABC):
    @abstractmethod
    def evaluate(self, request: SandboxExecutionRequest) -> SandboxDecision:
        """Return allow/sandbox/deny decision and policy metadata."""


class SandboxExecutor(ABC):
    @abstractmethod
    def execute(self, request: SandboxExecutionRequest, mode: str) -> dict:
        """Execute request in selected mode ('allow' or 'sandbox')."""


class SandboxAuditSink(ABC):
    @abstractmethod
    def emit(self, event_type: str, payload: dict) -> None:
        """Emit audit/telemetry events for sandbox decisions."""


class InMemorySandboxAuditSink(SandboxAuditSink):
    def __init__(self) -> None:
        self.events: List[dict] = []

    def emit(self, event_type: str, payload: dict) -> None:
        self.events.append({"event_type": event_type, "payload": payload})
