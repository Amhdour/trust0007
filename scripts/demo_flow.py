#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from adapters.onyx_gateway_adapter.adapter import OnyxGatewayAdapter
from adapters.onyx_gateway_adapter.interfaces import PolicyChecker, RetrievalChecker, ToolDecisionChecker
from adapters.onyx_gateway_adapter.schemas import (
    NormalizedRequest,
    PolicyDecision,
    RetrievalDecision,
    ToolDecision,
)
from adapters.onyx_gateway_adapter.telemetry import InMemoryTelemetryEmitter
from adapters.retrieval.engine import RetrievalSecurityLayer
from adapters.retrieval.interfaces import InMemoryRetrievalTelemetry, RetrievalBackend, RetrievalPolicyEvaluator
from adapters.retrieval.schemas import RetrievalDocument, RetrievalRequest
from adapters.tools.engine import ToolGovernanceEngine
from adapters.tools.interfaces import InMemoryAuditSink, ToolExecutor
from adapters.tools.policy_model import StaticToolPolicyEvaluator, default_policy_config
from adapters.tools.schemas import ToolActionRequest
from telemetry.model import EventModel
from telemetry.sinks import JsonlEventSink


OUT_DIR = Path("artifacts/demo")
EVENTS_PATH = OUT_DIR / "events.jsonl"
LAUNCH_GATE_PATH = OUT_DIR / "launch-gate.json"


class DemoPolicyChecker(PolicyChecker):
    def check_policy(self, request: NormalizedRequest) -> PolicyDecision:
        return PolicyDecision(allow=True, reasons=[])


class DemoRetrievalChecker(RetrievalChecker):
    def check_retrieval(self, request: NormalizedRequest) -> RetrievalDecision:
        if request.retrieval_needed:
            return RetrievalDecision(allow=True, reasons=[])
        return RetrievalDecision(allow=True, reasons=[])


class DemoToolChecker(ToolDecisionChecker):
    def check_tools(self, request: NormalizedRequest) -> ToolDecision:
        return ToolDecision(allowed_tools=request.requested_tools, denied_tools=[], reasons=[])


class DemoRetrievalBackend(RetrievalBackend):
    def search(self, request: RetrievalRequest):
        return [
            RetrievalDocument(
                doc_id="demo-doc-1",
                tenant_id=request.tenant_id,
                source=request.source,
                content="Demo retrieval content.",
                trust_label="trusted",
                quarantined=False,
                provenance={"uri": "kb://demo-doc-1"},
            )
        ]


class DemoRetrievalPolicy(RetrievalPolicyEvaluator):
    def evaluate(self, request: RetrievalRequest) -> dict:
        return {"allow": True, "mode": "allow", "reasons": []}


class DemoToolExecutor(ToolExecutor):
    def execute(self, request: ToolActionRequest) -> dict:
        return {"result": "ok", "tool": request.tool_name}


def load_launch_gate_module():
    module_path = Path("launch-gate/evaluator.py")
    spec = importlib.util.spec_from_file_location("launch_gate_evaluator_demo", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def emit(model: EventModel, sink: JsonlEventSink, event_type: str, trace_id: str, request_id: str, payload: dict):
    sink.emit(
        model.create(
            event_type=event_type,
            trace_id=trace_id,
            request_id=request_id,
            payload=payload,
            tenant_id="tenant-a",
            severity="info",
        )
    )


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if EVENTS_PATH.exists():
        EVENTS_PATH.unlink()

    model = EventModel()
    sink = JsonlEventSink(str(EVENTS_PATH))

    trace_id = "demo-trace-1"
    request_id = "demo-req-1"

    # 1) identity
    identity = {"sub": "user-1", "tenant_id": "tenant-a", "roles": ["tenant_user"]}
    emit(model, sink, "request.start", trace_id, request_id, {"path": "/demo"})
    emit(model, sink, "identity.established", trace_id, request_id, identity)

    # 2) ingress + policy check through gateway adapter
    gateway = OnyxGatewayAdapter(
        policy_checker=DemoPolicyChecker(),
        retrieval_checker=DemoRetrievalChecker(),
        tool_checker=DemoToolChecker(),
        telemetry_emitter=InMemoryTelemetryEmitter(),
    )
    normalized_request = NormalizedRequest(
        request_id=request_id,
        tenant_id="tenant-a",
        user_id="user-1",
        prompt="Summarize incident trends",
        requested_tools=["search"],
        retrieval_needed=True,
        retrieval_source="qdrant",
    )
    gateway_decision = gateway.evaluate(normalized_request)
    emit(model, sink, "policy.decision", trace_id, request_id, {"allow": gateway_decision.allow})

    # 3) optional retrieval check
    retrieval_layer = RetrievalSecurityLayer(
        backend=DemoRetrievalBackend(),
        policy_evaluator=DemoRetrievalPolicy(),
        telemetry=InMemoryRetrievalTelemetry(),
    )
    retrieval_decision = retrieval_layer.evaluate(
        RetrievalRequest(
            request_id=request_id,
            tenant_id="tenant-a",
            source="qdrant",
            query="incident trends",
            trust_labels=["trusted"],
        )
    )
    emit(
        model,
        sink,
        "retrieval.decision",
        trace_id,
        request_id,
        {"decision": retrieval_decision.mode, "source": "qdrant", "docs": len(retrieval_decision.filtered_documents)},
    )

    # 4) tool decision + execution
    tool_engine = ToolGovernanceEngine(
        policy_evaluator=StaticToolPolicyEvaluator(default_policy_config()),
        executor=DemoToolExecutor(),
        audit_sink=InMemoryAuditSink(),
    )
    tool_result = tool_engine.evaluate(
        ToolActionRequest(
            request_id=request_id,
            tenant_id="tenant-a",
            user_id="user-1",
            tool_name="search",
            arguments={"query": "incident trends"},
        )
    )
    emit(model, sink, "tool.decision", trace_id, request_id, {"status": tool_result.status})
    emit(model, sink, "tool.execution_attempt", trace_id, request_id, {"tool_name": "search", "executed": tool_result.executed})

    # optional fallback/deny hooks (not triggered in this happy demo)
    emit(model, sink, "fallback.event", trace_id, request_id, {"applied": False})
    emit(model, sink, "deny.event", trace_id, request_id, {"blocked": False})

    # incident signal placeholder for full launch-gate evidence completeness in demo
    emit(model, sink, "incident.signal", trace_id, request_id, {"signal": "none"})

    emit(model, sink, "request.end", trace_id, request_id, {"status": "ok"})

    # 5) launch-gate artifact generation
    evidence = {
        "policy.decision": True,
        "retrieval.decision": True,
        "tool.decision": True,
        "incident.signal": True,
    }
    launch_gate = load_launch_gate_module()
    result = launch_gate.evaluate_launch_gate(evidence=evidence, controls=launch_gate.default_controls())

    artifact = {
        "machine": result.to_machine_readable(),
        "human": result.to_human_readable(),
        "artifacts": {"events_jsonl": str(EVENTS_PATH)},
    }
    LAUNCH_GATE_PATH.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")

    print(f"Wrote {EVENTS_PATH}")
    print(f"Wrote {LAUNCH_GATE_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
