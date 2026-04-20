#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def _request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    req = Request(url, method=method, data=data, headers=headers or {})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _request_text(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, str]:
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=20) as resp:
        return int(getattr(resp, "status", 200)), resp.read().decode("utf-8")


def _mint_token(base_url: str, realm: str, client_id: str, username: str, password: str, scope: str) -> str:
    payload = _request_json(
        f"{base_url.rstrip('/')}/realms/{realm}/protocol/openid-connect/token",
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
        data=urlencode(
            {
                "client_id": client_id,
                "grant_type": "password",
                "username": username,
                "password": password,
                "scope": scope,
            }
        ).encode("utf-8"),
    )
    return str(payload["access_token"])


def _launch(control_plane_base_url: str, runtime: str, path: str, token: str, mcp_server: str = "") -> None:
    url = f"{control_plane_base_url.rstrip('/')}/launch/{runtime}?path={quote(path, safe='/?=&')}&mode=live"
    if mcp_server:
        url += f"&mcp={quote(mcp_server, safe='._-')}"
    status, body = _request_text(url, headers={"Authorization": f"Bearer {token}"})
    if status >= 400 or "✓ Approved" not in body:
        raise RuntimeError(f"live governed {runtime} launch failed: status={status}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate fresh live governed evidence for Onyx and Dify handoff lanes.")
    parser.add_argument("--control-plane-base-url", default=os.environ.get("CONTROL_PLANE_BASE_URL", "http://127.0.0.1:3000"))
    parser.add_argument("--keycloak-base-url", default=os.environ.get("KEYCLOAK_BASE_URL", "http://127.0.0.1:18080"))
    parser.add_argument("--realm", default=os.environ.get("KEYCLOAK_REALM", "umbrella"))
    parser.add_argument("--client-id", default=os.environ.get("SMOKE_CLIENT_ID", "governed-smoke-client"))
    parser.add_argument("--username", default=os.environ.get("LIVE_USERNAME", "governed-live-admin"))
    parser.add_argument("--password", default=os.environ.get("LIVE_PASSWORD", "change-me"))
    parser.add_argument("--scope", default=os.environ.get("KEYCLOAK_SCOPE", "openid email profile"))
    parser.add_argument("--mcp-server", default="mcp_server.dashboard_control_plane")
    args = parser.parse_args()

    token = _mint_token(args.keycloak_base_url, args.realm, args.client_id, args.username, args.password, args.scope)
    _launch(args.control_plane_base_url, "dify", "/apps", token, mcp_server=args.mcp_server)
    # Keep Onyx as the final governed run so retrieval/runtime proof in the
    # top-level summary reflects the RAG lane truthfully.
    _launch(args.control_plane_base_url, "onyx", "/app?chatMode=search", token)

    artifacts_root = Path("overlays/myStarterKit/artifacts")
    required = [
        "identity-evidence.json",
        "policy-evidence.json",
        "retrieval-evidence.json",
        "tool-evidence.json",
        "secret-evidence.json",
        "trace-correlation.json",
        "launch-gate-result.json",
        "governed-flow-summary.json",
        "onyx-runtime-proof.json",
        "dify-runtime-proof.json",
    ]
    missing = [name for name in required if not (artifacts_root / name).exists()]
    if missing:
        raise RuntimeError(f"missing expected artifacts after bootstrap: {', '.join(missing)}")

    # Refresh dashboard ingestion exports after live bootstrap so stale summary
    # feeds do not continue to surface older demo posture fragments.
    subprocess.run(["python", "scripts/export_mystarterkit_dashboard_feed.py"], check=True)
    print("runtime evidence bootstrap passed for Onyx and Dify")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
