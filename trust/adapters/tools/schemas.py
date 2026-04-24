from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal


DecisionStatus = Literal["allow", "deny", "confirm_required"]
RiskLevel = Literal["low", "medium", "high"]


@dataclass(frozen=True)
class ToolActionRequest:
    request_id: str
    tenant_id: str
    user_id: str
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    confirmed: bool = False


@dataclass(frozen=True)
class ToolDecision:
    status: DecisionStatus
    reason_codes: List[str] = field(default_factory=list)
    risk_level: RiskLevel = "low"
    rate_limit_key: str = ""
    rate_limit_hint: str = ""


@dataclass(frozen=True)
class ToolExecutionResult:
    executed: bool
    status: DecisionStatus
    output: Dict[str, Any] = field(default_factory=dict)
    reason_codes: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuditEvent:
    event_type: Literal["allow", "deny", "confirm", "execute"]
    request_id: str
    tenant_id: str
    tool_name: str
    payload: Dict[str, Any] = field(default_factory=dict)
