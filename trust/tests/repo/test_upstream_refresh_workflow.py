import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_list_upstream_groups_script_shows_default_and_opt_in_sets() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/list-upstream-groups.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Default checkout group" in completed.stdout
    assert "Opt-in checkout group" in completed.stdout
    assert "upstream/envoy (Envoy)" in completed.stdout
    assert "upstream/superset (Superset)" in completed.stdout


def test_record_upstream_refresh_script_updates_lock_copy() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_copy = Path(tmpdir) / "upstream.lock.json"
        lock_copy.write_text((ROOT / "evidence/upstream.lock.json").read_text(encoding="utf-8"), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                "scripts/record-upstream-refresh.py",
                "envoy",
                "--ref",
                "v1.99.0",
                "--commit",
                "deadbeef12345678",
                "--notes",
                "validated ingress config",
                "--lock-path",
                str(lock_copy),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr
        payload = json.loads(lock_copy.read_text(encoding="utf-8"))
        envoy = next(component for component in payload["components"] if component["component_name"] == "Envoy")

    assert envoy["source_ref"] == "v1.99.0"
    assert envoy["source_commit"] == "deadbeef12345678"
    assert envoy["refresh_notes"] == "validated ingress config"


def test_sync_upstream_pins_script_handles_plain_vendored_directories() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        lock_copy = Path(tmpdir) / "upstream.lock.json"
        lock_copy.write_text((ROOT / "evidence/upstream.lock.json").read_text(encoding="utf-8"), encoding="utf-8")

        completed = subprocess.run(
            [
                sys.executable,
                "scripts/sync-upstream-pins-from-checkout.py",
                "--component",
                "envoy",
                "--lock-path",
                str(lock_copy),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr
        assert "Updated source pins for" in completed.stdout
        assert "Skipped components without standalone git metadata:" in completed.stdout
        payload = json.loads(lock_copy.read_text(encoding="utf-8"))
        envoy = next(component for component in payload["components"] if component["component_name"] == "Envoy")

    assert envoy["snapshot_fingerprint"]
    assert envoy["snapshot_file_count"] > 0
    assert envoy["snapshot_bytes"] > 0


def test_stage_default_upstream_checkout_script_creates_default_only_tree() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "default-upstreams"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/stage-default-upstream-checkout.py",
                str(output_dir),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr
        manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
        assert any(item["upstream_path"] == "upstream/envoy" for item in manifest["default_components"])
        assert any(item["upstream_path"] == "upstream/superset" for item in manifest["opt_in_components"])
        assert (output_dir / "upstream" / "envoy").exists()
        assert not (output_dir / "upstream" / "superset").exists()
