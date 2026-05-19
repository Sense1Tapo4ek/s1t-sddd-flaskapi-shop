from dataclasses import dataclass

from typing import Any

from ...app import (
    ArchiveOrderCommand,
    ArchiveOrderUseCase,
    ChangeOrderStatusCommand,
    ChangeOrderStatusUseCase,
    CreateDemoOrderingDataUseCase,
    CreateTestOrderUseCase,
    GetOrderByIdQuery,
    GetOrdersQuery,
    PlaceOrderUseCase,
)
from .schemas import (
    OrderIn,
    OrderOut,
    OrderSearchQuery,
    OrderStatusUpdateIn,
    PaginatedOrdersOut,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class OrdersFacade:
    """
    Public API for the new Order aggregate.
    Driving adapter: place_order is customer-facing; all others are admin-facing.
    """

    _place_uc: PlaceOrderUseCase
    _change_status_uc: ChangeOrderStatusUseCase
    _archive_uc: ArchiveOrderUseCase
    _get_query: GetOrdersQuery
    _get_by_id_query: GetOrderByIdQuery
    _demo_uc: CreateDemoOrderingDataUseCase
    _test_order_uc: CreateTestOrderUseCase

    def place_order(self, schema: OrderIn, customer_user_id: int) -> int:
        cmd = schema.to_command(customer_user_id)
        return self._place_uc(cmd)

    def get_order(self, order_id: int) -> OrderOut:
        from ...app.errors import OrderNotFoundError

        order = self._get_by_id_query(order_id)
        if order is None:
            raise OrderNotFoundError(order_id)
        return OrderOut.from_domain(order)

    def change_order_status(self, order_id: int, schema: OrderStatusUpdateIn) -> int:
        cmd = schema.to_command(order_id)
        return self._change_status_uc(cmd)

    def archive_order(self, order_id: int) -> int:
        cmd = ArchiveOrderCommand(order_id=order_id)
        return self._archive_uc(cmd)

    def list_orders(
        self,
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        filters: dict | None = None,
    ) -> PaginatedOrdersOut:
        result = self._get_query(
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=filters or {},
        )
        return PaginatedOrdersOut.from_domain(result)

    def create_demo_data(self) -> dict[str, Any]:
        return self._demo_uc().as_dict()

    def create_test_order(self) -> int:
        return self._test_order_uc()
