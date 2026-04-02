# Main Dashboard

This frontend is the dashboard-first homepage for the repository.

- It is served by `backend/api_gateway/server.py`.
- It also serves a separate client-facing explanation layer at `/client-overview`.
- Shared dashboard labels and section metadata live in `contracts/control-plane-dashboard.json`.
- It treats Onyx as a governed runtime module behind the control plane.
- It now foregrounds a plain-language first layer, a compact command summary, a dominant live-vs-demo mode banner, a short reading guide, lighter summary-first reviewer sections, and deeper technical drilldowns.
- The homepage consumes `/api/control-plane/overview` for posture and evidence panels and `/api/control-plane/live-log` for recent activity.
- The client overview page reuses the same overview payload and the reviewer allow/deny artifacts, but presents them as simple visuals for non-technical audiences.
- The hero includes a direct governed live workspace link at `/launch/onyx?path=/app&mode=live&view=embedded`.
- The adjacent access-requirements panel explains that the deployment must already provide a valid Keycloak-backed browser session or bearer token.
- Drill-through links are expected to point at raw repo artifacts exposed by the API gateway under `/raw/...`.
