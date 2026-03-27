from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict


class VaultClient(ABC):
    @abstractmethod
    def read_secret(self, path: str) -> Dict[str, str]:
        """Return key/value data for a secret path."""
