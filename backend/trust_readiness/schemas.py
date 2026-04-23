from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ReadinessState(str, Enum):
    READY = "READY"
    READY_WITH_EXCEPTIONS = "READY_WITH_EXCEPTIONS"
    BLOCKED = "BLOCKED"
    DEGRADED = "DEGRADED"
    UNDER_REVIEW = "UNDER_REVIEW"
    INCIDENT_MODE = "INCIDENT_MODE"


SignalStatus = Literal["pass", "fail", "missing", "stale", "degraded", "review"]
RuntimeClass = Literal["onyx_governed_runtime", "rag"]
DecisionStatus = Literal["allow", "deny", "review"]


@dataclass(frozen=True)
class RuntimeDescriptor:
    runtime_id: str
    label: str
    runtime_class: RuntimeClass
    launch_path: str
    launch_route: str
    governance_lane: str
    primary_controls: list[str]
    fail_closed: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceSignal:
    signal_id: str
    label: str
    status: SignalStatus
    mandatory: bool
    observed_at: str = ""
    reason_codes: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RuntimeReadiness:
    runtime_id: str
    runtime_class: RuntimeClass
    state: ReadinessState
    score: int
    generated_at: str
    signals: list[EvidenceSignal]
    blockers: list[str] = field(default_factory=list)
    exceptions: list[str] = field(default_factory=list)
    degraded_dependencies: list[str] = field(default_factory=list)
    launch_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["state"] = self.state.value
        payload["signals"] = [signal.to_dict() for signal in self.signals]
        return payload


@dataclass(frozen=True)
class PolicyDecisionTrace:
    decision_id: str
    policy_id: str
    status: DecisionStatus
    default_deny: bool
    reason_codes: list[str]
    evaluated_rules: list[str]
    inputs: dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(default_factory=iso_now)

    @property
    def allow(self) -> bool:
        return self.status == "allow"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["allow"] = self.allow
        return payload


@dataclass(frozen=True)
class LaunchDecisionExplanation:
    decision_id: str
    launch_request_id: str
    runtime_id: str
    status: DecisionStatus
    readiness_state: ReadinessState
    reason_codes: list[str]
    evidence_refs: list[str]
    generated_at: str = field(default_factory=iso_now)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["readiness_state"] = self.readiness_state.value
        return payload


@dataclass(frozen=True)
class AuditEventRecord:
    audit_id: str
    timestamp: str
    correlation_id: str
    tenant_id: str
    actor_id: str
    runtime_id: str
    event_type: str
    outcome: str
    tool_id: str = ""
    decision_id: str = ""
    launch_request_id: str = ""
    reason_codes: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IncidentControl:
    control_id: str
    runtime_id: str
    control_type: Literal[
        "emergency_revoke",
        "runtime_quarantine",
        "tool_disable",
        "retrieval_isolation",
        "break_glass",
    ]
    active: bool
    tenant_id: str
    actor_id: str
    reason: str
    created_at: str
    expires_at: str = ""
    tool_id: str = ""
    audit_ref: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
