#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.integration_adapter.repository import load_upstream_source_lock, load_upstream_usage_inventory


def _declared_submodule_paths() -> list[str]:
    gitmodules = ROOT / ".gitmodules"
    if not gitmodules.exists():
        return []
    return re.findall(r"^\s*path = (.+)$", gitmodules.read_text(encoding="utf-8"), re.MULTILINE)


def main() -> int:
    declared_submodules = _declared_submodule_paths()
    upstream_submodules = sorted(path for path in declared_submodules if path.startswith("upstream/"))
    inventory = load_upstream_usage_inventory(ROOT)
    lock_manifest = load_upstream_source_lock(ROOT)

    errors: list[str] = []
    if "overlays/myStarterKit" not in declared_submodules:
        errors.append("managed overlay submodule overlays/myStarterKit is missing from .gitmodules")
    if upstream_submodules:
        errors.append(f"upstream paths unexpectedly declared as submodules: {', '.join(upstream_submodules)}")
    if not lock_manifest.get("audit", {}).get("lock_covers_all_upstreams"):
        errors.append("upstream lock manifest does not cover every vendored upstream exactly once")
    if not inventory.get("audit", {}).get("inventory_covers_all_upstreams"):
        errors.append("upstream usage inventory does not cover every vendored upstream exactly once")
    if not inventory.get("audit", {}).get("lock_consistent"):
        errors.append("upstream usage inventory and upstream lock manifest are out of sync")

    if errors:
        print("Upstream state validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Upstream state validation passed.")
    print(f"Managed submodules: {', '.join(lock_manifest.get('managed_submodules', []))}")
    print(f"Vendored upstream components: {lock_manifest.get('component_count', 0)}")
    print(f"Tracking model: {inventory.get('tracking_model', {}).get('mode', 'unknown')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
