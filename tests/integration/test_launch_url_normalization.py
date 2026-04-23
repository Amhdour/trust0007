from backend.api_gateway.server import ControlPlaneRequestHandler


def test_launch_url_normalization_rewrites_ampersand_query_to_canonical_form() -> None:
    normalized = ControlPlaneRequestHandler._normalize_launch_request_target(
        "/launch/onyx/agent&mcp=mcp_server.unapproved"
    )
    assert normalized == "/launch/onyx/agent?mcp=mcp_server.unapproved"


def test_launch_url_normalization_leaves_canonical_query_unchanged() -> None:
    raw = "/launch/onyx/agent?mcp=mcp_server.dashboard_control_plane"
    assert ControlPlaneRequestHandler._normalize_launch_request_target(raw) == raw


def test_launch_url_normalization_leaves_non_launch_urls_unchanged() -> None:
    raw = "/runtime-proxy/onyx/app&foo=bar"
    assert ControlPlaneRequestHandler._normalize_launch_request_target(raw) == raw
