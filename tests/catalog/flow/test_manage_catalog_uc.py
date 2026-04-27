from datetime import datetime
from typing import Any

import pytest

from catalog.app.use_cases.manage_catalog_uc import ManageCatalogUseCase
from catalog.domain import (
    AttributeOption,
    CategoryAttribute,
    InvalidAttributeError,
    InvalidProductError,
    Product,
    ProductAttributeValue,
    Tag,
)


def _tag(tag_id: int, title: str) -> Tag:
    return Tag(
        id=tag_id,
        title=title,
        slug=title.lower(),
        color="#ffffff",
        sort_order=tag_id,
        is_active=True,
    )


def _attribute(
    attribute_id: int,
    code: str,
    title: str,
    *,
    type: str = "text",
    is_required: bool = False,
    value_mode: str = "single",
    options: list[AttributeOption] | None = None,
) -> CategoryAttribute:
    return CategoryAttribute(
        id=attribute_id,
        category_id=10,
        code=code,
        title=title,
        type=type,
        unit=None,
        is_required=is_required,
        is_filterable=True,
        is_public=True,
        sort_order=attribute_id,
        value_mode=value_mode,
        options=options or [],
    )


def _option(option_id: int, attribute_id: int, value: str) -> AttributeOption:
    return AttributeOption(
        id=option_id,
        attribute_id=attribute_id,
        value=value,
        label=value.title(),
        sort_order=option_id,
    )


def _attribute_value(attribute_id: int, code: str, value: Any) -> ProductAttributeValue:
    return ProductAttributeValue(
        attribute_id=attribute_id,
        code=code,
        title=code.title(),
        type="text",
        value=value,
    )


def _product(
    product_id: int,
    *,
    title: str = "Product",
    images: list[str] | None = None,
    tags: list[Tag] | None = None,
    attributes: list[ProductAttributeValue] | None = None,
    category_id: int | None = 10,
) -> Product:
    return Product(
        id=product_id,
        title=title,
        price=100.0,
        description="Catalog product",
        is_active=True,
        created_at=datetime(2024, 1, 1),
        images=list(images or []),
        category_id=category_id,
        tags=list(tags or []),
        attributes=list(attributes or []),
    )


class FakeProductRepo:
    def __init__(
        self,
        products: dict[int, Product] | None = None,
        events: list[tuple[str, Any]] | None = None,
    ) -> None:
        self.products = products or {}
        self.events = events
        self.created_products: list[Product] = []
        self.updated_products: list[Product] = []
        self.deleted_ids: list[int] = []

    def get_by_id(self, product_id: int) -> Product | None:
        return self.products.get(product_id)

    def create(self, product: Product) -> Product:
        product.id = 100 + len(self.created_products)
        self.created_products.append(product)
        self.products[product.id] = product
        return product

    def update(self, product: Product) -> Product:
        self.updated_products.append(product)
        self.products[product.id] = product
        return product

    def delete(self, product_id: int) -> bool:
        self.deleted_ids.append(product_id)
        if self.events is not None:
            self.events.append(("repo.delete", product_id))
        return self.products.pop(product_id, None) is not None

    def get_paginated(self, params):
        raise NotImplementedError

    def search(self, query, params):
        raise NotImplementedError

    def get_random(self, limit):
        raise NotImplementedError

    def swap_ids(self, id_a: int, id_b: int) -> None:
        raise NotImplementedError


class FakeFileStorage:
    def __init__(self, events: list[tuple[str, Any]] | None = None) -> None:
        self.events = events
        self.saved: list[tuple[str, bytes]] = []
        self.deleted: list[str] = []

    def save(self, filename: str, data: bytes) -> str:
        self.saved.append((filename, data))
        return f"stored/{filename}"

    def delete(self, file_path: str) -> bool:
        self.deleted.append(file_path)
        if self.events is not None:
            self.events.append(("storage.delete", file_path))
        return True


class FakeTaxonomyRepo:
    def __init__(
        self,
        *,
        tags: dict[int, Tag] | None = None,
        leaf_categories: set[int] | None = None,
        attributes_by_category: dict[int, list[CategoryAttribute]] | None = None,
    ) -> None:
        self.tags = tags or {}
        self.leaf_categories = leaf_categories or set()
        self.attributes_by_category = attributes_by_category or {}
        self.tag_lookups: list[int] = []
        self.leaf_checks: list[int] = []
        self.attribute_lookups: list[int] = []

    def get_tag(self, tag_id: int) -> Tag | None:
        self.tag_lookups.append(tag_id)
        return self.tags.get(tag_id)

    def is_leaf_category(self, category_id: int) -> bool:
        self.leaf_checks.append(category_id)
        return category_id in self.leaf_categories

    def get_effective_attributes(self, category_id: int) -> list[CategoryAttribute]:
        self.attribute_lookups.append(category_id)
        return self.attributes_by_category.get(category_id, [])


