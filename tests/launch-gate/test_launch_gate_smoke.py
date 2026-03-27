import importlib.util
import json
from pathlib import Path
import sys


MODULE_PATH = Path("launch-gate/evaluator.py")
spec = importlib.util.spec_from_file_location("launch_gate_evaluator_smoke", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


REQUIRED_ARTIFACTS = [
    Path("telemetry/exports/event_schema.json"),
    Path("telemetry/exports/sample_events.jsonl"),
]


def test_required_evidence_artifacts_exist() -> None:
    missing = [str(p) for p in REQUIRED_ARTIFACTS if not p.exists()]
    assert missing == []


def test_launch_gate_no_go_when_mandatory_evidence_missing() -> None:
    evidence = {
        "policy.decision": True,
        "retrieval.decision": False,
        "tool.decision": True,
        "incident.signal": True,
    }
    result = module.evaluate_launch_gate(evidence, module.default_controls())
    assert result.decision == "no_go"


def test_launch_gate_cli_machine_human_shape() -> None:
    evidence = {
        "policy.decision": True,
        "retrieval.decision": True,
        "tool.decision": True,
        "incident.signal": False,
    }
    out = module.cli_run(json.dumps(evidence), kill_switch=False)
    parsed = json.loads(out)
    assert "machine" in parsed
    assert "human" in parsed
