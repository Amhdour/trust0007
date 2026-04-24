from __future__ import annotations

from pathlib import Path
from typing import Any

from backend.trust_readiness.evidence import load_evidence_bundle
from backend.trust_readiness.incidents import append_incident_control
from backend.trust_readiness.readiness import compute_runtime_readiness

from ..enums import DestructiveRisk, FailureCategory, FreshnessStatus, RemediationStatus, RuntimeLane
from ..models import DiagnosticFinding, RemediationAction, RepairExecutionResult, iso_now, new_id
from ..store import RepairArtifactStore


def _common_safe_actions(lane: RuntimeLane) -> list[RemediationAction]:
    return [
        RemediationAction(
            action_id="recheck_health",
            lane=lane,
            description="Re-run lane health checks without changing runtime state.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.recheck_health",
            execution_handler="recheck_health",
            categories=[FailureCategory.REACHABILITY, FailureCategory.IDENTITY, FailureCategory.POLICY, FailureCategory.SECRETS],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="reprobe_routes",
            lane=lane,
            description="Probe expected local and public runtime routes and record observed reachability.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.reprobe_routes",
            execution_handler="reprobe_routes",
            categories=[FailureCategory.REACHABILITY, FailureCategory.CONFIG_DRIFT],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="retry_governed_handoff",
            lane=lane,
            description="Retry only the governed handoff evaluation path; never bypass policy.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.retry_governed_handoff",
            execution_handler="retry_governed_handoff",
            categories=[FailureCategory.LAUNCH_GATE, FailureCategory.CONTINUITY],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="refresh_runtime_proof",
            lane=lane,
            description="Refresh the repair evidence view of runtime proof without fabricating runtime continuity.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.refresh_runtime_proof",
            execution_handler="refresh_runtime_proof",
            categories=[FailureCategory.CONTINUITY, FailureCategory.EVIDENCE_FRESHNESS],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="refresh_evidence_bundle",
            lane=lane,
            description="Generate a repair evidence bundle from current append-only artifacts.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.refresh_evidence_bundle",
            execution_handler="refresh_evidence_bundle",
            categories=[FailureCategory.EVIDENCE_FRESHNESS, FailureCategory.POLICY, FailureCategory.IDENTITY, FailureCategory.SECRETS],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="re_evaluate_launch_gate",
            lane=lane,
            description="Recompute launch-gate posture from current evidence; does not force GO.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.re_evaluate_launch_gate",
            execution_handler="re_evaluate_launch_gate",
            categories=[FailureCategory.LAUNCH_GATE, FailureCategory.EVIDENCE_FRESHNESS],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="validate_runtime_config",
            lane=lane,
            description="Compare configured runtime lane targets with observed proof paths and routes.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.validate_runtime_config",
            execution_handler="validate_runtime_config",
            categories=[FailureCategory.CONFIG_DRIFT],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="validate_dependency_connectivity",
            lane=lane,
            description="Validate identity, policy, secret, telemetry, and audit dependency evidence.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.validate_dependency_connectivity",
            execution_handler="validate_dependency_connectivity",
            categories=[FailureCategory.IDENTITY, FailureCategory.POLICY, FailureCategory.SECRETS],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="surface_precise_blocker",
            lane=lane,
            description="Publish a precise blocker explanation for operators and dashboard users.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.NONE,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.surface_precise_blocker",
            execution_handler="surface_precise_blocker",
            categories=[category for category in FailureCategory],
            safe_to_auto_execute=True,
        ),
        RemediationAction(
            action_id="mark_lane_degraded",
            lane=lane,
            description="Record a degraded-mode incident control for the lane.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.LOW,
            requires_approval=False,
            reversible=True,
            policy_check_name="repair.mark_lane_degraded",
            execution_handler="mark_lane_degraded",
            categories=[FailureCategory.REACHABILITY, FailureCategory.CONTINUITY, FailureCategory.CONFIG_DRIFT],
            safe_to_auto_execute=False,
        ),
        RemediationAction(
            action_id="quarantine_lane",
            lane=lane,
            description="Quarantine runtime lane through incident controls until a human clears the blocker.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.MEDIUM,
            requires_approval=True,
            reversible=True,
            policy_check_name="repair.quarantine_lane",
            execution_handler="quarantine_lane",
            categories=[FailureCategory.LAUNCH_GATE, FailureCategory.TOOLS_MCP, FailureCategory.RETRIEVAL, FailureCategory.CONTINUITY],
            safe_to_auto_execute=False,
        ),
    ]


