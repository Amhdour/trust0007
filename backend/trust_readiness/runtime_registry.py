from __future__ import annotations

from .schemas import RuntimeDescriptor


RUNTIME_DESCRIPTORS: dict[str, RuntimeDescriptor] = {
    "onyx": RuntimeDescriptor(
        runtime_id="onyx",
        label="Onyx",
        runtime_class="onyx_governed_runtime",
        launch_path="/app",
        launch_route="/launch/onyx/chat?mode=live&view=embedded",
        governance_lane="onyx_trust_readiness_control_plane",
        primary_controls=[
            "identity_health",
            "policy_decision",
            "retrieval_boundary",
            "agent_identity",
            "mcp_tool_authorization",
            "connector_freshness",
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
