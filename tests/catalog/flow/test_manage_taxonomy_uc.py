from __future__ import annotations

from typing import Any

import pytest

from catalog.app.use_cases.manage_taxonomy_uc import ManageTaxonomyUseCase
from catalog.domain import (
    ATTRIBUTE_TYPES,
    AttributeNotFoundError,
    Category,
    CategoryAttribute,
    CategoryNotFoundError,
    InvalidAttributeError,
    InvalidCategoryTreeError,
    Tag,
)


def _category(
    category_id: int,
    *,
    parent_id: int | None,
    title: str,
    slug: str | None = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> Category:
    return Category(
        id=category_id,
        parent_id=parent_id,
        title=title,
        slug=slug or title.lower().replace(" ", "-"),
        description="",
        sort_order=sort_order,
        is_active=is_active,
    )


def _attribute(
    attribute_id: int,
    *,
    category_id: int,
    code: str,
    title: str | None = None,
    type: str = "text",
    sort_order: int = 0,
    value_mode: str = "single",
) -> CategoryAttribute:
    return CategoryAttribute(
        id=attribute_id,
        category_id=category_id,
        code=code,
        title=title or code.title(),
        type=type,
        unit=None,
        is_required=False,
        is_filterable=True,
        is_public=True,
        sort_order=sort_order,
        value_mode=value_mode,
    )


class FakeTaxonomyRepo:
    def __init__(
        self,
        *,
        categories: list[Category] | None = None,
        attributes: list[CategoryAttribute] | None = None,
        category_product_counts: dict[int, int] | None = None,
    ) -> None:
        self.categories = {category.id: category for category in categories or []}
        self.attributes = {attribute.id: attribute for attribute in attributes or []}
        self.category_product_counts = category_product_counts or {}
        self.created_category_payloads: list[dict[str, Any]] = []
        self.updated_category_payloads: list[tuple[int, dict[str, Any]]] = []
        self.deleted_category_ids: list[int] = []
        self.created_attribute_payloads: list[dict[str, Any]] = []
        self.updated_attribute_payloads: list[tuple[int, dict[str, Any]]] = []
        self.deleted_attribute_ids: list[int] = []
        self.attribute_update_lookup_errors: set[int] = set()
        self.attribute_delete_lookup_errors: set[int] = set()
        self._next_category_id = max(self.categories, default=0) + 1
        self._next_attribute_id = max(self.attributes, default=0) + 1

    def list_categories(self, *, include_inactive: bool = True) -> list[Category]:
        return [
            category
            for category in self.categories.values()
            if include_inactive or category.is_active
        ]

    def get_category(self, category_id: int) -> Category | None:
        return self.categories.get(category_id)

    def get_category_by_slug(self, slug: str) -> Category | None:
        return next(
            (
                category
                for category in self.categories.values()
                if category.slug == slug
            ),
            None,
        )

    def create_category(
        self,
        *,
        parent_id: int | None,
        title: str,
        slug: str,
        description: str,
        sort_order: int,
        is_active: bool,
    ) -> Category:
        self.created_category_payloads.append(
            {
                "parent_id": parent_id,
                "title": title,
                "slug": slug,
                "description": description,
                "sort_order": sort_order,
                "is_active": is_active,
            }
        )
        category = Category(
            id=self._next_category_id,
            parent_id=parent_id,
            title=title,
            slug=slug,
            description=description,
            sort_order=sort_order,
            is_active=is_active,
        )
        self._next_category_id += 1
        self.categories[category.id] = category
        return category

    def update_category(self, category_id: int, **kwargs: Any) -> Category:
        category = self.categories.get(category_id)
        if category is None:
            raise LookupError(category_id)
        self.updated_category_payloads.append((category_id, dict(kwargs)))
        for field, value in kwargs.items():
            setattr(category, field, value)
        return category

    def delete_category(self, category_id: int) -> None:
        if category_id not in self.categories:
            raise LookupError(category_id)
        self.deleted_category_ids.append(category_id)
        del self.categories[category_id]

    def category_has_children(self, category_id: int) -> bool:
        return any(
            category.parent_id == category_id for category in self.categories.values()
        )

    def category_has_products(self, category_id: int) -> bool:
        return self.category_product_counts.get(category_id, 0) > 0

    def is_leaf_category(self, category_id: int) -> bool:
        return not self.category_has_children(category_id)

    def descendant_ids(self, category_id: int, *, include_self: bool = True) -> list[int]:
        result = [category_id] if include_self else []
        stack = [
            category.id
            for category in self.categories.values()
            if category.parent_id == category_id
        ]
        while stack:
            current_id = stack.pop(0)
            result.append(current_id)
            stack.extend(
                category.id
                for category in self.categories.values()
                if category.parent_id == current_id
            )
        return result

    def list_tags(self, *, include_inactive: bool = True) -> list[Tag]:
        return []

    def get_tag(self, tag_id: int) -> Tag | None:
        return None

    def create_tag(
        self,
        *,
        title: str,
        slug: str,
        color: str,
        sort_order: int,
        is_active: bool,
    ) -> Tag:
        raise NotImplementedError

    def update_tag(self, tag_id: int, **kwargs: Any) -> Tag:
        raise NotImplementedError

    def delete_tag(self, tag_id: int) -> None:
        raise NotImplementedError

    def get_effective_attributes(self, category_id: int) -> list[CategoryAttribute]:
        chain: list[Category] = []
        current = self.categories.get(category_id)
        seen: set[int] = set()
        while current is not None and current.id not in seen:
            chain.append(current)
            seen.add(current.id)
            current = (
                self.categories.get(current.parent_id)
                if current.parent_id is not None
                else None
            )
        chain.reverse()

        effective: list[CategoryAttribute] = []
        for category in chain:
            effective.extend(
                sorted(
                    (
                        attribute
                        for attribute in self.attributes.values()
                        if attribute.category_id == category.id
                    ),
                    key=lambda attribute: (attribute.sort_order, attribute.title.lower()),
                )
            )
        return effective

    def get_attribute(self, attribute_id: int) -> CategoryAttribute | None:
        return self.attributes.get(attribute_id)

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
    ) -> CategoryAttribute:
        self.created_attribute_payloads.append(
            {
                "category_id": category_id,
                "code": code,
                "title": title,
                "type": type,
                "unit": unit,
                "is_required": is_required,
                "is_filterable": is_filterable,
                "is_public": is_public,
                "value_mode": value_mode,
                "sort_order": sort_order,
                "options": options,
            }
        )
        attribute = CategoryAttribute(
            id=self._next_attribute_id,
            category_id=category_id,
            code=code,
            title=title,
            type=type,
            unit=unit,
            is_required=is_required,
            is_filterable=is_filterable,
            is_public=is_public,
            sort_order=sort_order,
            value_mode=value_mode,
            options=[],
        )
        self._next_attribute_id += 1
        self.attributes[attribute.id] = attribute
        return attribute

    def update_attribute(self, attribute_id: int, **kwargs: Any) -> CategoryAttribute:
        attribute = self.attributes.get(attribute_id)
        if attribute is None or attribute_id in self.attribute_update_lookup_errors:
            raise LookupError(attribute_id)
        self.updated_attribute_payloads.append((attribute_id, dict(kwargs)))
        for field, value in kwargs.items():
            setattr(attribute, field, value)
        return attribute

    def delete_attribute(self, attribute_id: int) -> None:
        if (
            attribute_id not in self.attributes
            or attribute_id in self.attribute_delete_lookup_errors
        ):
            raise LookupError(attribute_id)
        self.deleted_attribute_ids.append(attribute_id)
        del self.attributes[attribute_id]


