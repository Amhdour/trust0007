from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote

from backend.activity_service.service import build_activity_snapshot
from backend.evidence_service.service import build_evidence_pack_summary
from backend.integration_adapter.repository import (
    dashboard_ingestion_relative_path,
    has_live_governed_flow_artifacts,
    launch_report_relative_path,
    load_dashboard_contract,
    load_eval_summaries,
    load_latest_governed_flow_events,
    load_latest_governed_flow_summary,
    load_latest_identity_evidence,
    load_latest_policy_evidence,
    load_latest_retrieval_evidence,
    load_latest_secret_evidence,
    load_latest_trace_correlation,
    load_runtime_policy_bundle,
    load_reviewer_bundle,
    load_sample_events,
    load_service_inventory,
    load_upstream_usage_inventory,
    path_has_files,
    read_json,
    read_jsonl,
    repo_root,
    reviewer_bundle_relative_path,
)
from backend.launch_gate_service.service import build_launch_gate_summary


POLICY_BUNDLE_PATH = "overlays/myStarterKit/policies/bundles/default/policy.json"
INSPECTABLE_ALLOWED_FLOW = "evidence/reviewer/inspectable-live-runtime/allowed-flow.json"
INSPECTABLE_DENIED_FLOW = "evidence/reviewer/inspectable-live-runtime/denied-flow.json"
INSPECTABLE_IDENTITY_DENY = "evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json"
INSPECTABLE_OPA_DENY = "evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json"
INSPECTABLE_RETRIEVAL_DENY = "evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json"
INSPECTABLE_SECRET_DENY = "evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json"
INSPECTABLE_TRACE_DOWNGRADE = "evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json"
INSPECTABLE_SCENARIOS = [
    INSPECTABLE_ALLOWED_FLOW,
    INSPECTABLE_DENIED_FLOW,
    INSPECTABLE_IDENTITY_DENY,
    INSPECTABLE_OPA_DENY,
    INSPECTABLE_RETRIEVAL_DENY,
    INSPECTABLE_SECRET_DENY,
    INSPECTABLE_TRACE_DOWNGRADE,
]
PROD_SIM_EVENTS = "evidence/prod-sim/events.jsonl"
PROD_SIM_GOVERNED_FLOW = "evidence/prod-sim/governed-flow-response.json"
PROD_SIM_LAUNCH_GATE = "evidence/prod-sim/launch-gate-result.json"
SAMPLE_EVENTS = "telemetry/exports/sample_events.jsonl"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _card(label: str, value: str, status: str, detail: str, href: str = "") -> dict[str, str]:
    item = {"label": label, "value": value, "status": status, "detail": detail}
    if href:
        item["href"] = href
    return item


def _record(title: str, meta: str, detail: str, status: str = "neutral", href: str = "") -> dict[str, str]:
    item = {"title": title, "meta": meta, "detail": detail, "status": status}
    if href:
        item["href"] = href
    return item


def _link(label: str, href: str, description: str, status: str = "neutral") -> dict[str, str]:
    return {"label": label, "href": href, "description": description, "status": status}


def _raw(path: str) -> str:
    return f"/raw/{quote(path)}"


def _public_service_url(port: int, fallback_path: str = "") -> str:
    codespace_name = os.environ.get("CODESPACE_NAME", "").strip()
    forwarding_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "").strip()
    if codespace_name and forwarding_domain:
        base = f"https://{codespace_name}-{port}.{forwarding_domain}"
    else:
        base = f"http://localhost:{port}"
    return f"{base}{fallback_path}"


def _dashboard_url(path: str = "") -> str:
    return _public_service_url(3000, path)


def _launch_handoff_url(path: str) -> str:
    return _dashboard_url(f"/launch/onyx?path={quote(path, safe='/?=&')}")


def _status_from_launch(verdict: str) -> str:
    return {
        "go": "healthy",
        "conditional": "warning",
        "no-go": "critical",
    }.get(verdict, "neutral")


def _status_from_severity(value: str) -> str:
    normalized = value.strip().lower()
    return {
        "critical": "critical",
        "error": "critical",
        "warning": "warning",
        "warn": "warning",
        "healthy": "healthy",
        "info": "neutral",
        "neutral": "neutral",
        "debug": "neutral",
    }.get(normalized, "neutral")


def _parse_timestamp(value: str) -> datetime | None:
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


def _payload(event: dict[str, Any]) -> dict[str, Any]:
    payload = event.get("payload", {})
    return payload if isinstance(payload, dict) else {}


def _string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    return []


def _humanize_reason(reason: str) -> str:
    code = reason.strip()
    if not code:
        return "Governance reason unavailable"
    if ":" in code:
        head, tail = code.split(":", 1)
        head = head.replace(".", " ").replace("_", " ").strip().title()
        tail = tail.replace("_", " ").strip()
        return f"{head}: {tail}"
    return code.replace(".", " ").replace("_", " ").strip().title()


def _reason_codes(event: dict[str, Any]) -> list[str]:
    payload = _payload(event)
    codes = _string_list(payload.get("reason_codes"))
    if codes:
        return codes
    codes = _string_list(payload.get("reasons"))
    if codes:
        return codes
    if payload.get("reason"):
        return [str(payload["reason"])]
    return []


def _actor_for_event(event: dict[str, Any]) -> str:
    payload = _payload(event)
    for key in ("actor", "user_id", "sub", "actor_id"):
        if payload.get(key):
            return str(payload[key])
    return ""


def _surface_for_event(event: dict[str, Any]) -> str:
    payload = _payload(event)
    if payload.get("surface"):
        return str(payload["surface"])
    if payload.get("path"):
        return str(payload["path"])
    if payload.get("requested_path"):
        return str(payload["requested_path"])
    return ""


def _policy_path_for_event(event: dict[str, Any], fallback: str) -> str:
    payload = _payload(event)
    return str(payload.get("policy_path") or fallback)


def _policy_source_for_event(event: dict[str, Any], fallback: str) -> str:
    payload = _payload(event)
    return str(payload.get("policy_source") or fallback)


def _top_reason(reason_counter: Counter[str]) -> str:
    if not reason_counter:
        return "No dominant deny reason recorded"
    reason, count = reason_counter.most_common(1)[0]
    return f"{_humanize_reason(reason)} ({count})"


def _format_age_bucket(timestamp: str) -> tuple[str, str]:
    parsed = _parse_timestamp(timestamp)
    if parsed is None:
        return "warning", "timestamp unavailable"

    age = datetime.now(timezone.utc) - parsed
    if age.total_seconds() <= 48 * 3600:
        return "healthy", "fresh"
    if age.total_seconds() <= 7 * 24 * 3600:
        return "warning", "aging"
    return "critical", "stale"


def _artifact_timestamp(path: Path) -> str:
    if not path.exists():
        return ""

    if path.suffix == ".json":
        document = read_json(path)
        if isinstance(document, dict):
            for key in ("generated_at", "captured_at", "created_at", "timestamp"):
                if document.get(key):
                    return str(document[key])
            machine = document.get("machine", {})
            if isinstance(machine, dict) and machine.get("generated_at"):
                return str(machine["generated_at"])
        if isinstance(document, list) and document:
            candidate = document[-1]
            if isinstance(candidate, dict):
                for key in ("event_time", "generated_at", "captured_at", "timestamp"):
                    if candidate.get(key):
                        return str(candidate[key])

    if path.suffix == ".jsonl":
        records = read_jsonl(path)
        timestamps = sorted(
            value
            for value in (str(record.get("timestamp", "")) for record in records)
            if value
        )
        if timestamps:
            return timestamps[-1]

    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _artifact_integrity(path: Path, relative_path: str, root: Path) -> tuple[str, str]:
    if not path.exists():
        return "critical", "Artifact missing from checkout"

    if relative_path in INSPECTABLE_SCENARIOS:
        document = read_json(path)
        referenced = [root / artifact for artifact in _string_list(document.get("artifacts"))]
        missing = [artifact for artifact in referenced if not artifact.exists()]
        if missing:
            return "warning", f"{len(missing)} referenced artifacts missing"
        return "healthy", "Referenced artifact bundle present"

    if relative_path == reviewer_bundle_relative_path(root):
        reviewer = read_json(path)
        if isinstance(reviewer, dict):
            inspectable = reviewer.get("inspectable_evidence", {})
            bundles = [root / bundle for bundle in _string_list(inspectable.get("bundles"))]
            if bundles and all(bundle.exists() for bundle in bundles):
                return "healthy", "Reviewer bundle references inspectable evidence"
            return "warning", "Reviewer bundle present but referenced artifacts are incomplete"

    if path.suffix == ".json":
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return "critical", "JSON artifact is malformed"
        return "healthy", "JSON structure verified"

    if path.suffix == ".jsonl":
        records = read_jsonl(path)
        return ("healthy", f"{len(records)} structured events present") if records else ("warning", "No events recorded")

    return "neutral", "Raw artifact available"


def _event_feed(root: Path) -> tuple[list[dict[str, Any]], str, str]:
    if has_live_governed_flow_artifacts(root):
        summary = load_latest_governed_flow_summary(root)
        evidence_mode = str(summary.get("evidence_mode", "live")).lower()
        return (
            load_latest_governed_flow_events(root),
            "Live governed flow artifacts" if evidence_mode == "live" else "Governed flow artifacts",
            "overlays/myStarterKit/artifacts/events.jsonl",
        )
    return (
        load_sample_events(root),
        "Demo-derived governed telemetry",
        SAMPLE_EVENTS,
    )


