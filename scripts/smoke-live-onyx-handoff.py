#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
from http.cookiejar import CookieJar
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen


def _request_json(
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    timeout: float = 10.0,
    opener=None,
) -> dict[str, Any]:
    request = Request(url, data=data, headers=headers or {}, method=method)
    open_request = opener.open if opener is not None else urlopen
    with open_request(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _request_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    opener=None,
) -> tuple[int, str, str]:
    request = Request(url, headers=headers or {}, method="GET")
    open_request = opener.open if opener is not None else urlopen
    try:
        with open_request(request, timeout=timeout) as response:
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


def _direct_result(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
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
        f"{args.control_plane_base_url.rstrip('/')}/launch/onyx?path={args.path}&mode=live",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "text/html",
        },
    )

    result = {
        "auth_mode": "direct",
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
        "dashboard": _dashboard_mode_payload(args.control_plane_base_url),
    }

    success = (
        launch_status == 200
        and result["launch"]["approved"]
        and result["launch"]["evidence_mode_live"]
        and result["launch"]["identity_live"]
        and result["launch"]["runtime_proof_present"]
        and result["dashboard"]["data_mode"] == "Live current evidence"
        and result["dashboard"]["mode_banner"] == "LIVE GOVERNED MODE"
    )
    return result, success


def _bootstrap_result(args: argparse.Namespace) -> tuple[dict[str, Any], bool]:
    cookies = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookies))
    next_path = f"/launch/onyx?path={args.path}&mode=live&view=embedded"
    launch_status, launch_html, final_url = _request_text(
        f"{args.control_plane_base_url.rstrip('/')}/auth/live-session/start?{urlencode({'next': next_path})}",
        headers={"Accept": "text/html"},
        opener=opener,
    )
    session = _request_json(
        f"{args.control_plane_base_url.rstrip('/')}/api/control-plane/live-session",
        headers={"Accept": "application/json"},
        opener=opener,
    )
    cookie_present = any(cookie.name == "kc_access_token" and bool(cookie.value) for cookie in cookies)

    result = {
        "auth_mode": "bootstrap",
        "session": {
            "status": session.get("status"),
            "status_label": session.get("status_label"),
            "authenticated": session.get("authenticated"),
            "username": session.get("username"),
            "tenant_id": session.get("tenant_id"),
            "session_id": session.get("session_id"),
            "cookie_present": cookie_present,
        },
        "launch": {
            "status": launch_status,
            "workspace_loaded": "Live Runtime Workspace" in launch_html,
            "activity_panel_present": "Current Onyx Activity" in launch_html,
            "final_url": final_url,
        },
        "dashboard": _dashboard_mode_payload(args.control_plane_base_url),
    }

    success = (
        launch_status == 200
        and bool(result["session"]["authenticated"])
        and bool(result["session"]["cookie_present"])
        and result["launch"]["workspace_loaded"]
        and result["launch"]["activity_panel_present"]
        and result["dashboard"]["data_mode"] == "Live current evidence"
        and result["dashboard"]["mode_banner"] == "LIVE GOVERNED MODE"
    )
    return result, success


def main() -> int:
    parser = argparse.ArgumentParser(description="Mint a live Keycloak token and verify the governed /launch/onyx live path.")
    parser.add_argument("--control-plane-base-url", default="http://127.0.0.1:3000")
    parser.add_argument("--keycloak-base-url", default="http://127.0.0.1:18080")
    parser.add_argument("--auth-mode", choices=("direct", "bootstrap"), default="direct")
    parser.add_argument("--realm", default="umbrella-dev")
    parser.add_argument("--client-id", default="dev-web-app")
    parser.add_argument("--username", default="live-tenant-admin")
    parser.add_argument("--password", default="change-me")
    parser.add_argument("--scope", default="openid email profile")
    parser.add_argument("--path", default="/app")
    args = parser.parse_args()

    if args.auth_mode == "bootstrap":
        result, success = _bootstrap_result(args)
    else:
        result, success = _direct_result(args)

    print(json.dumps(result, indent=2))
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (HTTPError, URLError, KeyError, json.JSONDecodeError) as exc:
        print(f"live smoke test failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
