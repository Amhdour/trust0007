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
UPSTREAM_SOURCE_LOCK_PATH = "evidence/upstream.lock.json"
GOVERNED_FLOW_SUMMARY_PATH = "overlays/myStarterKit/artifacts/governed-flow-summary.json"
GOVERNED_REQUEST_FEED_PATH = "overlays/myStarterKit/artifacts/governed-request-feed.json"
IDENTITY_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/identity-evidence.json"
POLICY_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/policy-evidence.json"
RETRIEVAL_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/retrieval-evidence.json"
SECRET_EVIDENCE_PATH = "overlays/myStarterKit/artifacts/secret-evidence.json"
TRACE_CORRELATION_PATH = "overlays/myStarterKit/artifacts/trace-correlation.json"
ONYX_RUNTIME_PROOF_PATH = "overlays/myStarterKit/artifacts/onyx-runtime-proof.json"
DIFY_RUNTIME_PROOF_PATH = "overlays/myStarterKit/artifacts/dify-runtime-proof.json"
RUNTIME_PROOF_PATH = "overlays/myStarterKit/artifacts/runtime-proof.json"
AUDIT_RECORDS_PATH = "overlays/myStarterKit/artifacts/audit-records.jsonl"
UPSTREAM_INVENTORY_CLASSIFICATIONS = {
    "used_now",
    "partially_used",
    "optional_future",
    "reference_only",
}
UPSTREAM_RUNTIME_PATH_STATUSES = {"mandatory", "supporting", "optional", "reference"}
UPSTREAM_SOURCE_TRACKING_MODES = {"vendored_snapshot"}
UPSTREAM_SOURCE_CHECKOUT_POLICIES = {"default", "opt_in"}
UPSTREAM_INTEGRATION_DECISIONS = {"active_now", "platform_only", "opt_in_only", "reference_only"}
UPSTREAM_PROVENANCE_MODES = {"content_fingerprint", "manual_pin", "standalone_git_pin", "manual_pin+content_fingerprint", "standalone_git_pin+content_fingerprint"}


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


