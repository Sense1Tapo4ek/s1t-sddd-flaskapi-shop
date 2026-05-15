"""Shared helpers for scripts/db_*.py.

Loads .env at the project root, surfaces INFRA_DATABASE_URL, exposes a
parsed creds dict, and a yoyo-friendly URL.

yoyo-migrations registers `mysql` (MySQLdb) and `mysql+mysqldb` but NOT
`mysql+pymysql` (SQLAlchemy's convention). We make PyMySQL impersonate
MySQLdb so yoyo's plain `mysql://` backend can drive the migrations
without `libmysqlclient` / mysqlclient build deps — the whole point of
choosing PyMySQL on CPanel.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Final

try:
    import pymysql  # type: ignore[import-not-found]

    pymysql.install_as_MySQLdb()
except ImportError:
    # PyMySQL isn't installed in some script contexts (e.g. unit tests).
    # yoyo will fail later with a clearer message if MySQL is actually used.
    pass

PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR: Final[Path] = PROJECT_ROOT / "migrations"
DUMPS_DIR: Final[Path] = PROJECT_ROOT / "data" / "dumps"


def load_dotenv() -> None:
    """Best-effort .env loader (no python-dotenv dependency in scripts)."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def get_database_url() -> str:
    load_dotenv()
    url = os.environ.get("INFRA_DATABASE_URL")
    if not url:
        print(
            "INFRA_DATABASE_URL is not set. Copy .env.example to .env and "
            "fill in MySQL credentials, or export the variable.",
            file=sys.stderr,
        )
        sys.exit(2)
    return url


def get_yoyo_url() -> str:
    """Same URL but with the scheme yoyo's backend list understands.

    SQLAlchemy uses `mysql+pymysql://...`. yoyo registers `mysql` and
    `mysql+mysqldb`. After `pymysql.install_as_MySQLdb()` at import
    time, yoyo's `mysql://` backend can drive PyMySQL transparently.
    """
    url = get_database_url()
    if url.startswith("mysql+pymysql://"):
        return "mysql://" + url[len("mysql+pymysql://"):]
    return url


def parse_url(database_url: str) -> dict[str, str]:
    """Parse mysql+pymysql://user:pass@host:3306/db?charset=utf8mb4."""
    from urllib.parse import urlsplit, unquote

    parts = urlsplit(database_url)
    if not parts.scheme.startswith("mysql"):
        print(
            f"Expected a MySQL URL, got '{parts.scheme}://...'. "
            "Update INFRA_DATABASE_URL.",
            file=sys.stderr,
        )
        sys.exit(2)
    db = parts.path.lstrip("/")
    return {
        "host": parts.hostname or "localhost",
        "port": str(parts.port or 3306),
        "user": unquote(parts.username or ""),
        "password": unquote(parts.password or ""),
        "database": db,
    }


def ensure_dumps_dir() -> Path:
    DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    return DUMPS_DIR
