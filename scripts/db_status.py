#!/usr/bin/env python3
"""Show applied vs pending yoyo migrations.

Usage:
    python scripts/db_status.py
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

    applied_ids = {m.id for m in backend.to_rollback(migrations)}
    pending = list(backend.to_apply(migrations))

    print(f"Migrations folder: {MIGRATIONS_DIR}")
    print(f"Applied: {len(applied_ids)}")
    for m in migrations:
        if m.id in applied_ids:
            print(f"  [x] {m.id}")
    print(f"Pending: {len(pending)}")
    for m in pending:
        print(f"  [ ] {m.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
