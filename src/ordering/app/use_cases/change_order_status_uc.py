from dataclasses import dataclass

from ..commands import ChangeOrderStatusCommand
from ..errors import OrderNotFoundError
from ..interfaces import IOrderRepo
from ...domain import InvalidOrderTransitionError, OrderStatus


@dataclass(frozen=True, slots=True, kw_only=True)
class ChangeOrderStatusUseCase:
    _repo: IOrderRepo

    def __call__(self, cmd: ChangeOrderStatusCommand) -> int:
        order = self._repo.get_by_id(cmd.order_id)
        if order is None:
            raise OrderNotFoundError(cmd.order_id)

        try:
            new_status = OrderStatus(cmd.new_status)
        except ValueError:
            raise InvalidOrderTransitionError.for_transition(
                order.status.value, cmd.new_status
            ) from None

        order.change_status(new_status)
        self._repo.save(order)
        return order.id
