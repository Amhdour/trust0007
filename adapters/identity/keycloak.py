from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .interfaces import IdentityProvider
from .schemas import IdentityResolutionRequest, IdentityResolutionResult


def _extract_bearer_token(authorization_header: str, cookies: dict[str, str]) -> str:
    header = authorization_header.strip()
    if header.lower().startswith("bearer "):
        return header.split(" ", 1)[1].strip()
    return str(cookies.get("kc_access_token", "")).strip()


def _roles_from_claims(claims: dict[str, Any]) -> list[str]:
    roles: list[str] = []
    realm_access = claims.get("realm_access", {})
    if isinstance(realm_access, dict):
        for role in realm_access.get("roles", []) or []:
            if role and role not in roles:
                roles.append(str(role))
    resource_access = claims.get("resource_access", {})
    if isinstance(resource_access, dict):
        for resource_claims in resource_access.values():
            if not isinstance(resource_claims, dict):
                continue
            for role in resource_claims.get("roles", []) or []:
                if role and role not in roles:
                    roles.append(str(role))
    tenant_roles = claims.get("tenant_roles", [])
    if isinstance(tenant_roles, list):
        for role in tenant_roles:
            if role and role not in roles:
                roles.append(str(role))
    return roles


def _tenant_from_claims(claims: dict[str, Any]) -> str:
    for key in ("tenant_id", "tenant", "tenantId"):
        if claims.get(key):
            return str(claims[key])
    attributes = claims.get("attributes", {})
    if isinstance(attributes, dict):
        for key in ("tenant_id", "tenant"):
            if attributes.get(key):
                return str(attributes[key])
    return ""


class KeycloakIdentityProvider(IdentityProvider):
    """Resolve identity by calling a Keycloak-compatible userinfo endpoint."""

    def __init__(self, userinfo_url: str, timeout_seconds: float = 5.0) -> None:
        self._userinfo_url = userinfo_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def resolve(self, request: IdentityResolutionRequest) -> IdentityResolutionResult:
        token = _extract_bearer_token(request.authorization_header, request.cookies)
        token_present = bool(token)
        if not token_present:
            if request.required_live_identity:
                return IdentityResolutionResult(
                    authenticated=False,
                    live=False,
                    source="missing_token",
                    user_id="",
                    tenant_id="",
                    roles=[],
                    token_present=False,
                    token_active=False,
                    reason="identity.missing_bearer_token",
                    metadata={"requested_path": request.requested_path},
                )
            return IdentityResolutionResult(
                authenticated=True,
                live=False,
                source="demo_fallback",
                user_id=request.fallback_user_id,
                tenant_id=request.fallback_tenant_id,
                roles=list(request.fallback_roles),
                token_present=False,
                token_active=False,
                reason="identity.synthetic_fallback",
                metadata={"requested_path": request.requested_path},
            )

        req = Request(self._userinfo_url)
        req.add_header("Authorization", f"Bearer {token}")
        req.add_header("Accept", "application/json")

        try:
            with urlopen(req, timeout=self._timeout_seconds) as response:
                claims = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return IdentityResolutionResult(
                authenticated=False,
                live=False,
                source="keycloak_userinfo",
                user_id="",
                tenant_id="",
                roles=[],
                token_present=True,
                token_active=False,
                reason=f"identity.keycloak_http_error:{exc.code}",
                metadata={"requested_path": request.requested_path},
            )
        except (URLError, TimeoutError, json.JSONDecodeError):
            return IdentityResolutionResult(
                authenticated=False,
                live=False,
                source="keycloak_userinfo",
                user_id="",
                tenant_id="",
                roles=[],
                token_present=True,
                token_active=False,
                reason="identity.keycloak_unreachable",
                metadata={"requested_path": request.requested_path},
            )

        user_id = str(claims.get("sub") or claims.get("preferred_username") or claims.get("email") or "")
        tenant_id = _tenant_from_claims(claims)
        roles = _roles_from_claims(claims)
        session_id = str(claims.get("sid") or claims.get("session_state") or "")

        if not user_id:
            return IdentityResolutionResult(
                authenticated=False,
                live=False,
                source="keycloak_userinfo",
                user_id="",
                tenant_id=tenant_id,
                roles=roles,
                session_id=session_id,
                token_present=True,
                token_active=False,
                reason="identity.subject_missing",
                metadata={"requested_path": request.requested_path},
            )

        if request.required_live_identity and not tenant_id:
            return IdentityResolutionResult(
                authenticated=False,
                live=False,
                source="keycloak_userinfo",
                user_id=user_id,
                tenant_id="",
                roles=roles,
                session_id=session_id,
                token_present=True,
                token_active=False,
                reason="identity.tenant_missing",
                metadata={"requested_path": request.requested_path},
            )

        return IdentityResolutionResult(
            authenticated=True,
            live=True,
            source="keycloak_userinfo",
            user_id=user_id,
            tenant_id=tenant_id or request.fallback_tenant_id,
            roles=roles or list(request.fallback_roles),
            session_id=session_id,
            token_present=True,
            token_active=True,
            reason="identity.keycloak_validated",
            metadata={
                "requested_path": request.requested_path,
                "issuer": str(claims.get("iss", "")),
                "preferred_username": str(claims.get("preferred_username", "")),
            },
        )
