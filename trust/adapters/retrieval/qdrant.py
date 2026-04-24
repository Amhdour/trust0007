from __future__ import annotations

import json
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .interfaces import RetrievalBackend
from .schemas import RetrievalDocument, RetrievalRequest


class QdrantRetrievalBackend(RetrievalBackend):
    """Minimal Qdrant-backed retrieval bridge using filtered point scrolling."""

    def __init__(self, base_url: str, collection: str, timeout_seconds: float = 5.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._collection = collection
        self._timeout_seconds = timeout_seconds
        self._last_query: dict[str, Any] = {}

    def search(self, request: RetrievalRequest) -> Iterable[RetrievalDocument]:
        body = {
            "limit": 8,
            "with_payload": True,
            "filter": {
                "must": [
                    {"key": "tenant_id", "match": {"value": request.tenant_id}},
                    {"key": "source", "match": {"value": request.source}},
                ]
            },
        }
        self._last_query = {
            "backend": "qdrant",
            "collection": self._collection,
            "filters": body["filter"],
            "tenant_id": request.tenant_id,
            "source": request.source,
        }
        http_request = Request(
            f"{self._base_url}/collections/{self._collection}/points/scroll",
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(http_request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise RuntimeError("qdrant_unavailable") from exc

        points = payload.get("result", {}).get("points", []) or []
        docs: list[RetrievalDocument] = []
        lowered_query = request.query.lower().strip()
        for point in points:
            point_payload = point.get("payload", {}) or {}
            content = str(point_payload.get("content", ""))
            if lowered_query and lowered_query not in content.lower():
                continue
            docs.append(
                RetrievalDocument(
                    doc_id=str(point.get("id", "")),
                    tenant_id=str(point_payload.get("tenant_id", "")),
                    source=str(point_payload.get("source", request.source)),
                    content=content,
                    trust_label=str(point_payload.get("trust_label", "")),
                    quarantined=bool(point_payload.get("quarantined", False)),
                    provenance=dict(point_payload.get("provenance", {})),
                )
            )
        self._last_query["result_count"] = len(docs)
        return docs

    def last_query_metadata(self) -> dict[str, Any]:
        return dict(self._last_query)
