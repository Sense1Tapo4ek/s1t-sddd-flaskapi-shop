from dataclasses import dataclass

from ..interfaces import IOrderRepo
from ..commands import ProcessOrderCommand
from ..errors import OrderNotFoundError
from ...domain import OrderStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ProcessOrderUseCase:
    _repo: IOrderRepo

    def __call__(self, cmd: ProcessOrderCommand) -> int:
        order = self._repo.get_by_id(cmd.order_id)
        if order is None:
            raise OrderNotFoundError(cmd.order_id)

        # Domain Logic
        new_status = OrderStatus(cmd.new_status)
        order.change_status(new_status)

        # Persist
        self._repo.save(order)

        return order.id