def _conditional_actions(lane: RuntimeLane) -> list[RemediationAction]:
    return [
        RemediationAction(
            action_id="restart_local_service",
            lane=lane,
            description="Restart only the local lane service. Restricted to non-production and approval-aware flows.",
            allowed_environments=["dev", "local", "staging", "stage"],
            destructive_risk=DestructiveRisk.MEDIUM,
            requires_approval=True,
            reversible=True,
            policy_check_name="repair.restart_local_service",
            execution_handler="restart_local_service",
            categories=[FailureCategory.REACHABILITY],
            safe_to_auto_execute=False,
        ),
        RemediationAction(
            action_id="reload_runtime_config",
            lane=lane,
            description="Reload runtime lane configuration from governed config sources.",
            allowed_environments=["dev", "local", "staging", "stage"],
            destructive_risk=DestructiveRisk.LOW,
            requires_approval=True,
            reversible=True,
            policy_check_name="repair.reload_runtime_config",
            execution_handler="reload_runtime_config",
            categories=[FailureCategory.CONFIG_DRIFT],
            safe_to_auto_execute=False,
        ),
        RemediationAction(
            action_id="rotate_nonhuman_runtime_credential",
            lane=lane,
            description="Rotate non-human runtime credential through approved secret workflow.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.HIGH,
            requires_approval=True,
            reversible=False,
            policy_check_name="repair.rotate_nonhuman_runtime_credential",
            execution_handler="rotate_nonhuman_runtime_credential",
            categories=[FailureCategory.SECRETS],
            safe_to_auto_execute=False,
        ),
        RemediationAction(
            action_id="reseed_nonprod_test_data",
            lane=lane,
            description="Reseed non-production test data used by diagnostics.",
            allowed_environments=["dev", "local", "staging", "stage"],
            destructive_risk=DestructiveRisk.MEDIUM,
            requires_approval=True,
            reversible=False,
            policy_check_name="repair.reseed_nonprod_test_data",
            execution_handler="reseed_nonprod_test_data",
            categories=[FailureCategory.RETRIEVAL, FailureCategory.TOOLS_MCP],
            safe_to_auto_execute=False,
        ),
        RemediationAction(
            action_id="resync_policy_bundle",
            lane=lane,
            description="Resync policy bundle from governed source. Production requires elevated approval.",
            allowed_environments=["dev", "local", "staging", "stage", "production", "prod", "live"],
            destructive_risk=DestructiveRisk.HIGH,
            requires_approval=True,
            reversible=True,
            policy_check_name="repair.resync_policy_bundle",
            execution_handler="resync_policy_bundle",
            categories=[FailureCategory.POLICY],
            safe_to_auto_execute=False,
        ),
    ]


def action_catalog(lane: RuntimeLane) -> list[RemediationAction]:
    return _common_safe_actions(lane) + _conditional_actions(lane)


def actions_for_findings(lane: RuntimeLane, findings: list[DiagnosticFinding]) -> list[RemediationAction]:
    categories = {finding.category for finding in findings}
    selected: dict[str, RemediationAction] = {}
    for action in action_catalog(lane):
        if categories.intersection(action.categories):
            selected[action.action_id] = action
    if findings and "surface_precise_blocker" not in selected:
        selected["surface_precise_blocker"] = next(action for action in action_catalog(lane) if action.action_id == "surface_precise_blocker")
    return list(selected.values())


