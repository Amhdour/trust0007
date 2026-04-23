from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from backend.trust_readiness.evidence import evidence_age_status, latest_timestamp

from .base import DiagnosticContext, RuntimeDiagnosticAdapter, RuntimeRouteConfig
from ..enums import FailureCategory, FreshnessStatus, RuntimeLane, Severity


def onyx_route_config(root: Path | None = None) -> RuntimeRouteConfig:
    port = os.environ.get("CONTROL_PLANE_ONYX_PORT", "3010").strip() or "3010"
    local_base = os.environ.get("CONTROL_PLANE_ONYX_BASE_URL", f"http://127.0.0.1:{port}").strip().rstrip("/")
    public_base = os.environ.get("CONTROL_PLANE_ONYX_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not public_base:
        codespace = os.environ.get("CODESPACE_NAME", "").strip()
        domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "").strip()
        public_base = f"https://{codespace}-{port}.{domain}" if codespace and domain else f"http://localhost:{port}"
    return RuntimeRouteConfig(
        lane=RuntimeLane.ONYX,
        runtime_id="onyx",
        label="Onyx",
        default_path="/app",
        local_base_url=local_base,
        public_base_url=public_base,
        expected_routes=["/app", "/app/", "/health", "/api/health"],
        proof_path="overlays/myStarterKit/artifacts/onyx-runtime-proof.json",
    )


class OnyxDiagnosticAdapter(RuntimeDiagnosticAdapter):
    def __init__(self, config: RuntimeRouteConfig | None = None) -> None:
        super().__init__(config or onyx_route_config())

    def _lane_specific_findings(
        self,
        context: DiagnosticContext,
        bundle: Any,
        readiness: dict[str, Any],
        runtime_proof: dict[str, Any],
    ):
        findings = []
        retrieval_allow = bool(bundle.retrieval.get("allow", False))
        retrieval_timestamp = latest_timestamp(bundle.retrieval)
        retrieval_age = evidence_age_status(retrieval_timestamp)
        if not bundle.retrieval:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.RETRIEVAL,
                    "Retrieval boundary proof is absent",
                    "Onyx launch repair cannot prove data-boundary enforcement without retrieval evidence.",
                    evidence_used=[bundle.evidence_refs().get("retrieval", "")],
                    freshness=FreshnessStatus.MISSING,
                    reason_codes=["retrieval.proof_missing"],
                )
            )
        elif not retrieval_allow:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.RETRIEVAL,
                    "Retrieval boundary policy is denying access",
                    "Onyx retrieval boundary evidence does not allow the current tenant/source purpose.",
                    evidence_used=[bundle.evidence_refs().get("retrieval", "")],
                    reason_codes=list(bundle.retrieval.get("reason_codes", []) or ["retrieval.denied"]),
                    details=bundle.retrieval,
                )
            )
        elif retrieval_age in {"stale", "missing"}:
            findings.append(
                self._finding(
                    context,
                    Severity.HIGH,
                    FailureCategory.RETRIEVAL,
                    "Retrieval proof is stale",
                    "Onyx has retrieval boundary proof, but it is too old for live readiness.",
                    evidence_used=[bundle.evidence_refs().get("retrieval", "")],
                    freshness=FreshnessStatus(retrieval_age),
                    reason_codes=[f"retrieval.proof_{retrieval_age}"],
                    details={"observed_at": retrieval_timestamp},
                )
            )
        denied_tools = [str(tool).strip() for tool in bundle.tool.get("denied_tools", []) if str(tool).strip()]
        if denied_tools:
            findings.append(
                self._finding(
                    context,
                    Severity.HIGH,
                    FailureCategory.TOOLS_MCP,
                    "Tool/MCP governance denied runtime actions",
                    "Onyx tool governance shows denied tool or MCP actions that block runtime workflows.",
                    evidence_used=[bundle.evidence_refs().get("tool", "")],
                    reason_codes=[f"tools_mcp.denied:{tool}" for tool in denied_tools],
                    details={"denied_tools": denied_tools, "tool_evidence": bundle.tool},
                )
            )
        proof_path = str(runtime_proof.get("requested_path", ""))
        if proof_path and proof_path not in {"/app", "/app/"}:
            findings.append(
                self._finding(
                    context,
                    Severity.WARNING,
                    FailureCategory.CONFIG_DRIFT,
                    "Onyx runtime proof path differs from expected launch lane",
                    "The latest Onyx proof was generated for a path outside the primary governed RAG lane.",
                    evidence_used=[self.config.proof_path],
                    reason_codes=["config_drift.onyx_path"],
                    details={"observed_path": proof_path, "expected": ["/app", "/app/"]},
                )
            )
        return findings
