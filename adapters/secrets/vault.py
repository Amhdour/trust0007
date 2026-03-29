from __future__ import annotations

import json
from typing import Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .interfaces import VaultClient


class VaultHTTPClient(VaultClient):
    """Minimal Vault KV client for governed-flow secret lookups."""

    def __init__(self, base_url: str, token: str, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._timeout_seconds = timeout_seconds

    def read_secret(self, path: str) -> Dict[str, str]:
        request = Request(f"{self._base_url}/v1/{path.lstrip('/')}")
        request.add_header("X-Vault-Token", self._token)
        request.add_header("Accept", "application/json")
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("vault_unavailable") from exc

        data = payload.get("data", {})
        if isinstance(data, dict) and isinstance(data.get("data"), dict):
            return {str(key): str(value) for key, value in data["data"].items()}
        if isinstance(data, dict):
            return {str(key): str(value) for key, value in data.items()}
        return {}
