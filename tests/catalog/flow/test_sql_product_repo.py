from __future__ import annotations

from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from catalog.adapters.driven.db.models import (
    CategoryAttributeModel,
    CategoryModel,
    ProductAttributeValueModel,
    ProductModel,
    TagModel,
)
from catalog.ports.driven.sql_product_repo import SqlProductRepo
from shared.adapters.driven import Base
from shared.generics.pagination import PaginationParams


pytestmark = pytest.mark.flow


@pytest.fixture
def product_repo():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)

    with session_factory() as session:
        accessories = CategoryModel(title="Accessories", slug="accessories")
        boots = CategoryModel(title="Boots", slug="boots")
        sale = TagModel(title="Sale", slug="sale", sort_order=1)
        new = TagModel(title="New", slug="new", sort_order=2)
        session.add_all(
            [
                ProductModel(
                    title="Boot product",
                    price=20,
                    description="",
                    category=boots,
                    tags=[sale],
                ),
                ProductModel(
                    title="Accessory product",
                    price=10,
                    description="",
                    category=accessories,
                    tags=[new],
                ),
            ]
        )
        session.commit()

    return SqlProductRepo(_session_factory=session_factory)


@pytest.fixture
def nested_category_product_repo():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)

    with session_factory() as session:
        alpha = CategoryModel(title="Alpha", slug="alpha")
        zulu = CategoryModel(title="Zulu", slug="zulu")
        alpha_leaf = CategoryModel(title="Adapters", slug="alpha-adapters", parent=alpha)
        zulu_leaf = CategoryModel(title="Adapters", slug="zulu-adapters", parent=zulu)
        session.add_all(
            [
                ProductModel(
                    title="Zulu adapter",
                    price=20,
                    description="",
                    category=zulu_leaf,
                ),
                ProductModel(
                    title="Alpha adapter",
                    price=10,
                    description="",
                    category=alpha_leaf,
                ),
            ]
        )
        session.commit()

    return SqlProductRepo(_session_factory=session_factory)


@pytest.fixture
def attribute_product_repo():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)

    with session_factory() as session:
        category = CategoryModel(title="Boots", slug="boots")
        weight = CategoryAttributeModel(
            category=category,
            code="weight",
            title="Weight",
            type="number",
            unit="kg",
        )
        release_date = CategoryAttributeModel(
            category=category,
            code="release_date",
            title="Release date",
            type="date",
        )
        light = ProductModel(
            title="Light boot",
            price=10,
            description="",
            category=category,
            created_at=datetime(2024, 1, 2),
        )
        heavy = ProductModel(
            title="Heavy boot",
            price=20,
            description="",
            category=category,
            created_at=datetime(2024, 1, 1),
        )
        session.add_all([category, weight, release_date, light, heavy])
        session.flush()
        session.add_all(
            [
                ProductAttributeValueModel(
                    product=light,
                    attribute=weight,
                    value_number=1.2,
                ),
                ProductAttributeValueModel(
                    product=heavy,
                    attribute=weight,
                    value_number=2.4,
                ),
                ProductAttributeValueModel(
                    product=heavy,
                    attribute=release_date,
                    value_text="2024-01-03",
                ),
            ]
        )
        session.commit()

    return SqlProductRepo(_session_factory=session_factory)


def test_admin_search_sorts_products_by_category_title(product_repo):
    """
    Given products belong to different categories,
    When admin search sorts by the visible category column,
    Then rows are ordered by category title instead of ignoring the sort key.
    """
    # Act
    result = product_repo.search(
        "",
        PaginationParams(sort_by="category", sort_dir="asc"),
    )

    # Assert
    assert [product.title for product in result.items] == [
        "Accessory product",
        "Boot product",
    ]


def test_admin_search_sorts_products_by_visible_category_path(nested_category_product_repo):
    """
    Given products have categories with the same leaf title under different parents,
    When admin search sorts by the category column,
    Then rows follow the visible category path order.
    """
    # Act
    result = nested_category_product_repo.search(
        "",
        PaginationParams(sort_by="category", sort_dir="asc"),
    )

    # Assert
    assert [product.title for product in result.items] == [
        "Alpha adapter",
        "Zulu adapter",
    ]


def test_admin_search_sorts_products_by_first_tag_title(product_repo):
    """
    Given products have tags,
    When admin search sorts by the visible tags column,
    Then rows are ordered by their first tag title in a deterministic way.
    """
    # Act
    result = product_repo.search(
        "",
        PaginationParams(sort_by="tags", sort_dir="desc"),
    )

    # Assert
    assert [product.title for product in result.items] == [
        "Boot product",
        "Accessory product",
    ]


def test_admin_search_sorts_and_filters_by_attribute_columns(attribute_product_repo):
    """
    Given products have typed category attribute values,
    When admin search uses attr.<code> sort and filter keys,
    Then SQL applies the typed attribute value columns.
    """
    # Act
    sorted_result = attribute_product_repo.search(
        "",
        PaginationParams(sort_by="attr.weight", sort_dir="desc"),
    )
    filtered_result = attribute_product_repo.search(
        "",
        PaginationParams(filters={"attr.weight__gte": "2"}),
    )
    date_sorted = attribute_product_repo.search(
        "",
        PaginationParams(sort_by="attr.release_date", sort_dir="asc"),
    )

    # Assert
    assert [product.title for product in sorted_result.items] == [
        "Heavy boot",
        "Light boot",
    ]
    assert [product.title for product in filtered_result.items] == ["Heavy boot"]
    assert [product.title for product in date_sorted.items] == [
        "Light boot",
        "Heavy boot",
    ]
