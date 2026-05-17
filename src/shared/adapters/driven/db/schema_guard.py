"""Pre-flight check that yoyo migrations have been applied.

The Flask app never issues DDL on the production backend (MySQL).
Schema is owned by ``migrations/*.sql``. On startup we verify the
canonical tables exist; if not, we raise with a clear message pointing
the operator at the migration runner.

SQLite is a TEST-ONLY backend (in-memory or temp file in pytest).
Production never points at SQLite. We treat a SQLite engine as an
implicit test environment and auto-create the schema from SQLAlchemy
metadata — running yoyo against SQLite would fail anyway because the
migration SQL is MySQL-specific (utf8mb4, FULLTEXT, etc.).
"""

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


def _is_sqlite(engine: Engine) -> bool:
    return engine.dialect.name == "sqlite"


def ensure_schema_present(engine: Engine) -> None:
    if _is_sqlite(engine):
        # Test backend. Production never uses SQLite, so this branch
        # never runs in prod. Tests get a fresh schema for every
        # fixture without needing to wire yoyo against an
        # incompatible dialect.
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
