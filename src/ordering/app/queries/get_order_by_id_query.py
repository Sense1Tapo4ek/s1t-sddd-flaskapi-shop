from dataclasses import dataclass

from ..interfaces import IOrderRepo
from ...domain import Order


@dataclass(frozen=True, slots=True, kw_only=True)
class GetOrderByIdQuery:
    _repo: IOrderRepo

    def __call__(self, order_id: int) -> Order | None:
        return self._repo.get_by_id(order_id)
