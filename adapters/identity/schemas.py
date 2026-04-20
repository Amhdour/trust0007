from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class IdentityResolutionRequest:
    authorization_header: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    cookies: dict[str, str] = field(default_factory=dict)
    requested_path: str = ""
    required_live_identity: bool = False
    fallback_user_id: str = ""
    fallback_tenant_id: str = ""
    fallback_roles: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class IdentityResolutionResult:
    authenticated: bool
    live: bool
    source: str
    user_id: str
    tenant_id: str
    roles: list[str] = field(default_factory=list)
    session_id: str = ""
    token_present: bool = False
    token_active: bool = False
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
