from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from shared.generics.pagination import PaginatedResult
from shared.ports.driving.bulk_schemas import BulkTarget
from ...app.commands import CreateInquiryCommand, ChangeInquiryStatusCommand
from ...domain import Inquiry

InquiryStatusLiteral = Literal["new", "in_progress", "closed", "archived"]


class InquirySearchQuery(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sort_by: str | None = None
    sort_dir: str = Field("desc", pattern="^(asc|desc)$")

    status: InquiryStatusLiteral | None = None


class InquiryIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(..., min_length=1, max_length=200)
    phone: str | None = Field(None, min_length=5, max_length=30, pattern=r"^[\d\s\+\-\(\)]+$")
    contact_email: str | None = Field(None, max_length=255)
    message: str = Field(..., min_length=1, max_length=5000)

    def to_command(self) -> CreateInquiryCommand:
        return CreateInquiryCommand(
            name=self.name,
            phone=self.phone,
            contact_email=self.contact_email,
            message=self.message,
        )


class InquiryStatusUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: InquiryStatusLiteral

    def to_command(self, inquiry_id: int) -> ChangeInquiryStatusCommand:
        return ChangeInquiryStatusCommand(inquiry_id=inquiry_id, new_status=self.status)


class InquiryOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    name: str
    phone: str | None
    contact_email: str | None
    message: str
    status: str
    created_at: str
    author_user_id: int | None

    @classmethod
    def from_domain(cls, inquiry: Inquiry) -> "InquiryOut":
        return cls(
            id=inquiry.id,
            name=inquiry.name,
            phone=inquiry.phone,
            contact_email=inquiry.contact_email,
            message=inquiry.message,
            status=inquiry.status.value,
            created_at=inquiry.created_at.strftime("%Y-%m-%d %H:%M"),
            author_user_id=inquiry.author_user_id,
        )


class InquiryListOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[InquiryOut]
    total: int

    @classmethod
    def from_domain(cls, result: PaginatedResult[Inquiry]) -> "InquiryListOut":
        return cls(
            items=[InquiryOut.from_domain(i) for i in result.items], total=result.total
        )


# ─── Bulk action inputs ─────────────────────────────────────────────


class BulkInquiriesStatusIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    target: BulkTarget
    status: str
