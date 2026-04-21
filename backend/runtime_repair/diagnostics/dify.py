from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import DiagnosticContext, RuntimeDiagnosticAdapter, RuntimeRouteConfig
from ..enums import FailureCategory, FreshnessStatus, RuntimeLane, Severity


def dify_route_config(root: Path | None = None) -> RuntimeRouteConfig:
    port = os.environ.get("CONTROL_PLANE_DIFY_PORT", "8088").strip() or "8088"
    local_base = os.environ.get("CONTROL_PLANE_DIFY_BASE_URL", f"http://127.0.0.1:{port}").strip().rstrip("/")
    public_base = os.environ.get("CONTROL_PLANE_DIFY_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if not public_base:
        codespace = os.environ.get("CODESPACE_NAME", "").strip()
        domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "").strip()
        public_base = f"https://{codespace}-{port}.{domain}" if codespace and domain else f"http://localhost:{port}"
    return RuntimeRouteConfig(
        lane=RuntimeLane.DIFY,
        runtime_id="dify",
        label="Dify",
        default_path="/apps",
        local_base_url=local_base,
        public_base_url=public_base,
        expected_routes=["/apps", "/apps/workflows", "/apps/tools", "/health", "/api/health"],
        proof_path="overlays/myStarterKit/artifacts/dify-runtime-proof.json",
    )


class DifyDiagnosticAdapter(RuntimeDiagnosticAdapter):
    def __init__(self, config: RuntimeRouteConfig | None = None) -> None:
        super().__init__(config or dify_route_config())

    def _lane_specific_findings(
        self,
        context: DiagnosticContext,
        bundle: Any,
        readiness: dict[str, Any],
        runtime_proof: dict[str, Any],
    ):
        findings = []
        tool_doc = bundle.tool
        denied_tools = list(tool_doc.get("denied_tools", []))
        approval_required = list(tool_doc.get("approval_required_tools", [])) or list(tool_doc.get("requires_approval", []))
        mcp_governed = bool(tool_doc.get("mcp_governed", False))
        if not tool_doc:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.TOOLS_MCP,
                    "Dify tool/MCP posture evidence is absent",
                    "Dify cannot run as a governed execution plane without MCP/tool posture evidence.",
                    evidence_used=[bundle.evidence_refs().get("tool", "")],
                    freshness=FreshnessStatus.MISSING,
                    reason_codes=["tools_mcp.evidence_missing"],
                )
            )
        elif denied_tools:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.TOOLS_MCP,
                    "MCP/tool policy violations detected",
                    "Dify requested tools that are not allowed by the governed MCP/tool policy.",
                    evidence_used=[bundle.evidence_refs().get("tool", "")],
                    reason_codes=[f"tools_mcp.denied:{tool}" for tool in denied_tools],
                    details={"denied_tools": denied_tools},
                )
            )
        elif approval_required:
            findings.append(
                self._finding(
                    context,
                    Severity.HIGH,
                    FailureCategory.TOOLS_MCP,
                    "Privileged Dify tool requires approval",
                    "Dify has a privileged or external-write tool request that requires explicit approval.",
                    evidence_used=[bundle.evidence_refs().get("tool", "")],
                    reason_codes=[f"tools_mcp.approval_required:{tool}" for tool in approval_required],
                    details={"approval_required_tools": approval_required},
                )
            )
        elif not mcp_governed:
            findings.append(
                self._finding(
                    context,
                    Severity.CRITICAL,
                    FailureCategory.TOOLS_MCP,
                    "Dify MCP governance is not proven",
                    "Dify tool posture does not show an MCP allowlist-governed execution path.",
                    evidence_used=[bundle.evidence_refs().get("tool", "")],
                    reason_codes=["tools_mcp.not_governed"],
                    details=tool_doc,
                )
            )
        proof_path = str(runtime_proof.get("requested_path", ""))
        if proof_path and proof_path not in {"/apps", "/apps/", "/apps/workflows", "/apps/tools"}:
            findings.append(
                self._finding(
                    context,
                    Severity.WARNING,
                    FailureCategory.CONFIG_DRIFT,
                    "Dify runtime proof path differs from expected app/workspace routes",
                    "The latest Dify proof was generated for a path outside the governed agent workspace lane.",
                    evidence_used=[self.config.proof_path],
                    reason_codes=["config_drift.dify_path"],
                    details={"observed_path": proof_path, "expected": ["/apps", "/apps/workflows", "/apps/tools"]},
                )
            )
        return findings
