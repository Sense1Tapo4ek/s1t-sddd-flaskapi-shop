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

    def get_paginated(self, page: int = 1, limit: int = 20) -> PaginatedResult[Product]:
        params = PaginationParams(page=page, limit=limit)
        return self._repo.get_paginated(params)

    def get_detail(self, product_id: int) -> Product:
        product = self._repo.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)
        return product

    def get_random(self, limit: int = 4) -> list[Product]:
        return self._repo.get_random(limit)
