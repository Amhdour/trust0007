#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.integration_adapter.repository import load_upstream_source_lock


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a non-destructive staged upstream checkout that includes only the default upstream group.",
    )
    parser.add_argument("output_dir", help="Directory to create or replace with the staged checkout.")
    parser.add_argument(
        "--mode",
        choices=("symlink", "copy"),
        default="symlink",
        help="Whether to stage upstreams as symlinks or as copied directories.",
    )
    return parser.parse_args()


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    args = _parse_args()
    output_dir = Path(args.output_dir).resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_upstream = output_dir / "upstream"
    output_upstream.mkdir(parents=True, exist_ok=True)

    lock_manifest = load_upstream_source_lock(ROOT)
    components = list(lock_manifest.get("components", []))
    default_components = [component for component in components if component.get("checkout_policy") == "default"]
    opt_in_components = [component for component in components if component.get("checkout_policy") == "opt_in"]

    for component in default_components:
        source = ROOT / str(component.get("upstream_path", "")).strip()
        target = output_upstream / source.name
        if args.mode == "copy":
            shutil.copytree(source, target)
        else:
            os.symlink(source, target, target_is_directory=True)

    manifest = {
        "mode": args.mode,
        "default_components": [
            {"component_name": component["component_name"], "upstream_path": component["upstream_path"]}
            for component in default_components
        ],
        "opt_in_components": [
            {"component_name": component["component_name"], "upstream_path": component["upstream_path"]}
            for component in opt_in_components
        ],
    }
    _write_text(output_dir / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    _write_text(
        output_dir / "README.md",
        "\n".join(
            [
                "# Default Upstream Checkout",
                "",
                "This staged checkout contains only the default upstream group from `evidence/upstream.lock.json`.",
                "",
                "Included upstreams:",
                *[f"- {component['upstream_path']} ({component['component_name']})" for component in default_components],
                "",
                "Opt-in upstreams omitted from this staged checkout:",
                *[f"- {component['upstream_path']} ({component['component_name']})" for component in opt_in_components],
                "",
                "Use the main repo checkout to access the full vendored source set.",
            ]
        )
        + "\n",
    )

    print(f"Staged default upstream checkout at {output_dir}")
    print(f"Included components: {len(default_components)}")
    print(f"Omitted opt-in components: {len(opt_in_components)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
