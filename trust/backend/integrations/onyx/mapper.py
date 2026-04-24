from __future__ import annotations

from collections import defaultdict

from .types import LaunchGateCategory, OnyxLaunchGateSummary, OnyxReadinessCheck, OnyxReadinessResponse, TrustEvidenceItem

_CATEGORY_MAP = {
    "identity": "Identity & Access",
    "auth": "Identity & Access",
    "retrieval": "Retrieval Security",
    "search": "Retrieval Security",
    "connector": "Connector Boundary",
    "integration": "Connector Boundary",
    "prompt": "RAG Prompt/Context Safety",
    "context": "RAG Prompt/Context Safety",
    "agent": "Agent Tool Authorization",
    "tool": "Agent Tool Authorization",
    "mcp": "MCP Hardening",
    "secret": "Secrets Hygiene",
    "vault": "Secrets Hygiene",
    "telemetry": "Telemetry & Auditability",
    "audit": "Telemetry & Auditability",
    "incident": "Incident Readiness",
    "response": "Incident Readiness",
}

_GATE_ORDER = [
    "Identity & Access",
    "Retrieval Security",
    "Connector Boundary",
    "RAG Prompt/Context Safety",
    "Agent Tool Authorization",
    "MCP Hardening",
    "Secrets Hygiene",
    "Telemetry & Auditability",
    "Incident Readiness",
]


def map_to_launch_gates(readiness: OnyxReadinessResponse) -> OnyxLaunchGateSummary:
    grouped: dict[str, list[OnyxReadinessCheck]] = defaultdict(list)
    for check in readiness.checks:
        grouped[_gate_name(check)].append(check)

    categories: list[LaunchGateCategory] = []
    remediations: list[str] = []
    evidence_summary: list[TrustEvidenceItem] = []
    for gate in _GATE_ORDER:
        checks = grouped.get(gate, [])
        categories.append(_category_summary(gate, checks))
        for check in checks:
            if check.recommendation:
                remediations.append(f"{check.title}: {check.recommendation}")
            evidence_summary.append(check.evidence)

    return OnyxLaunchGateSummary(
        decision=derive_launch_gate_decision(readiness),
        categories=categories,
        evidence_summary=evidence_summary[:25],
        remediation_list=sorted(set(remediations)),
    )


def derive_launch_gate_decision(readiness: OnyxReadinessResponse) -> str:
    checks = readiness.checks
    if not readiness.reachable or readiness.overall_status == "unknown":
        return "UNKNOWN"
    if not checks:
        return "UNKNOWN"

    unknown_count = sum(1 for check in checks if check.status == "unknown")
    if unknown_count / max(1, len(checks)) >= 0.4:
        return "UNKNOWN"

    critical_fail = any(check.severity == "critical" and check.status == "fail" for check in checks)
    high_fail = any(check.severity == "high" and check.status == "fail" for check in checks)
    high_warn = any(check.severity == "high" and check.status == "warn" for check in checks)

    if critical_fail or readiness.overall_status == "fail" or readiness.overall_score < 60:
        return "BLOCKED"

    if readiness.overall_status == "warn" or (60 <= readiness.overall_score < 85) or high_warn:
        return "CONDITIONAL"

    if readiness.overall_status == "pass" and readiness.overall_score >= 85 and not (critical_fail or high_fail):
        return "APPROVED"

    return "UNKNOWN"


def _gate_name(check: OnyxReadinessCheck) -> str:
    tokens = f"{check.category}.{check.id}".lower().replace("_", ".").split(".")
    for token in tokens:
        if token in _CATEGORY_MAP:
            return _CATEGORY_MAP[token]
    return "Telemetry & Auditability"


def _category_summary(name: str, checks: list[OnyxReadinessCheck]) -> LaunchGateCategory:
    if not checks:
        return LaunchGateCategory(name=name, status="unknown", score=0, failed_checks=[], warning_checks=[], unknown_checks=[], remediations=[])

    failed = [check.title for check in checks if check.status == "fail"]
    warns = [check.title for check in checks if check.status == "warn"]
    unknown = [check.title for check in checks if check.status == "unknown"]
    score = round(sum(check.score for check in checks) / max(1, len(checks)))

    status = "pass"
    if failed:
        status = "fail"
    elif warns:
        status = "warn"
    elif unknown:
        status = "unknown"

    remediations = [check.recommendation for check in checks if check.recommendation and check.status in {"fail", "warn", "unknown"}]
    return LaunchGateCategory(
        name=name,
        status=status,
        score=score,
        failed_checks=failed,
        warning_checks=warns,
        unknown_checks=unknown,
        remediations=remediations,
    )
