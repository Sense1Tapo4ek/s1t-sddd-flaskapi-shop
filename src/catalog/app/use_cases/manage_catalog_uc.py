from dataclasses import dataclass
from typing import Any
from shared.generics.pagination import PaginatedResult, PaginationParams
from ...domain import (
    InvalidAttributeError,
    InvalidProductError,
    Product,
    ProductAttributeValue,
    ProductNotFoundError,
)
from ..interfaces import IProductRepo, IFileStorage, ITaxonomyRepo


@dataclass(frozen=True, slots=True, kw_only=True)
class ManageCatalogUseCase:
    """
    Admin access to the catalog (Write + Search).
    """

    _repo: IProductRepo
    _storage: IFileStorage
    _taxonomy_repo: ITaxonomyRepo

    def search(
        self,
        query: str,
        page: int = 1,
        limit: int = 20,
        sort_by: str | None = None,
        sort_dir: str = "asc",
        filters: dict | None = None,
    ) -> PaginatedResult[Product]:

        params = PaginationParams(
            page=page,
            limit=limit,
            sort_by=sort_by,
            sort_dir=sort_dir,
            filters=filters or {},
        )

        return self._repo.search(query, params)

    def create(
        self,
        title: str,
        price: float,
        description: str,
        images: list[tuple[str, bytes]],
        category_id: int | None = None,
        tag_ids: list[int] | None = None,
        attribute_values: dict[str, Any] | None = None,
    ) -> Product:
        # 1. Validate taxonomy before any file side effects.
        tags = self._load_tags(tag_ids or [])
        attributes = self._build_attributes(category_id, attribute_values or {})

        # 2. Save images
        image_paths = []
        for filename, data in images:
            path = self._storage.save(filename, data)
            image_paths.append(path)

        # 3. Create Domain Object (ID=0, repo will assign)
        product = Product.create(
            id=0,
            title=title,
            price=price,
            description=description,
            images=image_paths,
            category_id=category_id,
        )
        product.tags = tags
        product.attributes = attributes

        # 4. Persist
        return self._repo.create(product)

    def update(
        self,
        product_id: int,
        title: str | None = None,
        price: float | None = None,
        description: str | None = None,
        new_images: list[tuple[str, bytes]] | None = None,
        deleted_images: list[str] | None = None,
        category_id: int | None = None,
        tag_ids: list[int] | None = None,
        attribute_values: dict[str, Any] | None = None,
    ) -> Product:
        # 1. Load
        product = self._repo.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)

        # 2. Validate taxonomy before any file side effects.
        pending_category_id = category_id if category_id is not None else product.category_id
        pending_attributes = None
        if category_id is not None or attribute_values is not None:
            raw_attribute_values = (
                attribute_values
                if attribute_values is not None
                else {attribute.code: attribute.value for attribute in product.attributes}
            )
            pending_attributes = self._build_attributes(
                pending_category_id,
                raw_attribute_values,
            )

        # 3. Handle Image Side Effects (Infra)
        if deleted_images:
            for path in deleted_images:
                self._storage.delete(path)
                if path in product.images:
                    product.images.remove(path)

        if new_images:
            for filename, data in new_images:
                path = self._storage.save(filename, data)
                product.images.append(path)

        # 4. Update Domain Fields
        if title is not None:
            product.title = title
        if price is not None:
            product.price = price
        if description is not None:
            product.description = description
        if category_id is not None:
            product.category_id = category_id
            product.attributes = pending_attributes or []
        if tag_ids is not None:
            product.tags = self._load_tags(tag_ids)
        if attribute_values is not None and category_id is None:
            product.attributes = pending_attributes or []

        # 5. Persist
        return self._repo.update(product)

    def delete_image(self, product_id: int, image_path: str) -> Product:
        product = self._repo.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)

        if image_path not in product.images:
            raise ProductNotFoundError(product_id)

        self._storage.delete(image_path)
        product.images.remove(image_path)
        return self._repo.update(product)

    def delete(self, product_id: int) -> bool:
        # 1. Load to clean up files
        product = self._repo.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(product_id)

        # 2. Clean up files
        for path in product.images:
            self._storage.delete(path)

        # 3. Delete from DB
        return self._repo.delete(product_id)

    def swap_ids(self, id_a: int, id_b: int) -> None:
        self._repo.swap_ids(id_a, id_b)

    def _load_tags(self, tag_ids: list[int]):
        tags = []
        for tag_id in tag_ids:
            tag = self._taxonomy_repo.get_tag(tag_id)
            if tag is None:
                raise InvalidProductError(f"тег {tag_id} не найден")
            tags.append(tag)
        return tags

    def _build_attributes(
        self, category_id: int | None, raw_values: dict[str, Any]
    ) -> list[ProductAttributeValue]:
        if category_id is None:
            return []
        if not self._taxonomy_repo.is_leaf_category(category_id):
            raise InvalidProductError("товар можно привязать только к конечной категории")

        definitions = self._taxonomy_repo.get_effective_attributes(category_id)
        values: list[ProductAttributeValue] = []
        for definition in definitions:
            raw = raw_values.get(definition.code)
            if definition.type == "date" and raw in (None, "", []):
                continue
            if definition.is_required and raw in (None, "", []):
                raise InvalidAttributeError(f"поле {definition.title} обязательно")
            if raw in (None, "", []):
                continue
            values.append(
                ProductAttributeValue(
                    attribute_id=definition.id,
                    code=definition.code,
                    title=definition.title,
                    type=definition.type,
                    value=self._coerce_attribute_value(definition, raw),
                    unit=definition.unit,
                )
            )
        return values

    def _coerce_attribute_value(self, definition, raw: Any) -> Any:
        if definition.type == "number":
            try:
                return float(raw)
            except (TypeError, ValueError):
                raise InvalidAttributeError(f"{definition.title} должно быть числом")
        if definition.type == "boolean":
            return str(raw).lower() in ("1", "true", "yes", "on", "да")
        if definition.type == "multiselect":
            if isinstance(raw, list):
                values = raw
            else:
                values = [item.strip() for item in str(raw).split(",") if item.strip()]
            allowed = {option.value for option in definition.options}
            if allowed and any(str(value) not in allowed for value in values):
                raise InvalidAttributeError(f"{definition.title}: неизвестное значение")
            return values
        if definition.type == "select":
            allowed = {option.value for option in definition.options}
            if allowed and str(raw) not in allowed:
                raise InvalidAttributeError(f"{definition.title}: неизвестное значение")
        if definition.type in {"file", "image"}:
            if definition.value_mode == "multiple":
                if isinstance(raw, list):
                    return [str(item) for item in raw if str(item).strip()]
                return [
                    item.strip()
                    for item in str(raw).replace("\n", ",").split(",")
                    if item.strip()
                ]
            if isinstance(raw, list):
                return str(raw[0]) if raw else ""
            return str(raw)
        return raw
