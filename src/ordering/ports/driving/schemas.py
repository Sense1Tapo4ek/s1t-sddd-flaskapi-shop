from pydantic import BaseModel, ConfigDict, Field
from shared.generics.pagination import PaginatedResult
from ...app.commands import PlaceOrderCommand, ProcessOrderCommand
from ...domain import Order


class OrderSearchQuery(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)
    sort_by: str | None = None
    sort_dir: str = Field("desc", pattern="^(asc|desc)$")

    status: str | None = None


class OrderIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    name: str = Field(..., min_length=1, max_length=200)
    phone: str = Field(..., min_length=5, max_length=30, pattern=r"^[\d\s\+\-\(\)]+$")
    comment: str = Field("", max_length=2000)

    def to_command(self) -> PlaceOrderCommand:
        return PlaceOrderCommand(name=self.name, phone=self.phone, comment=self.comment)


class OrderStatusUpdateIn(BaseModel):
    model_config = ConfigDict(frozen=True)
    status: str

    def to_command(self, order_id: int) -> ProcessOrderCommand:
        return ProcessOrderCommand(order_id=order_id, new_status=self.status)


class OrderOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: int
    name: str
    phone: str
    status: str
    comment: str
    created_at: str

    @classmethod
    def from_domain(cls, order: Order) -> "OrderOut":
        return cls(
            id=order.id,
            name=order.name,
            phone=order.phone,
            status=order.status.value,
            comment=order.comment,
            created_at=order.created_at.strftime("%Y-%m-%d %H:%M"),
        )


class OrderListOut(BaseModel):
    model_config = ConfigDict(frozen=True)
    items: list[OrderOut]
    total: int

    @classmethod
    def from_domain(cls, result: PaginatedResult[Order]) -> "OrderListOut":
        return cls(
            items=[OrderOut.from_domain(o) for o in result.items], total=result.total
        )
