# scripts

Helper scripts for demo, vendored upstream source management, and local control-plane workflows.

- `run-demo.sh`: executes the minimal governed request flow.
- `test-demo.sh`: validates demo artifacts.
- `test-onyx-target.sh`: validates that the repo is still wired around Onyx as the primary runtime target.
- `start-control-plane.sh`: serves the local dashboard API/UI shell.
- `bootstrap-live-governed-path.sh`: starts the production-like compose stack, initializes Vault, configures Keycloak, seeds Qdrant/Vault, and brings the control plane up in `live` / `staging` mode.
- `smoke-live-onyx-handoff.py`: mints a real Keycloak token and verifies the governed `/launch/onyx?mode=live` handoff plus live dashboard evidence.
- `check-project-health.sh`: prints stack status, verifies the dashboard health endpoint, runs the live smoke path, and executes a focused pytest bundle for the most important governed dashboard/runtime flows.
- `bootstrap-submodules.sh`: declares missing managed overlay submodules that are still intentionally linked.
- `update-submodules.sh`: syncs and refreshes the managed overlay submodule working trees.
- `validate-upstream-state.py`: checks that vendored upstream paths, the upstream lock manifest, and the dashboard inventory remain consistent.
- `list-upstream-groups.py`: prints the default and opt-in vendored upstream checkout groups from the lock manifest.
- `record-upstream-refresh.py`: records a vendored upstream ref/commit refresh into `evidence/upstream.lock.json`.
- `sync-upstream-pins-from-checkout.py`: attempts to fill `source_ref` and `source_commit` from local standalone upstream git checkouts when that metadata is available.
- `stage-default-upstream-checkout.py`: creates a non-destructive staged checkout containing only the default upstream group, leaving opt-in upstreams out.
- `init-client-template.py`: materializes a tokenized client overlay from `overlays/client-template/` into `overlays/client-<slug>/` for client delivery work.
