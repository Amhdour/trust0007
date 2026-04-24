from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.integration_adapter.repository import repo_root

from .enums import DestructiveRisk, RepairPolicyStatus
from .models import RemediationAction, RepairPolicyDecision, new_id


DEFAULT_REPAIR_POLICY = {
    "deny_by_default": True,
    "demo_evidence_counts_for_live_readiness": False,
    "production_requires_elevated_role_for": ["resync_policy_bundle", "rotate_nonhuman_runtime_credential", "restart_local_service"],
    "allowed_without_approval": [
        "recheck_health",
        "reprobe_routes",
        "retry_governed_handoff",
        "refresh_runtime_proof",
        "refresh_evidence_bundle",
        "re_evaluate_launch_gate",
        "validate_runtime_config",
        "validate_dependency_connectivity",
        "surface_precise_blocker",
    ],
    "allowed_with_approval": [
        "mark_lane_degraded",
        "quarantine_lane",
        "restart_local_service",
        "reload_runtime_config",
        "rotate_nonhuman_runtime_credential",
        "reseed_nonprod_test_data",
        "resync_policy_bundle",
    ],
}


class RepairPolicyEngine:
    def __init__(self, document: dict[str, Any]) -> None:
        self.document = document
        self.repair_policy = document.get("repair_actions", DEFAULT_REPAIR_POLICY) or DEFAULT_REPAIR_POLICY

    @classmethod
    def from_repo(cls, root: Path | None = None) -> "RepairPolicyEngine":
        path = repo_root(root) / "policies/control-plane/default-governance-policy.json"
        if path.exists():
            return cls(json.loads(path.read_text(encoding="utf-8")))
        return cls({"repair_actions": DEFAULT_REPAIR_POLICY})

    def evaluate_action(
        self,
        action: RemediationAction,
        *,
        tenant_id: str,
        actor_id: str,
        actor_roles: list[str] | None = None,
        environment: str = "dev",
        approved: bool = False,
        evidence_mode: str = "live",
    ) -> RepairPolicyDecision:
        roles = set(actor_roles or [])
        env = environment.strip().lower() or "dev"
        action_id = action.action_id
        reasons: list[str] = []
        basis = [
            "repair.deny_by_default",
            f"repair.policy_check:{action.policy_check_name}",
            "repair.no_launch_gate_override",
        ]

        if evidence_mode == "demo":
            basis.append("repair.demo_evidence_not_live_readiness")

        if env not in {item.lower() for item in action.allowed_environments}:
            reasons.append(f"repair.environment_not_allowed:{env}")

        allowed_without = set(self.repair_policy.get("allowed_without_approval", []))
        allowed_with = set(self.repair_policy.get("allowed_with_approval", []))
        if action_id not in allowed_without and action_id not in allowed_with:
            reasons.append(f"repair.action_not_allowed:{action_id}")

        requires_approval = action.requires_approval or action_id in allowed_with or action.destructive_risk in {
            DestructiveRisk.MEDIUM,
            DestructiveRisk.HIGH,
        }
        if requires_approval and not approved:
            reasons.append(f"repair.approval_required:{action_id}")

        if env in {"production", "prod", "live"} and action_id in set(self.repair_policy.get("production_requires_elevated_role_for", [])):
            if "repair_admin" not in roles and "security_admin" not in roles:
                reasons.append(f"repair.elevated_role_required:{action_id}")

        if action.destructive_risk == DestructiveRisk.HIGH and not approved:
            reasons.append(f"repair.high_risk_requires_approval:{action_id}")

        if reasons:
            status = RepairPolicyStatus.REQUIRE_APPROVAL if any("approval_required" in reason for reason in reasons) else RepairPolicyStatus.DENY
        else:
            status = RepairPolicyStatus.ALLOW

        return RepairPolicyDecision(
            decision_id=new_id("repair-policy-decision"),
            action_id=action_id,
            lane=action.lane,
            tenant_id=tenant_id,
            actor_id=actor_id,
            status=status,
            reason_codes=reasons or ["repair.policy.allow"],
            policy_basis=basis,
            requires_approval=requires_approval,
            approved=approved,
            environment=env,
        )
