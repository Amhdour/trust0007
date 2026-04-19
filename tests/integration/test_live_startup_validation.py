from __future__ import annotations

import pytest

from backend.api_gateway import server


def test_live_startup_validation_fails_for_dev_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")
    monkeypatch.setenv("CONTROL_PLANE_ENVIRONMENT_MODE", "dev")
    monkeypatch.setenv("CONTROL_PLANE_VAULT_TOKEN", "token")
    monkeypatch.setenv("CONTROL_PLANE_ONYX_SECRET_PATH", "secret/data/runtime/tenant-stage/onyx")
    monkeypatch.setenv("CONTROL_PLANE_DIFY_SECRET_PATH", "secret/data/runtime/tenant-stage/dify")
    monkeypatch.setenv("CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS", "true")

    with pytest.raises(RuntimeError, match="environment_mode_dev_not_allowed"):
        server._validate_startup_configuration()


def test_live_startup_validation_fails_without_required_live_secret_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")
    monkeypatch.setenv("CONTROL_PLANE_ENVIRONMENT_MODE", "staging")
    monkeypatch.setenv("CONTROL_PLANE_VAULT_TOKEN", "token")
    monkeypatch.setenv("CONTROL_PLANE_ONYX_SECRET_PATH", "secret/data/runtime/tenant-stage/onyx")
    monkeypatch.delenv("CONTROL_PLANE_DIFY_SECRET_PATH", raising=False)
    monkeypatch.setenv("CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS", "true")

    with pytest.raises(RuntimeError, match="missing_required_env:CONTROL_PLANE_DIFY_SECRET_PATH"):
        server._validate_startup_configuration()


def test_live_startup_validation_passes_with_hardened_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CONTROL_PLANE_GOVERNANCE_MODE", "live")
    monkeypatch.setenv("CONTROL_PLANE_ENVIRONMENT_MODE", "staging")
    monkeypatch.setenv("CONTROL_PLANE_VAULT_TOKEN", "token")
    monkeypatch.setenv("CONTROL_PLANE_ONYX_SECRET_PATH", "secret/data/runtime/tenant-stage/onyx")
    monkeypatch.setenv("CONTROL_PLANE_DIFY_SECRET_PATH", "secret/data/runtime/tenant-stage/dify")
    monkeypatch.setenv("CONTROL_PLANE_ALLOW_LOCAL_RUNTIME_TARGETS", "true")
    monkeypatch.setenv("CONTROL_PLANE_EXTERNAL_REACHABLE", "false")
    monkeypatch.setenv("CONTROL_PLANE_KEYCLOAK_DEV_MODE", "false")
    monkeypatch.setenv("CONTROL_PLANE_VAULT_DEV_MODE", "false")
    monkeypatch.setenv("CONTROL_PLANE_KEYCLOAK_BASE_URL", "http://keycloak:8080")
    monkeypatch.setenv("CONTROL_PLANE_OPA_URL", "http://opa:8181")
    monkeypatch.setenv("CONTROL_PLANE_QDRANT_URL", "http://qdrant:6333")

    server._validate_startup_configuration()
