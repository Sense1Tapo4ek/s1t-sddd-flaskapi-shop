from dataclasses import dataclass


# ─── Order commands ──────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderItem:
    product_id: int
    quantity: int


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderCommand:
    customer_user_id: int
    items: list[PlaceOrderItem]
    delivery_method: str          # "pickup" | "courier"
    contact_phone: str
    contact_email: str = ""
    address: str = ""
    delivery_comment: str = ""
    comment: str = ""


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeOrderStatusCommand:
    order_id: int
    new_status: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchiveOrderCommand:
    order_id: int


# ─── Inquiry commands ─────────────────────────────────────────────────────────


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
