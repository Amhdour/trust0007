from __future__ import annotations

from pathlib import Path
from typing import Any

from .enums import RepairMode, RuntimeLane
from .orchestrator import GovernedRuntimeRepairOrchestrator
from .store import RepairArtifactStore


def lane_from_value(value: str) -> RuntimeLane:
    normalized = value.strip().lower()
    if normalized == "dify":
        return RuntimeLane.DIFY
    return RuntimeLane.ONYX


def build_repair_center(root: Path | None = None, *, tenant_id: str = "tenant-a") -> dict[str, Any]:
    return GovernedRuntimeRepairOrchestrator(root).fleet_repair_status(tenant_id=tenant_id)


def diagnose_lane(root: Path | None, lane: RuntimeLane, payload: dict[str, Any]) -> dict[str, Any]:
    orchestrator = GovernedRuntimeRepairOrchestrator(root)
    report = orchestrator.diagnose(
        lane,
        tenant_id=str(payload.get("tenant_id", "tenant-a")),
        actor_id=str(payload.get("actor_id", "repair-operator")),
        correlation_id=str(payload.get("correlation_id", "")),
        environment=str(payload.get("environment", "dev")),
    )
    return {
        "summary": report.summary,
        "lane": lane.value,
        "correlation_id": report.correlation_id,
        "readiness_impact": {
            "before_state": report.readiness_before.get("state", ""),
            "blocker_count": len(report.readiness_before.get("blockers", [])),
        },
        "audit_refs": ["overlays/myStarterKit/artifacts/audit-records.jsonl"],
        "evidence_refs": report.evidence_refs,
        "details": report.to_dict(),
    }


def plan_lane(root: Path | None, lane: RuntimeLane, payload: dict[str, Any]) -> dict[str, Any]:
    orchestrator = GovernedRuntimeRepairOrchestrator(root)
    plan = orchestrator.plan(
        lane,
        tenant_id=str(payload.get("tenant_id", "tenant-a")),
        actor_id=str(payload.get("actor_id", "repair-operator")),
        actor_roles=list(payload.get("actor_roles", [])) if isinstance(payload.get("actor_roles", []), list) else [],
        correlation_id=str(payload.get("correlation_id", "")),
        environment=str(payload.get("environment", "dev")),
        approved_actions=list(payload.get("approved_actions", [])) if isinstance(payload.get("approved_actions", []), list) else [],
    )
    return {
        "summary": plan.summary,
        "lane": lane.value,
        "correlation_id": plan.correlation_id,
        "readiness_impact": {
            "before_state": plan.readiness_before.get("state", ""),
            "safe_auto_actions": [
                action.action_id
                for action, decision in zip(plan.actions, plan.policy_decisions)
                if action.safe_to_auto_execute and decision.allow
            ],
        },
        "audit_refs": ["overlays/myStarterKit/artifacts/audit-records.jsonl"],
        "evidence_refs": ["overlays/myStarterKit/artifacts/runtime-repair/diagnostic-reports.json"],
        "details": plan.to_dict(),
    }


def execute_lane(root: Path | None, lane: RuntimeLane, payload: dict[str, Any]) -> dict[str, Any]:
    mode = RepairMode.EXECUTE_SAFE
    if payload.get("dry_run"):
        mode = RepairMode.DRY_RUN
    if payload.get("action_id"):
        mode = RepairMode.EXECUTE_ACTION
    orchestrator = GovernedRuntimeRepairOrchestrator(root)
    run = orchestrator.run(
        lane,
        mode=mode,
        tenant_id=str(payload.get("tenant_id", "tenant-a")),
        actor_id=str(payload.get("actor_id", "repair-operator")),
        actor_roles=list(payload.get("actor_roles", [])) if isinstance(payload.get("actor_roles", []), list) else [],
        correlation_id=str(payload.get("correlation_id", "")),
        environment=str(payload.get("environment", "dev")),
        approved_actions=list(payload.get("approved_actions", [])) if isinstance(payload.get("approved_actions", []), list) else [],
        action_id=str(payload.get("action_id", "")),
        dry_run=bool(payload.get("dry_run", False)),
    )
    payload_out = run.to_dict()
    return {
        "summary": run.summary,
        "lane": lane.value,
        "correlation_id": run.correlation_id,
        "readiness_impact": payload_out["readiness_impact"],
        "audit_refs": run.audit_refs,
        "evidence_refs": run.evidence_refs,
        "details": payload_out,
    }


def get_repair_run(root: Path | None, run_id: str) -> dict[str, Any]:
    return RepairArtifactStore(root).get_run(run_id)


def list_repair_runs(root: Path | None) -> dict[str, Any]:
    return {"runs": RepairArtifactStore(root).runs()}


def get_repair_plan(root: Path | None, plan_id: str) -> dict[str, Any]:
    return RepairArtifactStore(root).get_plan(plan_id)
