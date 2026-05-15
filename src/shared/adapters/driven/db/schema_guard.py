"""Pre-flight check that yoyo migrations have been applied.

The Flask app never issues DDL. Schema is owned by `migrations/*.sql`.
On startup we verify the canonical tables exist; if not, we raise with
a clear message pointing the operator at the migration runner.
"""

from sqlalchemy import inspect
from sqlalchemy.engine import Engine


REQUIRED_TABLES: tuple[str, ...] = (
    "admins",
    "settings",
    "storage_settings",
    "categories",
    "products",
    "orders",
    "_yoyo_migration",
)


class SchemaNotReadyError(RuntimeError):
    """Raised when expected tables are missing — migrations not applied."""


def ensure_schema_present(engine: Engine) -> None:
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
