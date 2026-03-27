from adapters.retrieval.engine import RetrievalSecurityLayer
from adapters.retrieval.interfaces import (
    InMemoryRetrievalTelemetry,
    RetrievalBackend,
    RetrievalPolicyEvaluator,
)
from adapters.retrieval.schemas import RetrievalDocument, RetrievalRequest


class StubBackend(RetrievalBackend):
    def __init__(self, docs):
        self._docs = docs

    def search(self, request: RetrievalRequest):
        return self._docs


class StubPolicyAllow(RetrievalPolicyEvaluator):
    def evaluate(self, request: RetrievalRequest) -> dict:
        return {"allow": True, "mode": "allow", "reasons": []}


class StubPolicyDeny(RetrievalPolicyEvaluator):
    def evaluate(self, request: RetrievalRequest) -> dict:
        return {"allow": False, "mode": "deny", "reasons": ["tenant/source boundary violation"]}


class StubPolicyDegrade(RetrievalPolicyEvaluator):
    def evaluate(self, request: RetrievalRequest) -> dict:
        return {"allow": True, "mode": "degrade", "reasons": ["trust labels missing"]}


def make_docs():
    return [
        RetrievalDocument(
            doc_id="d1",
            tenant_id="tenant-a",
            source="qdrant",
            content="doc one",
            trust_label="trusted",
            quarantined=False,
            provenance={"uri": "kb://one"},
        ),
        RetrievalDocument(
            doc_id="d2",
            tenant_id="tenant-a",
            source="qdrant",
            content="doc two",
            trust_label="trusted",
            quarantined=True,
            provenance={"uri": "kb://two"},
        ),
        RetrievalDocument(
            doc_id="d3",
            tenant_id="tenant-b",
            source="qdrant",
            content="doc three",
            trust_label="trusted",
            quarantined=False,
            provenance={"uri": "kb://three"},
        ),
    ]


def make_request() -> RetrievalRequest:
    return RetrievalRequest(
        request_id="r1",
        tenant_id="tenant-a",
        source="qdrant",
        query="incident summary",
        trust_labels=["trusted"],
        require_citations=True,
    )


def test_retrieval_happy_path_filters_and_citations() -> None:
    telemetry = InMemoryRetrievalTelemetry()
    layer = RetrievalSecurityLayer(
        backend=StubBackend(make_docs()),
        policy_evaluator=StubPolicyAllow(),
        telemetry=telemetry,
    )

    result = layer.evaluate(make_request())

    assert result.allow is True
    assert result.mode == "allow"
    assert [d.doc_id for d in result.filtered_documents] == ["d1"]
    assert result.citations[0]["doc_id"] == "d1"
    assert telemetry.events[0]["event_type"] == "retrieval.policy.decision"


def test_retrieval_deny_path() -> None:
    telemetry = InMemoryRetrievalTelemetry()
    layer = RetrievalSecurityLayer(
        backend=StubBackend(make_docs()),
        policy_evaluator=StubPolicyDeny(),
        telemetry=telemetry,
    )

    result = layer.evaluate(make_request())

    assert result.allow is False
    assert result.mode == "deny"
    assert result.filtered_documents == []
    assert "tenant/source boundary violation" in result.reasons


def test_retrieval_degrade_mode() -> None:
    telemetry = InMemoryRetrievalTelemetry()
    many_docs = [
        RetrievalDocument(
            doc_id=f"d{i}",
            tenant_id="tenant-a",
            source="qdrant",
            content=f"doc {i}",
            trust_label="trusted",
            quarantined=False,
            provenance={"uri": f"kb://{i}"},
        )
        for i in range(10)
    ]
    layer = RetrievalSecurityLayer(
        backend=StubBackend(many_docs),
        policy_evaluator=StubPolicyDegrade(),
        telemetry=telemetry,
    )

    result = layer.evaluate(make_request())

    assert result.allow is True
    assert result.mode == "degrade"
    assert len(result.filtered_documents) == 3
    assert "trust labels missing" in result.reasons
