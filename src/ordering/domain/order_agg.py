from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .delivery_vo import DeliveryInfo
from .order_item_ent import OrderItem
from .order_status import OrderStatus
from .errors import (
    EmptyOrderError,
    IllegalOrderTransitionError,
    InvalidOrderTransitionError,
    OrderAlreadyTerminalError,
    OrderRequiresCustomerError,
)

_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.CONFIRMED, OrderStatus.CANCELED, OrderStatus.ARCHIVED},
    OrderStatus.CONFIRMED: {OrderStatus.COMPLETED, OrderStatus.CANCELED, OrderStatus.ARCHIVED},
    OrderStatus.COMPLETED: {OrderStatus.ARCHIVED},
    OrderStatus.CANCELED: {OrderStatus.ARCHIVED},
    OrderStatus.ARCHIVED: set(),
}


@dataclass(slots=True, kw_only=True)
class Order:
    """
    Order Aggregate Root.
    Represents a real purchase order from an authenticated customer.
    Contains items, delivery info, and tracks status transitions.
    """

    id: int
    customer_user_id: int
    items: list[OrderItem]
    total: Decimal
    delivery: DeliveryInfo
    comment: str
    status: OrderStatus
    created_at: datetime
    contact_email: str = ""
    contact_phone: str = ""

    @classmethod
    def place(
        cls,
        *,
        customer_user_id: int,
        items: list[OrderItem],
        delivery: DeliveryInfo,
        contact_phone: str = "",
        contact_email: str = "",
        comment: str = "",
    ) -> "Order":
        if customer_user_id <= 0:
            raise OrderRequiresCustomerError()
        if not items:
            raise EmptyOrderError()
        total = sum(
            (item.unit_price * item.quantity for item in items),
            Decimal(0),
        )
        return cls(
            id=0,
            customer_user_id=customer_user_id,
            contact_email=contact_email,
            contact_phone=contact_phone,
            items=list(items),
            total=total,
            delivery=delivery,
            comment=comment,
            status=OrderStatus.NEW,
            created_at=datetime.now(),
        )

    def change_status(self, new_status: OrderStatus) -> None:
        allowed = _TRANSITIONS.get(self.status, set())
        if not allowed:
            raise OrderAlreadyTerminalError(self.status.value, new_status.value)
        if new_status not in allowed:
            raise IllegalOrderTransitionError(self.status.value, new_status.value)
        self.status = new_status

    def archive(self) -> None:
        """Convenience: transition to ARCHIVED from any non-terminal state."""
        if self.status is OrderStatus.ARCHIVED:
            raise OrderAlreadyTerminalError(
                self.status.value, OrderStatus.ARCHIVED.value
            )
        self.change_status(OrderStatus.ARCHIVED)
