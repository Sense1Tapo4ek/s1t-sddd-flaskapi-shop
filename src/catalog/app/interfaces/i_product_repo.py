from typing import Literal, Protocol, runtime_checkable

from shared.generics.pagination import PaginatedResult, PaginationParams
from ...domain import Product

BulkTagMode = Literal["replace", "add", "remove"]


@runtime_checkable
class IProductRepo(Protocol):
    def get_by_id(self, product_id: int) -> Product | None: ...

    def get_paginated(self, params: PaginationParams) -> PaginatedResult[Product]: ...

    def get_random(self, limit: int) -> list[Product]: ...

    def search(
        self, query: str, params: PaginationParams
    ) -> PaginatedResult[Product]: ...

    def create(self, product: Product) -> Product: ...

    def update(self, product: Product) -> Product: ...

    def delete(self, product_id: int) -> bool: ...

    def swap_ids(self, id_a: int, id_b: int) -> None: ...

    # ─── Bulk operations ────────────────────────────────────────────

    def iter_ids_by_filter(
        self,
        filter_payload: dict,
        *,
        cursor: str | None,
        limit: int,
    ) -> tuple[list[int], str | None]:
        """Cursor-paginated id loader for filter-mode bulk targets.

        ``filter_payload`` mirrors the search filter dict used by
        ``search()``. ``cursor`` is the last id from the previous page or
        ``None`` for the first page. Returns ``(ids, next_cursor)``;
        ``next_cursor=None`` signals the last page.
        """
        ...

    def set_active(self, product_id: int, active: bool) -> None:
        """Toggle a single product's active flag. Raises ``ProductNotFoundError``
        when no row matches."""
        ...

    def assign_category(self, product_id: int, category_id: int) -> None:
        """Move a product to a different leaf category. Raises
        ``ProductNotFoundError`` / ``CategoryNotFoundError`` /
        ``InvalidProductError`` on invariant violations."""
        ...

    def apply_tags(
        self,
        product_id: int,
        tag_ids: list[int],
        mode: BulkTagMode,
    ) -> None:
        """Apply tag changes per the requested mode."""
        ...

    def bulk_delete_one(self, product_id: int) -> None:
        """Delete a product, raising ``ProductInUseByActiveOrderError`` when
        a non-terminal order references it, or ``ProductNotFoundError`` when
        the row no longer exists."""
        ...
