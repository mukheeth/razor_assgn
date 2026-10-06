"""Tests for OrderService: pagination validation, search params, response transformation."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.orders import OrderService
from app.errors import ValidationError
from app.models.orders import OrderSummary
from tests.conftest import FAKE_ORDER


def _make_service(return_value=None, side_effect=None):
    client = MagicMock()
    if side_effect:
        client.list_orders = AsyncMock(side_effect=side_effect)
        client.get_order = AsyncMock(side_effect=side_effect)
    else:
        client.list_orders = AsyncMock(return_value=return_value or [FAKE_ORDER])
        client.get_order = AsyncMock(return_value=return_value or FAKE_ORDER)
    return OrderService(client)


class TestGetOrder:
    @pytest.mark.asyncio
    async def test_get_order_returns_summary(self):
        service = _make_service()
        result = await service.get_order(1042)
        assert isinstance(result, OrderSummary)
        assert result.id == 1042
        assert result.status == "processing"
        assert result.customer_email == "demo.alex@example.test"
        assert result.total == "2499.00"

    @pytest.mark.asyncio
    async def test_get_order_calls_correct_id(self):
        client = MagicMock()
        client.get_order = AsyncMock(return_value=FAKE_ORDER)
        service = OrderService(client)
        await service.get_order(1042)
        client.get_order.assert_called_once_with(1042)


class TestListOrders:
    @pytest.mark.asyncio
    async def test_list_orders_returns_list_of_summaries(self):
        service = _make_service([FAKE_ORDER])
        results = await service.list_orders()
        assert len(results) == 1
        assert isinstance(results[0], OrderSummary)

    @pytest.mark.asyncio
    async def test_pagination_params_passed_to_client(self):
        client = MagicMock()
        client.list_orders = AsyncMock(return_value=[FAKE_ORDER])
        service = OrderService(client)
        await service.list_orders(page=2, per_page=50)
        call_params = client.list_orders.call_args[0][0]
        assert call_params["page"] == 2
        assert call_params["per_page"] == 50

    @pytest.mark.asyncio
    async def test_invalid_page_raises_validation_error(self):
        service = _make_service()
        with pytest.raises(ValidationError):
            await service.list_orders(page=0)

    @pytest.mark.asyncio
    async def test_per_page_over_max_raises_validation_error(self):
        service = _make_service()
        with pytest.raises(ValidationError):
            await service.list_orders(per_page=101)

    @pytest.mark.asyncio
    async def test_per_page_zero_raises_validation_error(self):
        service = _make_service()
        with pytest.raises(ValidationError):
            await service.list_orders(per_page=0)


class TestSearchOrders:
    @pytest.mark.asyncio
    async def test_status_filter_passed_to_client(self):
        client = MagicMock()
        client.list_orders = AsyncMock(return_value=[FAKE_ORDER])
        service = OrderService(client)
        await service.search_orders(status="processing")
        params = client.list_orders.call_args[0][0]
        assert params["status"] == "processing"

    @pytest.mark.asyncio
    async def test_email_uses_search_param(self):
        client = MagicMock()
        client.list_orders = AsyncMock(return_value=[FAKE_ORDER])
        service = OrderService(client)
        await service.search_orders(customer_email="demo.alex@example.test")
        params = client.list_orders.call_args[0][0]
        assert params["search"] == "demo.alex@example.test"

    @pytest.mark.asyncio
    async def test_search_term_passed_when_no_email(self):
        client = MagicMock()
        client.list_orders = AsyncMock(return_value=[])
        service = OrderService(client)
        await service.search_orders(search="1042")
        params = client.list_orders.call_args[0][0]
        assert params["search"] == "1042"

    @pytest.mark.asyncio
    async def test_invalid_pagination_in_search(self):
        service = _make_service()
        with pytest.raises(ValidationError):
            await service.search_orders(per_page=200)

    @pytest.mark.asyncio
    async def test_search_result_is_normalized(self):
        client = MagicMock()
        client.list_orders = AsyncMock(return_value=[FAKE_ORDER])
        service = OrderService(client)
        results = await service.search_orders(status="processing")
        assert results[0].customer_email == "demo.alex@example.test"


class TestOrderSummaryTransformation:
    def test_from_api_extracts_fields(self):
        summary = OrderSummary.from_api(FAKE_ORDER)
        assert summary.id == 1042
        assert summary.number == "1042"
        assert summary.currency == "INR"
        assert summary.customer_id == 7

    def test_from_api_handles_missing_email(self):
        order = {**FAKE_ORDER, "billing": {}}
        summary = OrderSummary.from_api(order)
        assert summary.customer_email is None
