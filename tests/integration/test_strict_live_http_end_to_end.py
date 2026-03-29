from __future__ import annotations

import json
from pathlib import Path

import pytest

from .live_http_harness import LiveFixtureScenario, StrictLiveHarness


def _section(payload: dict, section_id: str) -> dict:
    return next(section for section in payload["sections"] if section["id"] == section_id)


def _cards(section: dict) -> dict[str, dict]:
    card_block = next(block for block in section["blocks"] if block["type"] == "cards")
    return {item["label"]: item for item in card_block["items"]}


def _assert_strict_live_acceptance(summary: dict) -> None:
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


def test_strict_live_handoff_passes_through_http_dependency_chain() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with StrictLiveHarness(repo_root, LiveFixtureScenario()) as harness:
        response = harness.launch(path="/app")
        assert response.status_code == 200
        assert "Governance Status:</strong> ✓ Approved" in response.text
        assert "Evidence mode: <code>live</code>" in response.text
        assert "Identity: Live" in response.text

        identity = harness.read_artifact("identity-evidence.json")
        policy = harness.read_artifact("policy-evidence.json")
        retrieval = harness.read_artifact("retrieval-evidence.json")
        secret = harness.read_artifact("secret-evidence.json")
        audit = harness.read_artifact("audit-records.jsonl", jsonl=True)
        trace = harness.read_artifact("trace-correlation.json")
        launch = harness.read_artifact("launch-gate-result.json")
        summary = harness.read_artifact("governed-flow-summary.json")

        _assert_strict_live_acceptance(summary)
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

        overview = harness.overview().json()
        assert overview["data_mode"]["label"] == "Live current evidence"
        assert overview["readiness_panel"]["status_label"] == "GO"
        identity_cards = _cards(_section(overview, "identity-session"))
        launch_cards = _cards(_section(overview, "launch-gate"))
        audit_cards = _cards(_section(overview, "audit-replay"))
        onyx_cards = _cards(_section(overview, "entry-points"))
        assert identity_cards["Identity result"]["value"] == "ALLOW"
        assert launch_cards["Evidence mode"]["value"] in {"live current evidence", "recent generated evidence"}
        assert audit_cards["Audit record source"]["value"] == "runtime-generated"
        assert onyx_cards["Latest handoff"]["value"] == "ALLOW"


