# Upstream Sources

`upstream/` contains third-party source snapshots tracked by the main repository.

These folders are intentionally kept flat for compatibility with compose files, adapters, and local scripts, but they are not all equally active in the current architecture. The operational classification lives in [upstream-usage-matrix.md](/workspaces/beta011/docs/upstream-usage-matrix.md), the checkout/source lock lives in [upstream.lock.json](/workspaces/beta011/evidence/upstream.lock.json), and the dashboard-facing inventory lives in [upstream_usage.inventory.json](/workspaces/beta011/evidence/upstream_usage.inventory.json).

## Active Now

- `upstream/onyx`
- `upstream/keycloak`
- `upstream/opa`
- `upstream/qdrant`
- `upstream/vault`
- `upstream/langfuse`

## Supporting / Partial

- `upstream/envoy`
- `upstream/grafana`

## Optional Future

- `upstream/superset`
- `upstream/gvisor`

## Reference Only

- `upstream/keycloak-quickstarts`
- `upstream/opa-envoy-plugin`
- `upstream/langfuse-python`

## Repo Rule

Treat `upstream/*` as vendored third-party code. Make repo-owned behavior additive in `frontend/`, `backend/`, `adapters/`, `compose/`, `policies/`, `telemetry/`, `launch-gate/`, and `docs/`.
