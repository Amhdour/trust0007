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
import subprocess
import time
import threading
from pathlib import Path
import tempfile
import requests
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings for local testing
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import pytest


class APIServer:
    """Helper to start/stop the API server for testing."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
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
            env={**dict(os.environ), **env},
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Wait for server to start
        for _ in range(30):  # 30 seconds timeout
            try:
                response = requests.get(f"http://127.0.0.1:{self.port}/api/health", timeout=1)
                if response.status_code == 200:
                    return
            except requests.exceptions.RequestException:
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
    repo_root = Path(__file__).resolve().parent.parent

    # Use a temporary directory for artifacts to avoid polluting the real overlay
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_artifacts = Path(temp_dir) / "artifacts"
        temp_artifacts.mkdir()

        # Override the artifact directory in the evaluator
        import backend.governance_flow_evaluator
        original_init = backend.governance_flow_evaluator.GovernedFlowEvaluator.__init__

        def patched_init(self, *args, artifact_dir=temp_artifacts, **kwargs):
            return original_init(self, *args, artifact_dir=artifact_dir, **kwargs)

        backend.governance_flow_evaluator.GovernedFlowEvaluator.__init__ = patched_init

        try:
            server = APIServer(repo_root)
            server.start()

            # 1. Call governed flow API
            response = requests.get(server.url("/api/control-plane/governed-flow"), timeout=30)
            assert response.status_code == 200

            flow_result = response.json()
            assert "decision" in flow_result
            assert "trace_id" in flow_result
            assert "launch_gate" in flow_result
            assert "artifacts" in flow_result

            # 2. Verify artifacts were created
            events_file = temp_artifacts / "events.jsonl"
            gate_file = temp_artifacts / "launch-gate-result.json"

            assert events_file.exists(), "events.jsonl should be created"
            assert gate_file.exists(), "launch-gate-result.json should be created"

            # 3. Verify events content
            events = [json.loads(line) for line in events_file.read_text().splitlines()]
            assert len(events) > 0

            event_types = {e["event_type"] for e in events}
            required_events = {
                "request.start",
                "identity.established",
                "policy.decision",
                "retrieval.decision",
                "tool.decision",
                "request.end"
            }
            assert required_events.issubset(event_types), f"Missing events: {required_events - event_types}"

            # 4. Verify launch-gate result
            gate_data = json.loads(gate_file.read_text())
            assert "machine" in gate_data
            assert "human" in gate_data
            assert "flow_metadata" in gate_data

            # 5. Verify trace_id consistency
            flow_trace_id = flow_result["trace_id"]
            event_trace_ids = {e["trace_id"] for e in events}
            assert flow_trace_id in event_trace_ids, "Trace ID should appear in events"

            print(f"✅ Governed flow completed with trace_id: {flow_trace_id}")
            print(f"✅ Artifacts created: {events_file}, {gate_file}")
            print(f"✅ Launch gate decision: {flow_result['launch_gate']['decision']}")

        finally:
            server.stop()
            # Restore original init
            backend.governance_flow_evaluator.GovernedFlowEvaluator.__init__ = original_init


def test_live_onyx_handoff_enforcement():
    """Test that Onyx handoff is governed and can be blocked."""
    repo_root = Path(__file__).resolve().parent.parent

    # Mock the evaluator to deny all requests for this test
    import backend.api_gateway.server
    original_evaluator = backend.api_gateway.server.GovernedFlowEvaluator

    class DenyAllEvaluator:
        def run(self, *args, **kwargs):
            from backend.governance_flow_evaluator import GovernedFlowResult
            return GovernedFlowResult(
                decision=False,
                trace_id="deny-test-trace",
                request_id="deny-test-req",
                launch_gate_decision="no_go",
                launch_gate_score=0,
                launch_gate_max_score=9,
                launch_gate_blockers=["policy.deny_all"],
                launch_gate_missing_evidence=[],
                artifacts={"events_jsonl": "test", "launch_gate_result": "test"},
            )

    backend.api_gateway.server.GovernedFlowEvaluator = DenyAllEvaluator

    try:
        server = APIServer(repo_root)
        server.start()

        # Call handoff endpoint - should be denied
        response = requests.get(server.url("/launch/onyx?path=/app"), timeout=10)

        # Should return 403 Forbidden
        assert response.status_code == 403, f"Expected 403, got {response.status_code}"

        # Should contain denial message
        content = response.text
        assert "Access Denied" in content
        assert "governance layer has blocked" in content
        assert "deny-test-trace" in content

        print("✅ Onyx handoff correctly blocked by governance")

    finally:
        server.stop()
        # Restore original evaluator
        backend.api_gateway.server.GovernedFlowEvaluator = original_evaluator


def test_live_dashboard_consumes_artifacts():
    """Test that dashboard API consumes live governed flow artifacts."""
    repo_root = Path(__file__).resolve().parent.parent

    # Create fake live artifacts
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_artifacts = Path(temp_dir) / "artifacts"
        temp_artifacts.mkdir()

        # Create events.jsonl
        events_data = [
            {
                "event_type": "request.start",
                "trace_id": "live-test-trace",
                "request_id": "live-test-req",
                "timestamp": "2026-03-27T18:00:00Z",
                "payload": {"path": "/governed-flow"}
            },
            {
                "event_type": "policy.decision",
                "trace_id": "live-test-trace",
                "request_id": "live-test-req",
                "timestamp": "2026-03-27T18:00:01Z",
                "payload": {"allow": True}
            }
        ]
        events_file = temp_artifacts / "events.jsonl"
        events_file.write_text("\n".join(json.dumps(e) for e in events_data))

        # Create launch-gate-result.json
        gate_data = {
            "machine": {
                "decision": "pass",
                "score": 9,
                "max_score": 9,
                "blockers": [],
                "missing_evidence": [],
                "controls_passed": ["policy_coverage", "retrieval_safety", "tool_governance"],
                "controls_failed": []
            },
            "human": "Launch Gate Decision: pass\nScore: 9/9\n...",
            "flow_metadata": {
                "trace_id": "live-test-trace",
                "request_id": "live-test-req"
            }
        }
        gate_file = temp_artifacts / "launch-gate-result.json"
        gate_file.write_text(json.dumps(gate_data))

        # Mock the repository functions to use our temp artifacts
        import backend.integration_adapter.repository
        original_has_live = backend.integration_adapter.repository.has_live_governed_flow_artifacts
        original_load_events = backend.integration_adapter.repository.load_latest_governed_flow_events
        original_load_gate = backend.integration_adapter.repository.load_latest_governed_flow_launch_gate

        def mock_has_live(root=None):
            return True

        def mock_load_events(root=None):
            return [json.loads(line) for line in events_file.read_text().splitlines()]

        def mock_load_gate(root=None):
            return json.loads(gate_file.read_text())

        backend.integration_adapter.repository.has_live_governed_flow_artifacts = mock_has_live
        backend.integration_adapter.repository.load_latest_governed_flow_events = mock_load_events
        backend.integration_adapter.repository.load_latest_governed_flow_launch_gate = mock_load_gate

        try:
            server = APIServer(repo_root)
            server.start()

            # Call dashboard API
            response = requests.get(server.url("/api/control-plane"), timeout=10)
            assert response.status_code == 200

            dashboard_data = response.json()

            # Should contain live events, not fallback
            assert "sections" in dashboard_data
            # Find the activity section
            activity_section = None
            for section in dashboard_data["sections"]:
                if section.get("id") == "activity":
                    activity_section = section
                    break

            assert activity_section is not None, "Should have activity section"
            assert "items" in activity_section

            # Should contain our live events
            items = activity_section["items"]
            event_summaries = [item.get("detail", "") for item in items]

            # Should see our live events
            assert any("Started /governed-flow" in summary for summary in event_summaries)
            assert any("Policy allow" in summary for summary in event_summaries)

            print("✅ Dashboard correctly consumed live governed flow artifacts")

        finally:
            server.stop()
            # Restore originals
            backend.integration_adapter.repository.has_live_governed_flow_artifacts = original_has_live
            backend.integration_adapter.repository.load_latest_governed_flow_events = original_load_events
            backend.integration_adapter.repository.load_latest_governed_flow_launch_gate = original_load_gate


if __name__ == "__main__":
    import os
    os.chdir(Path(__file__).parent.parent)

    print("Running live end-to-end tests...")
    test_live_governed_flow_end_to_end()
    test_live_onyx_handoff_enforcement()
    test_live_dashboard_consumes_artifacts()
    print("✅ All live end-to-end tests passed!")