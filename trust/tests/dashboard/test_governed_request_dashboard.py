from __future__ import annotations

import json
from pathlib import Path

from adapters.identity.interfaces import IdentityProvider
from adapters.identity.schemas import IdentityResolutionRequest, IdentityResolutionResult
from adapters.onyx_gateway_adapter.interfaces import PolicyChecker, RetrievalChecker, ToolDecisionChecker
from adapters.onyx_gateway_adapter.schemas import NormalizedRequest, PolicyDecision, RetrievalDecision, ToolDecision
from adapters.retrieval.interfaces import RetrievalBackend, RetrievalPolicyEvaluator
from adapters.retrieval.schemas import RetrievalDocument, RetrievalRequest
from adapters.tools.interfaces import ToolExecutor
from adapters.tools.schemas import ToolActionRequest
from backend.governance_flow_evaluator import GovernedFlowEvaluator
from backend.posture_service.service import build_control_plane_dashboard


class AllowPolicy(PolicyChecker):
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        return PolicyDecision(allow=True, reasons=["policy.allow"])


class LiveAllowPolicy(AllowPolicy):
    def decision_metadata(self) -> dict[str, object]:
        return {"engine": "opa", "reachable": True, "matched_surface": "onyx.chat"}


class DenyPolicy(PolicyChecker):
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        return PolicyDecision(allow=False, reasons=["policy.denied"])


class AllowRetrieval(RetrievalChecker):
    def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
        return RetrievalDecision(allow=True, reasons=["retrieval.allow"])


class AllowTools(ToolDecisionChecker):
    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        return ToolDecision(allowed_tools=request.requested_tools, denied_tools=[], reasons=[])


class StubRetrievalBackend(RetrievalBackend):
    def search(self, request: RetrievalRequest):
        return [
            RetrievalDocument(
                doc_id="doc-1",
                tenant_id=request.tenant_id,
                source=request.source,
                content="Governed request evidence document.",
                trust_label="trusted",
                quarantined=False,
                provenance={"uri": "kb://doc-1"},
            )
        ]


class AllowRetrievalPolicy(RetrievalPolicyEvaluator):
    def evaluate(self, request: RetrievalRequest) -> dict[str, object]:
        return {"allow": True, "mode": "allow", "reasons": ["retrieval.allow"]}


class StubToolExecutor(ToolExecutor):
    def execute(self, request: ToolActionRequest) -> dict[str, str]:
        return {"result": "executed", "tool": request.tool_name}


class LiveIdentityProvider(IdentityProvider):
    def resolve(self, request: IdentityResolutionRequest) -> IdentityResolutionResult:
        return IdentityResolutionResult(
            authenticated=True,
            live=True,
            source="test.live_identity",
            user_id=request.fallback_user_id,
            tenant_id=request.fallback_tenant_id,
            roles=list(request.fallback_roles),
            session_id="live-session-123",
            token_present=True,
            token_active=True,
            reason="identity.live_ok",
            metadata={"requested_path": request.requested_path},
        )


