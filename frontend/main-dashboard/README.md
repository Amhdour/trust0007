# Main Dashboard

This frontend is the dashboard-first homepage for the repository.

- It is served by `backend/api_gateway/server.py`.
- Shared dashboard labels and section metadata live in `contracts/control-plane-dashboard.json`.
- It treats Onyx as a governed runtime module behind the control plane.
- It summarizes posture, runtime activity, retrieval, tools/MCP, evals, audit/replay, launch gate, and evidence entry points.
