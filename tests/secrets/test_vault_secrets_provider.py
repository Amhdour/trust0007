from adapters.secrets.interfaces import VaultClient
from adapters.secrets.provider import VaultSecretsProvider
from adapters.secrets.schemas import SecretFetchRequest


class StubVaultClient(VaultClient):
    def __init__(self, data=None, should_fail=False):
        self.data = data or {}
        self.should_fail = should_fail
        self.calls = 0

    def read_secret(self, path: str):
        self.calls += 1
        if self.should_fail:
            raise RuntimeError("vault down")
        return self.data.get(path, {})


def mkreq(**kwargs):
    base = {
        "request_id": "r1",
        "tenant_id": "tenant-a",
        "needed": True,
        "secret_path": "secret/data/dev/tenant-a/runtime",
        "secret_key": "api_token",
    }
    base.update(kwargs)
    return SecretFetchRequest(**base)


def test_not_needed_does_not_call_vault() -> None:
    client = StubVaultClient()
    provider = VaultSecretsProvider(client)

    result = provider.fetch_if_needed(mkreq(needed=False))

    assert result.fetched is False
    assert result.reason == "not_needed"
    assert client.calls == 0


def test_fetch_success() -> None:
    client = StubVaultClient(
        data={"secret/data/dev/tenant-a/runtime": {"api_token": "token-value"}}
    )
    provider = VaultSecretsProvider(client)

    result = provider.fetch_if_needed(mkreq())

    assert result.fetched is True
    assert result.value == "token-value"
    assert result.reason == "ok"


def test_vault_unavailable_fails_safe() -> None:
    client = StubVaultClient(should_fail=True)
    provider = VaultSecretsProvider(client)

    result = provider.fetch_if_needed(mkreq())

    assert result.fetched is False
    assert result.value is None
    assert result.reason == "vault_unavailable"


def test_missing_key_returns_no_secret() -> None:
    client = StubVaultClient(data={"secret/data/dev/tenant-a/runtime": {"other": "x"}})
    provider = VaultSecretsProvider(client)

    result = provider.fetch_if_needed(mkreq(secret_key="api_token"))

    assert result.fetched is False
    assert result.reason == "secret_key_missing"
