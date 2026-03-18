from dataclasses import dataclass


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderCommand:
    name: str
    phone: str
    comment: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessOrderCommand:
    order_id: int
    new_status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class DeleteOrderCommand:
    order_id: int
