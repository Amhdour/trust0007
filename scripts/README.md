# scripts

Helper scripts for demo, vendored upstream source management, and local control-plane workflows.

- `run-demo.sh`: executes the minimal governed request flow.
- `test-demo.sh`: validates demo artifacts.
- `test-onyx-target.sh`: validates that the repo is still wired around Onyx as the primary runtime target.
- `start-control-plane.sh`: serves the local dashboard API/UI shell.
- `bootstrap-submodules.sh`: declares missing managed overlay submodules that are still intentionally linked.
- `update-submodules.sh`: syncs and refreshes the managed overlay submodule working trees.
- `validate-upstream-state.py`: checks that vendored upstream paths, the upstream lock manifest, and the dashboard inventory remain consistent.
- `list-upstream-groups.py`: prints the default and opt-in vendored upstream checkout groups from the lock manifest.
- `record-upstream-refresh.py`: records a vendored upstream ref/commit refresh into `evidence/upstream.lock.json`.
- `sync-upstream-pins-from-checkout.py`: attempts to fill `source_ref` and `source_commit` from local standalone upstream git checkouts when that metadata is available.
