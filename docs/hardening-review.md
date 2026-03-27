# Security & Architecture Hardening Review

_Date: 2026-03-25_

## Executive summary
This repository is a strong scaffold for control-plane oriented AI trust/security development, but several development defaults and coupling assumptions needed tightening.

Highest-priority fixes implemented in this change:
1. **Telemetry payload redaction** for common secret-like keys (`token`, `password`, `secret`, `api_key`, `authorization`).
2. **Safer local compose defaults** by removing weak secret fallbacks and binding exposed ports to localhost.

## Audit findings by area

### 1) Trust boundaries
- **Finding**: Boundaries are documented well, but local compose exposed service ports on all interfaces by default.
- **Risk**: Accidental external access on shared networks.
- **Fix applied**: Bound service ports to `127.0.0.1` in compose.

### 2) Policy bypass risks
- **Finding**: Policy paths are present, but adapter orchestration remains stub-driven and can be bypassed if consumers skip adapters.
- **Risk**: Inconsistent enforcement across future runtime integrations.
- **Recommendation**: enforce adapter invocation as mandatory integration contracts in runtime wrappers.

### 3) Secret exposure risks
- **Finding**: Telemetry payloads could include sensitive fields if callers emit raw request context.
- **Risk**: Secret/token leakage in logs and downstream observability systems.
- **Fix applied**: Event model now redacts sensitive keys recursively.

### 4) Weak defaults
- **Finding**: Compose used weak fallback values (`change-me`, `replace-me`, static dev token fallback).
- **Risk**: Unsafe defaults copied into long-lived environments.
- **Fix applied**: Removed fallback secret defaults from compose env interpolation.

### 5) Missing deny paths
- **Finding**: Most adapters include deny paths; demo flow intentionally exercises happy path.
- **Risk**: Consumers may not validate deny behavior during integration.
- **Recommendation**: add demo deny-mode scenario script.

### 6) Missing audit paths
- **Finding**: Tool/sandbox/telemetry have audit paths; secrets adapter currently has no explicit audit sink.
- **Risk**: Secret access failures may be under-observed.
- **Recommendation**: add optional audit emitter to `VaultSecretsProvider` in next phase.

### 7) Missing tests
- **Finding**: Good test coverage for adapters and telemetry; compose hardening behavior currently not unit-tested.
- **Recommendation**: add static config lint checks in CI for compose security assertions.

### 8) Over-coupling to upstream repos
- **Finding**: Current code remains additive and avoids upstream imports.
- **Status**: acceptable.

### 9) Dangerous assumptions in local compose config
- **Finding**: Services assume local single-user dev host and no network segmentation.
- **Status**: acceptable for dev with localhost binding, not production.

## Ranked remediation list

### P0 (implemented)
1. **Redact sensitive telemetry fields by default** in event creation path.
2. **Remove weak secret fallbacks and localhost-bind ports** in compose.

### P1 (next)
3. Add secret-access audit events to secrets provider (success/fail/no-need).
4. Add CI checks for compose security assertions (no wildcard binds, no secret fallbacks).
5. Add deny-path demo scenario and verify launch-gate no-go from demo evidence.

### P2 (later)
6. Enforce adapter contracts at runtime integration points via shared SDK wrappers.
7. Add policy coverage checks mapping each control point to explicit tests.
8. Add structured threat-model traceability from docs to tests.