def _control_family_name(control: str) -> str:
    mapping = {
        "policy_coverage": "Policy Enforcement",
        "retrieval_safety": "Retrieval Boundaries",
        "tool_governance": "Tool / MCP Governance",
        "incident_visibility": "Audit & Replay",
        "risky_config_defaults_disabled": "Launch Hygiene",
    }
    return mapping.get(control, control.replace("_", " ").title())


def _control_family_summary(findings: list[dict[str, Any]]) -> list[dict[str, str]]:
    families: dict[str, dict[str, float]] = defaultdict(lambda: {"score": 0.0, "total": 0.0, "pass": 0.0, "conditional": 0.0, "fail": 0.0})
    for finding in findings:
        family = _control_family_name(str(finding.get("control", "control")))
        status = str(finding.get("status", "unknown"))
        families[family]["total"] += 1
        if status == "pass":
            families[family]["score"] += 1.0
            families[family]["pass"] += 1
        elif status in {"conditional_pass", "conditional_go"}:
            families[family]["score"] += 0.5
            families[family]["conditional"] += 1
        else:
            families[family]["fail"] += 1

    summaries: list[dict[str, str]] = []
    for family, values in sorted(families.items()):
        percent = round((values["score"] / values["total"]) * 100) if values["total"] else 0
        status = "healthy"
        if values["fail"]:
            status = "critical"
        elif values["conditional"]:
            status = "warning"
        summaries.append(
            {
                "family": family,
                "score": str(percent),
                "status": status,
                "detail": f"{int(values['pass'])} pass, {int(values['conditional'])} conditional, {int(values['fail'])} fail",
            }
        )
    return summaries


def _section_meta(contract: dict[str, Any]) -> dict[str, dict[str, str]]:
    return {
        str(section.get("id", "")): {
            "id": str(section.get("id", "")),
            "title": str(section.get("title", "")),
            "description": str(section.get("description", "")),
        }
        for section in contract.get("sections", [])
        if section.get("id")
    }


def _upstream_components_by_classification(components: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(component.get("classification", "reference_only")) for component in components)


def _bool_label(value: bool) -> str:
    return "yes" if value else "no"


