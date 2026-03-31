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
- `KEYCLOAK_HOST_PORT`
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

### Local governed-live bootstrap

If you want the strict local live path, use the repeatable bootstrap instead of manually recreating the Keycloak / Qdrant / Vault setup:

```bash
make bootstrap-live
```

That workflow:

- starts Keycloak, OPA, Qdrant, Vault, and the compose control plane
- imports or reuses the local dev realm
- applies the dev-only `tenant_id` mapper for the single-tenant local stack
- creates or refreshes the repeatable live bootstrap user
- seeds a tenant-scoped Qdrant record and the required Vault runtime secret
- starts the control plane in `live` mode

Then verify the governed live path with:

```bash
make smoke-live
```

The smoke test runs from the control-plane container so it uses the same Keycloak network path as the live governed handoff. It mints a real Keycloak token, requests `openid email profile` scope, calls `/launch/onyx?path=/app&mode=live`, and confirms the dashboard is showing live evidence.

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
- The governed live path is what is proven when `make smoke-live` passes. That is stronger than a general “the whole project is live” claim.
- Unauthenticated or non-live-token requests to `/launch/onyx` should still fail closed with `403`, even after the local live bootstrap succeeds.
- The local Keycloak bootstrap uses a dev-only hardcoded tenant mapper for `tenant-dashboard`. It is a local single-tenant convenience, not a production tenant-claim design.
- The local Keycloak smoke token must include `openid` scope. Without `openid`, Keycloak `userinfo` returns `403`, and the strict live handoff correctly denies access.
- In this environment, Keycloak defaults to host port `18080` instead of `8080` because another local service already occupies `8080`.
- In another Codespace, replace `orange-space-journey-7vrrp4wqq4r6h7p9` with that Codespace name and keep the same port suffix.
- Secrets are provided via environment variables and placeholders only.
- `vault` is configured in `-dev` mode for local development.
- Langfuse uses the local `db` PostgreSQL service by default.
- Superset loads its local config from `compose/superset/superset_config.py`.
