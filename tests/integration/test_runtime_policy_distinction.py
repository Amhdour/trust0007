from backend.api_gateway.server import RuntimePolicyChecker, RuntimePolicyContext
from adapters.onyx_gateway_adapter.schemas import NormalizedRequest


def _request(*, runtime_key: str, path: str, mcp_server: str = "") -> NormalizedRequest:
    return NormalizedRequest(
        request_id="req-1",
        tenant_id="tenant-a",
        user_id="user-1",
        prompt="Open runtime surface",
        requested_tools=[runtime_key],
        metadata={
            "runtime_key": runtime_key,
            "requested_path": path,
            "requested_mcp_server": mcp_server,
            "identity_roles": ["tenant_user"],
        },
    )


def test_runtime_policy_distinguishes_onyx_data_boundary_and_onyx_mcp_rules() -> None:
    policy = {
        "runtime_controls": {
            "onyx": {
                "require_data_boundary": True,
                "require_mcp_governance": True,
                "mcp_allowed_servers": ["mcp_server.dashboard_control_plane"],
            },
        },
        "retrieval": {
            "tenant_allowed_sources": {
                # Intentionally empty for tenant-a to prove Onyx data-boundary enforcement.
            }
        },
        "surfaces": {
            "path_policies": [
                {"path": "/app", "surface": "onyx.chat", "allowed_roles": ["tenant_user"]},
                {"path": "/apps", "surface": "onyx.apps", "allowed_roles": ["tenant_user"]},
            ]
        },
    }
    checker = RuntimePolicyChecker(
        RuntimePolicyContext(document=policy, source="inline-test", relative_path="tests/runtime-policy.json")
    )

    onyx_chat_decision = checker.check_policy(_request(runtime_key="onyx", path="/app"))
    onyx_apps_decision = checker.check_policy(
        _request(runtime_key="onyx", path="/apps", mcp_server="mcp_server.dashboard_control_plane")
    )

    assert onyx_chat_decision.allow is False
    assert "policy.data_boundary_not_configured:tenant-a" in onyx_chat_decision.reasons

    assert onyx_apps_decision.allow is False
    assert "policy.data_boundary_not_configured:tenant-a" in onyx_apps_decision.reasons


def test_runtime_policy_denies_onyx_when_mcp_server_not_allowlisted() -> None:
    policy = {
        "runtime_controls": {
            "onyx": {
                "require_mcp_governance": True,
                "mcp_allowed_servers": ["mcp_server.dashboard_control_plane"],
            }
        },
        "surfaces": {
            "path_policies": [
                {"path": "/apps", "surface": "onyx.apps", "allowed_roles": ["tenant_user"]},
            ]
        },
    }
    checker = RuntimePolicyChecker(
        RuntimePolicyContext(document=policy, source="inline-test", relative_path="tests/runtime-policy.json")
    )

    onyx_decision = checker.check_policy(_request(runtime_key="onyx", path="/apps", mcp_server="mcp_server.unapproved"))

    assert onyx_decision.allow is False
    assert onyx_decision.reasons == ["policy.mcp_server_not_allowed:mcp_server.unapproved"]
