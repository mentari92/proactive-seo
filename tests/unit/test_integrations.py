import pytest
from proactive_core.integrations.base import CircuitBreaker, CircuitOpenError, FakeProvider
from proactive_core.integrations.providers import PROVIDERS


@pytest.mark.asyncio
async def test_fake_provider_never_reaches_network() -> None:
    provider = FakeProvider("gmail", {"draft": {"id": "draft-1"}})
    result = await provider.execute("draft", {"to": "test@example.com"})
    assert result == {"id": "draft-1"}
    assert len(provider.calls) == 1


def test_provider_catalog_and_circuit_breaker() -> None:
    assert len(PROVIDERS) == 13
    breaker = CircuitBreaker("test", threshold=2)
    breaker.failure()
    breaker.failure()
    with pytest.raises(CircuitOpenError):
        breaker.before_request()
