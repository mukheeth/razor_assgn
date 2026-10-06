"""Thin WooCommerce API wrapper.

Maps Python method calls to WC REST API endpoints.
No business logic here — just URL construction and parameter passing.
"""

from typing import Any

from app.client.http import WooCommerceHTTPClient


class WooCommerceClient:
    def __init__(self, http: WooCommerceHTTPClient):
        self._http = http

    async def get_order(self, order_id: int) -> dict:
        # GET /orders/{id}  — O(1)
        return await self._http.get(f"/orders/{order_id}")

    async def list_orders(self, params: dict[str, Any]) -> list[dict]:
        # GET /orders  — O(k) where k = per_page
        return await self._http.get("/orders", params=params)

    async def get_product(self, product_id: int) -> dict:
        # GET /products/{id}  — O(1)
        return await self._http.get(f"/products/{product_id}")

    async def list_products(self, params: dict[str, Any]) -> list[dict]:
        # GET /products  — O(k) where k = per_page
        return await self._http.get("/products", params=params)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.aclose()
