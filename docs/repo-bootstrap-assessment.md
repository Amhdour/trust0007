# AI Trust & Security Stack — Repository Bootstrap Assessment

_Date: 2026-03-25_

## 1) Repository map (current state)

```text
.
├── .gitmodules
├── overlays/
│   └── myStarterKit/              (git submodule; not initialized)
└── upstream/                      (git submodule placeholders; not initialized)
    ├── envoy/
    ├── grafana/
    ├── gvisor/
    ├── keycloak/
    ├── keycloak-quickstarts/
    ├── langfuse/
    ├── langfuse-python/
    ├── onyx/
    ├── opa/
    ├── opa-envoy-plugin/
    ├── qdrant/
    ├── superset/
    └── vault/
```

Additional top-level folders now provisioned for additive implementation overlays:

- `.devcontainer/`
- `compose/`
- `adapters/`
- `policies/`
- `telemetry/`
- `launch-gate/`
- `docs/`
- `scripts/`

## 2) Architecture summary (target umbrella design)

### Principles
- Treat `upstream/*` as third-party source and immutable by default.
- Integrate via:
  - docker compose wiring (`compose/`)
  - sidecar/adapter services (`adapters/`)
  - policy packs (`policies/`)
  - telemetry pipelines and dashboards (`telemetry/`)
  - startup and readiness enforcement (`launch-gate/`)
  - docs and operational scripts (`docs/`, `scripts/`)

### Proposed control-plane and data-plane flow
1. **Identity and authn**: Keycloak (OIDC/SAML) as identity provider.
2. **Secret management**: Vault for machine and service secrets.
3. **Policy decision**: OPA (+ optional Envoy external authz) for trust/security controls.
4. **LLM app and retrieval**: Onyx + Qdrant.
5. **Observability & tracing**: Langfuse + Grafana.
6. **Analytics/admin**: Superset for trust metrics/reporting.
7. **Runtime hardening**: gVisor profile overlays where feasible.
8. **Guarded startup**: launch-gate checks block stack startup on policy/security failures.

### Repository boundaries
- `upstream/*`: vendored/third-party, no local behavior assumptions.
- `overlays/*`: environment-specific values, manifests, and patches.
- `compose/*`: canonical local orchestration entrypoint for Codespaces.

## 3) Phased implementation plan

### Phase 0 — Baseline inventory (completed)
- Inspect root, `.devcontainer/`, `compose/`, `upstream/`, `overlays/`, `docs/`.
- Record submodule state and missing bootstrap assets.
- Validation:
  - `git submodule status --recursive`
  - `find . -maxdepth 2 -type d`

### Phase 1 — Codespaces bootstrap skeleton
- Create `.devcontainer/devcontainer.json` and minimal bootstrap script.
- Add `compose/docker-compose.codespaces.yml` with placeholder service topology.
- Add `scripts/validate-phase1.sh` for YAML lint + compose config resolution.
- Add docs for bootstrap and expected environment variables.

### Phase 2 — Security and policy integration
- Add `policies/opa/` baseline rego bundles.
- Add `adapters/envoy-opa/` glue config.
- Add `launch-gate/` checks for required secrets, policy bundle load, and identity readiness.
- Validation: policy unit tests and launch-gate dry-run.

### Phase 3 — Telemetry and trust reporting
- Add Langfuse/Grafana wiring and telemetry export adapters under `telemetry/`.
- Add trust KPI dashboards and alerting config overlays.
- Validation: smoke checks for metrics/traces ingestion.

### Phase 4 — Hardening and operationalization
- Add runtime hardening defaults (gVisor-compatible settings) in overlays.
- Add CI checks for compose, policies, and docs drift.
- Document incident response and rollback runbooks.
- Validation: end-to-end startup + policy enforcement scenario tests.

## 4) Exact files to create first

1. `.devcontainer/devcontainer.json`
2. `.devcontainer/postCreate.sh`
3. `compose/docker-compose.codespaces.yml`
4. `compose/.env.example`
5. `overlays/codespaces/README.md`
6. `adapters/README.md`
7. `policies/README.md`
8. `telemetry/README.md`
9. `launch-gate/README.md`
10. `scripts/validate-phase1.sh`
11. `docs/codespaces-bootstrap.md`
12. `docs/architecture/stack-overview.md`

These files establish a non-destructive integration layer without touching `upstream/*`.
