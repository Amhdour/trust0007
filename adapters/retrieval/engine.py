from __future__ import annotations

from typing import List

from .interfaces import RetrievalBackend, RetrievalPolicyEvaluator, RetrievalTelemetry
from .schemas import RetrievalDecision, RetrievalDocument, RetrievalRequest


class RetrievalSecurityLayer:
    """Framework-agnostic retrieval security enforcement layer."""

    def __init__(
        self,
        backend: RetrievalBackend,
        policy_evaluator: RetrievalPolicyEvaluator,
        telemetry: RetrievalTelemetry,
    ) -> None:
        self._backend = backend
        self._policy = policy_evaluator
        self._telemetry = telemetry

    def evaluate(self, request: RetrievalRequest) -> RetrievalDecision:
        policy = self._policy.evaluate(request)
        allow = bool(policy.get("allow", False))
        mode = policy.get("mode", "deny")
        reasons = list(policy.get("reasons", []))

        self._telemetry.emit(
            "retrieval.policy.decision",
            {
                "request_id": request.request_id,
                "tenant_id": request.tenant_id,
                "source": request.source,
                "allow": allow,
                "mode": mode,
                "reasons": reasons,
            },
        )

        if not allow or mode == "deny":
            return RetrievalDecision(
                allow=False,
                mode="deny",
                reasons=reasons or ["retrieval denied by policy"],
                citations=[],
                filtered_documents=[],
            )

        docs = list(self._backend.search(request))
        filtered = self._filter_documents(request, docs, degrade=(mode == "degrade"))

        citations = [self._citation_for(doc) for doc in filtered] if request.require_citations else []

        decision = RetrievalDecision(
            allow=True,
            mode="degrade" if mode == "degrade" else "allow",
            reasons=reasons,
            citations=citations,
            filtered_documents=filtered,
        )

        self._telemetry.emit(
            "retrieval.filter.applied",
            {
                "request_id": request.request_id,
                "tenant_id": request.tenant_id,
                "returned_docs": len(filtered),
                "mode": decision.mode,
            },
        )

        return decision

    def _filter_documents(
        self,
        request: RetrievalRequest,
        docs: List[RetrievalDocument],
        degrade: bool,
    ) -> List[RetrievalDocument]:
        filtered: List[RetrievalDocument] = []
        for doc in docs:
            if doc.quarantined:
                continue
            if doc.tenant_id != request.tenant_id:
                continue
            if doc.source != request.source:
                continue
            if request.trust_labels and doc.trust_label not in request.trust_labels:
                continue
            filtered.append(doc)

        if degrade:
            # Degrade mode: stricter result shaping to reduce risk blast radius.
            return filtered[: min(3, len(filtered))]

        return filtered

    @staticmethod
    def _citation_for(doc: RetrievalDocument) -> dict:
        return {
            "doc_id": doc.doc_id,
            "source": doc.source,
            "tenant_id": doc.tenant_id,
            "trust_label": doc.trust_label,
            "provenance": doc.provenance,
        }
