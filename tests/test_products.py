"""Tests for ProductService: search params, pagination, inventory transformation."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.products import ProductService
from app.errors import ValidationError
from app.models.products import ProductSummary
from tests.conftest import FAKE_PRODUCT, FAKE_PRODUCT_2


def _make_service(return_value=None):
    client = MagicMock()
    client.list_products = AsyncMock(return_value=return_value or [FAKE_PRODUCT])
    client.get_product = AsyncMock(return_value=return_value or FAKE_PRODUCT)
    return ProductService(client)


class TestGetProduct:
    @pytest.mark.asyncio
    async def test_returns_product_summary(self):
        service = _make_service()
        result = await service.get_product(201)
        assert isinstance(result, ProductSummary)
        assert result.id == 201
        assert result.sku == "KB-PRO"
        assert result.stock_quantity == 4

    @pytest.mark.asyncio
    async def test_calls_client_with_correct_id(self):
        client = MagicMock()
        client.get_product = AsyncMock(return_value=FAKE_PRODUCT)
        service = ProductService(client)
        await service.get_product(201)
        client.get_product.assert_called_once_with(201)


class TestListProducts:
    @pytest.mark.asyncio
    async def test_returns_list_of_summaries(self):
        service = _make_service([FAKE_PRODUCT, FAKE_PRODUCT_2])
        results = await service.list_products()
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_pagination_params_forwarded(self):
        client = MagicMock()
        client.list_products = AsyncMock(return_value=[FAKE_PRODUCT])
        service = ProductService(client)
        await service.list_products(page=3, per_page=10)
        params = client.list_products.call_args[0][0]
        assert params["page"] == 3
        assert params["per_page"] == 10

    @pytest.mark.asyncio
    async def test_invalid_per_page_rejected(self):
        service = _make_service()
        with pytest.raises(ValidationError):
            await service.list_products(per_page=0)

    @pytest.mark.asyncio
    async def test_per_page_over_max_rejected(self):
        service = _make_service()
        with pytest.raises(ValidationError):
            await service.list_products(per_page=101)


class TestSearchProducts:
    @pytest.mark.asyncio
    async def test_sku_param_passed_to_client(self):
        client = MagicMock()
        client.list_products = AsyncMock(return_value=[FAKE_PRODUCT])
        service = ProductService(client)
        await service.search_products(sku="KB-PRO")
        params = client.list_products.call_args[0][0]
        assert params["sku"] == "KB-PRO"

    @pytest.mark.asyncio
    async def test_search_term_passed(self):
        client = MagicMock()
        client.list_products = AsyncMock(return_value=[])
        service = ProductService(client)
        await service.search_products(search="keyboard")
        params = client.list_products.call_args[0][0]
        assert params["search"] == "keyboard"

    @pytest.mark.asyncio
    async def test_stock_status_filter_passed(self):
        client = MagicMock()
        client.list_products = AsyncMock(return_value=[FAKE_PRODUCT])
        service = ProductService(client)
        await service.search_products(stock_status="instock")
        params = client.list_products.call_args[0][0]
        assert params["stock_status"] == "instock"

    @pytest.mark.asyncio
    async def test_invalid_pagination_rejected(self):
        service = _make_service()
        with pytest.raises(ValidationError):
            await service.search_products(per_page=500)


class TestGetInventory:
    @pytest.mark.asyncio
    async def test_returns_inventory_with_stock_fields(self):
        service = _make_service([FAKE_PRODUCT, FAKE_PRODUCT_2])
        results = await service.get_inventory()
        assert all(hasattr(r, "stock_quantity") for r in results)
        assert results[0].stock_quantity == 4
        assert results[1].stock_quantity == 7

    @pytest.mark.asyncio
    async def test_inventory_pagination_validated(self):
        service = _make_service()
        with pytest.raises(ValidationError):
            await service.get_inventory(per_page=200)


class TestProductSummaryTransformation:
    def test_from_api_extracts_fields(self):
        p = ProductSummary.from_api(FAKE_PRODUCT)
        assert p.id == 201
        assert p.name == "Pro Keyboard"
        assert p.sku == "KB-PRO"
        assert p.stock_status == "instock"
        assert p.manage_stock is True

    def test_from_api_handles_missing_stock_quantity(self):
        product = {**FAKE_PRODUCT, "stock_quantity": None}
        p = ProductSummary.from_api(product)
        assert p.stock_quantity is None
