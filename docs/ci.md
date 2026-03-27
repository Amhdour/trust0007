# CI Workflows

CI workflow file: `.github/workflows/ci.yml`

## Stages
- `lint`
- `unit tests`
- `policy tests`
- `adapter tests`
- `telemetry schema tests`
- `launch-gate smoke test`

## Stage details

### lint
- Performs Python syntax compilation checks with `python -m compileall`.

### unit tests
- Runs core unit suites for retrieval, sandbox, secrets, and tools.

### adapter tests
- Runs adapter-focused suites (`tests/adapter`, `tests/observability`).

### telemetry schema tests
- Runs telemetry model/schema and dashboard artifact tests (`tests/telemetry`).

### policy tests
- Uses OPA to execute:
  - `opa test policies/rego policies/tests -v`
  - `opa test policies/retrieval -v`
- This stage fails on policy regressions.

### launch-gate smoke test
- Runs launch-gate tests under `tests/launch-gate`.
- Includes checks for required evidence artifact presence and explicit no-go behavior when mandatory evidence is missing.

## Design choices
- Readable single workflow with one job per CI stage.
- Minimal dependencies (`pytest`, `setup-opa`) and explicit commands.
- No unnecessary matrix or orchestration complexity for this phase.
