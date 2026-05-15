#!/usr/bin/env python3
"""Apply all pending yoyo migrations to the configured database.

Usage:
    python scripts/db_apply.py

Reads INFRA_DATABASE_URL from environment (loads .env if present).
Exits non-zero on failure. Safe to run repeatedly — yoyo skips applied
migrations.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import MIGRATIONS_DIR, get_yoyo_url


def main() -> int:
    try:
        from yoyo import get_backend, read_migrations
    except ImportError:
        print(
            "yoyo-migrations is not installed. Run `pip install -r requirements.txt`.",
            file=sys.stderr,
        )
        return 2

    backend = get_backend(get_yoyo_url(), migration_table="_yoyo_migration")
    migrations = read_migrations(str(MIGRATIONS_DIR))
    pending = list(backend.to_apply(migrations))

    if not pending:
        print("No pending migrations. Database is up to date.")
        return 0

    print(f"Applying {len(pending)} migration(s):")
    for m in pending:
        print(f"  -> {m.id}")

    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
