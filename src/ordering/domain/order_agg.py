from dataclasses import dataclass
from datetime import datetime

from .order_status import OrderStatus
from .errors import OrderCreationError, InvalidOrderTransitionError

_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.NEW: {OrderStatus.PROCESSING, OrderStatus.CANCELED},
    OrderStatus.PROCESSING: {OrderStatus.DONE, OrderStatus.CANCELED},
    OrderStatus.DONE: set(),
    OrderStatus.CANCELED: set(),
}


@dataclass(slots=True)
class Order:
    """
    Order Aggregate Root.
    """

    id: int
    name: str
    phone: str
    comment: str
    status: OrderStatus
    created_at: datetime

    @classmethod
    def create(cls, id: int, name: str, phone: str, comment: str) -> "Order":
        if not phone:
            raise OrderCreationError("Phone number is required")

        return cls(
            id=id,
            name=name,
            phone=phone,
            comment=comment,
            status=OrderStatus.NEW,
            created_at=datetime.now(),
        )

    def change_status(self, new_status: OrderStatus) -> None:
        if new_status not in _TRANSITIONS.get(self.status, set()):
            raise InvalidOrderTransitionError(self.status.value, new_status.value)
        self.status = new_status
