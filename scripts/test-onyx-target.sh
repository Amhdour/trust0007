#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

python - <<'PY'
from pathlib import Path

from backend.posture_service.service import build_control_plane_dashboard

assert Path("upstream/onyx").exists(), "missing upstream/onyx submodule path"

payload = build_control_plane_dashboard()
runtime_module = payload["runtime_module"]
assert "Onyx" in runtime_module, f"unexpected runtime module label: {runtime_module}"

entry_points = next(section for section in payload["sections"] if section["id"] == "entry-points")
links = []
for block in entry_points["blocks"]:
    if block["type"] == "links":
        links.extend(block["items"])

labels = {item["label"] for item in links}
hrefs = {item["href"] for item in links}

assert {"Open Chat", "Open Agents", "Search Knowledge"} <= labels
assert any("/app" in href for href in hrefs), "missing Onyx chat route"
assert any("/app/agents" in href for href in hrefs), "missing Onyx agents route"
assert any("chatMode=search" in href for href in hrefs), "missing Onyx search route"

print("Onyx runtime target checks passed")
PY
