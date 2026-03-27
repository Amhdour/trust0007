from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class NormalizedRequest:
    request_id: str
    tenant_id: str
    user_id: str
    prompt: str
    requested_tools: List[str] = field(default_factory=list)
    retrieval_needed: bool = False
    retrieval_source: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PolicyDecision:
    allow: bool
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class RetrievalDecision:
    allow: bool
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class ToolDecision:
    allowed_tools: List[str] = field(default_factory=list)
    denied_tools: List[str] = field(default_factory=list)
    reasons: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class TelemetryEvent:
    event_type: str
    request_id: str
    tenant_id: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedDecision:
    allow: bool
    reasons: List[str]
    policy_allow: bool
    retrieval_allow: bool
    allowed_tools: List[str]
    denied_tools: List[str]
