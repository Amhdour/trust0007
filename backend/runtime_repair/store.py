from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import AUDIT_RECORDS_PATH, repo_root

REPAIR_ROOT = "overlays/myStarterKit/artifacts/runtime-repair"
REPAIR_RUNS_PATH = f"{REPAIR_ROOT}/repair-runs.json"
REPAIR_PLANS_PATH = f"{REPAIR_ROOT}/repair-plans.json"
REPAIR_REPORTS_PATH = f"{REPAIR_ROOT}/diagnostic-reports.json"
REPAIR_EVENTS_PATH = f"{REPAIR_ROOT}/repair-events.jsonl"


def repair_path(root: Path | None, relative_path: str) -> Path:
    return repo_root(root) / relative_path


def read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def write_json_array(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(f"{path.suffix}.tmp")
    temp_path.write_text(json.dumps(records, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temp_path, path)


def append_json_array(path: Path, record: dict[str, Any], *, limit: int = 100) -> list[dict[str, Any]]:
    records = read_json_array(path)
    records.insert(0, record)
    trimmed = records[:limit]
    write_json_array(path, trimmed)
    return trimmed


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        if path.exists() and path.stat().st_size > 0:
            handle.write("\n")
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")


class RepairArtifactStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = repo_root(root)

    @property
    def reports_path(self) -> Path:
        return repair_path(self.root, REPAIR_REPORTS_PATH)

    @property
    def plans_path(self) -> Path:
        return repair_path(self.root, REPAIR_PLANS_PATH)

    @property
    def runs_path(self) -> Path:
        return repair_path(self.root, REPAIR_RUNS_PATH)

    @property
    def events_path(self) -> Path:
        return repair_path(self.root, REPAIR_EVENTS_PATH)

    @property
    def audit_path(self) -> Path:
        return repair_path(self.root, AUDIT_RECORDS_PATH)

    def save_report(self, report: dict[str, Any]) -> str:
        append_json_array(self.reports_path, report)
        return str(self.reports_path.relative_to(self.root))

    def save_plan(self, plan: dict[str, Any]) -> str:
        append_json_array(self.plans_path, plan)
        return str(self.plans_path.relative_to(self.root))

    def save_run(self, run: dict[str, Any]) -> str:
        append_json_array(self.runs_path, run)
        return str(self.runs_path.relative_to(self.root))

    def append_event(self, event: dict[str, Any]) -> str:
        append_jsonl(self.events_path, event)
        return str(self.events_path.relative_to(self.root))

    def append_audit(self, record: dict[str, Any]) -> str:
        append_jsonl(self.audit_path, record)
        return str(self.audit_path.relative_to(self.root))

    def reports(self) -> list[dict[str, Any]]:
        return read_json_array(self.reports_path)

    def plans(self) -> list[dict[str, Any]]:
        return read_json_array(self.plans_path)

    def runs(self) -> list[dict[str, Any]]:
        return read_json_array(self.runs_path)

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        for plan in self.plans():
            if str(plan.get("plan_id", "")) == plan_id:
                return plan
        return {}

    def get_run(self, run_id: str) -> dict[str, Any]:
        for run in self.runs():
            if str(run.get("run_id", "")) == run_id:
                return run
        return {}
