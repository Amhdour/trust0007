"""Minimal Vault secrets-access adapter for local development."""

from .provider import VaultSecretsProvider
from .schemas import SecretFetchRequest, SecretFetchResult

__all__ = ["VaultSecretsProvider", "SecretFetchRequest", "SecretFetchResult"]
