"""Tests for MCP tool registration and schema.

We verify that:
  - All expected tools are registered
  - Tool descriptions are present (required for agent discoverability)
  - Input schemas include expected fields
  - Tools return error dicts on connector errors (not raised exceptions)
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.mcp.server import mcp
from app.errors import AuthenticationError, NotFoundError, RateLimitError


# list_tools() is async in the MCP SDK
@pytest.fixture
async def all_tools():
    return await mcp.list_tools()


class TestToolRegistration:
    @pytest.mark.asyncio
    async def test_all_expected_tools_registered(self, all_tools):
        tool_names = {t.name for t in all_tools}
        expected = {
            "get_order",
            "list_orders",
            "search_orders",
            "get_product",
            "list_products",
            "search_products",
            "get_inventory",
        }
        assert expected.issubset(tool_names), f"Missing tools: {expected - tool_names}"

    @pytest.mark.asyncio
    async def test_all_tools_have_descriptions(self, all_tools):
        for tool in all_tools:
            assert tool.description, f"Tool '{tool.name}' has no description"

    @pytest.mark.asyncio
    async def test_search_orders_has_status_and_email_params(self, all_tools):
        tools = {t.name: t for t in all_tools}
        schema = tools["search_orders"].inputSchema
        props = schema.get("properties", {})
        assert "status" in props
        assert "customer_email" in props

    @pytest.mark.asyncio
    async def test_search_products_has_sku_param(self, all_tools):
        tools = {t.name: t for t in all_tools}
        schema = tools["search_products"].inputSchema
        props = schema.get("properties", {})
        assert "sku" in props
        assert "stock_status" in props

    @pytest.mark.asyncio
    async def test_get_inventory_has_pagination_params(self, all_tools):
        tools = {t.name: t for t in all_tools}
        schema = tools["get_inventory"].inputSchema
        props = schema.get("properties", {})
        assert "page" in props
        assert "per_page" in props


class TestToolErrorHandling:
    """Verify that connector errors are returned as {"error": "..."} not raised."""

    @pytest.mark.asyncio
    async def test_get_order_auth_error_returned_as_dict(self):
        with patch("app.mcp.server._make_services") as mock_make:
            orders_svc = AsyncMock()
            orders_svc.get_order.side_effect = AuthenticationError("auth failed")
            mock_make.return_value = (orders_svc, AsyncMock())
            from app.mcp.server import get_order
            result = await get_order(order_id=1)
        assert "error" in result
        assert "auth" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_get_product_not_found_returned_as_dict(self):
        with patch("app.mcp.server._make_services") as mock_make:
            products_svc = AsyncMock()
            products_svc.get_product.side_effect = NotFoundError("not found")
            mock_make.return_value = (AsyncMock(), products_svc)
            from app.mcp.server import get_product
            result = await get_product(product_id=9999)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_list_orders_rate_limit_returned_as_dict(self):
        with patch("app.mcp.server._make_services") as mock_make:
            orders_svc = AsyncMock()
            orders_svc.list_orders.side_effect = RateLimitError("rate limited")
            mock_make.return_value = (orders_svc, AsyncMock())
            from app.mcp.server import list_orders
            result = await list_orders()
        assert "error" in result
        assert "rate limit" in result["error"].lower()
