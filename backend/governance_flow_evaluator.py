"""Composable governed-flow evaluator with demo and live evidence modes."""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from adapters.identity.interfaces import IdentityProvider
from adapters.identity.schemas import IdentityResolutionRequest, IdentityResolutionResult
from adapters.onyx_gateway_adapter.adapter import OnyxGatewayAdapter
from adapters.onyx_gateway_adapter.interfaces import PolicyChecker, RetrievalChecker, ToolDecisionChecker
from adapters.onyx_gateway_adapter.schemas import NormalizedRequest
from adapters.onyx_gateway_adapter.telemetry import InMemoryTelemetryEmitter
from adapters.retrieval.engine import RetrievalSecurityLayer
from adapters.retrieval.interfaces import InMemoryRetrievalTelemetry, RetrievalBackend, RetrievalPolicyEvaluator
from adapters.retrieval.schemas import RetrievalRequest
from adapters.secrets.provider import VaultSecretsProvider
from adapters.secrets.schemas import SecretFetchRequest
from adapters.tools.engine import ToolGovernanceEngine
from adapters.tools.interfaces import InMemoryAuditSink, ToolExecutor, ToolPolicyEvaluator
from adapters.tools.policy_model import StaticToolPolicyEvaluator, default_policy_config
from adapters.tools.schemas import ToolActionRequest
from backend.governed_request_telemetry import (
    append_governed_request_feed,
    sanitize_question,
    write_history_artifacts,
)
from telemetry.model import EventModel
from telemetry.sinks import JsonlEventSink


def _load_launch_gate_module():
    module_path = Path(__file__).resolve().parent.parent / "launch-gate" / "evaluator.py"
    spec = importlib.util.spec_from_file_location("governed_flow_launch_gate", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load launch gate evaluator from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


LAUNCH_GATE = _load_launch_gate_module()


def _artifact_reference(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True))
        handle.write("\n")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _surface_identifier(base_metadata: dict[str, Any], requested_path: str) -> str:
    return str(base_metadata.get("surface", "")).strip() or requested_path


def _session_linkage(identity_result: IdentityResolutionResult, *, live_mode: bool) -> tuple[str, str]:
    if identity_result.session_id:
        return "linked", "session propagated from the identity authority"
    if not identity_result.authenticated:
        return "unavailable", "identity failed before a session identifier could be established"
    if not identity_result.live:
        return "unavailable", "demo or fallback identity path does not issue a live session identifier"
    if identity_result.source == "keycloak_userinfo":
        return "unavailable", "Keycloak userinfo response did not include sid or session_state"
    return "unavailable", f"{identity_result.source or 'identity source'} did not provide session context"


def _metadata_for(component: Any) -> dict[str, Any]:
    if hasattr(component, "decision_metadata"):
        metadata = component.decision_metadata()
        if isinstance(metadata, dict):
            return metadata
    if hasattr(component, "last_query_metadata"):
        metadata = component.last_query_metadata()
        if isinstance(metadata, dict):
            return metadata
    return {}


@dataclass
class GovernedFlowResult:
    decision: bool
    trace_id: str
    request_id: str
    session_id: str
    reasons: list[str]
    policy_allow: bool
    retrieval_allow: bool
    allowed_tools: list[str]
    denied_tools: list[str]
    launch_gate_decision: str
    launch_gate_score: int
    launch_gate_max_score: int
    launch_gate_blockers: list[str]
    launch_gate_missing_evidence: list[str]
    policy_source: str
    policy_path: str
    evidence_mode: str
    artifacts: dict[str, str]
    governed_request: dict[str, Any] = field(default_factory=dict)
    dependency_status: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "session_id": self.session_id,
            "reasons": self.reasons,
            "governance": {
                "policy_allow": self.policy_allow,
                "retrieval_allow": self.retrieval_allow,
                "allowed_tools": self.allowed_tools,
                "denied_tools": self.denied_tools,
            },
            "launch_gate": {
                "decision": self.launch_gate_decision,
                "score": self.launch_gate_score,
                "max_score": self.launch_gate_max_score,
                "blockers": self.launch_gate_blockers,
                "missing_evidence": self.launch_gate_missing_evidence,
            },
            "policy_bundle": {
                "source": self.policy_source,
                "path": self.policy_path,
            },
            "evidence_mode": self.evidence_mode,
            "governed_request": self.governed_request,
            "dependencies": self.dependency_status,
            "artifacts": self.artifacts,
        }


class _SyntheticIdentityProvider(IdentityProvider):
    def resolve(self, request: IdentityResolutionRequest) -> IdentityResolutionResult:
        return IdentityResolutionResult(
            authenticated=True,
            live=False,
            source="demo_fallback",
            user_id=request.fallback_user_id,
            tenant_id=request.fallback_tenant_id,
            roles=list(request.fallback_roles),
            session_id="",
            token_present=False,
            token_active=False,
            reason="identity.synthetic_fallback",
            metadata={"requested_path": request.requested_path},
        )


