from dataclasses import dataclass
import logging

from access.ports.driving import AdminFacade
from ordering.app.interfaces.i_notification_acl import INotificationAcl
from ordering.domain.inquiry_agg import Inquiry
from ordering.domain.order_agg import Order
from system.ports.driving import SystemFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemNotificationAcl(INotificationAcl):
    _system: SystemFacade
    _access: AdminFacade

    def notify_inquiry_created(self, inquiry: Inquiry) -> None:
        body = (
            f"📩 Новое обращение #{inquiry.id}\n"
            f"{inquiry.name} · {inquiry.phone or inquiry.contact_email or '—'}\n"
            f"«{inquiry.message[:300]}»"
        )
        self._fanout(subject="Новое обращение", body=body)

    def notify_order_placed(
        self, order: Order, customer_email: str | None = None
    ) -> None:
        items_count = len(order.items)
        contact = customer_email or "—"
        delivery_line = order.delivery.method.value
        if order.delivery.address:
            delivery_line += f" · {order.delivery.address}"
        body_lines = [
            f"🛒 Новый заказ #{order.id}",
            f"customer={order.customer_user_id} · {contact}",
            f"{items_count} товар(ов) · {order.total} Br",
            f"Доставка: {delivery_line}",
        ]
        if order.comment:
            body_lines.append(f"«{order.comment[:300]}»")
        self._fanout(subject="Новый заказ", body="\n".join(body_lines))

    def _fanout(self, *, subject: str, body: str) -> None:
        for user in self._access.order_notification_recipients():
            if not user.telegram_chat_id:
                continue
            try:
                self._system.send_notification_to_chat(
                    chat_id=user.telegram_chat_id,
                    subject=subject,
                    body=body,
                )
            except Exception:
                logger.exception(
                    "Notification fanout failed for recipient %s", user.login
                )
