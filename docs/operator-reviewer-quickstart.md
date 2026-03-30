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
  - use the Onyx launch entry points
- API path:
  - call `/api/control-plane/governed-flow?mode=live`
  - or `/launch/onyx?path=/app&mode=live`

## 3. Verify live evidence on the dashboard

Check these sections on the homepage:

- `Who Is Trying To Use It`
- `Rules Being Applied`
- `What Information It Can Access`
- `Protected Keys And Passwords`
- `Did We Follow The Full Process?`
- `Safety Check Before Use`
- `Connected Parts Of The System`

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
pytest -q tests/integration/test_strict_live_http_end_to_end.py
```

That suite covers:

- no valid Keycloak identity -> deny
- OPA unavailable -> deny
- retrieval backend unavailable or invalid -> deny
- required secret unavailable -> deny
- broken trace correlation -> launch-gate `no_go`
- full HTTP-level strict live pass and fail scenarios through the real control-plane server boundary

## 6. Review the evidence bundle

Use `evidence/reviewer_evidence_bundle.json`, `evidence/reviewer/inspectable-live-runtime/`, and `docs/strict-live-proof-matrix.md` for reviewer-facing summaries of allowed, denied, and downgraded live-mode scenarios.
