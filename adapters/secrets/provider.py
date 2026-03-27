from __future__ import annotations

from .interfaces import VaultClient
from .schemas import SecretFetchRequest, SecretFetchResult


class VaultSecretsProvider:
    """Fetches secrets from Vault only when explicitly needed.

    Behavior is fail-safe: if Vault read fails, secret is not returned.
    """

    def __init__(self, client: VaultClient) -> None:
        self._client = client

    def fetch_if_needed(self, request: SecretFetchRequest) -> SecretFetchResult:
        if not request.needed:
            return SecretFetchResult(fetched=False, value=None, reason="not_needed")

        if not request.secret_path or not request.secret_key:
            return SecretFetchResult(fetched=False, value=None, reason="invalid_secret_reference")

        try:
            data = self._client.read_secret(request.secret_path)
        except Exception:
            return SecretFetchResult(fetched=False, value=None, reason="vault_unavailable")

        if request.secret_key not in data:
            return SecretFetchResult(fetched=False, value=None, reason="secret_key_missing")

        return SecretFetchResult(fetched=True, value=data[request.secret_key], reason="ok")