class GovernedFlowEvaluator:
    """Orchestrate a governed request path with strict live-mode dependencies."""

    def __init__(
        self,
        policy_checker: PolicyChecker,
        retrieval_checker: RetrievalChecker,
        tool_checker: ToolDecisionChecker,
        retrieval_backend: RetrievalBackend,
        retrieval_policy: RetrievalPolicyEvaluator,
        tool_executor: ToolExecutor,
        tool_policy_evaluator: ToolPolicyEvaluator | None = None,
        artifact_dir: Optional[Path] = None,
        identity_provider: IdentityProvider | None = None,
        secret_provider: VaultSecretsProvider | None = None,
        flow_mode: str = "demo",
        environment_mode: str = "dev",
    ):
        self._policy_checker = policy_checker
        self._retrieval_checker = retrieval_checker
        self._tool_checker = tool_checker
        self._retrieval_backend = retrieval_backend
        self._retrieval_policy = retrieval_policy
        self._tool_executor = tool_executor
        self._tool_policy_evaluator = tool_policy_evaluator or StaticToolPolicyEvaluator(default_policy_config())
        self._identity_provider = identity_provider or _SyntheticIdentityProvider()
        self._secret_provider = secret_provider
        self._flow_mode = flow_mode
        self._environment_mode = environment_mode

        if artifact_dir is None:
            repo_root = Path(__file__).resolve().parent.parent
            artifact_dir = repo_root / "overlays" / "myStarterKit" / "artifacts"
        self._artifact_dir = artifact_dir.resolve()

    def run(
        self,
        user_id: str,
        tenant_id: str,
        prompt: str,
        requested_tools: list[str],
        retrieval_source: str = "qdrant",
        retrieval_needed: bool = True,
        roles: list[str] | None = None,
        request_metadata: dict[str, Any] | None = None,
        tool_arguments: dict[str, dict[str, Any]] | None = None,
        policy_source: str = "",
        policy_path: str = "",
        authorization_header: str = "",
        request_headers: dict[str, str] | None = None,
        cookies: dict[str, str] | None = None,
        evidence_mode: str | None = None,
        secret_request: dict[str, Any] | None = None,
    ) -> GovernedFlowResult:
        trace_id = f"flow-{uuid.uuid4().hex[:12]}"
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        decision_id = f"decision-{uuid.uuid4().hex[:12]}"
        launch_request_id = request_id
        mode = (evidence_mode or self._flow_mode or "demo").strip().lower()
        live_mode = mode == "live"
        base_metadata = dict(request_metadata or {})
        requested_path = str(base_metadata.get("requested_path", base_metadata.get("path", "/governed-flow")))
        identity_roles = list(roles or ["tenant_user"])

        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_paths = {
            "events_jsonl": self._artifact_dir / "events.jsonl",
            "audit_records": self._artifact_dir / "audit-records.jsonl",
            "launch_gate_result": self._artifact_dir / "launch-gate-result.json",
            "identity_evidence": self._artifact_dir / "identity-evidence.json",
            "policy_evidence": self._artifact_dir / "policy-evidence.json",
            "retrieval_evidence": self._artifact_dir / "retrieval-evidence.json",
            "tool_evidence": self._artifact_dir / "tool-evidence.json",
            "secret_evidence": self._artifact_dir / "secret-evidence.json",
            "trace_correlation": self._artifact_dir / "trace-correlation.json",
            "governed_flow_summary": self._artifact_dir / "governed-flow-summary.json",
        }
        for path in artifact_paths.values():
            if path.exists():
                path.unlink()
        governed_request_feed_path = self._artifact_dir / "governed-request-feed.json"
        governed_request_history_root = self._artifact_dir / "governed-request-history"

        model = EventModel()
        sink = JsonlEventSink(str(artifact_paths["events_jsonl"]))

        session_id = ""
        surface_id = _surface_identifier(base_metadata, requested_path)
        audit_stage_sequence: list[str] = []
        audit_record_count = 0
        question_telemetry = sanitize_question(prompt)
        runtime_target = str(base_metadata.get("runtime_key", base_metadata.get("runtime_target", "onyx")) or "onyx")
        runtime_class = str(base_metadata.get("runtime_class", "rag" if runtime_target == "onyx" else "autonomous_agents"))
        request_telemetry_common = {
            "runtime_target": runtime_target,
            "runtime_class": runtime_class,
            "surface": surface_id,
            "requested_path": requested_path,
            "evidence_mode": mode,
            "environment_mode": self._environment_mode,
            "question_hash": question_telemetry["question_hash"],
            "question_preview": question_telemetry["question_preview"],
            "question_redacted": question_telemetry["question_redacted"],
            "question_truncated": question_telemetry["question_truncated"],
            "contains_sensitive_patterns": question_telemetry["contains_sensitive_patterns"],
            "sensitive_pattern_labels": list(question_telemetry["sensitive_pattern_labels"]),
            "question_length": question_telemetry["question_length"],
        }

        def emit(event_type: str, payload: dict[str, Any], severity: str = "info") -> None:
            sink.emit(
                model.create(
                    event_type=event_type,
                    trace_id=trace_id,
                    request_id=request_id,
                    session_id=session_id,
                    payload=payload,
                    tenant_id=payload.get("tenant_id", tenant_id) if isinstance(payload, dict) else tenant_id,
                    severity=severity,
                )
            )

        def emit_audit(
            *,
            stage: str,
            action: str,
            outcome: str,
            actor_id: str,
            tenant_value: str,
            session_value: str,
            reason_codes: list[str] | None = None,
            component: str = "",
            severity: str = "info",
            details: dict[str, Any] | None = None,
        ) -> None:
            nonlocal audit_record_count
            audit_record_count += 1
            if stage not in audit_stage_sequence:
                audit_stage_sequence.append(stage)
            _append_jsonl(
                artifact_paths["audit_records"],
                {
                    "audit_id": f"audit-{uuid.uuid4().hex[:12]}",
                    "timestamp": _now_iso(),
                    "trace_id": trace_id,
                    "request_id": request_id,
                    "decision_id": decision_id,
                    "launch_request_id": launch_request_id,
                    "session_id": session_value,
                    "actor_id": actor_id,
                    "tenant_id": tenant_value,
                    "surface": surface_id,
                    "requested_path": requested_path,
                    "runtime_target": runtime_target,
                    "runtime_class": runtime_class,
                    "stage": stage,
                    "action": action,
                    "outcome": outcome,
                    "component": component,
                    "tool_id": component if stage in {"tool_execution", "tool_decision"} else "",
                    "policy_source": policy_source,
                    "policy_path": policy_path,
                    "evidence_mode": mode,
                    "provenance": "runtime-generated",
                    "severity": severity,
                    "reason_codes": list(reason_codes or []),
                    "details": dict(details or {}),
                },
            )

        emit(
            "request.start",
            {
                "path": requested_path,
                "actor_id": user_id,
                "tenant_id": tenant_id,
                "surface": surface_id,
                "evidence_mode": mode,
                "environment_mode": self._environment_mode,
            },
        )
        emit(
            "request.question_received",
            {
                **request_telemetry_common,
                "actor_id": user_id,
                "tenant_id": tenant_id,
            },
        )
        emit(
            "request.question_sanitized",
            {
                **request_telemetry_common,
                "actor_id": user_id,
                "tenant_id": tenant_id,
            },
            severity="warning" if question_telemetry["question_redacted"] else "info",
        )

        identity_request = IdentityResolutionRequest(
            authorization_header=authorization_header,
            headers=dict(request_headers or {}),
            cookies=dict(cookies or {}),
            requested_path=requested_path,
            required_live_identity=live_mode,
            fallback_user_id=user_id,
            fallback_tenant_id=tenant_id,
            fallback_roles=identity_roles,
        )
        identity_result = self._identity_provider.resolve(identity_request)
        session_id = identity_result.session_id
        effective_user_id = identity_result.user_id or user_id
        effective_tenant_id = identity_result.tenant_id or tenant_id
        effective_roles = list(identity_result.roles or identity_roles)
        session_linkage_status, session_linkage_reason = _session_linkage(identity_result, live_mode=live_mode)
        auth_mechanism = str(identity_result.metadata.get("auth_mechanism", "")).strip().lower()
        requires_live_session_linkage = live_mode and auth_mechanism in {"oidc_session"}

        identity_evidence = {
            "step": "identity",
            "captured_at": _now_iso(),
            "timestamp": _now_iso(),
            "trace_id": trace_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "launch_request_id": launch_request_id,
            "session_id": session_id,
            "actor_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "surface": surface_id,
            "requested_path": requested_path,
            "evidence_mode": mode,
            "mandatory": live_mode,
            "authenticated": identity_result.authenticated,
            "live": identity_result.live,
            "source": identity_result.source,
            "provider_verified": bool(identity_result.authenticated and identity_result.live),
            "user_id": effective_user_id,
            "roles": effective_roles,
            "token_present": identity_result.token_present,
            "token_active": identity_result.token_active,
            "reason": identity_result.reason,
            "reason_codes": [identity_result.reason] if identity_result.reason else [],
            "session_linkage_status": session_linkage_status,
            "session_linkage_reason": session_linkage_reason,
            "requires_live_session_linkage": requires_live_session_linkage,
            "provenance": "runtime-generated",
            "metadata": identity_result.metadata,
        }
        _write_json(artifact_paths["identity_evidence"], identity_evidence)
        emit(
            "identity.established",
            {
                "sub": effective_user_id,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "roles": effective_roles,
                "live": identity_result.live,
                "identity_source": identity_result.source,
                "reason": identity_result.reason,
                "session_id": session_id,
                "surface": surface_id,
            },
            severity="info" if identity_result.authenticated else "warning",
        )
        emit(
            "identity.session",
            {
                "session_id": session_id,
                "token_present": identity_result.token_present,
                "token_active": identity_result.token_active,
                "identity_source": identity_result.source,
                "session_linkage_status": session_linkage_status,
                "session_linkage_reason": session_linkage_reason,
                "requires_live_session_linkage": requires_live_session_linkage,
                "surface": surface_id,
            },
            severity="info" if identity_result.authenticated else "warning",
        )
        emit_audit(
            stage="identity",
            action="identity.established" if identity_result.authenticated else "identity.failed",
            outcome="allow" if identity_result.authenticated else "deny",
            actor_id=effective_user_id or user_id,
            tenant_value=effective_tenant_id or tenant_id,
            session_value=session_id,
            reason_codes=[identity_result.reason] if identity_result.reason else [],
            component=identity_result.source,
            severity="info" if identity_result.authenticated else "warning",
            details={
                "live": identity_result.live,
                "roles": effective_roles,
                "session_linkage_status": session_linkage_status,
                "session_linkage_reason": session_linkage_reason,
                "requires_live_session_linkage": requires_live_session_linkage,
            },
        )

        policy_allow = False
        retrieval_allow = False
        tools_allowed: list[str] = []
        tools_denied: list[str] = []
        tool_reasons: list[str] = []
        retrieval_reasons: list[str] = []
        secret_reason = "not_needed"
        secret_required = bool(secret_request and secret_request.get("needed"))
        secret_satisfied = not secret_required

        normalized_request = NormalizedRequest(
            request_id=request_id,
            tenant_id=effective_tenant_id,
            user_id=effective_user_id,
            prompt=prompt,
            requested_tools=requested_tools,
            retrieval_needed=retrieval_needed,
            retrieval_source=retrieval_source,
            metadata={
                "trace_id": trace_id,
                "session_id": session_id,
                "identity_roles": effective_roles,
                "identity_source": identity_result.source,
                "requested_path": requested_path,
                "evidence_mode": mode,
                "tool_arguments": dict(tool_arguments or {}),
                **base_metadata,
            },
        )

        gateway_decision = None
        policy_metadata: dict[str, Any] = {}
        gateway = OnyxGatewayAdapter(
            policy_checker=self._policy_checker,
            retrieval_checker=self._retrieval_checker,
            tool_checker=self._tool_checker,
            telemetry_emitter=InMemoryTelemetryEmitter(),
        )
        emit(
            "policy.input",
            {
                "surface": str(base_metadata.get("surface", "")),
                "requested_path": requested_path,
                "requested_tools": requested_tools,
                "retrieval_source": retrieval_source,
                "environment_mode": self._environment_mode,
                "evidence_mode": mode,
                "identity_authenticated": identity_result.authenticated,
            },
        )
        gateway_decision = gateway.evaluate(normalized_request)
        policy_allow = gateway_decision.policy_allow
        policy_metadata = _metadata_for(self._policy_checker)
        gateway_reasons = list(getattr(gateway_decision, "reasons", []))
        if live_mode and str(policy_metadata.get("engine", "")).strip().lower() != "opa":
            policy_allow = False
            if "policy.live_opa_required" not in gateway_reasons:
                gateway_reasons.append("policy.live_opa_required")
            policy_metadata = {
                **policy_metadata,
                "engine": str(policy_metadata.get("engine", "local") or "local"),
                "reachable": bool(policy_metadata.get("reachable", False)),
                "downgraded": True,
            }
        if not identity_result.authenticated:
            gateway_reasons = list(dict.fromkeys([identity_result.reason or "identity.denied"] + gateway_reasons))

        policy_evidence = {
            "step": "policy",
            "captured_at": _now_iso(),
            "timestamp": _now_iso(),
            "trace_id": trace_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "launch_request_id": launch_request_id,
            "session_id": session_id,
            "actor_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "surface": surface_id,
            "evidence_mode": mode,
            "mandatory": live_mode,
            "policy_source": policy_source,
            "policy_path": policy_path,
            "engine": policy_metadata.get("engine", "local"),
            "engine_reachable": policy_metadata.get("reachable", policy_metadata.get("engine") != "opa"),
            "package_path": policy_metadata.get("package_path", ""),
            "allow": policy_allow,
            "reasons": list(gateway_reasons),
            "reason_codes": list(gateway_reasons),
            "matched_surface": str(policy_metadata.get("matched_surface", "")),
            "identity_live": identity_result.live,
            "provenance": "runtime-generated",
        }
        _write_json(artifact_paths["policy_evidence"], policy_evidence)
        emit(
            "policy.decision",
            {
                "allow": policy_allow,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "policy_source": policy_source,
                "policy_path": policy_path,
                "policy_engine": policy_metadata.get("engine", "local"),
                "policy_engine_reachable": policy_metadata.get("reachable", policy_metadata.get("engine") != "opa"),
                "package_path": policy_metadata.get("package_path", ""),
                "surface": surface_id,
                "reason_codes": list(gateway_reasons),
            },
            severity="info" if policy_allow else "warning",
        )
        emit_audit(
            stage="policy",
            action="policy.decision",
            outcome="allow" if policy_allow else "deny",
            actor_id=effective_user_id,
            tenant_value=effective_tenant_id,
            session_value=session_id,
            reason_codes=list(gateway_reasons),
            component=str(policy_metadata.get("engine", "runtime_policy")),
            severity="info" if policy_allow else "warning",
            details={
                "engine_reachable": policy_metadata.get("reachable", policy_metadata.get("engine") != "opa"),
                "package_path": policy_metadata.get("package_path", ""),
                "matched_surface": str(policy_metadata.get("matched_surface", "")),
            },
        )

        retrieval_documents = []
        retrieval_execution = {
            "step": "retrieval",
            "captured_at": _now_iso(),
            "timestamp": _now_iso(),
            "trace_id": trace_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "launch_request_id": launch_request_id,
            "session_id": session_id,
            "actor_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "surface": surface_id,
            "evidence_mode": mode,
            "backend": getattr(self._retrieval_backend, "__class__", type(self._retrieval_backend)).__name__,
            "source": retrieval_source,
            "filters": {},
            "result_count": 0,
            "live_backend": False,
            "backend_verified": False,
            "mandatory": retrieval_needed,
            "allow": False,
            "mode": "skipped" if not retrieval_needed else "deny",
            "reasons": [],
            "reason_codes": [],
            "provenance": "runtime-generated",
        }
        if retrieval_needed:
            retrieval_layer = RetrievalSecurityLayer(
                backend=self._retrieval_backend,
                policy_evaluator=self._retrieval_policy,
                telemetry=InMemoryRetrievalTelemetry(),
            )
            try:
                retrieval_result = retrieval_layer.evaluate(
                    RetrievalRequest(
                        request_id=request_id,
                        tenant_id=effective_tenant_id,
                        source=retrieval_source,
                        query=prompt,
                        trust_labels=["trusted"],
                    )
                )
                retrieval_allow = retrieval_result.allow
                retrieval_reasons = list(retrieval_result.reasons)
                retrieval_documents = list(retrieval_result.filtered_documents)
                retrieval_meta = _metadata_for(self._retrieval_backend)
                retrieval_execution.update(
                    {
                        "backend": str(retrieval_meta.get("backend", "qdrant" if live_mode else retrieval_execution["backend"])),
                        "filters": retrieval_meta.get("filters", {}),
                        "result_count": len(retrieval_documents),
                        "collection": retrieval_meta.get("collection", ""),
                        "live_backend": live_mode,
                        "backend_verified": True,
                        "allow": retrieval_allow,
                        "mode": retrieval_result.mode,
                        "reasons": retrieval_reasons,
                        "reason_codes": retrieval_reasons,
                    }
                )
            except Exception:
                retrieval_allow = False
                retrieval_reasons = ["retrieval.backend_unavailable"]
                retrieval_execution.update(
                    {
                        "live_backend": live_mode,
                        "backend_verified": False,
                        "allow": False,
                        "mode": "deny",
                        "reasons": retrieval_reasons,
                        "reason_codes": retrieval_reasons,
                    }
                )
        else:
            retrieval_reasons = ["retrieval.not_needed"]
            retrieval_allow = True
            retrieval_execution.update(
                {
                    "allow": True,
                    "mode": "skipped",
                    "reasons": retrieval_reasons,
                    "reason_codes": retrieval_reasons,
                    "live_backend": live_mode and retrieval_needed,
                    "backend_verified": False,
                }
            )

        _write_json(artifact_paths["retrieval_evidence"], retrieval_execution)
        emit(
            "retrieval.decision",
            {
                "decision": retrieval_execution["mode"],
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "source": retrieval_source,
                "docs_filtered": retrieval_execution["result_count"],
                "reason_codes": retrieval_execution["reasons"],
                "backend": retrieval_execution["backend"],
                "live_backend": retrieval_execution["live_backend"],
                "backend_verified": retrieval_execution["backend_verified"],
                "surface": surface_id,
            },
            severity="info" if retrieval_execution["allow"] else "warning",
        )
        emit(
            "retrieval.execution",
            {
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "backend": retrieval_execution["backend"],
                "collection": retrieval_execution.get("collection", ""),
                "filters": retrieval_execution["filters"],
                "result_count": retrieval_execution["result_count"],
                "live_backend": retrieval_execution["live_backend"],
                "surface": surface_id,
            },
            severity="info" if retrieval_execution["allow"] else "warning",
        )
        emit_audit(
            stage="retrieval",
            action="retrieval.decision",
            outcome="allow" if retrieval_execution["allow"] else "deny",
            actor_id=effective_user_id,
            tenant_value=effective_tenant_id,
            session_value=session_id,
            reason_codes=list(retrieval_execution["reason_codes"]),
            component=str(retrieval_execution["backend"]),
            severity="info" if retrieval_execution["allow"] else "warning",
            details={
                "source": retrieval_source,
                "collection": retrieval_execution.get("collection", ""),
                "filters": retrieval_execution["filters"],
                "backend_verified": retrieval_execution["backend_verified"],
                "live_backend": retrieval_execution["live_backend"],
                "result_count": retrieval_execution["result_count"],
            },
        )

        secret_evidence = {
            "step": "secret",
            "captured_at": _now_iso(),
            "timestamp": _now_iso(),
            "trace_id": trace_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "launch_request_id": launch_request_id,
            "session_id": session_id,
            "actor_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "surface": surface_id,
            "evidence_mode": mode,
            "required": secret_required,
            "mandatory": secret_required,
            "purpose": str(secret_request.get("purpose", "")) if secret_request else "",
            "backend": "vault" if self._secret_provider else "unconfigured",
            "backend_configured": self._secret_provider is not None,
            "backend_available": self._secret_provider is not None,
            "access_attempted": False,
            "fetched": False,
            "reason": secret_reason,
            "reason_codes": [secret_reason] if secret_reason else [],
            "provenance": "runtime-generated",
        }
        if secret_required and not identity_result.authenticated:
            secret_reason = "secret.skipped_due_to_identity"
            secret_satisfied = False
            secret_evidence.update({"fetched": False, "reason": secret_reason, "reason_codes": [secret_reason]})
        elif secret_required and not policy_allow:
            secret_reason = "secret.skipped_due_to_policy"
            secret_satisfied = False
            secret_evidence.update({"fetched": False, "reason": secret_reason, "reason_codes": [secret_reason]})
        elif secret_required and not retrieval_allow:
            secret_reason = "secret.skipped_due_to_retrieval"
            secret_satisfied = False
            secret_evidence.update({"fetched": False, "reason": secret_reason, "reason_codes": [secret_reason]})
        elif secret_required and self._secret_provider is not None:
            secret_fetch = self._secret_provider.fetch_if_needed(
                SecretFetchRequest(
                    request_id=request_id,
                    tenant_id=effective_tenant_id,
                    needed=True,
                    secret_path=str(secret_request.get("secret_path", "")),
                    secret_key=str(secret_request.get("secret_key", "")),
                    purpose=str(secret_request.get("purpose", "")),
                )
            )
            secret_reason = secret_fetch.reason
            secret_satisfied = secret_fetch.fetched
            secret_evidence.update(
                {
                    "access_attempted": True,
                    "fetched": secret_fetch.fetched,
                    "reason": secret_fetch.reason,
                    "reason_codes": [secret_fetch.reason] if secret_fetch.reason else [],
                }
            )
        elif secret_required:
            secret_reason = "secret.backend_missing"
            secret_satisfied = False
            secret_evidence.update({"fetched": False, "reason": secret_reason, "reason_codes": [secret_reason]})
        else:
            secret_evidence.update({"fetched": False, "reason": "not_needed", "reason_codes": ["not_needed"]})
        _write_json(artifact_paths["secret_evidence"], secret_evidence)
        emit(
            "secret.access",
            {
                "required": secret_required,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "surface": surface_id,
                "purpose": secret_evidence["purpose"],
                "backend": secret_evidence["backend"],
                "backend_available": secret_evidence["backend_available"],
                "access_attempted": secret_evidence["access_attempted"],
                "fetched": secret_evidence["fetched"],
                "reason": secret_evidence["reason"],
            },
            severity="info" if secret_satisfied or not secret_required else "warning",
        )
        emit_audit(
            stage="secret",
            action="secret.access",
            outcome="allow" if secret_satisfied or not secret_required else "deny",
            actor_id=effective_user_id,
            tenant_value=effective_tenant_id,
            session_value=session_id,
            reason_codes=list(secret_evidence["reason_codes"]),
            component=str(secret_evidence["backend"]),
            severity="info" if secret_satisfied or not secret_required else "warning",
            details={
                "required": secret_required,
                "purpose": secret_evidence["purpose"],
                "backend_configured": secret_evidence["backend_configured"],
                "fetched": secret_evidence["fetched"],
            },
        )

        tools_denied = list(getattr(gateway_decision, "denied_tools", []))
        tools_allowed = []
        if policy_allow and retrieval_allow and secret_satisfied:
            tool_engine = ToolGovernanceEngine(
                policy_evaluator=self._tool_policy_evaluator,
                executor=self._tool_executor,
                audit_sink=InMemoryAuditSink(),
            )
            for tool_name in requested_tools:
                request_arguments = {"query": prompt}
                if tool_arguments and tool_name in tool_arguments:
                    request_arguments = dict(tool_arguments[tool_name])
                result = tool_engine.evaluate(
                    ToolActionRequest(
                        request_id=request_id,
                        tenant_id=effective_tenant_id,
                        user_id=effective_user_id,
                        tool_name=tool_name,
                        arguments=request_arguments,
                    )
                )
                if result.status == "allow":
                    tools_allowed.append(tool_name)
                    emit(
                        "tool.execution_attempt",
                        {
                            "tool_name": tool_name,
                            "status": "executed",
                            "actor_id": effective_user_id,
                            "tenant_id": effective_tenant_id,
                            "surface": surface_id,
                        },
                    )
                    emit_audit(
                        stage="tool_execution",
                        action="tool.execution_attempt",
                        outcome="executed",
                        actor_id=effective_user_id,
                        tenant_value=effective_tenant_id,
                        session_value=session_id,
                        reason_codes=list(result.reason_codes),
                        component=tool_name,
                        details={"status": "executed"},
                    )
                else:
                    if tool_name not in tools_denied:
                        tools_denied.append(tool_name)
                    tool_reasons.extend([f"tool.{tool_name}:{reason}" for reason in result.reason_codes] or [f"tool.{tool_name}:{result.status}"])
                    emit(
                        "tool.execution_attempt",
                        {
                            "tool_name": tool_name,
                            "status": result.status,
                            "reasons": result.reason_codes,
                            "actor_id": effective_user_id,
                            "tenant_id": effective_tenant_id,
                            "surface": surface_id,
                        },
                        severity="warning",
                    )
                    emit_audit(
                        stage="tool_execution",
                        action="tool.execution_attempt",
                        outcome=result.status,
                        actor_id=effective_user_id,
                        tenant_value=effective_tenant_id,
                        session_value=session_id,
                        reason_codes=list(result.reason_codes),
                        component=tool_name,
                        severity="warning",
                        details={"status": result.status},
                    )
        else:
            if not policy_allow:
                tool_reasons.append("tool.skipped_due_to_policy")
            elif not retrieval_allow:
                tool_reasons.append("tool.skipped_due_to_retrieval")
            elif not secret_satisfied:
                tool_reasons.append("tool.skipped_due_to_secret")
            for tool_name in requested_tools:
                emit_audit(
                    stage="tool_execution",
                    action="tool.execution_attempt",
                    outcome="skipped",
                    actor_id=effective_user_id,
                    tenant_value=effective_tenant_id,
                    session_value=session_id,
                    reason_codes=list(dict.fromkeys(tool_reasons)),
                    component=tool_name,
                    severity="warning" if tool_reasons else "info",
                    details={"status": "skipped"},
                )

        emit(
            "tool.decision",
            {
                "allowed": tools_allowed,
                "denied": tools_denied,
                "reasons": list(dict.fromkeys(tool_reasons)),
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "surface": surface_id,
                "runtime_target": runtime_target,
                "runtime_class": runtime_class,
            },
            severity="info" if not tools_denied else "warning",
        )
        emit_audit(
            stage="tool_decision",
            action="tool.decision",
            outcome="allow" if not tools_denied else "deny",
            actor_id=effective_user_id,
            tenant_value=effective_tenant_id,
            session_value=session_id,
            reason_codes=list(dict.fromkeys(tool_reasons)),
            component="tool_policy",
            severity="info" if not tools_denied else "warning",
            details={"allowed": tools_allowed, "denied": tools_denied},
        )
        mcp_server = str(base_metadata.get("requested_mcp_server", "")).strip()
        tool_evidence = {
            "step": "tool_governance",
            "captured_at": _now_iso(),
            "timestamp": _now_iso(),
            "trace_id": trace_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "launch_request_id": launch_request_id,
            "session_id": session_id,
            "actor_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "surface": surface_id,
            "runtime_target": runtime_target,
            "runtime_class": runtime_class,
            "evidence_mode": mode,
            "requested_tools": list(requested_tools),
            "allowed_tools": list(tools_allowed),
            "denied_tools": list(tools_denied),
            "reason_codes": list(dict.fromkeys(tool_reasons)),
            "mcp_server": mcp_server,
            "mcp_governance_required": runtime_target == "dify",
            "mcp_governed": runtime_target != "dify" or bool(mcp_server),
            "provenance": "runtime-generated",
        }
        _write_json(artifact_paths["tool_evidence"], tool_evidence)

        final_reasons = list(
            dict.fromkeys(
                [reason for reason in gateway_reasons if reason]
                + retrieval_reasons
                + tool_reasons
                + ([] if secret_satisfied else [secret_reason])
                + ([] if identity_result.authenticated else [identity_result.reason])
            )
        )
        preliminary_decision = (
            identity_result.authenticated
            and policy_allow
            and retrieval_allow
            and secret_satisfied
            and len(tools_denied) == 0
        )
        emit(
            "incident.signal",
            {
                "signal": "none" if preliminary_decision else "governed_path_blocked",
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "surface": surface_id,
            },
        )

        recorded_events = [json.loads(line) for line in artifact_paths["events_jsonl"].read_text(encoding="utf-8").splitlines() if line.strip()]
        observed_event_types = {event["event_type"] for event in recorded_events}
        pre_gate_required_steps = [
            "request.start",
            "identity.established",
            "policy.decision",
            "retrieval.decision",
            "secret.access",
            "tool.decision",
        ]
        trace_missing_pre = [step for step in pre_gate_required_steps if step not in observed_event_types]
        trace_complete = len(trace_missing_pre) == 0 and (not requires_live_session_linkage or bool(session_id))

        evidence = {
            "identity.live": identity_result.authenticated and identity_result.live,
            "policy.live_opa": bool(policy_metadata.get("engine") == "opa" and policy_metadata.get("reachable", True)),
            "retrieval.live_backend": bool(
                retrieval_needed
                and retrieval_execution["live_backend"]
                and retrieval_execution["backend_verified"]
                and retrieval_execution["mode"] != "skipped"
            ),
            "secret.access": bool(secret_required and secret_satisfied) or not secret_required,
            "trace.correlation": trace_complete,
            "handoff.decision": True,
            "policy.decision": "policy.decision" in observed_event_types,
            "retrieval.decision": "retrieval.decision" in observed_event_types,
            "tool.decision": "tool.decision" in observed_event_types,
            "incident.signal": "incident.signal" in observed_event_types,
        }
        controls = (
            LAUNCH_GATE.live_controls(
                secret_required=secret_required,
                retrieval_required=retrieval_needed,
            )
            if live_mode
            else LAUNCH_GATE.default_controls()
        )
        gate_result = LAUNCH_GATE.evaluate_launch_gate(
            evidence=evidence,
            controls=controls,
            kill_switch=not preliminary_decision,
        )
        final_decision = preliminary_decision and gate_result.decision != "no_go"
        if not final_decision and gate_result.decision == "no_go" and "launch_gate.no_go" not in final_reasons:
            final_reasons.append("launch_gate.no_go")
        emit(
            "launch_gate.evaluated",
            {
                "decision": gate_result.decision,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "surface": surface_id,
                "score": gate_result.score,
                "max_score": gate_result.max_score,
                "missing_evidence": gate_result.missing_evidence,
                "blockers": gate_result.blockers,
                "evidence_mode": mode,
            },
            severity="info" if gate_result.decision == "pass" else "warning",
        )
        emit_audit(
            stage="launch_gate",
            action="launch_gate.summary",
            outcome=gate_result.decision,
            actor_id=effective_user_id,
            tenant_value=effective_tenant_id,
            session_value=session_id,
            reason_codes=list(gate_result.blockers) + list(gate_result.missing_evidence),
            component="launch_gate",
            severity="info" if gate_result.decision == "pass" else "warning",
            details={
                "score": gate_result.score,
                "max_score": gate_result.max_score,
                "missing_evidence": gate_result.missing_evidence,
                "blockers": gate_result.blockers,
            },
        )
        emit("fallback.event", {"applied": False, "evidence_mode": mode})
        emit(
            "deny.event",
            {
                "blocked": not final_decision,
                "reason": final_reasons[0] if final_reasons else "",
                "reason_code": final_reasons[0].split(":")[0] if final_reasons else "",
                "reasons": final_reasons,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "surface": surface_id,
                "requested_path": requested_path,
            },
            severity="warning" if not final_decision else "info",
        )
        emit(
            "handoff.decision",
            {
                "runtime_target": runtime_target,
                "runtime_class": runtime_class,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "surface": surface_id,
                "requested_path": requested_path,
                "allow": final_decision,
                "reason_codes": final_reasons,
                "evidence_mode": mode,
                "policy_source": policy_source,
                "policy_path": policy_path,
            },
            severity="info" if final_decision else "warning",
        )
        emit_audit(
            stage="handoff",
            action=f"{runtime_target}.handoff",
            outcome="allow" if final_decision else "deny",
            actor_id=effective_user_id,
            tenant_value=effective_tenant_id,
            session_value=session_id,
            reason_codes=list(final_reasons),
            component=runtime_target,
            severity="info" if final_decision else "warning",
            details={
                "policy_source": policy_source,
                "policy_path": policy_path,
                "runtime_target": runtime_target,
                "runtime_class": runtime_class,
            },
        )
        repo_root = Path(__file__).resolve().parent.parent
        current_artifact_refs = {
            name: _artifact_reference(path, repo_root) for name, path in artifact_paths.items()
        }
        governed_request_record = {
            "timestamp": _now_iso(),
            "trace_id": trace_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "launch_request_id": launch_request_id,
            "session_id": session_id,
            "tenant_id": effective_tenant_id,
            "actor_id": effective_user_id,
            "user_id": effective_user_id,
            "surface": surface_id,
            "requested_path": requested_path,
            "runtime_target": runtime_target,
            "runtime_class": runtime_class,
            "evidence_mode": mode,
            "environment_mode": self._environment_mode,
            "identity_authenticated": identity_result.authenticated,
            "identity_live": identity_result.live,
            "policy_allow": policy_allow,
            "retrieval_allow": retrieval_allow,
            "secret_required": secret_required,
            "secret_satisfied": secret_satisfied,
            "handoff_allowed": final_decision,
            "reason_codes": list(final_reasons),
            "artifact_refs": dict(current_artifact_refs),
            **question_telemetry,
        }
        emit(
            "request.question_classified",
            {
                **request_telemetry_common,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "identity_authenticated": identity_result.authenticated,
                "identity_live": identity_result.live,
                "policy_allow": policy_allow,
                "retrieval_allow": retrieval_allow,
                "secret_required": secret_required,
                "secret_satisfied": secret_satisfied,
                "handoff_allowed": final_decision,
                "reason_codes": list(final_reasons),
            },
            severity="info" if final_decision else "warning",
        )
        emit(
            "request.end",
            {
                "status": "ok" if final_decision else "denied",
                "decision": final_decision,
                "evidence_mode": mode,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "surface": surface_id,
            },
            severity="info" if final_decision else "warning",
        )

        final_recorded_events = [json.loads(line) for line in artifact_paths["events_jsonl"].read_text(encoding="utf-8").splitlines() if line.strip()]
        final_observed_event_types = {event["event_type"] for event in final_recorded_events}
        audit_records = [json.loads(line) for line in artifact_paths["audit_records"].read_text(encoding="utf-8").splitlines() if line.strip()]
        audit_trace_ids = {str(record.get("trace_id", "")) for record in audit_records if str(record.get("trace_id", ""))}
        audit_stages_observed = sorted({str(record.get("stage", "")) for record in audit_records if str(record.get("stage", ""))})
        final_required_steps = pre_gate_required_steps + [
            "launch_gate.evaluated",
            "handoff.decision",
            "request.end",
        ]
        final_missing_steps = [step for step in final_required_steps if step not in final_observed_event_types]
        required_identifiers = {
            "trace_id": trace_id,
            "request_id": request_id,
            "session_id": session_id,
            "actor_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "surface": surface_id,
        }
        missing_identifiers = [
            key
            for key, value in required_identifiers.items()
            if not value and not (key == "session_id" and not requires_live_session_linkage)
        ]
        required_audit_stages = ["identity", "policy", "retrieval", "secret", "tool_decision", "launch_gate", "handoff"]
        if requested_tools:
            required_audit_stages.append("tool_execution")
        missing_audit_stages = [stage for stage in required_audit_stages if stage not in audit_stages_observed]
        trace_reason_codes = list(final_missing_steps)
        trace_reason_codes.extend(f"identifier_missing:{name}" for name in missing_identifiers)
        if requires_live_session_linkage and not session_id:
            trace_reason_codes.append("session.linkage_unavailable")
        trace_reason_codes.extend(f"audit.stage_missing:{stage}" for stage in missing_audit_stages)
        trace_correlation = {
            "captured_at": _now_iso(),
            "timestamp": _now_iso(),
            "trace_id": trace_id,
            "request_id": request_id,
            "decision_id": decision_id,
            "launch_request_id": launch_request_id,
            "session_id": session_id,
            "actor_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "surface": surface_id,
            "roles": effective_roles,
            "evidence_mode": mode,
            "environment_mode": self._environment_mode,
            "required_steps": final_required_steps,
            "observed_steps": sorted(final_observed_event_types),
            "missing_steps": final_missing_steps,
            "required_identifiers": sorted(required_identifiers),
            "missing_identifiers": missing_identifiers,
            "session_linkage": {
                "status": session_linkage_status,
                "reason": session_linkage_reason,
                "required": requires_live_session_linkage,
                "identity_source": identity_result.source,
            },
            "audit_linkage": {
                "record_count": len(audit_records),
                "trace_bound": trace_id in audit_trace_ids,
                "required_stages": required_audit_stages,
                "observed_stages": audit_stages_observed,
                "missing_stages": missing_audit_stages,
                "complete": trace_id in audit_trace_ids and not missing_audit_stages,
            },
            "complete": len(final_missing_steps) == 0 and not missing_identifiers and (not requires_live_session_linkage or bool(session_id)),
            "reason_codes": list(dict.fromkeys(trace_reason_codes)),
            "provenance": "runtime-generated",
        }
        _write_json(artifact_paths["trace_correlation"], trace_correlation)
        emit(
            "trace.correlation",
            trace_correlation,
            severity="info" if trace_correlation["complete"] else "warning",
        )

        launch_findings = [
            {
                "control": control.control_id,
                "status": (
                    "pass"
                    if not any(evidence_key in gate_result.missing_evidence for evidence_key in control.required_evidence)
                    and not any(blocker.endswith(control.control_id) for blocker in gate_result.blockers)
                    else "fail"
                ),
                "detail": control.description,
            }
            for control in controls
        ]
        score_percent = round((gate_result.score / gate_result.max_score) * 100) if gate_result.max_score else 0
        launch_gate_artifact = {
            "machine": gate_result.to_machine_readable(),
            "human": gate_result.to_human_readable(),
            "governed_request": governed_request_record,
            "decision_explanation": {
                "decision_id": decision_id,
                "launch_request_id": launch_request_id,
                "runtime_id": runtime_target,
                "status": "allow" if final_decision else "deny",
                "reason_codes": list(final_reasons),
                "evidence_refs": dict(current_artifact_refs),
                "generated_at": _now_iso(),
            },
            "flow_metadata": {
                "trace_id": trace_id,
                "request_id": request_id,
                "decision_id": decision_id,
                "launch_request_id": launch_request_id,
                "session_id": session_id,
                "actor_id": effective_user_id,
                "tenant_id": effective_tenant_id,
                "surface": surface_id,
                "policy_source": policy_source,
                "policy_path": policy_path,
                "evidence_mode": mode,
                "handoff_allowed": final_decision,
                "governed_request": {
                    "question_preview": governed_request_record["question_preview"],
                    "question_hash": governed_request_record["question_hash"],
                    "question_redacted": governed_request_record["question_redacted"],
                    "contains_sensitive_patterns": governed_request_record["contains_sensitive_patterns"],
                },
                "artifacts": {
                    "events_jsonl": _artifact_reference(artifact_paths["events_jsonl"], self._artifact_dir.parent.parent),
                    "audit_records": _artifact_reference(artifact_paths["audit_records"], self._artifact_dir.parent.parent),
                },
            },
        }

        dependency_status = {
            "identity": {
                "mandatory": live_mode,
                "live": identity_result.live,
                "source": identity_result.source,
                "authenticated": identity_result.authenticated,
            },
            "policy": {
                "mandatory": live_mode,
                "engine": policy_metadata.get("engine", "local"),
                "allow": policy_allow,
            },
            "retrieval": {
                "mandatory": retrieval_needed,
                "live_backend": retrieval_execution["live_backend"],
                "allow": retrieval_allow,
            },
            "secret": {
                "mandatory": secret_required,
                "fetched": secret_satisfied,
                "reason": secret_reason,
            },
            "trace": {
                "mandatory": True,
                "complete": bool(trace_correlation.get("complete")),
            },
            "audit": {
                "mandatory": True,
                "record_count": len(audit_records),
                "complete": bool(trace_correlation.get("audit_linkage", {}).get("complete")),
            },
        }
        launch_gate_artifact["flow_metadata"]["dependency_status"] = dependency_status
        _write_json(artifact_paths["launch_gate_result"], launch_gate_artifact)

        governed_summary = {
            "generated_at": _now_iso(),
            "trace_id": trace_id,
            "request_id": request_id,
            "session_id": session_id,
            "actor_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "surface": surface_id,
            "decision": final_decision,
            "reasons": final_reasons,
            "runtime_target": runtime_target,
            "runtime_class": runtime_class,
            "requested_path": requested_path,
            "evidence_mode": mode,
            "environment_mode": self._environment_mode,
            "handoff_allowed": final_decision,
            "question_preview": governed_request_record["question_preview"],
            "question_hash": governed_request_record["question_hash"],
            "question_redacted": governed_request_record["question_redacted"],
            "contains_sensitive_patterns": governed_request_record["contains_sensitive_patterns"],
            "governed_request": governed_request_record,
            "dependency_status": dependency_status,
            "identity": identity_evidence,
            "policy": policy_evidence,
            "retrieval": retrieval_execution,
            "secret": secret_evidence,
            "tools": {
                "allowed": tools_allowed,
                "denied": tools_denied,
                "reasons": list(dict.fromkeys(tool_reasons)),
            },
            "audit": {
                "record_count": len(audit_records),
                "stages": audit_stages_observed,
                "missing_stages": missing_audit_stages,
                "artifact": _artifact_reference(artifact_paths["audit_records"], repo_root := Path(__file__).resolve().parent.parent),
            },
            "trace": trace_correlation,
            "launch_gate": {
                "decision": gate_result.decision,
                "score": gate_result.score,
                "max_score": gate_result.max_score,
                "score_percent": score_percent,
                "blockers": gate_result.blockers,
                "missing_evidence": gate_result.missing_evidence,
                "control_coverage": f"{len([finding for finding in launch_findings if finding['status'] == 'pass'])}/{len(launch_findings)}",
                "findings": launch_findings,
                "residual_risks": [
                    f"missing:{missing}" for missing in gate_result.missing_evidence
                ] + list(gate_result.blockers),
            },
        }
        _write_json(artifact_paths["governed_flow_summary"], governed_summary)

        for evidence_payload, artifact_path in (
            (identity_evidence, artifact_paths["identity_evidence"]),
            (policy_evidence, artifact_paths["policy_evidence"]),
            (retrieval_execution, artifact_paths["retrieval_evidence"]),
            (secret_evidence, artifact_paths["secret_evidence"]),
            (trace_correlation, artifact_paths["trace_correlation"]),
        ):
            evidence_payload["handoff_allowed"] = final_decision
            evidence_payload["launch_gate_decision"] = gate_result.decision
            evidence_payload["launch_gate_missing_evidence"] = list(gate_result.missing_evidence)
            evidence_payload["dependency_status"] = dependency_status
            evidence_payload["question_preview"] = governed_request_record["question_preview"]
            evidence_payload["question_hash"] = governed_request_record["question_hash"]
            evidence_payload["question_redacted"] = governed_request_record["question_redacted"]
            evidence_payload["contains_sensitive_patterns"] = governed_request_record["contains_sensitive_patterns"]
            evidence_payload["governed_request"] = governed_request_record
            evidence_payload["reason_codes"] = list(
                dict.fromkeys(_string for _string in list(evidence_payload.get("reason_codes", [])) + list(final_reasons) if _string)
            )
            _write_json(artifact_path, evidence_payload)
        _write_json(artifact_paths["launch_gate_result"], launch_gate_artifact)
        _write_json(artifact_paths["governed_flow_summary"], governed_summary)

        history_refs = write_history_artifacts(
            governed_request_history_root,
            trace_id,
            {
                "governed-flow-summary": governed_summary,
                "identity-evidence": identity_evidence,
                "policy-evidence": policy_evidence,
                "retrieval-evidence": retrieval_execution,
                "secret-evidence": secret_evidence,
                "trace-correlation": trace_correlation,
                "launch-gate-result": launch_gate_artifact,
            },
        )
        feed_record = dict(governed_request_record)
        feed_record["artifact_refs"] = {
            name: _artifact_reference(Path(path), repo_root)
            for name, path in history_refs.items()
        }
        feed_record["feed_path"] = _artifact_reference(governed_request_feed_path, repo_root)
        append_governed_request_feed(governed_request_feed_path, feed_record)

        relative_artifacts = dict(current_artifact_refs)
        relative_artifacts["governed_request_feed"] = _artifact_reference(governed_request_feed_path, repo_root)

        return GovernedFlowResult(
            decision=final_decision,
            trace_id=trace_id,
            request_id=request_id,
            session_id=session_id,
            reasons=final_reasons,
            policy_allow=policy_allow,
            retrieval_allow=retrieval_allow,
            allowed_tools=tools_allowed,
            denied_tools=tools_denied,
            launch_gate_decision=gate_result.decision,
            launch_gate_score=gate_result.score,
            launch_gate_max_score=gate_result.max_score,
            launch_gate_blockers=gate_result.blockers,
            launch_gate_missing_evidence=gate_result.missing_evidence,
            policy_source=policy_source,
            policy_path=policy_path,
            evidence_mode=mode,
            artifacts=relative_artifacts,
            governed_request=feed_record,
            dependency_status=dependency_status,
        )
