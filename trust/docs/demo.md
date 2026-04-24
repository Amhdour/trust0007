# Minimal End-to-End Demo Path

This demo provides a **controlled** development request flow using stubs where upstream integrations are not yet wired.
Use it as the fast fallback path when the real Onyx runtime target is unavailable.

## Flow demonstrated
`identity -> request ingress -> policy check -> optional retrieval check -> tool decision -> telemetry emission -> launch-gate artifact generation`

## Files
- `scripts/demo_flow.py` — orchestrates the demo control flow.
- `scripts/run-demo.sh` — runs the demo.
- `scripts/test-demo.sh` — runs demo + validates generated artifacts.
- Artifacts output:
  - `artifacts/demo/events.jsonl`
  - `artifacts/demo/launch-gate.json`

## Run the demo
```bash
make demo
```

## Test the demo
```bash
make test-demo
```

## Validate the real runtime target
```bash
make test-onyx-target
```

## Serve the dashboard shell
```bash
make serve-dashboard
```

## Notes
- Onyx is the primary sample runtime platform for real integration testing in this repo.
- This is a correctness-of-control-flow demo, not a production stack.
- Identity, retrieval backend, and tool execution use in-repo stubs.
- Launch-gate artifact is generated from explicit demo evidence.
- Set `CONTROL_PLANE_DEMO_ARTIFACTS_DIR=/tmp/control-plane-demo` to redirect demo artifacts outside the repo.
