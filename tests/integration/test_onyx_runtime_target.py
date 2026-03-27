from pathlib import Path

from backend.posture_service.service import build_control_plane_dashboard


def test_onyx_is_the_primary_runtime_target() -> None:
    payload = build_control_plane_dashboard()

    assert Path("upstream/onyx").exists()
    assert "Onyx" in payload["runtime_module"]


def test_dashboard_exposes_onyx_entry_points() -> None:
    payload = build_control_plane_dashboard()
    entry_points = next(section for section in payload["sections"] if section["id"] == "entry-points")

    links = []
    for block in entry_points["blocks"]:
        if block["type"] == "links":
            links.extend(block["items"])

    labels = {item["label"] for item in links}
    hrefs = {item["href"] for item in links}

    assert {"Open Chat", "Open Agents", "Search Knowledge"} <= labels
    assert any("/launch/onyx?path=/app" in href for href in hrefs) or any("/app" in href for href in hrefs) or any("/raw/docs/onyx-integration.md" in href for href in hrefs)
    assert any("/launch/onyx?path=/app/agents" in href for href in hrefs) or any("/app/agents" in href for href in hrefs) or any("/raw/docs/onyx-integration.md" in href for href in hrefs)
    assert any("/launch/onyx?path=/app?chatMode=search" in href for href in hrefs) or any("chatMode=search" in href for href in hrefs) or any("/raw/docs/onyx-integration.md" in href for href in hrefs)