def read_json_array(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


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


def load_upstream_source_lock(root: Path | None = None) -> dict[str, Any]:
    lock_manifest = read_json(repo_root(root) / UPSTREAM_SOURCE_LOCK_PATH)
    components = list(lock_manifest.get("components", []))
    component_paths = list_upstream_component_paths(root)

    path_to_components: dict[str, list[dict[str, Any]]] = {}
    invalid_components: list[str] = []
    for component in components:
        component_name = str(component.get("component_name", "")).strip()
        component_path = str(component.get("upstream_path", "")).strip()
        classification = str(component.get("classification", "")).strip()
        runtime_path_status = str(component.get("runtime_path_status", "")).strip()
        tracked_as = str(component.get("tracked_as", "")).strip()
        checkout_policy = str(component.get("checkout_policy", "")).strip()
        integration_decision = str(component.get("integration_decision", "")).strip()
        provenance_mode = str(component.get("provenance_mode", "")).strip()
        if component_path:
            path_to_components.setdefault(component_path, []).append(component)
        required_fields = (
            component_name,
            component_path,
            str(component.get("source_repo", "")).strip(),
            str(component.get("source_owner", "")).strip(),
            classification,
            runtime_path_status,
            str(component.get("integration_owner", "")).strip(),
            tracked_as,
            checkout_policy,
            integration_decision,
            provenance_mode,
            str(component.get("refresh_policy", "")).strip(),
            str(component.get("last_validated", "")).strip(),
        )
        if (
            not all(required_fields)
            or classification not in UPSTREAM_INVENTORY_CLASSIFICATIONS
            or runtime_path_status not in UPSTREAM_RUNTIME_PATH_STATUSES
            or tracked_as not in UPSTREAM_SOURCE_TRACKING_MODES
            or checkout_policy not in UPSTREAM_SOURCE_CHECKOUT_POLICIES
            or integration_decision not in UPSTREAM_INTEGRATION_DECISIONS
            or provenance_mode not in UPSTREAM_PROVENANCE_MODES
            or "source_ref" not in component
            or "source_commit" not in component
            or "refresh_notes" not in component
            or "snapshot_fingerprint" not in component
            or "snapshot_file_count" not in component
            or "snapshot_bytes" not in component
        ):
            invalid_components.append(component_name or component_path or "unknown-component")

    missing_paths = [path for path in component_paths if path not in path_to_components]
    extra_paths = [path for path in path_to_components if path not in component_paths]
    duplicate_paths = sorted(path for path, mapped in path_to_components.items() if len(mapped) > 1)
    default_checkout_paths = sorted(
        str(component.get("upstream_path", "")).strip()
        for component in components
        if str(component.get("checkout_policy", "")).strip() == "default"
    )
    opt_in_checkout_paths = sorted(
        str(component.get("upstream_path", "")).strip()
        for component in components
        if str(component.get("checkout_policy", "")).strip() == "opt_in"
    )
    platform_only_components = sorted(
        str(component.get("component_name", "")).strip()
        for component in components
        if str(component.get("integration_decision", "")).strip() == "platform_only"
    )
    pinned_source_paths = sorted(
        str(component.get("upstream_path", "")).strip()
        for component in components
        if str(component.get("source_ref", "")).strip() and str(component.get("source_commit", "")).strip()
    )
    unpinned_source_components = sorted(
        str(component.get("component_name", "")).strip()
        for component in components
        if not str(component.get("source_ref", "")).strip() or not str(component.get("source_commit", "")).strip()
    )
    fingerprinted_paths = sorted(
        str(component.get("upstream_path", "")).strip()
        for component in components
        if str(component.get("snapshot_fingerprint", "")).strip()
    )
    unfingerprinted_components = sorted(
        str(component.get("component_name", "")).strip()
        for component in components
        if not str(component.get("snapshot_fingerprint", "")).strip()
    )
    checkout_policy_mismatches = []
    integration_decision_mismatches = []
    for component in components:
        component_name = str(component.get("component_name", "")).strip() or "unknown-component"
        classification = str(component.get("classification", "")).strip()
        checkout_policy = str(component.get("checkout_policy", "")).strip()
        integration_decision = str(component.get("integration_decision", "")).strip()

        expected_checkout_policy = "default" if classification in {"used_now", "partially_used"} else "opt_in"
        if checkout_policy != expected_checkout_policy:
            checkout_policy_mismatches.append(
                {
                    "component_name": component_name,
                    "classification": classification,
                    "checkout_policy": checkout_policy,
                    "expected_checkout_policy": expected_checkout_policy,
                }
            )

        expected_integration_decision = {
            "used_now": "active_now",
            "partially_used": "platform_only",
            "optional_future": "opt_in_only",
            "reference_only": "reference_only",
        }.get(classification, "")
        if integration_decision != expected_integration_decision:
            integration_decision_mismatches.append(
                {
                    "component_name": component_name,
                    "classification": classification,
                    "integration_decision": integration_decision,
                    "expected_integration_decision": expected_integration_decision,
                }
            )

    envoy_component = next(
        (component for component in components if str(component.get("upstream_path", "")).strip() == "upstream/envoy"),
        {},
    )
    envoy_platform_only_locked = (
        str(envoy_component.get("classification", "")).strip() == "partially_used"
        and str(envoy_component.get("runtime_path_status", "")).strip() == "supporting"
        and str(envoy_component.get("integration_decision", "")).strip() == "platform_only"
        and str(envoy_component.get("checkout_policy", "")).strip() == "default"
    )
    managed_submodules = [
        str(path).strip()
        for path in lock_manifest.get("managed_submodules", [])
        if str(path).strip()
    ]

    enriched_lock = dict(lock_manifest)
    enriched_lock["component_count"] = len(components)
    enriched_lock["upstream_paths"] = component_paths
    enriched_lock["checkout_groups"] = {
        "default_paths": default_checkout_paths,
        "opt_in_paths": opt_in_checkout_paths,
    }
    enriched_lock["pin_coverage"] = {
        "pinned_paths": pinned_source_paths,
        "unpinned_components": unpinned_source_components,
        "pinned_count": len(pinned_source_paths),
        "total_count": len(components),
    }
    enriched_lock["provenance_coverage"] = {
        "fingerprinted_paths": fingerprinted_paths,
        "unfingerprinted_components": unfingerprinted_components,
        "fingerprinted_count": len(fingerprinted_paths),
        "total_count": len(components),
    }
    enriched_lock["audit"] = {
        "lock_path": UPSTREAM_SOURCE_LOCK_PATH,
        "component_paths_in_repo": component_paths,
        "declared_paths": sorted(path_to_components),
        "missing_paths": missing_paths,
        "extra_paths": extra_paths,
        "duplicate_paths": duplicate_paths,
        "invalid_components": sorted(invalid_components),
        "lock_covers_all_upstreams": not missing_paths and not extra_paths and not duplicate_paths,
        "managed_submodules": managed_submodules,
        "default_checkout_paths": default_checkout_paths,
        "opt_in_checkout_paths": opt_in_checkout_paths,
        "platform_only_components": platform_only_components,
        "pinned_source_paths": pinned_source_paths,
        "unpinned_source_components": unpinned_source_components,
        "pinned_source_count": len(pinned_source_paths),
        "source_pins_complete": len(pinned_source_paths) == len(components),
        "fingerprinted_paths": fingerprinted_paths,
        "unfingerprinted_components": unfingerprinted_components,
        "fingerprinted_source_count": len(fingerprinted_paths),
        "fingerprints_complete": len(fingerprinted_paths) == len(components),
        "checkout_policy_mismatches": checkout_policy_mismatches,
        "checkout_policies_consistent": not checkout_policy_mismatches,
        "integration_decision_mismatches": integration_decision_mismatches,
        "integration_decisions_consistent": not integration_decision_mismatches,
        "envoy_platform_only_locked": envoy_platform_only_locked,
    }
    return enriched_lock


def load_upstream_usage_inventory(root: Path | None = None) -> dict[str, Any]:
    inventory = read_json(repo_root(root) / UPSTREAM_USAGE_INVENTORY_PATH)
    lock_manifest = load_upstream_source_lock(root)
    lock_components = list(lock_manifest.get("components", []))
    lock_by_path = {
        str(component.get("upstream_path", "")).strip(): component
        for component in lock_components
        if str(component.get("upstream_path", "")).strip()
    }
    components = []
    for component in list(inventory.get("components", [])):
        component_path = str(component.get("upstream_path", "")).strip()
        lock_component = dict(lock_by_path.get(component_path, {}))
        merged_component = dict(component)
        for field in (
            "source_repo",
            "source_owner",
            "integration_owner",
            "tracked_as",
            "checkout_policy",
            "integration_decision",
            "provenance_mode",
            "source_ref",
            "source_commit",
            "snapshot_fingerprint",
            "snapshot_file_count",
            "snapshot_bytes",
            "refresh_policy",
            "refresh_notes",
            "last_validated",
        ):
            if field in lock_component:
                merged_component[field] = lock_component[field]
        components.append(merged_component)
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
    lock_path_mismatches = sorted(set(component_paths) ^ set(lock_by_path))
    lock_classification_mismatches = []
    lock_runtime_path_status_mismatches = []
    for component in components:
        component_path = str(component.get("upstream_path", "")).strip()
        if component_path not in lock_by_path:
            continue
        lock_component = lock_by_path[component_path]
        if component.get("classification") != lock_component.get("classification"):
            lock_classification_mismatches.append(
                {
                    "upstream_path": component_path,
                    "inventory_classification": str(component.get("classification", "")),
                    "lock_classification": str(lock_component.get("classification", "")),
                }
            )
        if component.get("runtime_path_status") != lock_component.get("runtime_path_status"):
            lock_runtime_path_status_mismatches.append(
                {
                    "upstream_path": component_path,
                    "inventory_runtime_path_status": str(component.get("runtime_path_status", "")),
                    "lock_runtime_path_status": str(lock_component.get("runtime_path_status", "")),
                }
            )
    missing_paths = [path for path in component_paths if path not in path_to_components]
    extra_paths = [path for path in path_to_components if path not in component_paths]
    duplicate_paths = sorted(path for path, mapped in path_to_components.items() if len(mapped) > 1)

    enriched_inventory = dict(inventory)
    enriched_inventory["components"] = components
    enriched_inventory["component_count"] = len(components)
    enriched_inventory["upstream_paths"] = component_paths
    enriched_inventory["classification_counts"] = classification_counts
    enriched_inventory["tracking_model"] = {
        "mode": str(lock_manifest.get("tracking_model", "")).strip(),
        "lock_path": UPSTREAM_SOURCE_LOCK_PATH,
        "managed_submodules": list(lock_manifest.get("managed_submodules", [])),
        "default_checkout_paths": list(lock_manifest.get("checkout_groups", {}).get("default_paths", [])),
        "opt_in_checkout_paths": list(lock_manifest.get("checkout_groups", {}).get("opt_in_paths", [])),
        "platform_only_components": list(lock_manifest.get("audit", {}).get("platform_only_components", [])),
        "pinned_source_count": int(lock_manifest.get("pin_coverage", {}).get("pinned_count", 0)),
        "total_source_count": int(lock_manifest.get("pin_coverage", {}).get("total_count", 0)),
        "unpinned_source_components": list(lock_manifest.get("pin_coverage", {}).get("unpinned_components", [])),
        "fingerprinted_source_count": int(lock_manifest.get("provenance_coverage", {}).get("fingerprinted_count", 0)),
        "unfingerprinted_source_components": list(lock_manifest.get("provenance_coverage", {}).get("unfingerprinted_components", [])),
    }
    enriched_inventory["audit"] = {
        "inventory_path": UPSTREAM_USAGE_INVENTORY_PATH,
        "lock_path": UPSTREAM_SOURCE_LOCK_PATH,
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
        "lock_path_mismatches": lock_path_mismatches,
        "lock_classification_mismatches": lock_classification_mismatches,
        "lock_runtime_path_status_mismatches": lock_runtime_path_status_mismatches,
        "lock_consistent": (
            not lock_path_mismatches
            and not lock_classification_mismatches
            and not lock_runtime_path_status_mismatches
            and bool(lock_manifest.get("audit", {}).get("lock_covers_all_upstreams"))
        ),
        "managed_submodules": list(lock_manifest.get("managed_submodules", [])),
        "default_checkout_paths": list(lock_manifest.get("audit", {}).get("default_checkout_paths", [])),
        "opt_in_checkout_paths": list(lock_manifest.get("audit", {}).get("opt_in_checkout_paths", [])),
        "pinned_source_count": int(lock_manifest.get("audit", {}).get("pinned_source_count", 0)),
        "source_pins_complete": bool(lock_manifest.get("audit", {}).get("source_pins_complete")),
        "unpinned_source_components": list(lock_manifest.get("audit", {}).get("unpinned_source_components", [])),
        "fingerprinted_source_count": int(lock_manifest.get("audit", {}).get("fingerprinted_source_count", 0)),
        "fingerprints_complete": bool(lock_manifest.get("audit", {}).get("fingerprints_complete")),
        "unfingerprinted_source_components": list(lock_manifest.get("audit", {}).get("unfingerprinted_components", [])),
        "checkout_policies_consistent": bool(lock_manifest.get("audit", {}).get("checkout_policies_consistent")),
        "integration_decisions_consistent": bool(lock_manifest.get("audit", {}).get("integration_decisions_consistent")),
        "envoy_platform_only_locked": bool(lock_manifest.get("audit", {}).get("envoy_platform_only_locked")),
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


def governed_request_feed_relative_path(root: Path | None = None) -> str:
    resolved_root = repo_root(root)
    if (resolved_root / GOVERNED_REQUEST_FEED_PATH).exists():
        return GOVERNED_REQUEST_FEED_PATH
    return GOVERNED_REQUEST_FEED_PATH


def load_latest_governed_request_feed(root: Path | None = None) -> list[dict[str, Any]]:
    resolved_root = repo_root(root)
    return read_json_array(resolved_root / GOVERNED_REQUEST_FEED_PATH)


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


def load_latest_onyx_runtime_proof(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / ONYX_RUNTIME_PROOF_PATH)


def load_latest_dify_runtime_proof(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / DIFY_RUNTIME_PROOF_PATH)


def load_latest_runtime_proof(root: Path | None = None) -> dict[str, Any]:
    return read_json(repo_root(root) / RUNTIME_PROOF_PATH)


def load_latest_audit_records(root: Path | None = None) -> list[dict[str, Any]]:
    return read_jsonl(repo_root(root) / AUDIT_RECORDS_PATH)


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
