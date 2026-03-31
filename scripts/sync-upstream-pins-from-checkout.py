#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
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
        "--component",
        action="append",
        default=[],
        help="Optional component name, upstream path, or directory basename to limit syncing. May be repeated.",
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


def _matches_component(component: dict, needle: str) -> bool:
    normalized = needle.strip().lower()
    component_name = str(component.get("component_name", "")).strip().lower()
    upstream_path = str(component.get("upstream_path", "")).strip().lower()
    upstream_basename = upstream_path.split("/")[-1] if upstream_path else ""
    return normalized in {component_name, upstream_path, upstream_basename}


def _snapshot_fingerprint(path: Path) -> tuple[str, int, int]:
    digest = hashlib.sha256()
    file_count = 0
    total_bytes = 0
    for child in sorted(item for item in path.rglob("*") if item.is_file()):
        relative = child.relative_to(path).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        file_count += 1
        with child.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest(), file_count, total_bytes


def main() -> int:
    args = _parse_args()
    lock_path = Path(args.lock_path).resolve()
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    components = list(payload.get("components", []))
    selected = components
    if args.component:
        needles = list(args.component)
        selected = [
            component
            for component in components
            if any(_matches_component(component, needle) for needle in needles)
        ]
    updated = 0
    fingerprinted = 0
    skipped: list[str] = []

    for component in selected:
        upstream_path = ROOT / str(component.get("upstream_path", "")).strip()
        if not upstream_path.is_dir():
            skipped.append(str(component.get("component_name", upstream_path.name or "unknown")))
            continue
        fingerprint, file_count, total_bytes = _snapshot_fingerprint(upstream_path)
        component["snapshot_fingerprint"] = fingerprint
        component["snapshot_file_count"] = file_count
        component["snapshot_bytes"] = total_bytes
        fingerprinted += 1
        provenance_mode = "content_fingerprint"
        if _path_is_standalone_repo(upstream_path):
            component["source_commit"] = _run_git(upstream_path, "rev-parse", "HEAD")
            component["source_ref"] = _run_git(upstream_path, "describe", "--tags", "--always")
            provenance_mode = "standalone_git_pin+content_fingerprint"
            updated += 1
        else:
            skipped.append(str(component.get("component_name", upstream_path.name or "unknown")))
        if str(component.get("source_ref", "")).strip() and str(component.get("source_commit", "")).strip() and provenance_mode == "content_fingerprint":
            provenance_mode = "manual_pin+content_fingerprint"
        component["provenance_mode"] = provenance_mode

    payload["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    lock_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(f"Updated source pins for {updated} upstream components.")
    print(f"Updated snapshot fingerprints for {fingerprinted} upstream components.")
    if skipped:
        print("Skipped components without standalone git metadata:")
        for name in skipped:
            print(f"- {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
