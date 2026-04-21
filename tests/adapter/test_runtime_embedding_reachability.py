from __future__ import annotations

from urllib.error import HTTPError

import backend.api_gateway.server as server_module
from backend.api_gateway.server import ControlPlaneRequestHandler


class FakeResponse:
    def __init__(self, *, status: int = 200, url: str = "", headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.url = url
        self.headers = headers or {}

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def _handler() -> ControlPlaneRequestHandler:
    return object.__new__(ControlPlaneRequestHandler)


def test_runtime_reachability_treats_404_as_unreachable(monkeypatch) -> None:
    def raise_404(url: str, timeout: int = 2):
        raise HTTPError(url, 404, "Not Found", hdrs={}, fp=None)

    monkeypatch.setattr(server_module, "urlopen", raise_404)

    assert _handler()._url_is_reachable("https://fictional-fishstick-3000.app.github.dev/app") is False


def test_runtime_reachability_rejects_codespaces_redirect_to_github(monkeypatch) -> None:
    def redirected(url: str, timeout: int = 2):
        return FakeResponse(status=200, url="https://github.com/login?return_to=port")

    monkeypatch.setattr(server_module, "urlopen", redirected)

    assert _handler()._url_is_reachable("https://fictional-fishstick-8088.app.github.dev/apps") is False


def test_runtime_reachability_rejects_frame_denial_headers(monkeypatch) -> None:
    def frame_denied(url: str, timeout: int = 2):
        return FakeResponse(status=200, url=url, headers={"X-Frame-Options": "DENY"})

    monkeypatch.setattr(server_module, "urlopen", frame_denied)

    assert _handler()._url_is_reachable("https://fictional-fishstick-8088.app.github.dev/apps") is False


def test_runtime_reachability_accepts_embeddable_codespaces_response(monkeypatch) -> None:
    def ok(url: str, timeout: int = 2):
        return FakeResponse(status=200, url=url, headers={})

    monkeypatch.setattr(server_module, "urlopen", ok)

    assert _handler()._url_is_reachable("https://fictional-fishstick-8088.app.github.dev/apps") is True
