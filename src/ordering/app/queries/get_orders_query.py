from dataclasses import dataclass
from shared.generics.pagination import PaginatedResult, PaginationParams
from ...domain import Order
from ..interfaces import IOrderRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class GetOrdersQuery:
    _repo: IOrderRepo

    def __call__(
        self,
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        filters: dict | None = None,
    ) -> PaginatedResult[Order]:

        params = PaginationParams(
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=filters or {},
        )
        return self._repo.get_paginated(params)
