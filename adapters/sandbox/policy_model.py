from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Set

from .interfaces import SandboxPolicyEvaluator
from .schemas import SandboxDecision, SandboxExecutionRequest


@dataclass(frozen=True)
class SandboxPolicyConfig:
    deny_actions: Set[str] = field(default_factory=set)
    risky_tools: Set[str] = field(default_factory=set)
    risky_actions: Set[str] = field(default_factory=set)
    policy_ref: str = "sandbox.policy.v1"


class StaticSandboxPolicyEvaluator(SandboxPolicyEvaluator):
    """Local-development risk policy for deny vs sandbox vs allow."""

    def __init__(self, config: SandboxPolicyConfig) -> None:
        self._cfg = config

    def evaluate(self, request: SandboxExecutionRequest) -> SandboxDecision:
        reasons: List[str] = []
        risk_score = 0

        if request.action_type in self._cfg.deny_actions:
            return SandboxDecision(
                mode="deny",
                reasons=["action_denied_by_policy"],
                risk_score=100,
                policy_ref=self._cfg.policy_ref,
            )

        if request.action_type in self._cfg.risky_actions:
            reasons.append("risky_action_type")
            risk_score += 30

        if request.tool_name in self._cfg.risky_tools:
            reasons.append("risky_tool")
            risk_score += 25

        if request.code_supplied_by_user:
            reasons.append("user_supplied_code")
            risk_score += 25

        if request.network_access:
            reasons.append("network_access")
            risk_score += 10

        if request.filesystem_write:
            reasons.append("filesystem_write")
            risk_score += 10

        if request.external_integration:
            reasons.append("external_integration")
            risk_score += 10

        if risk_score >= 30:
            return SandboxDecision(
                mode="sandbox",
                reasons=reasons,
                risk_score=risk_score,
                policy_ref=self._cfg.policy_ref,
            )

        return SandboxDecision(
            mode="allow",
            reasons=reasons,
            risk_score=risk_score,
            policy_ref=self._cfg.policy_ref,
        )


def default_sandbox_policy_config() -> SandboxPolicyConfig:
    return SandboxPolicyConfig(
        deny_actions={"kernel_escape_attempt", "privilege_escalation"},
        risky_tools={"shell.exec", "python.exec", "container.exec"},
        risky_actions={"code_execution", "system_modification", "network_probe"},
    )
