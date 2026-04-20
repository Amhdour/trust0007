# Local Development Stack (Codespaces)

This stack is **development-focused** and intentionally minimal. It is not production hardened.

If you want the production-like governed live path, use [staging-governed-stack.md](staging-governed-stack.md) instead of this page.

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

These services are not all equally active in the current request path. The dashboard and governed runtime handoffs (`/launch/onyx`, `/launch/dify`) are the primary proof path. In `demo` mode, the repo can still run with local fallback behavior. In `live` mode, Keycloak, OPA, Qdrant, and conditional Vault access become fail-closed dependencies in the governed handoff path. See `docs/upstream-usage-matrix.md` and `docs/live-vs-demo-matrix.md`.

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

### Governed live staging bootstrap

If you want the strict live path with non-dev Keycloak and Vault, use the staging bootstrap instead of manually recreating the identity / retrieval / secret setup:

```bash
cp compose/.env.production.example compose/.env.production
make bootstrap-live
```

That workflow:

- starts the production-like compose stack
- imports or reuses the governed realm
- applies the user-attribute `tenant_id` mapper to the live clients
- creates or refreshes the repeatable live bootstrap user
- seeds a tenant-scoped Qdrant record and the required Vault runtime secret
- starts the control plane in `live` / `staging` mode

Then verify the governed live path with:

```bash
make smoke-live
```

The smoke test mints a real Keycloak token, requests `openid email profile` scope, calls the governed Onyx live route (`/launch/onyx?path=/app&mode=live`), and confirms the dashboard is showing live evidence.

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
- Control plane dashboard: `https://<codespace-name>-3000.<forwarding-domain>`
- Keycloak: `https://<codespace-name>-8080.<forwarding-domain>`
- Envoy: `https://<codespace-name>-10000.<forwarding-domain>`
- OPA: `https://<codespace-name>-8181.<forwarding-domain>`
- Vault: `https://<codespace-name>-8200.<forwarding-domain>`
- Qdrant: `https://<codespace-name>-6333.<forwarding-domain>`
- Langfuse: `https://<codespace-name>-3002.<forwarding-domain>`
- Grafana: `https://<codespace-name>-3001.<forwarding-domain>`
- Superset: `https://<codespace-name>-8088.<forwarding-domain>`

## Notes
- The dashboard is the main landing page and aggregates posture from repo-owned artifacts plus supporting services.
- Onyx (RAG) and Dify (Autonomous Agents) are governed runtime lanes. Onyx is the deepest default smoke-path runtime and is started separately from the default compose stack.
- Use `mode=live` on governed endpoints only after Keycloak, OPA, Qdrant, and Vault are configured; live mode is fail-closed by design.
- The governed live path is what is proven when `make smoke-live` passes. That is stronger than a general “the whole project is live” claim.
- `make health-check` is the fastest honest project-health answer: it validates the stack, pings the dashboard, runs the live smoke path, and executes the focused governed-flow pytest bundle.
- Unauthenticated or non-live-token requests to `/launch/onyx` and `/launch/dify` should still fail closed with `403`, even after the local live bootstrap succeeds.
- The local Keycloak smoke token must include `openid` scope. Without `openid`, Keycloak `userinfo` returns `403`, and the strict live handoff correctly denies access.
- In this environment, Keycloak defaults to host port `18080` instead of `8080` because another local service already occupies `8080`.
- In another Codespace, replace `<codespace-name>` and `<forwarding-domain>` while keeping the same port suffixes.
- Secrets are provided via environment variables and placeholders only.
- `vault` remains configured in `-dev` mode only in the development compose file. The staging bootstrap uses non-dev Vault storage and init/unseal.
- Langfuse uses the local `db` PostgreSQL service by default.
- Superset loads its local config from `compose/superset/superset_config.py`.