@pytest.mark.flow
class TestManageTaxonomyUseCase:
    def test_list_category_tree_sorts_roots_resets_children_and_promotes_orphans(self):
        """
        Given unordered categories with stale children and an orphaned parent reference,
        When listing the category tree,
        Then roots are sorted, children are rebuilt, and missing-parent categories are roots.
        """
        # Arrange
        root_b = _category(1, parent_id=None, title="Root B", sort_order=20)
        child_b = _category(2, parent_id=1, title="Child B", sort_order=0)
        orphan = _category(3, parent_id=404, title="Orphan", sort_order=5)
        root_a = _category(4, parent_id=None, title="Root A", sort_order=10)
        child_a = _category(5, parent_id=4, title="Child A", sort_order=0)
        root_b.children = [_category(99, parent_id=1, title="Stale")]
        child_b.children = [_category(100, parent_id=2, title="Stale grandchild")]
        repo = FakeTaxonomyRepo(
            categories=[root_b, child_b, orphan, root_a, child_a],
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act
        tree = uc.list_category_tree()

        # Assert
        assert [category.id for category in tree] == [3, 4, 1]
        assert [category.id for category in tree[1].children] == [5]
        assert [category.id for category in tree[2].children] == [2]
        assert tree[2].children[0].children == []

    def test_create_category_rejects_missing_parent(self):
        """
        Given a create category request with an unknown parent,
        When creating the category,
        Then the use case rejects it before persisting anything.
        """
        # Arrange
        repo = FakeTaxonomyRepo(categories=[_category(1, parent_id=None, title="Root")])
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(CategoryNotFoundError):
            uc.create_category(parent_id=404, title="Ghost")

        # Assert
        assert repo.created_category_payloads == []

    def test_create_category_slugifies_explicit_and_default_slugs(self):
        """
        Given category titles with whitespace and an explicit display slug,
        When creating categories,
        Then explicit and title-derived slugs are normalized before persistence.
        """
        # Arrange
        repo = FakeTaxonomyRepo(categories=[_category(1, parent_id=None, title="Root")])
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act
        explicit = uc.create_category(
            parent_id=1,
            title="  Camera Bags  ",
            slug="  Pro & Travel Bags! ",
        )
        default = uc.create_category(parent_id=None, title="Mirrorless Cameras")

        # Assert
        assert explicit.slug == "pro-travel-bags"
        assert explicit.title == "Camera Bags"
        assert default.slug == "mirrorless-cameras"

    def test_create_category_rejects_duplicate_slug(self):
        """
        Given an existing category with a normalized slug,
        When creating another category with the same normalized slug,
        Then the use case rejects the duplicate before persistence.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[_category(1, parent_id=None, title="Root", slug="pro-bags")]
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(InvalidCategoryTreeError):
            uc.create_category(parent_id=None, title="Pro Bags")

        # Assert
        assert repo.created_category_payloads == []

    def test_update_category_rejects_self_parent(self):
        """
        Given an existing category,
        When it is updated to use itself as parent,
        Then the use case rejects the invalid tree mutation.
        """
        # Arrange
        repo = FakeTaxonomyRepo(categories=[_category(1, parent_id=None, title="Root")])
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(InvalidCategoryTreeError):
            uc.update_category(1, parent_id=1)

        # Assert
        assert repo.updated_category_payloads == []

    def test_update_category_rejects_duplicate_slug(self):
        """
        Given two existing categories,
        When one category is updated to another category's normalized slug,
        Then the use case rejects the duplicate before persistence.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[
                _category(1, parent_id=None, title="Root", slug="root"),
                _category(2, parent_id=None, title="Sale", slug="sale"),
            ],
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(InvalidCategoryTreeError):
            uc.update_category(1, slug="Sale")

        # Assert
        assert repo.updated_category_payloads == []

    def test_update_category_rejects_move_into_descendant(self):
        """
        Given a category with nested descendants,
        When it is moved below one of its descendants,
        Then the use case rejects the cycle-forming parent change.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[
                _category(1, parent_id=None, title="Root"),
                _category(2, parent_id=1, title="Child"),
                _category(3, parent_id=2, title="Grandchild"),
            ],
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(InvalidCategoryTreeError):
            uc.update_category(1, parent_id=3)

        # Assert
        assert repo.updated_category_payloads == []

    def test_delete_category_rejects_category_with_children(self):
        """
        Given a category that still has a child category,
        When deleting the parent category,
        Then the use case rejects the deletion.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[
                _category(1, parent_id=None, title="Root"),
                _category(2, parent_id=1, title="Child"),
            ],
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(InvalidCategoryTreeError):
            uc.delete_category(1)

        # Assert
        assert 1 in repo.categories
        assert repo.deleted_category_ids == []

    def test_delete_category_rejects_category_with_products(self):
        """
        Given a leaf category with attached products,
        When deleting the category,
        Then the use case rejects the deletion.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[_category(1, parent_id=None, title="Root")],
            category_product_counts={1: 2},
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(InvalidCategoryTreeError):
            uc.delete_category(1)

        # Assert
        assert 1 in repo.categories
        assert repo.deleted_category_ids == []

    def test_delete_category_deletes_leaf_without_products(self):
        """
        Given a leaf category with no attached products,
        When deleting the category,
        Then the use case removes it from the repository.
        """
        # Arrange
        repo = FakeTaxonomyRepo(categories=[_category(1, parent_id=None, title="Root")])
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act
        uc.delete_category(1)

        # Assert
        assert 1 not in repo.categories
        assert repo.deleted_category_ids == [1]

    def test_create_attribute_rejects_unsupported_type(self):
        """
        Given an existing category and an unsupported attribute type,
        When creating the category attribute,
        Then the use case rejects the attribute before persistence.
        """
        # Arrange
        repo = FakeTaxonomyRepo(categories=[_category(1, parent_id=None, title="Root")])
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(InvalidAttributeError):
            uc.create_attribute(
                category_id=1,
                code="metadata",
                title="Metadata",
                type="json",
            )

        # Assert
        assert repo.created_attribute_payloads == []

    def test_color_is_not_a_supported_attribute_type(self):
        """
        Given the simplified attribute model,
        When checking supported types or creating a color attribute,
        Then color is rejected before persistence.
        """
        # Arrange
        repo = FakeTaxonomyRepo(categories=[_category(1, parent_id=None, title="Root")])
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        assert "color" not in ATTRIBUTE_TYPES
        with pytest.raises(InvalidAttributeError):
            uc.create_attribute(
                category_id=1,
                code="paint",
                title="Paint",
                type="color",
            )

        # Assert
        assert repo.created_attribute_payloads == []

    def test_create_attribute_forces_visibility_and_validates_value_mode(self):
        """
        Given callers still send old filterable/public flags,
        When creating file or image attributes,
        Then the use case stores public/filterable as true and validates multiplicity.
        """
        # Arrange
        repo = FakeTaxonomyRepo(categories=[_category(1, parent_id=None, title="Root")])
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act
        created = uc.create_attribute(
            category_id=1,
            code="manual",
            title="Manual",
            type="file",
            is_filterable=False,
            is_public=False,
            value_mode="multiple",
        )

        # Assert
        assert created.is_filterable is True
        assert created.is_public is True
        assert created.value_mode == "multiple"
        assert repo.created_attribute_payloads[-1]["is_filterable"] is True
        assert repo.created_attribute_payloads[-1]["is_public"] is True
        assert repo.created_attribute_payloads[-1]["value_mode"] == "multiple"

        # Act / Assert
        with pytest.raises(InvalidAttributeError):
            uc.create_attribute(
                category_id=1,
                code="gallery",
                title="Gallery",
                type="image",
                value_mode="many",
            )

    def test_update_attribute_forces_visibility_and_validates_value_mode(self):
        """
        Given an existing file attribute,
        When updating legacy visibility flags and multiplicity,
        Then visibility remains true and invalid modes are rejected.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[_category(1, parent_id=None, title="Root")],
            attributes=[
                _attribute(
                    10,
                    category_id=1,
                    code="manual",
                    title="Manual",
                    type="file",
                )
            ],
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act
        updated = uc.update_attribute(
            10,
            is_filterable=False,
            is_public=False,
            value_mode="multiple",
        )

        # Assert
        assert updated.is_filterable is True
        assert updated.is_public is True
        assert updated.value_mode == "multiple"
        assert repo.updated_attribute_payloads[-1] == (
            10,
            {"is_filterable": True, "is_public": True, "value_mode": "multiple"},
        )

        # Act / Assert
        with pytest.raises(InvalidAttributeError):
            uc.update_attribute(10, value_mode="gallery")

    def test_create_attribute_rejects_duplicate_effective_code_across_chain(self):
        """
        Given attributes already defined on an ancestor and a descendant category,
        When creating attributes with the same effective codes,
        Then the use case rejects duplicates across inheritance and descendants.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[
                _category(1, parent_id=None, title="Root"),
                _category(2, parent_id=1, title="Child"),
            ],
            attributes=[
                _attribute(10, category_id=1, code="size", title="Size"),
                _attribute(11, category_id=2, code="material", title="Material"),
            ],
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(InvalidAttributeError):
            uc.create_attribute(
                category_id=2,
                code="Size",
                title="Override size",
                type="text",
            )
        with pytest.raises(InvalidAttributeError):
            uc.create_attribute(
                category_id=1,
                code="Material",
                title="Root material",
                type="text",
            )

        # Assert
        assert repo.created_attribute_payloads == []

    def test_update_attribute_rejects_duplicate_code_but_excludes_itself(self):
        """
        Given two attributes in the same effective category chain,
        When updating one attribute code to itself and then to another attribute code,
        Then self matches are ignored and real duplicates are rejected.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[_category(1, parent_id=None, title="Root")],
            attributes=[
                _attribute(10, category_id=1, code="size", title="Size"),
                _attribute(11, category_id=1, code="color", title="Color"),
            ],
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act
        updated = uc.update_attribute(11, code="Color")

        # Assert
        assert updated.code == "color"

        # Act / Assert
        with pytest.raises(InvalidAttributeError):
            uc.update_attribute(11, code="Size")

    def test_update_attribute_normalizes_code(self):
        """
        Given an existing category attribute and a display-style code,
        When updating the attribute code,
        Then the use case stores the normalized code.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[_category(1, parent_id=None, title="Root")],
            attributes=[_attribute(10, category_id=1, code="width", title="Width")],
        )
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act
        updated = uc.update_attribute(10, code="Display Width")

        # Assert
        assert updated.code == "display_width"
        assert repo.updated_attribute_payloads == [(10, {"code": "display_width"})]

    def test_update_and_delete_missing_attribute_map_to_attribute_not_found(self):
        """
        Given missing attributes represented by None or repository LookupError,
        When updating or deleting those attributes,
        Then the use case raises AttributeNotFoundError.
        """
        # Arrange
        repo = FakeTaxonomyRepo(
            categories=[_category(1, parent_id=None, title="Root")],
            attributes=[_attribute(10, category_id=1, code="width", title="Width")],
        )
        repo.attribute_update_lookup_errors.add(10)
        repo.attribute_delete_lookup_errors.add(10)
        uc = ManageTaxonomyUseCase(_repo=repo)

        # Act / Assert
        with pytest.raises(AttributeNotFoundError):
            uc.update_attribute(404, title="Ghost")
        with pytest.raises(AttributeNotFoundError):
            uc.update_attribute(10, title="Lost during update")
        with pytest.raises(AttributeNotFoundError):
            uc.delete_attribute(10)
