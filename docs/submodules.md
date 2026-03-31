# Overlay Submodule & Vendored Upstream Guide

This repository tracks `upstream/*` as vendored source snapshots in the main repo checkout. The only currently managed git submodule is `overlays/myStarterKit`.

## Managed git submodule paths
- `overlays/myStarterKit`

## Vendored upstream paths

These are tracked as normal directories by the main repository, not as git submodules:

- `upstream/onyx`
- `upstream/keycloak`
- `upstream/keycloak-quickstarts`
- `upstream/envoy`
- `upstream/opa`
- `upstream/opa-envoy-plugin`
- `upstream/vault`
- `upstream/qdrant`
- `upstream/gvisor`
- `upstream/langfuse`
- `upstream/langfuse-python`
- `upstream/grafana`
- `upstream/superset`

The checkout/source lock for those paths lives in `evidence/upstream.lock.json`. Reviewer-facing classification lives in `evidence/upstream_usage.inventory.json`.

## Scripts
### 1) Bootstrap missing overlay submodule definitions
```bash
bash scripts/bootstrap-submodules.sh
```

Behavior:
- Checks the managed overlay target path.
- Adds a submodule only when the overlay path is missing from `.gitmodules`.
- Leaves existing submodule entries unchanged.

### 2) Sync and update managed overlay working trees
```bash
bash scripts/update-submodules.sh
```

Behavior:
- Syncs submodule URLs from `.gitmodules`.
- Initializes and updates submodules recursively.
- Pulls latest configured remote commits for each managed submodule (`--remote`).

### 3) Validate vendored upstream tracking state
```bash
python scripts/validate-upstream-state.py
```

Behavior:
- Confirms no `upstream/*` paths are declared as managed submodules.
- Confirms `evidence/upstream.lock.json` covers every vendored upstream exactly once.
- Confirms the lock manifest and dashboard inventory agree on path classification and runtime status.

### 4) Print default versus opt-in checkout groups
```bash
python scripts/list-upstream-groups.py
```

Behavior:
- Prints the upstream components that stay in the default checkout group.
- Prints the optional/reference upstream components that are explicitly treated as opt-in.

### 5) Record a vendored upstream refresh
```bash
python scripts/record-upstream-refresh.py envoy --ref vX.Y.Z --commit <sha> --notes "revalidated ingress config"
```

Behavior:
- Records the pinned upstream ref and commit in `evidence/upstream.lock.json`.
- Updates validation date and refresh notes so the vendored snapshot has a repo-visible refresh trail.

## Recommended workflow
1. Run bootstrap script after cloning if the overlay submodule is missing.
2. Commit `.gitmodules` and gitlink updates if bootstrap introduced new entries.
3. Run update script whenever you need to refresh managed overlay working trees.
4. Use `list-upstream-groups.py` to keep optional and reference upstreams explicitly opt-in in workflow decisions.
5. Use `record-upstream-refresh.py` whenever a vendored snapshot is intentionally updated.
6. Run the upstream validator whenever the vendored source set or classification model changes.

## Notes
- `upstream/*` is treated as third-party code.
- `upstream/*` is intentionally not declared in `.gitmodules` for this checkout model.
- Not every vendored upstream is an active runtime dependency; use `docs/upstream-usage-matrix.md` before making architecture claims.
- Avoid direct modifications in upstream repositories unless strictly necessary.
