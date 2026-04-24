import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_demo_flow_writes_artifacts_to_configured_directory(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "demo-artifacts"
    env = os.environ.copy()
    env["CONTROL_PLANE_DEMO_ARTIFACTS_DIR"] = str(artifact_dir)

    completed = subprocess.run(
        [sys.executable, "scripts/demo_flow.py"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    events_path = artifact_dir / "events.jsonl"
    launch_path = artifact_dir / "launch-gate.json"

    assert events_path.exists()
    assert launch_path.exists()
    assert str(events_path) in completed.stdout
    assert str(launch_path) in completed.stdout

    lines = [json.loads(line) for line in events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen = {item["event_type"] for item in lines}
    assert {"request.start", "policy.decision", "retrieval.decision", "tool.decision", "request.end"} <= seen

    launch = json.loads(launch_path.read_text(encoding="utf-8"))
    assert launch["machine"]["decision"] in {"pass", "conditional_go", "no_go"}
    assert launch["artifacts"]["events_jsonl"] == str(events_path)
