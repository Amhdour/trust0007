# Staging Governed Stack

This is the repo's production-like deployment path for proving the governed live handoff with real dependencies instead of fixture patching.

## First serious live-preview scope (minimum governed stack)

Success for the first serious preview is **not** “every vendored upstream is running.” It is the governed dashboard/control-plane path proving both runtime lanes with fail-closed controls and fresh evidence.

### Required services (proof path)

- `control_plane` (dashboard + governed launch routes)
- `keycloak` (+ `keycloak_db`) for live identity
- `opa` for policy decisions
- `qdrant` for retrieval checks
- `vault` for secret checks
- `onyx` runtime target (behind `/launch/onyx`)
- `dify` runtime target (behind `/launch/dify`)

### Optional/supporting services

- `langfuse` (evidence-plane destination)
- `grafana` (observability convenience)
- `envoy` (future ingress enforcement depth)

### Intentionally excluded from first preview success criteria

- Reference-only vendored upstreams in `upstream/` that are not in the governed launch proof path
- Additional optional systems (for example Superset, gVisor work) unless needed by your operator goals

## Files

- Compose target: `compose/docker-compose.production.yml`
- Env template: `compose/.env.production.example`
- Bootstrap: `scripts/bootstrap-live-governed-path.sh`
- Smoke test: `scripts/smoke-live-onyx-handoff.py`
- Real-stack Onyx test: `tests/integration/test_strict_live_onyx_end_to_end.py`
- Real-stack Dify test: `tests/integration/test_strict_live_dify_end_to_end.py`

## Local staging bootstrap

1. Copy the env template and replace the placeholder secrets.

```bash
cp compose/.env.production.example compose/.env.production
```

2. Bootstrap the governed stack.

```bash
make bootstrap-live
```

3. Verify live env guardrails, start the explicit live overlay, and run governed checks.

```bash
make verify-live
make up-live
make smoke-live
python scripts/bootstrap_runtime_evidence.py --control-plane-base-url http://127.0.0.1:3000
make test-live-stack
```

What this does:

- starts the production-like compose stack
- initializes and unseals Vault outside `-dev`
- starts Keycloak outside `start-dev`
- imports the governed realm template
- maps `tenant_id` from a real user attribute into token and userinfo claims
- seeds Qdrant and Vault with tenant-scoped launch data
- proves `/launch/onyx?path=/app&mode=live` against the running stack (deepest default sample lane)
- proves `/launch/dify?path=/apps&mode=live&mcp=mcp_server.dashboard_control_plane` under runtime-specific MCP governance
- writes fresh governed evidence artifacts consumed by the dashboard (`governed-flow-summary.json`, `onyx-runtime-proof.json`, `dify-runtime-proof.json`, and launch-gate-linked evidence)

## External deployment target

The same compose target can be used on a staging VM or similar host.

Required adjustments before calling it externally:

- set `CONTROL_PLANE_BASE_URL` to the public dashboard origin
- set `KEYCLOAK_HOSTNAME_URL` to the public Keycloak origin (scheme + host + port when non-default)
- replace every `replace-me` secret in `compose/.env.production`
- update the Keycloak redirect URI host in the env file so `control-plane-web` matches the deployed origin
- expose the dashboard and Keycloak through your ingress or reverse proxy

## Honest claim boundary

After the bootstrap, smoke test, and `live_stack` pytest pass, the repo proves a staging-style governed live handoff with real dependencies.

It still should not be described as a true live product workflow until the same path is exercised from an externally reachable environment outside localhost.
