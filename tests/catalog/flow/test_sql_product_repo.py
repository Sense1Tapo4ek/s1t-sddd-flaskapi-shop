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


@pytest.fixture
def fts_product_repo():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(engine, expire_on_commit=False)

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE VIRTUAL TABLE products_fts USING fts5(
                title, description,
                content='products', content_rowid='id'
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TRIGGER products_fts_insert
            AFTER INSERT ON products BEGIN
                INSERT INTO products_fts(rowid, title, description)
                VALUES (new.id, new.title, new.description);
            END
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TRIGGER products_fts_delete
            AFTER DELETE ON products BEGIN
                INSERT INTO products_fts(products_fts, rowid, title, description)
                VALUES ('delete', old.id, old.title, old.description);
            END
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TRIGGER products_fts_update
            AFTER UPDATE ON products BEGIN
                INSERT INTO products_fts(products_fts, rowid, title, description)
                VALUES ('delete', old.id, old.title, old.description);
                INSERT INTO products_fts(rowid, title, description)
                VALUES (new.id, new.title, new.description);
            END
            """
        )

    with session_factory() as session:
        session.add_all(
            [
                ProductModel(
                    title="Apple iPhone 14",
                    price=999,
                    description="Latest flagship smartphone from Apple",
                ),
                ProductModel(
                    title="Samsung Galaxy S23",
                    price=899,
                    description="Android flagship with great camera",
                ),
                ProductModel(
                    title="Apple Watch Series 8",
                    price=399,
                    description="Smart watch for fitness and health",
                ),
                ProductModel(
                    title="Sony Headphones",
                    price=199,
                    description="Noise cancelling headphones for music",
                ),
            ]
        )
        session.commit()

    return SqlProductRepo(_session_factory=session_factory)


def test_fts_search_returns_ranked_results(fts_product_repo):
    """
    Given products have title/description indexed by FTS5,
    When searching with a query term,
    Then only matching products are returned sorted by relevance.
    """
    result = fts_product_repo.search(
        "apple",
        PaginationParams(page=1, limit=10),
    )

    assert result.total == 2
    titles = [p.title for p in result.items]
    assert "Apple iPhone 14" in titles
    assert "Apple Watch Series 8" in titles


def test_fts_search_with_custom_sort(fts_product_repo):
    """
    Given FTS search results,
    When an explicit sort_by is provided,
    Then results are filtered by FTS but ordered by the requested column.
    """
    result = fts_product_repo.search(
        "apple",
        PaginationParams(page=1, limit=10, sort_by="price", sort_dir="desc"),
    )

    assert result.total == 2
    assert [p.title for p in result.items] == [
        "Apple iPhone 14",
        "Apple Watch Series 8",
    ]


def test_fts_search_pagination(fts_product_repo):
    """
    Given FTS search returns multiple results,
    When paginating,
    Then correct page slices are returned.
    """
    result = fts_product_repo.search(
        "apple",
        PaginationParams(page=1, limit=1),
    )

    assert result.total == 2
    assert len(result.items) == 1


def test_fts_index_syncs_on_update(fts_product_repo):
    """
    Given a product is updated,
    When the FTS index is synced via triggers,
    Then searching by the new description finds the updated product.
    """
    with fts_product_repo._session_factory() as session:
        product = session.get(ProductModel, 3)  # Apple Watch Series 8
        product.description = "Rugged smart watch for extreme sports"
        session.commit()

    result = fts_product_repo.search(
        "extreme",
        PaginationParams(page=1, limit=10),
    )

    assert result.total == 1
    assert result.items[0].title == "Apple Watch Series 8"
