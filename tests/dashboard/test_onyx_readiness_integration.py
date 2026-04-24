from __future__ import annotations

import json
from pathlib import Path
from urllib.error import URLError

from backend.integrations.onyx.client import OnyxReadinessClient, normalize_onyx_response
from backend.integrations.onyx.mapper import derive_launch_gate_decision, map_to_launch_gates
from backend.posture_service.service import build_control_plane_dashboard


def _load_fixture(name: str) -> dict:
    return json.loads((Path("fixtures") / name).read_text(encoding="utf-8"))


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return None


def test_onyx_client_success(monkeypatch) -> None:
    payload = _load_fixture("onyx-readiness-pass.json")

    monkeypatch.setenv("ONYX_READINESS_ENABLED", "true")
    monkeypatch.setattr("backend.integrations.onyx.client.urlopen", lambda request, timeout=0: _FakeResponse(payload))

    response = OnyxReadinessClient().fetch()

    assert response.system == "onyx007"
    assert response.overall_status == "pass"
    assert response.overall_score == 92
    assert response.checks[0].status == "pass"


def test_onyx_client_unreachable(monkeypatch) -> None:
    monkeypatch.setattr("backend.integrations.onyx.client.urlopen", lambda request, timeout=0: (_ for _ in ()).throw(URLError("down")))

    response = OnyxReadinessClient().fetch()

    assert response.overall_status == "unknown"
    assert response.overall_score == 0
    assert response.message == "Onyx readiness endpoint unreachable"


def test_onyx_response_mapping_and_categories() -> None:
    readiness = normalize_onyx_response(_load_fixture("onyx-readiness-fail.json"))
    mapped = map_to_launch_gates(readiness)
    by_name = {item.name: item for item in mapped.categories}

    assert by_name["Identity & Access"].status == "fail"
    assert "Authentication enabled" in by_name["Identity & Access"].failed_checks
    assert by_name["Telemetry & Auditability"].status == "warn"


def test_launch_gate_decision_logic() -> None:
    passing = normalize_onyx_response(_load_fixture("onyx-readiness-pass.json"))
    failing = normalize_onyx_response(_load_fixture("onyx-readiness-fail.json"))

    assert derive_launch_gate_decision(passing) == "APPROVED"
    assert derive_launch_gate_decision(failing) == "BLOCKED"


def test_dashboard_includes_onyx_security_readiness_states(monkeypatch) -> None:
    payload = _load_fixture("onyx-readiness-fail.json")
    monkeypatch.setattr("backend.integrations.onyx.client.urlopen", lambda request, timeout=0: _FakeResponse(payload))

    dashboard = build_control_plane_dashboard()
    section = next(item for item in dashboard["sections"] if item["id"] == "entry-points")
    readiness_block = next(block for block in section["blocks"] if block["title"] == "Onyx Security Readiness")
    checks_table = next(block for block in section["blocks"] if block["title"] == "Onyx detailed readiness checks")

    statuses = {row["status"] for row in checks_table["rows"]}
    assert readiness_block["items"][0]["label"] == "Launch Gate"
    assert dashboard["onyx_security_readiness"]["launch_gate_decision"] == "BLOCKED"
    assert {"FAIL", "WARN"} <= statuses

    unknown_payload = _load_fixture("onyx-readiness-fail.json")
    unknown_payload["overall_status"] = "unknown"
    unknown_payload["checks"][0]["status"] = "unknown"
    unknown_payload["checks"][1]["status"] = "unknown"
    monkeypatch.setattr("backend.integrations.onyx.client.urlopen", lambda request, timeout=0: _FakeResponse(unknown_payload))

    dashboard_unknown = build_control_plane_dashboard()
    unknown_table = next(
        block
        for block in next(item for item in dashboard_unknown["sections"] if item["id"] == "entry-points")["blocks"]
        if block["title"] == "Onyx detailed readiness checks"
    )
    assert {row["status"] for row in unknown_table["rows"]} == {"UNKNOWN"}
