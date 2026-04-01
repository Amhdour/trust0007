from __future__ import annotations

from base64 import urlsafe_b64encode
from io import BytesIO
import json
from unittest.mock import patch
from urllib.parse import urlparse

from adapters.identity.schemas import IdentityResolutionResult
from backend.api_gateway.server import ControlPlaneRequestHandler
from backend.api_gateway.server import _live_session_status_payload


class _FakeHandler:
    do_GET = ControlPlaneRequestHandler.do_GET
    _parse_int_query = ControlPlaneRequestHandler._parse_int_query
    _query_value = ControlPlaneRequestHandler._query_value
    _send_json = ControlPlaneRequestHandler._send_json
    _send_html = ControlPlaneRequestHandler._send_html
    _redirect = ControlPlaneRequestHandler._redirect
    _handle_dev_live_session_start = ControlPlaneRequestHandler._handle_dev_live_session_start
    _handle_dev_live_session_end = ControlPlaneRequestHandler._handle_dev_live_session_end
    _serve_onyx_handoff = ControlPlaneRequestHandler._serve_onyx_handoff

    def __init__(self, path: str = "/auth/live-session/start") -> None:
        self.path = path
        self.headers: dict[str, str] = {}
        self.wfile = BytesIO()
        self.status_code: int | None = None
        self.response_headers: list[tuple[str, str]] = []

    def send_response(self, status_code: int) -> None:
        self.status_code = status_code

    def send_header(self, key: str, value: str) -> None:
        self.response_headers.append((key, value))

    def end_headers(self) -> None:
        return

    def _url_is_reachable(self, url: str) -> bool:
        del url
        return False


def _jwt(payload: dict[str, object]) -> str:
    def encode(part: dict[str, object]) -> str:
        return urlsafe_b64encode(json.dumps(part).encode("utf-8")).decode("ascii").rstrip("=")

    return f"{encode({'alg': 'none', 'typ': 'JWT'})}.{encode(payload)}.fixture"


def test_dev_live_session_start_sets_cookie_and_redirects() -> None:
    handler = _FakeHandler(
        "/auth/live-session/start?next=%2Flaunch%2Fonyx%3Fpath%3D%2Fapp%26mode%3Dlive%26view%3Dembedded"
    )

    with patch("backend.api_gateway.server._dev_live_session_allowed", return_value=True), patch(
        "backend.api_gateway.server._mint_dev_live_session_token",
        return_value="dev-live-token",
    ):
        handler._handle_dev_live_session_start(urlparse(handler.path))

    assert handler.status_code == 303
    assert ("Location", "/launch/onyx?path=/app&mode=live&view=embedded") in handler.response_headers
    cookie_headers = [value for key, value in handler.response_headers if key == "Set-Cookie"]
    assert cookie_headers
    assert "kc_access_token=dev-live-token" in cookie_headers[0]
    assert "HttpOnly" in cookie_headers[0]
    assert "SameSite=Lax" in cookie_headers[0]


def test_live_handoff_denial_surfaces_dev_session_recovery_link() -> None:
    handler = _FakeHandler("/launch/onyx?path=/app&mode=live")

    with patch("backend.api_gateway.server._dev_live_session_allowed", return_value=True):
        handler._serve_onyx_handoff("/app")

    body = handler.wfile.getvalue().decode("utf-8")
    assert handler.status_code == 403
    assert "Start dev live session and retry" in body
    assert "/auth/live-session/start?next=%2Flaunch%2Fonyx%3Fpath%3D%2Fapp%26mode%3Dlive" in body


def test_dev_live_session_end_clears_cookie_and_redirects() -> None:
    handler = _FakeHandler("/auth/live-session/end?next=%2F")

    handler._handle_dev_live_session_end(urlparse(handler.path))

    assert handler.status_code == 303
    assert ("Location", "/") in handler.response_headers
    cookie_headers = [value for key, value in handler.response_headers if key == "Set-Cookie"]
    assert cookie_headers
    assert "kc_access_token=" in cookie_headers[0]
    assert "Max-Age=0" in cookie_headers[0]


