# .devcontainer

Scaffold directory for additive AI Trust & Security stack implementation.

- `post-create.sh` initializes managed submodules when the Codespace is first created.
- `post-start.sh` now defaults to live governed startup in Codespaces (`CODEX_DEVCONTAINER_BOOT_MODE=auto`):
  - boots the production-like compose stack with Onyx + Dify runtime lanes,
  - runs `scripts/bootstrap-live-governed-path.sh`,
  - generates fresh dual-runtime artifacts via `scripts/bootstrap_runtime_evidence.py`,
  - and skips expensive work on reattach when services and evidence are already healthy.

Override behavior with:
- `CODEX_DEVCONTAINER_BOOT_MODE=live` to force live bootstrap.
- `CODEX_DEVCONTAINER_BOOT_MODE=local` to use legacy local control-plane startup only.
