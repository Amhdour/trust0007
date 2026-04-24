# Telemetry Model

## Goals
- Keep event schema consistent across governance layers.
- Ensure every event includes `trace_id` and `request_id`.
- Produce JSONL-friendly artifacts for local debugging and pipeline handoff.
- Preserve future export compatibility for Langfuse and dashboard systems.

## Canonical event schema
Each event uses the same top-level fields:
- `event_type`
- `trace_id`
- `request_id`
- `timestamp`
- `tenant_id`
- `severity`
- `payload` (event-specific details)

## Required event types
- `request.start`
- `identity.established`
- `policy.decision`
- `retrieval.decision`
- `tool.decision`
- `tool.execution_attempt`
- `confirmation.required`
- `deny.event`
- `fallback.event`
- `request.end`
- `incident.signal`

## JSONL artifact model
`JsonlEventSink` writes one compact JSON object per line:
- easy to tail locally,
- easy to ingest by log forwarders,
- easy to transform into Langfuse/dashboard exports.

## Future export
- `telemetry/exporters.py` defines exporter interface.
- `LangfuseExporterStub` is the integration placeholder for future wiring.
