from dataclasses import dataclass
from ordering.app.interfaces.i_notification_acl import INotificationAcl
from ordering.domain.order_agg import Order
from system.ports.driving import SystemFacade


@dataclass(frozen=True, slots=True)
class SystemNotificationAcl(INotificationAcl):
    _system: SystemFacade

    def notify_new_order(self, order: Order) -> None:
        self._system.send_notification(
            subject="New order",
            body=f"{order.name}, {order.phone}"
        )
