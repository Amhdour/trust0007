from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict


@dataclass(frozen=True)
class TelemetryEvent:
    event_type: str
    trace_id: str
    request_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tenant_id: str = ""
    severity: str = "info"
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
