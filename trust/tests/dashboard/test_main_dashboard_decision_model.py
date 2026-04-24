from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="node is required for dashboard decision-model tests")
def test_dashboard_decision_model_node_tests_pass() -> None:
    result = subprocess.run(
        ["node", "--test", "frontend/main-dashboard/decision-model.test.js"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_dashboard_launch_surfaces_and_live_onyx_mapping_exist() -> None:
    html = Path("frontend/main-dashboard/index.html").read_text(encoding="utf-8")
    model_js = Path("frontend/main-dashboard/decision-model.js").read_text(encoding="utf-8")

    assert 'id="launch-decision-root"' in html
    assert 'id="live-onyx-project-root"' in html
    assert 'id="rag-proof-chain-root"' in html
    assert "deriveLaunchDecisionHeader" in model_js
    assert "deriveRagProofChain" in model_js
    assert "deriveLiveOnyxProject" in model_js
    assert 'runtimeSource: "/onyx"' in model_js
    assert 'trustRoot: "/trust"' in model_js
    assert 'dashboardPath: "/trust/frontend/main-dashboard"' in model_js
