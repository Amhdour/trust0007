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


def test_inspectable_live_runtime_examples_include_artifact_snapshots() -> None:
    inspectable_root = Path("evidence/reviewer/inspectable-live-runtime")

    for path in sorted(inspectable_root.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        if path.name in {"denied-flow.json"}:
            continue
        assert payload["mode"] == "live"
        assert payload["proof_sources"]
        assert "artifact_snapshots" in payload
        summary = payload["artifact_snapshots"].get("governed_flow_summary", {})
        assert summary.get("evidence_mode") == "live"
        assert "handoff_allowed" in summary


def test_reviewer_fast_path_docs_are_linked_from_bundle() -> None:
    bundle = json.loads(Path("evidence/reviewer_evidence_bundle.json").read_text(encoding="utf-8"))
    inspectable = bundle["inspectable_evidence"]

    assert inspectable["reviewer_fast_path"] == "docs/reviewer-fast-path.md"
    assert inspectable["visual_proof_guide"] == "docs/dashboard-visual-proof.md"
    assert Path(inspectable["reviewer_fast_path"]).is_file()
    assert Path(inspectable["visual_proof_guide"]).is_file()
