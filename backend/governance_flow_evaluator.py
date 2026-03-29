"""Composable governed-flow evaluator with demo and live evidence modes."""

from __future__ import annotations

import importlib.util
import json
import sys
import uuid
from dataclasses import dataclass, field
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
        cookies: dict[str, str] | None = None,
        evidence_mode: str | None = None,
        secret_request: dict[str, Any] | None = None,
    ) -> GovernedFlowResult:
        trace_id = f"flow-{uuid.uuid4().hex[:12]}"
        request_id = f"req-{uuid.uuid4().hex[:12]}"
        mode = (evidence_mode or self._flow_mode or "demo").strip().lower()
        live_mode = mode == "live"
        base_metadata = dict(request_metadata or {})
        requested_path = str(base_metadata.get("requested_path", base_metadata.get("path", "/governed-flow")))
        identity_roles = list(roles or ["tenant_user"])

        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_paths = {
            "events_jsonl": self._artifact_dir / "events.jsonl",
            "launch_gate_result": self._artifact_dir / "launch-gate-result.json",
            "identity_evidence": self._artifact_dir / "identity-evidence.json",
            "policy_evidence": self._artifact_dir / "policy-evidence.json",
            "retrieval_evidence": self._artifact_dir / "retrieval-evidence.json",
            "secret_evidence": self._artifact_dir / "secret-evidence.json",
            "trace_correlation": self._artifact_dir / "trace-correlation.json",
            "governed_flow_summary": self._artifact_dir / "governed-flow-summary.json",
        }
        for path in artifact_paths.values():
            if path.exists():
                path.unlink()

        model = EventModel()
        sink = JsonlEventSink(str(artifact_paths["events_jsonl"]))

        session_id = ""

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

        emit(
            "request.start",
            {
                "path": requested_path,
                "actor": user_id,
                "evidence_mode": mode,
                "environment_mode": self._environment_mode,
            },
        )

        identity_request = IdentityResolutionRequest(
            authorization_header=authorization_header,
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

        identity_evidence = {
            "step": "identity",
            "trace_id": trace_id,
            "request_id": request_id,
            "session_id": session_id,
            "requested_path": requested_path,
            "evidence_mode": mode,
            "authenticated": identity_result.authenticated,
            "live": identity_result.live,
            "source": identity_result.source,
            "user_id": effective_user_id,
            "tenant_id": effective_tenant_id,
            "roles": effective_roles,
            "token_present": identity_result.token_present,
            "token_active": identity_result.token_active,
            "reason": identity_result.reason,
            "metadata": identity_result.metadata,
        }
        _write_json(artifact_paths["identity_evidence"], identity_evidence)
        emit(
            "identity.established",
            {
                "sub": effective_user_id,
                "tenant_id": effective_tenant_id,
                "roles": effective_roles,
                "live": identity_result.live,
                "identity_source": identity_result.source,
                "reason": identity_result.reason,
                "surface": str(base_metadata.get("surface", "")),
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
            },
            severity="info" if identity_result.authenticated else "warning",
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
        if identity_result.authenticated:
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
                },
            )
            gateway_decision = gateway.evaluate(normalized_request)
            policy_allow = gateway_decision.policy_allow
            policy_metadata = _metadata_for(self._policy_checker)
        else:
            gateway_decision = type(
                "DeniedGatewayDecision",
                (),
                {
                    "allow": False,
                    "reasons": [identity_result.reason or "identity.denied"],
                    "policy_allow": False,
                    "retrieval_allow": False,
                    "allowed_tools": [],
                    "denied_tools": list(requested_tools),
                },
            )()

        policy_evidence = {
            "step": "policy",
            "trace_id": trace_id,
            "request_id": request_id,
            "session_id": session_id,
            "evidence_mode": mode,
            "policy_source": policy_source,
            "policy_path": policy_path,
            "engine": policy_metadata.get("engine", "local"),
            "package_path": policy_metadata.get("package_path", ""),
            "allow": policy_allow,
            "reasons": list(gateway_decision.reasons),
            "matched_surface": str(policy_metadata.get("matched_surface", "")),
            "identity_live": identity_result.live,
        }
        _write_json(artifact_paths["policy_evidence"], policy_evidence)
        emit(
            "policy.decision",
            {
                "allow": policy_allow,
                "policy_source": policy_source,
                "policy_path": policy_path,
                "policy_engine": policy_metadata.get("engine", "local"),
                "package_path": policy_metadata.get("package_path", ""),
                "surface": str(base_metadata.get("surface", "")),
                "reason_codes": list(gateway_decision.reasons),
            },
            severity="info" if policy_allow else "warning",
        )

        retrieval_documents = []
        retrieval_execution = {
            "step": "retrieval",
            "trace_id": trace_id,
            "request_id": request_id,
            "session_id": session_id,
            "evidence_mode": mode,
            "backend": getattr(self._retrieval_backend, "__class__", type(self._retrieval_backend)).__name__,
            "source": retrieval_source,
            "tenant_id": effective_tenant_id,
            "filters": {},
            "result_count": 0,
            "live_backend": False,
            "allow": False,
            "mode": "skipped" if not retrieval_needed else "deny",
            "reasons": [],
        }
        if retrieval_needed and policy_allow:
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
                        "allow": retrieval_allow,
                        "mode": retrieval_result.mode,
                        "reasons": retrieval_reasons,
                    }
                )
            except Exception:
                retrieval_allow = False
                retrieval_reasons = ["retrieval.backend_unavailable"]
                retrieval_execution.update(
                    {
                        "live_backend": live_mode,
                        "allow": False,
                        "mode": "deny",
                        "reasons": retrieval_reasons,
                    }
                )
        elif retrieval_needed:
            retrieval_reasons = [reason for reason in gateway_decision.reasons if str(reason).startswith("retrieval.")]
            retrieval_execution.update(
                {
                    "allow": False,
                    "mode": "deny",
                    "reasons": retrieval_reasons or ["retrieval.denied_by_policy"],
                    "live_backend": live_mode,
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
                    "live_backend": live_mode and retrieval_needed,
                }
            )

        _write_json(artifact_paths["retrieval_evidence"], retrieval_execution)
        emit(
            "retrieval.decision",
            {
                "decision": retrieval_execution["mode"],
                "source": retrieval_source,
                "docs_filtered": retrieval_execution["result_count"],
                "reason_codes": retrieval_execution["reasons"],
                "backend": retrieval_execution["backend"],
                "live_backend": retrieval_execution["live_backend"],
            },
            severity="info" if retrieval_execution["allow"] else "warning",
        )
        emit(
            "retrieval.execution",
            {
                "backend": retrieval_execution["backend"],
                "collection": retrieval_execution.get("collection", ""),
                "filters": retrieval_execution["filters"],
                "result_count": retrieval_execution["result_count"],
                "live_backend": retrieval_execution["live_backend"],
            },
            severity="info" if retrieval_execution["allow"] else "warning",
        )

        secret_evidence = {
            "step": "secret",
            "trace_id": trace_id,
            "request_id": request_id,
            "session_id": session_id,
            "evidence_mode": mode,
            "required": secret_required,
            "purpose": str(secret_request.get("purpose", "")) if secret_request else "",
            "backend": "vault" if self._secret_provider else "unconfigured",
            "fetched": False,
            "reason": secret_reason,
        }
        if secret_required and policy_allow and retrieval_allow and self._secret_provider is not None:
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
            secret_evidence.update({"fetched": secret_fetch.fetched, "reason": secret_fetch.reason})
        elif secret_required:
            secret_reason = "secret.backend_missing"
            secret_satisfied = False
            secret_evidence.update({"fetched": False, "reason": secret_reason})
        else:
            secret_evidence.update({"fetched": False, "reason": "not_needed"})
        _write_json(artifact_paths["secret_evidence"], secret_evidence)
        emit(
            "secret.access",
            {
                "required": secret_required,
                "purpose": secret_evidence["purpose"],
                "backend": secret_evidence["backend"],
                "fetched": secret_evidence["fetched"],
                "reason": secret_evidence["reason"],
            },
            severity="info" if secret_satisfied or not secret_required else "warning",
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
                        {"tool_name": tool_name, "status": "executed", "surface": str(base_metadata.get("surface", ""))},
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
                            "surface": str(base_metadata.get("surface", "")),
                        },
                        severity="warning",
                    )
        else:
            if not policy_allow:
                tool_reasons.append("tool.skipped_due_to_policy")
            elif not retrieval_allow:
                tool_reasons.append("tool.skipped_due_to_retrieval")
            elif not secret_satisfied:
                tool_reasons.append("tool.skipped_due_to_secret")

        emit(
            "tool.decision",
            {
                "allowed": tools_allowed,
                "denied": tools_denied,
                "reasons": list(dict.fromkeys(tool_reasons)),
                "surface": str(base_metadata.get("surface", "")),
            },
            severity="info" if not tools_denied else "warning",
        )

        final_reasons = list(
            dict.fromkeys(
                [reason for reason in list(getattr(gateway_decision, "reasons", [])) if reason]
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
        emit("incident.signal", {"signal": "none" if preliminary_decision else "governed_path_blocked"})

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
        trace_complete = len(trace_missing_pre) == 0 and bool(session_id or not live_mode)

        evidence = {
            "identity.live": identity_result.authenticated and identity_result.live,
            "policy.live_opa": bool(policy_metadata.get("engine") == "opa" and policy_metadata.get("reachable", True)),
            "retrieval.live_backend": bool(retrieval_needed and retrieval_execution["live_backend"] and retrieval_execution["mode"] != "skipped"),
            "secret.access": bool(secret_required and secret_satisfied) or not secret_required,
            "trace.correlation": trace_complete,
            "handoff.decision": True,
            "policy.decision": "policy.decision" in observed_event_types,
            "retrieval.decision": "retrieval.decision" in observed_event_types,
            "tool.decision": "tool.decision" in observed_event_types,
            "incident.signal": "incident.signal" in observed_event_types,
        }
        controls = LAUNCH_GATE.live_controls(secret_required=secret_required) if live_mode else LAUNCH_GATE.default_controls()
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
                "score": gate_result.score,
                "max_score": gate_result.max_score,
                "missing_evidence": gate_result.missing_evidence,
                "blockers": gate_result.blockers,
                "evidence_mode": mode,
            },
            severity="info" if gate_result.decision == "pass" else "warning",
        )
        emit("fallback.event", {"applied": False, "evidence_mode": mode})
        emit(
            "deny.event",
            {
                "blocked": not final_decision,
                "reason": final_reasons[0] if final_reasons else "",
                "reason_code": final_reasons[0].split(":")[0] if final_reasons else "",
                "reasons": final_reasons,
                "surface": str(base_metadata.get("surface", "")),
                "requested_path": requested_path,
            },
            severity="warning" if not final_decision else "info",
        )
        emit(
            "handoff.decision",
            {
                "runtime_target": "onyx",
                "requested_path": requested_path,
                "allow": final_decision,
                "reason_codes": final_reasons,
                "evidence_mode": mode,
            },
            severity="info" if final_decision else "warning",
        )
        emit(
            "request.end",
            {
                "status": "ok" if final_decision else "denied",
                "decision": final_decision,
                "evidence_mode": mode,
            },
            severity="info" if final_decision else "warning",
        )

        final_recorded_events = [json.loads(line) for line in artifact_paths["events_jsonl"].read_text(encoding="utf-8").splitlines() if line.strip()]
        final_observed_event_types = {event["event_type"] for event in final_recorded_events}
        final_required_steps = pre_gate_required_steps + [
            "launch_gate.evaluated",
            "handoff.decision",
            "request.end",
        ]
        final_missing_steps = [step for step in final_required_steps if step not in final_observed_event_types]
        trace_correlation = {
            "trace_id": trace_id,
            "request_id": request_id,
            "session_id": session_id,
            "evidence_mode": mode,
            "environment_mode": self._environment_mode,
            "required_steps": final_required_steps,
            "observed_steps": sorted(final_observed_event_types),
            "missing_steps": final_missing_steps,
            "complete": len(final_missing_steps) == 0 and bool(session_id or not live_mode),
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
            "flow_metadata": {
                "trace_id": trace_id,
                "request_id": request_id,
                "session_id": session_id,
                "policy_source": policy_source,
                "policy_path": policy_path,
                "evidence_mode": mode,
                "artifacts": {"events_jsonl": _artifact_reference(artifact_paths["events_jsonl"], self._artifact_dir.parent.parent)},
            },
        }
        _write_json(artifact_paths["launch_gate_result"], launch_gate_artifact)

        governed_summary = {
            "trace_id": trace_id,
            "request_id": request_id,
            "session_id": session_id,
            "decision": final_decision,
            "reasons": final_reasons,
            "runtime_target": "onyx",
            "requested_path": requested_path,
            "evidence_mode": mode,
            "environment_mode": self._environment_mode,
            "identity": identity_evidence,
            "policy": policy_evidence,
            "retrieval": retrieval_execution,
            "secret": secret_evidence,
            "tools": {
                "allowed": tools_allowed,
                "denied": tools_denied,
                "reasons": list(dict.fromkeys(tool_reasons)),
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

        repo_root = Path(__file__).resolve().parent.parent
        relative_artifacts = {name: _artifact_reference(path, repo_root) for name, path in artifact_paths.items()}
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
        }

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
            dependency_status=dependency_status,
        )
