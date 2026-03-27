from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SecretFetchRequest:
    request_id: str
    tenant_id: str
    needed: bool
    secret_path: str
    secret_key: str


@dataclass(frozen=True)
class SecretFetchResult:
    fetched: bool
    value: Optional[str]
    reason: str
