from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ReadinessStatus = Literal["pass", "warn", "fail", "unknown"]
ReadinessSeverity = Literal["low", "medium", "high", "critical"]
TrustLaunchGateStatus = Literal["APPROVED", "CONDITIONAL", "BLOCKED", "UNKNOWN"]


@dataclass(frozen=True)
class TrustEvidenceItem:
    source: str
    value: str
    details: dict[str, Any]


@dataclass(frozen=True)
class OnyxReadinessCheck:
    id: str
    category: str
    title: str
    status: ReadinessStatus
    severity: ReadinessSeverity
    score: int
    description: str
    evidence: TrustEvidenceItem
    recommendation: str


@dataclass(frozen=True)
class OnyxRiskSummary:
    critical: int
    high: int
    medium: int
    low: int


@dataclass(frozen=True)
class OnyxCapabilities:
    rag: bool
    connectors: bool
    agents: bool
    mcp: bool
    tools: bool


@dataclass(frozen=True)
class OnyxReadinessResponse:
    provider: str
    system: str
    component_type: str
    environment: str
    generated_at: str
    overall_status: ReadinessStatus
    overall_score: int
    checks: list[OnyxReadinessCheck]
    risk_summary: OnyxRiskSummary
    capabilities: OnyxCapabilities
    message: str = ""
    reachable: bool = True


@dataclass(frozen=True)
class LaunchGateCategory:
    name: str
    status: ReadinessStatus
    score: int
    failed_checks: list[str]
    warning_checks: list[str]
    unknown_checks: list[str]
    remediations: list[str]


@dataclass(frozen=True)
class OnyxLaunchGateSummary:
    decision: TrustLaunchGateStatus
    categories: list[LaunchGateCategory]
    evidence_summary: list[TrustEvidenceItem]
    remediation_list: list[str]
