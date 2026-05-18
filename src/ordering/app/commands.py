from dataclasses import dataclass

from shared.ports.driving.bulk_schemas import BulkTarget  # pre-existing project convention (see bulk_change_order_status_uc.py)


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkChangeInquiryStatusCommand:
    target: BulkTarget
    status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateInquiryCommand:
    name: str
    message: str
    phone: str | None = None
    contact_email: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeInquiryStatusCommand:
    inquiry_id: int
    new_status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchiveInquiryCommand:
    inquiry_id: int
