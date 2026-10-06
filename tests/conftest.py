"""Shared fixtures and fake data for tests.

All credentials here are clearly fake. No real keys are included.
"""

import pytest
from app.config import Settings

# Minimal fake settings — never use real credentials in tests
FAKE_SETTINGS = Settings(
    wc_store_url="https://fake-store.example.test",
    wc_consumer_key="ck_test_fake",
    wc_consumer_secret="cs_test_fake",
)

# Realistic-looking but entirely fictional order payload
FAKE_ORDER = {
    "id": 1042,
    "number": "1042",
    "status": "processing",
    "currency": "INR",
    "total": "2499.00",
    "date_created": "2026-10-01T10:30:00",
    "customer_id": 7,
    "billing": {"email": "demo.alex@example.test", "first_name": "Alex"},
}

# Fictional product payload
FAKE_PRODUCT = {
    "id": 201,
    "name": "Pro Keyboard",
    "sku": "KB-PRO",
    "price": "1299.00",
    "regular_price": "1499.00",
    "status": "publish",
    "stock_status": "instock",
    "stock_quantity": 4,
    "manage_stock": True,
    "permalink": "https://fake-store.example.test/product/pro-keyboard",
}

FAKE_PRODUCT_2 = {
    "id": 202,
    "name": "Noise Cancelling Headset",
    "sku": "HEAD-ANC",
    "price": "1200.00",
    "regular_price": "1200.00",
    "status": "publish",
    "stock_status": "instock",
    "stock_quantity": 7,
    "manage_stock": True,
    "permalink": "https://fake-store.example.test/product/noise-cancelling-headset",
}
