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


def test_runtime_policy_distinguishes_onyx_data_boundary_and_dify_mcp_rules() -> None:
    policy = {
        "runtime_controls": {
            "onyx": {
                "require_data_boundary": True,
            },
            "dify": {
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
                {"path": "/apps", "surface": "dify.apps", "allowed_roles": ["tenant_user"]},
            ]
        },
    }
    checker = RuntimePolicyChecker(
        RuntimePolicyContext(document=policy, source="inline-test", relative_path="tests/runtime-policy.json")
    )

    onyx_decision = checker.check_policy(_request(runtime_key="onyx", path="/app"))
    dify_decision = checker.check_policy(
        _request(runtime_key="dify", path="/apps", mcp_server="mcp_server.dashboard_control_plane")
    )

    assert onyx_decision.allow is False
    assert "policy.data_boundary_not_configured:tenant-a" in onyx_decision.reasons

    assert dify_decision.allow is True
    assert dify_decision.reasons == ["policy.allow"]


def test_runtime_policy_denies_dify_when_mcp_server_not_allowlisted() -> None:
    policy = {
        "runtime_controls": {
            "dify": {
                "require_mcp_governance": True,
                "mcp_allowed_servers": ["mcp_server.dashboard_control_plane"],
            }
        },
        "surfaces": {
            "path_policies": [
                {"path": "/apps", "surface": "dify.apps", "allowed_roles": ["tenant_user"]},
            ]
        },
    }
    checker = RuntimePolicyChecker(
        RuntimePolicyContext(document=policy, source="inline-test", relative_path="tests/runtime-policy.json")
    )

    dify_decision = checker.check_policy(_request(runtime_key="dify", path="/apps", mcp_server="mcp_server.unapproved"))

    assert dify_decision.allow is False
    assert dify_decision.reasons == ["policy.mcp_server_not_allowed:mcp_server.unapproved"]
