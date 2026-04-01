from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

from backend.activity_service.service import build_activity_snapshot, build_onyx_runtime_proof, build_stack_health_snapshot
from backend.evidence_service.service import build_evidence_pack_summary
from backend.integration_adapter.repository import (
    AUDIT_RECORDS_PATH,
    dashboard_ingestion_relative_path,
    governed_request_feed_relative_path,
    has_live_governed_flow_artifacts,
    launch_report_relative_path,
    load_latest_audit_records,
    load_dashboard_contract,
    load_eval_summaries,
    load_latest_governed_request_feed,
    load_latest_governed_flow_events,
    load_latest_governed_flow_summary,
    load_latest_identity_evidence,
    load_latest_onyx_runtime_proof,
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


def _card(label: str, value: str, status: str, detail: str, href: str = "", **extras: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"label": label, "value": value, "status": status, "detail": detail}
    if href:
        item["href"] = href
    item.update({key: extra for key, extra in extras.items() if extra is not None and extra != ""})
    return item


def _record(title: str, meta: str, detail: str, status: str = "neutral", href: str = "", **extras: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"title": title, "meta": meta, "detail": detail, "status": status}
    if href:
        item["href"] = href
    item.update({key: extra for key, extra in extras.items() if extra is not None and extra != ""})
    return item


def _link(label: str, href: str, description: str, status: str = "neutral", **extras: Any) -> dict[str, Any]:
    item: dict[str, Any] = {"label": label, "href": href, "description": description, "status": status}
    item.update({key: extra for key, extra in extras.items() if extra is not None and extra != ""})
    return item


def _spotlight(
    *,
    eyebrow: str,
    title: str,
    detail: str,
    status: str = "neutral",
    href: str = "",
    fields: list[dict[str, str]] | None = None,
    **extras: Any,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "eyebrow": eyebrow,
        "title": title,
        "detail": detail,
        "status": status,
        "fields": fields or [],
    }
    if href:
        item["href"] = href
    item.update({key: extra for key, extra in extras.items() if extra is not None and extra != ""})
    return item


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


def _launch_handoff_path(path: str, *, mode: str = "", view: str = "") -> str:
    href = f"/launch/onyx?path={quote(path, safe='/?=&')}"
    if mode:
        href = f"{href}&mode={quote(mode, safe='')}"
    if view:
        href = f"{href}&view={quote(view, safe='')}"
    return href


def _launch_handoff_url(path: str, *, mode: str = "", view: str = "") -> str:
    return _dashboard_url(_launch_handoff_path(path, mode=mode, view=view))


def _live_session_start_url(next_path: str) -> str:
    return _dashboard_url(f"/auth/live-session/start?{urlencode({'next': next_path})}")


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


def _status_display(status: str) -> str:
    return {
        "healthy": "Good",
        "warning": "Needs attention",
        "critical": "Serious issue",
        "neutral": "For context",
    }.get(status, status.title())


def _readiness_display(verdict: str) -> str:
    return {
        "go": "Ready now",
        "conditional": "Partly ready",
        "no-go": "Not ready",
    }.get(str(verdict).strip().lower(), str(verdict).strip().upper() or "Unknown")


def _normalize_launch_verdict(verdict: str) -> str:
    normalized = str(verdict).strip().lower().replace("_", "-")
    return {
        "pass": "go",
        "go": "go",
        "conditional": "conditional",
        "conditional-pass": "conditional",
        "conditional-go": "conditional",
        "no-go": "no-go",
        "fail": "no-go",
        "deny": "no-go",
        "blocked": "no-go",
    }.get(normalized, "")


def _allow_deny_display(value: bool) -> str:
    return "Allowed" if value else "Blocked"


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


def _timestamp_display(value: str) -> str:
    parsed = _parse_timestamp(value)
    if parsed is None:
        return value or "Unavailable"
    return parsed.strftime("%Y-%m-%d %H:%M UTC")


def _timestamp_badges(
    *,
    timestamp: str,
    evidence_mode: str = "",
    provenance: str = "",
    label: str = "Checked",
) -> list[dict[str, str]]:
    if not timestamp:
        return []
    freshness_status, _ = _format_age_bucket(timestamp)
    return [
        {"label": label, "value": timestamp, "kind": "timestamp"},
        {
            "label": "Freshness",
            "value": _freshness_label(timestamp=timestamp, evidence_mode=evidence_mode, provenance=provenance),
            "status": freshness_status,
        },
    ]


def _trend_summary(
    current: int,
    previous: int | None,
    *,
    lower_is_better: bool,
    context: str,
    baseline_label: str,
    worse_status: str = "warning",
) -> dict[str, str]:
    if previous is None:
        return {
            "label": "No earlier baseline",
            "detail": f"No earlier {baseline_label} is available yet.",
            "status": "neutral",
        }

    delta = current - previous
    if delta == 0:
        return {
            "label": f"Flat vs previous {context}",
            "detail": f"Previous {baseline_label}: {previous}.",
            "status": "healthy" if current == 0 else "neutral",
        }

    improved = delta < 0 if lower_is_better else delta > 0
    direction = "Down" if delta < 0 else "Up"
    return {
        "label": f"{direction} {abs(delta)} vs previous {context}",
        "detail": f"Previous {baseline_label}: {previous}.",
        "status": "healthy" if improved else worse_status,
    }


def _launch_gate_run_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    document = read_json(path)
    if not isinstance(document, dict):
        return {}

    machine = document.get("machine", {})
    if not isinstance(machine, dict):
        machine = {}
    governed_request = document.get("governed_request", {})
    if not isinstance(governed_request, dict):
        governed_request = {}

    return {
        "controls_failed": len(_string_list(machine.get("controls_failed", []))),
        "missing_evidence": len(_string_list(machine.get("missing_evidence", []))),
        "decision": str(machine.get("decision") or ""),
        "timestamp": str(governed_request.get("timestamp") or _artifact_timestamp(path)),
    }


def _artifact_gap_count(paths: list[Path]) -> int:
    gap_count = 0
    for path in paths:
        if not path.exists():
            gap_count += 1
            continue
        freshness_status, _ = _format_age_bucket(_artifact_timestamp(path))
        if freshness_status == "critical":
            gap_count += 1
    return gap_count


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


def _freshness_label(*, timestamp: str, evidence_mode: str = "", provenance: str = "") -> str:
    _, age_bucket = _format_age_bucket(timestamp)
    if provenance == "sample/demo":
        return "sample/demo evidence"
    if age_bucket == "stale":
        return "stale evidence"
    if str(evidence_mode).lower() == "live" and age_bucket == "fresh":
        return "live current evidence"
    if age_bucket in {"fresh", "aging"}:
        return "recent generated evidence"
    return "timestamp unavailable"


def _panel_provenance(*, source_kind: str, evidence_mode: str = "", live_expected: bool = False) -> tuple[str, str]:
    normalized = str(source_kind).strip().lower()
    if normalized in {"sample", "demo", "demo_fallback", "seedretrievalbackend"}:
        return "sample/demo", "sample/demo"
    if normalized in {"adapter", "keycloak_userinfo", "opa", "qdrant", "vault"}:
        return "adapter-derived", _freshness_label(timestamp=_iso_now(), evidence_mode=evidence_mode, provenance="adapter-derived")
    if normalized in {"runtime-generated", "generated"}:
        return "runtime-generated", _freshness_label(timestamp=_iso_now(), evidence_mode=evidence_mode, provenance="runtime-generated")
    if normalized in {"file", "file-backed"}:
        return "file-backed", _freshness_label(timestamp=_iso_now(), evidence_mode=evidence_mode, provenance="file-backed")
    if live_expected and str(evidence_mode).lower() != "live":
        return "sample/demo", "sample/demo evidence"
    return "file-backed", "recent generated evidence"


def _display_identity_source(identity_evidence: dict[str, Any]) -> str:
    source = str(identity_evidence.get("source", ""))
    live = bool(identity_evidence.get("live"))
    mapping = {
        "keycloak_userinfo": "Keycloak userinfo (live)",
        "demo_fallback": "Demo fallback identity",
        "missing_token": "Missing bearer token",
    }
    if source in mapping:
        return mapping[source]
    if live and source:
        return f"{source} (live)"
    return source or "Identity source unavailable"


def _display_policy_engine(policy_evidence: dict[str, Any]) -> str:
    engine = str(policy_evidence.get("engine", "")).strip().lower()
    if engine == "opa":
        return "OPA"
    if engine == "local":
        return "Runtime bundle (demo/local)"
    return engine.upper() if engine else "Policy engine unavailable"


def _display_retrieval_backend(retrieval_evidence: dict[str, Any]) -> str:
    backend = str(retrieval_evidence.get("backend", "")).strip()
    if not backend:
        return "Retrieval backend unavailable"
    if backend.lower() == "qdrant":
        return "Qdrant"
    if backend == "SeedRetrievalBackend":
        return "Seed retrieval (demo)"
    return backend


def _display_secret_backend(secret_evidence: dict[str, Any]) -> str:
    backend = str(secret_evidence.get("backend", "")).strip().lower()
    if backend == "vault":
        return "Vault"
    if backend == "unconfigured":
        return "Unconfigured"
    return backend.upper() if backend else "Secret backend unavailable"


def _panel_note(
    *,
    timestamp: str,
    evidence_mode: str,
    provenance: str,
    extra: str = "",
) -> str:
    note = f"Provenance: {provenance}; freshness: {_freshness_label(timestamp=timestamp, evidence_mode=evidence_mode, provenance=provenance)}."
    return f"{note} {extra}".strip()


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


def _derive_audit_records_from_events(events: list[dict[str, Any]], *, policy_source: str, policy_path: str) -> list[dict[str, Any]]:
    stage_map = {
        "identity.established": ("identity", "identity.established"),
        "policy.decision": ("policy", "policy.decision"),
        "retrieval.decision": ("retrieval", "retrieval.decision"),
        "secret.access": ("secret", "secret.access"),
        "tool.decision": ("tool_decision", "tool.decision"),
        "tool.execution_attempt": ("tool_execution", "tool.execution_attempt"),
        "launch_gate.evaluated": ("launch_gate", "launch_gate.summary"),
        "handoff.decision": ("handoff", "onyx.handoff"),
    }
    audit_records: list[dict[str, Any]] = []
    for event in events:
        event_type = str(event.get("event_type", ""))
        if event_type not in stage_map:
            continue
        payload = _payload(event)
        stage, action = stage_map[event_type]
        allow = payload.get("allow")
        outcome = "allow" if allow is True else "deny" if allow is False else str(payload.get("decision") or payload.get("status") or "recorded")
        audit_records.append(
            {
                "trace_id": str(event.get("trace_id", "")),
                "request_id": str(event.get("request_id", "")),
                "session_id": str(event.get("session_id", "")),
                "actor_id": str(payload.get("actor_id") or payload.get("sub") or payload.get("actor") or ""),
                "tenant_id": str(event.get("tenant_id", "") or payload.get("tenant_id", "")),
                "surface": str(payload.get("surface") or payload.get("requested_path") or payload.get("path") or ""),
                "requested_path": str(payload.get("requested_path") or payload.get("path") or ""),
                "timestamp": str(event.get("timestamp", "")),
                "stage": stage,
                "action": action,
                "outcome": outcome,
                "reason_codes": _reason_codes(event),
                "policy_source": str(payload.get("policy_source") or policy_source),
                "policy_path": str(payload.get("policy_path") or policy_path),
                "provenance": "adapter-derived",
            }
        )
    return audit_records


def _build_audit_dataset(
    *,
    audit_records: list[dict[str, Any]],
    events: list[dict[str, Any]],
    policy_source: str,
    policy_path: str,
) -> tuple[list[dict[str, Any]], str]:
    if audit_records:
        return audit_records, "runtime-generated"
    return _derive_audit_records_from_events(events, policy_source=policy_source, policy_path=policy_path), "adapter-derived"


def _flagship_denied_handoff(
    *,
    blocked_actions: list[dict[str, str]],
    denied_flow: dict[str, Any],
    trace_correlation: dict[str, Any],
    governed_flow_summary: dict[str, Any],
    policy_source: str,
    policy_path: str,
) -> dict[str, str]:
    primary = next((action for action in blocked_actions if action.get("kind") == "Blocked /launch/onyx handoff"), {})
    actor = primary.get("actor") or str(governed_flow_summary.get("actor_id", ""))
    tenant = primary.get("tenant") or str(governed_flow_summary.get("tenant_id", ""))
    trace_id = primary.get("trace_id") or str(governed_flow_summary.get("trace_id", "")) or str(trace_correlation.get("trace_id", ""))
    request_id = primary.get("request_id") or str(governed_flow_summary.get("request_id", ""))
    timestamp = primary.get("timestamp") or str(denied_flow.get("captured_at", ""))
    reason_code = primary.get("reason_code") or "policy.surface_role_denied:onyx.agents"
    return {
        "title": "Flagship denied Onyx handoff proof",
        "status": "critical",
        "reason_code": reason_code,
        "reason": _humanize_reason(reason_code),
        "surface": primary.get("surface") or "/launch/onyx -> /app/agents",
        "tenant": tenant or "tenant unavailable",
        "actor": actor or "actor unavailable",
        "trace_id": trace_id or "trace unavailable",
        "request_id": request_id or "request unavailable",
        "policy_source": primary.get("policy_source") or policy_source,
        "policy_path": primary.get("policy_path") or policy_path,
        "timestamp": timestamp or "timestamp unavailable",
        "href": primary.get("href") or _raw(INSPECTABLE_DENIED_FLOW),
        "bundle_href": _raw(INSPECTABLE_DENIED_FLOW),
        "detail": str(denied_flow.get("summary", "Denied /launch/onyx evidence bundle available.")),
    }


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
            "Live governed flow artifacts" if evidence_mode == "live" else "Recent generated demo/local governed artifacts",
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
            "group": str(section.get("group", "")),
            "group_label": str(section.get("group_label", "")),
        }
        for section in contract.get("sections", [])
        if section.get("id")
    }


def _upstream_components_by_classification(components: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(component.get("classification", "reference_only")) for component in components)


def _bool_label(value: bool) -> str:
    return "yes" if value else "no"


def _allow_deny_label(value: bool) -> str:
    return "ALLOW" if value else "DENY"


def _status_priority(status: str) -> int:
    return {"critical": 0, "warning": 1, "healthy": 2, "neutral": 3}.get(status, 4)


def _combine_statuses(*statuses: str) -> str:
    valid = [status for status in statuses if status]
    if not valid:
        return "neutral"
    return min(valid, key=_status_priority)


def _onyx_runtime_readiness_status(runtime_proof: dict[str, Any]) -> str:
    status = str(runtime_proof.get("reachability", {}).get("status", ""))
    return {
        "local_and_public_ready": "healthy",
        "local_ready_public_pending": "warning",
        "blocked_before_runtime": "warning",
        "public_visible_local_unhealthy": "critical",
        "runtime_unreachable": "critical",
    }.get(status, "warning")


def _onyx_runtime_continuity_status(runtime_proof: dict[str, Any]) -> str:
    status = str(runtime_proof.get("continuity", {}).get("status", ""))
    return {
        "path_activity_observed": "healthy",
        "runtime_activity_observed": "warning",
        "no_runtime_activity": "warning",
    }.get(status, "warning")


def _take_rows(rows: list[dict[str, str]], limit: int = 5) -> list[dict[str, str]]:
    return rows[:limit]


