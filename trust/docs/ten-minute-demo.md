# 10-Minute Demo Script (ALLOW + DENY)

## Goal
Show that the control plane enforces governed launch behavior, not just UI rendering.

## 1) Start stack (2 min)
```bash
make up-dev
```
Open dashboard: `http://127.0.0.1:3000`

## 2) Show runtime visibility (1 min)
- Open **Onyx RAG Access**
- Confirm **Onyx Security Readiness** is populated.

## 3) Show an ALLOW path (3 min)
- Hit governed Onyx lane in allowed conditions.
- Confirm runtime proof artifacts update:
  - `overlays/myStarterKit/artifacts/onyx-runtime-proof.json`
  - `overlays/myStarterKit/artifacts/launch-gate-result.json`

## 4) Show a DENY path (3 min)
- Trigger a known deny condition (e.g., invalid token / unapproved MCP server in agent lane).
- Confirm denial reason codes are present in artifacts and dashboard evidence summaries.

## 5) Export reviewer evidence (1 min)
```bash
make proof-pack
```
Share `artifacts/proof-pack/manifest.json` and bundled files.
