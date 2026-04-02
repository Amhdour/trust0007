# Staging Governed Stack

This is the repo's production-like deployment path for proving the governed live handoff with real dependencies instead of fixture patching.

## Files

- Compose target: `compose/docker-compose.production.yml`
- Env template: `compose/.env.production.example`
- Bootstrap: `scripts/bootstrap-live-governed-path.sh`
- Smoke test: `scripts/smoke-live-onyx-handoff.py`
- Real-stack tests: `tests/integration/test_strict_live_http_end_to_end.py`

## Local staging bootstrap

1. Copy the env template and replace the placeholder secrets.

```bash
cp compose/.env.production.example compose/.env.production
```

2. Bootstrap the governed stack.

```bash
make bootstrap-live
```

3. Verify the live handoff.

```bash
make smoke-live
make test-live-stack
```

What this does:

- starts the production-like compose stack
- initializes and unseals Vault outside `-dev`
- starts Keycloak outside `start-dev`
- imports the governed realm template
- maps `tenant_id` from a real user attribute into token and userinfo claims
- seeds Qdrant and Vault with tenant-scoped launch data
- proves `/launch/onyx?path=/app&mode=live` against the running stack

## External deployment target

The same compose target can be used on a staging VM or similar host.

Required adjustments before calling it externally:

- set `CONTROL_PLANE_BASE_URL` to the public dashboard origin
- set `KEYCLOAK_HOSTNAME` to the public Keycloak hostname
- replace every `replace-me` secret in `compose/.env.production`
- update the Keycloak redirect URI host in the env file so `control-plane-web` matches the deployed origin
- expose the dashboard and Keycloak through your ingress or reverse proxy

## Honest claim boundary

After the bootstrap, smoke test, and `live_stack` pytest pass, the repo proves a staging-style governed live handoff with real dependencies.

It still should not be described as a true live product workflow until the same path is exercised from an externally reachable environment outside localhost.
