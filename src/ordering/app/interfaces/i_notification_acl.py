from typing import Protocol, runtime_checkable
from ordering.domain.order_agg import Order


@runtime_checkable
class INotificationAcl(Protocol):
    def notify_new_order(self, order: Order) -> None: ...
