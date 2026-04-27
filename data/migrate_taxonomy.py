"""
Idempotent SQLite migration/backfill for catalog taxonomy.

The application still uses SQLAlchemy ``create_all()`` instead of Alembic.
``create_all()`` creates new tables, but it does not alter an existing
``products`` table, so this script adds ``products.category_id`` and backfills
old rows into a default leaf category.

Usage:
    PYTHONPATH=src uv run data/migrate_taxonomy.py
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import inspect
from sqlalchemy.engine import Connection
from sqlalchemy.engine.url import make_url

sys.path.append(os.path.join(os.getcwd(), "src"))

# Import models so all catalog tables are registered on the shared Base.
import catalog.adapters.driven.db.models  # noqa: F401
from shared.adapters.driven.db.base import Base
from shared.adapters.driven.db.connection import create_db_engine


DEFAULT_DB_URL = "sqlite:///data/shop.db"

TAXONOMY_TABLES = {
    "categories",
    "tags",
    "product_tags",
    "category_attributes",
    "attribute_options",
    "product_attribute_values",
}

INDEXES = (
    ("idx_categories_parent_id", "categories", "parent_id"),
    ("idx_categories_active_sort", "categories", "is_active, sort_order"),
    ("idx_products_category_id", "products", "category_id"),
    ("idx_products_active_id", "products", "is_active, id"),
    ("idx_tags_active_sort", "tags", "is_active, sort_order"),
    ("idx_product_tags_tag_id", "product_tags", "tag_id"),
    ("idx_category_attributes_category_id", "category_attributes", "category_id"),
    (
        "idx_product_attribute_values_attribute_id",
        "product_attribute_values",
        "attribute_id",
    ),
    (
        "idx_product_attribute_values_text",
        "product_attribute_values",
        "attribute_id, value_text",
    ),
    (
        "idx_product_attribute_values_number",
        "product_attribute_values",
        "attribute_id, value_number",
    ),
    (
        "idx_product_attribute_values_bool",
        "product_attribute_values",
        "attribute_id, value_bool",
    ),
)


@dataclass(slots=True)
class MigrationResult:
    tables_created: list[str] = field(default_factory=list)
    category_column_added: bool = False
    attribute_value_mode_column_added: bool = False
    color_attributes_deleted: int = 0
    indexes_created: list[str] = field(default_factory=list)
    catalog_id: int | None = None
    uncategorized_id: int | None = None
    products_backfilled: int = 0


def _ensure_sqlite_parent_dir(db_url: str) -> None:
    url = make_url(db_url)
    database = url.database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)


def _table_names(conn: Connection) -> set[str]:
    rows = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type = 'table'"
    ).all()
    return {row[0] for row in rows}


def _index_exists(conn: Connection, index_name: str) -> bool:
    row = conn.exec_driver_sql(
        "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = ?",
        (index_name,),
    ).first()
    return row is not None


def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    columns = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").all()
    return any(column[1] == column_name for column in columns)


def _ensure_products_category_column(conn: Connection) -> bool:
    if _column_exists(conn, "products", "category_id"):
        return False

    conn.exec_driver_sql(
        "ALTER TABLE products "
        "ADD COLUMN category_id INTEGER "
        "REFERENCES categories(id) ON DELETE RESTRICT"
    )
    return True


def _ensure_attribute_value_mode_column(conn: Connection) -> bool:
    if _column_exists(conn, "category_attributes", "value_mode"):
        conn.exec_driver_sql(
            "UPDATE category_attributes "
            "SET value_mode = 'single' "
            "WHERE value_mode IS NULL OR value_mode = ''"
        )
        return False

    conn.exec_driver_sql(
        "ALTER TABLE category_attributes "
        "ADD COLUMN value_mode VARCHAR(16) NOT NULL DEFAULT 'single'"
    )
    return True


def _delete_color_attributes(conn: Connection) -> int:
    rows = conn.exec_driver_sql(
        "SELECT id FROM category_attributes WHERE type = 'color'"
    ).all()
    if not rows:
        return 0

    attribute_ids = [int(row[0]) for row in rows]
    placeholders = ", ".join("?" for _ in attribute_ids)
    conn.exec_driver_sql(
        f"DELETE FROM product_attribute_values WHERE attribute_id IN ({placeholders})",
        tuple(attribute_ids),
    )
    conn.exec_driver_sql(
        f"DELETE FROM attribute_options WHERE attribute_id IN ({placeholders})",
        tuple(attribute_ids),
    )
    conn.exec_driver_sql(
        f"DELETE FROM category_attributes WHERE id IN ({placeholders})",
        tuple(attribute_ids),
    )
    return len(attribute_ids)


def _ensure_indexes(conn: Connection) -> list[str]:
    created: list[str] = []
    for index_name, table_name, columns in INDEXES:
        if _index_exists(conn, index_name):
            continue
        conn.exec_driver_sql(
            f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({columns})"
        )
        created.append(index_name)
    return created


def _get_category_id(conn: Connection, slug: str) -> int | None:
    row = conn.exec_driver_sql(
        "SELECT id FROM categories WHERE slug = ?",
        (slug,),
    ).first()
    return int(row[0]) if row else None


def _ensure_category(
    conn: Connection,
    *,
    title: str,
    slug: str,
    parent_id: int | None,
    description: str,
    sort_order: int,
) -> int:
    existing_id = _get_category_id(conn, slug)
    if existing_id is not None:
        return existing_id

    conn.exec_driver_sql(
        """
        INSERT INTO categories
            (parent_id, title, slug, description, sort_order, is_active)
        VALUES
            (?, ?, ?, ?, ?, 1)
        """,
        (parent_id, title, slug, description, sort_order),
    )
    category_id = _get_category_id(conn, slug)
    if category_id is None:
        raise RuntimeError(f"Failed to create category '{slug}'")
    return category_id


def _ensure_default_categories(conn: Connection) -> tuple[int, int]:
    catalog_id = _ensure_category(
        conn,
        title="Catalog",
        slug="catalog",
        parent_id=None,
        description="Default catalog root.",
        sort_order=0,
    )
    uncategorized_id = _ensure_category(
        conn,
        title="Uncategorized",
        slug="uncategorized",
        parent_id=catalog_id,
        description="Fallback category for products migrated from the flat catalog.",
        sort_order=9999,
    )

    # Older manual runs may have created the fallback as a root. Move only the
    # default slug under the default root; leave all other categories untouched.
    conn.exec_driver_sql(
        """
        UPDATE categories
        SET parent_id = ?
        WHERE id = ? AND parent_id IS NULL
        """,
        (catalog_id, uncategorized_id),
    )
    return catalog_id, uncategorized_id


def _backfill_products(conn: Connection, category_id: int) -> int:
    result = conn.exec_driver_sql(
        "UPDATE products SET category_id = ? WHERE category_id IS NULL",
        (category_id,),
    )
    return max(result.rowcount or 0, 0)


def migrate(db_url: str | None = None, *, quiet: bool = False) -> MigrationResult:
    database_url = db_url or os.environ.get("INFRA_DATABASE_URL", DEFAULT_DB_URL)
    _ensure_sqlite_parent_dir(database_url)

    engine = create_db_engine(database_url)
    if engine.dialect.name != "sqlite":
        raise RuntimeError(
            "data/migrate_taxonomy.py is a SQLite migration script. "
            f"Current dialect: {engine.dialect.name}"
        )

    with engine.begin() as conn:
        before_tables = _table_names(conn)

    Base.metadata.create_all(engine)

    result = MigrationResult(
        tables_created=sorted(TAXONOMY_TABLES - before_tables),
    )

    with engine.begin() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys = ON")
        result.category_column_added = _ensure_products_category_column(conn)
        result.attribute_value_mode_column_added = _ensure_attribute_value_mode_column(conn)
        result.color_attributes_deleted = _delete_color_attributes(conn)
        result.indexes_created = _ensure_indexes(conn)
        result.catalog_id, result.uncategorized_id = _ensure_default_categories(conn)
        result.products_backfilled = _backfill_products(conn, result.uncategorized_id)

    if not quiet:
        print("Catalog taxonomy migration complete.")
        print(f"  tables created: {', '.join(result.tables_created) or 'none'}")
        print(
            "  products.category_id: "
            f"{'added' if result.category_column_added else 'already exists'}"
        )
        print(
            "  category_attributes.value_mode: "
            f"{'added' if result.attribute_value_mode_column_added else 'already exists'}"
        )
        print(f"  color attributes deleted: {result.color_attributes_deleted}")
        print(f"  indexes created: {', '.join(result.indexes_created) or 'none'}")
        print(f"  Catalog category id: {result.catalog_id}")
        print(f"  Uncategorized category id: {result.uncategorized_id}")
        print(f"  products backfilled: {result.products_backfilled}")

    inspect(engine).clear_cache()
    return result


if __name__ == "__main__":
    migrate()
