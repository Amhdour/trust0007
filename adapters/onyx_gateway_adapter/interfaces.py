from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import (
    NormalizedRequest,
    PolicyDecision,
    RetrievalDecision,
    ToolDecision,
    TelemetryEvent,
)


class PolicyChecker(ABC):
    @abstractmethod
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        """Evaluate policy constraints for the request."""


class RetrievalChecker(ABC):
    @abstractmethod
    def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
        """Evaluate retrieval permission for the request."""


class ToolDecisionChecker(ABC):
    @abstractmethod
    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        """Evaluate tool-level allow/deny outcomes for the request."""


class TelemetryEmitter(ABC):
    @abstractmethod
    def emit(self, event: TelemetryEvent) -> None:
        """Emit telemetry for downstream audit/observability systems."""
