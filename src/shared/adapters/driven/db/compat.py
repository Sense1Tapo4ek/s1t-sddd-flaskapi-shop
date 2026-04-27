from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _column_exists(conn, table_name: str, column_name: str) -> bool:
    columns = conn.exec_driver_sql(f"PRAGMA table_info({table_name})").all()
    return any(column[1] == column_name for column in columns)


def ensure_sqlite_compatibility(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return
    _ensure_access_schema(engine)
    _ensure_system_schema(engine)
    _ensure_catalog_schema(engine)


def _ensure_access_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        if not _column_exists(conn, "admins", "role"):
            conn.exec_driver_sql(
                "ALTER TABLE admins ADD COLUMN role VARCHAR(30) NOT NULL DEFAULT 'owner'"
            )
        if not _column_exists(conn, "admins", "telegram_chat_id"):
            conn.exec_driver_sql(
                "ALTER TABLE admins ADD COLUMN telegram_chat_id VARCHAR(100)"
            )
        if not _column_exists(conn, "admins", "is_active"):
            conn.exec_driver_sql(
                "ALTER TABLE admins ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
            )
        if not _column_exists(conn, "admins", "password_changed_at"):
            conn.exec_driver_sql(
                "ALTER TABLE admins ADD COLUMN password_changed_at DATETIME"
            )
        if not _column_exists(conn, "admins", "recovery_code_attempts"):
            conn.exec_driver_sql(
                "ALTER TABLE admins ADD COLUMN recovery_code_attempts INTEGER NOT NULL DEFAULT 0"
            )
        if not _column_exists(conn, "admins", "recovery_code_last_sent_at"):
            conn.exec_driver_sql(
                "ALTER TABLE admins ADD COLUMN recovery_code_last_sent_at DATETIME"
            )
        if not _column_exists(conn, "admins", "recovery_code_locked_until"):
            conn.exec_driver_sql(
                "ALTER TABLE admins ADD COLUMN recovery_code_locked_until DATETIME"
            )
        conn.execute(text("UPDATE admins SET role = 'owner' WHERE role IS NULL OR role = ''"))
        conn.execute(text("UPDATE admins SET is_active = 1 WHERE is_active IS NULL"))
        conn.execute(
            text(
                "UPDATE admins SET recovery_code_attempts = 0 "
                "WHERE recovery_code_attempts IS NULL"
            )
        )


def _ensure_system_schema(engine: Engine) -> None:
    additions = [
        ("app_name", "VARCHAR(100) NOT NULL DEFAULT ''"),
        ("admin_panel_title", "VARCHAR(100) NOT NULL DEFAULT 'Админ панель'"),
        ("owner_can_view_category_tree", "BOOLEAN NOT NULL DEFAULT 1"),
        ("owner_can_edit_taxonomy", "BOOLEAN NOT NULL DEFAULT 0"),
        ("owner_can_view_products", "BOOLEAN NOT NULL DEFAULT 0"),
        ("owner_can_edit_products", "BOOLEAN NOT NULL DEFAULT 0"),
        ("owner_can_create_demo_data", "BOOLEAN NOT NULL DEFAULT 0"),
    ]

    with engine.begin() as conn:
        for column_name, ddl in additions:
            if not _column_exists(conn, "settings", column_name):
                conn.exec_driver_sql(
                    f"ALTER TABLE settings ADD COLUMN {column_name} {ddl}"
                )
        conn.execute(
            text(
                "UPDATE settings SET owner_can_view_category_tree = 1 "
                "WHERE owner_can_view_category_tree IS NULL"
            )
        )


def _ensure_catalog_schema(engine: Engine) -> None:
    with engine.begin() as conn:
        if not _column_exists(conn, "category_attributes", "value_mode"):
            conn.exec_driver_sql(
                "ALTER TABLE category_attributes "
                "ADD COLUMN value_mode VARCHAR(16) NOT NULL DEFAULT 'single'"
            )
        conn.execute(
            text(
                "UPDATE category_attributes "
                "SET value_mode = 'single' "
                "WHERE value_mode IS NULL OR value_mode = ''"
            )
        )
        conn.execute(
            text(
                "DELETE FROM product_attribute_values "
                "WHERE attribute_id IN ("
                "SELECT id FROM category_attributes WHERE type = 'color'"
                ")"
            )
        )
        conn.execute(
            text(
                "DELETE FROM attribute_options "
                "WHERE attribute_id IN ("
                "SELECT id FROM category_attributes WHERE type = 'color'"
                ")"
            )
        )
        conn.execute(text("DELETE FROM category_attributes WHERE type = 'color'"))
