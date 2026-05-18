from typing import Protocol, runtime_checkable
from shared.generics.pagination import PaginatedResult, PaginationParams
from ...domain import Inquiry


@runtime_checkable
class IInquiryRepo(Protocol):
    def next_id(self) -> int: ...
    def save(self, inquiry: Inquiry) -> None: ...
    def get_by_id(self, inquiry_id: int) -> Inquiry | None: ...
    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Inquiry]: ...
    def iter_ids_by_filter(
        self,
        filter_payload: dict,
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[int], str | None]: ...
