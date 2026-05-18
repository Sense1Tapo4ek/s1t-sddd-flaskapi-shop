from dataclasses import dataclass
from shared.generics.pagination import PaginatedResult, PaginationParams
from ...domain import Inquiry
from ..interfaces import IInquiryRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class GetInquiriesQuery:
    _repo: IInquiryRepo

    def __call__(
        self,
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "desc",
        filters: dict | None = None,
    ) -> PaginatedResult[Inquiry]:

        params = PaginationParams(
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=filters or {},
        )
        return self._repo.get_paginated(params)
