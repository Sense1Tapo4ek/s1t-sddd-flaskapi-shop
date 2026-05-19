from dataclasses import dataclass

from ...app import (
    ArchiveInquiryCommand,
    ArchiveInquiryUseCase,
    ChangeInquiryStatusCommand,
    ChangeInquiryStatusUseCase,
    CreateInquiryUseCase,
    GetInquiriesQuery,
)
from .schemas import InquiryIn, InquiryListOut, InquiryStatusUpdateIn


@dataclass(frozen=True, slots=True, kw_only=True)
class InquiriesFacade:
    """
    Public API for Inquiries (contact messages) within the Ordering Context.
    Handles both Public (Create) and Admin (Status / Archive) operations.
    Authentication/Authorization is handled by the Adapter (Controller).
    """

    _create_uc: CreateInquiryUseCase
    _change_status_uc: ChangeInquiryStatusUseCase
    _archive_uc: ArchiveInquiryUseCase
    _get_query: GetInquiriesQuery

    def create_inquiry(self, schema: InquiryIn) -> int:
        cmd = schema.to_command()
        return self._create_uc(cmd)

    def change_inquiry_status(self, inquiry_id: int, schema: InquiryStatusUpdateIn) -> int:
        cmd = schema.to_command(inquiry_id)
        return self._change_status_uc(cmd)

    def archive_inquiry(self, inquiry_id: int) -> int:
        cmd = ArchiveInquiryCommand(inquiry_id=inquiry_id)
        return self._archive_uc(cmd)

    def list_inquiries(
        self,
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        filters: dict | None = None,
    ) -> InquiryListOut:

        safe_filters = filters if filters is not None else {}

        result = self._get_query(
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=safe_filters,
        )
        return InquiryListOut.from_domain(result)
