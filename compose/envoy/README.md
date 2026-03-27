# Envoy OPA Integration Stub

This folder contains local-development Envoy config examples.

- `envoy.local.yaml`: listener/route/filter-chain showing where JWT authn and external authz would be applied.

Notes:
- JWT filter section is commented as a placement guide.
- `ext_authz` is configured to call OPA at `/v1/data/envoy/authz`.
- Upstream `onyx_runtime` cluster points to a local placeholder address.
