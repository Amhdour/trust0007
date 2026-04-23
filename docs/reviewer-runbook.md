# Reviewer / Operator Runbook (Live Readiness)

Use this runbook for a one-pass validation of the governed control plane.

## Minimum serious live-preview scope

Do **not** treat success as “run every upstream project under `upstream/`.”  
For this repo, a meaningful live preview is the governed control plane proving **both** runtime lanes:

- `/launch/onyx` (Onyx / RAG)
- `/launch/onyx/agent` (Onyx Agent / Autonomous Agents)

### Required for first-proof success

- `control_plane`
- `keycloak` + `keycloak_db`
- `opa`
- `qdrant`
- `vault`
- reachable Onyx runtime target
- reachable Onyx Agent runtime target

### Optional/supporting for first-proof success

- `langfuse`
- `grafana`
- `envoy` (platform depth; not a current strict pass dependency)

### Intentionally excluded from first-proof success criteria

- reference-only vendored upstream snapshots
- optional future depth (for example Superset or gVisor work) unless your environment specifically needs them

## Start here (5-minute validation path)

1. **Prepare env files**

   ```bash
   cp compose/.env.production.example compose/.env.production
   cp .env.live.example .env.live
   ```

2. **Bootstrap and start live/staging mode**

   ```bash
   make bootstrap-live
   make verify-live
   make up-live
   ```

3. **Run strict proof checks**

   ```bash
   make smoke-live
   pytest -q tests/integration/test_strict_live_onyx_end_to_end.py
   pytest -q tests/integration/test_live_end_to_end.py
   ```

4. **Check dashboard + governed entrypoints**
   - `/` (homepage decision + runtime portfolio)
   - `/launch/onyx?path=/app&mode=live`
   - `/launch/onyx/agent&mode=live&mcp=mcp_server.dashboard_control_plane`

5. **Confirm fresh artifacts + trace continuity**
   - `overlays/myStarterKit/artifacts/governed-flow-summary.json`
   - `overlays/myStarterKit/artifacts/launch-gate-result.json`
   - `overlays/myStarterKit/artifacts/identity-evidence.json`
   - `overlays/myStarterKit/artifacts/policy-evidence.json`
   - `overlays/myStarterKit/artifacts/retrieval-evidence.json`
   - `overlays/myStarterKit/artifacts/tool-evidence.json`
   - `overlays/myStarterKit/artifacts/audit-records.jsonl`

Related docs:

- Reviewer landing: [reviewer-fast-path.md](reviewer-fast-path.md)
- Visual cues (illustrative): [dashboard-visual-proof.md](dashboard-visual-proof.md)
- Strict proof map: [strict-live-proof-matrix.md](strict-live-proof-matrix.md)
- README deployment modes: [Deployment Maturity and Modes](../README.md#deployment-maturity-and-modes)

## What this project proves

This repository proves a **dashboard-first trust control plane** for two governed runtime lanes:

- **Onyx lane (RAG):** governed retrieval handoff at `/launch/onyx`.
- **Onyx Agent lane (Autonomous Agents):** governed tool/MCP handoff at `/launch/onyx/agent`.
- **Shared controls before runtime access:** identity, policy, retrieval/tool controls, secrets, trace continuity, and launch-gate decision.

## What good looks like

- Live stack starts with explicit live/staging env values.
- `make smoke-live` succeeds.
- Strict live tests pass for **both** runtime lanes.
- Dashboard shows `LIVE GOVERNED MODE` and current runtime portfolio cards for Onyx capability lanes.
- Latest artifacts show fresh timestamps and trace IDs.

## Runtime-specific checks

### Onyx (RAG)

- `/launch/onyx` allowed handoff succeeds in live mode.
- Retrieval evidence shows live backend participation + allowed boundaries.
- `onyx-runtime-proof.json` aligns with latest summary trace.
- Denied behavior appears with invalid token/dependency failure.

### Onyx Agentic (MCP/Tools)

- `/launch/onyx/agent` succeeds only with approved MCP server.
- Tool evidence shows MCP governance is enforced.
- `onyx-agent-runtime-proof.json` is generated for the live request.
- Unapproved MCP server denies with `policy.mcp_server_not_allowed:*`.

## Common failure signals (dashboard symptom -> likely cause)

- Dashboard fallback/demo cues in a claimed live run -> mode mismatch or missing live env.
- `startup.missing_required_env:*` -> incomplete `.env.live`/production env values.
- `identity.*` denies -> bearer token, realm mapping, or Keycloak reachability issue.
- `policy.opa_unavailable` -> OPA endpoint down or misconfigured.
- `retrieval.backend_unavailable` -> Qdrant unavailable.
- `vault_unavailable` / secret key errors -> Vault health/token/path mismatch.
- Launch gate `NO-GO` with partial passing dependencies -> missing trace/evidence continuity.

## What not ready looks like

- Live readiness claimed while dashboard is still demo/fallback mode.
- Dev toggles enabled in live/staging (`*_DEV_MODE=true`).
- Missing identity/policy/retrieval/trace entries in governed flow summary.
- Runtime lane unreachable or denied without expected reason code.
- Runtime proof artifacts missing/stale.

## Mode boundaries (avoid overclaiming)

- **Local/dev:** development and demo confidence only.
- **Live/staging:** governed proof generation and realistic validation.
- **Public production:** environment-specific; no always-on hosted deployment is bundled in this repo.

## Next milestone (external preview)

- Reproduce this exact governed dual-runtime proof path from **one externally reachable staging deployment outside localhost**.

For top-level framing, see [README deployment maturity and operating modes](../README.md#deployment-maturity-and-modes).