@pytest.mark.flow
class TestManageCatalogCreate:
    def test_create_saves_images_loads_tags_builds_attributes_and_persists_product(self):
        """
        Given images, valid tags, and attribute values for a leaf category,
        When creating a catalog product,
        Then the use case stores images, attaches taxonomy data, and persists the product.
        """
        # Arrange
        color = _attribute(
            2,
            "color",
            "Color",
            type="select",
            options=[_option(1, 2, "red"), _option(2, 2, "blue")],
        )
        weight = _attribute(1, "weight", "Weight", type="number", is_required=True)
        tags = {1: _tag(1, "New"), 2: _tag(2, "Sale")}
        repo = FakeProductRepo()
        storage = FakeFileStorage()
        taxonomy_repo = FakeTaxonomyRepo(
            tags=tags,
            leaf_categories={10},
            attributes_by_category={10: [weight, color]},
        )
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=storage,
            _taxonomy_repo=taxonomy_repo,
        )

        # Act
        product = use_case.create(
            title="Trail Shoes",
            price=129.99,
            description="Light trail shoes",
            images=[("front.jpg", b"front"), ("side.jpg", b"side")],
            category_id=10,
            tag_ids=[1, 2],
            attribute_values={"weight": "2.5", "color": "red"},
        )

        # Assert
        assert storage.saved == [("front.jpg", b"front"), ("side.jpg", b"side")]
        assert repo.created_products == [product]
        assert product.images == ["stored/front.jpg", "stored/side.jpg"]
        assert product.tags == [tags[1], tags[2]]
        assert taxonomy_repo.tag_lookups == [1, 2]
        assert taxonomy_repo.leaf_checks == [10]
        assert taxonomy_repo.attribute_lookups == [10]
        attributes = {attribute.code: attribute for attribute in product.attributes}
        assert attributes["weight"].value == 2.5
        assert attributes["color"].value == "red"

    def test_create_rejects_non_leaf_category(self):
        """
        Given a category that is not a leaf,
        When creating a product in that category,
        Then the use case rejects the product before persistence.
        """
        # Arrange
        repo = FakeProductRepo()
        storage = FakeFileStorage()
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=storage,
            _taxonomy_repo=FakeTaxonomyRepo(leaf_categories=set()),
        )

        # Act
        with pytest.raises(InvalidProductError) as exc_info:
            use_case.create(
                title="Parent Category Product",
                price=10.0,
                description="Invalid category",
                images=[("orphan.jpg", b"orphan")],
                category_id=10,
            )

        # Assert
        assert exc_info.value.code == "INVALID_PRODUCT"
        assert repo.created_products == []
        assert storage.saved == []

    def test_create_rejects_missing_required_attribute(self):
        """
        Given a leaf category with a required attribute,
        When creating a product without that attribute value,
        Then the use case raises an invalid-attribute error.
        """
        # Arrange
        repo = FakeProductRepo()
        taxonomy_repo = FakeTaxonomyRepo(
            leaf_categories={10},
            attributes_by_category={
                10: [_attribute(1, "weight", "Weight", is_required=True)]
            },
        )
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=FakeFileStorage(),
            _taxonomy_repo=taxonomy_repo,
        )

        # Act
        with pytest.raises(InvalidAttributeError) as exc_info:
            use_case.create(
                title="Missing Weight",
                price=10.0,
                description="Missing required attribute",
                images=[],
                category_id=10,
                attribute_values={},
            )

        # Assert
        assert exc_info.value.code == "INVALID_ATTRIBUTE"
        assert repo.created_products == []

    def test_required_date_attribute_can_use_product_creation_date_default(self):
        """
        Given a category has a required date attribute,
        When creating a product without an explicit date value,
        Then the use case allows creation and leaves the stored value absent for UI fallback.
        """
        # Arrange
        repo = FakeProductRepo()
        taxonomy_repo = FakeTaxonomyRepo(
            leaf_categories={10},
            attributes_by_category={
                10: [_attribute(1, "release_date", "Release date", type="date", is_required=True)]
            },
        )
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=FakeFileStorage(),
            _taxonomy_repo=taxonomy_repo,
        )

        # Act
        product = use_case.create(
            title="Launch Product",
            price=10.0,
            description="Uses created_at fallback",
            images=[],
            category_id=10,
            attribute_values={},
        )

        # Assert
        assert repo.created_products == [product]
        assert product.attributes == []

    def test_file_and_image_attributes_respect_value_mode(self):
        """
        Given file/image attributes use single or multiple value modes,
        When product attribute values are built,
        Then single values stay strings and multiple values become lists.
        """
        # Arrange
        repo = FakeProductRepo()
        taxonomy_repo = FakeTaxonomyRepo(
            leaf_categories={10},
            attributes_by_category={
                10: [
                    _attribute(1, "manual", "Manual", type="file", value_mode="single"),
                    _attribute(2, "gallery", "Gallery", type="image", value_mode="multiple"),
                ]
            },
        )
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=FakeFileStorage(),
            _taxonomy_repo=taxonomy_repo,
        )

        # Act
        product = use_case.create(
            title="Media Product",
            price=10.0,
            description="Has media attrs",
            images=[],
            category_id=10,
            attribute_values={
                "manual": "/files/manual.pdf",
                "gallery": ["/img/1.jpg", "/img/2.jpg"],
            },
        )

        # Assert
        attrs = {attribute.code: attribute.value for attribute in product.attributes}
        assert attrs["manual"] == "/files/manual.pdf"
        assert attrs["gallery"] == ["/img/1.jpg", "/img/2.jpg"]

    def test_create_rejects_invalid_tag(self):
        """
        Given a tag id absent from taxonomy,
        When creating a product with that tag id,
        Then the use case raises an invalid-product error.
        """
        # Arrange
        repo = FakeProductRepo()
        taxonomy_repo = FakeTaxonomyRepo(tags={})
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=FakeFileStorage(),
            _taxonomy_repo=taxonomy_repo,
        )

        # Act
        with pytest.raises(InvalidProductError) as exc_info:
            use_case.create(
                title="Unknown Tag Product",
                price=10.0,
                description="Invalid tag",
                images=[],
                tag_ids=[999],
            )

        # Assert
        assert exc_info.value.code == "INVALID_PRODUCT"
        assert taxonomy_repo.tag_lookups == [999]
        assert repo.created_products == []


