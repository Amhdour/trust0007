from dataclasses import dataclass, field
from typing import Any, Dict, Literal


RecordType = Literal["trace", "span"]


@dataclass(frozen=True)
class LangfuseRecord:
    record_type: RecordType
    trace_id: str
    observation_id: str
    name: str
    metadata: Dict[str, Any] = field(default_factory=dict)
