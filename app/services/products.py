"""Product and inventory service.

Complexity notes:
  get_product:     O(1) network, O(1) memory
  list_products:   O(k) network + memory, k = per_page
  search_products: O(k) — server-side SKU/name search via WooCommerce `search` param
  get_inventory:   O(k) — fetches only stock fields; same pagination as list_products

We never load the full product catalogue into memory. Pagination is mandatory.
"""

from app.client.woocommerce import WooCommerceClient
from app.errors import ValidationError
from app.models.products import ProductSummary

MAX_PER_PAGE = 100


def _validate_pagination(page: int, per_page: int) -> None:
    if page < 1:
        raise ValidationError("page must be >= 1")
    if per_page < 1 or per_page > MAX_PER_PAGE:
        raise ValidationError(f"per_page must be between 1 and {MAX_PER_PAGE}")


class ProductService:
    def __init__(self, client: WooCommerceClient):
        self._client = client

    async def get_product(self, product_id: int) -> ProductSummary:
        raw = await self._client.get_product(product_id)
        return ProductSummary.from_api(raw)

    async def list_products(self, page: int = 1, per_page: int = 20) -> list[ProductSummary]:
        _validate_pagination(page, per_page)
        params = {"page": page, "per_page": per_page, "orderby": "date", "order": "desc"}
        raw_list = await self._client.list_products(params)
        return [ProductSummary.from_api(r) for r in raw_list]

    async def search_products(
        self,
        search: str | None = None,
        sku: str | None = None,
        stock_status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> list[ProductSummary]:
        """Server-side search. SKU is matched exactly by WooCommerce."""
        _validate_pagination(page, per_page)
        params: dict = {"page": page, "per_page": per_page}
        if search:
            params["search"] = search
        if sku:
            params["sku"] = sku
        if stock_status:
            params["stock_status"] = stock_status
        raw_list = await self._client.list_products(params)
        return [ProductSummary.from_api(r) for r in raw_list]

    async def get_inventory(self, page: int = 1, per_page: int = 20) -> list[ProductSummary]:
        """Return stock info for products. Uses the same product endpoint but
        the caller's intent is specifically to inspect stock levels.

        Returns products with their stock_quantity and stock_status.
        We rely on server-side pagination — never loads the full catalogue.
        """
        _validate_pagination(page, per_page)
        params = {
            "page": page,
            "per_page": per_page,
            "orderby": "title",
            "order": "asc",
        }
        raw_list = await self._client.list_products(params)
        return [ProductSummary.from_api(r) for r in raw_list]
