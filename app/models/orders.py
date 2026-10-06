from pydantic import BaseModel
from typing import Optional


class OrderSummary(BaseModel):
    """Normalized order fields the agent actually needs.

    We deliberately exclude payment method details, billing address lines,
    line-item metadata, and other fields that add noise without value for
    read-only agent queries.
    """

    id: int
    status: str
    currency: str
    total: str
    date_created: str
    customer_email: Optional[str] = None
    customer_id: int = 0
    number: str  # human-readable order number e.g. "#1042"

    @classmethod
    def from_api(cls, raw: dict) -> "OrderSummary":
        billing = raw.get("billing", {})
        return cls(
            id=raw["id"],
            status=raw.get("status", ""),
            currency=raw.get("currency", ""),
            total=raw.get("total", ""),
            date_created=raw.get("date_created", ""),
            customer_email=billing.get("email") or None,
            customer_id=raw.get("customer_id", 0),
            number=raw.get("number", str(raw["id"])),
        )
