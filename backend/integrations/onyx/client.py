from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from .types import (
    OnyxCapabilities,
    OnyxReadinessCheck,
    OnyxReadinessResponse,
    OnyxRiskSummary,
    ReadinessSeverity,
    ReadinessStatus,
    TrustEvidenceItem,
)

_ALLOWED_STATUS: set[str] = {"pass", "warn", "fail", "unknown"}
_ALLOWED_SEVERITY: set[str] = {"low", "medium", "high", "critical"}


class OnyxReadinessClient:
    def __init__(self) -> None:
        self.base_url = os.environ.get("ONYX_BASE_URL", "http://localhost:3000").strip().rstrip("/")
        self.readiness_path = os.environ.get("ONYX_READINESS_PATH", "/api/security/readiness").strip() or "/api/security/readiness"
        self.token = os.environ.get("ONYX_READINESS_TOKEN", "").strip()
        self.timeout_ms = _int_env("ONYX_READINESS_TIMEOUT_MS", 5000)
        self.enabled = _bool_env("ONYX_READINESS_ENABLED", True)

    def fetch(self) -> OnyxReadinessResponse:
        if not self.enabled:
            return degraded_response(message="Onyx readiness integration disabled")

        target = f"{self.base_url}/"
        path = self.readiness_path.lstrip("/")
        url = urljoin(target, path)
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        request = Request(url=url, method="GET", headers=headers)
        try:
            with urlopen(request, timeout=max(0.1, self.timeout_ms / 1000)) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (TimeoutError, URLError, HTTPError, json.JSONDecodeError, ValueError):
            return degraded_response(message="Onyx readiness endpoint unreachable")

        return normalize_onyx_response(payload)


def normalize_onyx_response(payload: object) -> OnyxReadinessResponse:
    if not isinstance(payload, dict):
        return degraded_response(message="Onyx readiness payload invalid")

    checks_raw = payload.get("checks", [])
    checks = [_normalize_check(item) for item in checks_raw if isinstance(item, dict)] if isinstance(checks_raw, list) else []

    return OnyxReadinessResponse(
        provider="onyx",
        system=str(payload.get("system") or "onyx007"),
        component_type=str(payload.get("component_type") or "rag_runtime"),
        environment=str(payload.get("environment") or "unknown"),
        generated_at=str(payload.get("generated_at") or ""),
        overall_status=_status(payload.get("overall_status")),
        overall_score=_bounded_score(payload.get("overall_score")),
        checks=checks,
        risk_summary=_normalize_risk_summary(payload.get("risk_summary")),
        capabilities=_normalize_capabilities(payload.get("capabilities")),
        message=str(payload.get("message") or ""),
        reachable=True,
    )


def degraded_response(*, message: str) -> OnyxReadinessResponse:
    return OnyxReadinessResponse(
        provider="onyx",
        system="onyx007",
        component_type="rag_runtime",
        environment="unknown",
        generated_at="",
        overall_status="unknown",
        overall_score=0,
        checks=[],
        risk_summary=OnyxRiskSummary(critical=0, high=0, medium=0, low=0),
        capabilities=OnyxCapabilities(rag=False, connectors=False, agents=False, mcp=False, tools=False),
        message=message,
        reachable=False,
    )


def _normalize_check(payload: dict[str, object]) -> OnyxReadinessCheck:
    evidence_payload = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    recommendation = str(payload.get("recommendation") or "")
    return OnyxReadinessCheck(
        id=str(payload.get("id") or "unknown.check"),
        category=str(payload.get("category") or "unknown"),
        title=str(payload.get("title") or "Untitled check"),
        status=_status(payload.get("status")),
        severity=_severity(payload.get("severity")),
        score=_bounded_score(payload.get("score")),
        description=str(payload.get("description") or ""),
        evidence=TrustEvidenceItem(
            source=str(evidence_payload.get("source") or "runtime"),
            value=str(evidence_payload.get("value") or ""),
            details=dict(evidence_payload.get("details") or {}),
        ),
        recommendation=recommendation,
    )


def _normalize_risk_summary(payload: object) -> OnyxRiskSummary:
    source = payload if isinstance(payload, dict) else {}
    return OnyxRiskSummary(
        critical=_int(source.get("critical"), 0),
        high=_int(source.get("high"), 0),
        medium=_int(source.get("medium"), 0),
        low=_int(source.get("low"), 0),
    )


def _normalize_capabilities(payload: object) -> OnyxCapabilities:
    source = payload if isinstance(payload, dict) else {}
    return OnyxCapabilities(
        rag=bool(source.get("rag", False)),
        connectors=bool(source.get("connectors", False)),
        agents=bool(source.get("agents", False)),
        mcp=bool(source.get("mcp", False)),
        tools=bool(source.get("tools", False)),
    )


def _status(value: object) -> ReadinessStatus:
    normalized = str(value or "unknown").strip().lower()
    return normalized if normalized in _ALLOWED_STATUS else "unknown"  # type: ignore[return-value]


def _severity(value: object) -> ReadinessSeverity:
    normalized = str(value or "low").strip().lower()
    return normalized if normalized in _ALLOWED_SEVERITY else "low"  # type: ignore[return-value]


def _bounded_score(value: object) -> int:
    return min(100, max(0, _int(value, 0)))


def _int(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    return _int(os.environ.get(name), default)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
