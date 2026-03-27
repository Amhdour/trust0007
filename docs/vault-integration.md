# Vault Integration (Local Development Design)

## Scope
Minimal secrets-access design for local development. Not production hardening.

## Deliverables
- Adapter code: `adapters/secrets/`
- Local Vault placeholders: `compose/vault/`
- Tests: `tests/secrets/`

## Design goals
- Fetch secrets **only when needed**.
- Keep secrets out of source control.
- Support placeholder secret paths for local wiring.
- Be explicit about assumptions and fail-safe behavior.

## Access assumptions
- Vault is reachable at the configured preview address (e.g., `https://orange-space-journey-7vrrp4wqq4r6h7p9-8200.app.github.dev` in this Codespace).
- Caller provides a valid logical secret path and key reference.
- Vault auth/token lifecycle is handled outside this minimal adapter.

## Adapter behavior
`VaultSecretsProvider.fetch_if_needed(request)`:
1. If `needed=false`, do not call Vault (`reason=not_needed`).
2. Validate path/key references.
3. Attempt read from Vault client.
4. If Vault unavailable, return no secret (`reason=vault_unavailable`).
5. If key missing, return no secret (`reason=secret_key_missing`).
6. On success, return secret value (`reason=ok`).

## Failure-safe behavior
- If Vault is unavailable or secret lookup fails, adapter returns `fetched=false`.
- Upstream callers should deny or degrade operations that require the secret.
- No fallback to hardcoded secrets.

## Source-control safety
- Commit only placeholder paths and key names.
- Never commit actual secret values, tokens, or private keys.
- `compose/vault/paths.example.env` intentionally contains placeholders only.
