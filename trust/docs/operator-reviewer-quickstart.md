# Operator / Reviewer Quickstart

Use this sequence when you want to verify that the repo is proving live governed runtime access rather than only architecture intent.

## 1. Start the local platform

```bash
cp compose/.env.example compose/.env
docker compose --env-file compose/.env -f compose/docker-compose.yml up -d
```

Configure the live-mode variables in `compose/.env` before expecting live enforcement to succeed.

## 2. Trigger the governed flow

- Dashboard path:
  - open `/`
  - use the Onyx or Onyx Agent launch entry points
- API path:
  - call `/api/control-plane/governed-flow?mode=live`
  - or `/launch/onyx?path=/app&mode=live`
  - or `/launch/onyx/agent&mode=live`

## 3. Verify live evidence on the dashboard

Check these sections on the homepage:

- `Runtime Portfolio`
- `Onyx RAG Access`
- `Onyx Agent Access`
- `Policy Enforcement`
- `Retrieval Boundaries`
- `Tool and MCP Governance`
- `Audit and Replay`

The page should make `live` vs `demo` mode obvious.

## 4. Verify raw artifacts

Inspect:

- `overlays/myStarterKit/artifacts/governed-flow-summary.json`
- `overlays/myStarterKit/artifacts/identity-evidence.json`
- `overlays/myStarterKit/artifacts/policy-evidence.json`
- `overlays/myStarterKit/artifacts/retrieval-evidence.json`
- `overlays/myStarterKit/artifacts/secret-evidence.json`
- `overlays/myStarterKit/artifacts/trace-correlation.json`
- `overlays/myStarterKit/artifacts/launch-gate-result.json`

## 5. Run proof-oriented tests

```bash
pytest -q tests/integration/test_live_governed_runtime_dependencies.py
pytest -q tests/integration/test_strict_live_onyx_end_to_end.py
pytest -q tests/integration/test_live_end_to_end.py
```

That suite covers:

- no valid Keycloak identity -> deny
- OPA unavailable -> deny
- retrieval backend unavailable or invalid -> deny
- required secret unavailable -> deny
- missing trace/session linkage details are recorded in `trace-correlation.json` with reason codes
- full HTTP-level strict live pass and fail scenarios through the real control-plane server boundary

## 6. Denied-flow evidence expectations

Denied live handoffs should still persist machine-readable pre-runtime evidence when those checks were actually executed:

- `identity-evidence.json` (identity authority result)
- `policy-evidence.json` (OPA reachability + decision metadata)
- `retrieval-evidence.json` (backend used, boundary result, allow/deny reasons)
- `secret-evidence.json` (required/not-required, backend, fetched outcome without secret values)
- `trace-correlation.json` (trace/request linkage plus missing identifiers and audit-stage gaps)

This keeps launch decisions fail-closed while improving diagnostics and dashboard blocker accuracy.

## 7. Review the evidence bundle

Use `../evidence/reviewer_evidence_bundle.json`, `../evidence/reviewer/inspectable-live-runtime/`, and `strict-live-proof-matrix.md` for reviewer-facing summaries of allowed, denied, and downgraded live-mode scenarios.


For a tighter pass/fail checklist and deployment-mode boundaries, see [reviewer-runbook.md](reviewer-runbook.md).
