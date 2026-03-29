import json
from pathlib import Path


def test_reviewer_bundle_lists_live_governed_runtime_examples() -> None:
    bundle = json.loads(Path("evidence/reviewer_evidence_bundle.json").read_text(encoding="utf-8"))

    listed = set(bundle["inspectable_evidence"]["bundles"])
    expected = {
        "evidence/reviewer/inspectable-live-runtime/allowed-flow.json",
        "evidence/reviewer/inspectable-live-runtime/denied-flow.json",
        "evidence/reviewer/inspectable-live-runtime/denied-identity-flow.json",
        "evidence/reviewer/inspectable-live-runtime/denied-opa-flow.json",
        "evidence/reviewer/inspectable-live-runtime/denied-retrieval-flow.json",
        "evidence/reviewer/inspectable-live-runtime/denied-secret-flow.json",
        "evidence/reviewer/inspectable-live-runtime/live-launch-gate-downgrade.json",
    }

    assert expected <= listed
    for path in expected:
        assert Path(path).is_file()