@pytest.mark.parametrize(
    ("scenario", "token", "path", "expected_reason", "artifact_name", "artifact_field", "dashboard_section", "dashboard_card"),
    [
        (
            LiveFixtureScenario(),
            None,
            "/app",
            "identity.missing_bearer_token",
            "identity-evidence.json",
            "reason",
            "identity-session",
            "Identity result",
        ),
        (
            LiveFixtureScenario(),
            "invalid-live-token",
            "/app",
            "identity.keycloak_http_error:401",
            "identity-evidence.json",
            "reason",
            "identity-session",
            "Identity result",
        ),
        (
            LiveFixtureScenario(keycloak_mode="missing_tenant"),
            "valid-live-token",
            "/app",
            "identity.tenant_missing",
            "identity-evidence.json",
            "reason",
            "identity-session",
            "Identity result",
        ),
        (
            LiveFixtureScenario(keycloak_mode="unreachable"),
            "valid-live-token",
            "/app",
            "identity.keycloak_unreachable",
            "identity-evidence.json",
            "reason",
            "identity-session",
            "Identity result",
        ),
        (
            LiveFixtureScenario(opa_mode="unreachable"),
            "valid-live-token",
            "/app",
            "policy.opa_unavailable",
            "policy-evidence.json",
            "reason_codes",
            "policy-enforcement",
            "Latest policy result",
        ),
        (
            LiveFixtureScenario(opa_mode="deny"),
            "valid-live-token",
            "/app",
            "policy.opa_explicit_deny",
            "policy-evidence.json",
            "reason_codes",
            "policy-enforcement",
            "Latest policy result",
        ),
        (
            LiveFixtureScenario(qdrant_mode="unreachable"),
            "valid-live-token",
            "/app",
            "retrieval.backend_unavailable",
            "retrieval-evidence.json",
            "reason_codes",
            "retrieval-boundaries",
            "Latest retrieval result",
        ),
        (
            LiveFixtureScenario(qdrant_mode="empty"),
            "valid-live-token",
            "/app",
            "retrieval.empty_result",
            "retrieval-evidence.json",
            "reason_codes",
            "retrieval-boundaries",
            "Latest retrieval result",
        ),
        (
            LiveFixtureScenario(qdrant_mode="cross_tenant"),
            "valid-live-token",
            "/app",
            "retrieval.cross_tenant_filtered",
            "retrieval-evidence.json",
            "reason_codes",
            "retrieval-boundaries",
            "Latest retrieval result",
        ),
        (
            LiveFixtureScenario(vault_mode="unreachable"),
            "valid-live-token",
            "/app",
            "vault_unavailable",
            "secret-evidence.json",
            "reason",
            "secret-access",
            "Secret fetched",
        ),
        (
            LiveFixtureScenario(vault_mode="missing_key"),
            "valid-live-token",
            "/app",
            "secret_key_missing",
            "secret-evidence.json",
            "reason",
            "secret-access",
            "Secret fetched",
        ),
        (
            LiveFixtureScenario(secret_key=""),
            "valid-live-token",
            "/app",
            "invalid_secret_reference",
            "secret-evidence.json",
            "reason",
            "secret-access",
            "Secret fetched",
        ),
        (
            LiveFixtureScenario(keycloak_mode="no_session"),
            "valid-live-token",
            "/app",
            "launch_gate.no_go",
            "trace-correlation.json",
            "missing_steps",
            "trace-correlation",
            "Trace complete",
        ),
    ],
    ids=[
        "identity missing token",
        "identity invalid token",
        "identity tenant missing",
        "identity keycloak unreachable",
        "opa unreachable",
        "opa deny",
        "qdrant unavailable",
        "qdrant empty result",
        "cross-tenant retrieval",
        "vault unavailable",
        "secret key missing",
        "invalid secret reference",
        "trace incomplete",
    ],
)
def test_strict_live_handoff_fails_closed_for_dependency_breaks(
    scenario: LiveFixtureScenario,
    token: str | None,
    path: str,
    expected_reason: str,
    artifact_name: str,
    artifact_field: str,
    dashboard_section: str,
    dashboard_card: str,
) -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with StrictLiveHarness(repo_root, scenario) as harness:
        response = harness.launch(token=token, path=path)
        assert response.status_code == 403
        assert "Access Denied" in response.text
        assert expected_reason in response.text or "launch_gate.no_go" in response.text

        summary = harness.read_artifact("governed-flow-summary.json")
        artifact = harness.read_artifact(artifact_name)
        launch = harness.read_artifact("launch-gate-result.json")
        overview = harness.overview().json()
        overview_text = json.dumps(overview)

        assert summary["evidence_mode"] == "live"
        assert summary["handoff_allowed"] is False
        assert summary["decision"] is False
        assert expected_reason in json.dumps(summary)
        assert launch["machine"]["decision"] == "no_go"
        assert artifact_field in artifact
        assert expected_reason in json.dumps(artifact)
        assert expected_reason in overview_text or "Trace complete" in overview_text

        section_cards = _cards(_section(overview, dashboard_section))
        assert dashboard_card in section_cards
        assert section_cards[dashboard_card]["status"] in {"warning", "critical"}


def test_strict_live_dashboard_highlights_missing_live_evidence() -> None:
    repo_root = Path(__file__).resolve().parents[2]

    with StrictLiveHarness(repo_root, LiveFixtureScenario(keycloak_mode="no_session")) as harness:
        harness.launch(path="/app")
        overview = harness.overview().json()

        trace_cards = _cards(_section(overview, "trace-correlation"))
        launch_cards = _cards(_section(overview, "launch-gate"))
        onyx_cards = _cards(_section(overview, "entry-points"))

        assert trace_cards["Trace complete"]["value"] == "no"
        assert trace_cards["Missing steps"]["status"] in {"healthy", "critical"}
        assert launch_cards["Evidence mode"]["value"] == "live current evidence"
        assert launch_cards["Missing evidence"]["status"] == "critical"
        assert onyx_cards["Latest handoff"]["value"] == "DENY"
