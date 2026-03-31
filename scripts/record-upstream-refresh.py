#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = ROOT / "evidence" / "upstream.lock.json"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Record a vendored upstream refresh in evidence/upstream.lock.json.",
    )
    parser.add_argument(
        "component",
        help="Component name, upstream path, or upstream directory basename (for example: Envoy, upstream/envoy, envoy).",
    )
    parser.add_argument("--ref", required=True, help="Pinned upstream tag/ref to record.")
    parser.add_argument("--commit", required=True, help="Pinned upstream commit SHA to record.")
    parser.add_argument(
        "--notes",
        default="",
        help="Short note describing what changed or what was revalidated.",
    )
    parser.add_argument(
        "--validated-on",
        default=date.today().isoformat(),
        help="Validation date to record in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--lock-path",
        default=str(LOCK_PATH),
        help="Optional path to an alternate upstream.lock.json file.",
    )
    return parser.parse_args()


def _load_lock(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_lock(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _matches_component(component: dict, needle: str) -> bool:
    normalized = needle.strip().lower()
    component_name = str(component.get("component_name", "")).strip().lower()
    upstream_path = str(component.get("upstream_path", "")).strip().lower()
    upstream_basename = upstream_path.split("/")[-1] if upstream_path else ""
    return normalized in {component_name, upstream_path, upstream_basename}


def main() -> int:
    args = _parse_args()
    lock_path = Path(args.lock_path).resolve()
    payload = _load_lock(lock_path)
    components = list(payload.get("components", []))

    target = next((component for component in components if _matches_component(component, args.component)), None)
    if target is None:
        print(f"error: no upstream component matched '{args.component}'", file=sys.stderr)
        return 1

    target["source_ref"] = args.ref.strip()
    target["source_commit"] = args.commit.strip()
    target["last_validated"] = args.validated_on.strip()
    target["refresh_notes"] = args.notes.strip()
    payload["generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    _write_lock(lock_path, payload)

    print("Recorded upstream refresh:")
    print(f"- component: {target.get('component_name', 'unknown')}")
    print(f"- path: {target.get('upstream_path', '')}")
    print(f"- ref: {target.get('source_ref', '')}")
    print(f"- commit: {target.get('source_commit', '')}")
    print(f"- validated_on: {target.get('last_validated', '')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
