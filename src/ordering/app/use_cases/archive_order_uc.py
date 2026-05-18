from dataclasses import dataclass

from ..commands import ArchiveOrderCommand
from ..errors import OrderNotFoundError
from ..interfaces import IOrderRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ArchiveOrderUseCase:
    _repo: IOrderRepo

    def __call__(self, cmd: ArchiveOrderCommand) -> int:
        order = self._repo.get_by_id(cmd.order_id)
        if order is None:
            raise OrderNotFoundError(cmd.order_id)

        order.archive()
        self._repo.save(order)
        return order.id
