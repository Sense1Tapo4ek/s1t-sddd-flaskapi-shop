from dataclasses import dataclass
from ...app import ViewCatalogUseCase, ManageCatalogUseCase
from .schemas import CatalogListOut, ProductDetailOut, ProductOut, AdminProductListOut


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogFacade:
    """
    Unified Entry Point for Catalog Context.
    Used by both Public API and Admin Dashboard.
    """

    _view_uc: ViewCatalogUseCase
    _manage_uc: ManageCatalogUseCase

    # --- Public ---
    def get_public_catalog(self, page: int = 1, limit: int = 20) -> CatalogListOut:
        res = self._view_uc.get_paginated(page=page, limit=limit)
        return CatalogListOut.from_domain(res)

    def get_random(self, limit: int = 4) -> list[ProductOut]:
        res = self._view_uc.get_random(limit=limit)
        return [ProductOut.from_domain(p) for p in res]

    def get_detail(self, product_id: int) -> ProductDetailOut:
        res = self._view_uc.get_detail(product_id)
        return ProductDetailOut.from_domain(res)

    # --- Admin ---
    def search_products(
        self,
        query: str = "",
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        filters: dict | None = None,
    ) -> AdminProductListOut:

        # Guard against None
        safe_filters = filters if filters is not None else {}

        res = self._manage_uc.search(
            query=query,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=safe_filters,
        )
        return AdminProductListOut.from_domain(res)

    def create_product(
        self, title: str, price: float, description: str, images: list
    ) -> ProductDetailOut:
        res = self._manage_uc.create(
            title=title, price=price, description=description, images=images
        )
        return ProductDetailOut.from_domain(res)

    def update_product(self, product_id: int, **kwargs) -> ProductDetailOut:
        res = self._manage_uc.update(product_id=product_id, **kwargs)
        return ProductDetailOut.from_domain(res)

    def delete_image(self, product_id: int, image_path: str) -> ProductDetailOut:
        res = self._manage_uc.delete_image(product_id, image_path)
        return ProductDetailOut.from_domain(res)

    def delete_product(self, product_id: int) -> bool:
        return self._manage_uc.delete(product_id)
