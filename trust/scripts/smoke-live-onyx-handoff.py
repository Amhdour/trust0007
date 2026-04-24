#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def _env_file_candidates() -> list[Path]:
    script_root = Path(__file__).resolve().parents[1]
    candidates: list[Path] = []
    explicit = os.environ.get("ENV_FILE", "").strip()
    if explicit:
        candidates.append(Path(explicit))
    candidates.append(script_root / ".env.live")
    candidates.append(script_root / "compose" / ".env.production")
    return candidates


def _read_env_file_value(key: str) -> str:
    for path in _env_file_candidates():
        if not path.exists():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#") or "=" not in raw_line:
                continue
            found_key, value = raw_line.split("=", 1)
            if found_key.strip() == key:
                return value.strip()
    return ""


def _setting(key: str, default: str) -> str:
    explicit = os.environ.get(key, "").strip()
    if explicit:
        return explicit
    from_env_file = _read_env_file_value(key)
    if from_env_file:
        return from_env_file
    return default


def _default_control_plane_base_url() -> str:
    explicit = _setting("CONTROL_PLANE_BASE_URL", "")
    if explicit:
        return explicit
    host_port = _setting("CONTROL_PLANE_HOST_PORT", "3000")
    return f"http://127.0.0.1:{host_port}"


def _default_keycloak_base_url() -> str:
    explicit = _setting("KEYCLOAK_BASE_URL", "")
    if explicit:
        return explicit
    host_port = _setting("KEYCLOAK_HOST_PORT", "18080")
    return f"http://127.0.0.1:{host_port}"


def _request_json(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    timeout: float = 10.0,
) -> dict[str, Any]:
    request = Request(url, data=data, headers=headers or {}, method=method)
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> tuple[int, str, str]:
    request = Request(url, headers=headers or {}, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return (
                int(getattr(response, "status", 200)),
                response.read().decode("utf-8"),
                getattr(response, "geturl", lambda: url)(),
            )
    except HTTPError as exc:
        return exc.code, exc.read().decode("utf-8"), getattr(exc, "geturl", lambda: url)()


def _decode_jwt_claims(token: str) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    payload += "=" * ((4 - len(payload) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload.encode("ascii"))
        claims = json.loads(decoded.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return claims if isinstance(claims, dict) else {}


def _dashboard_mode_payload(control_plane_base_url: str) -> dict[str, Any]:
    overview = _request_json(f"{control_plane_base_url.rstrip('/')}/api/control-plane/overview")
    return {
        "data_mode": overview.get("data_mode", {}).get("label"),
        "mode_banner": overview.get("mode_banner", {}).get("label"),
        "latest_trace": next(
            (
                chip.get("value")
                for chip in overview.get("mode_banner", {}).get("chips", [])
                if chip.get("label") == "Latest trace"
            ),
            "",
        ),
    }


def _artifact(control_plane_base_url: str, filename: str) -> dict[str, Any]:
    return _request_json(f"{control_plane_base_url.rstrip('/')}/raw/overlays/myStarterKit/artifacts/{quote(filename)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mint a real Keycloak token and verify the governed /launch/onyx live path against the running stack."
    )
    parser.add_argument("--control-plane-base-url", default=_default_control_plane_base_url())
    parser.add_argument("--keycloak-base-url", default=_default_keycloak_base_url())
    parser.add_argument("--realm", default=_setting("KEYCLOAK_REALM", "umbrella"))
    parser.add_argument("--client-id", default=_setting("SMOKE_CLIENT_ID", "governed-smoke-client"))
    parser.add_argument("--username", default=_setting("LIVE_USERNAME", "governed-live-admin"))
    parser.add_argument("--password", default=_setting("LIVE_PASSWORD", "change-me"))
    parser.add_argument("--scope", default=_setting("KEYCLOAK_SCOPE", "openid email profile"))
    parser.add_argument("--path", default="/app")
    parser.add_argument("--expected-tenant-id", default=_setting("TENANT_ID", "tenant-stage"))
    args = parser.parse_args()

    token_payload = _request_json(
        f"{args.keycloak_base_url.rstrip('/')}/realms/{args.realm}/protocol/openid-connect/token",
        data=urlencode(
            {
                "client_id": args.client_id,
                "grant_type": "password",
                "username": args.username,
                "password": args.password,
                "scope": args.scope,
            }
        ).encode("utf-8"),
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
        method="POST",
    )
    access_token = str(token_payload["access_token"])
    claims = _decode_jwt_claims(access_token)

    userinfo = _request_json(
        f"{args.keycloak_base_url.rstrip('/')}/realms/{args.realm}/protocol/openid-connect/userinfo",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
    )

    launch_status, launch_html, final_url = _request_text(
        f"{args.control_plane_base_url.rstrip('/')}/launch/onyx?path={quote(args.path, safe='/?=&')}&mode=live",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "text/html",
        },
    )

    summary = _artifact(args.control_plane_base_url, "governed-flow-summary.json")
    identity = _artifact(args.control_plane_base_url, "identity-evidence.json")
    dashboard = _dashboard_mode_payload(args.control_plane_base_url)

    result = {
        "token_claims": {
            "preferred_username": claims.get("preferred_username"),
            "tenant_id": claims.get("tenant_id"),
            "sid": claims.get("sid") or claims.get("session_state"),
            "scope": claims.get("scope"),
            "roles": claims.get("realm_access", {}).get("roles", []),
        },
        "userinfo": {
            "preferred_username": userinfo.get("preferred_username"),
            "tenant_id": userinfo.get("tenant_id"),
            "sub": userinfo.get("sub"),
        },
        "launch": {
            "status": launch_status,
            "approved": "Governance Status:</strong> ✓ Approved" in launch_html,
            "evidence_mode_live": "Evidence mode: <code>live</code>" in launch_html,
            "identity_live": "Identity: Live" in launch_html,
            "runtime_proof_present": "Runtime proof after handoff" in launch_html,
            "final_url": final_url,
        },
        "summary": {
            "trace_id": summary.get("trace_id"),
            "handoff_allowed": summary.get("handoff_allowed"),
            "launch_gate_decision": summary.get("launch_gate", {}).get("decision"),
        },
        "identity": {
            "tenant_id": identity.get("tenant_id"),
            "source": identity.get("source"),
            "reason": identity.get("reason"),
        },
        "dashboard": dashboard,
    }

    success = (
        launch_status == 200
        and result["launch"]["approved"]
        and result["launch"]["evidence_mode_live"]
        and result["launch"]["identity_live"]
        and result["launch"]["runtime_proof_present"]
        and summary.get("handoff_allowed") is True
        and summary.get("launch_gate", {}).get("decision") == "pass"
        and identity.get("tenant_id") == args.expected_tenant_id
        and userinfo.get("tenant_id") == args.expected_tenant_id
        and dashboard["data_mode"] == "Live current evidence"
        and dashboard["mode_banner"] == "LIVE GOVERNED MODE"
    )

    print(json.dumps(result, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HTTPError, URLError, KeyError, json.JSONDecodeError) as exc:
        print(f"live smoke test failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
