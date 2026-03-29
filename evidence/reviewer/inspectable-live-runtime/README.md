Inspectable live runtime evidence captured from the production-simulated control-plane path on 2026-03-28 UTC.

Use this folder as the reviewer entry point:
- `allowed-flow.json` documents the successful governed runtime path and points to the raw artifacts.
- `denied-flow.json` documents the denied handoff path and points to the raw artifacts.
- `denied-identity-flow.json` documents fail-closed denial when live Keycloak-backed identity cannot be established.
- `denied-opa-flow.json` documents fail-closed denial when live OPA is unavailable or denies.
- `denied-retrieval-flow.json` documents fail-closed denial when live retrieval cannot satisfy governed boundary checks.
- `denied-secret-flow.json` documents fail-closed denial when a required secret cannot be retrieved.
- `live-launch-gate-downgrade.json` documents the live-evidence path where missing trace continuity downgrades readiness and blocks handoff.

The raw files remain under `evidence/prod-sim/` so the evidence stays traceable to the captured responses.
