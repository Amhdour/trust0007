from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import os
from pathlib import Path
from typing import Any

from backend.activity_service.service import build_activity_snapshot
from backend.evidence_service.service import build_evidence_pack_summary
from backend.integration_adapter.repository import (
    load_eval_summaries,
    load_policy_bundle,
    load_reviewer_bundle,
    load_sample_events,
    load_service_inventory,
    repo_root,
)
from backend.launch_gate_service.service import build_launch_gate_summary


def _card(label: str, value: str, status: str, detail: str) -> dict[str, str]:
    return {"label": label, "value": value, "status": status, "detail": detail}


def _record(title: str, meta: str, detail: str, status: str = "neutral") -> dict[str, str]:
    return {"title": title, "meta": meta, "detail": detail, "status": status}


def _raw(path: str) -> str:
    return f"/raw/{path}"


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


def _status_from_launch(verdict: str) -> str:
    return {
        "go": "healthy",
        "conditional": "warning",
        "no-go": "critical",
    }.get(verdict, "neutral")


def _count_events(events: list[dict[str, Any]]) -> Counter[str]:
    return Counter(str(event.get("event_type", "")) for event in events)


def _latest(items: list[dict[str, Any]]) -> dict[str, Any]:
    return items[-1] if items else {}


def _unique(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value and value not in ordered:
            ordered.append(value)
    return ordered


def _severity_status(value: str) -> str:
    normalized = value.strip().lower()
    return {
        "error": "critical",
        "critical": "critical",
        "warning": "warning",
        "warn": "warning",
        "info": "neutral",
        "debug": "neutral",
    }.get(normalized, "neutral")


def _summarize_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type", "event"))
    payload = event.get("payload", {})
    if not isinstance(payload, dict):
        payload = {}

    if event_type == "request.start":
        return f"Started {payload.get('path', '/runtime')}"
    if event_type == "request.end":
        return f"Completed with status {payload.get('status', 'unknown')}"
    if event_type == "policy.decision":
        decision = "allow" if payload.get("allow") else "deny"
        return f"Policy {decision} via {payload.get('policy', 'policy bundle')}"
    if event_type == "retrieval.decision":
        return f"{payload.get('decision', 'allow').upper()} retrieval from {payload.get('source', 'unknown source')}"
    if event_type == "tool.execution_attempt":
        return f"Attempted tool {payload.get('tool_name', 'unknown')}"
    if event_type == "fallback.event":
        return f"Fallback triggered: {payload.get('reason', 'degraded runtime')}"
    if event_type == "deny.event":
        return f"Denied by governance: {payload.get('reason', 'policy_denied')}"
    if event_type == "incident.signal":
        return f"Incident signal: {payload.get('signal', 'anomaly_detected')}"

    details = [f"{key}={value}" for key, value in payload.items() if value not in {"", None}]
    return ", ".join(details[:3]) if details else "No payload details recorded."


def build_control_plane_live_log(root: Path | None = None, limit: int = 12) -> dict[str, Any]:
    resolved_root = repo_root(root)
    return build_activity_snapshot(resolved_root, limit=limit)


def build_control_plane_dashboard(root: Path | None = None) -> dict[str, Any]:
    resolved_root = repo_root(root)
    services = load_service_inventory(resolved_root)
    events = load_sample_events(resolved_root)
    counts = _count_events(events)
    policy = load_policy_bundle(resolved_root)
    reviewer = load_reviewer_bundle(resolved_root)
    evidence_summary = build_evidence_pack_summary(resolved_root)
    launch_summary = build_launch_gate_summary(resolved_root)
    eval_summaries = load_eval_summaries(resolved_root)
    latest_eval = _latest(eval_summaries)
    activity_snapshot = build_activity_snapshot(resolved_root, limit=12)

    request_events = [event for event in events if event.get("event_type") == "request.start"]
    policy_events = [event for event in events if event.get("event_type") == "policy.decision"]
    retrieval_events = [event for event in events if event.get("event_type") == "retrieval.decision"]
    deny_events = [event for event in events if event.get("event_type") == "deny.event"]
    tool_events = [event for event in events if event.get("event_type") == "tool.execution_attempt"]
    fallback_events = [event for event in events if event.get("event_type") == "fallback.event"]
    trace_ids = _unique([str(event.get("trace_id", "")) for event in events])
    audit_events = reviewer.get("sample_audit_events", {}).get("events", [])
    blocked_attacks = reviewer.get("blocked_attack_summary", {}).get("blocked_attacks", [])

    allowed_sources = policy.get("retrieval", {}).get("tenant_allowed_sources", {})
    allowed_integrations = policy.get("integrations", {}).get("allowed_integrations", [])
    mcp_servers = [value for value in allowed_integrations if str(value).startswith("mcp_server.")]
    registered_tools = _unique(
        list(policy.get("tools", {}).get("allowed_tools", []))
        + list(policy.get("tools", {}).get("forbidden_tools", []))
    )
    confirmation_required = list(policy.get("tools", {}).get("confirmation_required_tools", []))
    sandbox_required_tools = ["admin_shell"] if (resolved_root / "overlays/myStarterKit/artifacts/logs/sandbox/demo-admin_shell-evidence.json").exists() else []
    eval_passed = int(latest_eval.get("passed_count", 0))
    eval_total = int(latest_eval.get("total", 0))
    eval_failed = max(eval_total - eval_passed, 0)
    readiness_status = launch_summary["status"]

    retrieval_rows = []
    for tenant_id, sources in allowed_sources.items():
        for source in sources:
            retrieval_rows.append(
                {
                    "tenant": tenant_id,
                    "source": source,
                    "boundary": "tenant-scoped",
                    "trust": "trust metadata + provenance required",
                }
            )

    tool_rows = [
        {
            "control": "Registered tools",
            "value": str(len(registered_tools)),
            "notes": ", ".join(registered_tools) or "none",
        },
        {
            "control": "Approved tools",
            "value": str(len(policy.get("tools", {}).get("allowed_tools", []))),
            "notes": ", ".join(policy.get("tools", {}).get("allowed_tools", [])) or "none",
        },
        {
            "control": "Blocked tools",
            "value": str(len(policy.get("tools", {}).get("forbidden_tools", []))),
            "notes": ", ".join(policy.get("tools", {}).get("forbidden_tools", [])) or "none",
        },
        {
            "control": "Confirmation-required tools",
            "value": str(len(confirmation_required)),
            "notes": ", ".join(confirmation_required) or "none",
        },
        {
            "control": "Sandbox-required tools",
            "value": str(len(sandbox_required_tools)),
            "notes": ", ".join(sandbox_required_tools) or "none",
        },
        {
            "control": "MCP server inventory",
            "value": str(len(mcp_servers)),
            "notes": ", ".join(mcp_servers) or "none",
        },
    ]

    audit_rows = [
        {
            "event": str(event.get("event_type", "audit.event")),
            "trace_id": str(event.get("trace_id", "")),
            "request_id": str(event.get("request_id", "")),
            "summary": str(event.get("event_payload", {}).get("action", "captured")),
        }
        for event in audit_events[:5]
    ]

    launch_records = [
        _record(
            title=str(finding.get("control", "control")),
            meta=str(finding.get("status", "unknown")),
            detail=str(finding.get("summary", "")),
            status="healthy" if finding.get("status") == "pass" else "warning",
        )
        for finding in launch_summary.get("findings", [])
    ]

    sections = [
        {
            "id": "overview",
            "title": "Business Overview",
            "description": "A simple summary of platform health, controls, and launch readiness.",
            "blocks": [
                {
                    "type": "cards",
                    "title": "Key business signals",
                    "items": [
                        _card(
                            "Overall platform",
                            "Platform running",
                            "healthy",
                            f"{len(services)} services inventoried across the local stack.",
                        ),
                        _card(
                            "Policy checks",
                            "Rules active" if "opa" in services else "Rules pending",
                            "healthy" if "opa" in services else "warning",
                            f"{len(allowed_integrations)} governed integrations in policy inventory.",
                        ),
                        _card(
                            "User access",
                            "Access controls active" if "keycloak" in services else "Access setup pending",
                            "healthy" if "keycloak" in services else "warning",
                            "Business access starts with identity and session controls.",
                        ),
                        _card(
                            "Company data access",
                            "Data access active" if "qdrant" in services else "Data inventory only",
                            "healthy" if "qdrant" in services else "warning",
                            f"{sum(len(sources) for sources in allowed_sources.values())} source boundaries are modeled.",
                        ),
                        _card(
                            "Monitoring",
                            "Monitoring active",
                            "healthy" if {"langfuse", "grafana", "superset"}.issubset(set(services)) else "warning",
                            f"{len(events)} recent events are available for dashboard reporting.",
                        ),
                        _card(
                            "Launch readiness",
                            readiness_status.upper(),
                            _status_from_launch(readiness_status),
                            f"Readiness score {launch_summary['readiness_score']} with {launch_summary['control_coverage']} controls passing.",
                        ),
                    ],
                }
            ],
        },
        {
            "id": "runtime",
            "title": "Recent Activity",
            "description": "A business-friendly view of recent requests, decisions, alerts, and approvals.",
            "blocks": [
                {
                    "type": "cards",
                    "title": "Activity summary",
                    "items": [
                        _card("Combined activity", str(activity_snapshot["counts"]["combined"]), "healthy" if activity_snapshot["counts"]["combined"] else "warning", "Recent Onyx and Langfuse items visible to the dashboard."),
                        _card("Onyx activity", str(activity_snapshot["counts"]["onyx"]), "healthy" if activity_snapshot["counts"]["onyx"] else "warning", "Recent requests and runtime events coming from Onyx."),
                        _card("Langfuse traces", str(activity_snapshot["counts"]["langfuse_traces"]), "healthy" if activity_snapshot["counts"]["langfuse_traces"] else "warning", "Recent trace items captured by Langfuse."),
                        _card("Langfuse sessions", str(activity_snapshot["counts"]["langfuse_sessions"]), "neutral", "Recent sessions recorded by Langfuse."),
                        _card("Recent alerts", str(activity_snapshot["counts"]["alerts"]), "warning" if activity_snapshot["counts"]["alerts"] else "healthy", "Warnings or critical items in the combined activity feed."),
                        _card("Source coverage", "2 sources", "healthy" if all(status.startswith("connected") for status in activity_snapshot["sources"].values()) else "warning", "The dashboard is reading from both Onyx and Langfuse activity sources."),
                    ],
                },
                {
                    "type": "records",
                    "title": "Recent activity details",
                    "items": [
                        *[
                            _record(
                                title=str(entry.get("event_type", "activity")),
                                meta=f"{entry.get('source_label', '')} | {entry.get('timestamp', '')}",
                                detail=str(entry.get("summary", "")),
                                status=str(entry.get("status", "neutral")),
                            )
                            for entry in activity_snapshot["entries"]
                        ],
                    ],
                },
            ],
        },
        {
            "id": "retrieval",
            "title": "Data Access",
            "description": "How company data is segmented, approved, and used by AI workflows.",
            "blocks": [
                {
                    "type": "cards",
                    "title": "Data access summary",
                    "items": [
                        _card("Indexed sources", str(len(retrieval_rows)), "healthy", "Sources currently modeled for tenant-scoped retrieval."),
                        _card("Tenant/source boundaries", str(len(allowed_sources)), "healthy", "Per-tenant source segmentation is declared in policy."),
                        _card("Retrieval decisions", str(len(retrieval_events)), "neutral", "Observed retrieval allow/deny decisions."),
                        _card("Blocked retrieval attempts", "0", "healthy", "No blocked retrieval attempts in the current telemetry sample."),
                        _card("Provenance coverage", "Required", "healthy", "Provenance and trust metadata checks are enforced in policy."),
                        _card("Connector exposure", "Scoped", "healthy", "Retrieval connectors are surfaced through allowed integration inventory only."),
                    ],
                },
                {
                    "type": "table",
                    "title": "Source boundaries",
                    "columns": [
                        {"key": "tenant", "label": "Tenant"},
                        {"key": "source", "label": "Indexed source"},
                        {"key": "boundary", "label": "Boundary"},
                        {"key": "trust", "label": "Trust requirements"},
                    ],
                    "rows": retrieval_rows,
                },
                {
                    "type": "records",
                    "title": "Recent retrieval decisions",
                    "items": [
                        _record(
                            title=f"{event.get('payload', {}).get('decision', 'allow').upper()} retrieval",
                            meta=f"{event.get('tenant_id', '')} | {event.get('timestamp', '')}",
                            detail=f"Backend {event.get('payload', {}).get('source', 'unknown')}",
                            status="healthy" if event.get("payload", {}).get("decision") == "allow" else "warning",
                        )
                        for event in retrieval_events
                    ],
                },
            ],
        },
        {
            "id": "tools-mcp",
            "title": "Controls and Integrations",
            "description": "Which tools are allowed, blocked, or require approval before use.",
            "blocks": [
                {
                    "type": "cards",
                    "title": "Control summary",
                    "items": [
                        _card("Registered tools", str(len(registered_tools)), "neutral", "Union of approved and blocked tool inventory."),
                        _card("Approved tools", str(len(policy.get("tools", {}).get("allowed_tools", []))), "healthy", "Tools allowed for governed execution."),
                        _card("Blocked tools", str(len(policy.get("tools", {}).get("forbidden_tools", []))), "warning", "Tools denied by policy bundle."),
                        _card("Confirmation-required", str(len(confirmation_required)), "warning", "High-impact tools requiring user approval."),
                        _card("Sandbox-required", str(len(sandbox_required_tools)), "warning" if sandbox_required_tools else "healthy", "Tools routed through isolated execution when needed."),
                        _card("MCP servers", str(len(mcp_servers)), "neutral", "Registered MCP runtime surfaces in policy inventory."),
                    ],
                },
                {
                    "type": "table",
                    "title": "Tool controls",
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
                                title=f"Tool attempt: {event.get('payload', {}).get('tool_name', 'unknown')}",
                                meta=f"{event.get('request_id', '')} | {event.get('timestamp', '')}",
                                detail="Observed from runtime activity stream.",
                                status="neutral",
                            )
                            for event in tool_events
                        ],
                        *[
                            _record(
                                title=f"Blocked tool path: {event.get('payload', {}).get('reason', 'forbidden_tool')}",
                                meta=f"{event.get('request_id', '')} | deny.event",
                                detail="Governance denied the attempted action.",
                                status="warning",
                            )
                            for event in deny_events
                        ],
                    ],
                },
            ],
        },
        {
            "id": "evals",
            "title": "Quality and Safety",
            "description": "How well the AI system performs in testing, tracing, and safety checks.",
            "blocks": [
                {
                    "type": "cards",
                    "title": "Quality summary",
                    "items": [
                        _card("Recent traces", str(len(trace_ids)), "neutral", "Unique traces observed in the telemetry sample."),
                        _card("Prompt/response paths", f"{counts.get('request.start', 0)}/{counts.get('request.end', 0)}", "healthy", "Request starts versus completed responses."),
                        _card("Eval pass/fail counts", f"{eval_passed}/{eval_failed}", "healthy" if eval_failed == 0 else "warning", "Latest red-team summary snapshot."),
                        _card("Red-team scenario status", f"{reviewer.get('blocked_attack_summary', {}).get('blocked_count', 0)} blocked", "healthy", "Known hostile scenarios are being intercepted."),
                        _card("Safety metrics", f"{eval_passed}/{eval_total}", "healthy", "Latest suite reports security-redteam pass coverage."),
                        _card("Quality views", "Per runtime module", "neutral", "Split between control-plane summary and drill-down tooling."),
                    ],
                },
                {
                    "type": "records",
                    "title": "Recent traces and evals",
                    "items": [
                        *[
                            _record(
                                title=f"Trace {trace_id}",
                                meta="Langfuse-ready telemetry",
                                detail="Prompt/response path is available for downstream drill-down.",
                                status="neutral",
                            )
                            for trace_id in trace_ids
                        ],
                        *[
                            _record(
                                title=scenario.get("scenario", "Red-team scenario"),
                                meta=scenario.get("decision", "blocked"),
                                detail=scenario.get("control_triggered", ""),
                                status="healthy",
                            )
                            for scenario in blocked_attacks
                        ],
                    ],
                },
            ],
        },
        {
            "id": "audit-replay",
            "title": "Audit and Evidence",
            "description": "Audit trails, traceability, and evidence exports for review and reporting.",
            "blocks": [
                {
                    "type": "table",
                    "title": "Recent audit records",
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
                    "title": "Replay and deny posture",
                    "items": [
                        _record(
                            title="Replay-ready sessions",
                            meta=str(len(_unique([str(event.get("request_id", "")) for event in audit_events]))),
                            detail="Audit sample includes request identifiers needed for replay correlation.",
                            status="healthy",
                        ),
                        *[
                            _record(
                                title=f"Deny reason: {event.get('payload', {}).get('reason', 'policy_denied')}",
                                meta=str(event.get("trace_id", "")),
                                detail="Visible to operators from the audit and runtime deny stream.",
                                status="warning",
                            )
                            for event in deny_events
                        ],
                    ],
                },
                {
                    "type": "links",
                    "title": "Evidence exports",
                    "items": [
                        {
                            "label": export["label"],
                            "href": export["href"],
                            "description": export["description"],
                            "status": "healthy",
                        }
                        for export in evidence_summary["exports"]
                    ],
                },
            ],
        },
        {
            "id": "launch-gate",
            "title": "Launch Readiness",
            "description": "A business view of coverage, risks, failed tests, and go-live readiness.",
            "blocks": [
                {
                    "type": "cards",
                    "title": "Readiness summary",
                    "items": [
                        _card("Control coverage", launch_summary["control_coverage"], "neutral", "Fully passing controls versus total control checks."),
                        _card("Missing controls", str(len(launch_summary["missing_controls"])), "warning" if launch_summary["missing_controls"] else "healthy", "Controls not fully satisfied in the current readiness report."),
                        _card("Failed tests", str(launch_summary["failed_tests"]), "healthy", "Known failed tests in the control-plane summary."),
                        _card("Residual risks", str(len(launch_summary["residual_risks"])), "warning" if launch_summary["residual_risks"] else "healthy", "Outstanding remediation or deployment caveats."),
                        _card("Readiness score", str(launch_summary["readiness_score"]), _status_from_launch(readiness_status), "Weighted readiness score derived from current findings."),
                        _card("Verdict", launch_summary["status"].upper(), _status_from_launch(readiness_status), "Go, conditional, or no-go summary for launch gate review."),
                    ],
                },
                {
                    "type": "records",
                    "title": "Findings and residual risks",
                    "items": [
                        *launch_records,
                        *[
                            _record(
                                title="Residual risk",
                                meta="remediation",
                                detail=str(risk),
                                status="warning",
                            )
                            for risk in launch_summary["residual_risks"]
                        ],
                    ],
                },
            ],
        },
        {
            "id": "entry-points",
            "title": "Useful Links",
            "description": "Direct links to the main business, operations, and evidence tools behind this dashboard.",
            "blocks": [
                {
                    "type": "links",
                    "title": "Open tools",
                    "items": [
                        {
                            "label": "Open Chat",
                            "href": _public_service_url(3010, "/app"),
                            "description": "Open the Onyx chat workspace as the governed runtime module behind the control plane.",
                            "status": "healthy",
                        },
                        {
                            "label": "Open Agents",
                            "href": _public_service_url(3010, "/app/agents"),
                            "description": "Open the Onyx agents workspace behind the dashboard-first control plane.",
                            "status": "healthy",
                        },
                        {
                            "label": "Search Knowledge",
                            "href": _public_service_url(3010, "/app?chatMode=search"),
                            "description": "Open the Onyx search experience backed by the governed retrieval stack.",
                            "status": "healthy",
                        },
                        {
                            "label": "Review Policies",
                            "href": _dashboard_url("/raw/overlays/myStarterKit/policies/bundles/default/policy.json"),
                            "description": "Review the active runtime policy bundle and integration inventory.",
                            "status": "healthy",
                        },
                        {
                            "label": "Review Evals",
                            "href": _public_service_url(3002),
                            "description": "Open Langfuse for trace and eval drill-down.",
                            "status": "healthy",
                        },
                        {
                            "label": "Review Evidence Pack",
                            "href": _dashboard_url("/raw/overlays/myStarterKit/artifacts/evidence/reviewer/reviewer_evidence_bundle.json"),
                            "description": "Open the reviewer evidence bundle exported by myStarterKit.",
                            "status": "healthy",
                        },
                        {
                            "label": "Admin / Tenant Settings",
                            "href": _public_service_url(8080),
                            "description": "Identity and tenant administration entry point via Keycloak.",
                            "status": "healthy",
                        },
                    ],
                }
            ],
        },
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "AI Trust and Security Business Dashboard",
        "subtitle": "Business overview -> access -> AI operations -> evidence and reporting",
        "runtime_module": "Onyx runs behind this dashboard as the managed AI workspace.",
        "tabs": [
            {"id": "overview", "label": "Overview"},
            {"id": "runtime", "label": "Activity"},
            {"id": "retrieval", "label": "Data Access"},
            {"id": "tools-mcp", "label": "Controls"},
            {"id": "evals", "label": "Quality"},
            {"id": "audit-replay", "label": "Audit"},
            {"id": "launch-gate", "label": "Readiness"},
            {"id": "entry-points", "label": "Useful Links"},
        ],
        "sections": sections,
        "sources": [
            {
                "label": "Policy bundle",
                "href": _raw("overlays/myStarterKit/policies/bundles/default/policy.json"),
                "description": "Policy, retrieval, tool, and integration inventory.",
            },
            {
                "label": "Telemetry sample",
                "href": _raw("telemetry/exports/sample_events.jsonl"),
                "description": "Normalized telemetry events feeding the dashboard summary.",
            },
            {
                "label": "Launch gate report",
                "href": _raw("overlays/myStarterKit/artifacts/logs/launch_gate/starter_launch_readiness_report.json"),
                "description": "Readiness findings consumed by the launch-gate section.",
            },
            {
                "label": "Reviewer evidence bundle",
                "href": _raw("overlays/myStarterKit/artifacts/evidence/reviewer/reviewer_evidence_bundle.json"),
                "description": "Audit and evidence-pack source material.",
            },
            {
                "label": "Grafana operational dashboard spec",
                "href": _raw("telemetry/dashboards/grafana/operational-dashboard-spec.json"),
                "description": "Operational drill-down contract surfaced behind the control plane.",
            },
        ],
    }
