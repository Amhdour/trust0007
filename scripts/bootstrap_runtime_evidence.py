#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
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


def _request_json(url: str, *, method: str = "GET", data: bytes | None = None, headers: dict[str, str] | None = None) -> dict:
    req = Request(url, method=method, data=data, headers=headers or {})
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _request_text(url: str, *, headers: dict[str, str] | None = None) -> tuple[int, str]:
    req = Request(url, headers=headers or {})
    with urlopen(req, timeout=20) as resp:
        return int(getattr(resp, "status", 200)), resp.read().decode("utf-8")


def _artifact(control_plane_base_url: str, filename: str) -> dict:
    return _request_json(f"{control_plane_base_url.rstrip('/')}/raw/overlays/myStarterKit/artifacts/{quote(filename)}")


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
    parser = argparse.ArgumentParser(description="Generate fresh live governed evidence for Onyx and Onyx Agent handoff lanes.")
    parser.add_argument("--control-plane-base-url", default=_default_control_plane_base_url())
    parser.add_argument("--keycloak-base-url", default=_default_keycloak_base_url())
    parser.add_argument("--realm", default=_setting("KEYCLOAK_REALM", "umbrella"))
    parser.add_argument("--client-id", default=_setting("SMOKE_CLIENT_ID", "governed-smoke-client"))
    parser.add_argument("--username", default=_setting("LIVE_USERNAME", "governed-live-admin"))
    parser.add_argument("--password", default=_setting("LIVE_PASSWORD", "change-me"))
    parser.add_argument("--scope", default=_setting("KEYCLOAK_SCOPE", "openid email profile"))
    parser.add_argument("--mcp-server", default="mcp_server.dashboard_control_plane")
    args = parser.parse_args()

    token = _mint_token(args.keycloak_base_url, args.realm, args.client_id, args.username, args.password, args.scope)
    _launch(args.control_plane_base_url, "onyx", "/apps", token, mcp_server=args.mcp_server)
    # Keep Onyx as the final governed run so retrieval/runtime proof in the
    # top-level summary reflects the RAG lane truthfully.
    _launch(args.control_plane_base_url, "onyx", "/app", token)

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
        "onyx-agent-runtime-proof.json",
    ]
    missing: list[str] = []
    for name in required:
        try:
            _artifact(args.control_plane_base_url, name)
        except Exception:
            missing.append(name)
    if missing:
        raise RuntimeError(f"missing expected artifacts after bootstrap: {', '.join(missing)}")

    # Refresh dashboard ingestion exports after live bootstrap so stale summary
    # feeds do not continue to surface older demo posture fragments.
    # In some containerized startup flows, artifact directories are volume-owned
    # and may not be writable from the workspace user. Treat export as best-effort.
    try:
        subprocess.run(
            ["python", "scripts/export_mystarterkit_dashboard_feed.py"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip().splitlines()
        suffix = f" ({detail[-1]})" if detail else ""
        print(f"warning: dashboard feed export skipped{suffix}", file=sys.stderr)
    print("runtime evidence bootstrap passed for Onyx and Onyx Agent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
