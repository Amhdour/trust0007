# Upstream Sources

`upstream/` contains third-party source snapshots tracked by the main repository.

These folders are intentionally kept flat for compatibility with compose files, adapters, and local scripts, but they are not all equally active in the current architecture. The operational classification lives in [upstream-usage-matrix.md](/workspaces/beta011/docs/upstream-usage-matrix.md), the checkout/source lock lives in [upstream.lock.json](/workspaces/beta011/evidence/upstream.lock.json), and the dashboard-facing inventory lives in [upstream_usage.inventory.json](/workspaces/beta011/evidence/upstream_usage.inventory.json).

Use `python /workspaces/beta011/scripts/list-upstream-groups.py` to see the default versus opt-in checkout groups, `python /workspaces/beta011/scripts/record-upstream-refresh.py ...` whenever a vendored snapshot is intentionally refreshed and needs a pinned ref/commit recorded, and `python /workspaces/beta011/scripts/sync-upstream-pins-from-checkout.py` when the vendored paths are standalone upstream git checkouts with real pin metadata available.

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
