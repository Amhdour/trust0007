# Retrieval Security Layer (Initial)

## Scope
Framework-agnostic retrieval security enforcement that can sit between runtime and any retrieval backend.

## Implemented capabilities
- Source allowlists.
- Tenant/source boundaries.
- Trust labels on request/document context.
- Retrieval-time filtering.
- Deny or degrade behavior on policy failure.
- Provenance and citation-ready metadata.
- Quarantine handling for untrusted ingestion.

## Components
- Adapter layer: `adapters/retrieval/`
- Retrieval policy model: `policies/retrieval/policy.rego`
- Tests: `tests/retrieval/`

## Security model

### 1) Source allowlists
Only allow retrieval from approved sources (e.g., `qdrant`, `kb`, `docs`).

### 2) Tenant/source boundaries
A tenant can only query explicitly allowed sources.

### 3) Trust labels
Requests can carry expected trust labels. Documents with non-matching trust labels are filtered.

### 4) Retrieval-time filtering
The adapter filters candidate results by:
- tenant match,
- source match,
- trust-label match,
- quarantine exclusion.

### 5) Deny or degrade on policy failure
- **Deny**: policy says `allow=false` or mode `deny`.
- **Degrade**: policy says `mode=degrade`; adapter applies stricter result shaping (top N subset).

### 6) Provenance and citation-ready metadata
The adapter emits citation records with doc ID, source, tenant, trust label, and provenance metadata.

### 7) Quarantine concept
`quarantined=true` documents are always excluded from retrieval outputs, regardless of other checks.

## Framework-agnostic design
- No direct dependency on Onyx internals.
- Uses interfaces for backend search, policy evaluator, and telemetry emitter.
- Can be integrated by any runtime that can produce `RetrievalRequest` DTOs.
