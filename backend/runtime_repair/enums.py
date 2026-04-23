from __future__ import annotations

from enum import Enum


class RuntimeLane(str, Enum):
    ONYX = "onyx"


class FailureCategory(str, Enum):
    REACHABILITY = "REACHABILITY"
    IDENTITY = "IDENTITY"
    POLICY = "POLICY"
    RETRIEVAL = "RETRIEVAL"
    TOOLS_MCP = "TOOLS_MCP"
    SECRETS = "SECRETS"
    EVIDENCE_FRESHNESS = "EVIDENCE_FRESHNESS"
    LAUNCH_GATE = "LAUNCH_GATE"
    CONFIG_DRIFT = "CONFIG_DRIFT"
    CONTINUITY = "CONTINUITY"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    AGING = "aging"
    STALE = "stale"
    MISSING = "missing"


class RemediationStatus(str, Enum):
    NOT_PLANNED = "not_planned"
    PLANNED = "planned"
    POLICY_DENIED = "policy_denied"
    APPROVAL_REQUIRED = "approval_required"
    DRY_RUN = "dry_run"
    EXECUTED = "executed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RepairRunStatus(str, Enum):
    DIAGNOSED = "diagnosed"
    PLANNED = "planned"
    DRY_RUN = "dry_run"
    EXECUTED = "executed"
    PARTIAL = "partial"
    BLOCKED = "blocked"
    FAILED = "failed"


class RepairMode(str, Enum):
    DIAGNOSE = "diagnose"
    PLAN = "plan"
    EXECUTE_SAFE = "execute_safe"
    EXECUTE_ACTION = "execute_action"
    DRY_RUN = "dry_run"


class DestructiveRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RepairPolicyStatus(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"
