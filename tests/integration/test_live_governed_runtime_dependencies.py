from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from adapters.identity.keycloak import KeycloakIdentityProvider
from adapters.policy.opa import OPAClient, OPAPolicyChecker
from adapters.retrieval.qdrant import QdrantRetrievalBackend
from adapters.secrets.provider import VaultSecretsProvider
from adapters.secrets.vault import VaultHTTPClient
from adapters.tools.policy_model import StaticToolPolicyEvaluator
from backend.api_gateway.server import (
    RuntimeRetrievalChecker,
    RuntimeRetrievalPolicy,
    RuntimeToolChecker,
    RuntimeToolExecutor,
    _runtime_policy_context,
    _runtime_tool_policy_config,
)
from backend.governance_flow_evaluator import GovernedFlowEvaluator
from backend.launch_gate_service.service import build_launch_gate_summary


class FakeHTTPResponse:
    def __init__(self, payload: dict):
        self._payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _http_error(url: str, code: int) -> HTTPError:
    return HTTPError(url, code, "error", hdrs=None, fp=io.BytesIO(b'{"error":"failed"}'))


def _mock_urlopen_factory(
    *,
    include_session: bool = True,
    opa_enabled: bool = True,
    qdrant_enabled: bool = True,
    vault_enabled: bool = True,
):
    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        url = request.full_url if hasattr(request, "full_url") else str(request)
        headers = {str(key).lower(): value for key, value in dict(getattr(request, "headers", {})).items()}

        if url.endswith("/protocol/openid-connect/userinfo"):
            token = headers.get("authorization", "").removeprefix("Bearer ").strip()
            if token != "valid-live-token":
                raise _http_error(url, 401)
            payload = {
                "sub": "tenant-admin-1",
                "tenant_id": "tenant-dashboard",
                "realm_access": {"roles": ["tenant_admin"]},
            }
            if include_session:
                payload["sid"] = "kc-session-123"
            return FakeHTTPResponse(payload)

        if url.endswith("/v1/data/umbrella/policy/decision"):
            if not opa_enabled:
                raise _http_error(url, 503)
            return FakeHTTPResponse(
                {
                    "result": {
                        "allow": True,
                        "matched_surface": "onyx.chat",
                        "reason_codes": ["policy.allow"],
                    }
                }
            )

        if url.endswith("/collections/governed_docs/points/scroll"):
            if not qdrant_enabled:
                raise _http_error(url, 503)
            return FakeHTTPResponse(
                {
                    "result": {
                        "points": [
                            {
                                "id": "launch-doc-1",
                                "payload": {
                                    "tenant_id": "tenant-dashboard",
                                    "source": "qdrant",
                                    "content": "Navigate to Onyx path: /app launch context",
                                    "trust_label": "trusted",
                                    "quarantined": False,
                                    "provenance": {"uri": "kb://launch-doc-1"},
                                },
                            }
                        ]
                    }
                }
            )

        if "/v1/secret/data/dev/tenant-dashboard/runtime" in url:
            if not vault_enabled:
                raise _http_error(url, 503)
            if headers.get("x-vault-token", "") != "root-token":
                raise _http_error(url, 403)
            return FakeHTTPResponse({"data": {"data": {"api_token": "runtime-secret"}}})

        raise AssertionError(f"Unexpected urlopen call: {url}")

    return fake_urlopen


def _build_live_evaluator(
    *,
    include_session: bool = True,
    opa_enabled: bool = True,
    vault_enabled: bool = True,
    artifact_dir: Path,
) -> GovernedFlowEvaluator:
    policy_context = _runtime_policy_context()
    secret_provider = None
    if vault_enabled:
        secret_provider = VaultSecretsProvider(VaultHTTPClient(base_url="http://vault.test", token="root-token"))
    return GovernedFlowEvaluator(
        policy_checker=OPAPolicyChecker(
            client=OPAClient("http://opa.test"),
            package_path="umbrella/policy/decision",
            runtime_policy=policy_context.document,
            environment_mode="prod-sim",
        ),
        retrieval_checker=RuntimeRetrievalChecker(policy_context),
        tool_checker=RuntimeToolChecker(policy_context),
        retrieval_backend=QdrantRetrievalBackend(base_url="http://qdrant.test", collection="governed_docs"),
        retrieval_policy=RuntimeRetrievalPolicy(policy_context),
        tool_executor=RuntimeToolExecutor(policy_context),
        tool_policy_evaluator=StaticToolPolicyEvaluator(_runtime_tool_policy_config(policy_context)),
        artifact_dir=artifact_dir,
        identity_provider=KeycloakIdentityProvider("http://keycloak.test/realms/umbrella-dev/protocol/openid-connect/userinfo"),
        secret_provider=secret_provider,
        flow_mode="live",
        environment_mode="prod-sim",
    )


