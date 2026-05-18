from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderItem:
    """
    Entity: snapshot of a product at the time of order placement.
    Identity is product_id within an order; unit_price/title are frozen.
    """

    product_id: int
    title_snapshot: str
    unit_price: Decimal
    quantity: int
