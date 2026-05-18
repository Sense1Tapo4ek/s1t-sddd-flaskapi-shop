from dataclasses import dataclass
from datetime import datetime

from .inquiry_status import InquiryStatus
from .errors import (
    InquiryCreationError,
    IllegalInquiryTransitionError,
    InquiryAlreadyTerminalError,
)

_TRANSITIONS: dict[InquiryStatus, set[InquiryStatus]] = {
    InquiryStatus.NEW: {InquiryStatus.IN_PROGRESS, InquiryStatus.CLOSED, InquiryStatus.ARCHIVED},
    InquiryStatus.IN_PROGRESS: {InquiryStatus.CLOSED, InquiryStatus.ARCHIVED},
    InquiryStatus.CLOSED: {InquiryStatus.ARCHIVED},
    InquiryStatus.ARCHIVED: set(),
}


@dataclass(slots=True, kw_only=True)
class Inquiry:
    """
    Inquiry Aggregate Root.
    Represents a contact/inquiry message from a visitor (not an order with items).
    """

    id: int
    name: str
    phone: str | None
    contact_email: str | None
    message: str
    status: InquiryStatus
    created_at: datetime
    author_user_id: int | None = None

    @classmethod
    def create(
        cls,
        id: int,
        name: str,
        message: str,
        *,
        phone: str | None = None,
        contact_email: str | None = None,
        author_user_id: int | None = None,
    ) -> "Inquiry":
        if not name or not name.strip():
            raise InquiryCreationError("Name is required")
        if not message or not message.strip():
            raise InquiryCreationError("Message is required")

        return cls(
            id=id,
            name=name,
            phone=phone,
            contact_email=contact_email,
            message=message,
            status=InquiryStatus.NEW,
            created_at=datetime.now(),
            author_user_id=author_user_id,
        )

    def change_status(self, new_status: InquiryStatus) -> None:
        allowed = _TRANSITIONS.get(self.status, set())
        if not allowed:
            raise InquiryAlreadyTerminalError(self.status.value, new_status.value)
        if new_status not in allowed:
            raise IllegalInquiryTransitionError(self.status.value, new_status.value)
        self.status = new_status

    def archive(self) -> None:
        """Convenience method: transition to ARCHIVED from any non-terminal state."""
        if self.status is InquiryStatus.ARCHIVED:
            raise InquiryAlreadyTerminalError(self.status.value, InquiryStatus.ARCHIVED.value)
        self.change_status(InquiryStatus.ARCHIVED)
