from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .schemas import PolicyDecisionTrace


CLASSIFICATION_RANK = {
    "public": 0,
    "internal": 1,
    "confidential": 2,
    "restricted": 3,
    "high": 3,
    "secret": 4,
}


def _decision_id() -> str:
    return f"decision-{uuid.uuid4().hex[:12]}"


def _rank(value: str) -> int:
    return CLASSIFICATION_RANK.get(str(value).strip().lower(), 99)


@dataclass(frozen=True)
class MachineReadablePolicy:
    policy_id: str
    version: str
    document: dict[str, Any]
    source_path: str


class PolicyAsCodeEngine:
    """Small inspectable policy engine for local control-plane decisions.

    This is intentionally deterministic and deny-by-default. Live deployments can
    still delegate to OPA for request-path enforcement; this engine provides the
    typed control-plane and unit-testable policy model used by readiness APIs.
    """

    def __init__(self, policy: MachineReadablePolicy) -> None:
        self._policy = policy

    @classmethod
    def from_file(cls, path: Path) -> "PolicyAsCodeEngine":
        document = json.loads(path.read_text(encoding="utf-8"))
        metadata = document.get("policy_metadata", {})
        policy = MachineReadablePolicy(
            policy_id=str(metadata.get("policy_id", "trust-readiness-default")),
            version=str(metadata.get("version", "v1")),
            document=document,
            source_path=str(path),
        )
        return cls(policy)

    @property
    def policy(self) -> MachineReadablePolicy:
        return self._policy

    def evaluate_retrieval_access(self, request: dict[str, Any]) -> PolicyDecisionTrace:
        rules = ["retrieval.default_deny"]
        tenant_id = str(request.get("tenant_id", ""))
        source = str(request.get("source", ""))
        source_classification = str(request.get("source_classification", "restricted"))
        actor_clearance = str(request.get("actor_clearance", "public"))
        purpose = str(request.get("purpose", ""))
        retrieval_policy = self._policy.document.get("retrieval", {})
        tenant_sources = retrieval_policy.get("tenant_allowed_sources", {}).get(tenant_id, [])
        approved_purposes = retrieval_policy.get("approved_purposes", [])

        reasons: list[str] = []
        if not tenant_id:
            reasons.append("tenant.missing")
        if not source or source not in tenant_sources:
            reasons.append(f"retrieval.source_not_allowed:{source or 'missing'}")
        rules.append("retrieval.tenant_source_boundary")

        if _rank(source_classification) > _rank(actor_clearance):
            reasons.append(f"retrieval.clearance_insufficient:{source_classification}")
        rules.append("retrieval.classification_clearance")

        if approved_purposes and purpose not in approved_purposes:
            reasons.append(f"retrieval.purpose_not_approved:{purpose or 'missing'}")
        rules.append("retrieval.purpose_binding")

        return PolicyDecisionTrace(
            decision_id=_decision_id(),
            policy_id=self._policy.policy_id,
            status="deny" if reasons else "allow",
            default_deny=bool(reasons),
            reason_codes=reasons or ["policy.allow"],
            evaluated_rules=rules,
            inputs={
                "tenant_id": tenant_id,
                "source": source,
                "source_classification": source_classification,
                "actor_clearance": actor_clearance,
                "purpose": purpose,
            },
        )

    def evaluate_tool_authorization(self, request: dict[str, Any]) -> PolicyDecisionTrace:
        rules = ["tools.default_deny"]
        runtime_id = str(request.get("runtime_id", "onyx"))
        mcp_server = str(request.get("mcp_server", ""))
        tool_id = str(request.get("tool_id", ""))
        risk = str(request.get("risk", "high"))
        action_type = str(request.get("action_type", ""))
        approved = bool(request.get("approved", False))
        controls = self._policy.document.get("runtime_controls", {}).get(runtime_id, {})
        allowed_mcp = set(controls.get("mcp_allowed_servers", []))
        allowed_tools = set(self._policy.document.get("tools", {}).get("allowed_tools", []))
        approval_required_tools = set(controls.get("approval_required_tools", [])) | set(
            self._policy.document.get("tools", {}).get("confirmation_required_tools", [])
        )
        privileged_actions = set(controls.get("approval_required_actions", []))

        reasons: list[str] = []
        if bool(controls.get("require_mcp_governance", False)) and mcp_server not in allowed_mcp:
            reasons.append(f"policy.mcp_server_not_allowed:{mcp_server or 'missing'}")
        rules.append("onyx.mcp_server_allowlist")

        if tool_id not in allowed_tools and tool_id not in approval_required_tools:
            reasons.append(f"tool.not_allowed:{tool_id or 'missing'}")
        rules.append("tools.allowlist")

        requires_approval = (
            tool_id in approval_required_tools
            or action_type in privileged_actions
            or risk in {"high", "critical"}
        )
        if requires_approval and not approved:
            reasons.append(f"tool.approval_required:{tool_id or action_type or 'unknown'}")
        rules.append("tools.privileged_approval")

        return PolicyDecisionTrace(
            decision_id=_decision_id(),
            policy_id=self._policy.policy_id,
            status="deny" if reasons else "allow",
            default_deny=bool(reasons),
            reason_codes=reasons or ["policy.allow"],
            evaluated_rules=rules,
            inputs={
                "runtime_id": runtime_id,
                "mcp_server": mcp_server,
                "tool_id": tool_id,
                "risk": risk,
                "action_type": action_type,
                "approved": approved,
            },
        )

    def evaluate_secret_health(self, evidence: dict[str, Any]) -> PolicyDecisionTrace:
        rules = ["secrets.backend_health", "secrets.required_secret_present"]
        required = bool(evidence.get("required", False))
        fetched = bool(evidence.get("fetched", False))
        backend_available = bool(evidence.get("backend_available", evidence.get("backend_configured", False)))
        reasons: list[str] = []
        if required and not backend_available:
            reasons.append("secret.backend_unhealthy")
        if required and not fetched:
            reasons.append("secret.required_not_satisfied")
        return PolicyDecisionTrace(
            decision_id=_decision_id(),
            policy_id=self._policy.policy_id,
            status="deny" if reasons else "allow",
            default_deny=bool(reasons),
            reason_codes=reasons or ["policy.allow"],
            evaluated_rules=rules,
            inputs={"required": required, "fetched": fetched, "backend_available": backend_available},
        )

    def evaluate_launch_gate(self, evidence: dict[str, Any]) -> PolicyDecisionTrace:
        rules = ["launch.evidence_freshness", "launch.telemetry_health", "launch.audit_health"]
        reasons: list[str] = []
        stale_signals = [key for key, value in evidence.get("freshness", {}).items() if value == "stale"]
        if stale_signals:
            reasons.extend(f"launch.evidence_stale:{signal}" for signal in stale_signals)
        if not evidence.get("telemetry_healthy", False):
            reasons.append("launch.telemetry_unhealthy")
        if not evidence.get("audit_healthy", False):
            reasons.append("launch.audit_unhealthy")
        if evidence.get("human_approval_required", False) and not evidence.get("human_approved", False):
            reasons.append("launch.human_approval_required")

        return PolicyDecisionTrace(
            decision_id=_decision_id(),
            policy_id=self._policy.policy_id,
            status="deny" if reasons else "allow",
            default_deny=bool(reasons),
            reason_codes=reasons or ["policy.allow"],
            evaluated_rules=rules,
            inputs={
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
                "evidence": evidence,
            },
        )
