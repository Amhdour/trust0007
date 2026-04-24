from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from backend.trust_readiness.schemas import RuntimeReadiness

from .enums import (
    DestructiveRisk,
    FailureCategory,
    FreshnessStatus,
    RemediationStatus,
    RepairMode,
    RepairPolicyStatus,
    RepairRunStatus,
    RuntimeLane,
    Severity,
)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


@dataclass(frozen=True)
class DiagnosticFinding:
    finding_id: str
    lane: RuntimeLane
    tenant_id: str
    runtime_id: str
    severity: Severity
    category: FailureCategory
    title: str
    detail: str
    evidence_used: list[str]
    correlation_id: str
    actor_id: str
    decision_id: str
    detected_at: str = field(default_factory=iso_now)
    freshness: FreshnessStatus = FreshnessStatus.FRESH
    safe_to_auto_execute: bool = False
    requires_approval: bool = False
    policy_basis: list[str] = field(default_factory=list)
    remediation_status: RemediationStatus = RemediationStatus.NOT_PLANNED
    reason_codes: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lane"] = self.lane.value
        payload["severity"] = self.severity.value
        payload["category"] = self.category.value
        payload["freshness"] = self.freshness.value
        payload["remediation_status"] = self.remediation_status.value
        return payload


@dataclass(frozen=True)
class DiagnosticReport:
    report_id: str
    lane: RuntimeLane
    tenant_id: str
    runtime_id: str
    correlation_id: str
    actor_id: str
    generated_at: str
    findings: list[DiagnosticFinding]
    evidence_refs: dict[str, str]
    readiness_before: dict[str, Any]
    summary: str

    @property
    def has_critical_findings(self) -> bool:
        return any(finding.severity == Severity.CRITICAL for finding in self.findings)

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "lane": self.lane.value,
            "tenant_id": self.tenant_id,
            "runtime_id": self.runtime_id,
            "correlation_id": self.correlation_id,
            "actor_id": self.actor_id,
            "generated_at": self.generated_at,
            "findings": [finding.to_dict() for finding in self.findings],
            "evidence_refs": self.evidence_refs,
            "readiness_before": self.readiness_before,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class RemediationAction:
    action_id: str
    lane: RuntimeLane
    description: str
    allowed_environments: list[str]
    destructive_risk: DestructiveRisk
    requires_approval: bool
    reversible: bool
    policy_check_name: str
    execution_handler: str
    categories: list[FailureCategory]
    safe_to_auto_execute: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lane"] = self.lane.value
        payload["destructive_risk"] = self.destructive_risk.value
        payload["categories"] = [category.value for category in self.categories]
        return payload


@dataclass(frozen=True)
class RepairPolicyDecision:
    decision_id: str
    action_id: str
    lane: RuntimeLane
    tenant_id: str
    actor_id: str
    status: RepairPolicyStatus
    reason_codes: list[str]
    policy_basis: list[str]
    evaluated_at: str = field(default_factory=iso_now)
    requires_approval: bool = False
    approved: bool = False
    environment: str = "dev"

    @property
    def allow(self) -> bool:
        return self.status == RepairPolicyStatus.ALLOW

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lane"] = self.lane.value
        payload["status"] = self.status.value
        payload["allow"] = self.allow
        return payload


@dataclass(frozen=True)
class RemediationPlan:
    plan_id: str
    report_id: str
    lane: RuntimeLane
    tenant_id: str
    runtime_id: str
    correlation_id: str
    actor_id: str
    generated_at: str
    actions: list[RemediationAction]
    policy_decisions: list[RepairPolicyDecision]
    findings: list[DiagnosticFinding]
    readiness_before: dict[str, Any]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "report_id": self.report_id,
            "lane": self.lane.value,
            "tenant_id": self.tenant_id,
            "runtime_id": self.runtime_id,
            "correlation_id": self.correlation_id,
            "actor_id": self.actor_id,
            "generated_at": self.generated_at,
            "actions": [action.to_dict() for action in self.actions],
            "policy_decisions": [decision.to_dict() for decision in self.policy_decisions],
            "findings": [finding.to_dict() for finding in self.findings],
            "readiness_before": self.readiness_before,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class RepairExecutionResult:
    result_id: str
    repair_run_id: str
    action_id: str
    lane: RuntimeLane
    tenant_id: str
    runtime_id: str
    correlation_id: str
    actor_id: str
    decision_id: str
    status: RemediationStatus
    result: str
    reason_codes: list[str]
    evidence_refs: list[str]
    started_at: str
    completed_at: str
    freshness: FreshnessStatus = FreshnessStatus.FRESH
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["lane"] = self.lane.value
        payload["status"] = self.status.value
        payload["freshness"] = self.freshness.value
        return payload


@dataclass(frozen=True)
class RepairRun:
    run_id: str
    mode: RepairMode
    lane: RuntimeLane
    tenant_id: str
    runtime_id: str
    correlation_id: str
    actor_id: str
    status: RepairRunStatus
    started_at: str
    completed_at: str
    report: DiagnosticReport | None
    plan: RemediationPlan | None
    execution_results: list[RepairExecutionResult]
    readiness_before: dict[str, Any]
    readiness_after: dict[str, Any]
    audit_refs: list[str]
    evidence_refs: list[str]
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "mode": self.mode.value,
            "lane": self.lane.value,
            "tenant_id": self.tenant_id,
            "runtime_id": self.runtime_id,
            "correlation_id": self.correlation_id,
            "actor_id": self.actor_id,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "report": self.report.to_dict() if self.report else None,
            "plan": self.plan.to_dict() if self.plan else None,
            "execution_results": [result.to_dict() for result in self.execution_results],
            "readiness_before": self.readiness_before,
            "readiness_after": self.readiness_after,
            "readiness_impact": {
                "before_state": self.readiness_before.get("state", ""),
                "after_state": self.readiness_after.get("state", ""),
                "before_score": self.readiness_before.get("score", 0),
                "after_score": self.readiness_after.get("score", 0),
                "blockers": self.readiness_after.get("blockers", []),
            },
            "audit_refs": self.audit_refs,
            "evidence_refs": self.evidence_refs,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class LaneRepairStatus:
    lane: RuntimeLane
    tenant_id: str
    runtime_id: str
    generated_at: str
    readiness: RuntimeReadiness
    latest_report: dict[str, Any] | None
    latest_plan: dict[str, Any] | None
    latest_run: dict[str, Any] | None
    safe_auto_remediation_candidates: list[dict[str, Any]]
    blocked_remediation_attempts: list[dict[str, Any]]
    audit_refs: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "lane": self.lane.value,
            "tenant_id": self.tenant_id,
            "runtime_id": self.runtime_id,
            "generated_at": self.generated_at,
            "readiness": self.readiness.to_dict(),
            "latest_report": self.latest_report,
            "latest_plan": self.latest_plan,
            "latest_run": self.latest_run,
            "safe_auto_remediation_candidates": self.safe_auto_remediation_candidates,
            "blocked_remediation_attempts": self.blocked_remediation_attempts,
            "audit_refs": self.audit_refs,
        }
