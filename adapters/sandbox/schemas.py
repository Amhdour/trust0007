from dataclasses import dataclass, field
from typing import Dict, List, Literal


ExecutionMode = Literal["allow", "sandbox", "deny"]


@dataclass(frozen=True)
class SandboxExecutionRequest:
    request_id: str
    tenant_id: str
    action_type: str
    tool_name: str
    network_access: bool = False
    filesystem_write: bool = False
    external_integration: bool = False
    code_supplied_by_user: bool = False
    policy_context: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SandboxDecision:
    mode: ExecutionMode
    reasons: List[str] = field(default_factory=list)
    risk_score: int = 0
    policy_ref: str = ""


@dataclass(frozen=True)
class SandboxExecutionResult:
    executed: bool
    mode: ExecutionMode
    reasons: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)
