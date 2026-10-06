"""MCP server for the WooCommerce read-only connector.

This module is intentionally thin. Each tool:
  1. Validates inputs (delegating heavy validation to the service layer)
  2. Calls the appropriate service method
  3. Serialises the result
  4. Maps connector errors to clean agent-facing messages

No business logic or HTTP calls live here.
"""

import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from app.config import get_settings
from app.client.http import WooCommerceHTTPClient
from app.client.woocommerce import WooCommerceClient
from app.errors import WooCommerceConnectorError
from app.services.orders import OrderService
from app.services.products import ProductService

logger = logging.getLogger(__name__)

mcp = FastMCP(
    "woocommerce-connector",
    instructions=(
        "Read-only connector for WooCommerce merchant data. "
        "Use these tools to retrieve orders, products, and inventory. "
        "You cannot create, update, delete, or refund anything."
    ),
)


def _make_services() -> tuple[OrderService, ProductService]:
    cfg = get_settings()
    http = WooCommerceHTTPClient(
        base_url=cfg.wc_store_url,
        consumer_key=cfg.wc_consumer_key,
        consumer_secret=cfg.wc_consumer_secret,
        connect_timeout=cfg.connect_timeout,
        read_timeout=cfg.read_timeout,
        max_retries=cfg.max_retries,
        retry_backoff_base=cfg.retry_backoff_base,
    )
    wc = WooCommerceClient(http)
    return OrderService(wc), ProductService(wc)


def _err(exc: Exception) -> str:
    if isinstance(exc, WooCommerceConnectorError):
        return str(exc)
    logger.exception("Unexpected error in MCP tool")
    return "An unexpected error occurred. Check server logs."


# ---------------------------------------------------------------------------
# Order tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_order(order_id: int) -> dict:
    """Retrieve a single WooCommerce order by its numeric ID.

    Returns order status, total, currency, date, and customer email.
    """
    orders, _ = _make_services()
    try:
        result = await orders.get_order(order_id)
        return result.model_dump()
    except Exception as exc:
        return {"error": _err(exc)}


@mcp.tool()
async def list_orders(page: int = 1, per_page: int = 20) -> dict:
    """List recent WooCommerce orders, sorted by date descending.

    Use page and per_page to paginate. Maximum per_page is 100.
    """
    orders, _ = _make_services()
    try:
        results = await orders.list_orders(page=page, per_page=per_page)
        return {"orders": [r.model_dump() for r in results], "page": page, "per_page": per_page}
    except Exception as exc:
        return {"error": _err(exc)}


@mcp.tool()
async def search_orders(
    status: Optional[str] = None,
    customer_email: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Find WooCommerce orders using status, customer email, or a search term.

    - status: e.g. 'processing', 'completed', 'pending', 'on-hold', 'refunded'
    - customer_email: exact email match
    - search: free-text search (order ID or customer name)
    Filtering is done server-side. Maximum per_page is 100.
    """
    orders, _ = _make_services()
    try:
        results = await orders.search_orders(
            status=status,
            customer_email=customer_email,
            search=search,
            page=page,
            per_page=per_page,
        )
        return {"orders": [r.model_dump() for r in results], "page": page, "per_page": per_page}
    except Exception as exc:
        return {"error": _err(exc)}


# ---------------------------------------------------------------------------
# Product tools
# ---------------------------------------------------------------------------

@mcp.tool()
async def get_product(product_id: int) -> dict:
    """Retrieve a single WooCommerce product by its numeric ID.

    Returns name, SKU, price, stock status, and stock quantity.
    """
    _, products = _make_services()
    try:
        result = await products.get_product(product_id)
        return result.model_dump()
    except Exception as exc:
        return {"error": _err(exc)}


@mcp.tool()
async def list_products(page: int = 1, per_page: int = 20) -> dict:
    """List WooCommerce products with pagination.

    Maximum per_page is 100. Results are sorted by date descending.
    """
    _, products = _make_services()
    try:
        results = await products.list_products(page=page, per_page=per_page)
        return {"products": [r.model_dump() for r in results], "page": page, "per_page": per_page}
    except Exception as exc:
        return {"error": _err(exc)}


@mcp.tool()
async def search_products(
    search: Optional[str] = None,
    sku: Optional[str] = None,
    stock_status: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """Search WooCommerce products by name, SKU, or stock status.

    - search: partial product name match
    - sku: exact SKU match
    - stock_status: 'instock', 'outofstock', or 'onbackorder'
    Server-side filtering — does not load the full catalogue. Maximum per_page is 100.
    """
    _, products = _make_services()
    try:
        results = await products.search_products(
            search=search, sku=sku, stock_status=stock_status, page=page, per_page=per_page
        )
        return {"products": [r.model_dump() for r in results], "page": page, "per_page": per_page}
    except Exception as exc:
        return {"error": _err(exc)}


@mcp.tool()
async def get_inventory(page: int = 1, per_page: int = 20) -> dict:
    """Retrieve stock levels for WooCommerce products.

    Returns product name, SKU, stock_status, and stock_quantity per product.
    Use page/per_page to paginate through the catalogue. Maximum per_page is 100.
    """
    _, products = _make_services()
    try:
        results = await products.get_inventory(page=page, per_page=per_page)
        inventory = [
            {
                "id": p.id,
                "name": p.name,
                "sku": p.sku,
                "stock_status": p.stock_status,
                "stock_quantity": p.stock_quantity,
                "manage_stock": p.manage_stock,
            }
            for p in results
        ]
        return {"inventory": inventory, "page": page, "per_page": per_page}
    except Exception as exc:
        return {"error": _err(exc)}
