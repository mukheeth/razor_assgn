"""Tests for the HTTP client: retry logic, auth failure, rate limiting, timeouts."""

import asyncio
import pytest
import httpx

from app.client.http import WooCommerceHTTPClient
from app.errors import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    UpstreamServiceError,
    ValidationError,
)


def _make_client(transport: httpx.MockTransport, **kwargs) -> WooCommerceHTTPClient:
    client = WooCommerceHTTPClient(
        base_url="https://fake-store.example.test",
        consumer_key="ck_fake",
        consumer_secret="cs_fake",
        connect_timeout=1.0,
        read_timeout=2.0,
        **kwargs,
    )
    # Replace the internal httpx client with a mock transport
    client._client = httpx.AsyncClient(
        auth=client._auth,
        timeout=client._timeout,
        transport=transport,
    )
    return client


def _response(status: int, json_body=None, headers=None) -> httpx.Response:
    import json
    content = json.dumps(json_body or {}).encode()
    return httpx.Response(status, content=content, headers=headers or {})


class TestSuccessfulGet:
    @pytest.mark.asyncio
    async def test_returns_json_on_200(self):
        transport = httpx.MockTransport(
            lambda req: _response(200, {"id": 1, "status": "processing"})
        )
        async with _make_client(transport) as client:
            result = await client.get("/orders/1")
        assert result["id"] == 1
        assert result["status"] == "processing"


class TestAuthFailures:
    @pytest.mark.asyncio
    async def test_401_raises_auth_error(self):
        transport = httpx.MockTransport(lambda req: _response(401, {"message": "Unauthorized"}))
        async with _make_client(transport) as client:
            with pytest.raises(AuthenticationError) as exc_info:
                await client.get("/orders/1")
        assert "authentication failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_403_raises_auth_error(self):
        transport = httpx.MockTransport(lambda req: _response(403, {"message": "Forbidden"}))
        async with _make_client(transport) as client:
            with pytest.raises(AuthenticationError):
                await client.get("/orders/1")

    @pytest.mark.asyncio
    async def test_401_is_not_retried(self):
        call_count = 0

        def handler(req):
            nonlocal call_count
            call_count += 1
            return _response(401)

        transport = httpx.MockTransport(handler)
        async with _make_client(transport, max_retries=3) as client:
            with pytest.raises(AuthenticationError):
                await client.get("/orders/1")

        assert call_count == 1  # no retries on 401


class TestNotFound:
    @pytest.mark.asyncio
    async def test_404_raises_not_found(self):
        transport = httpx.MockTransport(lambda req: _response(404, {"message": "Not found"}))
        async with _make_client(transport) as client:
            with pytest.raises(NotFoundError):
                await client.get("/orders/9999")

    @pytest.mark.asyncio
    async def test_404_is_not_retried(self):
        call_count = 0

        def handler(req):
            nonlocal call_count
            call_count += 1
            return _response(404)

        transport = httpx.MockTransport(handler)
        async with _make_client(transport, max_retries=3) as client:
            with pytest.raises(NotFoundError):
                await client.get("/orders/9999")

        assert call_count == 1


class TestRateLimit:
    @pytest.mark.asyncio
    async def test_429_raises_rate_limit_after_max_retries(self, monkeypatch):
        async def noop_sleep(_): pass
        monkeypatch.setattr("app.client.http.asyncio.sleep", noop_sleep)
        call_count = 0

        def handler(req):
            nonlocal call_count
            call_count += 1
            return _response(429, headers={"Retry-After": "1"})

        transport = httpx.MockTransport(handler)
        async with _make_client(transport, max_retries=2) as client:
            with pytest.raises(RateLimitError) as exc_info:
                await client.get("/orders")

        # Initial attempt + max_retries retries = max_retries + 1 calls
        assert call_count == 3
        assert "rate limit" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_429_retry_after_is_respected(self, monkeypatch):
        sleep_durations = []

        async def fake_sleep(seconds):
            sleep_durations.append(seconds)

        monkeypatch.setattr("app.client.http.asyncio.sleep", fake_sleep)

        def handler(req):
            return _response(429, headers={"Retry-After": "5"})

        transport = httpx.MockTransport(handler)
        async with _make_client(transport, max_retries=1) as client:
            with pytest.raises(RateLimitError):
                await client.get("/orders")

        assert 5.0 in sleep_durations


class TestTransientErrors:
    @pytest.mark.asyncio
    async def test_500_is_retried_and_eventually_fails(self, monkeypatch):
        async def noop_sleep(_): pass
        monkeypatch.setattr("app.client.http.asyncio.sleep", noop_sleep)
        call_count = 0

        def handler(req):
            nonlocal call_count
            call_count += 1
            return _response(500)

        transport = httpx.MockTransport(handler)
        async with _make_client(transport, max_retries=2) as client:
            with pytest.raises(UpstreamServiceError):
                await client.get("/orders")

        assert call_count == 3  # 1 initial + 2 retries

    @pytest.mark.asyncio
    async def test_500_succeeds_on_third_attempt(self, monkeypatch):
        async def noop_sleep(_): pass
        monkeypatch.setattr("app.client.http.asyncio.sleep", noop_sleep)
        call_count = 0

        def handler(req):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return _response(500)
            return _response(200, {"id": 1})

        transport = httpx.MockTransport(handler)
        async with _make_client(transport, max_retries=3) as client:
            result = await client.get("/orders/1")

        assert result["id"] == 1
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self, monkeypatch):
        sleep_durations = []

        async def fake_sleep(seconds):
            sleep_durations.append(seconds)

        monkeypatch.setattr("app.client.http.asyncio.sleep", fake_sleep)

        transport = httpx.MockTransport(lambda req: _response(503))
        async with _make_client(transport, max_retries=3, retry_backoff_base=1.0) as client:
            with pytest.raises(UpstreamServiceError):
                await client.get("/orders")

        # delays should be: 1.0, 2.0, 4.0  (base * 2^attempt)
        assert sleep_durations == [1.0, 2.0, 4.0]


class TestTimeout:
    @pytest.mark.asyncio
    async def test_timeout_raises_upstream_error(self, monkeypatch):
        async def noop_sleep(_): pass
        monkeypatch.setattr("app.client.http.asyncio.sleep", noop_sleep)

        def handler(req):
            raise httpx.ReadTimeout("timed out", request=req)

        transport = httpx.MockTransport(handler)
        async with _make_client(transport, max_retries=1) as client:
            with pytest.raises(UpstreamServiceError) as exc_info:
                await client.get("/orders")

        assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_retry_limit_stops_on_repeated_timeout(self, monkeypatch):
        async def noop_sleep(_): pass
        monkeypatch.setattr("app.client.http.asyncio.sleep", noop_sleep)
        call_count = 0

        def handler(req):
            nonlocal call_count
            call_count += 1
            raise httpx.ReadTimeout("timed out", request=req)

        transport = httpx.MockTransport(handler)
        async with _make_client(transport, max_retries=2) as client:
            with pytest.raises(UpstreamServiceError):
                await client.get("/orders")

        assert call_count == 3  # stops at max_retries
