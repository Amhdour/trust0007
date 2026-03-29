from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import IdentityResolutionRequest, IdentityResolutionResult


class IdentityProvider(ABC):
    @abstractmethod
    def resolve(self, request: IdentityResolutionRequest) -> IdentityResolutionResult:
        """Resolve caller identity for a governed request."""
