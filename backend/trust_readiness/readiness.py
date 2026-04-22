from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import DIFY_RUNTIME_PROOF_PATH, ONYX_RUNTIME_PROOF_PATH, read_json

from .evidence import evidence_age_status, latest_timestamp, load_evidence_bundle
from .incidents import active_incident_controls
from .runtime_registry import runtime_descriptor, runtime_descriptors
from .schemas import EvidenceSignal, ReadinessState, RuntimeReadiness


def _signal(
    signal_id: str,
    label: str,
    status: str,
    mandatory: bool,
    *,
    observed_at: str = "",
    reason_codes: list[str] | None = None,
    evidence_ref: str = "",
    details: dict[str, Any] | None = None,
) -> EvidenceSignal:
    refs = [evidence_ref] if evidence_ref else []
    return EvidenceSignal(
        signal_id=signal_id,
        label=label,
        status=status,  # type: ignore[arg-type]
        mandatory=mandatory,
        observed_at=observed_at,
        reason_codes=list(reason_codes or []),
        evidence_refs=refs,
        details=dict(details or {}),
    )


def _freshness_signal(name: str, timestamp: str, evidence_ref: str) -> EvidenceSignal:
    age = evidence_age_status(timestamp)
    status = {"fresh": "pass", "aging": "review", "stale": "stale", "missing": "missing"}[age]
    return _signal(
        name,
        "Evidence freshness",
        status,
        True,
        observed_at=timestamp,
        reason_codes=[] if status == "pass" else [f"evidence.{age}"],
        evidence_ref=evidence_ref,
        details={"age_bucket": age},
    )


def _runtime_matches(runtime_id: str, summary: dict[str, Any], tool: dict[str, Any]) -> bool:
    observed = str(summary.get("runtime_target") or tool.get("runtime_target") or "")
    return not observed or observed == runtime_id


def _runtime_specific_proof_current(root: Path, runtime_id: str) -> bool:
    proof_path = ONYX_RUNTIME_PROOF_PATH if runtime_id == "onyx" else DIFY_RUNTIME_PROOF_PATH
    proof = read_json(root / proof_path)
    if not proof:
        return False
    observed_runtime = str(proof.get("runtime_key") or proof.get("runtime_target") or runtime_id)
    if observed_runtime != runtime_id:
        return False
    if not bool(proof.get("handoff_allowed", False)):
        return False
    if str(proof.get("evidence_mode", "")) == "demo":
        return False
    continuity = proof.get("continuity", {}) if isinstance(proof.get("continuity"), dict) else {}
    if str(continuity.get("status", "")) in {"", "no_runtime_activity", "blocked_before_runtime"}:
        return False
    observed_at = latest_timestamp(proof)
    if observed_at and evidence_age_status(observed_at) == "stale":
        return False
    return True


