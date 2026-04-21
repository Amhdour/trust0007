from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import (
    AUDIT_RECORDS_PATH,
    GOVERNED_FLOW_SUMMARY_PATH,
    IDENTITY_EVIDENCE_PATH,
    POLICY_EVIDENCE_PATH,
    RETRIEVAL_EVIDENCE_PATH,
    SECRET_EVIDENCE_PATH,
    TRACE_CORRELATION_PATH,
    read_json,
    read_jsonl,
    repo_root,
)

TOOL_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/tool-evidence.json"
EVENTS_PATH = "overlays/myStarterKit/artifacts/events.jsonl"
LAUNCH_GATE_RESULT_PATH = "overlays/myStarterKit/artifacts/launch-gate-result.json"
INCIDENT_CONTROLS_PATH = "overlays/myStarterKit/artifacts/incident-controls.json"
EXCEPTIONS_WAIVERS_PATH = "overlays/myStarterKit/artifacts/exceptions-waivers.json"


def parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def latest_timestamp(*documents: dict[str, Any]) -> str:
    timestamps = [
        str(document.get("timestamp") or document.get("captured_at") or document.get("generated_at") or "")
        for document in documents
        if document
    ]
    parsed = [item for item in (parse_timestamp(timestamp) for timestamp in timestamps) if item is not None]
    if not parsed:
        return ""
    return max(parsed).isoformat()


def evidence_age_status(timestamp: str, *, fresh_hours: int = 6, stale_hours: int = 24) -> str:
    parsed = parse_timestamp(timestamp)
    if parsed is None:
        return "missing"
    age_seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
    if age_seconds <= fresh_hours * 3600:
        return "fresh"
    if age_seconds <= stale_hours * 3600:
        return "aging"
    return "stale"


def _read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


@dataclass(frozen=True)
class EvidenceBundle:
    root: Path
    identity: dict[str, Any]
    policy: dict[str, Any]
    retrieval: dict[str, Any]
    secret: dict[str, Any]
    tool: dict[str, Any]
    trace: dict[str, Any]
    launch_gate: dict[str, Any]
    summary: dict[str, Any]
    audit_records: list[dict[str, Any]]
    events: list[dict[str, Any]]
    incident_controls: list[dict[str, Any]]
    exceptions_waivers: list[dict[str, Any]]

    def evidence_refs(self) -> dict[str, str]:
        return {
            "identity": IDENTITY_EVIDENCE_PATH,
            "policy": POLICY_EVIDENCE_PATH,
            "retrieval": RETRIEVAL_EVIDENCE_PATH,
            "secret": SECRET_EVIDENCE_PATH,
            "tool": TOOL_EVIDENCE_PATH,
            "trace": TRACE_CORRELATION_PATH,
            "launch_gate": LAUNCH_GATE_RESULT_PATH,
            "summary": GOVERNED_FLOW_SUMMARY_PATH,
            "audit": AUDIT_RECORDS_PATH,
            "events": EVENTS_PATH,
        }

    def timeline(self, runtime_id: str = "") -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for event in self.events:
            payload = event.get("payload", {}) if isinstance(event.get("payload"), dict) else {}
            event_runtime = str(payload.get("runtime_target") or event.get("runtime_id") or "")
            if runtime_id and event_runtime and event_runtime != runtime_id:
                continue
            records.append(
                {
                    "timestamp": str(event.get("timestamp", "")),
                    "kind": "telemetry",
                    "event_type": str(event.get("event_type", "")),
                    "correlation_id": str(event.get("trace_id", "")),
                    "tenant_id": str(event.get("tenant_id") or payload.get("tenant_id", "")),
                    "actor_id": str(payload.get("actor_id", "")),
                    "runtime_id": event_runtime or runtime_id,
                    "decision_id": str(payload.get("decision_id", "")),
                    "launch_request_id": str(payload.get("launch_request_id", event.get("request_id", ""))),
                    "reason_codes": payload.get("reason_codes", []),
                }
            )
        for audit in self.audit_records:
            event_runtime = str(audit.get("runtime_target") or audit.get("runtime_id") or "")
            if runtime_id and event_runtime and event_runtime != runtime_id:
                continue
            records.append(
                {
                    "timestamp": str(audit.get("timestamp", "")),
                    "kind": "audit",
                    "event_type": str(audit.get("action") or audit.get("event_type", "")),
                    "correlation_id": str(audit.get("trace_id") or audit.get("correlation_id", "")),
                    "tenant_id": str(audit.get("tenant_id", "")),
                    "actor_id": str(audit.get("actor_id", "")),
                    "runtime_id": event_runtime or runtime_id,
                    "tool_id": str(audit.get("tool_id") or audit.get("component", "")),
                    "decision_id": str(audit.get("decision_id", "")),
                    "launch_request_id": str(audit.get("launch_request_id", audit.get("request_id", ""))),
                    "reason_codes": audit.get("reason_codes", []),
                }
            )
        records.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
        return records

    def to_bundle(self, runtime_id: str = "") -> dict[str, Any]:
        correlation_id = str(self.summary.get("trace_id") or self.trace.get("trace_id") or f"bundle-{uuid.uuid4().hex[:8]}")
        return {
            "bundle_id": f"evidence-{uuid.uuid4().hex[:12]}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "runtime_id": runtime_id,
            "correlation_id": correlation_id,
            "tenant_id": str(self.summary.get("tenant_id") or self.identity.get("tenant_id", "")),
            "actor_id": str(self.summary.get("actor_id") or self.identity.get("actor_id", "")),
            "refs": self.evidence_refs(),
            "timeline": self.timeline(runtime_id)[:100],
            "launch_decision": self.launch_gate,
            "summary": self.summary,
        }


def load_evidence_bundle(root: Path | None = None) -> EvidenceBundle:
    resolved_root = repo_root(root)
    return EvidenceBundle(
        root=resolved_root,
        identity=read_json(resolved_root / IDENTITY_EVIDENCE_PATH),
        policy=read_json(resolved_root / POLICY_EVIDENCE_PATH),
        retrieval=read_json(resolved_root / RETRIEVAL_EVIDENCE_PATH),
        secret=read_json(resolved_root / SECRET_EVIDENCE_PATH),
        tool=read_json(resolved_root / TOOL_EVIDENCE_PATH),
        trace=read_json(resolved_root / TRACE_CORRELATION_PATH),
        launch_gate=read_json(resolved_root / LAUNCH_GATE_RESULT_PATH),
        summary=read_json(resolved_root / GOVERNED_FLOW_SUMMARY_PATH),
        audit_records=read_jsonl(resolved_root / AUDIT_RECORDS_PATH),
        events=read_jsonl(resolved_root / EVENTS_PATH),
        incident_controls=_read_json_array(resolved_root / INCIDENT_CONTROLS_PATH),
        exceptions_waivers=_read_json_array(resolved_root / EXCEPTIONS_WAIVERS_PATH),
    )
