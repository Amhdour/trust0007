from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

from .interfaces import ToolPolicyEvaluator
from .schemas import ToolActionRequest, ToolDecision


@dataclass(frozen=True)
class ToolPolicyConfig:
    tool_allowlist: Set[str] = field(default_factory=set)
    confirmation_required_tools: Set[str] = field(default_factory=set)
    forbidden_tools: Set[str] = field(default_factory=set)
    forbidden_arguments: Set[str] = field(default_factory=set)
    high_risk_tools: Set[str] = field(default_factory=set)
    rate_limit_hints: Dict[str, str] = field(default_factory=dict)


class StaticToolPolicyEvaluator(ToolPolicyEvaluator):
    """Policy-driven evaluator with static config for local development."""

    def __init__(self, config: ToolPolicyConfig) -> None:
        self._cfg = config

    def evaluate(self, request: ToolActionRequest) -> ToolDecision:
        reasons: List[str] = []
        risk_level = "high" if request.tool_name in self._cfg.high_risk_tools else "low"
        rate_limit_hint = self._cfg.rate_limit_hints.get(request.tool_name, "")
        rate_limit_key = f"{request.tenant_id}:{request.tool_name}"

        if request.tool_name in self._cfg.forbidden_tools:
            reasons.append("forbidden_tool")
            return ToolDecision(
                status="deny",
                reason_codes=reasons,
                risk_level=risk_level,
                rate_limit_key=rate_limit_key,
                rate_limit_hint=rate_limit_hint,
            )

        if request.tool_name not in self._cfg.tool_allowlist and request.tool_name not in self._cfg.confirmation_required_tools:
            reasons.append("tool_not_allowlisted")
            return ToolDecision(
                status="deny",
                reason_codes=reasons,
                risk_level=risk_level,
                rate_limit_key=rate_limit_key,
                rate_limit_hint=rate_limit_hint,
            )

        forbidden_args = [k for k in request.arguments.keys() if k in self._cfg.forbidden_arguments]
        if forbidden_args:
            reasons.append("forbidden_arguments")
            return ToolDecision(
                status="deny",
                reason_codes=reasons + [f"arg:{a}" for a in forbidden_args],
                risk_level=risk_level,
                rate_limit_key=rate_limit_key,
                rate_limit_hint=rate_limit_hint,
            )

        if request.tool_name in self._cfg.confirmation_required_tools and not request.confirmed:
            reasons.append("confirmation_required")
            return ToolDecision(
                status="confirm_required",
                reason_codes=reasons,
                risk_level=risk_level,
                rate_limit_key=rate_limit_key,
                rate_limit_hint=rate_limit_hint,
            )

        return ToolDecision(
            status="allow",
            reason_codes=reasons,
            risk_level=risk_level,
            rate_limit_key=rate_limit_key,
            rate_limit_hint=rate_limit_hint,
        )


def default_policy_config() -> ToolPolicyConfig:
    return ToolPolicyConfig(
        tool_allowlist={"search", "retrieve", "summarize", "ticket.read"},
        confirmation_required_tools={"ticket.create", "email.send", "payment.charge"},
        forbidden_tools={"shell.exec", "db.drop", "http.post.untrusted"},
        forbidden_arguments={"password", "api_key", "token", "secret"},
        high_risk_tools={"payment.charge", "shell.exec", "email.send"},
        rate_limit_hints={
            "payment.charge": "5/min",
            "email.send": "30/min",
            "ticket.create": "20/min",
        },
    )
