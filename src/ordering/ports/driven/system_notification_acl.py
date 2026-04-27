from dataclasses import dataclass
import logging

from access.ports.driving.facade import AccessFacade
from ordering.app.interfaces.i_notification_acl import INotificationAcl
from ordering.domain.order_agg import Order
from system.ports.driving import SystemFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemNotificationAcl(INotificationAcl):
    _system: SystemFacade
    _access: AccessFacade

    def notify_new_order(self, order: Order) -> None:
        for user in self._access.order_notification_recipients():
            if not user.telegram_chat_id:
                continue
            try:
                self._system.send_notification_to_chat(
                    chat_id=user.telegram_chat_id,
                    subject="New order",
                    body=f"{order.name}, {order.phone}",
                )
            except Exception:
                logger.exception(
                    "Order notification failed for recipient %s", user.login
                )
