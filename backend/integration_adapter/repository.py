from __future__ import annotations

from dataclasses import dataclass
import json
import re
from pathlib import Path
from typing import Any

LAUNCH_REPORT_PRIMARY = "overlays/myStarterKit/artifacts/logs/launch_gate/starter_launch_readiness_report.json"
LAUNCH_REPORT_FALLBACK = "launch-gate/starter_launch_readiness_report.json"
POLICY_BUNDLE_PRIMARY = "overlays/myStarterKit/policies/bundles/default/policy.json"
POLICY_BUNDLE_FALLBACK = "policies/runtime-policy-fallback.json"
REVIEWER_BUNDLE_PRIMARY = "overlays/myStarterKit/artifacts/evidence/reviewer/reviewer_evidence_bundle.json"
REVIEWER_BUNDLE_FALLBACK = "evidence/reviewer_evidence_bundle.json"
DASHBOARD_INGESTION_PRIMARY = "overlays/myStarterKit/artifacts/dashboard/dashboard_ingestion.json"
DASHBOARD_INGESTION_FALLBACK = "telemetry/exports/mystarterkit_dashboard_feed.json"
DASHBOARD_CONTRACT_PATH = "contracts/control-plane-dashboard.json"
UPSTREAM_USAGE_INVENTORY_PATH = "evidence/upstream_usage.inventory.json"


@dataclass(frozen=True)
class RuntimePolicyBundle:
    document: dict[str, Any]
    relative_path: str
    source: str


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


def _preferred_relative_path(root: Path | None, primary: str, fallback: str) -> str:
    resolved_root = repo_root(root)
    if (resolved_root / primary).exists():
        return primary
    return fallback


def policy_bundle_relative_path(root: Path | None = None) -> str:
    return _preferred_relative_path(root, POLICY_BUNDLE_PRIMARY, POLICY_BUNDLE_FALLBACK)


def load_runtime_policy_bundle(root: Path | None = None) -> RuntimePolicyBundle:
    relative_path = policy_bundle_relative_path(root)
    source = "overlay" if relative_path == POLICY_BUNDLE_PRIMARY else "fallback"
    return RuntimePolicyBundle(
        document=read_json(repo_root(root) / relative_path),
        relative_path=relative_path,
        source=source,
    )


def load_policy_bundle(root: Path | None = None) -> dict[str, Any]:
    return load_runtime_policy_bundle(root).document


def load_dashboard_contract(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / DASHBOARD_CONTRACT_PATH)


def load_upstream_usage_inventory(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / UPSTREAM_USAGE_INVENTORY_PATH)


def launch_report_relative_path(root: Path | None = None) -> str:
    return _preferred_relative_path(root, LAUNCH_REPORT_PRIMARY, LAUNCH_REPORT_FALLBACK)


def load_launch_report(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / launch_report_relative_path(root))


def reviewer_bundle_relative_path(root: Path | None = None) -> str:
    return _preferred_relative_path(root, REVIEWER_BUNDLE_PRIMARY, REVIEWER_BUNDLE_FALLBACK)


def load_reviewer_bundle(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / reviewer_bundle_relative_path(root))


def dashboard_ingestion_relative_path(root: Path | None = None) -> str:
    return _preferred_relative_path(root, DASHBOARD_INGESTION_PRIMARY, DASHBOARD_INGESTION_FALLBACK)


def path_has_files(root: Path | None, relative_path: str) -> bool:
    target = repo_root(root) / relative_path
    if not target.exists():
        return False
    if target.is_file():
        return True
    return any(target.iterdir())


def load_eval_summaries(root: Path | None = None) -> list[dict[str, Any]]:
    resolved_root = repo_root(root)
    summaries: list[dict[str, Any]] = []
    for path in sorted((resolved_root / "overlays/myStarterKit/artifacts/logs/evals").glob("*.summary.json")):
        payload = read_json(path)
        payload["artifact_path"] = str(path.relative_to(resolved_root))
        summaries.append(payload)
    return summaries


def load_latest_governed_flow_events(root: Path | None = None) -> list[dict[str, Any]]:
    """Load the most recent governed flow events from overlay artifacts.
    
    Returns empty list if no governed flow artifacts are available.
    Governed flow artifacts are stored in overlays/myStarterKit/artifacts/events.jsonl
    after a /api/control-plane/governed-flow request.
    """
    resolved_root = repo_root(root)
    events_path = resolved_root / "overlays/myStarterKit/artifacts/events.jsonl"
    return read_jsonl(events_path)


def load_latest_governed_flow_launch_gate(root: Path | None = None) -> dict[str, Any]:
    """Load the most recent governed flow launch-gate result from overlay artifacts.
    
    Returns empty dict if no governed flow artifacts are available.
    """
    resolved_root = repo_root(root)
    gate_path = resolved_root / "overlays/myStarterKit/artifacts/launch-gate-result.json"
    return read_json(gate_path)


def has_live_governed_flow_artifacts(root: Path | None = None) -> bool:
    """Check if live governed flow artifacts are available in the overlay directory."""
    resolved_root = repo_root(root)
    artifacts_dir = resolved_root / "overlays/myStarterKit/artifacts"
    return (
        artifacts_dir.exists()
        and (artifacts_dir / "events.jsonl").exists()
        and (artifacts_dir / "launch-gate-result.json").exists()
    )
