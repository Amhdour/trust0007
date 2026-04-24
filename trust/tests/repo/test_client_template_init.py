import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_ROOT = ROOT / "overlays" / "client-template"


def test_client_template_scaffold_exists() -> None:
    expected_paths = [
        ROOT / "scripts" / "init-client-template.py",
        ROOT / "README.template.md",
        ROOT / "docs" / "client-template-kit.md",
        ROOT / "docs" / "client-engagement-tracks.md",
        TEMPLATE_ROOT / "README.md",
        TEMPLATE_ROOT / "client-profile.json",
        TEMPLATE_ROOT / "client.env.example",
        TEMPLATE_ROOT / "identity" / "claims-map.json",
        TEMPLATE_ROOT / "policy" / "runtime-governance.json",
        TEMPLATE_ROOT / "retrieval" / "boundaries.json",
        TEMPLATE_ROOT / "runtime" / "runtime-profile.json",
        TEMPLATE_ROOT / "secrets" / "paths.json",
        TEMPLATE_ROOT / "observability" / "evidence-profile.json",
        TEMPLATE_ROOT / "readiness" / "launch-gate.json",
        TEMPLATE_ROOT / "artifacts" / "README.md",
    ]

    for path in expected_paths:
        assert path.exists(), f"Missing template asset: {path}"


def test_init_client_template_renders_overlay() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "client-acme-health"
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/init-client-template.py",
                "--client-name",
                "Acme Health",
                "--client-slug",
                "acme-health",
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        assert completed.returncode == 0, completed.stdout + completed.stderr
        client_profile = json.loads((output_dir / "client-profile.json").read_text(encoding="utf-8"))
        policy = json.loads((output_dir / "policy" / "runtime-governance.json").read_text(encoding="utf-8"))
        launch_gate = json.loads((output_dir / "readiness" / "launch-gate.json").read_text(encoding="utf-8"))
        manifest = json.loads((output_dir / "generated-from-template.json").read_text(encoding="utf-8"))
        rendered_files = [
            output_dir / "client-profile.json",
            output_dir / "policy" / "runtime-governance.json",
            output_dir / "readiness" / "launch-gate.json",
            output_dir / "client.env.example",
        ]
        rendered_contents = {path: path.read_text(encoding="utf-8") for path in rendered_files}

    assert client_profile["client_name"] == "Acme Health"
    assert client_profile["client_slug"] == "acme-health"
    assert client_profile["engagement_track"] == "secure-starter-kit"
    assert client_profile["tenant_id"] == "tenant-acme-health"
    assert client_profile["output_overlay"] == str(output_dir)
    assert policy["bundle_path"] == f"{output_dir}/policy/runtime-governance.json"
    assert policy["registered_surfaces"][0]["surface"] == "onyx.chat"
    assert launch_gate["launch_question"] == "Should Acme Health allow governed runtime access for Onyx?"
    assert manifest["template_version"] == "client-template-v1"
    assert manifest["context"]["CLIENT_NAME"] == "Acme Health"
    assert manifest["context"]["CLIENT_SLUG"] == "acme-health"

    for path, content in rendered_contents.items():
        assert "{{" not in content, f"Unresolved template token found in {path}"


def test_init_client_template_refuses_existing_output_without_force() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "client-acme-health"
        output_dir.mkdir(parents=True, exist_ok=True)

        completed = subprocess.run(
            [
                sys.executable,
                "scripts/init-client-template.py",
                "--client-name",
                "Acme Health",
                "--client-slug",
                "acme-health",
                "--output-dir",
                str(output_dir),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    assert completed.returncode != 0
    assert "Refusing to overwrite existing output directory" in completed.stderr