def _run_live_flow(
    *,
    include_session: bool = True,
    opa_enabled: bool = True,
    qdrant_enabled: bool = True,
    vault_enabled: bool = True,
    with_token: bool = True,
):
    with tempfile.TemporaryDirectory() as tmpdir:
        artifact_dir = Path(tmpdir)
        evaluator = _build_live_evaluator(
            include_session=include_session,
            opa_enabled=opa_enabled,
            vault_enabled=vault_enabled,
            artifact_dir=artifact_dir,
        )
        fake_urlopen = _mock_urlopen_factory(
            include_session=include_session,
            opa_enabled=opa_enabled,
            qdrant_enabled=qdrant_enabled,
            vault_enabled=vault_enabled,
        )
        with (
            patch("adapters.identity.keycloak.urlopen", side_effect=fake_urlopen),
            patch("adapters.policy.opa.urlopen", side_effect=fake_urlopen),
            patch("adapters.retrieval.qdrant.urlopen", side_effect=fake_urlopen),
            patch("adapters.secrets.vault.urlopen", side_effect=fake_urlopen),
        ):
            result = evaluator.run(
                user_id="dashboard-user",
                tenant_id="tenant-dashboard",
                prompt="Navigate to Onyx path: /app",
                requested_tools=["onyx"],
                retrieval_source="qdrant",
                retrieval_needed=True,
                roles=["tenant_user"],
                request_metadata={"requested_path": "/app", "surface": "onyx.chat", "surface_query": {}},
                tool_arguments={"onyx": {"path": "/app", "surface": "onyx.chat"}},
                policy_source="overlay",
                policy_path="overlays/myStarterKit/policies/bundles/default/policy.json",
                authorization_header="Bearer valid-live-token" if with_token else "",
                cookies={},
                evidence_mode="live",
                secret_request={
                    "needed": True,
                    "secret_path": "secret/data/dev/tenant-dashboard/runtime",
                    "secret_key": "api_token",
                    "purpose": "onyx_runtime_handoff",
                },
            )
        summary = json.loads((artifact_dir / "governed-flow-summary.json").read_text(encoding="utf-8"))
        return result, summary


def test_live_handoff_uses_mandatory_runtime_dependencies():
    result, summary = _run_live_flow()

    assert result.decision is True
    assert summary["evidence_mode"] == "live"
    assert summary["identity"]["live"] is True
    assert summary["policy"]["engine"] == "opa"
    assert summary["retrieval"]["live_backend"] is True
    assert summary["secret"]["fetched"] is True
    assert summary["trace"]["complete"] is True
    assert summary["trace"]["audit_linkage"]["complete"] is True
    assert summary["audit"]["record_count"] >= 8
    assert summary["launch_gate"]["decision"] == "pass"


def test_live_handoff_denies_without_keycloak_identity():
    result, summary = _run_live_flow(with_token=False)

    assert result.decision is False
    assert summary["identity"]["authenticated"] is False
    assert summary["launch_gate"]["decision"] == "no_go"


def test_live_handoff_denies_when_opa_unavailable():
    result, summary = _run_live_flow(opa_enabled=False)

    assert result.decision is False
    assert summary["policy"]["allow"] is False
    assert "policy.opa_unavailable" in summary["reasons"]


def test_live_handoff_denies_when_retrieval_backend_unavailable():
    result, summary = _run_live_flow(qdrant_enabled=False)

    assert result.decision is False
    assert summary["retrieval"]["allow"] is False
    assert "retrieval.backend_unavailable" in summary["reasons"]


def test_live_handoff_denies_when_secret_backend_unavailable():
    result, summary = _run_live_flow(vault_enabled=False)

    assert result.decision is False
    assert summary["secret"]["required"] is True
    assert summary["secret"]["fetched"] is False


def test_live_handoff_trace_breakage_causes_launch_gate_no_go():
    result, summary = _run_live_flow(include_session=False)

    assert result.decision is False
    assert summary["trace"]["complete"] is False
    assert summary["trace"]["session_linkage"]["reason"]
    assert summary["launch_gate"]["decision"] == "no_go"


def test_launch_gate_summary_prefers_live_artifacts_when_live_mode_enabled():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "launch-gate").mkdir(parents=True, exist_ok=True)
        (root / "launch-gate" / "evaluator.py").write_text(
            Path(__file__).resolve().parents[2].joinpath("launch-gate/evaluator.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        artifact_dir = root / "overlays" / "myStarterKit" / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=True)
        (artifact_dir / "governed-flow-summary.json").write_text(
            json.dumps(
                {
                    "evidence_mode": "live",
                    "launch_gate": {
                        "decision": "no_go",
                        "score_percent": 40,
                        "control_coverage": "2/5",
                        "findings": [{"control": "trace_correlation", "status": "fail"}],
                        "residual_risks": ["missing:trace.correlation"],
                    },
                }
            ),
            encoding="utf-8",
        )
        (artifact_dir / "launch-gate-result.json").write_text(
            json.dumps({"machine": {"decision": "no_go", "missing_evidence": ["trace.correlation"], "blockers": ["mandatory_control_missing:trace_correlation"]}}),
            encoding="utf-8",
        )

        summary = build_launch_gate_summary(root)
        assert summary["evidence_mode"] == "live"
        assert summary["status"] == "no-go"
        assert "trace.correlation" in summary["missing_controls"]


def test_launch_gate_summary_fails_closed_without_live_evidence(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "launch-gate").mkdir(parents=True, exist_ok=True)
        (root / "launch-gate" / "evaluator.py").write_text(
            Path(__file__).resolve().parents[2].joinpath("launch-gate/evaluator.py").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")

        summary = build_launch_gate_summary(root)

        assert summary["evidence_mode"] == "live"
        assert summary["status"] == "no-go"
        assert "identity.live" in summary["missing_controls"]
