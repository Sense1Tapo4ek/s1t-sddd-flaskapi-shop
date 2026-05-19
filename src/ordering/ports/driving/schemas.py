from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from shared.generics.pagination import PaginatedResult
from shared.ports.driving.bulk_schemas import BulkTarget
from ...app.commands import (
    CreateInquiryCommand,
    ChangeInquiryStatusCommand,
    PlaceOrderCommand,
    PlaceOrderItem as PlaceOrderItemCmd,
    ChangeOrderStatusCommand,
)
from ...domain import Inquiry, Order
from ...domain.inquiry_status import InquiryStatus
from ...domain.order_status import OrderStatus


class InquirySearchQuery(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sort_by: str | None = None
    sort_dir: str = Field("desc", pattern="^(asc|desc)$")

    status: InquiryStatus | None = None


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
    status: InquiryStatus

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


# ─── Bulk action inputs (Inquiries) ─────────────────────────────────


class BulkInquiriesStatusIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    target: BulkTarget
    status: str


# ─── Order schemas ────────────────────────────────────────────────────────────

class OrderItemIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    product_id: int = Field(..., ge=1)
    quantity: int = Field(..., ge=1)


class OrderIn(BaseModel):
    """
    Input schema for placing an order.
    customer_user_id is NOT here — it comes from g.customer_user_id via @customer_required.
    """
    model_config = ConfigDict(frozen=True)
    items: list[OrderItemIn] = Field(..., min_length=1)
    delivery_method: Literal["pickup", "courier"] = "pickup"
    contact_phone: str = Field(..., min_length=5, max_length=30, pattern=r"^[\d\s\+\-\(\)]+$")
    contact_email: str = Field("", max_length=255)
    address: str = Field("", max_length=500)
    delivery_comment: str = Field("", max_length=500)
    comment: str = Field("", max_length=2000)

    def to_command(self, customer_user_id: int) -> PlaceOrderCommand:
        return PlaceOrderCommand(
            customer_user_id=customer_user_id,
            items=[
                PlaceOrderItemCmd(product_id=i.product_id, quantity=i.quantity)
                for i in self.items
            ],
            delivery_method=self.delivery_method,
            contact_phone=self.contact_phone,
            contact_email=self.contact_email,
            address=self.address,
            delivery_comment=self.delivery_comment,
            comment=self.comment,
        )


class OrderStatusUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: OrderStatus

    def to_command(self, order_id: int) -> ChangeOrderStatusCommand:
        return ChangeOrderStatusCommand(order_id=order_id, new_status=self.status)


class OrderItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    product_id: int
    title_snapshot: str
    unit_price: Decimal
    quantity: int

    @classmethod
    def from_domain(cls, item) -> "OrderItemOut":
        return cls(
            product_id=item.product_id,
            title_snapshot=item.title_snapshot,
            unit_price=item.unit_price,
            quantity=item.quantity,
        )


class OrderOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    customer_user_id: int
    contact_email: str
    contact_phone: str
    items: list[OrderItemOut]
    total: Decimal
    delivery_method: str
    delivery_address: str
    delivery_comment: str
    comment: str
    status: str
    created_at: str

    @classmethod
    def from_domain(cls, order: Order) -> "OrderOut":
        return cls(
            id=order.id,
            customer_user_id=order.customer_user_id,
            contact_email=order.contact_email,
            contact_phone=order.contact_phone,
            items=[OrderItemOut.from_domain(i) for i in order.items],
            total=order.total,
            delivery_method=order.delivery.method.value,
            delivery_address=order.delivery.address,
            delivery_comment=order.delivery.comment,
            comment=order.comment,
            status=order.status.value,
            created_at=order.created_at.strftime("%Y-%m-%d %H:%M"),
        )


class OrderSearchQuery(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sort_by: str | None = None
    sort_dir: str = Field("desc", pattern="^(asc|desc)$")
    status: OrderStatus | None = None
    customer_user_id: int | None = None


class PaginatedOrdersOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[OrderOut]
    total: int

    @classmethod
    def from_domain(cls, result: PaginatedResult[Order]) -> "PaginatedOrdersOut":
        return cls(
            items=[OrderOut.from_domain(o) for o in result.items],
            total=result.total,
        )


# ─── Bulk action inputs (Orders) ─────────────────────────────────────


class BulkOrdersStatusIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    target: BulkTarget
    status: OrderStatus
