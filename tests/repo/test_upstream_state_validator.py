import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_upstream_state_validator_script_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/validate-upstream-state.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "Upstream state validation passed." in completed.stdout
