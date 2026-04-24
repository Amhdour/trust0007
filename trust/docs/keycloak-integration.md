# Keycloak Identity Integration (Initial Design Skeleton)

> Scope: local-development integration design only. This is **not** a full production IAM implementation.

## 1) Login and session model

### Human/user login
- Primary model: OIDC Authorization Code Flow (with PKCE for browser clients).
- Keycloak acts as IdP and issues ID/access/refresh tokens.
- Envoy/edge and runtime components consume validated access tokens.

### Session lifecycle (development)
- Access token: short-lived (e.g., 5–15 minutes).
- Refresh token: longer-lived and revocable.
- Logout behavior should revoke refresh/session state where possible.

### Session assumptions
- Clients store tokens securely (no localStorage for sensitive web clients in production).
- Session invalidation and key rotation should be testable in local environments.

## 2) JWT validation assumptions

### Validation points
- Ingress (Envoy JWT filter placement already stubbed in `compose/envoy/envoy.local.yaml`).
- Runtime-side verification for defense in depth (especially for service edges).

### Required JWT checks
- Signature verification against JWKS.
- `iss` (issuer) exact match.
- `aud` (audience) includes expected client/service audience.
- `exp`, `nbf`, `iat` time checks with bounded skew.
- `azp` / `client_id` checks for client-specific access decisions.

### Development notes
- Use realm-scoped issuer URLs.
- Keep a local JWKS refresh interval and cache strategy documented.

## 3) Role mapping model

### Suggested roles
- `platform_admin`: global platform administration.
- `security_operator`: policy/security operations.
- `tenant_admin`: tenant-scoped administration.
- `tenant_user`: tenant-scoped application usage.
- `service_runtime`: non-human workload/service principal role.

### Mapping approach
- Realm roles for platform-wide permissions.
- Client roles for service-specific permissions.
- Map token claims -> internal authorization context in adapters/governance layer.

## 4) Service-to-service identity

- Preferred model: OIDC Client Credentials flow for machine identities.
- Each service gets distinct client ID + secret/cert.
- Service tokens should include least-privilege roles/scopes.
- Rotate service credentials and avoid shared clients across services.

## 5) Admin/operator role separation

- Separate administrative operations from runtime operations.
- Minimum split:
  - `platform_admin`: realm/client management and break-glass tasks.
  - `security_operator`: policy, audit, and incident response tasks.
  - `tenant_admin`: tenant-specific administration only.
- Prevent regular runtime/service users from receiving admin roles.

## 6) Tenant-aware claims expectations

Expected claims for tenant-aware authorization decisions:
- `tenant_id` (required for tenant-scoped operations)
- `tenant_roles` (tenant-scoped role list)
- `realm_access.roles` and/or `resource_access` for broader role context
- `sub` as stable principal ID
- `azp` / `client_id` to distinguish caller type

Behavioral expectations:
- Missing `tenant_id` for tenant-scoped endpoints => deny by default.
- Cross-tenant access requires explicit policy allow.
- Tenant claims must be propagated into policy context for OPA/myStarterKit checks.

## 7) Local development integration checklist

1. Start Keycloak from compose stack.
2. Import development realm template (`adapters/identity/realm-dev-template.json`).
3. Configure application clients and redirect URIs for local URLs.
4. Validate JWT claims with helper scripts in `scripts/keycloak/`.
5. Confirm role-to-permission mapping behavior in policy tests and runtime adapters.

## 8) Non-goals in this phase

- No production-grade IAM hardening baseline.
- No enterprise federation setup (SAML/LDAP brokering).
- No full SCIM lifecycle automation.
