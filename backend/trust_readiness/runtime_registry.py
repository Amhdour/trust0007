from __future__ import annotations

from .schemas import RuntimeDescriptor


RUNTIME_DESCRIPTORS: dict[str, RuntimeDescriptor] = {
    "onyx": RuntimeDescriptor(
        runtime_id="onyx",
        label="Onyx",
        runtime_class="rag",
        launch_path="/app",
        launch_route="/launch/onyx?path=/app&mode=live&view=embedded",
        governance_lane="governed_rag_launch_lane",
        primary_controls=[
            "identity_health",
            "policy_decision",
            "retrieval_boundary",
            "connector_freshness",
            "telemetry_heartbeat",
            "audit_pipeline",
            "launch_gate",
        ],
    ),
    "dify": RuntimeDescriptor(
        runtime_id="dify",
        label="Dify",
        runtime_class="autonomous_agents",
        launch_path="/apps",
        launch_route="/launch/dify?path=/apps&mode=live&view=embedded",
        governance_lane="governed_agent_launch_lane",
        primary_controls=[
            "identity_health",
            "policy_decision",
            "mcp_tool_authorization",
            "privileged_tool_approval",
            "telemetry_heartbeat",
            "audit_pipeline",
            "launch_gate",
        ],
    ),
}


def runtime_descriptor(runtime_id: str) -> RuntimeDescriptor:
    normalized = (runtime_id or "onyx").strip().lower()
    return RUNTIME_DESCRIPTORS.get(normalized, RUNTIME_DESCRIPTORS["onyx"])


def runtime_descriptors() -> list[RuntimeDescriptor]:
    return [RUNTIME_DESCRIPTORS[key] for key in sorted(RUNTIME_DESCRIPTORS)]
