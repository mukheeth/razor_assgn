"""Low-level HTTP client with retry and rate-limit handling.

Retry policy:
- 429: respect Retry-After header; back off and retry
- 500/502/503/504 and network errors: bounded exponential backoff
- 4xx (except 429): never retried — they indicate a bad request or auth failure

Timeout: explicit connect + read timeouts on every request.
Credentials (consumer_key/secret) are passed as HTTP Basic Auth on every request.
They are never written to logs or included in error messages.
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from app.errors import (
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    UpstreamServiceError,
    ValidationError,
)

logger = logging.getLogger(__name__)

# Status codes where a retry makes sense
_RETRYABLE = {429, 500, 502, 503, 504}


class WooCommerceHTTPClient:
    def __init__(
        self,
        base_url: str,
        consumer_key: str,
        consumer_secret: str,
        connect_timeout: float = 5.0,
        read_timeout: float = 30.0,
        max_retries: int = 3,
        retry_backoff_base: float = 1.0,
    ):
        self._base_url = base_url.rstrip("/") + "/wp-json/wc/v3"
        self._auth = (consumer_key, consumer_secret)
        self._timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout, write=10.0, pool=5.0)
        self._max_retries = max_retries
        self._backoff_base = retry_backoff_base
        # Single shared async client; caller must close via aclose()
        self._client = httpx.AsyncClient(auth=self._auth, timeout=self._timeout)

    async def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET request with retry logic. Returns parsed JSON."""
        url = f"{self._base_url}{path}"
        attempt = 0

        while True:
            try:
                resp = await self._client.get(url, params=params)
            except httpx.TimeoutException as exc:
                if attempt >= self._max_retries:
                    raise UpstreamServiceError("WooCommerce request timed out.") from exc
                await self._backoff(attempt)
                attempt += 1
                continue
            except httpx.RequestError as exc:
                if attempt >= self._max_retries:
                    raise UpstreamServiceError(f"Network error reaching WooCommerce: {exc}") from exc
                await self._backoff(attempt)
                attempt += 1
                continue

            status = resp.status_code
            logger.debug("GET %s params=%s -> %d (attempt %d)", path, _safe_params(params), status, attempt + 1)

            if status == 200:
                return resp.json()

            if status == 401 or status == 403:
                raise AuthenticationError(
                    "WooCommerce authentication failed. Check the configured API credentials."
                )

            if status == 404:
                raise NotFoundError(f"Resource not found: {path}")

            if status == 422:
                detail = _extract_message(resp)
                raise ValidationError(f"WooCommerce rejected the request: {detail}")

            if status == 429:
                retry_after = _parse_retry_after(resp)
                logger.warning("Rate limited by WooCommerce. Retry-After=%ss attempt=%d", retry_after, attempt + 1)
                if attempt >= self._max_retries:
                    raise RateLimitError(
                        f"WooCommerce rate limit exceeded. Retry after {retry_after}s."
                    )
                await asyncio.sleep(retry_after)
                attempt += 1
                continue

            if status in _RETRYABLE:
                if attempt >= self._max_retries:
                    raise UpstreamServiceError(
                        f"WooCommerce returned {status} after {self._max_retries} retries."
                    )
                await self._backoff(attempt)
                attempt += 1
                continue

            # Any other 4xx/5xx
            detail = _extract_message(resp)
            raise UpstreamServiceError(f"WooCommerce error {status}: {detail}")

    async def _backoff(self, attempt: int) -> None:
        delay = self._backoff_base * (2 ** attempt)
        logger.debug("Retrying after %.1fs (attempt %d)", delay, attempt + 1)
        await asyncio.sleep(delay)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.aclose()


def _parse_retry_after(resp: httpx.Response) -> float:
    header = resp.headers.get("Retry-After", "")
    try:
        return float(header)
    except (ValueError, TypeError):
        return 2.0  # safe fallback


def _extract_message(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        return body.get("message", resp.text[:200])
    except Exception:
        return resp.text[:200]


def _safe_params(params: dict | None) -> dict:
    """Strip credentials from params before logging. Auth is handled by httpx
    Basic auth so params shouldn't contain secrets, but be defensive."""
    if not params:
        return {}
    return {k: v for k, v in params.items() if k not in ("consumer_key", "consumer_secret")}
