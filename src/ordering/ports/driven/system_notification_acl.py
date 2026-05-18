from dataclasses import dataclass
import logging

from access.ports.driving import AdminFacade
from ordering.app.interfaces.i_notification_acl import INotificationAcl
from ordering.domain.inquiry_agg import Inquiry
from system.ports.driving import SystemFacade

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemNotificationAcl(INotificationAcl):
    _system: SystemFacade
    _access: AdminFacade

    def notify_inquiry_created(self, inquiry: Inquiry) -> None:
        for user in self._access.order_notification_recipients():
            if not user.telegram_chat_id:
                continue
            try:
                self._system.send_notification_to_chat(
                    chat_id=user.telegram_chat_id,
                    subject="Новое обращение",
                    body=f"{inquiry.name}, {inquiry.phone or inquiry.contact_email or '—'}",
                )
            except Exception:
                logger.exception(
                    "Inquiry notification failed for recipient %s", user.login
                )
