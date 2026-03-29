from __future__ import annotations

from collections import Counter
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
        required_trust_labels = list(policy.get("required_trust_labels", request.trust_labels))
        required_provenance_fields = list(policy.get("required_provenance_fields", []))
        deny_on_empty = bool(policy.get("deny_on_empty_result", False))

        self._telemetry.emit(
            "retrieval.policy.decision",
            {
                "request_id": request.request_id,
                "tenant_id": request.tenant_id,
                "source": request.source,
                "allow": allow,
                "mode": mode,
                "reasons": reasons,
                "required_trust_labels": required_trust_labels,
                "required_provenance_fields": required_provenance_fields,
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
        filtered, filter_failures = self._filter_documents(
            request,
            docs,
            degrade=(mode == "degrade"),
            required_trust_labels=required_trust_labels,
            required_provenance_fields=required_provenance_fields,
        )

        if not filtered and deny_on_empty:
            failure_reasons = list(dict.fromkeys(reasons + sorted(filter_failures.elements())))
            if "retrieval.empty_result" not in failure_reasons:
                failure_reasons.append("retrieval.empty_result")
            return RetrievalDecision(
                allow=False,
                mode="deny",
                reasons=failure_reasons,
                citations=[],
                filtered_documents=[],
            )

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
        required_trust_labels: List[str],
        required_provenance_fields: List[str],
    ) -> tuple[List[RetrievalDocument], Counter[str]]:
        filtered: List[RetrievalDocument] = []
        failures: Counter[str] = Counter()
        for doc in docs:
            if doc.quarantined:
                failures["retrieval.document_quarantined"] += 1
                continue
            if doc.tenant_id != request.tenant_id:
                failures["retrieval.cross_tenant_filtered"] += 1
                continue
            if doc.source != request.source:
                failures["retrieval.source_mismatch"] += 1
                continue
            if required_trust_labels and doc.trust_label not in required_trust_labels:
                failures["retrieval.trust_label_not_allowed"] += 1
                continue
            missing_provenance = [
                field_name
                for field_name in required_provenance_fields
                if not doc.provenance.get(field_name)
            ]
            if missing_provenance:
                failures["retrieval.provenance_missing"] += 1
                continue
            filtered.append(doc)

        if degrade:
            # Degrade mode: stricter result shaping to reduce risk blast radius.
            return filtered[: min(3, len(filtered))], failures

        return filtered, failures

    @staticmethod
    def _citation_for(doc: RetrievalDocument) -> dict:
        return {
            "doc_id": doc.doc_id,
            "source": doc.source,
            "tenant_id": doc.tenant_id,
            "trust_label": doc.trust_label,
            "provenance": doc.provenance,
        }
