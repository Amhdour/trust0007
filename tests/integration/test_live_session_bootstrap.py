from __future__ import annotations

from io import BytesIO
from unittest.mock import patch
from urllib.parse import urlparse

from backend.api_gateway.server import ControlPlaneRequestHandler


class _FakeHandler:
    _query_value = ControlPlaneRequestHandler._query_value
    _send_html = ControlPlaneRequestHandler._send_html
    _redirect = ControlPlaneRequestHandler._redirect
    _handle_dev_live_session_start = ControlPlaneRequestHandler._handle_dev_live_session_start
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