def compute_runtime_readiness(root: Path | None = None, *, runtime_id: str = "onyx") -> RuntimeReadiness:
    descriptor = runtime_descriptor(runtime_id)
    bundle = load_evidence_bundle(root)
    refs = bundle.evidence_refs()
    runtime_current = _runtime_matches(descriptor.runtime_id, bundle.summary, bundle.tool) or _runtime_specific_proof_current(bundle.root, descriptor.runtime_id)
    signals: list[EvidenceSignal] = []

    identity_ok = bool(bundle.identity.get("authenticated", False))
    signals.append(
        _signal(
            "identity_health",
            "Identity health",
            "pass" if identity_ok else "fail",
            True,
            observed_at=str(bundle.identity.get("timestamp") or bundle.identity.get("captured_at", "")),
            reason_codes=[] if identity_ok else [str(bundle.identity.get("reason") or "identity.unhealthy")],
            evidence_ref=refs["identity"],
            details={
                "source": bundle.identity.get("source", ""),
                "live": bool(bundle.identity.get("live", False)),
                "session_id": bundle.identity.get("session_id", ""),
            },
        )
    )

    policy_ok = bool(bundle.policy.get("allow", False)) and bool(bundle.policy.get("engine_reachable", True))
    signals.append(
        _signal(
            "policy_evaluation",
            "Policy evaluation",
            "pass" if policy_ok else "fail",
            True,
            observed_at=str(bundle.policy.get("timestamp") or bundle.policy.get("captured_at", "")),
            reason_codes=list(bundle.policy.get("reason_codes", [])) if not policy_ok else [],
            evidence_ref=refs["policy"],
            details={"engine": bundle.policy.get("engine", ""), "reachable": bundle.policy.get("engine_reachable", True)},
        )
    )

    secret_required = bool(bundle.secret.get("required", False))
    secret_ok = (not secret_required) or bool(bundle.secret.get("fetched", False))
    signals.append(
        _signal(
            "secret_health",
            "Secret health",
            "pass" if secret_ok else "fail",
            True,
            observed_at=str(bundle.secret.get("timestamp") or bundle.secret.get("captured_at", "")),
            reason_codes=[] if secret_ok else list(bundle.secret.get("reason_codes", []) or ["secret.unhealthy"]),
            evidence_ref=refs["secret"],
            details={"required": secret_required, "backend": bundle.secret.get("backend", "")},
        )
    )

    retrieval_mandatory = descriptor.runtime_id == "onyx"
    retrieval_ok = (not retrieval_mandatory and not bundle.retrieval) or bool(bundle.retrieval.get("allow", False))
    retrieval_status = "pass" if retrieval_ok else "fail"
    if bundle.retrieval.get("mode") == "degrade":
        retrieval_status = "degraded"
    signals.append(
        _signal(
            "retrieval_boundary",
            "Retrieval boundary",
            retrieval_status,
            retrieval_mandatory,
            observed_at=str(bundle.retrieval.get("timestamp") or bundle.retrieval.get("captured_at", "")),
            reason_codes=[] if retrieval_ok else list(bundle.retrieval.get("reason_codes", []) or ["retrieval.unhealthy"]),
            evidence_ref=refs["retrieval"],
            details={
                "source": bundle.retrieval.get("source", ""),
                "backend_verified": bundle.retrieval.get("backend_verified", False),
                "result_count": bundle.retrieval.get("result_count", 0),
            },
        )
    )

    tool_required = descriptor.runtime_id == "dify"
    denied_tools = list(bundle.tool.get("denied_tools", []))
    mcp_governed = bool(bundle.tool.get("mcp_governed", False))
    tool_ok = not denied_tools and ((not tool_required) or mcp_governed)
    signals.append(
        _signal(
            "mcp_tool_authorization",
            "Tool and MCP authorization",
            "pass" if tool_ok else "fail",
            tool_required,
            observed_at=str(bundle.tool.get("timestamp") or bundle.tool.get("captured_at", "")),
            reason_codes=[] if tool_ok else list(bundle.tool.get("reason_codes", []) or ["tool.mcp_unhealthy"]),
            evidence_ref=refs["tool"],
            details={
                "mcp_server": bundle.tool.get("mcp_server", ""),
                "allowed_tools": bundle.tool.get("allowed_tools", []),
                "denied_tools": denied_tools,
            },
        )
    )

    trace_ok = bool(bundle.trace.get("complete", False))
    signals.append(
        _signal(
            "telemetry_heartbeat",
            "Telemetry heartbeat",
            "pass" if bundle.events else "missing",
            True,
            observed_at=latest_timestamp(*bundle.events[-5:]),
            reason_codes=[] if bundle.events else ["telemetry.missing"],
            evidence_ref=refs["events"],
            details={"event_count": len(bundle.events)},
        )
    )
    signals.append(
        _signal(
            "audit_pipeline",
            "Audit pipeline",
            "pass" if bundle.audit_records and trace_ok else "fail",
            True,
            observed_at=latest_timestamp(*bundle.audit_records[-5:]),
            reason_codes=[] if bundle.audit_records and trace_ok else ["audit.pipeline_unhealthy"],
            evidence_ref=refs["audit"],
            details={"record_count": len(bundle.audit_records), "trace_complete": trace_ok},
        )
    )

    launch_machine = bundle.launch_gate.get("machine", {})
    launch_decision = str(launch_machine.get("decision", ""))
    launch_ok = launch_decision == "pass"
    signals.append(
        _signal(
            "launch_gate",
            "Launch gate",
            "pass" if launch_ok else ("review" if launch_decision == "conditional_go" else "fail"),
            True,
            observed_at=str(bundle.launch_gate.get("generated_at") or bundle.summary.get("timestamp") or ""),
            reason_codes=list(launch_machine.get("blockers", [])) + list(launch_machine.get("missing_evidence", [])),
            evidence_ref=refs["launch_gate"],
            details={"decision": launch_decision, "score": launch_machine.get("score"), "max_score": launch_machine.get("max_score")},
        )
    )

    signals.append(_freshness_signal("evidence_freshness", latest_timestamp(bundle.identity, bundle.policy, bundle.retrieval, bundle.secret, bundle.tool, bundle.trace), refs["summary"]))

    signals.append(
        _signal(
            "red_team_eval_status",
            "Red-team and eval status",
            "review",
            False,
            reason_codes=["eval.external_status_not_attached"],
            details={"note": "Attach CI or eval-suite results to promote this optional signal to pass."},
        )
    )

    incidents = active_incident_controls(root, runtime_id=descriptor.runtime_id)
    exceptions = [
        str(item.get("waiver_id") or item.get("exception_id") or item.get("id"))
        for item in bundle.exceptions_waivers
        if str(item.get("runtime_id", descriptor.runtime_id)) in {"", descriptor.runtime_id}
    ]
    blockers = [
        reason
        for signal in signals
        if signal.mandatory and signal.status in {"fail", "missing", "stale"}
        for reason in (signal.reason_codes or [signal.signal_id])
    ]
    degraded = [signal.signal_id for signal in signals if signal.status == "degraded"]
    if not runtime_current:
        degraded.append("runtime.latest_evidence_from_other_lane")

    if incidents:
        state = ReadinessState.INCIDENT_MODE
        blockers.extend(str(item.get("control_type", "incident.active")) for item in incidents)
    elif blockers:
        state = ReadinessState.BLOCKED
    elif degraded:
        state = ReadinessState.DEGRADED
    elif exceptions or any(signal.status == "review" for signal in signals if not signal.mandatory):
        state = ReadinessState.READY_WITH_EXCEPTIONS
    elif any(signal.status == "review" for signal in signals if signal.mandatory):
        state = ReadinessState.UNDER_REVIEW
    else:
        state = ReadinessState.READY

    mandatory = [signal for signal in signals if signal.mandatory]
    passed = [signal for signal in mandatory if signal.status == "pass"]
    score = round((len(passed) / len(mandatory)) * 100) if mandatory else 0
    return RuntimeReadiness(
        runtime_id=descriptor.runtime_id,
        runtime_class=descriptor.runtime_class,
        state=state,
        score=score,
        generated_at=datetime.now(timezone.utc).isoformat(),
        signals=signals,
        blockers=sorted(set(blockers)),
        exceptions=sorted(set(exceptions)),
        degraded_dependencies=sorted(set(degraded)),
        launch_allowed=state in {ReadinessState.READY, ReadinessState.READY_WITH_EXCEPTIONS},
    )


def compute_fleet_readiness(root: Path | None = None) -> list[RuntimeReadiness]:
    return [compute_runtime_readiness(root, runtime_id=runtime.runtime_id) for runtime in runtime_descriptors()]
