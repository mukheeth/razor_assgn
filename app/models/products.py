from pydantic import BaseModel
from typing import Optional


class ProductSummary(BaseModel):
    """Normalized product/inventory fields for agent use.

    Raw WooCommerce product responses include HTML descriptions, image arrays,
    metadata arrays, and attribute sets. We return only what's useful for
    read-only agent queries.
    """

    id: int
    name: str
    sku: str
    price: str
    regular_price: str
    status: str          # publish / draft / private
    stock_status: str    # instock / outofstock / onbackorder
    stock_quantity: Optional[int] = None
    manage_stock: bool = False
    permalink: str = ""

    @classmethod
    def from_api(cls, raw: dict) -> "ProductSummary":
        return cls(
            id=raw["id"],
            name=raw.get("name", ""),
            sku=raw.get("sku", ""),
            price=raw.get("price", ""),
            regular_price=raw.get("regular_price", ""),
            status=raw.get("status", ""),
            stock_status=raw.get("stock_status", ""),
            stock_quantity=raw.get("stock_quantity"),
            manage_stock=raw.get("manage_stock", False),
            permalink=raw.get("permalink", ""),
        )
