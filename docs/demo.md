# Minimal End-to-End Demo Path

This demo provides a **controlled** development request flow using stubs where upstream integrations are not yet wired.

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
bash scripts/run-demo.sh
```

## Test the demo
```bash
bash scripts/test-demo.sh
```

## Notes
- This is a correctness-of-control-flow demo, not a production stack.
- Identity, retrieval backend, and tool execution use in-repo stubs.
- Launch-gate artifact is generated from explicit demo evidence.
