# Overlays

`overlays/` contains governance and integration overlays layered on top of upstream projects.

## Scope

- `myStarterKit/` (submodule): baseline governance overlay from upstream.
- `governance-overlay/` (local): repository-owned additive wiring, contracts, and environment-specific glue.
- `client-template/` (local): tokenized scaffold for creating per-client overlays such as `client-acme/`.

Do not moonyx third-party upstream code directly in this repository; extend behavior via the local overlay and adapter/policy layers.
