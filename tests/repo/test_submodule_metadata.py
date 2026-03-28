import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _gitlinks() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "--stage"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths: list[str] = []
    for line in completed.stdout.splitlines():
        if line.startswith("160000 "):
            paths.append(line.split("\t", 1)[1])
    return paths


def test_gitlinks_are_declared_in_gitmodules() -> None:
    gitmodules = (ROOT / ".gitmodules").read_text(encoding="utf-8")
    declared_paths = set(re.findall(r"^\s*path = (.+)$", gitmodules, re.MULTILINE))

    assert declared_paths
    assert set(_gitlinks()) <= declared_paths


def test_compatibility_snapshot_submodule_is_not_managed() -> None:
    gitmodules = (ROOT / ".gitmodules").read_text(encoding="utf-8")

    assert '[submodule "ai-trust-security-stack"]' not in gitmodules
    assert "path = ai-trust-security-stack" not in gitmodules
