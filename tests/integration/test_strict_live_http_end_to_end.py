from __future__ import annotations

from pathlib import Path

import pytest

from .live_stack_harness import LiveStackHarness


pytestmark = pytest.mark.live_stack


def _section(payload: dict, section_id: str) -> dict:
    return next(section for section in payload["sections"] if section["id"] == section_id)


def _cards(section: dict) -> dict[str, dict]:
    card_block = next(block for block in section["blocks"] if block["type"] == "cards")
    return {item["label"]: item for item in card_block["items"]}


def _assert_live_acceptance(summary: dict) -> None:
    assert summary["evidence_mode"] == "live"
    assert summary["identity"]["live"] is True
    assert summary["policy"]["engine"] == "opa"
    assert summary["policy"]["allow"] is True
    assert summary["retrieval"]["live_backend"] is True
    assert summary["retrieval"]["allow"] is True
    assert summary["secret"]["required"] is True
    assert summary["secret"]["fetched"] is True
    assert summary["trace"]["complete"] is True
    assert summary["launch_gate"]["decision"] == "pass"
    assert summary["handoff_allowed"] is True
    assert summary["decision"] is True


@pytest.fixture(scope="module")
def live_stack() -> LiveStackHarness:
    harness = LiveStackHarness(Path(__file__).resolve().parents[2])
    harness.require_ready()
    return harness


def test_strict_live_handoff_passes_through_real_stack(live_stack: LiveStackHarness) -> None:
    token = live_stack.mint_access_token()

    response = live_stack.launch(path="/app", token=token)
    assert response.status_code == 200
    assert "Governance Status:</strong> ✓ Approved" in response.text
    assert "Evidence mode: <code>live</code>" in response.text
    assert "Identity: Live" in response.text

    identity = live_stack.fetch_json_artifact("identity-evidence.json")
    policy = live_stack.fetch_json_artifact("policy-evidence.json")
    retrieval = live_stack.fetch_json_artifact("retrieval-evidence.json")
    secret = live_stack.fetch_json_artifact("secret-evidence.json")
    audit = live_stack.fetch_jsonl_artifact("audit-records.jsonl")
    trace = live_stack.fetch_json_artifact("trace-correlation.json")
    launch = live_stack.fetch_json_artifact("launch-gate-result.json")
    summary = live_stack.fetch_json_artifact("governed-flow-summary.json")
    runtime_proof = live_stack.fetch_json_artifact("onyx-runtime-proof.json")

    _assert_live_acceptance(summary)
    assert identity["source"] == "keycloak_userinfo"
    assert identity["handoff_allowed"] is True
    assert policy["engine"] == "opa"
    assert policy["handoff_allowed"] is True
    assert retrieval["backend"] == "qdrant"
    assert retrieval["result_count"] == 1
    assert secret["backend"] == "vault"
    assert audit
    assert any(record["stage"] == "handoff" for record in audit)
    assert trace["complete"] is True
    assert trace["audit_linkage"]["complete"] is True
    assert launch["machine"]["decision"] == "pass"
    assert launch["flow_metadata"]["handoff_allowed"] is True
    assert runtime_proof["trace_id"] == summary["trace_id"]
    assert runtime_proof["requested_path"] == "/app"
    assert summary["runtime_proof"]["artifact"].endswith("onyx-runtime-proof.json")
    assert summary["runtime_proof"]["continuity"]["label"]

    overview = live_stack.overview()
    assert overview["data_mode"]["label"] == "Live current evidence"
    assert overview["readiness_panel"]["status_label"] == "GO"
    identity_cards = _cards(_section(overview, "identity-session"))
    launch_cards = _cards(_section(overview, "launch-gate"))
    audit_cards = _cards(_section(overview, "audit-replay"))
    onyx_cards = _cards(_section(overview, "entry-points"))
    governed_requests = _section(overview, "governed-requests")
    governed_request_table = next(block for block in governed_requests["blocks"] if block["type"] == "table")
    assert identity_cards["Identity result"]["value"] == "ALLOW"
    assert launch_cards["Evidence mode"]["value"] in {"live current evidence", "recent generated evidence"}
    assert audit_cards["Audit record source"]["value"] == "runtime-generated"
    assert onyx_cards["Latest handoff"]["value"] == "ALLOW"
    assert governed_request_table["rows"][0]["mode"] == "live"
    assert governed_request_table["rows"][0]["trace"] == summary["trace_id"]


