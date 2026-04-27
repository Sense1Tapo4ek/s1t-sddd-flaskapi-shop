from typing import Any, Protocol, runtime_checkable

from catalog.domain import Category, CategoryAttribute, Tag


@runtime_checkable
class ITaxonomyRepo(Protocol):
    def list_categories(self, *, include_inactive: bool = True) -> list[Category]: ...

    def get_category(self, category_id: int) -> Category | None: ...

    def get_category_by_slug(self, slug: str) -> Category | None: ...

    def create_category(
        self,
        *,
        parent_id: int | None,
        title: str,
        slug: str,
        description: str,
        sort_order: int,
        is_active: bool,
    ) -> Category: ...

    def update_category(self, category_id: int, **kwargs: Any) -> Category: ...

    def delete_category(self, category_id: int) -> None: ...

    def category_has_children(self, category_id: int) -> bool: ...

    def category_has_products(self, category_id: int) -> bool: ...

    def is_leaf_category(self, category_id: int) -> bool: ...

    def descendant_ids(self, category_id: int, *, include_self: bool = True) -> list[int]: ...

    def list_tags(self, *, include_inactive: bool = True) -> list[Tag]: ...

    def get_tag(self, tag_id: int) -> Tag | None: ...

    def create_tag(
        self,
        *,
        title: str,
        slug: str,
        color: str,
        sort_order: int,
        is_active: bool,
    ) -> Tag: ...

    def update_tag(self, tag_id: int, **kwargs: Any) -> Tag: ...

    def delete_tag(self, tag_id: int) -> None: ...

    def get_effective_attributes(self, category_id: int) -> list[CategoryAttribute]: ...
    def get_attribute(self, attribute_id: int) -> CategoryAttribute | None: ...

    def create_attribute(
        self,
        *,
        category_id: int,
        code: str,
        title: str,
        type: str,
        unit: str | None,
        is_required: bool,
        is_filterable: bool,
        is_public: bool,
        value_mode: str,
        sort_order: int,
        options: list[dict[str, Any]],
    ) -> CategoryAttribute: ...

    def update_attribute(self, attribute_id: int, **kwargs: Any) -> CategoryAttribute: ...

    def delete_attribute(self, attribute_id: int) -> None: ...
