from __future__ import annotations

from base64 import urlsafe_b64encode
from http.cookiejar import CookieJar
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import HTTPCookieProcessor, build_opener

import pytest

from .test_live_end_to_end import APIServer


def _jwt(payload: dict[str, object]) -> str:
    def encode(part: dict[str, object]) -> str:
        return urlsafe_b64encode(json.dumps(part).encode("utf-8")).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none', 'typ': 'JWT'})}.{encode(payload)}.fixture"


class _FixtureServer:
    def __init__(self, handler_type: type[BaseHTTPRequestHandler]) -> None:
        self._handler_type = handler_type
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self.port = 0

    def __enter__(self) -> _FixtureServer:
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler_type)
        self.port = int(self._server.server_port)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
        if self._thread:
            self._thread.join(timeout=5)


def _dependency_handler(expected_token: str) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

        def _send_json(self, payload: dict[str, object], status: int = 200) -> None:
            encoded = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _read_json_body(self) -> dict[str, object]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0:
                return {}
            return json.loads(self.rfile.read(length).decode("utf-8"))

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.endswith("/protocol/openid-connect/userinfo"):
                if self.headers.get("Authorization", "") != f"Bearer {expected_token}":
                    self._send_json({"error": "unauthorized"}, status=401)
                    return
                self._send_json(
                    {
                        "sub": "tenant-admin-1",
                        "preferred_username": "live-tenant-admin",
                        "tenant_id": "tenant-dashboard",
                        "sid": "kc-session-123",
                        "realm_access": {"roles": ["tenant_user"]},
                    }
                )
                return

            if parsed.path == "/v1/secret/data/dev/tenant-dashboard/runtime":
                if self.headers.get("X-Vault-Token", "") != "root-token":
                    self._send_json({"error": "forbidden"}, status=403)
                    return
                self._send_json({"data": {"data": {"api_token": "runtime-secret"}}})
                return

            self.send_error(404)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.endswith("/protocol/openid-connect/token"):
                self._send_json(
                    {
                        "access_token": expected_token,
                        "expires_in": 1800,
                        "token_type": "Bearer",
                    }
                )
                return

            if parsed.path == "/v1/data/umbrella/policy/decision":
                payload = self._read_json_body()
                surface = (
                    payload.get("input", {})
                    .get("request", {})
                    .get("surface", "")
                )
                self._send_json(
                    {
                        "result": {
                            "allow": True,
                            "matched_surface": surface,
                            "reason_codes": ["policy.allow"],
                        }
                    }
                )
                return

            if parsed.path == "/collections/governed_docs/points/scroll":
                payload = self._read_json_body()
                must_filters = payload.get("filter", {}).get("must", [])
                tenant_id = must_filters[0].get("match", {}).get("value", "tenant-dashboard") if len(must_filters) > 0 else "tenant-dashboard"
                source = must_filters[1].get("match", {}).get("value", "qdrant") if len(must_filters) > 1 else "qdrant"
                self._send_json(
                    {
                        "result": {
                            "points": [
                                {
                                    "id": "launch-doc-1",
                                    "payload": {
                                        "tenant_id": tenant_id,
                                        "source": source,
                                        "content": "Navigate to Onyx path: /app",
                                        "trust_label": "trusted",
                                        "quarantined": False,
                                        "provenance": {"uri": "kb://launch-doc-1"},
                                    },
                                }
                            ]
                        }
                    }
                )
                return

            self.send_error(404)

    return Handler


