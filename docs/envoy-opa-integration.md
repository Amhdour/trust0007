# Envoy + OPA Integration (Local Development Stub)

> This is a **development stub** and is **not production-validated**.

## What is included
- Envoy example config: `compose/envoy/envoy.local.yaml`
- OPA example policy: `compose/opa/policy.rego`
- Optional compose overlay for local run: `compose/docker-compose.envoy-opa.yml`

## Where checks happen

1. **Authentication (JWT) placement in Envoy**
   - In `envoy.local.yaml`, the `jwt_authn` filter location is documented via comments in `http_filters`.
   - This is where token validation would happen before authorization checks.

2. **Authorization (external authz) in Envoy**
   - `envoy.filters.http.ext_authz` is configured in `http_filters`.
   - Envoy sends authorization check requests to OPA at:
     - `http://opa:8181/v1/data/envoy/authz`

3. **Policy decision in OPA**
   - OPA policy package: `envoy.authz`.
   - Rule `allow` decides if request should proceed.
   - Default behavior is deny.

## Local flow (stub)
1. Request enters Envoy listener on `:10000`.
2. (Future) JWT authn filter validates bearer token.
3. Envoy ext_authz sends request context to OPA.
4. OPA returns policy decision from `envoy.authz` rules.
5. Envoy allows or denies upstream routing to `onyx_runtime`.

## Run locally

Start base local stack first (creates `trust_stack` network):

```bash
docker compose --env-file compose/.env -f compose/docker-compose.yml up -d
```

Then start Envoy + OPA overlay:

```bash
docker compose --env-file compose/.env -f compose/docker-compose.yml -f compose/docker-compose.envoy-opa.yml up -d envoy opa
```

Stop overlay services:

```bash
docker compose --env-file compose/.env -f compose/docker-compose.yml -f compose/docker-compose.envoy-opa.yml down
```

## Notes
- This stub intentionally keeps policy simple for development iteration.
- JWT configuration values (issuer, JWKS, audiences) are not wired yet.
- Envoy/OPA behavior should be validated end-to-end before production use.
