from __future__ import annotations

from pathlib import Path

import pytest

from .live_stack_harness import LiveStackHarness


pytestmark = pytest.mark.live_stack


@pytest.fixture(scope="module")
def live_stack() -> LiveStackHarness:
    """Require a running live stack once per module before strict-live assertions."""
    harness = LiveStackHarness(Path(__file__).resolve().parents[2])
    harness.require_ready()
    return harness


def section(payload: dict, section_id: str) -> dict:
    return next(item for item in payload["sections"] if item["id"] == section_id)


def cards(section_payload: dict) -> dict[str, dict]:
    card_block = next(block for block in section_payload["blocks"] if block["type"] == "cards")
    return {item["label"]: item for item in card_block["items"]}