def _seed_dashboard_root(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    for relative in ("contracts", "compose", "docs", "evidence", "launch-gate", "telemetry", "upstream"):
        source = repo_root / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.symlink_to(source, target_is_directory=True)

    policies_source = repo_root / "overlays" / "myStarterKit" / "policies"
    policies_target = tmp_path / "overlays" / "myStarterKit" / "policies"
    policies_target.parent.mkdir(parents=True, exist_ok=True)
    policies_target.symlink_to(policies_source, target_is_directory=True)

    (tmp_path / "overlays" / "myStarterKit" / "artifacts").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _run_flow(
    artifact_dir: Path,
    *,
    prompt: str,
    flow_mode: str = "demo",
    policy_checker: PolicyChecker | None = None,
    identity_provider: IdentityProvider | None = None,
) -> None:
    evaluator = GovernedFlowEvaluator(
        policy_checker=policy_checker or AllowPolicy(),
        retrieval_checker=AllowRetrieval(),
        tool_checker=AllowTools(),
        retrieval_backend=StubRetrievalBackend(),
        retrieval_policy=AllowRetrievalPolicy(),
        tool_executor=StubToolExecutor(),
        artifact_dir=artifact_dir,
        identity_provider=identity_provider,
        flow_mode=flow_mode,
        environment_mode="test",
    )
    evaluator.run(
        user_id="dashboard-user",
        tenant_id="tenant-dashboard",
        prompt=prompt,
        requested_tools=["search"],
        retrieval_source="qdrant",
        retrieval_needed=(flow_mode == "live"),
        roles=["tenant_user"],
        request_metadata={"requested_path": "/app", "surface": "onyx.chat", "surface_query": {}},
        tool_arguments={"search": {"query": prompt}},
        policy_source="overlay",
        policy_path="overlays/myStarterKit/policies/bundles/default/policy.json",
        evidence_mode=flow_mode,
    )


def _latest_governed_request(payload: dict[str, object]) -> dict[str, object]:
    command_center = payload.get("command_center", {})
    if not isinstance(command_center, dict):
        return {}
    latest_request = command_center.get("latest_request", {})
    return latest_request if isinstance(latest_request, dict) else {}


def test_dashboard_shows_sanitized_governed_request_preview(tmp_path: Path) -> None:
    root = _seed_dashboard_root(tmp_path)
    artifact_dir = root / "overlays" / "myStarterKit" / "artifacts"

    _run_flow(
        artifact_dir,
        prompt="Summarize governed launch readiness blockers for tenant dashboard reviewers.",
    )

    payload = build_control_plane_dashboard(root)
    latest_request = _latest_governed_request(payload)

    assert latest_request["title"].startswith("Summarize governed launch readiness blockers")
    fields = {field["label"]: field["value"] for field in latest_request.get("display_fields", [])}
    assert fields["Proof mode"] == "Demo"
    assert fields["Decision"] == "Allowed"


def test_dashboard_redacts_sensitive_request_preview_and_keeps_secret_out_of_payload(tmp_path: Path) -> None:
    root = _seed_dashboard_root(tmp_path)
    artifact_dir = root / "overlays" / "myStarterKit" / "artifacts"
    raw_secret = "sk-ABCDEF1234567890ABCDEF1234567890"

    _run_flow(
        artifact_dir,
        prompt=f"Debug access with token={raw_secret} and summarize the failure path.",
    )

    payload = build_control_plane_dashboard(root)
    latest_request = _latest_governed_request(payload)
    dashboard_text = json.dumps(latest_request)
    feed_text = (artifact_dir / "governed-request-feed.json").read_text(encoding="utf-8")

    assert "[REDACTED" in dashboard_text
    assert raw_secret not in dashboard_text
    assert raw_secret not in feed_text


def test_governed_request_feed_keeps_denies_distinguishes_modes_and_links_history(tmp_path: Path) -> None:
    root = _seed_dashboard_root(tmp_path)
    artifact_dir = root / "overlays" / "myStarterKit" / "artifacts"

    _run_flow(
        artifact_dir,
        prompt="Show blocked governed request for denied policy evidence.",
        policy_checker=DenyPolicy(),
    )
    _run_flow(
        artifact_dir,
        prompt="Review recent governed request evidence for live runtime launch.",
        flow_mode="live",
        policy_checker=LiveAllowPolicy(),
        identity_provider=LiveIdentityProvider(),
    )

    feed = json.loads((artifact_dir / "governed-request-feed.json").read_text(encoding="utf-8"))
    modes = {item["evidence_mode"] for item in feed}
    denied = next(item for item in feed if item["handoff_allowed"] is False)

    assert {"demo", "live"} <= modes
    assert "policy.denied" in denied["reason_codes"]
    assert denied["question_preview"].startswith("Show blocked governed request")

    for ref in denied["artifact_refs"].values():
        assert Path(ref).exists()

    summary_path = Path(denied["artifact_refs"]["governed_flow_summary"])
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert summary["trace_id"] == denied["trace_id"]
    assert summary["question_preview"] == denied["question_preview"]
