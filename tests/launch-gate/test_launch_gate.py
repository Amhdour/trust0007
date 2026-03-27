import importlib.util
from pathlib import Path


MODULE_PATH = Path("launch-gate/evaluator.py")
spec = importlib.util.spec_from_file_location("launch_gate_evaluator", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_pass_when_all_evidence_present() -> None:
    evidence = {
        "policy.decision": True,
        "retrieval.decision": True,
        "tool.decision": True,
        "incident.signal": True,
    }
    result = module.evaluate_launch_gate(evidence, module.default_controls())

    assert result.decision == "pass"
    assert result.blockers == []
    assert result.missing_evidence == []
    assert result.score == result.max_score


def test_conditional_go_when_only_optional_evidence_missing() -> None:
    evidence = {
        "policy.decision": True,
        "retrieval.decision": True,
        "tool.decision": True,
        "incident.signal": False,
    }
    result = module.evaluate_launch_gate(evidence, module.default_controls())

    assert result.decision == "conditional_go"
    assert result.blockers == []
    assert "incident.signal" in result.missing_evidence


def test_no_go_when_mandatory_evidence_missing() -> None:
    evidence = {
        "policy.decision": True,
        "retrieval.decision": False,
        "tool.decision": True,
        "incident.signal": True,
    }
    result = module.evaluate_launch_gate(evidence, module.default_controls())

    assert result.decision == "no_go"
    assert any(b.startswith("mandatory_control_missing") for b in result.blockers)
    assert "retrieval.decision" in result.missing_evidence


def test_no_go_when_kill_switch_enabled() -> None:
    evidence = {
        "policy.decision": True,
        "retrieval.decision": True,
        "tool.decision": True,
        "incident.signal": True,
    }
    result = module.evaluate_launch_gate(evidence, module.default_controls(), kill_switch=True)

    assert result.decision == "no_go"
    assert "kill_switch_enabled" in result.blockers


def test_machine_and_human_outputs_exist() -> None:
    evidence = {
        "policy.decision": True,
        "retrieval.decision": True,
        "tool.decision": True,
        "incident.signal": False,
    }
    result = module.evaluate_launch_gate(evidence, module.default_controls())

    machine = result.to_machine_readable()
    human = result.to_human_readable()

    assert "decision" in machine
    assert "score" in machine
    assert "Launch Gate Decision" in human
