"""Pre-flight check that yoyo migrations have been applied.

The Flask app never issues DDL on the production backend (MySQL 5.7+).
Schema is owned by ``migrations/*.sql``. On startup we verify the
canonical tables exist; if not, we raise with a clear message pointing
the operator at the migration runner.

Tests bypass yoyo via the ``INFRA_TEST_AUTO_SCHEMA=1`` escape hatch:
when set, the guard issues ``Base.metadata.create_all`` against the
engine. This is the ONLY supported way to short-circuit migrations,
and is intended exclusively for the pytest harness.
"""

import os

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


REQUIRED_TABLES: tuple[str, ...] = (
    "admins",
    "customers",
    "settings",
    "storage_settings",
    "categories",
    "products",
    "orders",
    "_yoyo_migration",
)


class SchemaNotReadyError(RuntimeError):
    """Raised when expected tables are missing — migrations not applied."""


def _auto_schema_requested() -> bool:
    return os.environ.get("INFRA_TEST_AUTO_SCHEMA", "").lower() in ("1", "true", "yes", "on")


def ensure_schema_present(engine: Engine) -> None:
    if _auto_schema_requested():
        # Test-only escape hatch: skip migration-applied check and
        # build the schema from SQLAlchemy metadata directly. Never
        # enable in production — DDL ownership belongs to yoyo.
        from shared.adapters.driven import Base

        Base.metadata.create_all(engine)
        return

    inspector = inspect(engine)
    existing = set(inspector.get_table_names())
    missing = [t for t in REQUIRED_TABLES if t not in existing]
    if not missing:
        return
    raise SchemaNotReadyError(
        "Database schema is not ready. Missing tables: "
        f"{', '.join(missing)}. "
        "Run `python scripts/db_apply.py` (or `yoyo apply` directly) "
        "to apply pending migrations before starting the app."
    )
