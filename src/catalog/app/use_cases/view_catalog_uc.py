from dataclasses import dataclass
from shared.generics.pagination import PaginatedResult, PaginationParams
from ...domain import Product, ProductNotFoundError
from ..interfaces import IProductRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ViewCatalogUseCase:
    """
    Public access to the catalog (Read-Only).
    """

    _repo: IProductRepo

    def get_paginated(
        self,
        page: int = 1,
        limit: int = 20,
        filters: dict | None = None,
    ) -> PaginatedResult[Product]:
        safe_filters = dict(filters or {})
        safe_filters["is_active"] = True
        params = PaginationParams(
            page=page,
            limit=limit,
            sort_by="id",
            sort_dir="desc",
            filters=safe_filters,
        )
        if filters:
            return self._repo.search("", params)
        return self._repo.get_paginated(params)

    def get_detail(self, product_id: int, *, include_inactive: bool = False) -> Product:
        product = self._repo.get_by_id(product_id)
        if product is None or (not include_inactive and not product.is_active):
            raise ProductNotFoundError(product_id)
        return product

    def get_random(self, limit: int = 4) -> list[Product]:
        return [product for product in self._repo.get_random(limit) if product.is_active]
