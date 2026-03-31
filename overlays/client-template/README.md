# {{CLIENT_NAME}} Client Overlay

This directory is a tokenized client overlay scaffold generated for the `{{ENGAGEMENT_TRACK_LABEL}}` track.

It is meant to become `{{OUTPUT_OVERLAY}}`, a client-specific governance layer that can be adapted without forking the repo-owned control plane.

## Client profile

- Client name: `{{CLIENT_NAME}}`
- Client slug: `{{CLIENT_SLUG}}`
- Tenant id: `{{TENANT_ID}}`
- Primary runtime: `{{PRIMARY_RUNTIME}}`
- Dashboard brand: `{{DASHBOARD_BRAND}}`
- Output overlay: `{{OUTPUT_OVERLAY}}`

## What to change first

1. Replace placeholder trust boundaries, approved surfaces, and allowed tools.
2. Replace retrieval, secrets, and readiness defaults with client-specific requirements.
3. Decide whether the client proof path will stay `demo`, require `live`, or center on launch-gate readiness.
4. Decide whether `{{PRIMARY_RUNTIME}}` stays the reference runtime or is replaced by another governed runtime profile.

## Expected deliverables

- Technical review dashboard
- Client overview
- Evidence bundle
- Launch-gate report and readiness artifacts

## Important note

This scaffold is safe to reuse. Existing artifacts from other engagements are not.

The scaffold provides placeholders and governance structure only. It does not reuse prior client evidence or claim live readiness by default.
