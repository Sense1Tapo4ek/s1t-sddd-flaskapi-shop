#!/usr/bin/env python3
"""Roll back the most recently applied yoyo migration.

Usage:
    python scripts/db_rollback.py

Requires a matching `*.rollback.sql` sibling for the migration. If the
migration is forward-only, yoyo exits with a clear error.
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
        print("yoyo-migrations is not installed.", file=sys.stderr)
        return 2

    backend = get_backend(get_yoyo_url(), migration_table="_yoyo_migration")
    migrations = read_migrations(str(MIGRATIONS_DIR))
    rollback_candidates = list(backend.to_rollback(migrations))

    if not rollback_candidates:
        print("Nothing to roll back.")
        return 0

    last = rollback_candidates[-1]
    print(f"Rolling back: {last.id}")
    with backend.lock():
        backend.rollback_one(last)
    print("Rolled back.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
