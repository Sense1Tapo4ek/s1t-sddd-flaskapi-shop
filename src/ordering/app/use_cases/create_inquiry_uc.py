import logging
from dataclasses import dataclass

from ..interfaces import IInquiryRepo, INotificationAcl
from ..commands import CreateInquiryCommand
from ...domain import Inquiry

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateInquiryUseCase:
    _repo: IInquiryRepo
    _notification_acl: INotificationAcl

    def __call__(self, cmd: CreateInquiryCommand) -> int:
        # 1. Identity generation
        new_id = self._repo.next_id()

        # 2. Create Aggregate
        inquiry = Inquiry.create(
            id=new_id,
            name=cmd.name,
            message=cmd.message,
            phone=cmd.phone,
            contact_email=cmd.contact_email,
        )

        # 3. Persist
        self._repo.save(inquiry)

        # 4. Notify (Side Effect)
        # Notification failure must not break inquiry creation.
        try:
            self._notification_acl.notify_inquiry_created(inquiry)
        except Exception:
            logger.exception("Notification failed for inquiry %s", inquiry.id)

        return inquiry.id
