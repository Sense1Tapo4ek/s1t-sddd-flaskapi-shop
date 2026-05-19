"""Top-level test fixtures.

The project uses MySQL exclusively, including in tests. The
``mysql_test_db`` fixture provisions a clean, isolated MySQL database
per test by:

1. Connecting to the running ``mysql:5.7`` container at ``localhost:3306``
   with the ``root`` user (the only user with CREATE/DROP DATABASE
   privileges).
2. Creating a fresh database named ``test_<uuid hex>``.
3. Setting ``INFRA_DATABASE_URL`` to point the app at that database
   (still using the ``shop``-equivalent connection — root is reused so
   the connection works regardless of which DB exists).
4. Setting ``INFRA_TEST_AUTO_SCHEMA=1`` so ``ensure_schema_present`` runs
   ``Base.metadata.create_all`` instead of expecting yoyo migrations.
5. Dropping the database on teardown.

The fixture is function-scoped: each test gets a fresh schema, so tests
remain self-isolated without shared state.
"""
from __future__ import annotations

import uuid
from typing import Iterator

import pymysql
import pytest


_MYSQL_HOST = "127.0.0.1"
_MYSQL_PORT = 3306
# Use root for DDL — the ``shop`` user only has rights on the ``shop`` DB.
_MYSQL_ADMIN_USER = "root"
_MYSQL_ADMIN_PASSWORD = "root"


def _server_connection() -> pymysql.connections.Connection:
    return pymysql.connect(
        host=_MYSQL_HOST,
        port=_MYSQL_PORT,
        user=_MYSQL_ADMIN_USER,
        password=_MYSQL_ADMIN_PASSWORD,
        autocommit=True,
    )


def _build_url(db_name: str) -> str:
    return (
        f"mysql+pymysql://{_MYSQL_ADMIN_USER}:{_MYSQL_ADMIN_PASSWORD}"
        f"@{_MYSQL_HOST}:{_MYSQL_PORT}/{db_name}?charset=utf8mb4"
    )


@pytest.fixture
def mysql_test_db(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    """Provision a per-test MySQL database, yield its SQLAlchemy URL.

    Sets ``INFRA_DATABASE_URL`` and ``INFRA_TEST_AUTO_SCHEMA`` so the
    Flask app factory picks up the isolated database with auto-created
    schema.
    """
    db_name = f"test_{uuid.uuid4().hex[:16]}"
    conn = _server_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE `{db_name}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
    finally:
        conn.close()

    url = _build_url(db_name)
    monkeypatch.setenv("INFRA_DATABASE_URL", url)
    monkeypatch.setenv("INFRA_TEST_AUTO_SCHEMA", "1")

    try:
        yield url
    finally:
        # Tear down the per-test DB; ignore errors so a failed test
        # cannot mask the original failure.
        try:
            conn = _server_connection()
            with conn.cursor() as cur:
                cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            conn.close()
        except Exception:
            pass