def execute_remediation_action(
    action: RemediationAction,
    *,
    repair_run_id: str,
    tenant_id: str,
    runtime_id: str,
    correlation_id: str,
    actor_id: str,
    decision_id: str,
    root: Path | None,
    dry_run: bool = False,
    findings: list[DiagnosticFinding] | None = None,
) -> RepairExecutionResult:
    started_at = iso_now()
    store = RepairArtifactStore(root)
    evidence_refs: list[str] = []
    status = RemediationStatus.DRY_RUN if dry_run else RemediationStatus.EXECUTED
    reason_codes = [f"repair.{action.action_id}.dry_run" if dry_run else f"repair.{action.action_id}.executed"]
    details: dict[str, Any] = {"destructive_risk": action.destructive_risk.value, "reversible": action.reversible}

    if not dry_run:
        if action.execution_handler == "refresh_evidence_bundle":
            bundle = load_evidence_bundle(root).to_bundle(runtime_id)
            event_ref = store.append_event(_event_payload(action, repair_run_id, tenant_id, runtime_id, correlation_id, actor_id, decision_id, "evidence_bundle_refreshed", bundle))
            evidence_refs.append(event_ref)
            details["bundle"] = bundle
        elif action.execution_handler == "refresh_runtime_proof":
            bundle = load_evidence_bundle(root)
            refs = bundle.evidence_refs()
            proof_ref = "overlays/myStarterKit/artifacts/onyx-runtime-proof.json" if action.lane == RuntimeLane.ONYX else "overlays/myStarterKit/artifacts/onyx-agent-runtime-proof.json"
            evidence_refs.append(proof_ref)
            details["proof_ref"] = proof_ref
            details["note"] = "Existing runtime proof was referenced; repair did not fabricate continuity."
        elif action.execution_handler == "re_evaluate_launch_gate":
            readiness = compute_runtime_readiness(root, runtime_id=runtime_id)
            details["readiness"] = readiness.to_dict()
            evidence_refs.extend([ref for signal in readiness.signals for ref in signal.evidence_refs])
        elif action.execution_handler in {"mark_lane_degraded", "quarantine_lane"}:
            control_type = "runtime_quarantine" if action.execution_handler == "quarantine_lane" else "break_glass"
            control = append_incident_control(
                runtime_id=runtime_id,
                control_type=control_type,
                tenant_id=tenant_id,
                actor_id=actor_id,
                reason=f"repair.{action.action_id}:{','.join(f.reason_codes[0] if f.reason_codes else f.category.value for f in findings or [])}",
                root=root,
            )
            evidence_refs.append(control.audit_ref)
            details["incident_control"] = control.to_dict()
        elif action.execution_handler in {
            "restart_local_service",
            "reload_runtime_config",
            "rotate_nonhuman_runtime_credential",
            "reseed_nonprod_test_data",
            "resync_policy_bundle",
        }:
            status = RemediationStatus.SKIPPED
            reason_codes = [f"repair.{action.action_id}.requires_external_operator"]
            details["note"] = "This bounded action is policy-gated but intentionally not executed by the local repair subsystem."
        else:
            details["observed_readiness"] = compute_runtime_readiness(root, runtime_id=runtime_id).to_dict()

    completed_at = iso_now()
    result = RepairExecutionResult(
        result_id=new_id("repair-result"),
        repair_run_id=repair_run_id,
        action_id=action.action_id,
        lane=action.lane,
        tenant_id=tenant_id,
        runtime_id=runtime_id,
        correlation_id=correlation_id,
        actor_id=actor_id,
        decision_id=decision_id,
        status=status,
        result="dry-run only" if dry_run else ("executed bounded remediation" if status == RemediationStatus.EXECUTED else "skipped"),
        reason_codes=reason_codes,
        evidence_refs=sorted(set(evidence_refs)),
        started_at=started_at,
        completed_at=completed_at,
        freshness=FreshnessStatus.FRESH,
        details=details,
    )
    store.append_event(_event_payload(action, repair_run_id, tenant_id, runtime_id, correlation_id, actor_id, decision_id, str(status.value), result.to_dict()))
    return result


def _event_payload(
    action: RemediationAction,
    repair_run_id: str,
    tenant_id: str,
    runtime_id: str,
    correlation_id: str,
    actor_id: str,
    decision_id: str,
    result: str,
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "event_type": "runtime_repair.remediation",
        "repair_run_id": repair_run_id,
        "correlation_id": correlation_id,
        "tenant_id": tenant_id,
        "actor_id": actor_id,
        "lane": action.lane.value,
        "runtime_id": runtime_id,
        "decision_id": decision_id,
        "action_id": action.action_id,
        "result": result,
        "reason_codes": [f"repair.{action.action_id}"],
        "timestamps": {"captured_at": iso_now()},
        "freshness": FreshnessStatus.FRESH.value,
        "trace_links": [],
        "source_references": [],
        "details": details,
    }
