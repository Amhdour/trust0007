from __future__ import annotations

from contextlib import ExitStack
from io import BytesIO
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from backend.api_gateway.server import ControlPlaneRequestHandler
from backend.posture_service.service import build_control_plane_dashboard


class HTTPResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def json(self) -> dict[str, Any]:
        return json.loads(self.text)


class FixtureHTTPResponse:
    def __init__(self, payload: dict[str, Any]):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self) -> FixtureHTTPResponse:
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


@dataclass
class LiveFixtureScenario:
    keycloak_mode: str = "allow"
    opa_mode: str = "allow"
    qdrant_mode: str = "allow"
    vault_mode: str = "allow"
    onyx_running: bool = True
    expected_token: str = "valid-live-token"
    tenant_id: str = "tenant-dashboard"
    user_id: str = "tenant-admin-1"
    roles: tuple[str, ...] = ("tenant_user",)
    secret_path: str = "secret/data/dev/tenant-dashboard/runtime"
    secret_key: str = "api_token"


class LiveDependencyURLDispatcher:
    def __init__(self, scenario: LiveFixtureScenario):
        self.scenario = scenario

    def __call__(self, request, timeout=0):  # noqa: ARG002
        url = request.full_url if hasattr(request, "full_url") else str(request)
        headers = {str(key).lower(): value for key, value in dict(getattr(request, "headers", {})).items()}
        body = getattr(request, "data", b"") or b""

        if url.endswith("/realms/umbrella-dev/protocol/openid-connect/userinfo"):
            return self._keycloak(url, headers)
        if url.endswith("/v1/data/umbrella/policy/decision"):
            return self._opa(url, body)
        if url.endswith("/collections/governed_docs/points/scroll"):
            return self._qdrant(url, body)
        if "/v1/secret/data/dev/tenant-dashboard/runtime" in url:
            return self._vault(url, headers)
        raise AssertionError(f"Unexpected urlopen call: {url}")

    @staticmethod
    def _http_error(url: str, code: int, payload: bytes | None = None) -> HTTPError:
        return HTTPError(url, code, "error", hdrs=None, fp=BytesIO(payload or b'{"error":"failed"}'))

    def _keycloak(self, url: str, headers: dict[str, str]):
        if self.scenario.keycloak_mode == "unreachable":
            raise URLError("keycloak unavailable")
        token = headers.get("authorization", "").removeprefix("Bearer ").strip()
        if token != self.scenario.expected_token:
            raise self._http_error(url, 401)
        payload: dict[str, Any] = {
            "sub": self.scenario.user_id,
            "realm_access": {"roles": list(self.scenario.roles)},
            "preferred_username": self.scenario.user_id,
        }
        if self.scenario.keycloak_mode != "missing_tenant":
            payload["tenant_id"] = self.scenario.tenant_id
        if self.scenario.keycloak_mode != "no_session":
            payload["sid"] = "kc-session-123"
        return FixtureHTTPResponse(payload)

    def _opa(self, url: str, body: bytes):
        if self.scenario.opa_mode == "unreachable":
            raise self._http_error(url, 503)
        payload = json.loads(body.decode("utf-8"))
        request_input = payload.get("input", {})
        surface = str(request_input.get("request", {}).get("surface", ""))
        result = {
            "allow": self.scenario.opa_mode != "deny",
            "matched_surface": surface,
            "reason_codes": ["policy.allow"] if self.scenario.opa_mode != "deny" else ["policy.opa_explicit_deny"],
        }
        return FixtureHTTPResponse({"result": result})

    def _qdrant(self, url: str, body: bytes):
        if self.scenario.qdrant_mode == "unreachable":
            raise self._http_error(url, 503)
        payload = json.loads(body.decode("utf-8"))
        must_filters = payload.get("filter", {}).get("must", [])
        tenant_id = must_filters[0].get("match", {}).get("value", self.scenario.tenant_id) if len(must_filters) > 0 else self.scenario.tenant_id
        source = must_filters[1].get("match", {}).get("value", "qdrant") if len(must_filters) > 1 else "qdrant"

        if self.scenario.qdrant_mode == "empty":
            points: list[dict[str, Any]] = []
        elif self.scenario.qdrant_mode == "cross_tenant":
            points = [
                {
                    "id": "cross-tenant-doc",
                    "payload": {
                        "tenant_id": "tenant-other",
                        "source": source,
                        "content": "Navigate to Onyx path: /app",
                        "trust_label": "trusted",
                        "quarantined": False,
                        "provenance": {"uri": "kb://cross-tenant-doc"},
                    },
                }
            ]
        else:
            points = [
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
        return FixtureHTTPResponse({"result": {"points": points}})

    def _vault(self, url: str, headers: dict[str, str]):
        if self.scenario.vault_mode == "unreachable":
            raise self._http_error(url, 503)
        if headers.get("x-vault-token", "") != "root-token":
            raise self._http_error(url, 403)
        if self.scenario.vault_mode == "missing_key":
            payload = {"data": {"data": {"not_api_token": "value"}}}
        else:
            payload = {"data": {"data": {"api_token": "runtime-secret"}}}
        return FixtureHTTPResponse(payload)


class _FakeHeaderMap(dict):
    def get(self, key: str, default=None):
        return super().get(key, default)


class _FakeLaunchHandler:
    def __init__(self, path: str, authorization_header: str, onyx_running: bool) -> None:
        self.path = path
        self.headers = _FakeHeaderMap()
        if authorization_header:
            self.headers["Authorization"] = authorization_header
        self.wfile = BytesIO()
        self.status_code = 200
        self.response_headers: dict[str, str] = {}
        self._onyx_running = onyx_running

    def send_response(self, status_code: int) -> None:
        self.status_code = status_code

    def send_header(self, key: str, value: str) -> None:
        self.response_headers[key] = value

    def end_headers(self) -> None:
        return

    def _url_is_reachable(self, url: str) -> bool:
        del url
        return self._onyx_running


class StrictLiveHarness:
    def __init__(self, repo_root: Path, scenario: LiveFixtureScenario):
        self.repo_root = repo_root
        self.scenario = scenario
        self.artifact_dir = self.repo_root / "overlays" / "myStarterKit" / "artifacts"
        self._stack = ExitStack()

    def __enter__(self) -> StrictLiveHarness:
        dispatcher = LiveDependencyURLDispatcher(self.scenario)
        self._stack.enter_context(
            patch.dict(
                os.environ,
                {
                    "CONTROL_PLANE_GOVERNANCE_MODE": "live",
                    "CONTROL_PLANE_ENVIRONMENT_MODE": "prod-sim",
                    "CONTROL_PLANE_KEYCLOAK_USERINFO_URL": "http://fixture-keycloak/realms/umbrella-dev/protocol/openid-connect/userinfo",
                    "CONTROL_PLANE_OPA_URL": "http://fixture-opa",
                    "CONTROL_PLANE_OPA_PACKAGE": "umbrella/policy/decision",
                    "CONTROL_PLANE_QDRANT_URL": "http://fixture-qdrant",
                    "CONTROL_PLANE_QDRANT_COLLECTION": "governed_docs",
                    "CONTROL_PLANE_VAULT_ADDR": "http://fixture-vault",
                    "CONTROL_PLANE_VAULT_TOKEN": "root-token",
                    "CONTROL_PLANE_ONYX_SECRET_PATH": self.scenario.secret_path,
                    "CONTROL_PLANE_ONYX_SECRET_KEY": self.scenario.secret_key,
                },
                clear=False,
            )
        )
        self._stack.enter_context(patch("adapters.identity.keycloak.urlopen", side_effect=dispatcher))
        self._stack.enter_context(patch("adapters.policy.opa.urlopen", side_effect=dispatcher))
        self._stack.enter_context(patch("adapters.retrieval.qdrant.urlopen", side_effect=dispatcher))
        self._stack.enter_context(patch("adapters.secrets.vault.urlopen", side_effect=dispatcher))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stack.close()

    def read_artifact(self, filename: str, *, jsonl: bool = False) -> Any:
        raw = (self.artifact_dir / filename).read_text(encoding="utf-8")
        if jsonl:
            return [json.loads(line) for line in raw.splitlines() if line.strip()]
        return json.loads(raw)

    def launch(self, *, token: str | None = "valid-live-token", path: str = "/app") -> HTTPResponse:
        authorization_header = f"Bearer {token}" if token is not None else ""
        handler = _FakeLaunchHandler(
            path=f"/launch/onyx?path={path}&mode=live",
            authorization_header=authorization_header,
            onyx_running=self.scenario.onyx_running,
        )
        ControlPlaneRequestHandler._serve_onyx_handoff(handler, path)
        return HTTPResponse(handler.status_code, handler.wfile.getvalue().decode("utf-8"))

    def overview(self) -> HTTPResponse:
        payload = build_control_plane_dashboard(self.repo_root)
        return HTTPResponse(200, json.dumps(payload))
