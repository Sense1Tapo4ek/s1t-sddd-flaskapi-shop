from dataclasses import dataclass

from ..interfaces import IOrderRepo
from ..commands import DeleteOrderCommand
from ..errors import OrderNotFoundError


@dataclass(frozen=True, slots=True, kw_only=True)
class DeleteOrderUseCase:
    _repo: IOrderRepo

    def __call__(self, cmd: DeleteOrderCommand) -> None:
        order = self._repo.get_by_id(cmd.order_id)
        if order is None:
            raise OrderNotFoundError(cmd.order_id)
        self._repo.delete(cmd.order_id)
