from __future__ import annotations

import json
from pathlib import Path

from backend.governed_request_telemetry import append_governed_request_feed


def test_governed_request_feed_recovers_from_corrupt_json(tmp_path: Path) -> None:
    feed_path = tmp_path / "governed-request-feed.json"
    feed_path.write_text('[{"trace_id":"old"}]{"trace_id":"extra"}', encoding="utf-8")

    updated = append_governed_request_feed(
        feed_path,
        {
            "timestamp": "2026-04-21T08:50:00+00:00",
            "trace_id": "new",
            "handoff_allowed": True,
        },
    )

    assert [item["trace_id"] for item in updated] == ["new"]
    persisted = json.loads(feed_path.read_text(encoding="utf-8"))
    assert [item["trace_id"] for item in persisted] == ["new"]
