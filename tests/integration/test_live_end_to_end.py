"""Live end-to-end test proving the governed flow works in the running system.

This test:
1. Starts the API gateway server
2. Calls /api/control-plane/governed-flow to generate artifacts
3. Verifies artifacts are written to overlay directory
4. Calls dashboard API to verify it consumes live artifacts
5. Calls /launch/onyx to verify governance enforcement
6. Verifies deny path blocks handoff
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest


class HTTPResponse:
    def __init__(self, status_code: int, text: str):
        self.status_code = status_code
        self.text = text

    def json(self):
        return json.loads(self.text)


def http_get(url: str, timeout: int = 10) -> HTTPResponse:
    try:
        with urlopen(url, timeout=timeout) as response:
            return HTTPResponse(getattr(response, "status", 200), response.read().decode("utf-8"))
    except HTTPError as exc:
        return HTTPResponse(exc.code, exc.read().decode("utf-8"))


class APIServer:
    """Helper to start/stop the API server for testing."""

    def __init__(self, repo_root: Path, extra_env: dict[str, str] | None = None):
        self.repo_root = repo_root
        self.extra_env = extra_env or {}
        self.process = None
        self.port = 3001  # Use different port for testing

    def start(self):
        """Start the API server in background."""
        env = {
            "CONTROL_PLANE_REPO_ROOT": str(self.repo_root),
            "CONTROL_PLANE_HOST": "127.0.0.1",
            "CONTROL_PLANE_PORT": str(self.port),
            "PYTHONPATH": str(self.repo_root),
        }

        self.process = subprocess.Popen(
            ["python", "-m", "backend.api_gateway.server"],
            cwd=self.repo_root,
            env={**dict(os.environ), **env, **self.extra_env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to start
        for _ in range(30):  # 30 seconds timeout
            try:
                response = http_get(f"http://127.0.0.1:{self.port}/api/health", timeout=1)
                if response.status_code == 200:
                    return
            except URLError:
                pass
            time.sleep(1)

        raise RuntimeError("Server failed to start within 30 seconds")

    def stop(self):
        """Stop the API server."""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()

    def url(self, path: str) -> str:
        """Get full URL for a path."""
        return f"http://127.0.0.1:{self.port}{path}"


def test_live_governed_flow_end_to_end():
    """Test the complete governed flow from API call to artifact consumption."""
    repo_root = Path(__file__).resolve().parents[2]
    artifacts_dir = repo_root / "overlays" / "myStarterKit" / "artifacts"

    server = APIServer(repo_root)
    server.start()

    try:
        response = http_get(server.url("/api/control-plane/governed-flow"), timeout=30)
        assert response.status_code == 200

        flow_result = response.json()
        assert flow_result["decision"] is True
        assert "trace_id" in flow_result
        assert "launch_gate" in flow_result
        assert "artifacts" in flow_result
        assert flow_result["policy_bundle"]["source"] == "overlay"
        assert flow_result["policy_bundle"]["path"] == "overlays/myStarterKit/policies/bundles/default/policy.json"

        events_file = repo_root / flow_result["artifacts"]["events_jsonl"]
        gate_file = repo_root / flow_result["artifacts"]["launch_gate_result"]

        assert events_file.exists(), "events.jsonl should be created"
        assert gate_file.exists(), "launch-gate-result.json should be created"
        assert events_file.parent == artifacts_dir
        assert gate_file.parent == artifacts_dir

        events = [json.loads(line) for line in events_file.read_text().splitlines()]
        event_types = {e["event_type"] for e in events}
        required_events = {
            "request.start",
            "identity.established",
            "policy.decision",
            "retrieval.decision",
            "tool.decision",
            "request.end",
        }
        assert required_events.issubset(event_types), f"Missing events: {required_events - event_types}"
        assert flow_result["trace_id"] in {e["trace_id"] for e in events}

        gate_data = json.loads(gate_file.read_text())
        assert gate_data["machine"]["decision"] == "pass"
        assert gate_data["flow_metadata"]["trace_id"] == flow_result["trace_id"]
    finally:
        server.stop()


def test_live_onyx_handoff_enforcement():
    """Test that Onyx handoff is governed and can be blocked."""
    repo_root = Path(__file__).resolve().parents[2]
    server = APIServer(repo_root)
    server.start()

    try:
        response = http_get(server.url("/launch/onyx?path=/app/bypass"), timeout=10)

        assert response.status_code == 403, f"Expected 403, got {response.status_code}"

        content = response.text
        assert "Access Denied" in content
        assert "governance layer has blocked" in content
        assert "policy.forbidden_content" in content
        assert "Policy source" in content
    finally:
        server.stop()


def test_live_onyx_search_handoff_allowed() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server = APIServer(repo_root)
    server.start()

    try:
        response = http_get(server.url("/launch/onyx?path=/app?chatMode=search"), timeout=10)

        assert response.status_code == 200, f"Expected 200, got {response.status_code}"
        assert "Governance Status:</strong> ✓ Approved" in response.text
        assert "Policy Source" in response.text
    finally:
        server.stop()


def test_live_onyx_agents_handoff_requires_admin_role() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    server = APIServer(repo_root)
    server.start()

    try:
        response = http_get(server.url("/launch/onyx?path=/app/agents"), timeout=10)

        assert response.status_code == 403, f"Expected 403, got {response.status_code}"
        assert "policy.surface_role_denied:onyx.agents" in response.text
    finally:
        server.stop()


def test_live_dashboard_consumes_artifacts():
    """Test that dashboard API consumes live governed flow artifacts."""
    repo_root = Path(__file__).resolve().parents[2]
    server = APIServer(repo_root)
    server.start()

    try:
        governed_flow = http_get(server.url("/api/control-plane/governed-flow"), timeout=30)
        assert governed_flow.status_code == 200
        trace_id = governed_flow.json()["trace_id"]

        response = http_get(server.url("/api/control-plane"), timeout=10)
        assert response.status_code == 200

        dashboard_data = response.json()
        assert "sections" in dashboard_data
        assert "readiness_panel" in dashboard_data
        dashboard_text = json.dumps(dashboard_data)
        assert trace_id in dashboard_text
        assert "Blocked / Governed Actions" in dashboard_text
        assert "Onyx Governed Runtime" in dashboard_text
    finally:
        server.stop()


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).resolve().parents[2])

    print("Running live end-to-end tests...")
    test_live_governed_flow_end_to_end()
    test_live_onyx_handoff_enforcement()
    test_live_onyx_search_handoff_allowed()
    test_live_onyx_agents_handoff_requires_admin_role()
    test_live_dashboard_consumes_artifacts()
    print("✅ All live end-to-end tests passed!")
