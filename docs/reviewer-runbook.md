# Reviewer / Operator Runbook (Live Readiness)

Use this runbook when you need to validate the control plane end-to-end in one pass.

## 1) What this project proves

- **Onyx lane (RAG):** governed retrieval runtime handoff (`/launch/onyx`).
- **Dify lane (Autonomous Agents):** governed tool/MCP runtime handoff (`/launch/dify`).
- **Shared trust/security control plane:** identity, policy, retrieval/tool controls, secret access, trace continuity, and launch-gate decision are enforced before runtime access.

## 2) What “good” looks like

- Live stack starts with explicit live/staging env values.
- `make smoke-live` succeeds.
- Strict live tests for **both runtimes** pass.
- Dashboard shows `LIVE GOVERNED MODE`, current evidence, and runtime portfolio cards for Onyx + Dify.
- Artifacts under `overlays/myStarterKit/artifacts/` are current (new trace IDs and timestamps).

## 3) What “not ready” looks like

- Dashboard is in demo/fallback mode while claiming live readiness.
- Dev-mode toggles are still enabled in staging/live env (`*_DEV_MODE=true`).
- Missing identity/policy/retrieval/trace evidence in `governed-flow-summary.json`.
- Runtime lane is unreachable or denied without expected reason codes.
- Runtime proof artifacts (`onyx-runtime-proof.json`, `dify-runtime-proof.json`) are missing or stale.

## 4) Exact validation flow

1. **Prepare env files**
   ```bash
   cp compose/.env.production.example compose/.env.production
   cp .env.live.example .env.live
   ```
2. **Bring up stack and bootstrap live path**
   ```bash
   make bootstrap-live
   make verify-live
   make up-live
   ```
3. **Run smoke and strict live tests**
   ```bash
   make smoke-live
   pytest -q tests/integration/test_strict_live_onyx_end_to_end.py
   pytest -q tests/integration/test_strict_live_dify_end_to_end.py
   ```
4. **Inspect dashboard**
   - `/` (homepage decision + runtime portfolio)
   - `/launch/onyx?path=/app&mode=live`
   - `/launch/dify?path=/apps&mode=live&mcp=mcp_server.dashboard_control_plane`
5. **Inspect artifacts/logs**
   - `overlays/myStarterKit/artifacts/governed-flow-summary.json`
   - `overlays/myStarterKit/artifacts/identity-evidence.json`
   - `overlays/myStarterKit/artifacts/policy-evidence.json`
   - `overlays/myStarterKit/artifacts/retrieval-evidence.json`
   - `overlays/myStarterKit/artifacts/tool-evidence.json`
   - `overlays/myStarterKit/artifacts/launch-gate-result.json`
   - `overlays/myStarterKit/artifacts/audit-records.jsonl`

## 5) Runtime-specific checks

### Onyx (RAG)

- Allowed governed handoff passes for `/launch/onyx`.
- Retrieval evidence shows live backend participation and allowed boundaries.
- Runtime proof (`onyx-runtime-proof.json`) matches the latest summary trace.
- Denied behavior appears when token/dependency is invalid or unavailable.

### Dify (Autonomous Agents)

- Allowed governed handoff passes for `/launch/dify` with approved MCP server.
- Tool evidence shows MCP governance required + enforced.
- Runtime proof (`dify-runtime-proof.json`) is generated for live request.
- Denied behavior appears for unapproved MCP server (`policy.mcp_server_not_allowed:*`).

## 6) Common failure modes

- `startup.missing_required_env:*`: live/staging env file incomplete.
- `identity.*`: bearer token, realm, or Keycloak reachability issue.
- `policy.opa_unavailable`: OPA endpoint unavailable or misconfigured.
- `retrieval.backend_unavailable`: Qdrant down/unreachable.
- `vault_unavailable` or secret-key errors: Vault health/token/path mismatch.
- Launch-gate `no_go`: trace/evidence continuity incomplete, even if one dependency appears healthy.

## Mode boundaries (avoid overclaiming)

- **Local/dev:** for development/demo confidence only.
- **Live/staging:** for governed proof generation and realistic validation.
- **Public production:** environment-specific; not bundled as an always-on hosted deployment in this repo.
