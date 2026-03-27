from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Dict, List, Literal

LaunchDecision = Literal["pass", "conditional_go", "no_go"]


@dataclass(frozen=True)
class ControlRequirement:
    control_id: str
    description: str
    required_evidence: List[str] = field(default_factory=list)
    mandatory: bool = True
    weight: int = 1


@dataclass(frozen=True)
class LaunchGateResult:
    decision: LaunchDecision
    score: int
    max_score: int
    blockers: List[str]
    missing_evidence: List[str]
    controls_passed: List[str]
    controls_failed: List[str]

    def to_machine_readable(self) -> Dict:
        return {
            "decision": self.decision,
            "score": self.score,
            "max_score": self.max_score,
            "blockers": self.blockers,
            "missing_evidence": self.missing_evidence,
            "controls_passed": self.controls_passed,
            "controls_failed": self.controls_failed,
        }

    def to_human_readable(self) -> str:
        return (
            f"Launch Gate Decision: {self.decision}\n"
            f"Score: {self.score}/{self.max_score}\n"
            f"Blockers: {', '.join(self.blockers) if self.blockers else 'none'}\n"
            f"Missing evidence: {', '.join(self.missing_evidence) if self.missing_evidence else 'none'}\n"
            f"Controls passed: {', '.join(self.controls_passed) if self.controls_passed else 'none'}\n"
            f"Controls failed: {', '.join(self.controls_failed) if self.controls_failed else 'none'}"
        )


def _evaluate_control(evidence: Dict[str, bool], control: ControlRequirement):
    """Evaluate a single control against evidence and return missing keys + score delta.

    This isolates control-scoring logic so gate decision rules remain readable.
    """
    missing = [key for key in control.required_evidence if not evidence.get(key, False)]
    if missing:
        return False, missing, 0
    return True, [], control.weight


def evaluate_launch_gate(
    evidence: Dict[str, bool],
    controls: List[ControlRequirement],
    *,
    kill_switch: bool = False,
) -> LaunchGateResult:
    blockers: List[str] = []
    missing_evidence: List[str] = []
    controls_passed: List[str] = []
    controls_failed: List[str] = []

    if kill_switch:
        blockers.append("kill_switch_enabled")

    score = 0
    max_score = sum(c.weight for c in controls)

    for control in controls:
        passed, control_missing, score_delta = _evaluate_control(evidence, control)

        if not passed:
            missing_evidence.extend(control_missing)
            controls_failed.append(control.control_id)
            if control.mandatory:
                blockers.append(f"mandatory_control_missing:{control.control_id}")
            continue

        controls_passed.append(control.control_id)
        score += score_delta

    # Gate rule order is critical:
    # 1) hard blockers (kill switch, missing mandatory controls) => no_go
    # 2) missing optional evidence => conditional_go
    # 3) full evidence and full score => pass
    # No green without evidence.
    if blockers:
        decision: LaunchDecision = "no_go"
    elif missing_evidence:
        decision = "conditional_go"
    elif score == max_score and max_score > 0:
        decision = "pass"
    else:
        decision = "no_go"

    return LaunchGateResult(
        decision=decision,
        score=score,
        max_score=max_score,
        blockers=sorted(set(blockers)),
        missing_evidence=sorted(set(missing_evidence)),
        controls_passed=sorted(controls_passed),
        controls_failed=sorted(controls_failed),
    )


def default_controls() -> List[ControlRequirement]:
    return [
        ControlRequirement(
            control_id="policy_coverage",
            description="Policy decision evidence present.",
            required_evidence=["policy.decision"],
            mandatory=True,
            weight=3,
        ),
        ControlRequirement(
            control_id="retrieval_safety",
            description="Retrieval decision evidence present.",
            required_evidence=["retrieval.decision"],
            mandatory=True,
            weight=2,
        ),
        ControlRequirement(
            control_id="tool_governance",
            description="Tool governance evidence present.",
            required_evidence=["tool.decision"],
            mandatory=True,
            weight=2,
        ),
        ControlRequirement(
            control_id="incident_visibility",
            description="Incident signal telemetry pipeline available.",
            required_evidence=["incident.signal"],
            mandatory=False,
            weight=1,
        ),
    ]


def cli_run(evidence_json: str, kill_switch: bool = False) -> str:
    evidence = json.loads(evidence_json)
    result = evaluate_launch_gate(evidence=evidence, controls=default_controls(), kill_switch=kill_switch)
    return json.dumps(
        {
            "machine": result.to_machine_readable(),
            "human": result.to_human_readable(),
        },
        indent=2,
        sort_keys=True,
    )