def _important_upstream_components(components: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    classification_rank = {
        "used_now": 0,
        "partially_used": 1,
        "optional_future": 2,
        "reference_only": 3,
    }
    path_rank = {
        "mandatory": 0,
        "supporting": 1,
        "optional": 2,
        "reference": 3,
    }
    prioritized = sorted(
        components,
        key=lambda component: (
            classification_rank.get(str(component.get("classification", "reference_only")), 9),
            path_rank.get(str(component.get("runtime_path_status", "reference")), 9),
            0 if bool(component.get("dashboard_visible")) else 1,
            str(component.get("component_name", "")),
        ),
    )
    return prioritized[:limit]


def _focus_artifacts(inventory: list[dict[str, str]], limit: int = 5) -> list[dict[str, str]]:
    ranked = sorted(
        inventory,
        key=lambda artifact: (
            0 if artifact.get("status") == "critical" else 1 if artifact.get("status") == "warning" else 2,
            0 if artifact.get("label") in {"Governed request feed", "Reviewer evidence bundle", "Launch readiness report"} else 1,
            artifact.get("label", ""),
        ),
    )
    return ranked[:limit]


def _governed_request_feed(
    feed: list[dict[str, Any]],
    summary: dict[str, Any],
) -> list[dict[str, Any]]:
    if feed:
        return feed

    fallback = dict(summary.get("governed_request", {}))
    if not fallback:
        return []

    fallback.setdefault("timestamp", str(summary.get("generated_at", "")))
    fallback.setdefault("trace_id", str(summary.get("trace_id", "")))
    fallback.setdefault("request_id", str(summary.get("request_id", "")))
    fallback.setdefault("session_id", str(summary.get("session_id", "")))
    fallback.setdefault("tenant_id", str(summary.get("tenant_id", "")))
    fallback.setdefault("actor_id", str(summary.get("actor_id", "")))
    fallback.setdefault("surface", str(summary.get("surface", "")))
    fallback.setdefault("requested_path", str(summary.get("requested_path", "")))
    fallback.setdefault("runtime_target", str(summary.get("runtime_target", "onyx")))
    fallback.setdefault("evidence_mode", str(summary.get("evidence_mode", "")))
    fallback.setdefault("policy_allow", bool(summary.get("policy", {}).get("allow")))
    fallback.setdefault("retrieval_allow", bool(summary.get("retrieval", {}).get("allow")))
    fallback.setdefault("secret_required", bool(summary.get("secret", {}).get("required")))
    fallback.setdefault("secret_satisfied", bool(summary.get("secret", {}).get("fetched")) or not bool(summary.get("secret", {}).get("required")))
    fallback.setdefault("handoff_allowed", bool(summary.get("handoff_allowed", summary.get("decision", False))))
    fallback.setdefault("reason_codes", _string_list(summary.get("reasons", [])))
    runtime_proof = dict(summary.get("runtime_proof", {}))
    runtime_proof_ref = str(runtime_proof.get("history_artifact") or runtime_proof.get("artifact") or "")
    artifact_refs = {"governed_flow_summary": "overlays/myStarterKit/artifacts/governed-flow-summary.json"}
    if runtime_proof_ref:
        artifact_refs["onyx_runtime_proof"] = runtime_proof_ref
    fallback.setdefault("artifact_refs", artifact_refs)
    if runtime_proof:
        fallback.setdefault("runtime_proof", runtime_proof)
    return [fallback]


def _governed_request_status(record: dict[str, Any]) -> str:
    return "healthy" if bool(record.get("handoff_allowed")) else "critical"


def _governed_request_rows(feed: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in feed:
        secret_required = bool(item.get("secret_required"))
        secret_satisfied = bool(item.get("secret_satisfied"))
        rows.append(
            {
                "timestamp": str(item.get("timestamp", "")),
                "question": str(item.get("question_preview", "Preview unavailable")),
                "tenant": str(item.get("tenant_id", "")),
                "actor_session": " / ".join(
                    value
                    for value in (str(item.get("actor_id", "")), str(item.get("session_id", "")))
                    if value
                ),
                "surface": str(item.get("surface") or item.get("requested_path") or ""),
                "mode": str(item.get("evidence_mode", "")),
                "identity": _allow_deny_label(bool(item.get("identity_authenticated", True))),
                "policy": _allow_deny_label(bool(item.get("policy_allow"))),
                "retrieval": _allow_deny_label(bool(item.get("retrieval_allow"))),
                "secret": (
                    "not required"
                    if not secret_required
                    else ("satisfied" if secret_satisfied else "missing")
                ),
                "handoff": _allow_deny_label(bool(item.get("handoff_allowed"))),
                "trace": str(item.get("trace_id", "")),
            }
        )
    return rows


def _governed_request_records(feed: list[dict[str, Any]]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for item in feed:
        reason_codes = _string_list(item.get("reason_codes", []))
        artifact_refs = item.get("artifact_refs", {})
        summary_href = ""
        if isinstance(artifact_refs, dict) and artifact_refs.get("governed_flow_summary"):
            summary_href = _raw(str(artifact_refs.get("governed_flow_summary")))
        detail = (
            f"Question preview: {str(item.get('question_preview', 'Preview unavailable'))}. "
            f"Handoff: {_allow_deny_label(bool(item.get('handoff_allowed')))}. "
            f"Reasons: {', '.join(reason_codes or ['policy.allow'])}. "
            f"Redacted: {_bool_label(bool(item.get('question_redacted')))}. "
            f"Sensitive patterns: {_bool_label(bool(item.get('contains_sensitive_patterns')))}."
        )
        records.append(
            _record(
                title=str(item.get("question_preview", "Preview unavailable")),
                meta=" | ".join(
                    value
                    for value in (
                        str(item.get("evidence_mode", "")),
                        str(item.get("tenant_id", "")),
                        str(item.get("surface") or item.get("requested_path") or ""),
                        str(item.get("trace_id", "")),
                    )
                    if value
                ),
                detail=detail,
                status=_governed_request_status(item),
                href=summary_href,
            )
        )
    return records


def _is_onyx_component(component: dict[str, Any]) -> bool:
    return str(component.get("component_name", "")).strip().lower() == "onyx" or str(component.get("upstream_path", "")).strip() == "upstream/onyx"


def _upstream_table_rows(
    components: list[dict[str, Any]],
    *,
    onyx_governed_entry_url: str = "",
    onyx_runtime_public_url: str = "",
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for component in components:
        signals = _string_list(component.get("governance_signals"))
        evidence = _string_list(component.get("evidence_artifacts"))
        source_ref = str(component.get("source_ref", "")).strip()
        source_commit = str(component.get("source_commit", "")).strip()
        source_pin = (
            f"{source_ref} @ {source_commit[:8]}"
            if source_ref and source_commit
            else (
                f"digest:{str(component.get('snapshot_fingerprint', '')).strip()[:12]}"
                if str(component.get("snapshot_fingerprint", "")).strip()
                else "Provenance not recorded"
            )
        )
        rows.append(
            {
                "component": str(component.get("component_name", "Component")),
                "classification": str(component.get("classification", "reference_only")),
                "path_status": str(component.get("runtime_path_status", "reference")),
                "decision": str(component.get("integration_decision", "reference_only")).replace("_", " "),
                "checkout": str(component.get("checkout_policy", "opt_in")).replace("_", "-"),
                "validated": str(component.get("last_validated", "")) or "Not recorded",
                "source_pin": source_pin,
                "location": str(component.get("runtime_location", "Runtime location not documented.")),
                "signal": signals[0] if signals else "No dedicated governance signal yet.",
                "evidence": evidence[0] if evidence else "No evidence artifact listed.",
                "live_surface": (
                    onyx_runtime_public_url or onyx_governed_entry_url or "Not published yet."
                    if _is_onyx_component(component)
                    else "Not exposed from this section."
                ),
                "dev": _bool_label(bool(component.get("enabled_in_dev"))),
                "prod_sim": _bool_label(bool(component.get("enabled_in_prod_sim"))),
            }
        )
    return rows


def _upstream_record_items(
    components: list[dict[str, Any]],
    *,
    onyx_governed_entry_url: str = "",
    onyx_runtime_public_url: str = "",
    onyx_runtime_local_url: str = "",
) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for component in components:
        detail_parts = [
            f"Checkout: {str(component.get('checkout_policy', 'opt_in')).replace('_', '-')}.",
            f"Last validated: {str(component.get('last_validated', '') or 'Not recorded')}.",
            (
                f"Source pin: {str(component.get('source_ref', '')).strip()} @ "
                f"{str(component.get('source_commit', '')).strip()[:8]}."
                if str(component.get("source_ref", "")).strip() and str(component.get("source_commit", "")).strip()
                else (
                    f"Snapshot digest: {str(component.get('snapshot_fingerprint', '')).strip()[:16]}."
                    if str(component.get("snapshot_fingerprint", "")).strip()
                    else "Source pin: not recorded yet."
                )
            ),
            f"Provenance mode: {str(component.get('provenance_mode', 'content_fingerprint')).replace('_', ' ')}.",
            f"Why it stays: {str(component.get('necessity_rationale', '')).strip()}",
            f"Current gap: {str(component.get('missing_integration_depth', '')).strip()}",
            f"Removal impact: {str(component.get('removal_impact', '')).strip()}",
        ]
        href = ""
        if _is_onyx_component(component):
            if onyx_governed_entry_url:
                detail_parts.append(f"Governed entry: {onyx_governed_entry_url}.")
                href = onyx_governed_entry_url
            if onyx_runtime_public_url:
                detail_parts.append(f"Live runtime URL: {onyx_runtime_public_url}.")
            if onyx_runtime_local_url:
                detail_parts.append(f"Local runtime URL: {onyx_runtime_local_url}.")
        items.append(
            _record(
                title=str(component.get("component_name", "Component")),
                meta=" | ".join(
                    (
                        str(component.get("classification", "reference_only")),
                        str(component.get("runtime_path_status", "reference")),
                        str(component.get("integration_decision", "reference_only")).replace("_", " "),
                        str(component.get("recommended_action", "review classification")),
                    )
                ),
                detail=" ".join(part for part in detail_parts if part),
                status={
                    "used_now": "healthy",
                    "partially_used": "warning",
                    "optional_future": "neutral",
                    "reference_only": "neutral",
                }.get(str(component.get("classification", "")), "neutral"),
                href=href,
            )
        )
    return items


def _upstream_audit_cards(inventory: dict[str, Any]) -> list[dict[str, str]]:
    components = list(inventory.get("components", []))
    counts = inventory.get("classification_counts", {})
    audit = inventory.get("audit", {})
    runtime_path_counts = audit.get("runtime_path_counts", {})
    covered = len(audit.get("classified_paths", []))
    total_paths = len(audit.get("component_paths_in_repo", []))
    coverage_status = "healthy" if audit.get("inventory_covers_all_upstreams") else "critical"
    dashboard_visible_count = int(audit.get("dashboard_visible_count", 0))
    pinned_source_count = int(audit.get("pinned_source_count", 0))
    total_source_count = len(components)
    fingerprinted_source_count = int(audit.get("fingerprinted_source_count", 0))
    default_checkout_count = len(audit.get("default_checkout_paths", []))
    opt_in_checkout_count = len(audit.get("opt_in_checkout_paths", []))
    platform_only_count = len(audit.get("platform_only_components", []))

    return [
        _card("Used now", str(counts.get("used_now", 0)), "healthy", "Components that currently strengthen the repo's real runtime or evidence path.", "#upstream-posture"),
        _card("Partially used", str(counts.get("partially_used", 0)), "neutral", "Components present through containers, policy, adapters, or bridge configs without full mandatory-path proof.", "#upstream-posture"),
        _card("Optional / future", str(counts.get("optional_future", 0)), "neutral", "Components intentionally kept out of active architecture claims until they produce reviewer-visible outcomes.", "#upstream-posture"),
        _card("Reference only", str(counts.get("reference_only", 0)), "neutral", "Vendored snapshots retained for compatibility or implementation reference only.", "#upstream-posture"),
        _card("Inventory coverage", f"{covered} / {total_paths or len(components)}", coverage_status, "Every vendored upstream path should be classified exactly once.", "#upstream-posture"),
        _card("Pinned sources", f"{pinned_source_count} / {total_source_count}", "healthy" if audit.get("source_pins_complete") else "warning", "Pinned upstream refs and commits recorded in the lock manifest.", "#upstream-posture"),
        _card("Snapshot provenance", f"{fingerprinted_source_count} / {total_source_count}", "healthy" if audit.get("fingerprints_complete") else "warning", "Content fingerprints recorded for vendored upstream snapshots even when upstream git pins are unavailable.", "#upstream-posture"),
        _card("Default checkout", str(default_checkout_count), "healthy", "Vendored upstreams expected to stay in the default checkout group.", "#upstream-posture"),
        _card("Opt-in checkout", str(opt_in_checkout_count), "neutral", "Optional and reference-only upstreams explicitly treated as opt-in.", "#upstream-posture"),
        _card("Platform-only", str(platform_only_count), "neutral", "Components intentionally kept off the mandatory governed path until deeper proof exists.", "#upstream-posture"),
        _card("Dashboard-visible signals", str(dashboard_visible_count), "healthy" if dashboard_visible_count else "warning", "Components with a reviewer-visible posture, evidence, or activity signal on the homepage.", "#upstream-posture"),
        _card("Mandatory path components", str(runtime_path_counts.get("mandatory", 0)), "healthy", "Components the repo currently treats as part of the proved runtime or evidence path.", "#upstream-posture"),
        _card("Supporting path components", str(runtime_path_counts.get("supporting", 0)), "neutral", "Components that strengthen the platform but are not yet proven as mandatory request-path dependencies.", "#upstream-posture"),
    ]


def _build_artifact_inventory(root: Path) -> tuple[list[dict[str, str]], Counter[str]]:
    reviewer_path = reviewer_bundle_relative_path(root)
    launch_path = launch_report_relative_path(root)
    ingestion_path = dashboard_ingestion_relative_path(root)
    governed_request_feed_path = governed_request_feed_relative_path(root)

    artifact_specs = [
        ("Reviewer evidence bundle", reviewer_path, "review"),
        ("Launch readiness report", launch_path, "launch gate"),
        ("Dashboard ingestion feed", ingestion_path, "telemetry export"),
        ("Governed request feed", governed_request_feed_path, "request telemetry"),
        ("Governed telemetry sample", SAMPLE_EVENTS, "telemetry feed"),
        ("Governed audit records", AUDIT_RECORDS_PATH, "audit trail"),
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
        provenance = "sample/demo" if relative_path in {SAMPLE_EVENTS, PROD_SIM_GOVERNED_FLOW, PROD_SIM_LAUNCH_GATE, PROD_SIM_EVENTS} else "file-backed"
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
                "freshness": _freshness_label(timestamp=timestamp, provenance=provenance),
                "integrity": integrity_detail,
                "last_updated": timestamp or "timestamp unavailable",
                "path": relative_path,
                "href": _raw(relative_path),
                "provenance": provenance,
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
    governed_request_feed = _governed_request_feed(
        load_latest_governed_request_feed(resolved_root),
        governed_flow_summary,
    )
    onyx_runtime_proof = load_latest_onyx_runtime_proof(resolved_root)
    identity_evidence = load_latest_identity_evidence(resolved_root)
    policy_evidence = load_latest_policy_evidence(resolved_root)
    retrieval_evidence = load_latest_retrieval_evidence(resolved_root)
    secret_evidence = load_latest_secret_evidence(resolved_root)
    trace_correlation = load_latest_trace_correlation(resolved_root)
    audit_records = load_latest_audit_records(resolved_root)
    policy_bundle = load_runtime_policy_bundle(resolved_root)
    policy = policy_bundle.document
    reviewer = load_reviewer_bundle(resolved_root)
    launch_summary = build_launch_gate_summary(resolved_root)
    evidence_summary = build_evidence_pack_summary(resolved_root)
    eval_summaries = load_eval_summaries(resolved_root)
    latest_eval = eval_summaries[-1] if eval_summaries else {}
    activity_snapshot = build_activity_snapshot(resolved_root, limit=12)
    stack_health = build_stack_health_snapshot(resolved_root)
    artifact_inventory, artifact_counts = _build_artifact_inventory(resolved_root)
    denied_flow = read_json(resolved_root / INSPECTABLE_DENIED_FLOW)
    allowed_flow = read_json(resolved_root / INSPECTABLE_ALLOWED_FLOW)

    policy_path = policy_bundle.relative_path
    policy_source = "overlay" if policy_bundle.source == "overlay" else "fallback"
    policy_href = _raw(policy_path)
    reviewer_href = _raw(reviewer_bundle_relative_path(resolved_root))
    launch_report_href = _raw(launch_report_relative_path(resolved_root))
    ingestion_href = _raw(dashboard_ingestion_relative_path(resolved_root))
    governed_request_feed_href = _raw(governed_request_feed_relative_path(resolved_root))

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
    latest_governed_flow_href = _raw("overlays/myStarterKit/artifacts/governed-flow-summary.json")
    dependency_status = governed_flow_summary.get("dependency_status", {})
    dependency_status = dependency_status if isinstance(dependency_status, dict) else {}
    identity_dependency = dict(dependency_status.get("identity", {}))
    policy_dependency = dict(dependency_status.get("policy", {}))
    retrieval_dependency = dict(dependency_status.get("retrieval", {}))
    secret_dependency = dict(dependency_status.get("secret", {}))
    trace_dependency = dict(dependency_status.get("trace", {}))
    identity_live = bool(identity_evidence.get("live"))
    policy_engine = str(policy_evidence.get("engine", policy_source))
    retrieval_live_backend = bool(retrieval_evidence.get("live_backend"))
    secret_required = bool(secret_evidence.get("required"))
    secret_fetched = bool(secret_evidence.get("fetched"))
    trace_complete = bool(trace_correlation.get("complete"))
    session_linkage = dict(trace_correlation.get("session_linkage", {}))
    audit_linkage = dict(trace_correlation.get("audit_linkage", {}))
    trace_missing_identifiers = _string_list(trace_correlation.get("missing_identifiers", []))
    latest_handoff_allowed = bool(governed_flow_summary.get("handoff_allowed", governed_flow_summary.get("decision", False)))
    latest_reason_codes = _string_list(governed_flow_summary.get("reasons", []))
    latest_handoff_reason = latest_reason_codes[0] if latest_reason_codes else "policy.allow"
    latest_missing_evidence = _string_list(governed_flow_summary.get("launch_gate", {}).get("missing_evidence", []))
    latest_governed_launch_gate = dict(governed_flow_summary.get("launch_gate", {}))
    latest_governed_verdict = _normalize_launch_verdict(str(latest_governed_launch_gate.get("decision", "")))
    latest_governed_posture = _readiness_display(latest_governed_verdict) if latest_governed_verdict else "Unavailable"
    identity_authenticated = bool(identity_dependency.get("authenticated", identity_evidence.get("authenticated")))
    identity_live_step = bool(identity_dependency.get("live", identity_live))
    policy_allowed = bool(policy_dependency.get("allow", policy_evidence.get("allow")))
    policy_engine_step = str(policy_dependency.get("engine", policy_engine))
    retrieval_allowed = bool(retrieval_dependency.get("allow", retrieval_evidence.get("allow")))
    retrieval_live_step = bool(retrieval_dependency.get("live_backend", retrieval_live_backend))
    secret_required_step = bool(secret_dependency.get("mandatory", secret_required))
    secret_fetched_step = bool(secret_dependency.get("fetched", secret_fetched))
    trace_complete_step = bool(trace_dependency.get("complete", trace_complete))
    identity_timestamp = str(identity_evidence.get("timestamp") or identity_evidence.get("captured_at") or governed_flow_summary.get("generated_at") or "")
    policy_timestamp = str(policy_evidence.get("timestamp") or policy_evidence.get("captured_at") or governed_flow_summary.get("generated_at") or "")
    retrieval_timestamp = str(retrieval_evidence.get("timestamp") or retrieval_evidence.get("captured_at") or governed_flow_summary.get("generated_at") or "")
    secret_timestamp = str(secret_evidence.get("timestamp") or secret_evidence.get("captured_at") or governed_flow_summary.get("generated_at") or "")
    blocked_attacks = reviewer.get("blocked_attack_summary", {}).get("blocked_attacks", [])

    blocked_actions = _build_blocked_actions(
        events,
        event_feed_path=event_feed_path,
        policy_path=policy_path,
        policy_source=policy_source,
        denied_flow=denied_flow,
    )
    governed_request_rows = _take_rows(_governed_request_rows(governed_request_feed), 5)
    governed_request_records = _governed_request_records(governed_request_feed[:5])
    live_request_count = sum(1 for item in governed_request_feed if str(item.get("evidence_mode", "")).lower() == "live")
    denied_request_count = sum(1 for item in governed_request_feed if not bool(item.get("handoff_allowed")))
    redacted_request_count = sum(1 for item in governed_request_feed if bool(item.get("question_redacted")))
    audit_dataset, audit_provenance = _build_audit_dataset(
        audit_records=audit_records,
        events=events,
        policy_source=policy_source,
        policy_path=policy_path,
    )
    if not audit_linkage:
        observed_stages = sorted({str(record.get("stage", "")) for record in audit_dataset if str(record.get("stage", ""))})
        expected_stages = ["identity", "policy", "retrieval", "secret", "tool_decision", "launch_gate", "handoff"]
        if tool_attempts or tool_decisions:
            expected_stages.append("tool_execution")
        missing_stages = [stage for stage in expected_stages if stage not in observed_stages]
        audit_linkage = {
            "record_count": len(audit_dataset),
            "trace_bound": latest_trace_id in {str(record.get("trace_id", "")) for record in audit_dataset},
            "required_stages": expected_stages,
            "observed_stages": observed_stages,
            "missing_stages": missing_stages,
            "complete": bool(audit_dataset) and not missing_stages,
        }
    flagship_denied = _flagship_denied_handoff(
        blocked_actions=blocked_actions,
        denied_flow=denied_flow,
        trace_correlation=trace_correlation,
        governed_flow_summary=governed_flow_summary,
        policy_source=policy_source,
        policy_path=policy_path,
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
        for event in audit_dataset
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
    baseline_posture_display = _readiness_display(launch_summary["status"])
    runtime_generated_demo = (not live_evidence_mode) and event_feed_path == "overlays/myStarterKit/artifacts/events.jsonl"
    mode_banner_label = (
        "LIVE GOVERNED MODE"
        if live_evidence_mode
        else ("GOVERNED DEMO MODE" if runtime_generated_demo else "DEMO FALLBACK MODE")
    )
    mode_banner_status = (
        "healthy"
        if live_evidence_mode
        else ("neutral" if latest_handoff_allowed and latest_governed_verdict == "go" else "warning")
    )
    mode_banner_display_label = (
        "Live governed mode: real checks and live proof"
        if live_evidence_mode
        else (
            "Governed demo mode: local run, not live dependency proof"
            if runtime_generated_demo
            else "Demo fallback mode: sample review proof"
        )
    )
    mode_banner_display_summary = (
        "This page is using real live checks. If key checks or proof are missing, the system should block access instead of guessing."
        if live_evidence_mode
        else (
            "This page is showing a governed local run in demo mode. It is useful for control review and UX validation, but it does not prove the full live dependency chain."
            if runtime_generated_demo
            else "This page is showing sample or fallback proof. It is useful for review, but it is not claiming a fresh governed live run."
        )
    )
    latest_governed_decision_display = _allow_deny_display(latest_handoff_allowed)
    live_readiness_display = "Proven on current trace" if live_evidence_mode else "Not yet proven"
    demo_gap_details: list[str] = []
    if not live_evidence_mode:
        if not identity_live_step:
            demo_gap_details.append("identity stayed on demo or fallback resolution")
        if policy_engine_step.lower() != "opa":
            demo_gap_details.append("policy stayed on the local evaluator")
        if not retrieval_live_step:
            demo_gap_details.append("the live retrieval path was not exercised")
        if not secret_required_step:
            demo_gap_details.append("conditional live secret access was not exercised on this trace")
        elif not secret_fetched_step:
            demo_gap_details.append("required secret access did not complete")
    top_baseline_issue = str(failing_controls[0].get("summary", "")).strip() if failing_controls else ""

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
    latest_request = governed_request_feed[0] if governed_request_feed else {}
    latest_request_reason = ", ".join(_string_list(latest_request.get("reason_codes", []))[:2] or ["policy.allow"])
    latest_request_href = ""
    if isinstance(latest_request.get("artifact_refs"), dict) and latest_request["artifact_refs"].get("governed_flow_summary"):
        latest_request_href = _raw(str(latest_request["artifact_refs"]["governed_flow_summary"]))
    latest_requested_path = str(latest_request.get("requested_path") or governed_flow_summary.get("requested_path") or "/app")
    summary_runtime_proof = governed_flow_summary.get("runtime_proof", {})
    summary_runtime_proof = dict(summary_runtime_proof) if isinstance(summary_runtime_proof, dict) else {}
    if not onyx_runtime_proof:
        onyx_runtime_proof = dict(summary_runtime_proof)
    if not onyx_runtime_proof:
        onyx_runtime_proof = build_onyx_runtime_proof(
            resolved_root,
            requested_path=latest_requested_path,
            trace_id=latest_trace_id,
            session_id=latest_session_id,
            activity_snapshot=activity_snapshot,
        )
    onyx_runtime_proof.setdefault("artifact", "overlays/myStarterKit/artifacts/onyx-runtime-proof.json")
    onyx_runtime_proof.setdefault("requested_path", latest_requested_path)
    runtime_proof_href = _raw(str(onyx_runtime_proof.get("history_artifact") or onyx_runtime_proof.get("artifact") or "overlays/myStarterKit/artifacts/onyx-runtime-proof.json"))
    runtime_continuity = dict(onyx_runtime_proof.get("continuity", {}))
    runtime_readiness = dict(onyx_runtime_proof.get("reachability", {}))
    runtime_latest_activity = dict(onyx_runtime_proof.get("matched_activity") or onyx_runtime_proof.get("latest_activity") or {})
    runtime_continuity_label = str(runtime_continuity.get("label", "No runtime proof yet"))
    runtime_readiness_label = str(runtime_readiness.get("label", "Not checked yet"))
    runtime_latest_activity_summary = str(runtime_latest_activity.get("summary", "")) or "No recent Onyx runtime activity captured yet."
    runtime_continuity_status = _onyx_runtime_continuity_status(onyx_runtime_proof)
    runtime_readiness_status = _onyx_runtime_readiness_status(onyx_runtime_proof)
    runtime_proof_status = _combine_statuses(runtime_continuity_status, runtime_readiness_status)
    onyx_governed_entry_url = _launch_handoff_url(latest_requested_path)
    onyx_live_workspace_url = _launch_handoff_path(latest_requested_path, mode="live", view="embedded")
    onyx_runtime_public_url = str(runtime_readiness.get("public_url", "")).strip() or _public_service_url(3010, latest_requested_path)
    onyx_runtime_local_url = str(runtime_readiness.get("local_url", "")).strip() or f"http://127.0.0.1:3010{latest_requested_path}"
    runtime_activity_href = (
        f"/api/control-plane/onyx-activity?path={quote(latest_requested_path, safe='/?=&')}"
        f"&trace_id={quote(latest_trace_id, safe='')}"
        f"&session_id={quote(latest_session_id, safe='')}"
    )
    top_failing_control = failing_controls[0] if failing_controls else {}
    governed_flow_generated_at = str(governed_flow_summary.get("generated_at", ""))
    latest_request_timestamp = str(latest_request.get("timestamp") or governed_flow_generated_at or "")
    trace_timestamp = str(trace_correlation.get("timestamp") or trace_correlation.get("generated_at") or governed_flow_generated_at or "")
    handoff_timestamp = latest_request_timestamp or governed_flow_generated_at
    launch_report_timestamp = str(launch_summary.get("generated_at") or readiness_panel["generated_at"] or "")
    evidence_summary_timestamp = str(
        evidence_summary.get("generated_at")
        or reviewer.get("generated_at")
        or artifact_inventory[0]["last_updated"]
        or ""
    )
    latest_allowed_request = next((item for item in governed_request_feed if bool(item.get("handoff_allowed"))), {})
    last_good_run_timestamp = str(latest_allowed_request.get("timestamp") or "")
    last_good_run_trace = str(latest_allowed_request.get("trace_id") or "")
    history_root = resolved_root / "overlays/myStarterKit/artifacts/governed-request-history"
    recent_window = governed_request_feed[:5]
    previous_window = governed_request_feed[5:10]
    recent_blocked_handoffs = sum(1 for item in recent_window if not bool(item.get("handoff_allowed")))
    previous_blocked_handoffs = (
        sum(1 for item in previous_window if not bool(item.get("handoff_allowed")))
        if previous_window
        else None
    )
    previous_trace_id = ""
    previous_trace_timestamp = ""
    previous_launch_gate_metrics: dict[str, Any] = {}
    for item in governed_request_feed:
        candidate_trace_id = str(item.get("trace_id") or "")
        if not candidate_trace_id or candidate_trace_id == latest_trace_id:
            continue
        candidate_launch_gate = history_root / candidate_trace_id / "launch-gate-result.json"
        if not candidate_launch_gate.exists():
            continue
        previous_trace_id = candidate_trace_id
        previous_launch_gate_metrics = _launch_gate_run_metrics(candidate_launch_gate)
        previous_trace_timestamp = str(previous_launch_gate_metrics.get("timestamp") or _artifact_timestamp(candidate_launch_gate))
        break
    core_artifact_names = [
        "governed-flow-summary.json",
        "identity-evidence.json",
        "policy-evidence.json",
        "retrieval-evidence.json",
        "secret-evidence.json",
        "trace-correlation.json",
        "launch-gate-result.json",
    ]
    current_core_artifact_paths = [(resolved_root / "overlays/myStarterKit/artifacts" / name) for name in core_artifact_names]
    current_core_proof_gap_count = _artifact_gap_count(current_core_artifact_paths)
    previous_core_proof_gap_count = (
        _artifact_gap_count([(history_root / previous_trace_id / name) for name in core_artifact_names])
        if previous_trace_id
        else None
    )
    blocked_handoff_trend = _trend_summary(
        recent_blocked_handoffs,
        previous_blocked_handoffs,
        lower_is_better=True,
        context="window",
        baseline_label="5-request window",
        worse_status="critical",
    )
    failing_controls_trend = _trend_summary(
        len(failing_controls),
        (
            int(previous_launch_gate_metrics.get("controls_failed", 0))
            if previous_launch_gate_metrics
            else None
        ),
        lower_is_better=True,
        context="run",
        baseline_label="launch run",
        worse_status="critical",
    )
    proof_gap_trend = _trend_summary(
        current_core_proof_gap_count,
        previous_core_proof_gap_count,
        lower_is_better=True,
        context="run",
        baseline_label="runtime proof set",
        worse_status="warning",
    )
    last_good_run_trend = _trend_summary(
        sum(1 for item in recent_window if bool(item.get("handoff_allowed"))),
        (
            sum(1 for item in previous_window if bool(item.get("handoff_allowed")))
            if previous_window
            else None
        ),
        lower_is_better=False,
        context="window",
        baseline_label="5-request window",
    )
    if last_good_run_timestamp:
        last_good_run_status, _ = _format_age_bucket(last_good_run_timestamp)
        last_good_run_value = _timestamp_display(last_good_run_timestamp)
        last_good_run_detail = (
            f"Latest approved trace {last_good_run_trace}."
            if last_good_run_trace
            else "Latest approved governed handoff in the request feed."
        )
        last_good_run_badges = _timestamp_badges(
            timestamp=last_good_run_timestamp,
            evidence_mode=str(latest_allowed_request.get("evidence_mode", "")),
            provenance="runtime-generated",
            label="Approved",
        )
    else:
        last_good_run_status = "warning"
        last_good_run_value = "No recent approved run"
        last_good_run_detail = "The recent request feed does not show an allowed governed handoff yet."
        last_good_run_badges = []
    mode_banner = {
        "label": mode_banner_label,
        "status": mode_banner_status,
        "display_label": mode_banner_display_label,
        "summary": (
            "Strict live dependency participation is expected. Missing identity, policy, retrieval, secret, trace, or launch-gate evidence should fail closed."
            if live_evidence_mode
            else mode_banner_display_summary
        ),
        "display_summary": mode_banner_display_summary,
        "detail": (
            f"Current evidence source: {event_feed_path}. Latest governed decision is {_allow_deny_label(latest_handoff_allowed)}. "
            f"Latest governed run posture: {latest_governed_posture}. Baseline repo posture: {launch_summary['status'].upper()}."
        ),
        "display_detail": (
            f"Source: {event_feed_path}. Latest governed decision: {latest_governed_decision_display}. "
            f"Latest governed run: {latest_governed_posture}. Baseline repo posture: {baseline_posture_display}."
        ),
        "chips": [
            {
                "label": "Evidence mode",
                "value": "LIVE" if live_evidence_mode else ("GOVERNED DEMO" if runtime_generated_demo else "DEMO FALLBACK"),
                "display_label": "Proof source",
                "display_value": "Live evidence" if live_evidence_mode else ("Governed local artifacts" if runtime_generated_demo else "Sample or fallback artifacts"),
            },
            {
                "label": "Latest governed decision",
                "value": _allow_deny_label(latest_handoff_allowed),
                "display_label": "Latest governed decision",
                "display_value": latest_governed_decision_display,
            },
            {
                "label": "Latest governed run",
                "value": latest_governed_posture,
                "display_label": "Latest run posture",
                "display_value": latest_governed_posture,
            },
            {
                "label": "Live proof",
                "value": "proven" if live_evidence_mode else "not_proven",
                "display_label": "Live readiness",
                "display_value": live_readiness_display,
            },
            {
                "label": "Baseline posture",
                "value": baseline_posture_display,
                "display_label": "Baseline posture",
                "display_value": baseline_posture_display,
            },
            {
                "label": "Latest trace",
                "value": latest_trace_id or "missing",
                "display_label": "Latest technical trace",
                "display_value": latest_trace_id or "missing",
            },
        ],
        "consequences": [
            (
                "Live mode means Keycloak-compatible identity, OPA, retrieval, conditional secrets, trace continuity, and launch-gate evidence should participate under one trace or the handoff fails closed."
                if live_evidence_mode
                else (
                    "This page is showing a governed local run with fresh repo artifacts, not a strict live dependency chain."
                    if runtime_generated_demo
                    else "This page is showing sample or fallback governed evidence rather than a fresh live run."
                )
            ),
            (
                "Treat live launch claims as credible only when the same trace shows complete evidence and a governed Onyx handoff outcome."
                if live_evidence_mode
                else (
                    f"For this trace, {', '.join(demo_gap_details[:-1])}, and {demo_gap_details[-1]}."
                    if len(demo_gap_details) > 1
                    else (
                        f"For this trace, {demo_gap_details[0]}."
                        if demo_gap_details
                        else "For this trace, live dependency participation is not yet proven."
                    )
                )
            ),
            (
                f"The latest governed run passed, but the broader repo baseline is still {baseline_posture_display.lower()} because {top_baseline_issue}"
                if (not live_evidence_mode and latest_governed_verdict == "go" and launch_summary["status"] != "go" and top_baseline_issue)
                else (
                    "Use this mode to inspect UX and proof shape, but not to claim the full fail-closed live path was exercised."
                    if not live_evidence_mode
                    else ""
                )
            ),
        ],
    }
    mode_banner["consequences"] = [item for item in mode_banner["consequences"] if item]
    evidence_freshness_value = f"{artifact_counts['fresh']} fresh"
    if artifact_counts["aging"]:
        evidence_freshness_value += f" / {artifact_counts['aging']} aging"
    if artifact_counts["stale"] or artifact_counts["missing"]:
        evidence_freshness_value += f" / {artifact_counts['stale']} stale / {artifact_counts['missing']} missing"
    latest_request_status = "healthy" if latest_request and bool(latest_request.get("handoff_allowed")) else ("critical" if latest_request else "warning")
    latest_request_fields = [
        {"label": "Result", "value": _allow_deny_label(bool(latest_request.get("handoff_allowed", False))) if latest_request else "No request"},
        {"label": "Evidence mode", "value": str(latest_request.get("evidence_mode", "")) or "unavailable"},
        {"label": "Tenant", "value": str(latest_request.get("tenant_id", "")) or "unavailable"},
        {"label": "Trace ID", "value": str(latest_request.get("trace_id", "")) or "unavailable"},
        {"label": "Timestamp", "value": str(latest_request.get("timestamp", "")) or "unavailable"},
    ]
    identity_step_status = (
        "healthy"
        if identity_authenticated and (identity_live_step or not live_evidence_mode)
        else ("warning" if identity_authenticated else "critical")
    )
    policy_step_status = (
        "healthy"
        if policy_allowed and (policy_engine_step.strip().lower() == "opa" or not live_evidence_mode)
        else ("warning" if policy_allowed else "critical")
    )
    retrieval_step_status = (
        "healthy"
        if retrieval_allowed and (retrieval_live_step or not live_evidence_mode)
        else ("warning" if retrieval_allowed else "critical")
    )
    secret_step_status = "neutral" if not secret_required_step else ("healthy" if secret_fetched_step else "critical")
    trace_step_status = "healthy" if trace_complete_step else "critical"
    handoff_step_status = "healthy" if latest_handoff_allowed else "critical"
    pipeline_steps = [
        {
            "id": "identity",
            "label": "Identity",
            "value": (
                "Live identity passed"
                if identity_authenticated and identity_live_step
                else ("Identity passed" if identity_authenticated else "Identity missing")
            ),
            "detail": str(identity_dependency.get("source") or identity_evidence.get("source") or "Identity evidence unavailable"),
            "status": identity_step_status,
            "href": "#identity-session",
            "meta_badges": _timestamp_badges(
                timestamp=identity_timestamp,
                evidence_mode="live" if live_evidence_mode else "demo",
                provenance="runtime-generated",
            ),
        },
        {
            "id": "policy",
            "label": "Policy",
            "value": (
                f"{policy_engine_step.upper()} allowed"
                if policy_allowed and policy_engine_step
                else ("Allowed" if policy_allowed else "Blocked")
            ),
            "detail": "Current rule evaluation before AI access.",
            "status": policy_step_status,
            "href": "#policy-enforcement",
            "meta_badges": _timestamp_badges(
                timestamp=policy_timestamp,
                evidence_mode="live" if live_evidence_mode else "demo",
                provenance="runtime-generated",
            ),
        },
        {
            "id": "retrieval",
            "label": "Retrieval",
            "value": (
                "Allowed on live source"
                if retrieval_allowed and retrieval_live_step
                else ("Allowed on reviewed source" if retrieval_allowed else "Blocked")
            ),
            "detail": "Checks which information sources the AI can read.",
            "status": retrieval_step_status,
            "href": "#retrieval-boundaries",
            "meta_badges": _timestamp_badges(
                timestamp=retrieval_timestamp,
                evidence_mode="live" if live_evidence_mode else "demo",
                provenance="runtime-generated",
            ),
        },
        {
            "id": "secret",
            "label": "Secret",
            "value": (
                "No secret needed"
                if not secret_required_step
                else ("Required secret fetched" if secret_fetched_step else "Required secret missing")
            ),
            "detail": "Protected credentials stay governed before runtime access.",
            "status": secret_step_status,
            "href": "#secret-access",
            "meta_badges": _timestamp_badges(
                timestamp=secret_timestamp,
                evidence_mode="live" if live_evidence_mode else "demo",
                provenance="runtime-generated",
            ),
        },
        {
            "id": "trace",
            "label": "Trace",
            "value": "Trace complete" if trace_complete_step else "Trace incomplete",
            "detail": (
                "Cross-step proof is tied together under one trace."
                if trace_complete_step
                else (
                    f"Missing proof: {', '.join(latest_missing_evidence)}."
                    if latest_missing_evidence
                    else "Cross-step proof is incomplete."
                )
            ),
            "status": trace_step_status,
            "href": "#trace-correlation",
            "meta_badges": _timestamp_badges(
                timestamp=trace_timestamp,
                evidence_mode="live" if live_evidence_mode else "demo",
                provenance="runtime-generated",
            ),
        },
        {
            "id": "handoff",
            "label": "Handoff",
            "value": _allow_deny_display(latest_handoff_allowed),
            "detail": (
                "Access reached the AI runtime through the governed path."
                if latest_handoff_allowed
                else "Access stayed blocked because the full governed path did not pass."
            ),
            "status": handoff_step_status,
            "href": "#entry-points",
            "meta_badges": _timestamp_badges(
                timestamp=handoff_timestamp,
                evidence_mode="live" if live_evidence_mode else "demo",
                provenance="runtime-generated",
            ),
        },
    ]
    pipeline_statuses = [str(step["status"]) for step in pipeline_steps]
    if "critical" in pipeline_statuses:
        pipeline_status = "critical"
    elif "warning" in pipeline_statuses:
        pipeline_status = "warning"
    elif "neutral" in pipeline_statuses:
        pipeline_status = "neutral"
    else:
        pipeline_status = "healthy"
    pipeline_summary = (
        "The latest governed path cleared the mandatory checks and allowed AI access."
        if latest_handoff_allowed
        else (
            f"The latest governed path was blocked because required proof is missing: {', '.join(latest_missing_evidence)}."
            if latest_missing_evidence
            else f"The latest governed path was blocked with reason {_humanize_reason(latest_request_reason)}."
        )
    )
    incident_status = "critical" if not latest_handoff_allowed else _status_from_launch(launch_summary["status"])
    if incident_status == "healthy" and (
        artifact_counts["stale"]
        or artifact_counts["missing"]
        or not live_evidence_mode
    ):
        incident_status = "warning"
    incident_main_blocker = (
        f"Missing proof: {', '.join(latest_missing_evidence)}"
        if latest_missing_evidence
        else (
            str(top_failing_control.get("summary", ""))
            or _humanize_reason(latest_request_reason)
        )
    )
    incident_visible = True
    if incident_status == "healthy":
        incident_eyebrow = "Why the page is green right now"
        incident_title = "Current checks look healthy"
        incident_summary = "The latest governed request was allowed, the launch check is GO, and the key proof is current enough to trust."
        incident_detail = (
            f"Latest approved trace {latest_trace_id or 'available'} shows a governed handoff with "
            f"{artifact_counts['stale']} stale and {artifact_counts['missing']} missing proof item(s)."
        )
        incident_signal_value = "Approved handoff with current proof"
        incident_actions = [
            _link("Open latest technical summary", latest_governed_flow_href, "Inspect the latest governed-flow summary behind the healthy state.", "healthy"),
            _link("Open approved example", _raw(INSPECTABLE_ALLOWED_FLOW), "Open the strongest approved governed handoff proof path.", "healthy"),
            _link("Open safety check", "#launch-gate", "Jump straight to the launch and readiness evidence.", "healthy"),
        ]
    elif not latest_handoff_allowed:
        incident_eyebrow = "Why the page is red right now"
        incident_title = "AI access is blocked right now"
        incident_summary = "The latest governed request did not reach the AI runtime because a mandatory proof or control failed."
        incident_detail = incident_main_blocker
        incident_signal_value = incident_main_blocker or "No primary blocker recorded"
        incident_actions = [
            _link("Open latest technical summary", latest_governed_flow_href, "Inspect the latest governed-flow summary tied to this blocked state.", "critical"),
            _link("Open safety check", "#launch-gate", "Jump straight to the launch and readiness evidence.", "critical"),
            _link("Open blocked example", flagship_denied["bundle_href"], "Open the strongest blocked-access proof path.", "critical"),
        ]
    else:
        incident_eyebrow = "Why the page is not green yet"
        incident_title = "Current safety checks still need attention"
        incident_summary = "The latest handoff passed, but the posture still has at least one issue that keeps this page out of a fully healthy state."
        incident_detail = incident_main_blocker
        incident_signal_value = incident_main_blocker or "No primary blocker recorded"
        incident_actions = [
            _link("Open latest technical summary", latest_governed_flow_href, "Inspect the latest governed-flow summary behind this warning state.", "warning"),
            _link("Open safety check", "#launch-gate", "Jump straight to the launch and readiness evidence.", "warning"),
            _link("Open approved example", _raw(INSPECTABLE_ALLOWED_FLOW), "Open the latest approved governed handoff proof path.", "healthy"),
        ]
    dashboard_generated_at = _iso_now()
    approved_example_timestamp = last_good_run_timestamp or handoff_timestamp
    approved_example = {
        "eyebrow": "Approved example",
        "title": "Governed handoff allowed",
        "detail": "Use this example when you need to show the system allowing AI access only after the governed checks align.",
        "status": "healthy",
        "href": _raw(INSPECTABLE_ALLOWED_FLOW),
        "fields": [
            {"label": "Decision", "value": "Allowed"},
            {"label": "Latest approved trace", "value": last_good_run_trace or "Unavailable"},
            {"label": "Tenant", "value": str(latest_allowed_request.get("tenant_id", "")) or "Unavailable"},
            {"label": "Checked", "value": _timestamp_display(approved_example_timestamp) if approved_example_timestamp else "Unavailable"},
        ],
        "meta_badges": _timestamp_badges(
            timestamp=approved_example_timestamp,
            evidence_mode=str(latest_allowed_request.get("evidence_mode", "")) or ("live" if live_evidence_mode else "demo"),
            provenance="runtime-generated",
            label="Approved",
        ),
    }
    blocked_example = {
        "eyebrow": "Blocked example",
        "title": "Governed handoff blocked",
        "detail": "Use this example when you need to show the system refusing unsafe or unsupported AI access.",
        "status": "critical",
        "href": flagship_denied["bundle_href"],
        "fields": [
            {"label": "Decision", "value": "Blocked"},
            {"label": "Why it stopped", "value": flagship_denied["reason"]},
            {"label": "Trace", "value": flagship_denied["trace_id"]},
            {"label": "Tenant", "value": flagship_denied["tenant"]},
        ],
        "meta_badges": _timestamp_badges(
            timestamp=flagship_denied["timestamp"],
            evidence_mode="live" if live_evidence_mode else "demo",
            provenance="runtime-generated",
            label="Blocked",
        ),
    }
    if not latest_handoff_allowed:
        next_action_change = blocked_handoff_trend
        next_action = {
            "eyebrow": "Recommended next action",
            "title": "Review the blocker",
            "summary": "Start with the latest governed-flow summary, confirm the main reason for the deny, and decide whether the block should remain in place.",
            "status": "critical",
            "primary_action": _link("Open blocker summary", latest_governed_flow_href, "Open the latest governed-flow summary behind the blocked handoff.", "critical"),
            "secondary_actions": [
                _link("Open blocked example", flagship_denied["bundle_href"], "Open the strongest blocked-access proof path.", "critical"),
                _link("Open safety check", "#launch-gate", "Jump straight to the launch and readiness evidence.", "warning"),
            ],
            "steps": [
                f"Confirm the main signal: {incident_signal_value}.",
                "Check whether the deny matches the expected policy outcome.",
                "Decide whether the missing proof needs remediation or the user should stay blocked.",
            ],
            "change": next_action_change,
        }
    elif artifact_counts["stale"] or artifact_counts["missing"]:
        next_action_change = proof_gap_trend
        next_action = {
            "eyebrow": "Recommended next action",
            "title": "Refresh the proof",
            "summary": "The current posture has stale or missing evidence. Generate a fresh governed flow before you rely on this state.",
            "status": "warning",
            "primary_action": _link("Create fresh technical proof", _dashboard_url("/api/control-plane/governed-flow"), "Run a new governed flow to refresh runtime artifacts.", "warning"),
            "secondary_actions": [
                _link("Open proof quality", "#evidence-integrity", "Jump straight to the evidence freshness section.", "warning"),
                _link("Open latest summary", latest_governed_flow_href, "Open the latest technical request summary.", "neutral"),
            ],
            "steps": [
                f"Current stale / missing count: {artifact_counts['stale']} / {artifact_counts['missing']}.",
                "Run a fresh governed flow to regenerate runtime proof.",
                "Re-check the proof-quality section after the refresh completes.",
            ],
            "change": next_action_change,
        }
    elif incident_status == "warning":
        next_action_change = failing_controls_trend
        next_action = {
            "eyebrow": "Recommended next action",
            "title": "Harden the remaining config gap",
            "summary": "The latest handoff passed, but one remaining config or readiness issue still keeps the page out of a fully healthy state.",
            "status": "warning",
            "primary_action": _link("Open safety check", "#launch-gate", "Jump straight to the launch and readiness evidence.", "warning"),
            "secondary_actions": [
                _link("Open latest summary", latest_governed_flow_href, "Open the latest technical request summary.", "neutral"),
                _link("Open approved example", _raw(INSPECTABLE_ALLOWED_FLOW), "Open the strongest approved governed handoff proof path.", "healthy"),
            ],
            "steps": [
                f"Focus on the main signal: {incident_signal_value}.",
                "Use the launch-gate section to confirm what still prevents a green state.",
                "After hardening the gap, rerun the governed flow and check whether the banner turns green.",
            ],
            "change": next_action_change,
        }
    else:
        next_action_change = last_good_run_trend
        next_action = {
            "eyebrow": "Recommended next action",
            "title": "Inspect the approved flow",
            "summary": "The posture is healthy enough to walk through the approved example and confirm the proof story from top to bottom.",
            "status": "healthy",
            "primary_action": _link("Open approved example", _raw(INSPECTABLE_ALLOWED_FLOW), "Open the strongest approved governed handoff proof path.", "healthy"),
            "secondary_actions": [
                _link("Open latest summary", latest_governed_flow_href, "Open the latest technical request summary.", "neutral"),
                _link("Open safety check", "#launch-gate", "Jump straight to the launch and readiness evidence.", "healthy"),
            ],
            "steps": [
                "Use the posture banner, risk strip, and governed path to explain why the current state is healthy.",
                "Walk through the approved example to confirm the same story in raw proof.",
                "Switch on presentation mode when you want a lighter external-facing walkthrough.",
            ],
            "change": next_action_change,
        }
    flagship_proof = _spotlight(
        eyebrow="Flagship proof",
        title="Denied /launch/onyx handoff",
        detail=(
            f"{flagship_denied['reason']}. "
            f"Surface {flagship_denied['surface']} stayed blocked with policy {flagship_denied['policy_source']} / {flagship_denied['policy_path']}."
        ),
        status="critical",
        href=flagship_denied["bundle_href"],
        fields=[
            {"label": "Reason code", "value": flagship_denied["reason_code"]},
            {"label": "Tenant", "value": flagship_denied["tenant"]},
            {"label": "Actor", "value": flagship_denied["actor"]},
            {"label": "Trace ID", "value": flagship_denied["trace_id"]},
        ],
        display_eyebrow="Flagship blocked-access proof",
        display_title="Example of the system blocking unsafe or unauthorized access",
        display_detail="Clearest proof that the system can refuse AI access when the rules or proof do not support it.",
        display_fields=[
            {"label": "Why it was blocked", "value": flagship_denied["reason"]},
            {"label": "Customer or tenant", "value": flagship_denied["tenant"]},
            {"label": "Person or actor", "value": flagship_denied["actor"]},
            {"label": "Technical trace", "value": flagship_denied["trace_id"]},
        ],
        meta_badges=_timestamp_badges(
            timestamp=flagship_denied["timestamp"],
            evidence_mode="live" if live_evidence_mode else "demo",
            provenance="runtime-generated",
            label="Blocked",
        ),
    )
    presentation_summary = {
        "eyebrow": "Share summary",
        "title": incident_title,
        "summary": incident_summary,
        "status": incident_status,
        "bullets": [
            f"Current safety state: {_readiness_display(launch_summary['status'])}.",
            f"Latest access decision: {_allow_deny_display(latest_handoff_allowed)}.",
            f"Proof freshness: {evidence_freshness_value}.",
            f"Latest technical trace: {latest_trace_id or 'Missing'}.",
            f"Next recommended action: {next_action['title']}.",
        ],
        "export_text": "\n".join(
            [
                incident_title,
                incident_summary,
                f"- Current safety state: {_readiness_display(launch_summary['status'])}.",
                f"- Latest access decision: {_allow_deny_display(latest_handoff_allowed)}.",
                f"- Proof freshness: {evidence_freshness_value}.",
                f"- Latest technical trace: {latest_trace_id or 'Missing'}.",
                f"- Next recommended action: {next_action['title']}.",
                f"- Snapshot generated: {_timestamp_display(dashboard_generated_at)}.",
            ]
        ),
    }
    runtime_summary = {
        "eyebrow": "Live runtime",
        "title": "Onyx runtime status",
        "summary": (
            "The governed runtime looks ready for the current workspace path."
            if runtime_proof_status == "healthy"
            else (
                "The governed runtime is partially visible, but continuity or reachability still needs attention."
                if runtime_proof_status == "warning"
                else "The governed runtime still needs attention before you treat the live path as healthy."
            )
        ),
        "detail": (
            f"Workspace path {latest_requested_path}. Reachability: {runtime_readiness_label}. "
            f"Continuity: {runtime_continuity_label}. Latest runtime signal: {runtime_latest_activity_summary}"
        ),
        "status": runtime_proof_status,
        "meta_badges": _timestamp_badges(
            timestamp=handoff_timestamp,
            evidence_mode="live" if live_evidence_mode else "demo",
            provenance="runtime-generated",
            label="Runtime proof",
        ),
        "items": [
            _card("Reachability", runtime_readiness_label, runtime_readiness_status, str(runtime_readiness.get("detail", ""))),
            _card("Continuity", runtime_continuity_label, runtime_continuity_status, str(runtime_continuity.get("detail", ""))),
            _card("Current path", latest_requested_path, "neutral", "The runtime path the current governed workspace targets."),
            _card("Public runtime", onyx_runtime_public_url, "neutral", "Publicly visible runtime target when the Onyx surface is reachable."),
        ],
        "actions": [
            _link(
                "Open live workspace",
                onyx_live_workspace_url,
                "Open the governed embedded workspace for the current Onyx path.",
                runtime_proof_status,
                display_label="Open live workspace",
                display_description="Jump into the governed Onyx workspace with the current path and live controls.",
            ),
            _link(
                "Open runtime proof",
                runtime_proof_href,
                "Inspect the runtime reachability and continuity proof for the latest governed handoff.",
                runtime_proof_status,
                display_label="Open runtime proof",
                display_description="Inspect the technical runtime proof tied to the latest governed handoff.",
            ),
            _link(
                "Open runtime activity",
                runtime_activity_href,
                "Inspect the current Onyx activity feed filtered to this governed workspace path.",
                "neutral",
                display_label="Open runtime activity",
                display_description="Inspect current Onyx activity filtered to the governed workspace path.",
            ),
        ],
    }
    command_center = {
        "cards": [
            _card(
                "Readiness",
                launch_summary["status"].upper(),
                _status_from_launch(launch_summary["status"]),
                "Launch posture for the governed runtime right now.",
                "#launch-gate",
                id="readiness",
                display_label="Can it be used safely now?",
                display_value=f"{_readiness_display(launch_summary['status'])} · {launch_summary['readiness_score']}/100",
                display_detail=f"Launch verdict: {launch_summary['status'].upper()}. {launch_summary['control_coverage']} checks are passing.",
                meta_badges=_timestamp_badges(
                    timestamp=launch_report_timestamp,
                    evidence_mode="live" if live_evidence_mode else "demo",
                    provenance="file-backed",
                ),
            ),
            _card(
                "Latest handoff",
                _allow_deny_label(latest_handoff_allowed),
                "healthy" if latest_handoff_allowed else "critical",
                f"Most recent governed handoff reason: {latest_handoff_reason}.",
                "#entry-points",
                id="latest_handoff",
                display_label="Latest access decision",
                display_value=_allow_deny_display(latest_handoff_allowed),
                display_detail="Shows whether the latest checked handoff into the AI system was allowed or blocked.",
                meta_badges=_timestamp_badges(
                    timestamp=handoff_timestamp,
                    evidence_mode="live" if live_evidence_mode else "demo",
                    provenance="runtime-generated",
                ),
            ),
            _card(
                "Top failing control",
                str(top_failing_control.get("control", "none")).replace("_", " "),
                "critical" if top_failing_control else "healthy",
                str(top_failing_control.get("summary", "No failing controls are currently listed.")),
                "#launch-gate",
                id="top_failing_control",
                display_label="Most important issue",
                display_value=str(top_failing_control.get("control", "none")).replace("_", " ").title() if top_failing_control else "No major issue listed",
                display_detail=(
                    f"{len(failing_controls)} important issue{'s' if len(failing_controls) != 1 else ''} still affect safe use."
                    if top_failing_control
                    else "No failing control is listed in the current launch report."
                ),
                meta_badges=_timestamp_badges(
                    timestamp=launch_report_timestamp,
                    evidence_mode="live" if live_evidence_mode else "demo",
                    provenance="file-backed",
                    label="From report",
                ),
            ),
            _card(
                "Evidence freshness",
                evidence_freshness_value,
                "healthy" if artifact_counts["stale"] == 0 and artifact_counts["missing"] == 0 else "warning",
                f"Stale: {artifact_counts['stale']}. Missing: {artifact_counts['missing']}.",
                "#evidence-integrity",
                id="evidence_freshness",
                display_label="How up to date the proof is",
                display_value=evidence_freshness_value,
                display_detail=f"{artifact_counts['stale']} stale and {artifact_counts['missing']} missing proof item(s).",
                meta_badges=_timestamp_badges(
                    timestamp=evidence_summary_timestamp,
                    evidence_mode="live" if live_evidence_mode else "demo",
                    provenance="file-backed",
                ),
            ),
        ],
        "latest_request": _spotlight(
            eyebrow="Newest governed request",
            title=str(latest_request.get("question_preview", "No governed request recorded yet")),
            detail=(
                f"Reasons: {latest_request_reason}. "
                f"Redacted: {_bool_label(bool(latest_request.get('question_redacted')))}. "
                f"Sensitive patterns: {_bool_label(bool(latest_request.get('contains_sensitive_patterns')))}."
                if latest_request
                else "Run a governed flow to surface a sanitized request preview, decision state, and trace-linked evidence."
            ),
            status=latest_request_status,
            href=latest_request_href,
            fields=latest_request_fields,
            display_eyebrow="Latest checked request",
            display_title=str(latest_request.get("question_preview", "No recent checked request yet")),
            display_detail=(
                "Latest safe preview of a checked request. The full raw prompt is not shown here."
                if latest_request
                else "Run a new checked flow to show the latest request, decision, and proof links."
            ),
            display_fields=[
                {"label": "Decision", "value": _allow_deny_display(bool(latest_request.get("handoff_allowed", False))) if latest_request else "No request"},
                {"label": "Proof mode", "value": "Live" if str(latest_request.get("evidence_mode", "")).lower() == "live" else (str(latest_request.get("evidence_mode", "")).title() or "Unavailable")},
                {"label": "Customer or tenant", "value": str(latest_request.get("tenant_id", "")) or "Unavailable"},
                {"label": "Time", "value": str(latest_request.get("timestamp", "")) or "Unavailable"},
            ],
            meta_badges=_timestamp_badges(
                timestamp=latest_request_timestamp,
                evidence_mode=str(latest_request.get("evidence_mode", "")),
                provenance="runtime-generated",
            ),
        ),
        "flagship_proof": flagship_proof,
        "risk_strip": {
            "eyebrow": "Current risk strip",
            "title": "Four signals to watch",
            "detail": "These four signals tell you fastest whether the system needs review right now.",
            "items": [
                _card(
                    "Blocked handoffs",
                    str(recent_blocked_handoffs),
                    "critical" if recent_blocked_handoffs else ("warning" if denied_request_count else "healthy"),
                    f"Blocked handoffs in the latest {len(recent_window) or 1} checked request(s).",
                    "#blocked-actions",
                    trend=blocked_handoff_trend,
                    meta_badges=[
                        {"label": "Retained feed", "value": f"{denied_request_count} blocked total"},
                    ],
                ),
                _card(
                    "Failing controls",
                    str(len(failing_controls)),
                    "critical" if failing_controls else "healthy",
                    "Launch or readiness checks still not fully passing.",
                    "#launch-gate",
                    trend=failing_controls_trend,
                    meta_badges=(
                        _timestamp_badges(
                            timestamp=previous_trace_timestamp,
                            evidence_mode="live" if live_evidence_mode else "demo",
                            provenance="runtime-generated",
                            label="Previous run",
                        )
                        if previous_trace_timestamp
                        else []
                    ),
                ),
                _card(
                    "Stale / missing proof",
                    f"{artifact_counts['stale']} / {artifact_counts['missing']}",
                    "warning" if artifact_counts["stale"] or artifact_counts["missing"] else "healthy",
                    "Current stale and missing counts across the reviewer-visible proof set.",
                    "#evidence-integrity",
                    trend=proof_gap_trend,
                    meta_badges=[
                        {"label": "Core runtime proof", "value": f"{current_core_proof_gap_count} stale or missing", "status": "warning" if current_core_proof_gap_count else "healthy"},
                    ],
                ),
                _card(
                    "Last good run",
                    last_good_run_value,
                    last_good_run_status,
                    last_good_run_detail,
                    "#governed-requests",
                    meta_badges=last_good_run_badges,
                    trend=last_good_run_trend,
                ),
            ],
        },
        "incident_banner": {
            "visible": incident_visible,
            "status": incident_status,
            "eyebrow": incident_eyebrow,
            "title": incident_title,
            "summary": incident_summary,
            "detail": incident_detail,
            "facts": [
                {"label": "Readiness", "value": _readiness_display(launch_summary["status"])},
                {"label": "Latest access decision", "value": _allow_deny_display(latest_handoff_allowed)},
                {"label": "Main signal", "value": incident_signal_value},
                {"label": "Latest trace", "value": latest_trace_id or "Missing"},
                {"label": "Proof mode", "value": "Live evidence" if live_evidence_mode else "Demo or local evidence"},
            ],
            "actions": incident_actions,
        },
        "next_action": next_action,
        "walkthrough": [
            _link("Start with posture", "#overview", "Jump to the plain-language state summary first.", "neutral", display_label="Start with posture", display_description="Open the main overview before you drill into examples or technical proof."),
            _link("Show blocked example", flagship_denied["bundle_href"], "Open the clearest proof of the system refusing an unsafe or unauthorized handoff.", "critical", display_label="Show blocked example", display_description="Walk through the strongest blocked-access example when you need to explain why the system says no."),
            _link("Show approved example", _raw(INSPECTABLE_ALLOWED_FLOW), "Open the governed handoff example where the checks passed end to end.", "healthy", display_label="Show approved example", display_description="Use the approved example to show what a healthy governed flow looks like."),
            _link("Open technical proof", latest_governed_flow_href or "#audit-replay", "Inspect the newest governed-flow summary and trace-linked proof trail.", "neutral", display_label="Open technical proof", display_description="Use the latest technical summary when someone needs the raw proof behind the story."),
        ],
        "example_compare": {
            "eyebrow": "Compare outcomes",
            "title": "Approved and blocked examples side by side",
            "detail": "Use the two examples together to explain what changes between a safe governed handoff and a blocked one.",
            "approved": approved_example,
            "blocked": blocked_example,
            "contrasts": [
                {
                    "label": "Decision",
                    "approved": "Allowed after the governed checks lined up.",
                    "blocked": "Blocked before the AI runtime handoff.",
                },
                {
                    "label": "Main reason",
                    "approved": "Identity, policy, retrieval, secret, and trace checks aligned under one governed path.",
                    "blocked": incident_main_blocker or flagship_denied["reason"],
                },
                {
                    "label": "Best way to use it",
                    "approved": "Show what healthy governed access looks like.",
                    "blocked": "Show why the system refuses unsafe or unsupported access.",
                },
            ],
        },
        "freshness_bar": {
            "title": "Current proof",
            "items": [
                {"label": "Updated", "value": _timestamp_display(dashboard_generated_at), "status": "healthy"},
                {
                    "label": "Proof freshness",
                    "value": evidence_freshness_value,
                    "status": "healthy" if artifact_counts["stale"] == 0 and artifact_counts["missing"] == 0 else "warning",
                },
                {"label": "Latest trace", "value": latest_trace_id or "Missing", "status": "healthy" if latest_trace_id else "critical"},
                {"label": "Mode", "value": "Live evidence" if live_evidence_mode else "Demo or local evidence", "status": "healthy" if live_evidence_mode else "warning"},
            ],
        },
        "presentation_summary": presentation_summary,
        "runtime_summary": runtime_summary,
        "proof_pipeline": {
            "title": "Latest governed path",
            "detail": "Follow the latest request through the checks that must line up before AI access is allowed.",
            "summary": pipeline_summary,
            "status": pipeline_status,
            "summary_href": latest_governed_flow_href,
            "trace_id": latest_trace_id,
            "mode": "live" if live_evidence_mode else "demo",
            "mode_label": "Live proof" if live_evidence_mode else "Demo or local proof",
            "meta_badges": _timestamp_badges(
                timestamp=handoff_timestamp,
                evidence_mode="live" if live_evidence_mode else "demo",
                provenance="runtime-generated",
            ),
            "steps": pipeline_steps,
        },
        "actions": [
            _link("Inspect pass flow", _raw(INSPECTABLE_ALLOWED_FLOW), "Reviewer-ready allowed governed handoff proof.", "healthy", display_label="See approved example", display_description="Open a full example where the checks passed and access was allowed."),
            _link("Inspect deny flow", _raw(INSPECTABLE_DENIED_FLOW), "Reviewer-ready denied governed handoff proof.", "critical", display_label="See blocked example", display_description="Open a full example where the checks failed and access was blocked."),
            _link("Generate fresh governed flow", _dashboard_url("/api/control-plane/governed-flow"), "Refresh runtime-generated governed artifacts through the control-plane API.", "neutral", display_label="Create a fresh checked example", display_description="Run the system again to produce new technical proof and updated results."),
        ],
    }
    audience_paths = [
        {
            "title": "Plain-language review",
            "status": "healthy",
            "detail": "Start here for the simple safety story: what happened, what was stopped, what proof exists, and whether it looks safe to use now.",
            "links": [
                _link("Big picture", "#overview", "Start with the clearest explanation of the current safety state.", "neutral"),
                _link("Recent requests", "#governed-requests", "See the latest checked requests using safe previews.", "neutral"),
                _link("Safety check", "#launch-gate", "See whether the system is ready, partly ready, or not ready.", "neutral"),
                _link("Proof quality", "#evidence-integrity", "See whether the proof is current, complete, and reliable.", "neutral"),
            ],
        },
        {
            "title": "Technical details",
            "status": "neutral",
            "detail": "Use these sections when you need the technical story underneath the plain-language summary: rules, traces, evidence, and raw artifacts.",
            "links": [
                _link("Who is trying to use it", "#identity-session", "Identity, session, and access-boundary detail.", "neutral"),
                _link("Rules being applied", "#policy-enforcement", "Detailed rule decisions, engines, and reason codes.", "neutral"),
                _link("What happened and how we review it", "#audit-replay", "Audit coverage, replay evidence, and raw records.", "neutral"),
                _link("Recent activity", "#live-log-title", "Recent technical events and alerts from the running system.", "neutral"),
            ],
        },
    ]

    quick_answers = [
        {
            "question": "What is protected?",
            "answer": f"{len(surfaces)} governed surfaces, {len(tenants)} tenants, {len(retrieval_sources)} retrieval sources, {len(all_tools)} governed tools, and Onyx behind governed handoffs.",
            "detail": "Identity, policy, retrieval, tools, audit, and launch controls are modeled on the homepage.",
            "href": "#asset-coverage",
            "status": "healthy",
            "display_question": "What is this page watching?",
            "display_answer": f"{len(surfaces)} product surfaces, {len(tenants)} tenant spaces, {len(retrieval_sources)} data sources, and {len(all_tools)} AI actions are under review.",
            "display_detail": "This tells you what parts of the system are actively being checked.",
        },
        {
            "question": "What was blocked?",
            "answer": f"{len(blocked_actions)} recent governed interventions are visible, including retrieval, tool, confirmation, and runtime handoff outcomes.",
            "detail": "The denied /launch/onyx handoff is promoted as a flagship proof path with trace, request, actor, tenant, and policy context.",
            "href": "#blocked-actions",
            "status": "critical" if blocked_actions else "healthy",
            "display_question": "What did the system stop?",
            "display_answer": f"{len(blocked_actions)} recent requests or actions were stopped or held back for review.",
            "display_detail": "This includes blocked AI access, blocked data access, blocked actions, and approval-required steps.",
        },
        {
            "question": "Why was it blocked?",
            "answer": _top_reason(policy_reason_counts),
            "detail": "Reason codes are surfaced with policy source, policy path, surface, and trace identifiers.",
            "href": "#policy-enforcement",
            "status": "warning" if policy_reason_counts else "neutral",
            "display_question": "Why did the system stop it?",
            "display_answer": _humanize_reason(policy_reason_counts.most_common(1)[0][0]) if policy_reason_counts else "No main block reason recorded",
            "display_detail": "Detailed reason codes and raw technical evidence are available lower on the page.",
        },
        {
            "question": "What evidence exists?",
            "answer": f"{len(artifact_inventory) - artifact_counts['missing']} artifacts are present across reviewer bundles, governed traces, launch reports, and dashboard exports.",
            "detail": "Every critical section includes drill-through links to raw evidence.",
            "href": "#evidence-integrity",
            "status": "healthy" if artifact_counts["missing"] == 0 else "warning",
            "display_question": "What proof do we have?",
            "display_answer": f"{len(artifact_inventory) - artifact_counts['missing']} proof items are present for review.",
            "display_detail": "You can open raw evidence, technical artifacts, and detailed reports from the links below each section.",
        },
        {
            "question": "Is the system launch-ready?",
            "answer": f"{launch_summary['status'].upper()} with readiness score {launch_summary['readiness_score']}.",
            "detail": f"{len(failing_controls)} controls still need attention and {len(residual_risks)} residual risks remain visible to reviewers.",
            "href": "#launch-gate",
            "status": _status_from_launch(launch_summary["status"]),
            "display_question": "Can this system be used safely now?",
            "display_answer": f"{_readiness_display(launch_summary['status'])}: {launch_summary['readiness_score']}/100",
            "display_detail": f"There {'is' if len(failing_controls) == 1 else 'are'} {len(failing_controls)} important issue{'s' if len(failing_controls) != 1 else ''} to fix and {len(residual_risks)} remaining risk{'s' if len(residual_risks) != 1 else ''} to watch.",
        },
    ]

    reading_guide = {
        "title": "How to read this dashboard",
        "intro": "Start with the summary cards and the two spotlight panels. Open the lower sections only when you need the technical proof.",
        "statuses": [
            {"status": "healthy", "label": "Good", "detail": "The available proof supports the current claim."},
            {"status": "warning", "label": "Needs attention", "detail": "Something important is incomplete, aging, or limited."},
            {"status": "critical", "label": "Serious issue", "detail": "A blocker or important failure is visible."},
        ],
        "questions": [
            {
                "question": str(item.get("display_question", item["question"])),
                "answer": str(item.get("display_answer", item["answer"])),
                "detail": str(item.get("display_detail", item["detail"])),
                "href": item["href"],
                "status": item["status"],
            }
            for item in quick_answers
        ],
        "technical_note": "Need the engineering proof? Open the lower technical sections or the raw evidence links.",
    }

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
            "type": "links",
            "title": "Fast proof links",
            "items": [
                _link("Blocked access proof", flagship_denied["bundle_href"], "Open the strongest blocked-access example without repeating the full proof card here.", "critical", display_label="Blocked access example", display_description="Open the clearest example showing the system refusing access."),
                _link("Allowed governed flow proof", _raw(INSPECTABLE_ALLOWED_FLOW), "Open the strongest approved-access example from the governed path.", "healthy", display_label="Approved access example", display_description="Open the clearest example showing access being allowed after the checks passed."),
                _link("Launch-gate no-go proof", _raw(INSPECTABLE_TRACE_DOWNGRADE), "Open the example where missing proof or an incomplete process made the system not ready.", "warning", display_label="Not-ready example", display_description="Open the example where the safety check stopped use."),
            ],
        },
        {
            "type": "cards",
            "title": "What this homepage proves",
            "items": [
                _card("Protected now", f"{len(surfaces)} surfaces / {len(tenants)} tenants / {len(all_tools)} tools", "healthy", "The repo shows what is under governance without pretending every vendored component is equally active.", "#asset-coverage", display_label="What the system is watching", display_detail="Shows the main product surfaces, customer spaces, and AI actions currently under protection."),
                _card("Classification discipline", f"{upstream_counts['used_now']} active / {upstream_counts['partially_used']} supporting", "healthy" if upstream_audit.get("inventory_covers_all_upstreams") else "critical", "Mandatory, supporting, optional, and reference-only upstream claims stay explicit.", "#upstream-posture", display_label="Connected systems in use", display_detail="Shows which connected components are actively part of the proven path today."),
            ][:2],
        },
        {
            "type": "links",
            "title": "Helpful links",
            "items": [
                _link("Reviewer evidence bundle", reviewer_href, "Reviewer-ready proof pack for blocked actions, auditability, and launch posture.", "healthy", display_label="Full proof bundle", display_description="Open the bundled evidence pack for reviewers."),
                _link("Reviewer fast path", _raw("docs/reviewer-fast-path.md"), "Shortest proof path through pass, deny, and launch-gate no-go evidence.", "neutral", display_label="How to review this quickly", display_description="Open the shortest path through the main proof points."),
                _link("Dashboard visual proof", _raw("docs/dashboard-visual-proof.md"), "Fast reviewer cues for the top command summary and flagship evidence.", "neutral", display_label="Visual guide", display_description="Open a simple guide to the most important cues on the page."),
            ],
        },
    ]

    blocked_rows = _take_rows([
        {
            "kind": action["kind"],
            "reason": action["reason_code"],
            "surface": action["surface"] or "surface unavailable",
            "tenant": action["tenant"] or "tenant unavailable",
            "actor": action["actor"] or "actor unavailable",
            "trace": action["trace_id"] or "trace unavailable",
            "request": action["request_id"] or "request unavailable",
            "timestamp": action["timestamp"] or "timestamp unavailable",
        }
        for action in blocked_actions
    ], 5)

    identity_rows = _take_rows([
        {
            "surface": str(rule.get("surface", "")),
            "path": str(rule.get("path", "")),
            "query": json.dumps(rule.get("query", {}), sort_keys=True) if rule.get("query") else "none",
            "allowed_roles": ", ".join(_string_list(rule.get("allowed_roles"))),
        }
        for rule in surfaces
    ], 5)

    retrieval_rows = _take_rows([
        {
            "tenant": tenant_id,
            "source": source,
            "boundary": "tenant-scoped",
            "trust": ", ".join(policy.get("retrieval", {}).get("source_trust_labels", {}).get(source, [])) or "trust metadata required",
        }
        for tenant_id, sources in policy.get("retrieval", {}).get("tenant_allowed_sources", {}).items()
        for source in sources
    ], 5)

    tool_rows = [
        {"control": "Allowed tools", "value": str(len(allowed_tools)), "notes": ", ".join(allowed_tools) or "none"},
        {"control": "Forbidden tools", "value": str(len(forbidden_tools)), "notes": ", ".join(forbidden_tools) or "none"},
        {"control": "Confirmation required", "value": str(len(confirmation_required_tools)), "notes": ", ".join(confirmation_required_tools) or "none"},
        {"control": "MCP servers", "value": str(len(mcp_servers)), "notes": ", ".join(mcp_servers) or "none"},
        {"control": "Governed runtime", "value": "1", "notes": "Onyx is reached through governed surfaces."},
    ]

    audit_rows = _take_rows([
        {
            "event": str(event.get("action") or event.get("event_type", "audit.event")),
            "trace_id": str(event.get("trace_id", "")),
            "request_id": str(event.get("request_id", "")),
            "summary": " | ".join(
                value
                for value in (
                    str(event.get("stage", "")),
                    str(event.get("outcome", "")),
                    ", ".join(_string_list(event.get("reason_codes", []))),
                )
                if value
            )
            or str(event.get("event_payload", {}).get("action", "captured")),
        }
        for event in audit_dataset[:6]
    ], 5)

    asset_rows = _take_rows([
        {"asset_class": "Surfaces", "count": str(len(surfaces)), "governed_by": "surface path policy", "evidence": policy_path},
        {"asset_class": "Tenants", "count": str(len(tenants)), "governed_by": "identity tenant roles", "evidence": policy_path},
        {"asset_class": "Roles", "count": str(len(roles)), "governed_by": "identity role allowlists", "evidence": policy_path},
        {"asset_class": "Policy bundles", "count": "1", "governed_by": policy_source, "evidence": policy_path},
        {"asset_class": "Retrieval sources", "count": str(len(retrieval_sources)), "governed_by": "retrieval source policy", "evidence": policy_path},
        {"asset_class": "Tools", "count": str(len(all_tools)), "governed_by": "tool policy", "evidence": policy_path},
        {"asset_class": "MCP servers", "count": str(len(mcp_servers)), "governed_by": "integration inventory", "evidence": policy_path},
        {"asset_class": "Governed runtimes", "count": "1", "governed_by": "launch gate + onyx surface policy", "evidence": INSPECTABLE_ALLOWED_FLOW},
    ], 5)

    evidence_rows = [
        {
            "artifact": artifact["label"],
            "category": artifact["category"],
            "freshness": artifact["freshness"],
            "integrity": artifact["integrity"],
            "updated": artifact["last_updated"],
        }
        for artifact in _focus_artifacts(artifact_inventory, 5)
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
        _record(
            title="Latest Onyx runtime proof",
            meta=" | ".join(value for value in (runtime_readiness_label, runtime_continuity_label, latest_requested_path) if value),
            detail=f"{str(runtime_readiness.get('detail', 'Runtime reachability check unavailable.'))} Latest activity: {runtime_latest_activity_summary}",
            status=runtime_proof_status,
            href=runtime_proof_href,
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
            **section_contracts["governed-requests"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Request summary",
                    "items": [
                        _card("Recent requests", str(len(governed_request_feed)), "healthy" if governed_request_feed else "warning", "Recent governed requests available as sanitized previews rather than raw transcript replay.", governed_request_feed_href, display_label="Requests shown here", display_detail="These are safe previews, not raw prompts."),
                        _card("Denied requests", str(denied_request_count), "critical" if denied_request_count else "healthy", "Governed requests remain visible even when policy, retrieval, secrets, or launch-gate logic denied the handoff.", "#governed-requests", display_label="Requests that were blocked", display_detail="These requests were checked but not allowed through."),
                        _card("Redacted previews", str(redacted_request_count), "warning" if redacted_request_count else "healthy", "Dashboard-visible previews are redacted when likely secrets or sensitive patterns appear.", "#governed-requests", display_label="Requests hidden for safety", display_detail="Sensitive-looking text is redacted before it appears here."),
                        _card("Live-mode requests", str(live_request_count), "healthy" if live_request_count else "warning", "Live versus demo request telemetry stays explicit in the main reviewer view.", "#governed-requests", display_label="Requests using live proof", display_detail="Shows how many recent requests used the strict live path rather than demo proof."),
                    ],
                },
                {
                    "type": "records",
                    "title": "Recent requests with proof links",
                    "items": governed_request_records or [
                        _record("No governed requests recorded", "Reviewer-safe telemetry", "Run a governed flow to generate sanitized request previews and trace-linked evidence artifacts.", "warning")
                    ],
                },
                {
                    "type": "table",
                    "title": "Latest request slice",
                    "collapsed": True,
                    "summary": "Open latest request slice (top 5 rows)",
                    "columns": [
                        {"key": "timestamp", "label": "Timestamp"},
                        {"key": "question", "label": "Sanitized preview"},
                        {"key": "tenant", "label": "Tenant"},
                        {"key": "actor_session", "label": "Actor / session"},
                        {"key": "surface", "label": "Surface"},
                        {"key": "mode", "label": "Mode"},
                        {"key": "identity", "label": "Identity"},
                        {"key": "policy", "label": "Policy"},
                        {"key": "retrieval", "label": "Retrieval"},
                        {"key": "secret", "label": "Secret"},
                        {"key": "handoff", "label": "Handoff"},
                        {"key": "trace", "label": "Trace ID"},
                    ],
                    "rows": governed_request_rows,
                },
                {
                    "type": "links",
                    "title": "Request links",
                    "items": [
                        _link("Governed request feed artifact", governed_request_feed_href, "Reviewer-safe request telemetry with sanitized previews, reason codes, and trace-linked history references.", "healthy" if governed_request_feed else "warning", display_label="Technical request feed", display_description="Open the raw request feed used to build this summary."),
                        _link("Latest governed flow summary", _raw("overlays/myStarterKit/artifacts/governed-flow-summary.json"), "Latest governed request summary tying question preview, trace, allow or deny result, and dependency status together.", "healthy" if governed_flow_summary else "warning", display_label="Latest technical request summary", display_description="Open the technical summary for the latest checked request."),
                        _link("Question sanitization note", _raw("docs/evidence-model.md"), "Explains that request visibility uses sanitized previews and hashes, not raw transcript replay.", "neutral", display_label="Why the request text is shortened", display_description="Explains why this page shows safe previews instead of raw prompts."),
                    ],
                },
            ],
        },
        {
            **section_contracts["blocked-actions"],
            "blocks": [
                {
                    "type": "records",
                    "title": "Main blocked-access proof",
                    "items": [
                        _record(
                            flagship_denied["title"],
                            " | ".join(
                                (
                                    flagship_denied["surface"],
                                    flagship_denied["tenant"],
                                    flagship_denied["actor"],
                                    flagship_denied["trace_id"],
                                )
                            ),
                            (
                                f"Machine reason: {flagship_denied['reason_code']}. "
                                f"Human reason: {flagship_denied['reason']}. "
                                f"Request: {flagship_denied['request_id']}. "
                                f"Policy source/path: {flagship_denied['policy_source']} / {flagship_denied['policy_path']}. "
                                f"Timestamp: {flagship_denied['timestamp']}."
                            ),
                            "critical",
                            flagship_denied["bundle_href"],
                        )
                    ],
                },
                {
                    "type": "records",
                    "title": "Recent blocked or paused actions",
                    "items": [
                        _record(action["title"], action["meta"], action["detail"], action["status"], action["href"])
                        for action in blocked_actions[:4]
                    ] or [
                        _record("No recent blocked actions", "Governance posture", "No denies or confirmation-required actions are visible in the current dataset.", "healthy")
                    ],
                },
                {
                    "type": "table",
                    "title": "Latest blocked timeline",
                    "collapsed": True,
                    "summary": "Open blocked timeline sample (top 5 rows)",
                    "columns": [
                        {"key": "kind", "label": "Kind"},
                        {"key": "reason", "label": "Reason code"},
                        {"key": "surface", "label": "Surface / path"},
                        {"key": "tenant", "label": "Tenant"},
                        {"key": "actor", "label": "Actor"},
                        {"key": "trace", "label": "Trace ID"},
                        {"key": "request", "label": "Request ID"},
                        {"key": "timestamp", "label": "Timestamp"},
                    ],
                    "rows": blocked_rows,
                },
                {
                    "type": "links",
                    "title": "Blocked-action links",
                    "items": [
                        _link("Governed telemetry feed", _raw(event_feed_path), "Raw reason codes, trace IDs, and timestamps for current governed actions.", "healthy", display_label="Technical event feed", display_description="Open the raw event feed behind the blocked-action summary."),
                        _link("Inspectable denied runtime flow", _raw(INSPECTABLE_DENIED_FLOW), "Denied /launch/onyx handoff bundle with linked artifacts, request context, and reviewer proof.", "critical", display_label="Full blocked-access example", display_description="Open the technical proof bundle for the blocked access example."),
                        _link("Reviewer evidence bundle", reviewer_href, "Reviewer-facing evidence pack containing blocked attack summary and audit signals.", "healthy", display_label="Reviewer proof bundle", display_description="Open the bundled proof for blocked actions and review history."),
                    ],
                },
            ],
        },
        {
            **section_contracts["upstream-posture"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "Connected-system summary",
                    "items": [
                        item
                        for item in _upstream_audit_cards(upstream_inventory)
                        if item["label"] in {"Used now", "Partially used", "Inventory coverage", "Snapshot provenance", "Mandatory path components"}
                    ],
                },
                {
                    "type": "records",
                    "title": "Most important connected parts",
                    "items": _upstream_record_items(
                        _important_upstream_components(upstream_components, 4),
                        onyx_governed_entry_url=onyx_governed_entry_url,
                        onyx_runtime_public_url=onyx_runtime_public_url,
                        onyx_runtime_local_url=onyx_runtime_local_url,
                    ),
                },
                {
                    "type": "table",
                    "title": "Top homepage components and lifecycle",
                    "collapsed": True,
                    "summary": "Open upstream component slice (top 5 rows)",
                    "columns": [
                        {"key": "component", "label": "Component"},
                        {"key": "classification", "label": "Classification"},
                        {"key": "path_status", "label": "Path status"},
                        {"key": "decision", "label": "Lifecycle decision"},
                        {"key": "checkout", "label": "Checkout"},
                        {"key": "validated", "label": "Last validated"},
                        {"key": "source_pin", "label": "Source pin"},
                        {"key": "location", "label": "Where it sits"},
                        {"key": "signal", "label": "Governance signal"},
                        {"key": "evidence", "label": "Evidence artifact"},
                        {"key": "live_surface", "label": "Live runtime"},
                        {"key": "dev", "label": "Dev"},
                        {"key": "prod_sim", "label": "Prod-sim"},
                    ],
                    "rows": _upstream_table_rows(
                        _important_upstream_components(upstream_components, 5),
                        onyx_governed_entry_url=onyx_governed_entry_url,
                        onyx_runtime_public_url=onyx_runtime_public_url,
                    ),
                },
                {
                    "type": "links",
                    "title": "Connected-system links",
                    "items": [
                        _link("Onyx governed entry", onyx_governed_entry_url, "Open the checked dashboard handoff into the current Onyx path.", "healthy" if latest_handoff_allowed else "warning", display_label="Open governed Onyx", display_description="Use the dashboard-controlled handoff into the current Onyx path."),
                        _link("Onyx live runtime", onyx_runtime_public_url, "Open the current public Onyx runtime target for the latest requested path.", runtime_readiness_status, display_label="Open live runtime", display_description="Open the current public Onyx runtime target from the upstream section."),
                        _link("Full upstream inventory", _dashboard_url("/api/control-plane/upstream-usage"), "Full machine-readable component inventory beyond the homepage slice.", "healthy", display_label="Full connected-system inventory", display_description="Open the complete machine-readable inventory."),
                        _link("Upstream usage API", _dashboard_url("/api/control-plane/upstream-usage"), "Machine-readable upstream inventory exposed by the control plane.", "healthy", display_label="Connected-system API", display_description="Open the technical API view of the component inventory."),
                        _link("Upstream usage inventory", _raw("evidence/upstream_usage.inventory.json"), "Repo-owned component inventory with classification, signals, evidence, and removal impact.", "healthy", display_label="Inventory file", display_description="Open the raw inventory file behind this section."),
                        _link("Upstream source lock", _raw("evidence/upstream.lock.json"), "Checkout/source-management lock with checkout policy, validation date, lifecycle decision, and source-pin fields.", "healthy", display_label="Lifecycle lock file", display_description="Open the raw lock file for vendored source tracking."),
                        _link("Upstream usage matrix", _raw("docs/upstream-usage-matrix.md"), "Reviewer-facing explanation of what is active, partial, optional, or reference-only.", "neutral", display_label="How connected systems are classified", display_description="Open the explanation of active, supporting, optional, and reference-only components."),
                        _link("Upstream tracking guide", _raw("docs/submodules.md"), "Repo checkout guidance for vendored upstreams, overlay submodules, pin recording, and validation.", "neutral", display_label="Tracking guide", display_description="Open the operational guide for vendored upstream tracking."),
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
                        _card(
                            "Identity source",
                            _display_identity_source(identity_evidence),
                            "healthy" if identity_live else ("critical" if live_evidence_mode else "warning"),
                            _panel_note(
                                timestamp=identity_timestamp,
                                evidence_mode=str(identity_evidence.get("evidence_mode", governed_flow_summary.get("evidence_mode", ""))),
                                provenance="adapter-derived" if identity_live else "sample/demo",
                                extra="Live mode should show Keycloak-backed validation and fail closed otherwise.",
                            ),
                            _raw("overlays/myStarterKit/artifacts/identity-evidence.json"),
                        ),
                        _card(
                            "Session correlation",
                            latest_session_id or "unavailable",
                            "healthy" if latest_session_id else ("critical" if live_evidence_mode else "warning"),
                            f"{session_linkage.get('reason', 'Session linkage reason unavailable')}.",
                            "#trace-correlation",
                        ),
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
                        _link("Identity evidence artifact", _raw("overlays/myStarterKit/artifacts/identity-evidence.json"), "Latest governed-flow identity proof showing live vs demo identity derivation and session-linkage status.", "healthy" if identity_evidence else "warning"),
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
                        _card(
                            "Decision engine",
                            _display_policy_engine(policy_evidence),
                            "healthy" if policy_engine == "opa" and bool(policy_evidence.get("engine_reachable", True)) else ("critical" if live_evidence_mode else "warning"),
                            _panel_note(
                                timestamp=policy_timestamp,
                                evidence_mode=str(policy_evidence.get("evidence_mode", governed_flow_summary.get("evidence_mode", ""))),
                                provenance="adapter-derived" if policy_engine == "opa" else "sample/demo",
                                extra="Live mode should show OPA as the active decision path and mark reachability failures explicitly.",
                            ),
                            _raw("overlays/myStarterKit/artifacts/policy-evidence.json"),
                        ),
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
                        for event in policy_events[:4]
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
                        _card(
                            "Latest backend",
                            _display_retrieval_backend(retrieval_evidence),
                            "healthy" if retrieval_live_backend and bool(retrieval_evidence.get("backend_verified")) else ("critical" if live_evidence_mode else "warning"),
                            _panel_note(
                                timestamp=retrieval_timestamp,
                                evidence_mode=str(retrieval_evidence.get("evidence_mode", governed_flow_summary.get("evidence_mode", ""))),
                                provenance="adapter-derived" if retrieval_evidence.get("backend_verified") else "sample/demo",
                                extra="Live mode should show a verified backend path such as Qdrant instead of seeded retrieval.",
                            ),
                            _raw("overlays/myStarterKit/artifacts/retrieval-evidence.json"),
                        ),
                        _card("Latest retrieval result", "ALLOW" if retrieval_evidence.get("allow") else "DENY", "healthy" if retrieval_evidence.get("allow") else "critical", f"Latest retrieval reasons: {', '.join(_string_list(retrieval_evidence.get('reason_codes')) or _string_list(retrieval_evidence.get('reasons')) or ['unknown'])}.", _raw("overlays/myStarterKit/artifacts/retrieval-evidence.json")),
                    ],
                },
                {
                    "type": "table",
                    "title": "Retrieval source coverage",
                    "collapsed": True,
                    "summary": "Open retrieval boundary slice (top 5 rows)",
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
                        for event in retrieval_events[:4]
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
                        _card(
                            "Secret backend",
                            _display_secret_backend(secret_evidence),
                            "healthy" if secret_evidence.get("backend") == "vault" and bool(secret_evidence.get("backend_configured")) else ("critical" if secret_required and live_evidence_mode else "warning"),
                            _panel_note(
                                timestamp=secret_timestamp,
                                evidence_mode=str(secret_evidence.get("evidence_mode", governed_flow_summary.get("evidence_mode", ""))),
                                provenance="adapter-derived" if secret_evidence.get("backend") == "vault" and secret_evidence.get("backend_configured") else "sample/demo",
                                extra="Vault is conditional: only secret-requiring governed flows should expect it as a live dependency.",
                            ),
                            _raw("overlays/myStarterKit/artifacts/secret-evidence.json"),
                        ),
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
                    "collapsed": True,
                    "summary": "Open tool and MCP inventory slice",
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
                        _card("Audit coverage", f"{audit_coverage}%", "healthy" if audit_coverage >= 60 else "warning", "Observed traces tied to explicit governed audit records, with adapter-derived fallback only when no audit artifact exists.", _raw(AUDIT_RECORDS_PATH) if audit_provenance == "runtime-generated" else reviewer_href),
                        _card("Trace coverage", f"{trace_coverage}%", "healthy" if trace_coverage >= 80 else "warning", "Requests with visible completion telemetry in the current feed.", _raw(event_feed_path)),
                        _card("Trace continuity", "complete" if trace_complete else "incomplete", "healthy" if trace_complete else "critical", "Latest governed flow trace continuity across identity, policy, retrieval, secret, tool, and handoff steps.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Audit record source", audit_provenance, "healthy" if audit_provenance == "runtime-generated" else "warning", "Audit coverage prefers runtime-generated records and falls back to adapter-derived reconstruction only for older artifacts.", _raw(AUDIT_RECORDS_PATH) if audit_provenance == "runtime-generated" else _raw(event_feed_path)),
                        _card("Replay bundles", str(len(INSPECTABLE_SCENARIOS)), "healthy", "Inspectable pass/fail live-governed examples are available for evaluator review.", _raw(INSPECTABLE_ALLOWED_FLOW)),
                        _card("Blocked attacks", str(evidence_summary.get("blocked_count", 0)), "healthy", "Reviewer evidence bundle records blocked hostile scenarios.", reviewer_href),
                        _card("Eval pass / total", f"{eval_passed} / {eval_total}", "healthy" if eval_total == 0 or eval_passed == eval_total else "warning", "Latest available evaluation summary for the governed stack.", ingestion_href),
                    ],
                },
                {
                    "type": "table",
                    "title": "Audit event sample",
                    "collapsed": True,
                    "summary": "Open audit event sample",
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
                            for attack in blocked_attacks[:3]
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
                        _record(
                            title="Current audit linkage",
                            meta=audit_provenance,
                            detail=(
                                f"{len(audit_dataset)} audit records mapped to {len(audit_trace_ids)} traces. "
                                f"Missing audit stages: {', '.join(_string_list(audit_linkage.get('missing_stages', [])) or ['none'])}."
                            ),
                            status="healthy" if not _string_list(audit_linkage.get("missing_stages", [])) and audit_dataset else "warning",
                            href=_raw(AUDIT_RECORDS_PATH) if audit_provenance == "runtime-generated" else _raw(event_feed_path),
                        ),
                    ],
                },
                {
                    "type": "links",
                    "title": "Audit drill-through",
                    "items": [
                        _link("Reviewer evidence bundle", reviewer_href, "Audit sample, blocked attack summary, and inspectable evidence references.", "healthy"),
                        _link("Governed audit records", _raw(AUDIT_RECORDS_PATH), "Runtime-generated audit records for governed stages when a fresh governed flow has run.", "healthy" if audit_provenance == "runtime-generated" else "warning"),
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
                        _card("Latest session", latest_session_id or "unavailable", "healthy" if latest_session_id else ("critical" if live_evidence_mode else "warning"), str(session_linkage.get("reason", "Latest governed-flow session identifier tied to the trace.")), _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Trace complete", "yes" if trace_complete else "no", "healthy" if trace_complete else "critical", "Whether the latest governed flow recorded the required end-to-end control steps under one correlated trace.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Missing steps", str(len(_string_list(trace_correlation.get("missing_steps", [])))), "healthy" if not _string_list(trace_correlation.get("missing_steps", [])) else "critical", "Missing trace-correlation steps for the latest governed flow.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Missing identifiers", str(len(trace_missing_identifiers)), "healthy" if not trace_missing_identifiers else "critical", "Missing trace identifiers such as session, actor, tenant, or surface linkage.", _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                        _card("Audit linkage", "complete" if audit_linkage.get("complete") else "incomplete", "healthy" if audit_linkage.get("complete") else "warning", f"Audit records observed: {audit_linkage.get('record_count', 0)}. Missing stages: {', '.join(_string_list(audit_linkage.get('missing_stages', [])) or ['none'])}.", _raw(AUDIT_RECORDS_PATH) if audit_linkage.get("record_count") else _raw("overlays/myStarterKit/artifacts/trace-correlation.json")),
                    ],
                },
                {
                    "type": "records",
                    "title": "Latest trace evidence",
                    "items": [
                        _record(
                            title="Correlated governed request",
                            meta=" | ".join(value for value in (latest_trace_id, latest_session_id, str(governed_flow_summary.get("evidence_mode", event_feed_label))) if value),
                            detail=(
                                f"Missing steps: {', '.join(trace_correlation.get('missing_steps', [])) or 'none'}. "
                                f"Missing identifiers: {', '.join(trace_missing_identifiers) or 'none'}. "
                                f"Session linkage: {session_linkage.get('reason', 'unavailable')}."
                            ),
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
                        _link("Governed audit records", _raw(AUDIT_RECORDS_PATH), "Audit-stage linkage for the same trace/request/session model used by the governed flow.", "healthy" if audit_linkage.get("record_count") else "warning"),
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
                    "title": "Safety-check summary",
                    "items": [
                        _card("Readiness status", launch_summary["status"].upper(), _status_from_launch(launch_summary["status"]), "Current launch verdict from the launch-gate summary.", launch_report_href, display_label="Current safety decision", display_value=_readiness_display(launch_summary["status"]), display_detail=f"Current score: {launch_summary['readiness_score']}/100."),
                        _card("Failing controls", str(len(failing_controls)), "critical" if failing_controls else "healthy", "Controls that are not in a full pass state.", launch_report_href, display_label="Important issues still open", display_detail="These are the main issues still keeping the system from a cleaner ready state."),
                        _card(
                            "Evidence mode",
                            _freshness_label(
                                timestamp=str(governed_flow_summary.get("generated_at", "")),
                                evidence_mode=str(launch_summary.get("evidence_mode", "")),
                                provenance="runtime-generated" if str(launch_summary.get("evidence_mode", "")) == "live" else "sample/demo",
                            ),
                            "healthy" if str(launch_summary.get("evidence_mode", "")) == "live" else "warning",
                            "Live mode should compute readiness from governed-flow evidence artifacts instead of sample/demo telemetry.",
                            launch_report_href,
                            display_label="Proof used for this decision",
                            display_detail="Shows whether the safety decision came from live proof or from demo/sample material.",
                        ),
                        _card(
                            "Missing evidence",
                            ", ".join(latest_missing_evidence) or "none",
                            "healthy" if not latest_missing_evidence else "critical",
                            "Latest launch-gate evidence still missing from the governed flow.",
                            latest_governed_flow_href,
                            display_label="Missing proof for safety decision",
                            display_value=", ".join(latest_missing_evidence) or "none",
                            display_detail="Missing proof here keeps the launch decision from being fully supported by current governed evidence.",
                        ),
                    ],
                },
                {
                    "type": "records",
                    "title": "Most important issues",
                    "items": (readiness_panel["top_failing_controls"][:3]) or [
                        _record("No failing controls", "Launch gate", "All controls are in a pass state.", "healthy", launch_report_href)
                    ],
                },
                {
                    "type": "records",
                    "title": "Risks still being watched",
                    "items": (readiness_panel["residual_risks"][:3]) or [
                        _record("No residual risks", "Launch gate", "No residual launch risks are listed in the current report.", "healthy", launch_report_href)
                    ],
                },
                {
                    "type": "links",
                    "title": "Safety-check links",
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
                    "title": "Homepage protection slice",
                    "collapsed": True,
                    "summary": "Open homepage protection slice (top 5 rows)",
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
                        _link("Full policy inventory", policy_href, "Complete governed surface, retrieval, and tool inventory beyond the homepage slice.", "healthy"),
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
                    "title": "Proof-quality summary",
                    "items": [
                        _card("Fresh artifacts", str(artifact_counts["fresh"]), "healthy", "Artifacts updated recently enough for evaluator trust.", "#evidence-integrity", display_label="Current proof items", display_detail="These proof items were updated recently enough to trust for review."),
                        _card("Stale artifacts", str(artifact_counts["stale"]), "critical" if artifact_counts["stale"] else "healthy", "Artifacts present but old enough to warrant attention.", "#evidence-integrity", display_label="Out-of-date proof items", display_detail="These proof items are old enough to need attention."),
                        _card("Missing artifacts", str(artifact_counts["missing"]), "critical" if artifact_counts["missing"] else "healthy", "Expected evidence that is missing from the checkout.", "#evidence-integrity", display_label="Missing proof items", display_detail="These proof items are expected but not currently present."),
                    ][:3],
                },
                {
                    "type": "table",
                    "title": "Priority artifact slice",
                    "collapsed": True,
                    "summary": "Open priority artifact slice (top 5 rows)",
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
                    "title": "Proof problems to review",
                    "items": [
                        _record(
                            title=artifact["label"],
                            meta=artifact["freshness"],
                            detail=f"{artifact['integrity']}. {artifact['detail']} ({artifact['path']}).",
                            status=artifact["status"],
                            href=artifact["href"],
                        )
                        for artifact in artifact_inventory[:]
                        if artifact["status"] in {"warning", "critical"}
                    ][:4] or [
                        _record("No integrity warnings", "Evidence integrity", "All tracked artifacts are present and structurally readable.", "healthy")
                    ],
                },
                {
                    "type": "links",
                    "title": "Proof links",
                    "items": [
                        _link("Reviewer evidence bundle", reviewer_href, "Reviewer-ready bundle for pass, deny, and launch-gate evidence.", "healthy", display_label="Reviewer proof bundle", display_description="Open the main bundle of reviewer-ready proof."),
                        _link("Dashboard ingestion feed", ingestion_href, "Export used for dashboard-level ingestion and replay references.", "neutral", display_label="Technical export feed", display_description="Open the technical export used by downstream views."),
                        _link("Evidence model note", _raw("docs/evidence-model.md"), "Explains artifact types, request previews, and trace-linked evidence expectations.", "neutral", display_label="How proof works here", display_description="Open the explanation of traces, proof items, and safe request previews."),
                    ],
                },
            ],
        },
        {
            **section_contracts["entry-points"],
            "blocks": [
                {
                    "type": "cards",
                    "title": "AI-access summary",
                    "items": [
                        _card("Onyx visibility", "Governed runtime plane", "healthy" if onyx_available else "warning", "Onyx remains behind dashboard-controlled handoffs; this control plane decides whether access is allowed and what evidence must exist.", _raw("docs/onyx-integration.md"), id="onyx_visibility", display_label="AI system being protected", display_value="Onyx", display_detail="This dashboard decides when access to the AI system is allowed and what proof is required."),
                        _card("Latest handoff", "ALLOW" if latest_handoff_allowed else "DENY", "healthy" if latest_handoff_allowed else "critical", f"Latest governed handoff reason: {latest_handoff_reason}.", _raw("overlays/myStarterKit/artifacts/governed-flow-summary.json"), id="latest_handoff", display_label="Latest access decision", display_value=_allow_deny_display(latest_handoff_allowed), display_detail="Shows whether the latest checked access into the AI system was allowed or blocked."),
                        _card("Missing handoff evidence", ", ".join(latest_missing_evidence) or "none", "healthy" if not latest_missing_evidence else "critical", "Live-mode missing evidence that affected the latest handoff or launch-gate result.", _raw("overlays/myStarterKit/artifacts/governed-flow-summary.json"), id="missing_handoff_evidence", display_label="Missing proof for access decision", display_value=", ".join(latest_missing_evidence) or "none", display_detail="Missing proof can cause AI access to be blocked or downgraded."),
                        _card("Runtime continuity", runtime_continuity_label, runtime_continuity_status, f"{str(runtime_continuity.get('detail', 'Post-handoff continuity is not available yet.'))} Latest activity: {runtime_latest_activity_summary}", runtime_proof_href, id="onyx_runtime_continuity", display_label="Runtime continuity after access", display_value=runtime_continuity_label, display_detail="Shows whether recent Onyx runtime activity lines up with the governed handoff path."),
                        _card("Runtime readiness", runtime_readiness_label, runtime_readiness_status, f"{str(runtime_readiness.get('detail', 'Runtime reachability is not available yet.'))} Target path: {latest_requested_path}.", runtime_proof_href, id="onyx_runtime_readiness", display_label="Runtime readiness after access", display_value=runtime_readiness_label, display_detail="Shows whether the Onyx runtime and public handoff target were reachable after approval."),
                    ],
                },
                {
                    "type": "records",
                    "title": "Recent AI-access outcomes",
                    "items": onyx_handoffs[:3],
                },
                {
                    "type": "links",
                    "title": "AI-access links",
                    "items": [
                        _link("Live Workspace", _live_session_start_url(_launch_handoff_path("/app", mode="live", view="embedded")), "Mint a local dev-only live session in the control plane and open the dashboard-owned runtime workspace with governance context and embedded Onyx access when reachable. Intended for local dev and prod-sim runs.", "healthy", display_label="Start dev live workspace", display_description="Mint the local dev-only session and open the live chat surface inside the dashboard-owned runtime workspace."),
                        _link("Open Chat", _launch_handoff_url("/app"), "Launch the governed Onyx chat surface through the dashboard handoff.", "healthy", display_label="Open chat", display_description="Open the checked chat entry point for the AI system."),
                        _link("Search Knowledge", _launch_handoff_url("/app?chatMode=search"), "Launch the governed search-oriented Onyx surface.", "healthy", display_label="Open search", display_description="Open the checked search entry point for the AI system."),
                        _link("Open Agents", _launch_handoff_url("/app/agents"), "Governed agents surface; non-admin roles should be denied.", "warning", display_label="Open agents", display_description="Open the agents entry point. Non-admin roles should still be blocked here."),
                        _link("Governed flow API", _dashboard_url("/api/control-plane/governed-flow"), "Trigger a governed flow run to generate fresh runtime artifacts.", "neutral", display_label="Create fresh technical proof", display_description="Run a new checked flow to create fresh AI-access evidence."),
                        _link("Latest runtime proof", runtime_proof_href, "Post-handoff Onyx runtime reachability and continuity summary for the latest governed request.", runtime_proof_status, display_label="Open runtime proof", display_description="Open the latest post-handoff runtime proof for the AI system."),
                        _link("Onyx integration note", _raw("docs/onyx-integration.md"), "Architecture note for Onyx as the governed runtime plane behind the dashboard control plane.", "neutral", display_label="How AI access works", display_description="Open the technical note explaining the AI-access architecture."),
                    ],
                },
            ],
        },
    ]
    section_order = {str(section.get("id", "")): index for index, section in enumerate(contract.get("sections", []))}
    sections.sort(key=lambda section: section_order.get(str(section.get("id", "")), len(section_order)))

    sources = [
        _link("Governed event feed", _raw(event_feed_path), "Event feed used by the dashboard overview and blocked-actions views.", "healthy", id="governed_event_feed"),
        _link("Governed request feed", governed_request_feed_href, "Reviewer-safe request telemetry with sanitized previews and per-trace evidence history.", "healthy" if governed_request_feed else "warning", id="governed_request_feed"),
        _link("Governed audit records", _raw(AUDIT_RECORDS_PATH), "Audit-stage records tied to the same trace/request/session model when a governed flow has run.", "healthy" if audit_provenance == "runtime-generated" else "warning", id="governed_audit_records"),
        _link("Policy bundle", policy_href, "Runtime surface, retrieval, and tool governance policy.", "healthy" if policy_source == "overlay" else "warning", id="policy_bundle"),
        _link("Governed flow summary", latest_governed_flow_href, "Latest governed-flow summary including identity, policy, retrieval, secret, trace, and launch-gate evidence.", "healthy" if governed_flow_summary else "warning", id="governed_flow_summary"),
        _link("Onyx runtime proof", runtime_proof_href, "Latest post-handoff Onyx runtime readiness and continuity summary.", runtime_proof_status, id="onyx_runtime_proof"),
        _link("Upstream usage inventory", _raw("evidence/upstream_usage.inventory.json"), "Classification of active, partial, optional, and reference-only upstream components.", "healthy", id="upstream_usage_inventory"),
        _link("Reviewer evidence bundle", reviewer_href, "Consolidated reviewer-facing evidence pack.", "healthy", id="reviewer_evidence_bundle"),
        _link("Launch report", launch_report_href, "Launch-gate findings and residual risk guidance.", "warning", id="launch_report"),
        _link("Dashboard ingestion feed", ingestion_href, "Dashboard export sample used for evidence drill-through and replay references.", "neutral", id="dashboard_ingestion_feed"),
    ]

    return {
        "title": str(contract.get("title", "AI Trust & Security Stack Control Plane")),
        "subtitle": str(contract.get("subtitle", "")),
        "hero_copy": str(contract.get("hero_copy", "")),
        "landing_steps": list(contract.get("landing_steps", [])),
        "generated_at": dashboard_generated_at,
        "runtime_module": "Safety review layer over the Onyx AI system",
        "data_mode": {
            "label": "Live current evidence" if live_evidence_mode else ("Recent generated governed evidence" if has_live_governed_flow_artifacts(resolved_root) else "Sample/demo governed evidence"),
            "status": "healthy" if live_evidence_mode else ("healthy" if has_live_governed_flow_artifacts(resolved_root) else "warning"),
            "detail": f"Primary event feed: {event_feed_path}",
            "display_label": "Live proof" if live_evidence_mode else ("Recent generated proof" if has_live_governed_flow_artifacts(resolved_root) else "Sample or demo proof"),
        },
        "repo_description_suggestion": str(contract.get("repo_description_suggestion", "")),
        "mode_banner": mode_banner,
        "reading_guide": reading_guide,
        "command_center": command_center,
        "stack_health": stack_health,
        "audience_paths": audience_paths,
        "operator_briefing": quick_answers,
        "kpis": kpis,
        "readiness_panel": readiness_panel,
        "tabs": list(contract.get("tabs", [])),
        "sections": sections,
        "sources": sources,
        "activity_snapshot": activity_snapshot,
        "evidence_exports": evidence_summary.get("exports", []),
    }
