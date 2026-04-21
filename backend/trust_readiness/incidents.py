from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import repo_root
from .evidence import INCIDENT_CONTROLS_PATH
from .schemas import IncidentControl


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _controls_path(root: Path | None = None) -> Path:
    return repo_root(root) / INCIDENT_CONTROLS_PATH


def load_incident_controls(root: Path | None = None) -> list[dict[str, Any]]:
    path = _controls_path(root)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def append_incident_control(
    *,
    runtime_id: str,
    control_type: str,
    tenant_id: str,
    actor_id: str,
    reason: str,
    tool_id: str = "",
    expires_at: str = "",
    root: Path | None = None,
) -> IncidentControl:
    path = _controls_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    controls = load_incident_controls(root)
    control = IncidentControl(
        control_id=f"incident-control-{uuid.uuid4().hex[:12]}",
        runtime_id=runtime_id,
        control_type=control_type,  # type: ignore[arg-type]
        active=True,
        tenant_id=tenant_id,
        actor_id=actor_id,
        reason=reason,
        tool_id=tool_id,
        expires_at=expires_at,
        created_at=_now(),
        audit_ref=str(path),
    )
    controls.append(control.to_dict())
    path.write_text(json.dumps(controls, indent=2, sort_keys=True), encoding="utf-8")
    return control


def active_incident_controls(root: Path | None = None, *, runtime_id: str = "") -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    active: list[dict[str, Any]] = []
    for control in load_incident_controls(root):
        if runtime_id and str(control.get("runtime_id", "")) not in {"", runtime_id}:
            continue
        if not bool(control.get("active", False)):
            continue
        expires_at = str(control.get("expires_at", ""))
        if expires_at:
            try:
                expires = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            except ValueError:
                expires = now
            if expires.tzinfo is None:
                expires = expires.replace(tzinfo=timezone.utc)
            if expires < now:
                continue
        active.append(control)
    return active
