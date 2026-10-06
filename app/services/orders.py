"""Order service — business logic between the MCP layer and WooCommerce client.

Filtering is pushed to the API wherever WooCommerce supports it (status,
customer email, free-text search). We never fetch an unbounded list and
filter in Python.

Complexity notes:
  get_order:     O(1) network, O(1) memory
  list_orders:   O(k) network + memory, k = per_page
  search_orders: O(k) network + memory — filtering is server-side
"""

from app.client.woocommerce import WooCommerceClient
from app.errors import ValidationError
from app.models.orders import OrderSummary

MAX_PER_PAGE = 100


def _validate_pagination(page: int, per_page: int) -> None:
    if page < 1:
        raise ValidationError("page must be >= 1")
    if per_page < 1 or per_page > MAX_PER_PAGE:
        raise ValidationError(f"per_page must be between 1 and {MAX_PER_PAGE}")


class OrderService:
    def __init__(self, client: WooCommerceClient):
        self._client = client

    async def get_order(self, order_id: int) -> OrderSummary:
        raw = await self._client.get_order(order_id)
        return OrderSummary.from_api(raw)

    async def list_orders(self, page: int = 1, per_page: int = 20) -> list[OrderSummary]:
        _validate_pagination(page, per_page)
        params = {"page": page, "per_page": per_page, "orderby": "date", "order": "desc"}
        raw_list = await self._client.list_orders(params)
        return [OrderSummary.from_api(r) for r in raw_list]

    async def search_orders(
        self,
        status: str | None = None,
        customer_email: str | None = None,
        search: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[OrderSummary]:
        """Search uses WooCommerce server-side filters — no client-side filtering."""
        _validate_pagination(page, per_page)
        params: dict = {"page": page, "per_page": per_page, "orderby": "date", "order": "desc"}
        if status:
            params["status"] = status
        if customer_email:
            # WooCommerce filters by exact customer email match
            params["search"] = customer_email
        elif search:
            params["search"] = search
        raw_list = await self._client.list_orders(params)
        return [OrderSummary.from_api(r) for r in raw_list]
