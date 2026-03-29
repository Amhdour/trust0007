Inspectable live runtime evidence captured from the production-simulated control-plane path on 2026-03-28 UTC.

Use this folder as the reviewer entry point:
- `allowed-flow.json` documents the successful governed runtime path and points to the raw artifacts.
- `denied-flow.json` documents the denied handoff path and points to the raw artifacts.
- `denied-identity-flow.json` documents fail-closed denial when live Keycloak-backed identity cannot be established.
- `denied-opa-flow.json` documents fail-closed denial when live OPA is unavailable or denies.
- `denied-retrieval-flow.json` documents fail-closed denial when live retrieval cannot satisfy governed boundary checks.
- `denied-secret-flow.json` documents fail-closed denial when a required secret cannot be retrieved.
- `live-launch-gate-downgrade.json` documents the live-evidence path where missing trace continuity downgrades readiness and blocks handoff.

Each scenario file now includes:
- proof sources
- representative artifact snapshots
- the final handoff result
- the dependency status that mattered most to the scenario

## Scenario Map

- Passing strict live flow:
  - file: `allowed-flow.json`
  - expected result: handoff allowed
  - key files to inspect:
    - `overlays/myStarterKit/artifacts/governed-flow-summary.json`
    - `overlays/myStarterKit/artifacts/launch-gate-result.json`
  - key fields to inspect:
    - `evidence_mode`
    - `decision`
    - `handoff_allowed`
    - `dependency_status`
  - what it proves:
    - the mandatory live path succeeded end to end
  - what it does not prove:
    - Envoy, Grafana, or Langfuse are mandatory request-path dependencies

- Denied identity flow:
  - file: `denied-identity-flow.json`
  - expected result: handoff denied
  - key fields to inspect:
    - `reason_codes`
    - `authenticated`
    - `live`
    - `handoff_allowed`
  - what it proves:
    - identity failure blocks the live path

- Denied OPA flow:
  - file: `denied-opa-flow.json`
  - expected result: handoff denied
  - key fields to inspect:
    - `engine`
    - `allow`
    - `reason_codes`
    - `handoff_allowed`
  - what it proves:
    - OPA failure or deny blocks the live path

- Denied retrieval flow:
  - file: `denied-retrieval-flow.json`
  - expected result: handoff denied
  - key fields to inspect:
    - `backend`
    - `result_count`
    - `reason_codes`
    - `handoff_allowed`
  - what it proves:
    - retrieval failure or boundary failure blocks the live path

- Denied secret flow:
  - file: `denied-secret-flow.json`
  - expected result: handoff denied
  - key fields to inspect:
    - `backend`
    - `required`
    - `fetched`
    - `reason_codes`
  - what it proves:
    - required secret failure blocks the live path

- Launch-gate downgrade / no-go:
  - file: `live-launch-gate-downgrade.json`
  - expected result: no-go and denied handoff
  - key fields to inspect:
    - `missing_evidence`
    - `complete`
    - `handoff_allowed`
  - what it proves:
    - missing live evidence can still block the handoff

Use [strict-live-proof-matrix.md](/workspaces/beta011/docs/strict-live-proof-matrix.md) alongside this folder when you need the exact acceptance criteria and pass/fail test mapping.
Use [reviewer-fast-path.md](/workspaces/beta011/docs/reviewer-fast-path.md) when you want the shortest route through the proof surface.
Use [dashboard-visual-proof.md](/workspaces/beta011/docs/dashboard-visual-proof.md) for the fast visual cues.

The raw files remain under `evidence/prod-sim/` so the evidence stays traceable to the captured responses.
