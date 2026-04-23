#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

POLICY_FILES = [
    ROOT / "overlays/myStarterKit/policies/bundles/default/policy.json",
    ROOT / "policies/control-plane/default-governance-policy.json",
]

REQUIRED_ONYX_ARGS = {"surface", "path", "chat_mode", "mcp_server", "action"}
REQUIRED_ONYX_SURFACES = {
    ("/app", "onyx.chat"),
    ("/app/agents", "onyx.agents"),
    ("/apps", "onyx.apps"),
}


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def _validate(path: Path) -> list[str]:
    document = _load(path)
    errors: list[str] = []
    if not document:
        return [f"{path}: missing_or_invalid_json"]

    tools = document.get("tools", {})
    runtime_controls = document.get("runtime_controls", {})

    allowed_tools = set(tools.get("allowed_tools", []))
    if "onyx" not in allowed_tools:
        errors.append(f"{path}: tools.allowed_tools must include 'onyx'")
    onyx_allowed_tools = sorted(tool for tool in allowed_tools if tool.startswith("onyx"))

    onyx_controls = runtime_controls.get("onyx", {})
    if not isinstance(onyx_controls, dict):
        errors.append(f"{path}: runtime_controls.onyx must be an object")
    else:
        if not bool(onyx_controls.get("require_mcp_governance", False)):
            errors.append(f"{path}: runtime_controls.onyx.require_mcp_governance must be true")
        if not list(onyx_controls.get("mcp_allowed_servers", [])):
            errors.append(f"{path}: runtime_controls.onyx.mcp_allowed_servers must not be empty")

    arg_policies = tools.get("argument_policies", {})
    if not isinstance(arg_policies, dict):
        arg_policies = {}
    onyx_policy = arg_policies.get("onyx", {}) if isinstance(arg_policies, dict) else {}
    onyx_allowed = set(onyx_policy.get("allowed_arguments", [])) if isinstance(onyx_policy, dict) else set()
    missing_args = sorted(REQUIRED_ONYX_ARGS - onyx_allowed)
    if missing_args:
        errors.append(f"{path}: tools.argument_policies.onyx.allowed_arguments missing {', '.join(missing_args)}")

    for tool in onyx_allowed_tools:
        if tool not in arg_policies:
            errors.append(f"{path}: tools.argument_policies missing policy for {tool}")

    # The overlay policy is expected to define lane surfaces and role coverage.
    if path.as_posix().endswith("overlays/myStarterKit/policies/bundles/default/policy.json"):
        surface_rules = document.get("surfaces", {}).get("path_policies", [])
        if not isinstance(surface_rules, list):
            surface_rules = []
        surface_pairs = {(str(rule.get("path", "")), str(rule.get("surface", ""))) for rule in surface_rules if isinstance(rule, dict)}
        missing_surfaces = sorted(REQUIRED_ONYX_SURFACES - surface_pairs)
        if missing_surfaces:
            errors.append(f"{path}: missing required Onyx surfaces {missing_surfaces}")

        def _roles_for(surface: str) -> set[str]:
            for rule in surface_rules:
                if isinstance(rule, dict) and str(rule.get("surface", "")) == surface:
                    return set(str(role) for role in rule.get("allowed_roles", []))
            return set()

        if not {"tenant_user", "tenant_admin"}.issubset(_roles_for("onyx.chat")):
            errors.append(f"{path}: onyx.chat must allow tenant_user and tenant_admin")
        if not {"tenant_user", "tenant_admin"}.issubset(_roles_for("onyx.apps")):
            errors.append(f"{path}: onyx.apps must allow tenant_user and tenant_admin")
        if "tenant_admin" not in _roles_for("onyx.agents"):
            errors.append(f"{path}: onyx.agents must allow tenant_admin")

    return errors


def main() -> int:
    errors: list[str] = []
    for path in POLICY_FILES:
        errors.extend(_validate(path))

    if errors:
        print("Runtime policy schema validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Runtime policy schema validation passed.")
    for path in POLICY_FILES:
        print(f"- {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
