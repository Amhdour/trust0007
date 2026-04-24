from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal


DecisionMode = Literal["allow", "degrade", "deny"]


@dataclass(frozen=True)
class RetrievalRequest:
    request_id: str
    tenant_id: str
    source: str
    query: str
    trust_labels: List[str] = field(default_factory=list)
    require_citations: bool = True


@dataclass(frozen=True)
class RetrievalDocument:
    doc_id: str
    tenant_id: str
    source: str
    content: str
    trust_label: str
    quarantined: bool
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalDecision:
    allow: bool
    mode: DecisionMode
    reasons: List[str] = field(default_factory=list)
    citations: List[Dict[str, Any]] = field(default_factory=list)
    filtered_documents: List[RetrievalDocument] = field(default_factory=list)
