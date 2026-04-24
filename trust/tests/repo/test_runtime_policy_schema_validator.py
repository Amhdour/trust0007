from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_runtime_policy_schema_validator_script_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate-runtime-policy-schema.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Runtime policy schema validation passed." in completed.stdout
