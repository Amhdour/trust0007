#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.integration_adapter.repository import load_upstream_source_lock


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List default and opt-in vendored upstream checkout groups.",
    )
    parser.add_argument(
        "--policy",
        choices=("all", "default", "opt_in"),
        default="all",
        help="Which checkout policy group to print.",
    )
    return parser.parse_args()


def _print_group(title: str, entries: list[dict]) -> None:
    print(title)
    for entry in entries:
        print(f"- {entry['upstream_path']} ({entry['component_name']})")


def main() -> int:
    args = _parse_args()
    components = list(load_upstream_source_lock(ROOT).get("components", []))
    default_entries = [entry for entry in components if entry.get("checkout_policy") == "default"]
    opt_in_entries = [entry for entry in components if entry.get("checkout_policy") == "opt_in"]

    if args.policy in {"all", "default"}:
        _print_group("Default checkout group", default_entries)
    if args.policy == "all":
        print()
    if args.policy in {"all", "opt_in"}:
        _print_group("Opt-in checkout group", opt_in_entries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