def test_strict_live_workspace_shell_embeds_runtime_when_reachable(live_stack: LiveStackHarness) -> None:
    token = live_stack.mint_access_token()

    response = live_stack.launch(path="/app", token=token, view="embedded")

    assert response.status_code == 200
    assert "Live Runtime Workspace" in response.text
    assert "Dashboard-owned live runtime" in response.text
    assert "Open in new tab" in response.text
    assert "Return to dashboard" in response.text
    assert 'src="' in response.text
    assert '/app"' in response.text
    assert 'title="Live Onyx runtime for /app"' in response.text
    assert "Trace ID" in response.text
    assert "Current Onyx Activity" in response.text
    assert "Open activity API" in response.text


def test_strict_live_handoff_denies_without_token(live_stack: LiveStackHarness) -> None:
    response = live_stack.launch(path="/app", token=None)

    assert response.status_code == 403
    assert "identity.missing_bearer_token" in response.text

    identity = live_stack.fetch_json_artifact("identity-evidence.json")
    assert identity["reason"] == "identity.missing_bearer_token"


def test_strict_live_handoff_denies_with_invalid_token(live_stack: LiveStackHarness) -> None:
    response = live_stack.launch(path="/app", token="invalid-live-token")

    assert response.status_code == 403
    assert "identity.keycloak_http_error:401" in response.text

    identity = live_stack.fetch_json_artifact("identity-evidence.json")
    assert identity["reason"] == "identity.keycloak_http_error:401"


def test_strict_live_handoff_fails_closed_when_keycloak_is_unavailable(live_stack: LiveStackHarness) -> None:
    token = live_stack.mint_access_token()

    with live_stack.service_unavailable("keycloak"):
        response = live_stack.launch(path="/app", token=token)
        assert response.status_code == 403
        assert "identity.keycloak_unreachable" in response.text

    summary = live_stack.fetch_json_artifact("governed-flow-summary.json")
    assert "identity.keycloak_unreachable" in summary["reasons"]


def test_strict_live_handoff_fails_closed_when_opa_is_unavailable(live_stack: LiveStackHarness) -> None:
    token = live_stack.mint_access_token()

    with live_stack.service_unavailable("opa"):
        response = live_stack.launch(path="/app", token=token)
        assert response.status_code == 403
        assert "policy.opa_unavailable" in response.text

    policy = live_stack.fetch_json_artifact("policy-evidence.json")
    summary = live_stack.fetch_json_artifact("governed-flow-summary.json")
    assert "policy.opa_unavailable" in policy["reason_codes"]
    assert "policy.opa_unavailable" in summary["reasons"]


def test_strict_live_handoff_fails_closed_when_qdrant_is_unavailable(live_stack: LiveStackHarness) -> None:
    token = live_stack.mint_access_token()

    with live_stack.service_unavailable("qdrant"):
        response = live_stack.launch(path="/app", token=token)
        assert response.status_code == 403
        assert "retrieval.backend_unavailable" in response.text

    retrieval = live_stack.fetch_json_artifact("retrieval-evidence.json")
    summary = live_stack.fetch_json_artifact("governed-flow-summary.json")
    assert "retrieval.backend_unavailable" in retrieval["reason_codes"]
    assert "retrieval.backend_unavailable" in summary["reasons"]


def test_strict_live_handoff_fails_closed_when_vault_is_unavailable(live_stack: LiveStackHarness) -> None:
    token = live_stack.mint_access_token()

    with live_stack.service_unavailable("vault"):
        response = live_stack.launch(path="/app", token=token)
        assert response.status_code == 403
        assert "vault_unavailable" in response.text

    secret = live_stack.fetch_json_artifact("secret-evidence.json")
    summary = live_stack.fetch_json_artifact("governed-flow-summary.json")
    assert secret["reason"] == "vault_unavailable"
    assert "vault_unavailable" in summary["reasons"]