def _upstream_table_rows(components: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for component in components:
        signals = _string_list(component.get("governance_signals"))
        evidence = _string_list(component.get("evidence_artifacts"))
        rows.append(
            {
                "component": str(component.get("component_name", "Component")),
                "classification": str(component.get("classification", "reference_only")),
                "path_status": str(component.get("runtime_path_status", "reference")),
                "location": str(component.get("runtime_location", "Runtime location not documented.")),
                "signal": signals[0] if signals else "No dedicated governance signal yet.",
                "evidence": evidence[0] if evidence else "No evidence artifact listed.",
                "dev": _bool_label(bool(component.get("enabled_in_dev"))),
                "prod_sim": _bool_label(bool(component.get("enabled_in_prod_sim"))),
            }
        )
    return rows


def _upstream_record_items(components: list[dict[str, Any]]) -> list[dict[str, str]]:
    return [
        _record(
            title=str(component.get("component_name", "Component")),
            meta=" | ".join(
                (
                    str(component.get("classification", "reference_only")),
                    str(component.get("runtime_path_status", "reference")),
                    str(component.get("recommended_action", "review classification")),
                )
            ),
            detail=" ".join(
                part
                for part in (
                    f"Why it stays: {str(component.get('necessity_rationale', '')).strip()}",
                    f"Current gap: {str(component.get('missing_integration_depth', '')).strip()}",
                    f"Removal impact: {str(component.get('removal_impact', '')).strip()}",
                )
                if part
            ),
            status={
                "used_now": "healthy",
                "partially_used": "warning",
                "optional_future": "neutral",
                "reference_only": "neutral",
            }.get(str(component.get("classification", "")), "neutral"),
        )
        for component in components
    ]


def _upstream_audit_cards(inventory: dict[str, Any]) -> list[dict[str, str]]:
    components = list(inventory.get("components", []))
    counts = inventory.get("classification_counts", {})
    audit = inventory.get("audit", {})
    runtime_path_counts = audit.get("runtime_path_counts", {})
    covered = len(audit.get("classified_paths", []))
    total_paths = len(audit.get("component_paths_in_repo", []))
    coverage_status = "healthy" if audit.get("inventory_covers_all_upstreams") else "critical"
    dashboard_visible_count = int(audit.get("dashboard_visible_count", 0))

    return [
        _card("Used now", str(counts.get("used_now", 0)), "healthy", "Components that currently strengthen the repo's real runtime or evidence path.", "#upstream-posture"),
        _card("Partially used", str(counts.get("partially_used", 0)), "warning", "Components present through containers, policy, adapters, or bridge configs without full mandatory-path proof.", "#upstream-posture"),
        _card("Optional / future", str(counts.get("optional_future", 0)), "neutral", "Components intentionally kept out of active architecture claims until they produce reviewer-visible outcomes.", "#upstream-posture"),
        _card("Reference only", str(counts.get("reference_only", 0)), "neutral", "Vendored snapshots retained for compatibility or implementation reference only.", "#upstream-posture"),
        _card("Inventory coverage", f"{covered} / {total_paths or len(components)}", coverage_status, "Every vendored upstream path should be classified exactly once.", "#upstream-posture"),
        _card("Dashboard-visible signals", str(dashboard_visible_count), "healthy" if dashboard_visible_count else "warning", "Components with a reviewer-visible posture, evidence, or activity signal on the homepage.", "#upstream-posture"),
        _card("Mandatory path components", str(runtime_path_counts.get("mandatory", 0)), "healthy", "Components the repo currently treats as part of the proved runtime or evidence path.", "#upstream-posture"),
        _card("Supporting path components", str(runtime_path_counts.get("supporting", 0)), "warning" if runtime_path_counts.get("supporting", 0) else "neutral", "Components that strengthen the platform but are not yet proven as mandatory request-path dependencies.", "#upstream-posture"),
    ]


def _build_artifact_inventory(root: Path) -> tuple[list[dict[str, str]], Counter[str]]:
    reviewer_path = reviewer_bundle_relative_path(root)
    launch_path = launch_report_relative_path(root)
    ingestion_path = dashboard_ingestion_relative_path(root)

    artifact_specs = [
        ("Reviewer evidence bundle", reviewer_path, "review"),
        ("Launch readiness report", launch_path, "launch gate"),
        ("Dashboard ingestion feed", ingestion_path, "telemetry export"),
        ("Governed telemetry sample", SAMPLE_EVENTS, "telemetry feed"),
        ("Prod-sim governed flow", PROD_SIM_GOVERNED_FLOW, "governed flow"),
        ("Prod-sim launch result", PROD_SIM_LAUNCH_GATE, "launch gate"),
        ("Prod-sim events", PROD_SIM_EVENTS, "audit trail"),
        ("Inspectable allowed flow", INSPECTABLE_ALLOWED_FLOW, "inspectable evidence"),
        ("Inspectable denied flow", INSPECTABLE_DENIED_FLOW, "inspectable evidence"),
        ("Inspectable identity denial", INSPECTABLE_IDENTITY_DENY, "inspectable evidence"),
        ("Inspectable OPA denial", INSPECTABLE_OPA_DENY, "inspectable evidence"),
        ("Inspectable retrieval denial", INSPECTABLE_RETRIEVAL_DENY, "inspectable evidence"),
        ("Inspectable secret denial", INSPECTABLE_SECRET_DENY, "inspectable evidence"),
        ("Inspectable trace downgrade", INSPECTABLE_TRACE_DOWNGRADE, "inspectable evidence"),
    ]

    inventory: list[dict[str, str]] = []
    counts: Counter[str] = Counter()
    for label, relative_path, category in artifact_specs:
        path = root / relative_path
        timestamp = _artifact_timestamp(path)
        freshness_status, freshness = _format_age_bucket(timestamp) if path.exists() else ("critical", "missing")
        integrity_status, integrity_detail = _artifact_integrity(path, relative_path, root)
        status = integrity_status if integrity_status == "critical" else freshness_status
        if not path.exists():
            counts["missing"] += 1
        elif freshness == "fresh":
            counts["fresh"] += 1
        elif freshness == "aging":
            counts["aging"] += 1
        elif freshness == "stale":
            counts["stale"] += 1
        if integrity_status == "healthy":
            counts["verified"] += 1

        inventory.append(
            {
                "label": label,
                "category": category,
                "status": status,
                "freshness": freshness,
                "integrity": integrity_detail,
                "last_updated": timestamp or "timestamp unavailable",
                "path": relative_path,
                "href": _raw(relative_path),
                "detail": "Artifact present" if path.exists() else "Artifact missing",
            }
        )

    return inventory, counts


def _build_blocked_actions(
    events: list[dict[str, Any]],
    *,
    event_feed_path: str,
    policy_path: str,
    policy_source: str,
    denied_flow: dict[str, Any],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()

    def append_action(kind: str, title: str, reason_code: str, detail: str, event: dict[str, Any], status: str) -> None:
        trace_id = str(event.get("trace_id", ""))
        key = (str(event.get("request_id", "")), kind, reason_code)
        if key in seen:
            return
        seen.add(key)
        meta = " | ".join(
            value
            for value in (
                str(event.get("tenant_id", "")),
                _surface_for_event(event),
                trace_id,
                str(event.get("timestamp", "")),
            )
            if value
        )
        actions.append(
            {
                "kind": kind,
                "title": title,
                "meta": meta,
                "detail": detail,
                "status": status,
                "reason_code": reason_code or "reason unavailable",
                "reason": _humanize_reason(reason_code) if reason_code else "Reason unavailable",
                "policy_source": _policy_source_for_event(event, policy_source),
                "policy_path": _policy_path_for_event(event, policy_path),
                "trace_id": trace_id,
                "request_id": str(event.get("request_id", "")),
                "tenant": str(event.get("tenant_id", "")),
                "actor": _actor_for_event(event),
                "surface": _surface_for_event(event),
                "timestamp": str(event.get("timestamp", "")),
                "href": _raw(event_feed_path),
            }
        )

    for event in events:
        payload = _payload(event)
        event_type = str(event.get("event_type", ""))
        reasons = _reason_codes(event)
        primary_reason = reasons[0] if reasons else ""

        if event_type == "retrieval.decision" and str(payload.get("decision", "")).lower() in {"deny", "blocked"}:
            source = str(payload.get("source", "unknown source"))
            append_action(
                "Denied retrieval",
                f"Retrieval blocked from {source}",
                primary_reason or f"retrieval.source_not_allowed:{source}",
                f"{_humanize_reason(primary_reason or f'retrieval.source_not_allowed:{source}')}. Tenant retrieval boundary prevented access to {source}.",
                event,
                "critical",
            )

        if event_type == "tool.decision" and _string_list(payload.get("denied")):
            denied_tools = ", ".join(_string_list(payload.get("denied")))
            append_action(
                "Denied tool call",
                f"Tool execution denied: {denied_tools}",
                primary_reason or f"tool.forbidden:{denied_tools}",
                f"{_humanize_reason(primary_reason or f'tool.forbidden:{denied_tools}')}. Governance prevented execution of {denied_tools}.",
                event,
                "critical",
            )

        if event_type == "confirmation.required":
            action_name = str(payload.get("action") or payload.get("tool_name") or "governed action")
            append_action(
                "Confirmation required",
                f"Operator approval required for {action_name}",
                primary_reason or f"tool.confirmation_required:{action_name}",
                f"{_humanize_reason(primary_reason or f'tool.confirmation_required:{action_name}')}. This action stays governed until a human confirms it.",
                event,
                "warning",
            )

        if event_type == "deny.event" and payload.get("blocked") is True:
            surface = _surface_for_event(event)
            requested_path = str(payload.get("requested_path", ""))
            kind = "Blocked /launch/onyx handoff" if "launch/onyx" in surface or requested_path.startswith("/app") else "Governed deny event"
            title = "Onyx handoff blocked by governance" if kind == "Blocked /launch/onyx handoff" else "Governance deny event recorded"
            append_action(
                kind,
                title,
                primary_reason or str(payload.get("reason_code", payload.get("reason", "policy.denied"))),
                f"{_humanize_reason(primary_reason or str(payload.get('reason_code', payload.get('reason', 'policy.denied'))))}. Surface {surface or requested_path or 'unknown'} was denied.",
                event,
                "critical",
            )

    if denied_flow:
        actions.append(
            {
                "kind": "Blocked /launch/onyx handoff",
                "title": "Inspectable denied Onyx handoff",
                "meta": "Reviewer evidence bundle | governed runtime",
                "detail": str(denied_flow.get("summary", "Denied runtime handoff evidence available.")),
                "status": "critical",
                "reason_code": "policy.surface_role_denied:onyx.agents",
                "reason": _humanize_reason("policy.surface_role_denied:onyx.agents"),
                "policy_source": policy_source,
                "policy_path": policy_path,
                "trace_id": "",
                "request_id": "",
                "tenant": "",
                "actor": "",
                "surface": "/launch/onyx -> /app/agents",
                "timestamp": str(denied_flow.get("captured_at", "")),
                "href": _raw(INSPECTABLE_DENIED_FLOW),
            }
        )

    actions.sort(key=lambda item: item.get("timestamp", ""), reverse=True)
    return actions[:8]


def build_control_plane_live_log(root: Path | None = None, limit: int = 12) -> dict[str, Any]:
    resolved_root = repo_root(root)
    return build_activity_snapshot(resolved_root, limit=limit)


def build_control_plane_dashboard(root: Path | None = None) -> dict[str, Any]:
    resolved_root = repo_root(root)
    contract = load_dashboard_contract(resolved_root)
    section_contracts = _section_meta(contract)
    services = load_service_inventory(resolved_root)
    upstream_inventory = load_upstream_usage_inventory(resolved_root)
    upstream_components = list(upstream_inventory.get("components", []))
    upstream_counts = Counter(
        {
            key: int(value)
            for key, value in dict(upstream_inventory.get("classification_counts", {})).items()
        }
    ) or _upstream_components_by_classification(upstream_components)
    upstream_audit = dict(upstream_inventory.get("audit", {}))
    events, event_feed_label, event_feed_path = _event_feed(resolved_root)
    governed_flow_summary = load_latest_governed_flow_summary(resolved_root)
    identity_evidence = load_latest_identity_evidence(resolved_root)
    policy_evidence = load_latest_policy_evidence(resolved_root)
    retrieval_evidence = load_latest_retrieval_evidence(resolved_root)
    secret_evidence = load_latest_secret_evidence(resolved_root)
    trace_correlation = load_latest_trace_correlation(resolved_root)
    policy_bundle = load_runtime_policy_bundle(resolved_root)
    policy = policy_bundle.document
    reviewer = load_reviewer_bundle(resolved_root)
    launch_summary = build_launch_gate_summary(resolved_root)
    evidence_summary = build_evidence_pack_summary(resolved_root)
    eval_summaries = load_eval_summaries(resolved_root)
    latest_eval = eval_summaries[-1] if eval_summaries else {}
    activity_snapshot = build_activity_snapshot(resolved_root, limit=12)
    artifact_inventory, artifact_counts = _build_artifact_inventory(resolved_root)
    denied_flow = read_json(resolved_root / INSPECTABLE_DENIED_FLOW)
    allowed_flow = read_json(resolved_root / INSPECTABLE_ALLOWED_FLOW)

    policy_path = policy_bundle.relative_path
    policy_source = "overlay" if policy_bundle.source == "overlay" else "fallback"
    policy_href = _raw(policy_path)
    reviewer_href = _raw(reviewer_bundle_relative_path(resolved_root))
    launch_report_href = _raw(launch_report_relative_path(resolved_root))
    ingestion_href = _raw(dashboard_ingestion_relative_path(resolved_root))

    policy_events = [event for event in events if event.get("event_type") == "policy.decision"]
    retrieval_events = [event for event in events if event.get("event_type") == "retrieval.decision"]
    tool_attempts = [event for event in events if event.get("event_type") == "tool.execution_attempt"]
    tool_decisions = [event for event in events if event.get("event_type") == "tool.decision"]
    confirmation_events = [event for event in events if event.get("event_type") == "confirmation.required"]
    deny_events = [event for event in events if event.get("event_type") == "deny.event"]
    identity_events = [event for event in events if event.get("event_type") == "identity.established"]
    request_starts = [event for event in events if event.get("event_type") == "request.start"]
    request_ends = [event for event in events if event.get("event_type") == "request.end"]
    trace_ids = sorted({str(event.get("trace_id", "")) for event in events if event.get("trace_id")})
    live_evidence_mode = str(governed_flow_summary.get("evidence_mode", "")).lower() == "live"
    latest_trace_id = str(governed_flow_summary.get("trace_id", "")) or str(trace_correlation.get("trace_id", ""))
    latest_session_id = str(governed_flow_summary.get("session_id", "")) or str(trace_correlation.get("session_id", ""))
    identity_live = bool(identity_evidence.get("live"))
    policy_engine = str(policy_evidence.get("engine", policy_source))
    retrieval_live_backend = bool(retrieval_evidence.get("live_backend"))
    secret_required = bool(secret_evidence.get("required"))
    secret_fetched = bool(secret_evidence.get("fetched"))
    trace_complete = bool(trace_correlation.get("complete"))
    latest_handoff_allowed = bool(governed_flow_summary.get("handoff_allowed", governed_flow_summary.get("decision", False)))
    latest_reason_codes = _string_list(governed_flow_summary.get("reasons", []))
    latest_handoff_reason = latest_reason_codes[0] if latest_reason_codes else "policy.allow"
    latest_missing_evidence = _string_list(governed_flow_summary.get("launch_gate", {}).get("missing_evidence", []))
    audit_events = reviewer.get("sample_audit_events", {}).get("events", [])
    blocked_attacks = reviewer.get("blocked_attack_summary", {}).get("blocked_attacks", [])

    blocked_actions = _build_blocked_actions(
        events,
        event_feed_path=event_feed_path,
        policy_path=policy_path,
        policy_source=policy_source,
        denied_flow=denied_flow,
    )

    denied_policy_decisions = sum(1 for event in policy_events if _payload(event).get("allow") is False)
    blocked_retrievals = sum(
        1
        for event in retrieval_events
        if str(_payload(event).get("decision", "")).lower() in {"deny", "blocked"}
    )
    denied_tool_attempts = sum(1 for event in tool_decisions if _string_list(_payload(event).get("denied")))
    retrieval_pairs = sorted(
        {
            f"{event.get('tenant_id', '')}:{_payload(event).get('source', '')}"
            for event in retrieval_events
            if _payload(event).get("source")
        }
    )
    retrieval_sources = sorted(
        {
            source
            for sources in policy.get("retrieval", {}).get("tenant_allowed_sources", {}).values()
            for source in sources
        }
    )
    policy_reason_counts: Counter[str] = Counter()
    for event in policy_events + deny_events:
        for reason in _reason_codes(event):
            policy_reason_counts[reason] += 1

    surfaces = list(policy.get("surfaces", {}).get("path_policies", []))
    tenants = sorted(policy.get("identity", {}).get("tenant_roles", {}).keys())
    roles = sorted(
        {
            role
            for tenant_roles in policy.get("identity", {}).get("tenant_roles", {}).values()
            for role in tenant_roles
        }
    )
    mcp_servers = sorted(
        value
        for value in policy.get("integrations", {}).get("allowed_integrations", [])
        if str(value).startswith("mcp_server.")
    )
    allowed_tools = list(policy.get("tools", {}).get("allowed_tools", []))
    forbidden_tools = list(policy.get("tools", {}).get("forbidden_tools", []))
    confirmation_required_tools = list(policy.get("tools", {}).get("confirmation_required_tools", []))
    all_tools = sorted(set(allowed_tools + forbidden_tools + confirmation_required_tools))
    onyx_available = path_has_files(resolved_root, "upstream/onyx")

    audit_trace_ids = {
        str(event.get("trace_id", ""))
        for event in audit_events
        if str(event.get("trace_id", ""))
    }
    audit_coverage = round((len(audit_trace_ids & set(trace_ids)) / max(1, len(trace_ids))) * 100)
    trace_coverage = round((len(request_ends) / max(1, len(request_starts))) * 100)
    launch_findings = launch_summary.get("findings", [])
    control_families = _control_family_summary(launch_findings)
    failing_controls = [finding for finding in launch_findings if finding.get("status") != "pass"]
    residual_risks = [str(item) for item in launch_summary.get("residual_risks", [])]
    eval_passed = int(latest_eval.get("passed_count", 0))
    eval_total = int(latest_eval.get("total", 0))

    readiness_panel = {
        "status": _status_from_launch(launch_summary["status"]),
        "status_label": launch_summary["status"].upper(),
        "score": str(launch_summary["readiness_score"]),
        "coverage": str(launch_summary["control_coverage"]),
        "summary": f"{launch_summary['status'].upper()} launch posture with {launch_summary['readiness_score']} readiness score and {len(failing_controls)} non-pass controls.",
        "generated_at": artifact_inventory[1]["last_updated"] if len(artifact_inventory) > 1 else _iso_now(),
        "control_families": control_families,
        "top_failing_controls": [
            _record(
                title=str(finding.get("control", "control")).replace("_", " "),
                meta=str(finding.get("status", "unknown")),
                detail=str(finding.get("summary", "Control summary unavailable.")),
                status="warning" if str(finding.get("status")) in {"conditional_pass", "conditional_go"} else "critical",
                href=launch_report_href,
            )
            for finding in failing_controls[:4]
        ],
        "residual_risks": [
            _record(
                title=f"Residual risk {index + 1}",
                meta="Launch remediation",
                detail=risk,
                status="warning",
                href=launch_report_href,
            )
            for index, risk in enumerate(residual_risks[:4])
        ],
        "evidence_links": [
            _link("Launch report", launch_report_href, "Underlying launch-gate findings and remediation guidance.", "warning"),
            _link("Reviewer bundle", reviewer_href, "Reviewer-ready evidence pack tied to readiness posture.", "healthy"),
            _link("Prod-sim launch result", _raw(PROD_SIM_LAUNCH_GATE), "Machine-readable governed launch result captured from the prod-sim flow.", "healthy"),
        ],
    }

    quick_answers = [
        {
            "question": "What is protected?",
            "answer": f"{len(surfaces)} governed surfaces, {len(tenants)} tenants, {len(retrieval_sources)} retrieval sources, {len(all_tools)} governed tools, and Onyx behind governed handoffs.",
            "detail": "Identity, policy, retrieval, tools, audit, and launch controls are modeled on the homepage.",
            "href": "#asset-coverage",
            "status": "healthy",
        },
        {
            "question": "What was blocked?",
            "answer": f"{len(blocked_actions)} recent governed interventions are visible, including retrieval, tool, confirmation, and runtime handoff outcomes.",
            "detail": "Blocked /launch/onyx handoffs and denied tool paths are called out with trace context.",
            "href": "#blocked-actions",
            "status": "critical" if blocked_actions else "healthy",
        },
        {
            "question": "Why was it blocked?",
            "answer": _top_reason(policy_reason_counts),
            "detail": "Reason codes are surfaced with policy source, policy path, surface, and trace identifiers.",
            "href": "#policy-enforcement",
            "status": "warning" if policy_reason_counts else "neutral",
        },
        {
            "question": "What evidence exists?",
            "answer": f"{len(artifact_inventory) - artifact_counts['missing']} artifacts are present across reviewer bundles, governed traces, launch reports, and dashboard exports.",
            "detail": "Every critical section includes drill-through links to raw evidence.",
            "href": "#evidence-integrity",
            "status": "healthy" if artifact_counts["missing"] == 0 else "warning",
        },
        {
            "question": "Is the system launch-ready?",
            "answer": f"{launch_summary['status'].upper()} with readiness score {launch_summary['readiness_score']}.",
            "detail": f"{len(failing_controls)} controls still need attention and {len(residual_risks)} residual risks remain visible to reviewers.",
            "href": "#launch-gate",
            "status": _status_from_launch(launch_summary["status"]),
        },
    ]

    kpis = [
        _card("Total policy decisions", str(len(policy_events)), "healthy" if policy_events else "warning", "Observed policy decisions in the current governed dataset.", "#policy-enforcement"),
        _card("Denied policy decisions", str(denied_policy_decisions), "critical" if denied_policy_decisions else "healthy", "Explicit policy denies before runtime handoff or action execution.", "#blocked-actions"),
        _card("Conditional actions", str(len(confirmation_events)), "warning" if confirmation_events else "healthy", "Actions paused for human approval before execution.", "#blocked-actions"),
        _card("Retrieval by tenant/source", f"{len(retrieval_events)} / {len(retrieval_pairs)}", "healthy" if retrieval_events else "warning", "Retrieval requests observed across tenant/source boundary pairs.", "#retrieval-boundaries"),
        _card("Blocked retrievals", str(blocked_retrievals), "critical" if blocked_retrievals else "healthy", "Retrieval requests denied by source or tenant policy.", "#blocked-actions"),
        _card("Tool execution attempts", str(len(tool_attempts)), "healthy" if tool_attempts else "warning", "Observed governed tool execution attempts.", "#tool-mcp-governance"),
        _card("Denied tool attempts", str(denied_tool_attempts), "critical" if denied_tool_attempts else "healthy", "Tool invocations blocked by tool policy.", "#blocked-actions"),
        _card("Audit coverage", f"{audit_coverage}%", "healthy" if audit_coverage >= 60 else "warning", "Observed traces that map to explicit audit records.", "#audit-replay"),
        _card("Trace coverage", f"{trace_coverage}%", "healthy" if trace_coverage >= 80 else "warning", "Requests with visible end-state telemetry.", "#audit-replay"),
        _card("Evidence freshness", f"{artifact_counts['fresh']} fresh / {artifact_counts['aging']} aging", "healthy" if artifact_counts["stale"] == 0 else "warning", "Artifact recency across reviewer bundles, launch reports, and telemetry exports.", "#evidence-integrity"),
        _card("Launch-gate status", launch_summary["status"].upper(), _status_from_launch(launch_summary["status"]), f"Readiness score {launch_summary['readiness_score']} with {launch_summary['control_coverage']} control coverage.", "#launch-gate"),
        _card("Failing controls / residual risks", f"{len(failing_controls)} / {len(residual_risks)}", "critical" if failing_controls else "healthy", "Non-pass controls and remaining risks still visible to launch reviewers.", "#launch-gate"),
    ]

    overview_blocks = [
        {
            "type": "cards",
            "title": "Operating posture",
            "items": [
                _card("Dashboard mode", "Governance-first", "healthy", "This homepage leads with governance outcomes and readiness, not raw runtime usage.", "#overview"),
                _card("Data source", event_feed_label, "healthy" if has_live_governed_flow_artifacts(resolved_root) else "warning", f"Primary feed: {event_feed_path}.", _raw(event_feed_path)),
                _card("Runtime position", "Onyx behind governed handoffs", "healthy", "Onyx remains visible as a governed runtime reached through dashboard-controlled surfaces.", "#entry-points"),
                _card(
                    "Upstream discipline",
                    f"{upstream_counts['used_now']} active / {len(upstream_audit.get('component_paths_in_repo', upstream_components))} vendored",
                    "healthy" if upstream_audit.get("inventory_covers_all_upstreams") else "warning",
                    "Vendored upstreams are classified by real runtime use, not by mere presence under `upstream/`.",
                    "#upstream-posture",
                ),
                _card("Portfolio framing", "Layer Retrofit + Launch Gate", "healthy", "The homepage is tuned for evaluator review of enforcement, evidence, and launch readiness.", _raw("docs/control-plane-dashboard-homepage.md")),
            ],
        },
        {
            "type": "records",
            "title": "Portfolio note",
            "items": [
                _record(
                    title="Suggested repository description",
                    meta="README and portfolio positioning",
                    detail=str(contract.get("repo_description_suggestion", "")),
                    status="neutral",
                    href=_raw("README.md"),
                )
            ],
        },
        {
            "type": "links",
            "title": "Primary evidence links",
            "items": [
                _link("Reviewer evidence bundle", reviewer_href, "Reviewer-ready proof pack for blocked actions, auditability, and launch posture.", "healthy"),
                _link("Launch readiness report", launch_report_href, "Raw control findings and residual risk guidance.", "warning"),
                _link("Governed telemetry feed", _raw(event_feed_path), "The event feed used to power the blocked-actions and domain sections.", "healthy"),
                _link("Homepage structure note", _raw("docs/control-plane-dashboard-homepage.md"), "What changed, how the homepage is structured, and what is demo-derived.", "neutral"),
            ],
        },
    ]

    blocked_rows = [
        {
            "kind": action["kind"],
            "reason": action["reason_code"],
            "surface": action["surface"] or "surface unavailable",
            "tenant": action["tenant"] or "tenant unavailable",
            "trace": action["trace_id"] or "trace unavailable",
            "timestamp": action["timestamp"] or "timestamp unavailable",
        }
        for action in blocked_actions
    ]

    identity_rows = [
        {
            "surface": str(rule.get("surface", "")),
            "path": str(rule.get("path", "")),
            "query": json.dumps(rule.get("query", {}), sort_keys=True) if rule.get("query") else "none",
            "allowed_roles": ", ".join(_string_list(rule.get("allowed_roles"))),
        }
        for rule in surfaces
    ]

    retrieval_rows = [
        {
            "tenant": tenant_id,
            "source": source,
            "boundary": "tenant-scoped",
            "trust": ", ".join(policy.get("retrieval", {}).get("source_trust_labels", {}).get(source, [])) or "trust metadata required",
        }
        for tenant_id, sources in policy.get("retrieval", {}).get("tenant_allowed_sources", {}).items()
        for source in sources
    ]

    tool_rows = [
        {"control": "Allowed tools", "value": str(len(allowed_tools)), "notes": ", ".join(allowed_tools) or "none"},
        {"control": "Forbidden tools", "value": str(len(forbidden_tools)), "notes": ", ".join(forbidden_tools) or "none"},
        {"control": "Confirmation required", "value": str(len(confirmation_required_tools)), "notes": ", ".join(confirmation_required_tools) or "none"},
        {"control": "MCP servers", "value": str(len(mcp_servers)), "notes": ", ".join(mcp_servers) or "none"},
        {"control": "Governed runtime", "value": "1", "notes": "Onyx is reached through governed surfaces."},
    ]

    audit_rows = [
        {
            "event": str(event.get("event_type", "audit.event")),
            "trace_id": str(event.get("trace_id", "")),
            "request_id": str(event.get("request_id", "")),
            "summary": str(event.get("event_payload", {}).get("action", "captured")),
        }
        for event in audit_events[:6]
    ]

    asset_rows = [
        {"asset_class": "Surfaces", "count": str(len(surfaces)), "governed_by": "surface path policy", "evidence": policy_path},
        {"asset_class": "Tenants", "count": str(len(tenants)), "governed_by": "identity tenant roles", "evidence": policy_path},
        {"asset_class": "Roles", "count": str(len(roles)), "governed_by": "identity role allowlists", "evidence": policy_path},
        {"asset_class": "Policy bundles", "count": "1", "governed_by": policy_source, "evidence": policy_path},
        {"asset_class": "Retrieval sources", "count": str(len(retrieval_sources)), "governed_by": "retrieval source policy", "evidence": policy_path},
        {"asset_class": "Tools", "count": str(len(all_tools)), "governed_by": "tool policy", "evidence": policy_path},
        {"asset_class": "MCP servers", "count": str(len(mcp_servers)), "governed_by": "integration inventory", "evidence": policy_path},
        {"asset_class": "Governed runtimes", "count": "1", "governed_by": "launch gate + onyx surface policy", "evidence": INSPECTABLE_ALLOWED_FLOW},
    ]

    evidence_rows = [
        {
            "artifact": artifact["label"],
            "category": artifact["category"],
            "freshness": artifact["freshness"],
            "integrity": artifact["integrity"],
            "updated": artifact["last_updated"],
        }
        for artifact in artifact_inventory
    ]

    onyx_handoffs = [
        _record(
            title="Allowed governed handoff",
            meta=str(allowed_flow.get("captured_at", "runtime evidence")),
            detail=str(allowed_flow.get("summary", "Allowed governed handoff evidence available.")),
            status="healthy",
            href=_raw(INSPECTABLE_ALLOWED_FLOW),
        ),
        _record(
            title="Denied governed handoff",
            meta=str(denied_flow.get("captured_at", "runtime evidence")),
            detail=str(denied_flow.get("summary", "Denied governed handoff evidence available.")),
            status="critical",
            href=_raw(INSPECTABLE_DENIED_FLOW),
        ),
    ]
    for event in events:
        payload = _payload(event)
        if str(event.get("event_type")) != "request.start":
            continue
        path = str(payload.get("path", ""))
        if "/launch/onyx" not in path:
            continue
        onyx_handoffs.append(
            _record(
                title="Recent Onyx handoff request",
                meta=" | ".join(
                    value
                    for value in (
                        str(event.get("tenant_id", "")),
                        path,
                        str(event.get("trace_id", "")),
                    )
                    if value
                ),
                detail="Governed launch surface requested through the dashboard entry path.",
                status="neutral",
                href=_raw(event_feed_path),
            )
        )
    onyx_handoffs = onyx_handoffs[:5]

    sections = [
        {
            **section_contracts["overview"],
            "blocks": overview_blocks,
        },
        {
            **section_contracts["blocked-actions"],
            "blocks": [
                {
                    "type": "records",
                    "title": "Recent governed interventions",
                    "items": [
                        _record(action["title"], action["meta"], action["detail"], action["status"], action["href"])
                        for action in blocked_actions
                    ] or [
                        _record("No recent blocked actions", "Governance posture", "No denies or confirmation-required actions are visible in the current dataset.", "healthy")
                    ],
                },
                {
                    "type": "table",
                    "title": "Blocked action timeline",
                    "columns": [
                        {"key": "kind", "label": "Kind"},
                        {"key": "reason", "label": "Reason code"},
                        {"key": "surface", "label": "Surface / path"},
                        {"key": "tenant", "label": "Tenant"},
                        {"key": "trace", "label": "Trace ID"},
                        {"key": "timestamp", "label": "Timestamp"},
                    ],
                    "rows": blocked_rows,
                },
                {
                    "type": "links",
                    "title": "Blocked action evidence",
                    "items": [
                        _link("Governed telemetry feed", _raw(event_feed_path), "Raw reason codes, trace IDs, and timestamps for current governed actions.", "healthy"),
                        _link("Inspectable denied runtime flow", _raw(INSPECTABLE_DENIED_FLOW), "Denied /launch/onyx handoff bundle with linked artifacts.", "critical"),
                        _link("Reviewer evidence bundle", reviewer_href, "Reviewer-facing evidence pack containing blocked attack summary and audit signals.", "healthy"),
                    ],
                },
            ],
        },
        {
            **section_contracts["upstream-posture"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Upstream usage classification",
                    "items": _upstream_audit_cards(upstream_inventory),
                },
                {
                    "type": "table",
                    "title": "Component-by-component posture",
                    "columns": [
                        {"key": "component", "label": "Component"},
                        {"key": "classification", "label": "Classification"},
                        {"key": "path_status", "label": "Path status"},
                        {"key": "location", "label": "Where it sits"},
                        {"key": "signal", "label": "Governance signal"},
                        {"key": "evidence", "label": "Evidence artifact"},
                        {"key": "dev", "label": "Dev"},
                        {"key": "prod_sim", "label": "Prod-sim"},
                    ],
                    "rows": _upstream_table_rows(upstream_components),
                },
                {
                    "type": "records",
                    "title": "Why each component stays or shrinks",
                    "items": _upstream_record_items(upstream_components),
                },
                {
                    "type": "records",
                    "title": "Inventory audit",
                    "items": [
                        _record(
                            "Inventory coverage",
                            f"{len(upstream_audit.get('classified_paths', []))} classified / {len(upstream_audit.get('component_paths_in_repo', []))} vendored paths",
                            "Every top-level vendored upstream path is expected to have one classification entry and no duplicates.",
                            "healthy" if upstream_audit.get("inventory_covers_all_upstreams") else "critical",
                            _dashboard_url("/api/control-plane/upstream-usage"),
                        ),
                        _record(
                            "Dashboard-visible components",
                            ", ".join(upstream_audit.get("dashboard_visible_components", [])[:6]) or "none recorded",
                            "Only components with reviewer-visible outcomes should feel active on the homepage.",
                            "healthy" if upstream_audit.get("dashboard_visible_count", 0) else "warning",
                            "#upstream-posture",
                        ),
                        _record(
                            "Source snapshot required",
                            ", ".join(upstream_audit.get("source_snapshot_required_components", [])[:6]) or "none required",
                            "These are the few components whose vendored source snapshot is currently part of a real repo-owned workflow, test target, or launch path.",
                            "neutral",
                            _raw("docs/upstream-usage-matrix.md"),
                        ),
                    ],
                },
                {
                    "type": "links",
                    "title": "Upstream inventory evidence",
                    "items": [
                        _link("Upstream usage API", _dashboard_url("/api/control-plane/upstream-usage"), "Machine-readable upstream inventory exposed by the control plane.", "healthy"),
                        _link("Upstream usage inventory", _raw("evidence/upstream_usage.inventory.json"), "Repo-owned component inventory with classification, signals, evidence, and removal impact.", "healthy"),
                        _link("Upstream usage matrix", _raw("docs/upstream-usage-matrix.md"), "Reviewer-facing explanation of what is active, partial, optional, or reference-only.", "neutral"),
                    ],
                },
            ],
        },
        {
            **section_contracts["identity-session"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Identity and session coverage",
                    "items": [
                        _card("Tenants under governance", str(len(tenants)), "healthy", "Tenants with explicit role mappings in the runtime policy bundle.", policy_href),
                        _card("Roles under governance", str(len(roles)), "healthy", "Roles allowed to reach governed surfaces.", policy_href),
                        _card("Identity assertions observed", str(len(identity_events)), "healthy" if identity_events else "warning", "Identity establishment events visible in current telemetry.", _raw(event_feed_path)),
                        _card("Governed surfaces", str(len(surfaces)), "healthy", "Registered runtime surfaces protected by policy path rules.", "#entry-points"),
                        _card("Identity source", str(identity_evidence.get("source", "demo_fallback")), "healthy" if identity_live else "warning", "Latest governed flow identity source. Live mode should show Keycloak-backed validation.", _raw("overlays/myStarterKit/artifacts/identity-evidence.json")),
                        _card("Session correlation", latest_session_id or "missing", "healthy" if latest_session_id else "critical", "Latest governed flow session identifier used for trace correlation.", "#trace-correlation"),
                        _card("Identity result", "ALLOW" if identity_evidence.get("authenticated") else "DENY", "healthy" if identity_evidence.get("authenticated") else "critical", f"Latest identity reason: {identity_evidence.get('reason', 'unknown')}.", _raw("overlays/myStarterKit/artifacts/identity-evidence.json")),
                    ],
                },
                {
                    "type": "table",
                    "title": "Surface access policy",
                    "columns": [
                        {"key": "surface", "label": "Surface"},
                        {"key": "path", "label": "Path"},
                        {"key": "query", "label": "Query match"},
                        {"key": "allowed_roles", "label": "Allowed roles"},
                    ],
                    "rows": identity_rows,
                },
                {
                    "type": "links",
                    "title": "Identity evidence",
                    "items": [
                        _link("Policy bundle", policy_href, "Tenant roles and surface access rules used by runtime governance.", "healthy"),
                        _link("Keycloak integration note", _raw("docs/keycloak-integration.md"), "Identity/session wiring and integration notes for the dashboard-first stack.", "neutral"),
                        _link("Governed telemetry feed", _raw(event_feed_path), "Identity-established events with tenant and actor context.", "healthy"),
                        _link("Identity evidence artifact", _raw("overlays/myStarterKit/artifacts/identity-evidence.json"), "Latest governed-flow identity proof showing live vs demo identity derivation.", "healthy" if identity_evidence else "warning"),
                    ],
                },
            ],
        },
        {
            **section_contracts["policy-enforcement"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Policy decision summary",
                    "items": [
                        _card("Policy decisions", str(len(policy_events)), "healthy" if policy_events else "warning", "Observed policy decision events in current governed telemetry.", _raw(event_feed_path)),
                        _card("Explicit denies", str(denied_policy_decisions), "critical" if denied_policy_decisions else "healthy", "Policy decisions that directly denied access or handoff.", "#blocked-actions"),
                        _card("Top deny reason", _top_reason(policy_reason_counts), "warning" if policy_reason_counts else "neutral", "Dominant governance rationale across denies and blocked runtime handoffs.", "#blocked-actions"),
                        _card("Policy source", policy_source.upper(), "healthy" if policy_source == "overlay" else "warning", f"Current runtime policy bundle path: {policy_path}.", policy_href),
                        _card("Decision engine", policy_engine.upper(), "healthy" if policy_engine == "opa" else "warning", "Latest governed-flow policy engine. Live mode should show OPA as the active decision path.", _raw("overlays/myStarterKit/artifacts/policy-evidence.json")),
                        _card("Latest policy result", "ALLOW" if policy_evidence.get("allow") else "DENY", "healthy" if policy_evidence.get("allow") else "critical", f"Latest policy reasons: {', '.join(_string_list(policy_evidence.get('reason_codes')) or _string_list(policy_evidence.get('reasons')) or ['unknown'])}.", _raw("overlays/myStarterKit/artifacts/policy-evidence.json")),
                    ],
                },
                {
                    "type": "records",
                    "title": "Recent policy outcomes",
                    "items": [
                        _record(
                            title="Allow" if _payload(event).get("allow") else "Deny",
                            meta=" | ".join(
                                value
                                for value in (
                                    str(event.get("tenant_id", "")),
                                    _surface_for_event(event),
                                    str(event.get("trace_id", "")),
                                )
                                if value
                            ),
                            detail=", ".join(_reason_codes(event)) or "Policy reasons unavailable.",
                            status="healthy" if _payload(event).get("allow") else "critical",
                            href=_raw(event_feed_path),
                        )
                        for event in policy_events[:6]
                    ],
                },
                {
                    "type": "links",
                    "title": "Policy drill-through",
                    "items": [
                        _link("Runtime policy bundle", policy_href, "Raw runtime policy bundle governing surfaces, retrieval, and tools.", "healthy"),
                        _link("Policy rego", _raw("policies/rego/policy.rego"), "Underlying policy rule definitions used for the local stack.", "neutral"),
                        _link("Tool governance note", _raw("docs/tool-governance.md"), "Documentation for tool policy posture and runtime enforcement.", "neutral"),
                        _link("Policy evidence artifact", _raw("overlays/myStarterKit/artifacts/policy-evidence.json"), "Latest governed-flow policy decision artifact with engine, package path, and reasons.", "healthy" if policy_evidence else "warning"),
                    ],
                },
            ],
        },
        {
            **section_contracts["retrieval-boundaries"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Retrieval enforcement summary",
                    "items": [
                        _card("Retrieval requests", str(len(retrieval_events)), "healthy" if retrieval_events else "warning", "Observed governed retrieval requests.", _raw(event_feed_path)),
                        _card("Blocked retrievals", str(blocked_retrievals), "critical" if blocked_retrievals else "healthy", "Denied retrievals by source or tenant boundary.", "#blocked-actions"),
                        _card("Allowed sources", str(len(retrieval_sources)), "healthy", "Sources explicitly modeled in policy.", policy_href),
                        _card("Tenant/source pairs", str(len(retrieval_rows)), "healthy", "Tenant-scoped retrieval boundaries declared in policy.", policy_href),
                        _card("Latest backend", str(retrieval_evidence.get("backend", "demo")), "healthy" if retrieval_live_backend else "warning", "Latest governed-flow retrieval backend. Live mode should show a real backend path such as Qdrant.", _raw("overlays/myStarterKit/artifacts/retrieval-evidence.json")),
                        _card("Latest retrieval result", "ALLOW" if retrieval_evidence.get("allow") else "DENY", "healthy" if retrieval_evidence.get("allow") else "critical", f"Latest retrieval reasons: {', '.join(_string_list(retrieval_evidence.get('reason_codes')) or _string_list(retrieval_evidence.get('reasons')) or ['unknown'])}.", _raw("overlays/myStarterKit/artifacts/retrieval-evidence.json")),
                    ],
                },
                {
                    "type": "table",
                    "title": "Retrieval source coverage",
                    "columns": [
                        {"key": "tenant", "label": "Tenant"},
                        {"key": "source", "label": "Source"},
                        {"key": "boundary", "label": "Boundary"},
                        {"key": "trust", "label": "Trust requirement"},
                    ],
                    "rows": retrieval_rows,
                },
                {
                    "type": "records",
                    "title": "Recent retrieval outcomes",
                    "items": [
                        _record(
                            title=f"{str(_payload(event).get('decision', 'allow')).upper()} retrieval",
                            meta=" | ".join(
                                value
                                for value in (
                                    str(event.get("tenant_id", "")),
                                    str(_payload(event).get("source", "")),
                                    str(event.get("trace_id", "")),
                                )
                                if value
                            ),
                            detail=", ".join(_reason_codes(event)) or "Retrieval reason unavailable.",
                            status="critical" if str(_payload(event).get("decision", "")).lower() in {"deny", "blocked"} else "healthy",
                            href=_raw(event_feed_path),
                        )
                        for event in retrieval_events[:6]
                    ],
                },
                {
                    "type": "links",
                    "title": "Retrieval evidence",
                    "items": [
                        _link("Retrieval evidence artifact", _raw("overlays/myStarterKit/artifacts/retrieval-evidence.json"), "Latest governed-flow retrieval evidence with backend, filters, and result count.", "healthy" if retrieval_evidence else "warning"),
                        _link("Retrieval security note", _raw("docs/retrieval-security.md"), "Tenant-scoped retrieval governance and trust requirements.", "neutral"),
                    ],
                },
            ],
        },
        {
            **section_contracts["secret-access"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Secret access posture",
                    "items": [
                        _card("Secret required", "yes" if secret_required else "no", "warning" if secret_required else "neutral", "Whether the latest governed flow required a live secret lookup.", _raw("overlays/myStarterKit/artifacts/secret-evidence.json")),
                        _card("Secret fetched", "yes" if secret_fetched else "no", "healthy" if secret_fetched or not secret_required else "critical", "Required secret access must succeed in live mode or the governed operation fails closed.", _raw("overlays/myStarterKit/artifacts/secret-evidence.json")),
                        _card("Secret backend", str(secret_evidence.get("backend", "unconfigured")), "healthy" if secret_evidence.get("backend") == "vault" else "warning", "Latest governed-flow secret backend.", _raw("overlays/myStarterKit/artifacts/secret-evidence.json")),
                        _card("Secret reason", str(secret_evidence.get("reason", "unknown")), "healthy" if secret_fetched or not secret_required else "critical", "Latest governed-flow secret access reason code.", _raw("overlays/myStarterKit/artifacts/secret-evidence.json")),
                    ],
                },
                {
                    "type": "records",
                    "title": "Latest secret access evidence",
                    "items": [
                        _record(
                            title="Latest governed secret lookup",
                            meta=" | ".join(value for value in (str(secret_evidence.get("purpose", "")), latest_trace_id, latest_session_id) if value),
                            detail=f"Required={secret_required} fetched={secret_fetched} reason={secret_evidence.get('reason', 'unknown')}",
                            status="healthy" if secret_fetched or not secret_required else "critical",
                            href=_raw("overlays/myStarterKit/artifacts/secret-evidence.json"),
                        )
                    ],
                },
                {
                    "type": "links",
                    "title": "Secret evidence",
                    "items": [
                        _link("Secret evidence artifact", _raw("overlays/myStarterKit/artifacts/secret-evidence.json"), "Latest governed-flow secret access artifact with masked status only.", "healthy" if secret_evidence else "warning"),
                        _link("Vault integration note", _raw("docs/vault-integration.md"), "Safe secret-handling expectations and fail-safe behavior.", "neutral"),
                    ],
                },
            ],
        },
        {
            **section_contracts["tool-mcp-governance"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Tool and MCP posture",
                    "items": [
                        _card("Tool inventory", str(len(all_tools)), "healthy", "Union of allowed, forbidden, and confirmation-required tools.", policy_href),
                        _card("Tool attempts", str(len(tool_attempts)), "healthy" if tool_attempts else "warning", "Observed governed tool execution attempts.", _raw(event_feed_path)),
                        _card("Denied tool attempts", str(denied_tool_attempts), "critical" if denied_tool_attempts else "healthy", "Blocked tool invocations recorded in telemetry.", "#blocked-actions"),
                        _card("Confirmation required", str(len(confirmation_events)), "warning" if confirmation_events else "healthy", "High-impact tool actions paused pending approval.", "#blocked-actions"),
                        _card("MCP servers", str(len(mcp_servers)), "healthy" if mcp_servers else "warning", "MCP surfaces explicitly present in integration policy.", policy_href),
                        _card("Governed runtime", "Onyx", "healthy" if onyx_available else "warning", "Onyx is reached through governed launch surfaces only.", "#entry-points"),
                    ],
                },
                {
                    "type": "table",
                    "title": "Tool / MCP inventory",
                    "columns": [
                        {"key": "control", "label": "Control"},
                        {"key": "value", "label": "Value"},
                        {"key": "notes", "label": "Notes"},
                    ],
                    "rows": tool_rows,
                },
                {
                    "type": "records",
                    "title": "Recent tool decisions",
                    "items": [
                        *[
                            _record(
                                title=f"Tool attempt: {str(_payload(event).get('tool_name', 'unknown'))}",
                                meta=" | ".join(
                                    value
                                    for value in (
                                        str(_payload(event).get("status", "")),
                                        _surface_for_event(event),
                                        str(event.get("trace_id", "")),
                                    )
                                    if value
                                ),
                                detail="Tool execution attempt observed through the governed runtime.",
                                status="warning" if str(_payload(event).get("status", "")) == "confirmation_required" else "neutral",
                                href=_raw(event_feed_path),
                            )
                            for event in tool_attempts[:4]
                        ],
                        *[
                            _record(
                                title=f"Tool decision: {', '.join(_string_list(_payload(event).get('denied')))}",
                                meta=str(event.get("trace_id", "")),
                                detail=", ".join(_reason_codes(event)) or "Tool reason unavailable.",
                                status="critical",
                                href=_raw(event_feed_path),
                            )
                            for event in tool_decisions[:4]
                            if _string_list(_payload(event).get("denied"))
                        ],
                    ],
                },
            ],
        },
        {
            **section_contracts["audit-replay"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Auditability summary",
                    "items": [
                        _card("Audit coverage", f"{audit_coverage}%", "healthy" if audit_coverage >= 60 else "warning", "Observed traces tied to explicit audit events in the reviewer bundle.", reviewer_href),
                        _card("Trace coverage", f"{trace_coverage}%", "healthy" if trace_coverage >= 80 else "warning", "Requests with visible completion telemetry in the current feed.", _raw(event_feed_path)),
                        _card("Trace continuity", "complete" if trace_complete else "incomplete", "healthy" if trace_complete else "critical", "Latest governed flow trace continuity across identity, policy, retrieval, secret, tool, and handoff steps.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Replay bundles", str(len(INSPECTABLE_SCENARIOS)), "healthy", "Inspectable pass/fail live-governed examples are available for evaluator review.", _raw(INSPECTABLE_ALLOWED_FLOW)),
                        _card("Blocked attacks", str(evidence_summary.get("blocked_count", 0)), "healthy", "Reviewer evidence bundle records blocked hostile scenarios.", reviewer_href),
                        _card("Eval pass / total", f"{eval_passed} / {eval_total}", "healthy" if eval_total == 0 or eval_passed == eval_total else "warning", "Latest available evaluation summary for the governed stack.", ingestion_href),
                    ],
                },
                {
                    "type": "table",
                    "title": "Audit event sample",
                    "columns": [
                        {"key": "event", "label": "Audit event"},
                        {"key": "trace_id", "label": "Trace ID"},
                        {"key": "request_id", "label": "Request ID"},
                        {"key": "summary", "label": "Summary"},
                    ],
                    "rows": audit_rows,
                },
                {
                    "type": "records",
                    "title": "Replay and reviewer evidence",
                    "items": [
                        *[
                            _record(
                                title=str(attack.get("scenario", "Blocked scenario")).replace("_", " "),
                                meta=str(attack.get("decision", "blocked")),
                                detail=str(attack.get("control_triggered", "control triggered")),
                                status="healthy",
                                href=reviewer_href,
                            )
                            for attack in blocked_attacks
                        ],
                        _record(
                            title="Inspectable allowed flow",
                            meta="Reviewer evidence",
                            detail="Allowed governed runtime flow with linked launch and event artifacts.",
                            status="healthy",
                            href=_raw(INSPECTABLE_ALLOWED_FLOW),
                        ),
                        _record(
                            title="Inspectable denied flow",
                            meta="Reviewer evidence",
                            detail="Denied runtime handoff with inspectable reasons and linked artifacts.",
                            status="critical",
                            href=_raw(INSPECTABLE_DENIED_FLOW),
                        ),
                    ],
                },
                {
                    "type": "links",
                    "title": "Audit drill-through",
                    "items": [
                        _link("Reviewer evidence bundle", reviewer_href, "Audit sample, blocked attack summary, and inspectable evidence references.", "healthy"),
                        _link("Dashboard ingestion feed", ingestion_href, "Export used for dashboard-level ingestion and replay views.", "neutral"),
                        _link("Prod-sim governed flow response", _raw(PROD_SIM_GOVERNED_FLOW), "Governed flow response with trace, reasons, and launch-gate outcome.", "healthy"),
                    ],
                },
            ],
        },
        {
            **section_contracts["trace-correlation"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Trace correlation posture",
                    "items": [
                        _card("Latest trace", latest_trace_id or "missing", "healthy" if latest_trace_id else "critical", "Latest governed-flow trace identifier.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Latest session", latest_session_id or "missing", "healthy" if latest_session_id else "warning", "Latest governed-flow session identifier tied to the trace.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Trace complete", "yes" if trace_complete else "no", "healthy" if trace_complete else "critical", "Whether the latest governed flow recorded the required end-to-end control steps under one correlated trace.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Missing steps", str(len(_string_list(trace_correlation.get("missing_steps", [])))), "healthy" if not _string_list(trace_correlation.get("missing_steps", [])) else "critical", "Missing trace-correlation steps for the latest governed flow.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                    ],
                },
                {
                    "type": "records",
                    "title": "Latest trace evidence",
                    "items": [
                        _record(
                            title="Correlated governed request",
                            meta=" | ".join(value for value in (latest_trace_id, latest_session_id, str(governed_flow_summary.get("evidence_mode", event_feed_label))) if value),
                            detail=f"Missing steps: {', '.join(trace_correlation.get('missing_steps', [])) or 'none'}",
                            status="healthy" if trace_complete else "critical",
                            href=_raw("overlays/myStarterKit/artifacts/trace-correlation.json"),
                        )
                    ],
                },
                {
                    "type": "links",
                    "title": "Trace evidence",
                    "items": [
                        _link("Trace correlation artifact", _raw("overlays/myStarterKit/artifacts/trace-correlation.json"), "Cross-step trace evidence for the latest governed flow.", "healthy" if trace_correlation else "warning"),
                        _link("Governed event feed", _raw(event_feed_path), "Underlying correlated events for the latest governed path.", "healthy"),
                    ],
                },
            ],
        },
        {
            **section_contracts["launch-gate"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Launch decision summary",
                    "items": [
                        _card("Readiness status", launch_summary["status"].upper(), _status_from_launch(launch_summary["status"]), "Current launch verdict from the launch-gate summary.", launch_report_href),
                        _card("Readiness score", str(launch_summary["readiness_score"]), _status_from_launch(launch_summary["status"]), "Readiness score synthesized from the launch report findings.", launch_report_href),
                        _card("Control coverage", str(launch_summary["control_coverage"]), "healthy", "Passing controls over total launch findings.", launch_report_href),
                        _card("Failing controls", str(len(failing_controls)), "critical" if failing_controls else "healthy", "Controls that are not in a full pass state.", launch_report_href),
                        _card("Residual risks", str(len(residual_risks)), "warning" if residual_risks else "healthy", "Remaining launch caveats or hardening tasks.", launch_report_href),
                        _card("Evidence mode", str(launch_summary.get("evidence_mode", "demo")).upper(), "healthy" if str(launch_summary.get("evidence_mode", "")) == "live" else "warning", "Live mode should compute readiness from governed-flow evidence artifacts instead of sample/demo telemetry.", launch_report_href),
                        _card("Missing evidence", str(len(launch_summary.get("missing_controls", []))), "healthy" if not launch_summary.get("missing_controls") else "critical", "Launch-gate missing evidence currently blocking or downgrading readiness.", launch_report_href),
                    ],
                },
                {
                    "type": "records",
                    "title": "Top failing controls",
                    "items": readiness_panel["top_failing_controls"] or [
                        _record("No failing controls", "Launch gate", "All controls are in a pass state.", "healthy", launch_report_href)
                    ],
                },
                {
                    "type": "records",
                    "title": "Residual risks",
                    "items": readiness_panel["residual_risks"] or [
                        _record("No residual risks", "Launch gate", "No residual launch risks are listed in the current report.", "healthy", launch_report_href)
                    ],
                },
                {
                    "type": "links",
                    "title": "Launch evidence",
                    "items": readiness_panel["evidence_links"],
                },
            ],
        },
        {
            **section_contracts["asset-coverage"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Governed asset counts",
                    "items": [
                        _card("Surfaces", str(len(surfaces)), "healthy", "Registered governed UI/runtime surfaces.", policy_href),
                        _card("Tenants", str(len(tenants)), "healthy", "Tenant identities protected by role policy.", policy_href),
                        _card("Roles", str(len(roles)), "healthy", "Roles mapped into governed surface access.", policy_href),
                        _card("Retrieval sources", str(len(retrieval_sources)), "healthy", "Retrieval sources under tenant-scoped policy.", policy_href),
                        _card("Tools", str(len(all_tools)), "healthy", "Governed tools across allow, deny, and confirmation-required modes.", policy_href),
                        _card("MCP servers", str(len(mcp_servers)), "healthy" if mcp_servers else "warning", "MCP inventory visible in integration policy.", policy_href),
                        _card("Governed runtimes", "1", "healthy", "Onyx is the governed runtime behind dashboard surfaces.", "#entry-points"),
                    ],
                },
                {
                    "type": "table",
                    "title": "Protection inventory",
                    "columns": [
                        {"key": "asset_class", "label": "Asset class"},
                        {"key": "count", "label": "Count"},
                        {"key": "governed_by", "label": "Governed by"},
                        {"key": "evidence", "label": "Evidence path"},
                    ],
                    "rows": asset_rows,
                },
                {
                    "type": "links",
                    "title": "Coverage references",
                    "items": [
                        _link("Asset inventory note", _raw("docs/asset-inventory.md"), "Repository note describing protected assets and control-plane ownership.", "neutral"),
                        _link("Repo map", _raw("docs/repo-map.md"), "High-level repository layout that anchors the dashboard-first architecture.", "neutral"),
                        _link("Runtime policy bundle", policy_href, "Source of truth for governed surfaces, roles, retrieval sources, and tools.", "healthy"),
                    ],
                },
            ],
        },
        {
            **section_contracts["evidence-integrity"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Freshness and integrity summary",
                    "items": [
                        _card("Fresh artifacts", str(artifact_counts["fresh"]), "healthy", "Artifacts updated recently enough for evaluator trust.", "#evidence-integrity"),
                        _card("Aging artifacts", str(artifact_counts["aging"]), "warning" if artifact_counts["aging"] else "healthy", "Artifacts that exist but are no longer same-day fresh.", "#evidence-integrity"),
                        _card("Stale artifacts", str(artifact_counts["stale"]), "critical" if artifact_counts["stale"] else "healthy", "Artifacts present but old enough to warrant attention.", "#evidence-integrity"),
                        _card("Missing artifacts", str(artifact_counts["missing"]), "critical" if artifact_counts["missing"] else "healthy", "Expected evidence that is missing from the checkout.", "#evidence-integrity"),
                        _card("Verified artifacts", str(artifact_counts["verified"]), "healthy", "Artifacts whose structure or bundle references were checked.", "#evidence-integrity"),
                    ],
                },
                {
                    "type": "table",
                    "title": "Artifact inventory",
                    "columns": [
                        {"key": "artifact", "label": "Artifact"},
                        {"key": "category", "label": "Category"},
                        {"key": "freshness", "label": "Freshness"},
                        {"key": "integrity", "label": "Integrity"},
                        {"key": "updated", "label": "Last updated"},
                    ],
                    "rows": evidence_rows,
                },
                {
                    "type": "records",
                    "title": "Integrity warnings",
                    "items": [
                        _record(
                            title=artifact["label"],
                            meta=artifact["freshness"],
                            detail=f"{artifact['integrity']}. {artifact['detail']} ({artifact['path']}).",
                            status=artifact["status"],
                            href=artifact["href"],
                        )
                        for artifact in artifact_inventory
                        if artifact["status"] in {"warning", "critical"}
                    ] or [
                        _record("No integrity warnings", "Evidence integrity", "All tracked artifacts are present and structurally readable.", "healthy")
                    ],
                },
            ],
        },
        {
            **section_contracts["entry-points"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Governed runtime posture",
                    "items": [
                        _card("Onyx visibility", "Governed runtime", "healthy" if onyx_available else "warning", "Onyx remains behind governed dashboard handoffs.", _raw("docs/onyx-integration.md")),
                        _card("Allowed handoff evidence", "Visible", "healthy", "Inspectable evidence bundle for an allowed runtime handoff is present.", _raw(INSPECTABLE_ALLOWED_FLOW)),
                        _card("Denied handoff evidence", "Visible", "critical", "Inspectable evidence bundle for a denied runtime handoff is present.", _raw(INSPECTABLE_DENIED_FLOW)),
                        _card("Recent handoff outcomes", str(len(onyx_handoffs)), "healthy", "Recent governed handoff outcomes are visible to reviewers.", "#entry-points"),
                        _card("Latest handoff", "ALLOW" if latest_handoff_allowed else "DENY", "healthy" if latest_handoff_allowed else "critical", f"Latest governed handoff reason: {latest_handoff_reason}.", _raw("overlays/myStarterKit/artifacts/governed-flow-summary.json")),
                        _card("Latest evidence mode", str(governed_flow_summary.get("evidence_mode", event_feed_label)).upper(), "healthy" if live_evidence_mode else "warning", "Current governed handoff evidence mode.", _raw("overlays/myStarterKit/artifacts/governed-flow-summary.json")),
                        _card("Missing handoff evidence", ", ".join(latest_missing_evidence) or "none", "healthy" if not latest_missing_evidence else "critical", "Live-mode missing evidence that affected the latest handoff or launch-gate result.", _raw("overlays/myStarterKit/artifacts/governed-flow-summary.json")),
                    ],
                },
                {
                    "type": "records",
                    "title": "Recent Onyx handoff outcomes",
                    "items": onyx_handoffs,
                },
                {
                    "type": "links",
                    "title": "Governed entry points",
                    "items": [
                        _link("Open Chat", _launch_handoff_url("/app"), "Launch the governed Onyx chat surface through the dashboard handoff.", "healthy"),
                        _link("Search Knowledge", _launch_handoff_url("/app?chatMode=search"), "Launch the governed search-oriented Onyx surface.", "healthy"),
                        _link("Open Agents", _launch_handoff_url("/app/agents"), "Governed agents surface; non-admin roles should be denied.", "warning"),
                        _link("Governed flow API", _dashboard_url("/api/control-plane/governed-flow"), "Trigger a governed flow run to generate fresh runtime artifacts.", "neutral"),
                        _link("Onyx integration note", _raw("docs/onyx-integration.md"), "Architecture note for the governed Onyx runtime path.", "neutral"),
                    ],
                },
            ],
        },
    ]

    sources = [
        _link("Governed event feed", _raw(event_feed_path), "Event feed used by the dashboard overview and blocked-actions views.", "healthy"),
        _link("Policy bundle", policy_href, "Runtime surface, retrieval, and tool governance policy.", "healthy" if policy_source == "overlay" else "warning"),
        _link("Governed flow summary", _raw("overlays/myStarterKit/artifacts/governed-flow-summary.json"), "Latest governed-flow summary including identity, policy, retrieval, secret, trace, and launch-gate evidence.", "healthy" if governed_flow_summary else "warning"),
        _link("Upstream usage inventory", _raw("evidence/upstream_usage.inventory.json"), "Classification of active, partial, optional, and reference-only upstream components.", "healthy"),
        _link("Reviewer evidence bundle", reviewer_href, "Consolidated reviewer-facing evidence pack.", "healthy"),
        _link("Launch report", launch_report_href, "Launch-gate findings and residual risk guidance.", "warning"),
        _link("Dashboard ingestion feed", ingestion_href, "Dashboard export sample used for evidence drill-through and replay references.", "neutral"),
    ]

    return {
        "title": str(contract.get("title", "AI Trust & Security Stack Control Plane")),
        "subtitle": str(contract.get("subtitle", "")),
        "hero_copy": str(contract.get("hero_copy", "")),
        "landing_steps": list(contract.get("landing_steps", [])),
        "generated_at": _iso_now(),
        "runtime_module": "Onyx governed runtime",
        "data_mode": {
            "label": "Live governed flow artifacts" if live_evidence_mode else event_feed_label,
            "status": "healthy" if live_evidence_mode else ("healthy" if has_live_governed_flow_artifacts(resolved_root) else "warning"),
            "detail": f"Primary event feed: {event_feed_path}",
        },
        "repo_description_suggestion": str(contract.get("repo_description_suggestion", "")),
        "operator_briefing": quick_answers,
        "kpis": kpis,
        "readiness_panel": readiness_panel,
        "tabs": list(contract.get("tabs", [])),
        "sections": sections,
        "sources": sources,
        "activity_snapshot": activity_snapshot,
        "evidence_exports": evidence_summary.get("exports", []),
    }
