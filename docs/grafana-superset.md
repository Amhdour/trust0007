# Grafana + Superset Integration (Scaffolding)

## Scope
Development scaffolding for dashboard and analytics integration using telemetry/audit artifacts.
No production metrics are generated here.

## Goals
- Define operational dashboard views in Grafana.
- Define evidence/analytics views in Superset.
- Document mapping from event artifacts to dashboard dimensions/metrics.
- Provide sample schemas and development-only examples.

## Data sources
Primary event artifact source:
- JSONL telemetry/audit stream (`telemetry/exports/sample_events.jsonl` schema-compatible).

Reference schema:
- `telemetry/exports/event_schema.json`

## Grafana operational dashboard focus
Example operational panels (scaffold):
- Request volume over time (`request.start`, `request.end`).
- Deny rate (`deny.event` / requests).
- Fallback rate (`fallback.event` / requests).
- Incident signal count (`incident.signal`).
- Tool execution attempts (`tool.execution_attempt`).
- Retrieval decision mix (`retrieval.decision` allow/deny/degrade).

## Superset evidence/analytics focus
Example analytical views:
- Policy outcomes by tenant and time bucket.
- Deny/fallback trend by tool and source.
- Retrieval decision distribution by source/trust labels.
- Incident signal correlation with deny/fallback spikes.

## Mapping from events to metrics
- **Deny rate** = `count(event_type='deny.event') / count(event_type='request.start')`
- **Fallback rate** = `count(event_type='fallback.event') / count(event_type='request.start')`
- **Tool usage** = `count(event_type='tool.execution_attempt')` grouped by `payload.tool_name`
- **Retrieval decisions** = count grouped by `payload.decision` for `event_type='retrieval.decision'`
- **Incident signals** = `count(event_type='incident.signal')`

## Filters
Recommended shared filters:
- time range
- tenant_id
- event_type
- severity
- tool_name (from payload)
- retrieval source (from payload)

## Artifacts in this scaffold
- Grafana dashboard spec scaffold: `telemetry/dashboards/grafana/operational-dashboard-spec.json`
- Superset evidence view scaffold: `telemetry/dashboards/superset/evidence-views.yaml`
- Export schema + sample dev dataset: `telemetry/exports/`
