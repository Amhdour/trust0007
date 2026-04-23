from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from .policy_engine import PolicyAsCodeEngine
from .readiness import compute_runtime_readiness
from .runtime_registry import runtime_descriptor
from .schemas import LaunchDecisionExplanation


@dataclass(frozen=True)
class GovernedLaunchRequest:
    runtime_id: str
    tenant_id: str
    actor_id: str
    requested_path: str
    auth_mode: str
    purpose: str
    retrieval_source: str = ""
    source_classification: str = "internal"
    actor_clearance: str = "internal"
    mcp_server: str = ""
    tool_id: str = ""
    tool_risk: str = "low"
    action_type: str = ""
    approved: bool = False
    launch_request_id: str = field(default_factory=lambda: f"launch-{uuid.uuid4().hex[:12]}")


@dataclass(frozen=True)
class GovernedLaunchPlan:
    request: GovernedLaunchRequest
    explanation: LaunchDecisionExplanation
    policy_traces: list[dict[str, Any]]
    evidence: dict[str, Any]

    @property
    def allow(self) -> bool:
        return self.explanation.status == "allow"

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow": self.allow,
            "request": self.request.__dict__,
            "explanation": self.explanation.to_dict(),
            "policy_traces": self.policy_traces,
            "evidence": self.evidence,
        }


class OnyxGovernanceLane:
    """Governed Onyx launch lane for chat, search, and RAG access.

    Onyx is treated as a runtime behind data-boundary and retrieval policy,
    never as an unrestricted direct target.
    """

    runtime_id = "onyx"

    def __init__(self, policy_engine: PolicyAsCodeEngine) -> None:
        self._policy = policy_engine

    def plan_launch(self, request: GovernedLaunchRequest, *, root=None) -> GovernedLaunchPlan:
        readiness = compute_runtime_readiness(root, runtime_id=self.runtime_id)
        retrieval_trace = self._policy.evaluate_retrieval_access(
            {
                "tenant_id": request.tenant_id,
                "source": request.retrieval_source or "qdrant",
                "source_classification": request.source_classification,
                "actor_clearance": request.actor_clearance,
                "purpose": request.purpose,
            }
        )
        allow = readiness.launch_allowed and retrieval_trace.allow
        reasons = []
        if not readiness.launch_allowed:
            reasons.extend(readiness.blockers or [f"readiness.{readiness.state.value.lower()}"])
        if not retrieval_trace.allow:
            reasons.extend(retrieval_trace.reason_codes)
        explanation = LaunchDecisionExplanation(
            decision_id=retrieval_trace.decision_id,
            launch_request_id=request.launch_request_id,
            runtime_id=self.runtime_id,
            status="allow" if allow else "deny",
            readiness_state=readiness.state,
            reason_codes=reasons or ["policy.allow"],
            evidence_refs=[ref for signal in readiness.signals for ref in signal.evidence_refs],
        )
        return GovernedLaunchPlan(
            request=request,
            explanation=explanation,
            policy_traces=[retrieval_trace.to_dict()],
            evidence={"readiness": readiness.to_dict(), "auth_mode": request.auth_mode},
        )


class OnyxAgentGovernanceLane:
    """Governed Onyx launch lane for agentic and MCP/tool execution.

    Agentic execution remains inside the Onyx governed runtime model. Tool and
    MCP access are authorized by control-plane policy before the handoff.
    """

    runtime_id = "onyx"

    def __init__(self, policy_engine: PolicyAsCodeEngine) -> None:
        self._policy = policy_engine

    def plan_launch(self, request: GovernedLaunchRequest, *, root=None) -> GovernedLaunchPlan:
        readiness = compute_runtime_readiness(root, runtime_id=self.runtime_id)
        tool_trace = self._policy.evaluate_tool_authorization(
            {
                "runtime_id": self.runtime_id,
                "mcp_server": request.mcp_server,
                "tool_id": request.tool_id or "onyx.agent",
                "risk": request.tool_risk,
                "action_type": request.action_type,
                "approved": request.approved,
            }
        )
        allow = readiness.launch_allowed and tool_trace.allow
        reasons = []
        if not readiness.launch_allowed:
            reasons.extend(readiness.blockers or [f"readiness.{readiness.state.value.lower()}"])
        if not tool_trace.allow:
            reasons.extend(tool_trace.reason_codes)
        explanation = LaunchDecisionExplanation(
            decision_id=tool_trace.decision_id,
            launch_request_id=request.launch_request_id,
            runtime_id=self.runtime_id,
            status="allow" if allow else "deny",
            readiness_state=readiness.state,
            reason_codes=reasons or ["policy.allow"],
            evidence_refs=[ref for signal in readiness.signals for ref in signal.evidence_refs],
        )
        return GovernedLaunchPlan(
            request=request,
            explanation=explanation,
            policy_traces=[tool_trace.to_dict()],
            evidence={
                "readiness": readiness.to_dict(),
                "agent_workflow_registration": {
                    "runtime_id": self.runtime_id,
                    "requested_path": request.requested_path,
                    "mcp_server": request.mcp_server,
                    "tool_id": request.tool_id,
                    "risk": request.tool_risk,
                },
            },
        )
