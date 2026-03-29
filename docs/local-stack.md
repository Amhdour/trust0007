# Local Development Stack (Codespaces)

This stack is **development-focused** and intentionally minimal. It is not production hardened.

## Services
- control-plane dashboard homepage
- postgres (Langfuse backing database)
- keycloak
- envoy
- opa
- vault (dev mode)
- qdrant
- langfuse
- grafana
- superset

Compose file: `compose/docker-compose.yml`

These services are not all equally active in the current request path. The dashboard and governed Onyx handoff are the primary proof path. In `demo` mode, the repo can still run with local fallback behavior. In `live` mode, Keycloak, OPA, Qdrant, and conditional Vault access become fail-closed dependencies in the governed handoff path. See `docs/upstream-usage-matrix.md` and `docs/live-vs-demo-matrix.md`.

## 1) Configure environment

```bash
cp compose/.env.example compose/.env
```

Update placeholder values in `compose/.env` before starting.

Important live-mode variables:
- `CONTROL_PLANE_GOVERNANCE_MODE`
- `CONTROL_PLANE_KEYCLOAK_BASE_URL`
- `CONTROL_PLANE_KEYCLOAK_REALM`
- `CONTROL_PLANE_OPA_URL`
- `CONTROL_PLANE_QDRANT_URL`
- `CONTROL_PLANE_QDRANT_COLLECTION`
- `CONTROL_PLANE_VAULT_ADDR`
- `CONTROL_PLANE_VAULT_TOKEN`
- `CONTROL_PLANE_ONYX_SECRET_PATH`
- `CONTROL_PLANE_ONYX_SECRET_KEY`

## 2) Start the stack

```bash
docker compose --env-file compose/.env -f compose/docker-compose.yml up -d
```

To stream logs:

```bash
docker compose --env-file compose/.env -f compose/docker-compose.yml logs -f
```

## 3) Stop the stack

```bash
docker compose --env-file compose/.env -f compose/docker-compose.yml down
```

To also remove named volumes:

```bash
docker compose --env-file compose/.env -f compose/docker-compose.yml down -v
```

## Service endpoints (Codespaces preview URLs)
- Control plane dashboard: `https://orange-space-journey-7vrrp4wqq4r6h7p9-3000.app.github.dev`
- Keycloak: `https://orange-space-journey-7vrrp4wqq4r6h7p9-8080.app.github.dev`
- Envoy: `https://orange-space-journey-7vrrp4wqq4r6h7p9-10000.app.github.dev`
- OPA: `https://orange-space-journey-7vrrp4wqq4r6h7p9-8181.app.github.dev`
- Vault: `https://orange-space-journey-7vrrp4wqq4r6h7p9-8200.app.github.dev`
- Qdrant: `https://orange-space-journey-7vrrp4wqq4r6h7p9-6333.app.github.dev`
- Langfuse: `https://orange-space-journey-7vrrp4wqq4r6h7p9-3002.app.github.dev`
- Grafana: `https://orange-space-journey-7vrrp4wqq4r6h7p9-3001.app.github.dev`
- Superset: `https://orange-space-journey-7vrrp4wqq4r6h7p9-8088.app.github.dev`

## Notes
- The dashboard is the main landing page and aggregates posture from repo-owned artifacts plus supporting services.
- Onyx is the governed runtime target, but it is started separately from the default compose stack.
- Use `mode=live` on governed endpoints only after Keycloak, OPA, Qdrant, and Vault are configured; live mode is fail-closed by design.
- In another Codespace, replace `orange-space-journey-7vrrp4wqq4r6h7p9` with that Codespace name and keep the same port suffix.
- Secrets are provided via environment variables and placeholders only.
- `vault` is configured in `-dev` mode for local development.
- Langfuse uses the local `db` PostgreSQL service by default.
- Superset loads its local config from `compose/superset/superset_config.py`.
