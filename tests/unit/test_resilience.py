import time
from datetime import date
from typing import Any

import httpx
import pytest
from proactive_core.events import AgentEvent, EventBus
from proactive_core.integrations.base import (
    CircuitBreaker,
    CircuitOpenError,
    FakeProvider,
    ProviderError,
    ResilientHttpClient,
)
from proactive_core.integrations.openai_router import ModelRole, OpenAIRouter
from proactive_core.integrations.providers import (
    DataForSEOAdapter,
    GmailAdapter,
    GoogleSearchConsoleAdapter,
    JsonApiAdapter,
)
from proactive_core.security import CredentialCipher
from pydantic import BaseModel


@pytest.mark.asyncio
async def test_resilient_http_retries_and_normalizes_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json=[{"ok": True}], request=request)

    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("proactive_core.integrations.base.asyncio.sleep", no_sleep)
    client = ResilientHttpClient("test", base_url="https://provider.test", transport=httpx.MockTransport(handler))
    try:
        assert await client.request("GET", "/items") == {"items": [{"ok": True}]}
        assert attempts == 2
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_resilient_http_rejects_non_retryable_and_network_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def no_sleep(_: float) -> None:
        return None

    monkeypatch.setattr("proactive_core.integrations.base.asyncio.sleep", no_sleep)

    async def rejected(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    client = ResilientHttpClient("test", base_url="https://provider.test", transport=httpx.MockTransport(rejected))
    with pytest.raises(ProviderError, match="rejected") as exc_info:
        await client.request("GET", "/private")
    assert not exc_info.value.retryable
    await client.close()

    async def disconnected(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = ResilientHttpClient("test", base_url="https://provider.test", transport=httpx.MockTransport(disconnected))
    with pytest.raises(ProviderError, match="offline") as network_error:
        await client.request("GET", "/health", max_attempts=1)
    assert network_error.value.code == "network_error"
    await client.close()


def test_circuit_recovery_and_cipher_tamper_detection() -> None:
    breaker = CircuitBreaker("test", threshold=1, recovery_seconds=1)
    breaker.failure()
    with pytest.raises(CircuitOpenError):
        breaker.before_request()
    breaker.opened_at = time.monotonic() - 2
    breaker.before_request()
    assert breaker.failures == 0
    breaker.success()

    cipher = CredentialCipher("unit-test-root-secret")
    ciphertext = cipher.encrypt("provider-secret")
    assert cipher.decrypt(ciphertext) == "provider-secret"
    with pytest.raises(ValueError, match="authentication"):
        cipher.decrypt(ciphertext[:-2] + "xx")


@pytest.mark.asyncio
async def test_provider_adapters_apply_payloads_and_approval_gates(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, dict[str, Any]]] = []

    async def request(method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        calls.append((method, path, kwargs))
        return {"ok": True}

    dataforseo = DataForSEOAdapter("login", "password")
    monkeypatch.setattr(dataforseo.http, "request", request)
    await dataforseo.health()
    await dataforseo.serp("enterprise seo", engine="bing", device="mobile")
    await dataforseo.keyword_data(["a", "b"])
    await dataforseo.backlinks("example.com", 25)
    await dataforseo.http.close()
    assert calls[1][1] == "/serp/bing/organic/live/advanced"

    gsc = GoogleSearchConsoleAdapter("token")
    monkeypatch.setattr(gsc.http, "request", request)
    await gsc.health()
    await gsc.analytics("https://example.com/", date(2026, 1, 1), date(2026, 1, 31), ["query"])
    await gsc.http.close()
    assert "https%3A%2F%2Fexample.com%2F" in calls[-1][1]

    gmail = GmailAdapter("token")
    monkeypatch.setattr(gmail.http, "request", request)
    await gmail.health()
    await gmail.create_draft("raw", "thread-1")
    assert await gmail.send_draft("draft-1", approved=True) == {
        "status": "approval_required",
        "draft_id": "draft-1",
    }
    gmail.live_actions_enabled = True
    assert await gmail.send_draft("draft-1", approved=True) == {"ok": True}
    await gmail.http.close()

    generic = JsonApiAdapter("cms", "https://cms.test", health_path="/health")
    monkeypatch.setattr(generic.http, "request", request)
    await generic.health()
    await generic.read("/items", limit=2)
    assert (await generic.write("/items", {"name": "draft"}, approved=True))["status"] == "approval_required"
    generic.live_actions_enabled = True
    assert await generic.write("/items", {"name": "live"}, approved=True) == {"ok": True}
    await generic.http.close()


@pytest.mark.asyncio
async def test_fake_provider_health_list_fixture_and_event_bus() -> None:
    fake = FakeProvider("exa", {"search": ["one", "two"]})
    assert (await fake.health())["status"] == "fake"
    assert await fake.execute("search", {}) == {"items": ["one", "two"]}

    class RedisFake:
        async def xadd(self, stream: str, values: dict[Any, Any], **kwargs: Any) -> bytes:
            assert stream == "events"
            assert "event" in values
            assert kwargs["approximate"] is True
            return b"1-0"

    event = AgentEvent(
        source="sentinel",
        org_id="00000000-0000-0000-0000-000000000001",
        trace_id="trace-event",
        type="crawl.completed",
    )
    bus = EventBus(RedisFake(), stream="events")  # type: ignore[arg-type]
    assert await bus.publish(event) == "1-0"


class StructuredAnswer(BaseModel):
    value: str


@pytest.mark.asyncio
async def test_openai_router_uses_structured_responses() -> None:
    class Parsed:
        output_parsed = StructuredAnswer(value="typed")

    class Responses:
        async def parse(self, **kwargs: Any) -> Parsed:
            assert kwargs["model"] == "gpt-5.6-luna"
            assert kwargs["text_format"] is StructuredAnswer
            return Parsed()

    class Client:
        responses = Responses()

    router = object.__new__(type("AgentRouter", (), {}))
    router.client = Client()  # type: ignore[assignment]
    result = await router.generate(
        role=ModelRole.EXTRACTION,
        developer_prompt="Extract one field.",
        user_input="value typed",
        output_type=StructuredAnswer,
    )
    assert result.value == "typed"
