# Main Dashboard

This frontend is the dashboard-first homepage for the repository.

- It is served by `backend/api_gateway/server.py`.
- Shared dashboard labels and section metadata live in `contracts/control-plane-dashboard.json`.
- It treats Onyx as a governed runtime module behind the control plane.
- It now foregrounds a compact command summary, a dominant live-vs-demo mode banner, reviewer/operator navigation lanes, lighter summary-first reviewer sections, and deeper operator drilldowns.
- The homepage consumes `/api/control-plane/overview` for posture and evidence panels and `/api/control-plane/live-log` for recent activity.
- Drill-through links are expected to point at raw repo artifacts exposed by the API gateway under `/raw/...`.
