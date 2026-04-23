from __future__ import annotations

from pathlib import Path

from tests.integration.test_live_end_to_end import APIServer, http_get


def test_agent_lane_unknown_suffix_denies_as_unregistered_surface() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server = APIServer(repo_root)
    server.start()

    try:
        response = http_get(server.url("/launch/onyx/agent/not-a-real-surface"), timeout=10)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        assert "policy.surface_not_registered:/app/not-a-real-surface" in response.text
    finally:
        server.stop()


def test_agent_lane_malformed_query_is_canonicalized_and_governed() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server = APIServer(repo_root)
    server.start()

    try:
        response = http_get(server.url("/launch/onyx/agent&mcp=mcp_server.unapproved"), timeout=10)
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        assert "policy.mcp_server_not_allowed:mcp_server.unapproved" in response.text
    finally:
        server.stop()