def test_live_session_status_payload_reports_active_validated_cookie() -> None:
    token = _jwt(
        {
            "sub": "tenant-admin-1",
            "preferred_username": "live-tenant-admin",
            "tenant_id": "tenant-dashboard",
            "sid": "kc-session-123",
            "iss": "http://keycloak.test/realms/umbrella-dev",
            "exp": 4102444800,
        }
    )

    with patch("backend.api_gateway.server._dev_live_session_allowed", return_value=True), patch(
        "backend.api_gateway.server.KeycloakIdentityProvider.resolve",
        return_value=IdentityResolutionResult(
            authenticated=True,
            live=True,
            source="keycloak_userinfo",
            user_id="tenant-admin-1",
            tenant_id="tenant-dashboard",
            roles=["tenant_user"],
            session_id="kc-session-123",
            token_present=True,
            token_active=True,
            reason="identity.keycloak_validated",
            metadata={"preferred_username": "live-tenant-admin", "issuer": "http://keycloak.test/realms/umbrella-dev"},
        ),
    ):
        payload = _live_session_status_payload({"kc_access_token": token})

    assert payload["status"] == "healthy"
    assert payload["status_label"] == "Live session active"
    assert payload["authenticated"] is True
    assert payload["username"] == "live-tenant-admin"
    assert payload["tenant_id"] == "tenant-dashboard"
    assert payload["session_id"] == "kc-session-123"
    assert payload["expires_at"] == "2100-01-01T00:00:00+00:00"


def test_live_session_status_payload_reports_inactive_without_cookie() -> None:
    with patch("backend.api_gateway.server._dev_live_session_allowed", return_value=True):
        payload = _live_session_status_payload({})

    assert payload["status"] == "neutral"
    assert payload["authenticated"] is False
    assert payload["cookie_present"] is False
    assert payload["status_label"] == "No dev live session"


def test_onyx_activity_api_supports_json_and_html_payloads() -> None:
    json_handler = _FakeHandler("/api/control-plane/onyx-activity?path=%2Fapp&trace_id=trace-123&session_id=session-123")
    html_handler = _FakeHandler("/api/control-plane/onyx-activity?path=%2Fapp&format=html")
    activity_payload = {
        "summary": {"status": "healthy", "label": "Direct runtime activity visible", "detail": "Matched /app."},
        "counts": {"current_surface": 1, "correlated": 0, "other_runtime": 0},
        "groups": [
            {
                "title": "This workspace path",
                "description": "Direct runtime events.",
                "entries": [
                    {
                        "summary": "GET /app -> 200",
                        "timestamp": "2026-04-01T12:00:00+00:00",
                        "scope": "current_surface",
                        "correlation_detail": "Matched the governed Onyx path directly from runtime activity.",
                        "path_match": True,
                        "trace_match": False,
                        "session_match": False,
                        "source_label": "Onyx Web",
                        "trace_id": "",
                        "session_id": "",
                    }
                ],
                "empty_state": "No direct runtime hits.",
            }
        ],
        "limitations": ["Runtime rows are matched by path."],
        "sources": {"onyx": "connected", "langfuse": "connected"},
        "source_href": "/api/control-plane/onyx-activity?path=%2Fapp",
    }

    with patch("backend.api_gateway.server.build_onyx_workspace_activity", return_value=activity_payload):
        json_handler.do_GET()

    assert json_handler.status_code == 200
    json_payload = json.loads(json_handler.wfile.getvalue().decode("utf-8"))
    assert json_payload["summary"]["label"] == "Direct runtime activity visible"

    with patch("backend.api_gateway.server.build_onyx_workspace_activity", return_value=activity_payload):
        html_handler.do_GET()

    assert html_handler.status_code == 200
    html_body = html_handler.wfile.getvalue().decode("utf-8")
    assert "Current Onyx Activity" in html_body
    assert "GET /app -&gt; 200" in html_body
