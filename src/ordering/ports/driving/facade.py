from dataclasses import dataclass
from ...app import PlaceOrderUseCase, ProcessOrderUseCase, DeleteOrderUseCase, GetOrdersQuery, DeleteOrderCommand
from .schemas import OrderIn, OrderStatusUpdateIn, OrderListOut


@dataclass(frozen=True, slots=True, kw_only=True)
class OrderingFacade:
    """
    Public API for Ordering Context.
    Handles both Public (Placement) and Admin (Processing) operations.
    Authentication/Authorization is handled by the Adapter (Controller).
    """

    _place_uc: PlaceOrderUseCase
    _process_uc: ProcessOrderUseCase
    _delete_uc: DeleteOrderUseCase
    _get_query: GetOrdersQuery

    def place_order(self, schema: OrderIn) -> int:
        cmd = schema.to_command()
        return self._place_uc(cmd)

    def process_order(self, order_id: int, schema: OrderStatusUpdateIn) -> int:
        cmd = schema.to_command(order_id)
        return self._process_uc(cmd)

    def delete_order(self, order_id: int) -> None:
        cmd = DeleteOrderCommand(order_id=order_id)
        self._delete_uc(cmd)

    def list_orders(
        self,
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        filters: dict | None = None,
    ) -> OrderListOut:

        safe_filters = filters if filters is not None else {}

        result = self._get_query(
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=safe_filters,
        )
        return OrderListOut.from_domain(result)
