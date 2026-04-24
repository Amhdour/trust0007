# Vault Local Development Notes

This folder documents local-development Vault conventions for the umbrella stack.

- Use placeholder secret paths only in committed config/docs.
- Do not commit real tokens or secret values.

Suggested placeholder paths:
- `secret/data/dev/tenant-a/runtime`
- `secret/data/dev/tenant-b/runtime`

Failure-safe expectation:
- If Vault is unavailable, callers should fail closed for operations requiring secrets.
