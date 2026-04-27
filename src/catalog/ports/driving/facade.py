from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, Callable

from ...app import (
    CreateDemoDataUseCase,
    ManageCatalogUseCase,
    ManageTaxonomyUseCase,
    ViewCatalogUseCase,
)
from .schemas import (
    AdminProductListOut,
    CatalogListOut,
    CategoryAttributeCreateIn,
    CategoryAttributeOut,
    CategoryAttributesOut,
    CategoryAttributeUpdateIn,
    CategoryCreateIn,
    CategoryMoveIn,
    CategoryOut,
    CategoryUpdateIn,
    ProductDetailOut,
    ProductOut,
    TagCreateIn,
    TagOut,
    TagUpdateIn,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogFacade:
    """
    Unified Entry Point for Catalog Context.
    Used by both Public API and Admin Dashboard.
    """

    _view_uc: ViewCatalogUseCase
    _manage_uc: ManageCatalogUseCase
    _taxonomy_uc: ManageTaxonomyUseCase
    _demo_data_uc: CreateDemoDataUseCase

    def _taxonomy(self) -> ManageTaxonomyUseCase:
        return self._taxonomy_uc

    def _dump_payload(self, payload: Any, *, exclude_unset: bool = False) -> dict[str, Any]:
        if hasattr(payload, "model_dump"):
            return payload.model_dump(exclude_unset=exclude_unset)
        return dict(payload)

    def _call_supported(self, method: Callable[..., Any], **kwargs: Any) -> Any:
        method_signature = signature(method)
        parameters = method_signature.parameters.values()
        accepts_kwargs = any(p.kind == Parameter.VAR_KEYWORD for p in parameters)
        if accepts_kwargs:
            return method(**kwargs)

        supported_keys = set(method_signature.parameters)
        filtered_kwargs = {
            key: value for key, value in kwargs.items() if key in supported_keys
        }
        return method(**filtered_kwargs)

    # --- Public ---
    def get_public_catalog(
        self,
        page: int = 1,
        limit: int = 20,
        filters: dict[str, Any] | None = None,
    ) -> CatalogListOut:
        res = self._call_supported(
            self._view_uc.get_paginated,
            page=page,
            limit=limit,
            filters=filters or {},
        )
        return CatalogListOut.from_domain(res)

    def get_random(self, limit: int = 4) -> list[ProductOut]:
        res = self._view_uc.get_random(limit=limit)
        return [ProductOut.from_domain(p) for p in res]

    def get_detail(self, product_id: int) -> ProductDetailOut:
        res = self._view_uc.get_detail(product_id)
        return ProductDetailOut.from_domain(res)

    def get_admin_detail(self, product_id: int) -> ProductDetailOut:
        res = self._view_uc.get_detail(product_id, include_inactive=True)
        return ProductDetailOut.from_domain(res)

    def list_public_category_tree(self) -> list[CategoryOut]:
        return self.list_category_tree(include_inactive=False)

    def list_public_tags(self) -> list[TagOut]:
        return self.list_tags(include_inactive=False)

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
        self,
        title: str,
        price: float,
        description: str,
        images: list[tuple[str, bytes]],
        category_id: int | None = None,
        tag_ids: list[int] | None = None,
        attribute_values: dict[str, Any] | None = None,
    ) -> ProductDetailOut:
        res = self._call_supported(
            self._manage_uc.create,
            title=title,
            price=price,
            description=description,
            images=images,
            category_id=category_id,
            tag_ids=tag_ids or [],
            attribute_values=attribute_values or {},
        )
        return ProductDetailOut.from_domain(res)

    def update_product(self, product_id: int, **kwargs) -> ProductDetailOut:
        res = self._call_supported(
            self._manage_uc.update, product_id=product_id, **kwargs
        )
        return ProductDetailOut.from_domain(res)

    def delete_image(self, product_id: int, image_path: str) -> ProductDetailOut:
        res = self._manage_uc.delete_image(product_id, image_path)
        return ProductDetailOut.from_domain(res)

    def delete_product(self, product_id: int) -> bool:
        return self._manage_uc.delete(product_id)

    def swap_ids(self, id_a: int, id_b: int) -> None:
        self._manage_uc.swap_ids(id_a, id_b)

    # --- Taxonomy Admin ---
    def list_category_tree(self, *, include_inactive: bool = True) -> list[CategoryOut]:
        categories = self._taxonomy().list_category_tree(
            include_inactive=include_inactive
        )
        return [CategoryOut.from_domain(category) for category in categories]

    def get_category(self, category_id: int) -> CategoryOut:
        return CategoryOut.from_domain(self._taxonomy().get_category(category_id))

    def create_category(self, data: CategoryCreateIn | dict[str, Any]) -> CategoryOut:
        payload = self._dump_payload(data)
        category = self._taxonomy().create_category(**payload)
        return CategoryOut.from_domain(category)

    def update_category(
        self, category_id: int, data: CategoryUpdateIn | dict[str, Any]
    ) -> CategoryOut:
        payload = self._dump_payload(data, exclude_unset=True)
        category = self._taxonomy().update_category(category_id, **payload)
        return CategoryOut.from_domain(category)

    def move_category(
        self, category_id: int, data: CategoryMoveIn | dict[str, Any]
    ) -> CategoryOut:
        payload = self._dump_payload(data, exclude_unset=True)
        category = self._taxonomy().update_category(category_id, **payload)
        return CategoryOut.from_domain(category)

    def delete_category(self, category_id: int) -> None:
        self._taxonomy().delete_category(category_id)

    def get_category_products(
        self,
        category_id: int,
        *,
        include_descendants: bool = False,
        query: str = "",
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        filters: dict[str, Any] | None = None,
    ) -> AdminProductListOut:
        product_filters = dict(filters or {})
        product_filters["category_id"] = str(category_id)
        if include_descendants:
            product_filters["include_descendants"] = "true"
        return self.search_products(
            query=query,
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=product_filters,
        )

    def list_tags(self, *, include_inactive: bool = True) -> list[TagOut]:
        tags = self._taxonomy().list_tags(include_inactive=include_inactive)
        return [TagOut.from_domain(tag) for tag in tags]

    def create_tag(self, data: TagCreateIn | dict[str, Any]) -> TagOut:
        payload = self._dump_payload(data)
        tag = self._taxonomy().create_tag(**payload)
        return TagOut.from_domain(tag)

    def update_tag(self, tag_id: int, data: TagUpdateIn | dict[str, Any]) -> TagOut:
        payload = self._dump_payload(data, exclude_unset=True)
        tag = self._taxonomy().update_tag(tag_id, **payload)
        return TagOut.from_domain(tag)

    def delete_tag(self, tag_id: int) -> None:
        self._taxonomy().delete_tag(tag_id)

    def get_category_attributes(self, category_id: int) -> CategoryAttributesOut:
        attributes = self._taxonomy().get_effective_attributes(category_id)
        return CategoryAttributesOut.from_domain(category_id, attributes)

    def create_category_attribute(
        self, category_id: int, data: CategoryAttributeCreateIn | dict[str, Any]
    ) -> CategoryAttributeOut:
        payload = self._dump_payload(data)
        attribute = self._taxonomy().create_attribute(
            category_id=category_id, **payload
        )
        return CategoryAttributeOut.from_domain(attribute)

    def update_category_attribute(
        self,
        attribute_id: int,
        data: CategoryAttributeUpdateIn | dict[str, Any],
    ) -> CategoryAttributeOut:
        payload = self._dump_payload(data, exclude_unset=True)
        attribute = self._taxonomy().update_attribute(attribute_id, **payload)
        return CategoryAttributeOut.from_domain(attribute)

    def delete_category_attribute(self, attribute_id: int) -> None:
        self._taxonomy().delete_attribute(attribute_id)

    def create_demo_data(self) -> dict[str, Any]:
        return self._demo_data_uc().as_dict()
