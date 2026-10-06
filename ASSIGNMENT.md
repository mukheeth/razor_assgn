# Razorpay Forward-Deployed Engineer — Agent Studio Assignment

**Option 3: Private connector for a merchant tool**

---

## Problem

Merchants using Agent Studio need to give their AI agents read access to WooCommerce store data — orders, products, and stock levels — without exposing any mutation capabilities. The connector should work as a standard MCP server so it plugs into any MCP-compatible agent runtime.

## Why WooCommerce

WooCommerce powers roughly 40% of online stores globally. Many Razorpay merchants run WooCommerce for their storefront and need payment + order visibility in one place. It has a well-documented REST API v3, supports API key auth, and has realistic pagination and rate-limit behaviour to design around.

## What the connector does

Exposes seven read-only MCP tools across three domains:

- **Orders**: `get_order`, `list_orders`, `search_orders`
- **Products**: `get_product`, `list_products`, `search_products`
- **Inventory**: `get_inventory`

Each tool returns a normalised Pydantic model rather than the raw WooCommerce response. A raw order response is ~4KB including line items, metadata, billing/shipping addresses, and payment tokens. The `OrderSummary` model returns only the fields an agent needs for read queries: id, status, currency, total, date, and customer email.

## Authentication approach

WooCommerce REST API v3 supports HTTP Basic Auth with a consumer key and secret. The httpx client is configured with `auth=(consumer_key, consumer_secret)` so credentials go into the `Authorization` header on every request. They never appear in query params, log lines, or error messages.

Credentials are loaded exclusively via `pydantic-settings` from environment variables. There is no fallback value in code. If the variables are missing, the server fails at startup with a clear config error.

The API key should be generated with **Read** permission only. That's all this connector ever needs, and it limits blast radius if the key leaks.

## Tool design

The MCP layer (`app/mcp/server.py`) is intentionally thin — it validates inputs, calls a service method, and serialises the result. Business logic lives in `app/services/`, HTTP mechanics in `app/client/`.

Tool descriptions are written from the agent's perspective:

```
search_orders: "Find WooCommerce orders using status, customer email, or a search term."
```

All filtering is pushed to the WooCommerce API (status, SKU, stock_status, search param). The connector never fetches a full catalogue and filters in Python.

Pagination is mandatory with a hard cap of `per_page=100`. This matches WooCommerce's own API limit and prevents an agent from accidentally loading thousands of records into context.

## Rate-limit handling

The HTTP client handles retries in one place (`app/client/http.py`), not scattered across tools:

- **429**: reads `Retry-After` header, sleeps that duration, retries up to `MAX_RETRIES`
- **5xx / network errors**: exponential backoff (`base * 2^attempt`), bounded by `MAX_RETRIES`
- **4xx (except 429)**: immediate failure — bad requests and auth failures should not be retried

Default `MAX_RETRIES=3` with `retry_backoff_base=1.0`, giving delays of 1s, 2s, 4s.

Explicit timeouts (connect=5s, read=30s) on every request. Without them, a slow or unresponsive store would block an agent indefinitely.

## Security and least privilege

The connector is read-only by design, not just by convention. There are no tools for create, update, delete, refund, or payment operations. An agent using this connector literally cannot mutate merchant state — the tools don't exist.

This matters because:
1. AI agents can be prompted into unintended actions. Removing mutation capabilities eliminates a whole class of risk.
2. WooCommerce API keys can be scoped to Read. There's no reason to grant Write.
3. If the connector is ever compromised, the attacker can only read data — not process refunds or modify orders.

## Testing approach

49 tests, all mocked — no real WooCommerce account needed.

Key test decisions:
- **Retry tests** verify call count and sleep durations directly, not just that errors are raised
- **Auth/404 tests** verify the retry loop is NOT entered
- **Pagination tests** verify invalid inputs are rejected before the HTTP call
- **MCP tests** verify tool registration, schema shape, and that connector errors become `{"error": "..."}` dicts rather than raised exceptions

Tests live in `tests/` and run with `pytest tests/ -v`.

## Limitations

Honest limitations of this implementation:

1. **No connection reuse** — `_make_services()` creates a new `httpx.AsyncClient` per tool call. In production this should be a shared lifespan client.
2. **No caching** — identical queries hit the API every time. A short TTL cache on product lookups would reduce load.
3. **Email search is fuzzy** — WooCommerce's `search` param does broad text matching. A customer search for `alex@example.com` may return orders from `alexb@example.com` too. Exact email lookup requires a WooCommerce filter plugin or post-processing.
4. **No product variation support** — WooCommerce variable products have child variants with their own SKUs. This connector only queries top-level products.
5. **Not tested against live API** — the implementation follows WooCommerce REST API v3 documentation. It hasn't been validated against a production store with unusual configurations (custom plugins, modified endpoints, etc.).

## Long-term production improvements

In rough priority order:

1. **Shared async client with lifespan management** — one `httpx.AsyncClient` for the process lifetime, closed on shutdown
2. **Startup health check** — call `GET /` on boot to validate credentials and surface config errors early
3. **Request ID propagation** — generate a UUID per tool call, include it in logs and error messages for tracing
4. **Short-lived cache** — 30s TTL on `get_product` and `get_order` to handle repeated agent lookups
5. **Structured logging** — JSON logs with endpoint, status, elapsed time, retry count
6. **OAuth 1.0a support** — some WooCommerce configurations require signed requests rather than Basic Auth
7. **Metric instrumentation** — latency per endpoint, retry rate, error rate by status code
8. **Configurable response field selection** — let callers request only the fields they need, reducing payload size further
