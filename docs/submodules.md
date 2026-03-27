# Submodule Bootstrap & Update Guide

This repository vendors third-party projects via git submodules under `upstream/` and overlay sources under `overlays/`.

## Managed submodule paths
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
- `overlays/myStarterKit`

## Scripts
### 1) Bootstrap missing submodule definitions
```bash
bash scripts/bootstrap-submodules.sh
```

Behavior:
- Checks each target path.
- Adds a submodule only when the path is missing from `.gitmodules`.
- Leaves existing submodule entries unchanged.

### 2) Sync and update submodule working trees
```bash
bash scripts/update-submodules.sh
```

Behavior:
- Syncs submodule URLs from `.gitmodules`.
- Initializes and updates submodules recursively.
- Pulls latest configured remote commits for each submodule (`--remote`).

## Recommended workflow
1. Run bootstrap script after cloning (or when adding missing module definitions).
2. Commit `.gitmodules` and gitlink updates if bootstrap introduced new entries.
3. Run update script whenever you need to refresh submodule working trees.

## Notes
- `upstream/*` is treated as third-party code.
- Avoid direct modifications in upstream repositories unless strictly necessary.
