#!/usr/bin/env python3
"""One-off helper: copy data from a legacy SQLite shop.db into MySQL.

Usage:
    1. Create the MySQL database, user, and grants.
    2. Apply migrations:  python scripts/db_apply.py
    3. Copy data:         python scripts/migrate_sqlite_to_mysql.py path/to/shop.db

Only copies known tables. Skips _yoyo_migration. Uses TRUNCATE before
inserting so this script is idempotent.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import get_database_url, parse_url

TABLES_IN_ORDER = (
    "admins",
    "settings",
    "storage_settings",
    "tags",
    "categories",
    "category_attributes",
    "attribute_options",
    "products",
    "product_tags",
    "product_attribute_values",
    "product_images",
    "orders",
)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2

    sqlite_path = Path(sys.argv[1]).resolve()
    if not sqlite_path.is_file():
        print(f"SQLite file not found: {sqlite_path}", file=sys.stderr)
        return 2

    try:
        import pymysql
    except ImportError:
        print("PyMySQL is not installed. Run `pip install pymysql`.", file=sys.stderr)
        return 2

    creds = parse_url(get_database_url())
    mysql_conn = pymysql.connect(
        host=creds["host"],
        port=int(creds["port"]),
        user=creds["user"],
        password=creds["password"],
        database=creds["database"],
        charset="utf8mb4",
        autocommit=False,
    )
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        with mysql_conn.cursor() as cur:
            cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            for table in TABLES_IN_ORDER:
                rows = sqlite_conn.execute(f"SELECT * FROM {table}").fetchall()
                if not rows:
                    print(f"[skip] {table}: empty")
                    continue
                columns = rows[0].keys()
                placeholders = ", ".join(["%s"] * len(columns))
                col_list = ", ".join(f"`{c}`" for c in columns)
                cur.execute(f"TRUNCATE TABLE `{table}`")
                cur.executemany(
                    f"INSERT INTO `{table}` ({col_list}) VALUES ({placeholders})",
                    [tuple(r) for r in rows],
                )
                print(f"[ok]   {table}: {len(rows)} row(s)")
            cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        mysql_conn.commit()
        print("Data migration complete.")
        return 0
    except Exception:
        mysql_conn.rollback()
        raise
    finally:
        sqlite_conn.close()
        mysql_conn.close()


if __name__ == "__main__":
    sys.exit(main())
