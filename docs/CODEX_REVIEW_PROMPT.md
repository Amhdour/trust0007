# Codex Prompt — Final Readiness + Onyx Dashboard Validation

Use this prompt with Codex when you want a strict reviewer-grade pass for this repository.

```text
You are a senior AI Trust & Security platform engineer, GitHub Codespaces engineer, DevSecOps reviewer, and technical product strategist.

Repository:
https://github.com/Amhdour/trust0007.git

Mission:
Perform a final reviewer-grade readiness pass so this repository presents as a credible, runnable, portfolio-quality project for an AI Trust & Security Readiness Engineer for RAG and Autonomous Agents.

Non-negotiable scope:
- Do not redesign the repository.
- Improve reliability, consistency, docs clarity, reviewer flow, and CI confidence.
- Preserve fail-closed governance behavior.

Validation requirements:
1) Confirm Codespaces/devcontainer startup works from repo root.
2) Confirm reviewer flow from root with:
   - make help
   - make test
   - make up-dev
3) Confirm Onyx visibility in dashboard:
   - Verify /api/control-plane/dashboard includes Onyx runtime + Onyx Security Readiness block.
   - Verify wiring commands:
     - make verify-remote-onyx
     - make verify-live
     - make preflight-onyx-trust
4) Ensure docs explain exactly where to find Onyx in the dashboard and expected states (APPROVED/CONDITIONAL/BLOCKED/UNKNOWN).
5) Ensure CI checks are staged and predictable (smoke/policy/integration-lite).
6) Keep root README as canonical landing page and avoid duplicated narrative drift.

Execution steps:
- Inspect repo structure and identify gaps.
- Apply minimal, high-signal fixes.
- Run relevant checks/tests locally.
- Commit changes.
- Produce a concise PR summary with what changed, why, and how verified.

Output format:
- Summary bullets.
- Risks / remaining follow-ups.
- Testing section with explicit commands and pass/fail.
```
