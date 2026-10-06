"""Offline demo — no real WooCommerce account needed.

This script simulates agent-like interactions using fictional merchant data.
All orders, customers, products, and SKUs are invented for demonstration purposes.

Run with:
    python demo/offline_demo.py
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.models.orders import OrderSummary
from app.models.products import ProductSummary
from app.services.orders import OrderService
from app.services.products import ProductService


# --- Fictional merchant data ---

FICTIONAL_ORDERS = [
    {
        "id": 1042, "number": "1042", "status": "processing",
        "currency": "INR", "total": "2499.00",
        "date_created": "2026-10-05T14:22:00", "customer_id": 7,
        "billing": {"email": "demo.alex@example.test"},
    },
    {
        "id": 1041, "number": "1041", "status": "completed",
        "currency": "INR", "total": "1200.00",
        "date_created": "2026-10-04T09:10:00", "customer_id": 12,
        "billing": {"email": "demo.priya@example.test"},
    },
    {
        "id": 1040, "number": "1040", "status": "on-hold",
        "currency": "INR", "total": "3799.00",
        "date_created": "2026-10-03T18:55:00", "customer_id": 7,
        "billing": {"email": "demo.alex@example.test"},
    },
]

FICTIONAL_PRODUCTS = [
    {
        "id": 201, "name": "Pro Keyboard", "sku": "KB-PRO",
        "price": "1299.00", "regular_price": "1499.00",
        "status": "publish", "stock_status": "instock",
        "stock_quantity": 4, "manage_stock": True,
        "permalink": "https://demo-store.example.test/product/pro-keyboard",
    },
    {
        "id": 202, "name": "Noise Cancelling Headset", "sku": "HEAD-ANC",
        "price": "1200.00", "regular_price": "1200.00",
        "status": "publish", "stock_status": "instock",
        "stock_quantity": 7, "manage_stock": True,
        "permalink": "https://demo-store.example.test/product/headset",
    },
    {
        "id": 203, "name": "USB-C Hub 7-in-1", "sku": "HUB-USBC-7",
        "price": "1599.00", "regular_price": "1599.00",
        "status": "publish", "stock_status": "outofstock",
        "stock_quantity": 0, "manage_stock": True,
        "permalink": "https://demo-store.example.test/product/usbc-hub",
    },
    {
        "id": 204, "name": "Ergonomic Mouse", "sku": "MOUSE-ERG",
        "price": "799.00", "regular_price": "799.00",
        "status": "publish", "stock_status": "instock",
        "stock_quantity": 23, "manage_stock": True,
        "permalink": "https://demo-store.example.test/product/mouse",
    },
]


def _make_order_service() -> OrderService:
    client = MagicMock()

    async def fake_list_orders(params):
        status_filter = params.get("status")
        search = params.get("search")
        results = FICTIONAL_ORDERS
        if status_filter and status_filter != "any":
            results = [o for o in results if o["status"] == status_filter]
        if search:
            results = [o for o in results if search in o["billing"]["email"]]
        per_page = params.get("per_page", 20)
        return results[:per_page]

    async def fake_get_order(order_id):
        for o in FICTIONAL_ORDERS:
            if o["id"] == order_id:
                return o
        raise KeyError(f"Order {order_id} not found")

    client.list_orders = fake_list_orders
    client.get_order = fake_get_order
    return OrderService(client)


def _make_product_service() -> ProductService:
    client = MagicMock()

    async def fake_list_products(params):
        results = FICTIONAL_PRODUCTS
        sku = params.get("sku")
        search = params.get("search", "").lower()
        stock_status = params.get("stock_status")
        if sku:
            results = [p for p in results if p["sku"] == sku]
        if search:
            results = [p for p in results if search in p["name"].lower()]
        if stock_status:
            results = [p for p in results if p["stock_status"] == stock_status]
        per_page = params.get("per_page", 20)
        return results[:per_page]

    async def fake_get_product(product_id):
        for p in FICTIONAL_PRODUCTS:
            if p["id"] == product_id:
                return p
        raise KeyError(f"Product {product_id} not found")

    client.list_products = fake_list_products
    client.get_product = fake_get_product
    return ProductService(client)


def print_orders(orders: list[OrderSummary]) -> None:
    for o in orders:
        print(f"  Order #{o.number} | {o.status:12} | {o.currency} {o.total:>10} | {o.date_created[:10]} | {o.customer_email}")


def print_inventory(products: list[ProductSummary]) -> None:
    for p in products:
        stock = f"{p.stock_quantity} units" if p.stock_quantity is not None else "unmanaged"
        print(f"  [{p.sku:12}] {p.name:30} | {p.stock_status:12} | {stock}")


async def run_demo():
    print("=" * 65)
    print("  WooCommerce Agent Connector — Offline Demo")
    print("  (All data is fictional — no real store connected)")
    print("=" * 65)

    order_svc = _make_order_service()
    product_svc = _make_product_service()

    # Scenario 1: Agent finds latest processing order for a customer
    print("\n[Agent query] Find the latest processing order for demo.alex@example.test")
    print("[Tool called] search_orders(status='processing', customer_email='demo.alex@example.test')")
    results = await order_svc.search_orders(status="processing", customer_email="demo.alex@example.test")
    print_orders(results)

    # Scenario 2: Agent looks up a specific order by ID
    print("\n[Agent query] Get details for order #1042")
    print("[Tool called] get_order(order_id=1042)")
    order = await order_svc.get_order(1042)
    print(f"  Order #{order.number} | status={order.status} | {order.currency} {order.total} | customer={order.customer_email}")

    # Scenario 3: Agent checks products with low stock
    print("\n[Agent query] Which products have fewer than 10 units in stock?")
    print("[Tool called] get_inventory(per_page=20)")
    inventory = await product_svc.get_inventory()
    low_stock = [p for p in inventory if p.stock_quantity is not None and p.stock_quantity < 10]
    print(f"  Found {len(low_stock)} product(s) with fewer than 10 units:")
    print_inventory(low_stock)

    # Scenario 4: Agent searches for a product by SKU
    print("\n[Agent query] Find the product with SKU 'HEAD-ANC'")
    print("[Tool called] search_products(sku='HEAD-ANC')")
    products = await product_svc.search_products(sku="HEAD-ANC")
    print_inventory(products)

    # Scenario 5: Out-of-stock products
    print("\n[Agent query] List all out-of-stock products")
    print("[Tool called] search_products(stock_status='outofstock')")
    oos = await product_svc.search_products(stock_status="outofstock")
    print_inventory(oos)

    print("\n" + "=" * 65)
    print("  Demo complete. Run with a real WooCommerce store by")
    print("  configuring .env — see README for setup instructions.")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(run_demo())
