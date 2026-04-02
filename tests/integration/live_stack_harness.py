from __future__ import annotations

from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pytest


class HTTPResponse:
    def __init__(self, status_code: int, text: str, final_url: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.final_url = final_url

    def json(self) -> dict:
        return json.loads(self.text)


def _request_text(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    data: bytes | None = None,
    timeout: float = 20.0,
) -> HTTPResponse:
    request = Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return HTTPResponse(
                int(getattr(response, "status", 200)),
                response.read().decode("utf-8"),
                getattr(response, "geturl", lambda: url)(),
            )
    except HTTPError as exc:
        return HTTPResponse(exc.code, exc.read().decode("utf-8"), getattr(exc, "geturl", lambda: url)())


def _request_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    method: str = "GET",
    data: bytes | None = None,
    timeout: float = 20.0,
) -> dict:
    response = _request_text(url, headers=headers, method=method, data=data, timeout=timeout)
    if response.status_code >= 400:
        raise RuntimeError(f"request failed: {url} -> {response.status_code}: {response.text}")
    return response.json()


class LiveStackHarness:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root
        self.control_plane_base_url = os.environ.get("CONTROL_PLANE_BASE_URL", "http://127.0.0.1:3000").rstrip("/")
        self.keycloak_base_url = os.environ.get("KEYCLOAK_BASE_URL", "http://127.0.0.1:18080").rstrip("/")
        self.realm = os.environ.get("KEYCLOAK_REALM", "umbrella")
        self.client_id = os.environ.get("SMOKE_CLIENT_ID", "governed-smoke-client")
        self.username = os.environ.get("LIVE_USERNAME", "governed-live-admin")
        self.password = os.environ.get("LIVE_PASSWORD", "change-me")
        self.scope = os.environ.get("KEYCLOAK_SCOPE", "openid email profile")
        self.compose_file = Path(
            os.environ.get("LIVE_STACK_COMPOSE_FILE", str(repo_root / "compose" / "docker-compose.production.yml"))
        )
        self.env_file = Path(os.environ.get("LIVE_STACK_ENV_FILE", str(repo_root / "compose" / ".env.production")))
        self.vault_init_file = Path(
            os.environ.get("VAULT_INIT_FILE", str(repo_root / ".runtime" / "live-governed" / "vault-init.json"))
        )

    def require_ready(self) -> None:
        if self._status_code(f"{self.control_plane_base_url}/api/health") != 200:
            pytest.skip("live governed stack is not running at the configured control-plane URL")
        if self._status_code(f"{self.keycloak_base_url}/health/ready") != 200:
            pytest.skip("Keycloak is not ready for the live governed stack tests")

    @property
    def can_manage_services(self) -> bool:
        if not self.compose_file.exists() or not self.env_file.exists():
            return False
        try:
            self._compose("ps")
        except RuntimeError:
            return False
        return True

    def mint_access_token(self) -> str:
        payload = _request_json(
            f"{self.keycloak_base_url}/realms/{self.realm}/protocol/openid-connect/token",
            method="POST",
            data=urlencode(
                {
                    "client_id": self.client_id,
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                    "scope": self.scope,
                }
            ).encode("utf-8"),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        return str(payload["access_token"])

    def launch(self, *, path: str = "/app", token: str | None = None, view: str = "") -> HTTPResponse:
        url = f"{self.control_plane_base_url}/launch/onyx?path={quote(path, safe='/?=&')}&mode=live"
        if view:
            url = f"{url}&view={quote(view, safe='')}"
        headers = {"Accept": "text/html"}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        return _request_text(url, headers=headers)

    def overview(self) -> dict:
        return _request_json(f"{self.control_plane_base_url}/api/control-plane/overview")

    def fetch_json_artifact(self, filename: str) -> dict:
        return _request_json(f"{self.control_plane_base_url}/raw/overlays/myStarterKit/artifacts/{quote(filename)}")

    def fetch_jsonl_artifact(self, filename: str) -> list[dict]:
        response = _request_text(f"{self.control_plane_base_url}/raw/overlays/myStarterKit/artifacts/{quote(filename)}")
        if response.status_code >= 400:
            raise RuntimeError(f"request failed: {filename} -> {response.status_code}: {response.text}")
        return [json.loads(line) for line in response.text.splitlines() if line.strip()]

    @contextmanager
    def service_unavailable(self, service_name: str) -> Iterator[None]:
        if not self.can_manage_services:
            pytest.skip(f"docker compose service control is not available for {service_name} outage testing")
        self._compose("stop", service_name)
        self._wait_until_unreachable(service_name)
        try:
            yield
        finally:
            self._compose("start", service_name)
            if service_name == "vault":
                self._unseal_vault()
            self._wait_until_ready(service_name)

    def _compose(self, *args: str) -> str:
        command = [
            "docker",
            "compose",
            "--env-file",
            str(self.env_file),
            "-f",
            str(self.compose_file),
            *args,
        ]
        completed = subprocess.run(
            command,
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(detail or f"docker compose {' '.join(args)} failed")
        return completed.stdout

    def _status_code(self, url: str) -> int | None:
        try:
            with urlopen(url, timeout=5) as response:
                return int(getattr(response, "status", 200))
        except HTTPError as exc:
            return exc.code
        except URLError:
            return None

    def _wait_until_unreachable(self, service_name: str) -> None:
        check_url = {
            "keycloak": f"{self.keycloak_base_url}/health/ready",
            "opa": "http://127.0.0.1:8181/v1/data",
            "qdrant": "http://127.0.0.1:6333/collections",
            "vault": "http://127.0.0.1:8200/v1/sys/health",
        }.get(service_name, "")
        if not check_url:
            time.sleep(3)
            return
        for _ in range(30):
            if self._status_code(check_url) is None:
                return
            time.sleep(1)
        raise RuntimeError(f"{service_name} never became unreachable")

    def _wait_until_ready(self, service_name: str) -> None:
        if service_name == "keycloak":
            url = f"{self.keycloak_base_url}/health/ready"
            expected = {200}
        elif service_name == "opa":
            url = "http://127.0.0.1:8181/v1/data"
            expected = {200}
        elif service_name == "qdrant":
            url = "http://127.0.0.1:6333/collections"
            expected = {200}
        elif service_name == "vault":
            url = "http://127.0.0.1:8200/v1/sys/health"
            expected = {200, 429, 472, 473}
        else:
            time.sleep(3)
            return

        for _ in range(90):
            status = self._status_code(url)
            if status in expected:
                return
            time.sleep(2)
        raise RuntimeError(f"{service_name} never became healthy again")

    def _unseal_vault(self) -> None:
        if not self.vault_init_file.exists():
            raise RuntimeError("vault init state file is missing; cannot unseal the restarted vault")
        init_payload = json.loads(self.vault_init_file.read_text(encoding="utf-8"))
        unseal_keys = init_payload.get("unseal_keys_b64", [])
        if not unseal_keys:
            raise RuntimeError("vault init state file does not contain an unseal key")

        status_output = self._compose("exec", "-T", "vault", "sh", "-lc", "VAULT_ADDR=http://127.0.0.1:8200 vault status -format=json")
        status_payload = json.loads(status_output)
        if not status_payload.get("sealed", False):
            return

        self._compose(
            "exec",
            "-T",
            "vault",
            "sh",
            "-lc",
            f"VAULT_ADDR=http://127.0.0.1:8200 vault operator unseal {unseal_keys[0]}",
        )
