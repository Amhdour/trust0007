"""Reusable governed flow evaluator for control-plane demonstrations.

This module extracts the demo_flow logic into a composable, testable class
that can be invoked from the API gateway or test harnesses.

The flow is:
1. Identity context (user, tenant)
2. Policy check through gateway adapter
3. Retrieval decision and document filtering
4. Tool decision and governance
5. Launch-gate evidence generation
6. Artifact storage to configured directory (default: overlay path)
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from adapters.onyx_gateway_adapter.adapter import OnyxGatewayAdapter
from adapters.onyx_gateway_adapter.interfaces import PolicyChecker, RetrievalChecker, ToolDecisionChecker
from adapters.onyx_gateway_adapter.schemas import NormalizedRequest
from adapters.onyx_gateway_adapter.telemetry import InMemoryTelemetryEmitter
from adapters.retrieval.engine import RetrievalSecurityLayer
from adapters.retrieval.interfaces import InMemoryRetrievalTelemetry, RetrievalBackend, RetrievalPolicyEvaluator
from adapters.retrieval.schemas import RetrievalDocument, RetrievalRequest
from adapters.tools.engine import ToolGovernanceEngine
from adapters.tools.interfaces import InMemoryAuditSink, ToolExecutor
from adapters.tools.policy_model import StaticToolPolicyEvaluator, default_policy_config
from adapters.tools.schemas import ToolActionRequest
from launch_gate.evaluator import default_controls, evaluate_launch_gate
from telemetry.model import EventModel
from telemetry.sinks import JsonlEventSink


@dataclass
class GovernedFlowResult:
    """Result of a governed flow execution with artifact paths and decision data."""

    decision: bool
    trace_id: str
    request_id: str
    launch_gate_decision: str
    launch_gate_score: int
    launch_gate_max_score: int
    launch_gate_blockers: list[str]
    launch_gate_missing_evidence: list[str]
    artifacts: dict[str, str]  # artifact_name -> path (relative to repo root)

    def to_dict(self) -> dict:
        """Serialize to dict for JSON responses."""
        return {
            "decision": self.decision,
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "launch_gate": {
                "decision": self.launch_gate_decision,
                "score": self.launch_gate_score,
                "max_score": self.launch_gate_max_score,
                "blockers": self.launch_gate_blockers,
                "missing_evidence": self.launch_gate_missing_evidence,
            },
            "artifacts": self.artifacts,
        }


class GovernedFlowEvaluator:
    """Orchestrate a complete governed request flow with live artifact generation."""

    def __init__(
        self,
        policy_checker: PolicyChecker,
        retrieval_checker: RetrievalChecker,
        tool_checker: ToolDecisionChecker,
        retrieval_backend: RetrievalBackend,
        retrieval_policy: RetrievalPolicyEvaluator,
        tool_executor: ToolExecutor,
        artifact_dir: Optional[Path] = None,
    ):
        """Initialize the flow evaluator with governance components.

        Args:
            policy_checker: Evaluates policy constraints on requests.
            retrieval_checker: Evaluates retrieval permissions.
            tool_checker: Evaluates tool-level governance.
            retrieval_backend: Document retrieval backend.
            retrieval_policy: Retrieval policy evaluation.
            tool_executor: Tool execution engine.
            artifact_dir: Directory to write artifacts. Defaults to overlays/myStarterKit/artifacts/.
        """
        self._policy_checker = policy_checker
        self._retrieval_checker = retrieval_checker
        self._tool_checker = tool_checker
        self._retrieval_backend = retrieval_backend
        self._retrieval_policy = retrieval_policy
        self._tool_executor = tool_executor

        if artifact_dir is None:
            # Default to overlay path
            repo_root = Path(__file__).resolve().parent.parent
            artifact_dir = repo_root / "overlays" / "myStarterKit" / "artifacts"

        self._artifact_dir = artifact_dir.resolve()

    def run(
        self,
        user_id: str,
        tenant_id: str,
        prompt: str,
        requested_tools: list[str],
        retrieval_source: str = "qdrant",
        retrieval_needed: bool = True,
    ) -> GovernedFlowResult:
        """Execute the full governed flow and return decision + artifacts.

        This is the main entry point for running a governed request through
        the control-plane pipeline. All governance decisions are made and
        telemetry is emitted.

        Args:
            user_id: User identifier.
            tenant_id: Tenant identifier.
            prompt: User-provided prompt/query.
            requested_tools: List of tool names user/LLM requested.
            retrieval_source: Which retrieval backend (default: qdrant).
            retrieval_needed: Whether to perform retrieval.

        Returns:
            GovernedFlowResult with decision outcome and artifact paths.
        """
        # Generate unique identifiers for this flow
        trace_id = f"flow-{uuid.uuid4().hex[:12]}"
        request_id = f"req-{uuid.uuid4().hex[:12]}"

        # Ensure artifact directory exists
        self._artifact_dir.mkdir(parents=True, exist_ok=True)
        events_path = self._artifact_dir / "events.jsonl"
        launch_gate_path = self._artifact_dir / "launch-gate-result.json"

        # Clean up old artifacts if they exist
        if events_path.exists():
            events_path.unlink()

        # Set up telemetry
        model = EventModel()
        sink = JsonlEventSink(str(events_path))

        # Helper to emit events consistently
        def emit(event_type: str, payload: dict) -> None:
            sink.emit(
                model.create(
                    event_type=event_type,
                    trace_id=trace_id,
                    request_id=request_id,
                    payload=payload,
                    tenant_id=tenant_id,
                    severity="info",
                )
            )

        # 1) Identity established
        identity = {"sub": user_id, "tenant_id": tenant_id, "roles": ["tenant_user"]}
        emit("request.start", {"path": "/governed-flow", "user_id": user_id})
        emit("identity.established", identity)

        # 2) Policy check through gateway adapter
        gateway = OnyxGatewayAdapter(
            policy_checker=self._policy_checker,
            retrieval_checker=self._retrieval_checker,
            tool_checker=self._tool_checker,
            telemetry_emitter=InMemoryTelemetryEmitter(),  # Gateway emits to its own in-memory store
        )

        normalized_request = NormalizedRequest(
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            prompt=prompt,
            requested_tools=requested_tools,
            retrieval_needed=retrieval_needed,
            retrieval_source=retrieval_source,
            metadata={"trace_id": trace_id},
        )

        gateway_decision = gateway.evaluate(normalized_request)
        emit("policy.decision", {"allow": gateway_decision.policy_allow, "reasons": gateway_decision.reasons})

        # 3) Retrieval decision
        retrieval_decision_made = False
        filtered_docs_count = 0

        if retrieval_needed and gateway_decision.retrieval_allow:
            retrieval_layer = RetrievalSecurityLayer(
                backend=self._retrieval_backend,
                policy_evaluator=self._retrieval_policy,
                telemetry=InMemoryRetrievalTelemetry(),
            )

            retrieval_result = retrieval_layer.evaluate(
                RetrievalRequest(
                    request_id=request_id,
                    tenant_id=tenant_id,
                    source=retrieval_source,
                    query=prompt,
                    trust_labels=["trusted"],
                )
            )

            retrieval_decision_made = True
            filtered_docs_count = len(retrieval_result.filtered_documents)
            emit(
                "retrieval.decision",
                {
                    "decision": retrieval_result.mode,
                    "source": retrieval_source,
                    "docs_filtered": filtered_docs_count,
                },
            )

        if retrieval_decision_made:
            emit("retrieval.decision", {"result": "completed"})
        else:
            emit("retrieval.decision", {"result": "skipped"})

        # 4) Tool execution decision
        tools_allowed = []
        tools_denied = gateway_decision.denied_tools

        if gateway_decision.allow and not tools_denied:
            tool_engine = ToolGovernanceEngine(
                policy_evaluator=StaticToolPolicyEvaluator(default_policy_config()),
                executor=self._tool_executor,
                audit_sink=InMemoryAuditSink(),
            )

            for tool_name in requested_tools:
                result = tool_engine.evaluate(
                    ToolActionRequest(
                        request_id=request_id,
                        tenant_id=tenant_id,
                        user_id=user_id,
                        tool_name=tool_name,
                        arguments={"query": prompt},
                    )
                )
                if result.status == "allowed":
                    tools_allowed.append(tool_name)
                    emit(
                        "tool.execution_attempt",
                        {"tool_name": tool_name, "status": "executed"},
                    )
                else:
                    tools_denied.append(tool_name)
                    emit("tool.execution_attempt", {"tool_name": tool_name, "status": "denied"})

        emit(
            "tool.decision",
            {
                "allowed": tools_allowed,
                "denied": tools_denied,
            },
        )

        # 5) Fallback/deny hooks (not triggered in happy path)
        emit("fallback.event", {"applied": False})
        emit("deny.event", {"blocked": not gateway_decision.allow})
        emit("incident.signal", {"signal": "none"})

        # End request
        emit("request.end", {"status": "ok", "decision": gateway_decision.allow})

        # 6) Launch-gate evaluation
        evidence = {
            "policy.decision": True,
            "retrieval.decision": retrieval_decision_made,
            "tool.decision": True,
            "incident.signal": True,
        }

        gate_result = evaluate_launch_gate(evidence=evidence, controls=default_controls())

        launch_gate_artifact = {
            "machine": gate_result.to_machine_readable(),
            "human": gate_result.to_human_readable(),
            "flow_metadata": {
                "trace_id": trace_id,
                "request_id": request_id,
                "artifacts": {"events_jsonl": str(events_path.relative_to(self._artifact_dir.parent.parent))},
            },
        }

        launch_gate_path.write_text(json.dumps(launch_gate_artifact, indent=2, sort_keys=True), encoding="utf-8")

        # Build result with relative artifact paths (from repo root)
        repo_root = Path(__file__).resolve().parent.parent
        relative_events = events_path.relative_to(repo_root)
        relative_gate = launch_gate_path.relative_to(repo_root)

        return GovernedFlowResult(
            decision=gateway_decision.allow,
            trace_id=trace_id,
            request_id=request_id,
            launch_gate_decision=gate_result.decision,
            launch_gate_score=gate_result.score,
            launch_gate_max_score=gate_result.max_score,
            launch_gate_blockers=gate_result.blockers,
            launch_gate_missing_evidence=gate_result.missing_evidence,
            artifacts={
                "events_jsonl": str(relative_events),
                "launch_gate_result": str(relative_gate),
            },
        )
