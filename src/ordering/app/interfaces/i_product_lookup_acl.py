from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True, kw_only=True)
class ProductSnapshot:
    """Immutable snapshot of a catalog product at order-placement time."""

    id: int
    title: str
    unit_price: Decimal
    is_active: bool


@runtime_checkable
class IProductLookupACL(Protocol):
    def get(self, product_id: int) -> ProductSnapshot | None: ...
