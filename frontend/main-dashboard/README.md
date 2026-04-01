# Main Dashboard

This frontend is the dashboard-first homepage for the repository.

- It is served by `backend/api_gateway/server.py`.
- It also serves a separate client-facing explanation layer at `/client-overview`.
- Shared dashboard labels and section metadata live in `contracts/control-plane-dashboard.json`.
- It treats Onyx as a governed runtime module behind the control plane.
- It now foregrounds a plain-language first layer, a compact command summary, a dominant live-vs-demo mode banner, a short reading guide, lighter summary-first reviewer sections, and deeper technical drilldowns.
- The homepage consumes `/api/control-plane/overview` for posture and evidence panels and `/api/control-plane/live-log` for recent activity.
- The hero also consumes `/api/control-plane/live-session` so the page can show whether the dev-only live-session cookie is active, when it expires, and how to clear it.
- The client overview page reuses the same overview payload and the reviewer allow/deny artifacts, but presents them as simple visuals for non-technical audiences.
- The hero now includes a dev-only live-session bootstrap link that mints a local `kc_access_token` cookie and then redirects into `/launch/onyx?path=/app&mode=live&view=embedded`.
- The same hero surface also exposes `/auth/live-session/end?next=/` so operators can clear that cookie without leaving the dashboard.
- Drill-through links are expected to point at raw repo artifacts exposed by the API gateway under `/raw/...`.