class _OnyxHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def do_GET(self) -> None:  # noqa: N802
        encoded = b"<!doctype html><html><body><h1>Fake Onyx Runtime</h1></body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def test_live_session_bootstrap_round_trip_over_http() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expires_at = int(time.time()) + 1800
    token = _jwt(
        {
            "sub": "tenant-admin-1",
            "preferred_username": "live-tenant-admin",
            "tenant_id": "tenant-dashboard",
            "sid": "kc-session-123",
            "iss": "http://fixture-keycloak/realms/umbrella-dev",
            "exp": expires_at,
        }
    )

    try:
        dependency_server = _FixtureServer(_dependency_handler(token))
        onyx_server = _FixtureServer(_OnyxHandler)
        deps = dependency_server.__enter__()
        onyx = onyx_server.__enter__()
    except PermissionError:
        pytest.skip("Local socket binding is not permitted in this environment.")

    try:
        server = APIServer(
            repo_root,
            extra_env={
                "CONTROL_PLANE_GOVERNANCE_MODE": "live",
                "CONTROL_PLANE_ENVIRONMENT_MODE": "prod-sim",
                "CONTROL_PLANE_KEYCLOAK_BASE_URL": f"http://127.0.0.1:{deps.port}",
                "CONTROL_PLANE_KEYCLOAK_USERINFO_URL": f"http://127.0.0.1:{deps.port}/realms/umbrella-dev/protocol/openid-connect/userinfo",
                "CONTROL_PLANE_KEYCLOAK_TOKEN_URL": f"http://127.0.0.1:{deps.port}/realms/umbrella-dev/protocol/openid-connect/token",
                "CONTROL_PLANE_OPA_URL": f"http://127.0.0.1:{deps.port}",
                "CONTROL_PLANE_OPA_PACKAGE": "umbrella/policy/decision",
                "CONTROL_PLANE_QDRANT_URL": f"http://127.0.0.1:{deps.port}",
                "CONTROL_PLANE_QDRANT_COLLECTION": "governed_docs",
                "CONTROL_PLANE_VAULT_ADDR": f"http://127.0.0.1:{deps.port}",
                "CONTROL_PLANE_VAULT_TOKEN": "root-token",
                "CONTROL_PLANE_ONYX_SECRET_PATH": "secret/data/dev/tenant-dashboard/runtime",
                "CONTROL_PLANE_ONYX_SECRET_KEY": "api_token",
                "CONTROL_PLANE_ONYX_PORT": str(onyx.port),
            },
        )
        server.start()

        try:
            cookies = CookieJar()
            opener = build_opener(HTTPCookieProcessor(cookies))

            with opener.open(server.url("/api/control-plane/live-session"), timeout=20) as response:
                before = json.loads(response.read().decode("utf-8"))
            assert before["authenticated"] is False
            assert before["status_label"] == "No dev live session"

            start_url = server.url(
                "/auth/live-session/start?next=%2Flaunch%2Fonyx%3Fpath%3D%2Fapp%26mode%3Dlive%26view%3Dembedded"
            )
            with opener.open(start_url, timeout=30) as response:
                workspace_html = response.read().decode("utf-8")
                final_url = response.geturl()

            parsed_final = urlparse(final_url)
            assert parsed_final.path == "/launch/onyx"
            final_query = parse_qs(parsed_final.query)
            assert final_query["path"] == ["/app"]
            assert final_query["mode"] == ["live"]
            assert final_query["view"] == ["embedded"]
            assert "Live Runtime Workspace" in workspace_html
            assert "Dashboard-owned live runtime" in workspace_html
            assert "End dev session" in workspace_html
            assert "runtime-frame" in workspace_html
            assert any(cookie.name == "kc_access_token" for cookie in cookies)

            with opener.open(server.url("/api/control-plane/live-session"), timeout=20) as response:
                active = json.loads(response.read().decode("utf-8"))
            assert active["authenticated"] is True
            assert active["status_label"] == "Live session active"
            assert active["tenant_id"] == "tenant-dashboard"
            assert active["session_id"] == "kc-session-123"

            with opener.open(server.url("/auth/live-session/end?next=%2F"), timeout=20) as response:
                response.read()

            with opener.open(server.url("/api/control-plane/live-session"), timeout=20) as response:
                after = json.loads(response.read().decode("utf-8"))
            assert after["authenticated"] is False
            assert after["cookie_present"] is False
        finally:
            server.stop()
    finally:
        onyx_server.__exit__(None, None, None)
        dependency_server.__exit__(None, None, None)
