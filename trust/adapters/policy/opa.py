from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from adapters.onyx_gateway_adapter.interfaces import PolicyChecker
from adapters.onyx_gateway_adapter.schemas import NormalizedRequest, PolicyDecision


class OPAClient:
    def __init__(self, base_url: str, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    def evaluate(self, package_path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(
            f"{self._base_url}/v1/data/{package_path.lstrip('/')}",
            data=json.dumps({"input": payload}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self._timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        result = body.get("result")
        return result if isinstance(result, dict) else {}


class OPAPolicyChecker(PolicyChecker):
    """Policy checker that routes request evaluation through a live OPA endpoint."""

    def __init__(self, client: OPAClient, package_path: str, runtime_policy: dict[str, Any], environment_mode: str) -> None:
        self._client = client
        self._package_path = package_path.strip("/")
        self._runtime_policy = runtime_policy
        self._environment_mode = environment_mode
        self._last_metadata: dict[str, Any] = {}

    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        payload = {
            "tenant_id": request.tenant_id,
            "user_id": request.user_id,
            "prompt": request.prompt,
            "requested_tools": list(request.requested_tools),
            "retrieval": {
                "needed": request.retrieval_needed,
                "source": request.retrieval_source,
            },
            "metadata": request.metadata,
            "identity": {
                "roles": list(request.metadata.get("identity_roles", [])),
                "subject": request.user_id,
                "tenant_id": request.tenant_id,
                "session_id": str(request.metadata.get("session_id", "")),
                "source": str(request.metadata.get("identity_source", "")),
            },
            "request": {
                "path": str(request.metadata.get("requested_path", "")),
                "surface": str(request.metadata.get("surface", "")),
                "query": dict(request.metadata.get("surface_query", {})),
                "tool_arguments": dict(request.metadata.get("tool_arguments", {})),
                "environment_mode": self._environment_mode,
                "evidence_mode": str(request.metadata.get("evidence_mode", "")),
            },
            "runtime_policy": self._runtime_policy,
        }

        try:
            result = self._client.evaluate(self._package_path, payload)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            self._last_metadata = {
                "engine": "opa",
                "package_path": self._package_path,
                "reachable": False,
                "error": type(exc).__name__,
            }
            return PolicyDecision(allow=False, reasons=["policy.opa_unavailable"])

        allow = bool(result.get("allow", False))
        reasons = [str(reason) for reason in result.get("reason_codes", result.get("reasons", [])) if str(reason)]
        if not reasons:
            reasons = ["policy.allow"] if allow else ["policy.default_deny"]

        self._last_metadata = {
            "engine": "opa",
            "package_path": self._package_path,
            "reachable": True,
            "matched_surface": str(result.get("matched_surface", "")),
            "environment_mode": self._environment_mode,
        }
        return PolicyDecision(allow=allow, reasons=reasons)

    def decision_metadata(self) -> dict[str, Any]:
        return dict(self._last_metadata)
