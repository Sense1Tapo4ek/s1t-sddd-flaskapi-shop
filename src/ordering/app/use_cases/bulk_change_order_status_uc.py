"""Bulk change order status. Per-row mutation through the runner;
domain errors become BulkFailure rows."""
from __future__ import annotations

from dataclasses import dataclass

from shared.app.bulk_runner import BulkRunner
from shared.ports.driving.bulk_schemas import BulkResultSchema

from ..commands import BulkChangeOrderStatusCommand, BulkArchiveOrderCommand
from ..errors import OrderNotFoundError
from ..interfaces import IOrderRepo
from ...domain import InvalidOrderTransitionError, OrderStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkChangeOrderStatusUseCase:
    _repo: IOrderRepo

    def __call__(self, cmd: BulkChangeOrderStatusCommand) -> BulkResultSchema:
        def process_one(order_id: int) -> None:
            order = self._repo.get_by_id(int(order_id))
            if order is None:
                raise OrderNotFoundError(int(order_id))
            try:
                target = OrderStatus(cmd.status)
            except ValueError:
                raise InvalidOrderTransitionError.for_transition(
                    order.status.value, cmd.status
                ) from None
            order.change_status(target)
            self._repo.save(order)

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_ids_by_filter,
        )
        return runner.run(cmd.target)


@dataclass(frozen=True, slots=True, kw_only=True)
class BulkArchiveOrderUseCase:
    _repo: IOrderRepo

    def __call__(self, cmd: BulkArchiveOrderCommand) -> BulkResultSchema:
        def process_one(order_id: int) -> None:
            order = self._repo.get_by_id(int(order_id))
            if order is None:
                raise OrderNotFoundError(int(order_id))
            order.archive()
            self._repo.save(order)

        runner = BulkRunner(
            process_one=process_one,
            load_filter_page=self._repo.iter_ids_by_filter,
        )
        return runner.run(cmd.target)
