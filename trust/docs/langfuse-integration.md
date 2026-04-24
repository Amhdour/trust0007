# Langfuse Integration (Telemetry Export)

## Scope
Langfuse-ready export adapter for internal telemetry events. This phase provides mapping and exporter behavior without requiring live credentials.

## Deliverables
- `adapters/observability/langfuse/` mapper/exporter/schemas.
- `tests/observability/` coverage using stub clients.

## Mapping model
Internal `TelemetryEvent` is mapped to Langfuse-friendly records:
- `request.start`, `request.end` -> `trace` records
- other exported event types -> `span` records

Mapped fields include:
- `trace_id`
- `request_id` (inside metadata)
- `event_type` -> `name`
- `timestamp`, `tenant_id`, `severity`, sanitized payload metadata

## Separation of internal vs external data
By default, exporter excludes internal audit-only event types:
- `deny.event`
- `incident.signal`

Additionally, payload keys prefixed with `internal_` are sanitized out before export.

## What is exported
- Request lifecycle and operational decisions suitable for observability traces/spans.
- Metadata safe for external telemetry systems.

## What stays internal
- Internal-only audit events by default (`deny.event`, `incident.signal`).
- Payload fields explicitly marked `internal_*`.
- Any local raw audit logs outside exporter pipeline.

## Credentials/testing
- Exporter accepts a client-like interface (`ingest(record)`), enabling tests with in-memory stubs.
- No live Langfuse credentials are required for tests in this phase.
