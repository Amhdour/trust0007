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
GOVERNED_FLOW_SUMMARY_PATH = "overlays/myStarterKit/artifacts/governed-flow-summary.json"
IDENTITY_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/identity-evidence.json"
POLICY_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/policy-evidence.json"
RETRIEVAL_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/retrieval-evidence.json"
SECRET_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/secret-evidence.json"
TRACE_CORRELATION_PATH = "overlays/myStarterKit/artifacts/trace-correlation.json"
UPSTREAM_INVENTORY_CLASSIFICATIONS = {
    "used_now",
    "partially_used",
    "optional_future",
    "reference_only",
}


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


def list_upstream_component_paths(root: Path | None = None) -> list[str]:
    upstream_root = repo_root(root) / "upstream"
    if not upstream_root.exists():
        return []
    return sorted(
        str(path.relative_to(repo_root(root)))
        for path in upstream_root.iterdir()
        if path.is_dir()
    )


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
    inventory = read_json(repo_root(root) / UPSTREAM_USAGE_INVENTORY_PATH)
    components = list(inventory.get("components", []))
    component_paths = list_upstream_component_paths(root)

    path_to_components: dict[str, list[dict[str, Any]]] = {}
    invalid_components: list[str] = []
    for component in components:
        component_name = str(component.get("component_name", "")).strip()
        component_path = str(component.get("upstream_path", "")).strip()
        classification = str(component.get("classification", "")).strip()
        if component_path:
            path_to_components.setdefault(component_path, []).append(component)
        required_fields = (
            component_name,
            component_path,
            classification,
            str(component.get("runtime_role", "")).strip(),
            str(component.get("runtime_location", "")).strip(),
            str(component.get("necessity_rationale", "")).strip(),
            str(component.get("removal_impact", "")).strip(),
            str(component.get("missing_integration_depth", "")).strip(),
        )
        if not all(required_fields) or classification not in UPSTREAM_INVENTORY_CLASSIFICATIONS:
            invalid_components.append(component_name or component_path or "unknown-component")

    classification_counts = {
        classification: sum(1 for component in components if component.get("classification") == classification)
        for classification in sorted(UPSTREAM_INVENTORY_CLASSIFICATIONS)
    }
    runtime_path_counts = {
        status: sum(1 for component in components if component.get("runtime_path_status") == status)
        for status in ("mandatory", "supporting", "optional", "reference")
    }
    dashboard_visible_components = [
        str(component.get("component_name", "Component"))
        for component in components
        if bool(component.get("dashboard_visible"))
    ]
    source_snapshot_required = [
        str(component.get("component_name", "Component"))
        for component in components
        if bool(component.get("source_snapshot_required"))
    ]
    missing_paths = [path for path in component_paths if path not in path_to_components]
    extra_paths = [path for path in path_to_components if path not in component_paths]
    duplicate_paths = sorted(path for path, mapped in path_to_components.items() if len(mapped) > 1)

    enriched_inventory = dict(inventory)
    enriched_inventory["component_count"] = len(components)
    enriched_inventory["upstream_paths"] = component_paths
    enriched_inventory["classification_counts"] = classification_counts
    enriched_inventory["audit"] = {
        "inventory_path": UPSTREAM_USAGE_INVENTORY_PATH,
        "component_paths_in_repo": component_paths,
        "classified_paths": sorted(path_to_components),
        "missing_paths": missing_paths,
        "extra_paths": extra_paths,
        "duplicate_paths": duplicate_paths,
        "invalid_components": sorted(invalid_components),
        "inventory_covers_all_upstreams": not missing_paths and not extra_paths and not duplicate_paths,
        "dashboard_visible_components": dashboard_visible_components,
        "dashboard_visible_count": len(dashboard_visible_components),
        "source_snapshot_required_components": source_snapshot_required,
        "source_snapshot_required_count": len(source_snapshot_required),
        "runtime_path_counts": runtime_path_counts,
    }
    return enriched_inventory


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


def load_latest_governed_flow_summary(root: Path | None = None) -> dict[str, Any]:
    resolved_root = repo_root(root)
    return read_json(resolved_root / GOVERNED_FLOW_SUMMARY_PATH)


def load_latest_identity_evidence(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / IDENTITY_EVIDENCE_PATH)


def load_latest_policy_evidence(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / POLICY_EVIDENCE_PATH)


def load_latest_retrieval_evidence(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / RETRIEVAL_EVIDENCE_PATH)


def load_latest_secret_evidence(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / SECRET_EVIDENCE_PATH)


def load_latest_trace_correlation(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / TRACE_CORRELATION_PATH)


def has_live_governed_flow_artifacts(root: Path | None = None) -> bool:
    """Check if live governed flow artifacts are available in the overlay directory."""
    resolved_root = repo_root(root)
    artifacts_dir = resolved_root / "overlays/myStarterKit/artifacts"
    return (
        artifacts_dir.exists()
        and (artifacts_dir / "events.jsonl").exists()
        and (artifacts_dir / "launch-gate-result.json").exists()
        and (artifacts_dir / "governed-flow-summary.json").exists()
    )
