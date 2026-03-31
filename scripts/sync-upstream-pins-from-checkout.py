#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "evidence" / "upstream.lock.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Attempt to sync vendored upstream source pins from standalone local git checkouts.",
    )
    parser.add_argument(
        "--lock-path",
        default=str(LOCK_PATH),
        help="Optional path to an alternate upstream.lock.json file.",
    )
    return parser.parse_args()


def _run_git(path: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _path_is_standalone_repo(path: Path) -> bool:
    try:
        top = Path(_run_git(path, "rev-parse", "--show-toplevel")).resolve()
    except subprocess.CalledProcessError:
        return False
    return top == path.resolve()


def main() -> int:
    args = _parse_args()
    lock_path = Path(args.lock_path).resolve()
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    components = list(payload.get("components", []))
    updated = 0
    skipped: list[str] = []

    for component in components:
        upstream_path = ROOT / str(component.get("upstream_path", "")).strip()
        if not upstream_path.is_dir() or not _path_is_standalone_repo(upstream_path):
            skipped.append(str(component.get("component_name", upstream_path.name or "unknown")))
            continue
        component["source_commit"] = _run_git(upstream_path, "rev-parse", "HEAD")
        component["source_ref"] = _run_git(upstream_path, "describe", "--tags", "--always")
        updated += 1

    payload["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lock_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Updated source pins for {updated} upstream components.")
    if skipped:
        print("Skipped components without standalone git metadata:")
        for name in skipped:
            print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