@pytest.mark.flow
class TestManageCatalogUpdate:
    def test_title_only_update_preserves_tags_attributes_and_images(self):
        """
        Given an existing product with tags, attributes, and images,
        When updating only the title,
        Then the use case preserves the existing associations and image list.
        """
        # Arrange
        original_tags = [_tag(1, "New")]
        original_attributes = [_attribute_value(1, "weight", "2kg")]
        original_images = ["stored/front.jpg", "stored/side.jpg"]
        product = _product(
            7,
            title="Old Title",
            images=original_images,
            tags=original_tags,
            attributes=original_attributes,
        )
        repo = FakeProductRepo({7: product})
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=FakeFileStorage(),
            _taxonomy_repo=FakeTaxonomyRepo(),
        )

        # Act
        updated = use_case.update(7, title="New Title")

        # Assert
        assert updated is product
        assert repo.updated_products == [product]
        assert product.title == "New Title"
        assert product.images == original_images
        assert product.tags == original_tags
        assert product.attributes == original_attributes

    def test_explicit_empty_tag_ids_clears_tags(self):
        """
        Given an existing product with tags,
        When updating with an explicit empty tag list,
        Then the use case clears the product tags.
        """
        # Arrange
        product = _product(7, tags=[_tag(1, "New")])
        repo = FakeProductRepo({7: product})
        taxonomy_repo = FakeTaxonomyRepo()
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=FakeFileStorage(),
            _taxonomy_repo=taxonomy_repo,
        )

        # Act
        updated = use_case.update(7, tag_ids=[])

        # Assert
        assert updated is product
        assert repo.updated_products == [product]
        assert product.tags == []
        assert taxonomy_repo.tag_lookups == []

    def test_category_update_rejects_non_leaf_category_before_persisting(self):
        """
        Given an existing product and a category that is not a leaf,
        When updating the product category to that non-leaf category,
        Then the use case rejects the update before file side effects or persistence.
        """
        # Arrange
        product = _product(7, category_id=10, images=["stored/old.jpg"])
        repo = FakeProductRepo({7: product})
        storage = FakeFileStorage()
        taxonomy_repo = FakeTaxonomyRepo(leaf_categories={10})
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=storage,
            _taxonomy_repo=taxonomy_repo,
        )

        # Act
        with pytest.raises(InvalidProductError) as exc_info:
            use_case.update(
                7,
                category_id=99,
                new_images=[("new.jpg", b"new")],
                deleted_images=["stored/old.jpg"],
            )

        # Assert
        assert exc_info.value.code == "INVALID_PRODUCT"
        assert product.category_id == 10
        assert product.images == ["stored/old.jpg"]
        assert taxonomy_repo.leaf_checks == [99]
        assert storage.saved == []
        assert storage.deleted == []
        assert repo.updated_products == []


@pytest.mark.flow
class TestManageCatalogDelete:
    def test_delete_removes_stored_images_before_deleting_product(self):
        """
        Given an existing product with stored images,
        When deleting the product,
        Then the use case deletes stored images before deleting the product record.
        """
        # Arrange
        events: list[tuple[str, Any]] = []
        product = _product(7, images=["stored/front.jpg", "stored/side.jpg"])
        repo = FakeProductRepo({7: product}, events=events)
        use_case = ManageCatalogUseCase(
            _repo=repo,
            _storage=FakeFileStorage(events=events),
            _taxonomy_repo=FakeTaxonomyRepo(),
        )

        # Act
        deleted = use_case.delete(7)

        # Assert
        assert deleted is True
        assert events == [
            ("storage.delete", "stored/front.jpg"),
            ("storage.delete", "stored/side.jpg"),
            ("repo.delete", 7),
        ]
        assert repo.deleted_ids == [7]
