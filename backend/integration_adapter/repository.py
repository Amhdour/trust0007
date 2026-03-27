from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def repo_root(explicit: Path | None = None) -> Path:
    return explicit or Path(__file__).resolve().parents[2]


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def parse_compose_services(path: Path) -> list[str]:
    if not path.exists():
        return []

    services: list[str] = []
    in_services = False
    for line in _read_text(path).splitlines():
        if line.startswith("services:"):
            in_services = True
            continue
        if in_services and line and not line.startswith(" "):
            break
        match = re.match(r"^  ([A-Za-z0-9_-]+):\s*$", line)
        if in_services and match:
            services.append(match.group(1))
    return services


def load_service_inventory(root: Path | None = None) -> list[str]:
    resolved_root = repo_root(root)
    service_names: list[str] = []
    for relative_path in (
        "compose/docker-compose.yml",
        "compose/docker-compose.envoy-opa.yml",
    ):
        for service in parse_compose_services(resolved_root / relative_path):
            if service not in service_names:
                service_names.append(service)
    return service_names


def load_sample_events(root: Path | None = None) -> list[dict[str, Any]]:
    return read_jsonl(repo_root(root) / "telemetry/exports/sample_events.jsonl")


def load_policy_bundle(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / "overlays/myStarterKit/policies/bundles/default/policy.json")


def load_launch_report(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / "overlays/myStarterKit/artifacts/logs/launch_gate/starter_launch_readiness_report.json")


def load_reviewer_bundle(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / "overlays/myStarterKit/artifacts/evidence/reviewer/reviewer_evidence_bundle.json")


def load_eval_summaries(root: Path | None = None) -> list[dict[str, Any]]:
    resolved_root = repo_root(root)
    summaries: list[dict[str, Any]] = []
    for path in sorted((resolved_root / "overlays/myStarterKit/artifacts/logs/evals").glob("*.summary.json")):
        payload = read_json(path)
        payload["artifact_path"] = str(path.relative_to(resolved_root))
        summaries.append(payload)
    return summaries
