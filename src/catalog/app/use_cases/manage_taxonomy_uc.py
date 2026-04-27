from dataclasses import dataclass
from typing import Any

from catalog.domain import (
    ATTRIBUTE_TYPES,
    ATTRIBUTE_VALUE_MODES,
    AttributeNotFoundError,
    Category,
    CategoryAttribute,
    CategoryNotFoundError,
    InvalidAttributeError,
    InvalidCategoryTreeError,
    Tag,
    TagNotFoundError,
)
from catalog.app.interfaces import ITaxonomyRepo


def _slugify(value: str) -> str:
    slug = value.strip().lower()
    result = []
    prev_dash = False
    for char in slug:
        if char.isalnum():
            result.append(char)
            prev_dash = False
        elif not prev_dash:
            result.append("-")
            prev_dash = True
    return "".join(result).strip("-") or "item"


@dataclass(frozen=True, slots=True, kw_only=True)
class ManageTaxonomyUseCase:
    _repo: ITaxonomyRepo

    def list_category_tree(self, *, include_inactive: bool = True) -> list[Category]:
        categories = self._repo.list_categories(include_inactive=include_inactive)
        by_parent: dict[int | None, list[Category]] = {}
        by_id = {c.id: c for c in categories}

        for category in categories:
            category.children = []
            by_parent.setdefault(category.parent_id, []).append(category)

        for category in categories:
            category.children = by_parent.get(category.id, [])

        roots = [
            category
            for category in categories
            if category.parent_id is None or category.parent_id not in by_id
        ]
        return sorted(roots, key=lambda c: (c.sort_order, c.title.lower()))

    def get_category(self, category_id: int) -> Category:
        category = self._repo.get_category(category_id)
        if category is None:
            raise CategoryNotFoundError(category_id)
        return category

    def create_category(
        self,
        *,
        parent_id: int | None,
        title: str,
        slug: str | None = None,
        description: str = "",
        sort_order: int = 0,
        is_active: bool = True,
    ) -> Category:
        if parent_id is not None and self._repo.get_category(parent_id) is None:
            raise CategoryNotFoundError(parent_id)
        safe_slug = _slugify(slug or title)
        self._assert_category_slug_available(safe_slug)
        return self._repo.create_category(
            parent_id=parent_id,
            title=title.strip(),
            slug=safe_slug,
            description=description,
            sort_order=sort_order,
            is_active=is_active,
        )

    def update_category(self, category_id: int, **kwargs: Any) -> Category:
        category = self.get_category(category_id)
        if "parent_id" in kwargs:
            parent_id = kwargs["parent_id"]
            if parent_id == category_id:
                raise InvalidCategoryTreeError("категория не может быть родителем самой себя")
            if parent_id is not None:
                parent = self._repo.get_category(parent_id)
                if parent is None:
                    raise CategoryNotFoundError(parent_id)
                if parent_id in self._repo.descendant_ids(category_id, include_self=False):
                    raise InvalidCategoryTreeError("нельзя переместить категорию внутрь собственного потомка")
        if "slug" in kwargs and kwargs["slug"]:
            safe_slug = _slugify(kwargs["slug"])
            self._assert_category_slug_available(safe_slug, exclude_category_id=category_id)
            kwargs["slug"] = safe_slug
        elif "title" in kwargs and not kwargs.get("slug"):
            kwargs.pop("slug", None)
        return self._repo.update_category(category_id, **kwargs)

    def delete_category(self, category_id: int) -> None:
        self.get_category(category_id)
        if self._repo.category_has_children(category_id):
            raise InvalidCategoryTreeError("нельзя удалить категорию с подкатегориями")
        if self._repo.category_has_products(category_id):
            raise InvalidCategoryTreeError("нельзя удалить категорию с товарами")
        self._repo.delete_category(category_id)

    def list_tags(self, *, include_inactive: bool = True) -> list[Tag]:
        return self._repo.list_tags(include_inactive=include_inactive)

    def create_tag(
        self,
        *,
        title: str,
        slug: str | None = None,
        color: str = "#7c8c6e",
        sort_order: int = 0,
        is_active: bool = True,
    ) -> Tag:
        return self._repo.create_tag(
            title=title.strip(),
            slug=_slugify(slug or title),
            color=color or "#7c8c6e",
            sort_order=sort_order,
            is_active=is_active,
        )

    def update_tag(self, tag_id: int, **kwargs: Any) -> Tag:
        if self._repo.get_tag(tag_id) is None:
            raise TagNotFoundError(tag_id)
        if "slug" in kwargs and kwargs["slug"]:
            kwargs["slug"] = _slugify(kwargs["slug"])
        return self._repo.update_tag(tag_id, **kwargs)

    def delete_tag(self, tag_id: int) -> None:
        if self._repo.get_tag(tag_id) is None:
            raise TagNotFoundError(tag_id)
        self._repo.delete_tag(tag_id)

    def get_effective_attributes(self, category_id: int) -> list[CategoryAttribute]:
        self.get_category(category_id)
        return self._repo.get_effective_attributes(category_id)

    def create_attribute(
        self,
        *,
        category_id: int,
        code: str,
        title: str,
        type: str,
        unit: str | None = None,
        is_required: bool = False,
        is_filterable: bool = True,
        is_public: bool = True,
        value_mode: str = "single",
        sort_order: int = 0,
        options: list[dict[str, Any]] | None = None,
    ) -> CategoryAttribute:
        self.get_category(category_id)
        safe_code = _slugify(code or title).replace("-", "_")
        if type not in ATTRIBUTE_TYPES:
            raise InvalidAttributeError(f"тип {type} не поддерживается")
        safe_value_mode = self._normalize_value_mode(type, value_mode)
        self._assert_attribute_code_available(category_id, safe_code)
        return self._repo.create_attribute(
            category_id=category_id,
            code=safe_code,
            title=title.strip(),
            type=type,
            unit=unit if type == "number" else None,
            is_required=is_required,
            is_filterable=True,
            is_public=True,
            value_mode=safe_value_mode,
            sort_order=sort_order,
            options=(options or []) if type in {"select", "multiselect"} else [],
        )

    def update_attribute(self, attribute_id: int, **kwargs: Any) -> CategoryAttribute:
        attribute = self._repo.get_attribute(attribute_id)
        if attribute is None:
            raise AttributeNotFoundError(attribute_id)

        next_type = kwargs.get("type", attribute.type)
        if next_type not in ATTRIBUTE_TYPES:
            raise InvalidAttributeError(f"тип {next_type} не поддерживается")
        if "code" in kwargs:
            if not kwargs["code"]:
                kwargs.pop("code")
            else:
                safe_code = _slugify(kwargs["code"]).replace("-", "_")
                self._assert_attribute_code_available(
                    attribute.category_id,
                    safe_code,
                    exclude_attribute_id=attribute_id,
                )
                kwargs["code"] = safe_code
        if "is_filterable" in kwargs:
            kwargs["is_filterable"] = True
        if "is_public" in kwargs:
            kwargs["is_public"] = True
        if "unit" in kwargs or "type" in kwargs:
            kwargs["unit"] = kwargs.get("unit", attribute.unit)
            if next_type != "number":
                kwargs["unit"] = None
        if "value_mode" in kwargs or "type" in kwargs:
            kwargs["value_mode"] = self._normalize_value_mode(
                next_type,
                kwargs.get("value_mode", attribute.value_mode),
            )
        if ("options" in kwargs or "type" in kwargs) and next_type not in {
            "select",
            "multiselect",
        }:
            kwargs["options"] = []
        try:
            return self._repo.update_attribute(attribute_id, **kwargs)
        except LookupError:
            raise AttributeNotFoundError(attribute_id)

    def delete_attribute(self, attribute_id: int) -> None:
        try:
            self._repo.delete_attribute(attribute_id)
        except LookupError:
            raise AttributeNotFoundError(attribute_id)

    def _assert_attribute_code_available(
        self,
        category_id: int,
        code: str,
        *,
        exclude_attribute_id: int | None = None,
    ) -> None:
        for descendant_id in self._repo.descendant_ids(category_id, include_self=True):
            for attr in self._repo.get_effective_attributes(descendant_id):
                if attr.id == exclude_attribute_id:
                    continue
                if attr.code == code:
                    raise InvalidAttributeError(f"код {code} уже есть в цепочке наследования")

    def _normalize_value_mode(self, type: str, value_mode: str | None) -> str:
        mode = value_mode or "single"
        if mode not in ATTRIBUTE_VALUE_MODES:
            raise InvalidAttributeError(f"режим значения {mode} не поддерживается")
        if type not in {"file", "image"}:
            return "single"
        return mode

    def _assert_category_slug_available(
        self,
        slug: str,
        *,
        exclude_category_id: int | None = None,
    ) -> None:
        existing = self._repo.get_category_by_slug(slug)
        if existing is not None and existing.id != exclude_category_id:
            raise InvalidCategoryTreeError(f"slug {slug} уже используется")
