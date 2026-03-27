"""Build a Grafana-friendly dashboard feed from myStarterKit JSONL artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOG_ROOT = ROOT / "overlays" / "myStarterKit" / "artifacts" / "logs"
JSON_OUTPUT = ROOT / "overlays" / "myStarterKit" / "artifacts" / "dashboard" / "dashboard_ingestion.json"
CSV_OUTPUT = ROOT / "telemetry" / "exports" / "mystarterkit_dashboard_feed.csv"
JSON_EXPORT = ROOT / "telemetry" / "exports" / "mystarterkit_dashboard_feed.json"

CSV_FIELDS = [
    "event_time",
    "event_type",
    "decision",
    "stage",
    "severity",
    "tenant_id",
    "request_id",
    "actor_id",
    "tool_name",
    "source",
    "reason",
    "source_file",
]


def infer_decision(action: str, event_type: str) -> str:
    action = action.lower()
    event_type = event_type.lower()
    if any(token in action for token in ("block", "deny")) or "deny" in event_type:
        return "deny"
    if "warn" in action:
        return "warn"
    if any(token in action for token in ("allow", "ok")):
        return "allow"
    if any(token in action for token in ("invoke", "start", "end")):
        return "observe"
    return "observe"


def infer_stage(record: dict[str, Any]) -> str:
    payload = record.get("event_payload")
    if isinstance(payload, dict):
        stage = payload.get("stage")
        if isinstance(stage, str) and stage:
            return stage

    event_type = str(record.get("event_type", "")).lower()
    if "retrieval" in event_type:
        return "retrieval"
    if "tool" in event_type:
        return "tool"
    if "output" in event_type:
        return "output"
    if "model" in event_type:
        return "model"
    if "prompt" in event_type or "input" in event_type:
        return "input"
    if "request" in event_type:
        return "entry"
    return "logging"


def extract_source(payload: dict[str, Any]) -> str:
    sources = payload.get("sources")
    if isinstance(sources, list) and sources:
        return str(sources[0])
    source = payload.get("source")
    if source is not None:
        return str(source)
    return ""


def convert_record(path: Path, record: dict[str, Any]) -> dict[str, str]:
    payload = record.get("event_payload")
    payload = payload if isinstance(payload, dict) else {}
    action = str(payload.get("action", ""))
    event_type = str(record.get("event_type", "runtime_event"))
    return {
        "event_time": str(record.get("created_at") or record.get("timestamp") or ""),
        "event_type": event_type,
        "decision": infer_decision(action, event_type),
        "stage": infer_stage(record),
        "severity": str(payload.get("severity") or record.get("severity") or ""),
        "tenant_id": str(record.get("tenant_id") or ""),
        "request_id": str(record.get("request_id") or ""),
        "actor_id": str(record.get("actor_id") or ""),
        "tool_name": str(payload.get("tool_name") or payload.get("tool_used") or ""),
        "source": extract_source(payload),
        "reason": str(payload.get("reason") or payload.get("message") or ""),
        "source_file": str(path.relative_to(LOG_ROOT)),
    }


def load_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted(LOG_ROOT.rglob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            if isinstance(record, dict):
                rows.append(convert_record(path, record))
    rows.sort(key=lambda row: (row["event_time"], row["request_id"], row["event_type"]))
    return rows


def write_json(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = load_rows()
    write_json(JSON_OUTPUT, rows)
    write_json(JSON_EXPORT, rows)
    write_csv(CSV_OUTPUT, rows)
    print(f"Wrote {len(rows)} rows to {JSON_OUTPUT}, {JSON_EXPORT}, and {CSV_OUTPUT}")


if __name__ == "__main__":
    main()
