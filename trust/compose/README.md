# compose

Dashboard-first local stack wiring for the AI Trust & Security control plane.

- `docker-compose.yml` now makes the repo-owned control-plane dashboard the primary homepage.
- Keycloak, Envoy, OPA, Vault, Qdrant, Langfuse, Grafana, and Superset remain supporting modules behind that entry flow, but they are not all equally active in the current runtime path.
- Langfuse, Grafana, and Superset are drill-down destinations rather than the main landing page.
- The current upstream activation model is documented in `docs/upstream-usage-matrix.md`.
