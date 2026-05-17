from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import select

from access.adapters.driven.db.models import UserModel
from shared.adapters.driven.db.connection import create_db_engine
from shared.helpers.security import hash_password
from system.adapters.driven.db.models import SettingsModel


pytestmark = pytest.mark.flow


def _login(client, login: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"login": login, "password": password},
    )
    assert response.status_code == 200
    return response.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_runtime_app_identity_and_owner_catalog_access_apply_without_restart(
    monkeypatch,
    tmp_path,
):
    """
    Given an owner token created before settings are changed,
    When superadmin enables catalog edit access and changes app identity in settings,
    Then owner catalog access and rendered app identity update without restarting Flask.

    Phase-1 note: dual-user bootstrap was removed. The superadmin user is the
    bootstrapped user (superadmin/superadmin). A separate owner-role user
    (admin/changeme) is inserted via direct DB write after app creation.
    """
    # Arrange
    db_path = tmp_path / "shop.db"
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    monkeypatch.setenv("ACCESS_DEFAULT_LOGIN", "superadmin")
    monkeypatch.setenv("ACCESS_DEFAULT_PASSWORD", "superadmin")
    monkeypatch.setenv("ACCESS_PROMOTE_TO_SUPERADMIN", "true")
    monkeypatch.setenv("ACCESS_OWNER_CAN_VIEW_CATEGORY_TREE", "false")
    monkeypatch.setenv("ACCESS_OWNER_CAN_VIEW_PRODUCTS", "false")
    monkeypatch.setenv("ACCESS_OWNER_CAN_EDIT_PRODUCTS", "false")

    from sqlalchemy.orm import Session
    from root.entrypoints.api import create_app

    app = create_app()

    # Insert a second owner-role user directly so we can test two distinct actors.
    engine = create_db_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        owner_user = UserModel(
            login="admin",
            password_hash=hash_password("changeme"),
            role="owner",
            is_active=True,
            password_changed_at=None,
        )
        session.add(owner_user)
        session.commit()

    client = app.test_client()
    owner_token = _login(client, "admin", "changeme")
    superadmin_token = _login(client, "superadmin", "superadmin")

    # Act
    response = client.put(
        "/admin/settings/store",
        headers=_auth(superadmin_token),
        data={
            "app_name": "Runtime Shop",
            "admin_panel_title": "Runtime Admin",
            "coords_lat": "53.9",
            "coords_lon": "27.56",
            "owner_can_edit_products": "on",
        },
    )
    settings_page = client.get(
        "/admin/settings/store",
        headers=_auth(superadmin_token),
    )
    catalog_page = client.get("/admin/catalog/", headers=_auth(owner_token))

    # Assert
    assert response.status_code == 200
    assert settings_page.status_code == 200
    assert "Runtime Shop" in settings_page.get_data(as_text=True)
    assert "Runtime Admin" in settings_page.get_data(as_text=True)
    assert catalog_page.status_code == 200


def test_default_dev_superadmin_cannot_download_sqlite_database_dump(monkeypatch, tmp_path):
    """
    Given the application uses SQLite,
    When the default dev superadmin has not changed the bootstrap password,
    Then the database dump is blocked.
    """
    # Arrange
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    monkeypatch.setenv("ACCESS_DEFAULT_LOGIN", "superadmin")
    monkeypatch.setenv("ACCESS_DEFAULT_PASSWORD", "superadmin")
    monkeypatch.setenv("ACCESS_PROMOTE_TO_SUPERADMIN", "true")

    from root.entrypoints.api import create_app

    app = create_app()
    client = app.test_client()
    superadmin_token = _login(client, "superadmin", "superadmin")

    response = client.get(
        "/admin/settings/database-dump",
        headers=_auth(superadmin_token),
    )

    assert response.status_code == 403


def test_superadmin_can_download_latest_database_dump_after_password_change(monkeypatch, tmp_path):
    """
    Given superadmin changed the bootstrap password AND a MySQL dump
    file exists in data/dumps/,
    When superadmin requests a database dump,
    Then the newest dump file is returned as a no-store attachment.

    The endpoint no longer dumps live — scripts/db_dump.py runs out
    of process (cron on CPanel, manual on a workstation) and writes
    into data/dumps/.
    """
    import os
    from pathlib import Path

    # Place a dump in the CWD-relative data/dumps/ — same location the
    # endpoint reads from.
    dumps_dir = Path(os.getcwd()) / "data" / "dumps"
    dumps_dir.mkdir(parents=True, exist_ok=True)
    dump_file = dumps_dir / "shop-test-20260515-120000.sql.gz"
    dump_file.write_bytes(b"\x1f\x8b\x08\x00fake gzip payload")

    try:
        monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
        monkeypatch.setenv("ROOT_APP_ENV", "dev")
        monkeypatch.setenv("ACCESS_DEFAULT_LOGIN", "superadmin")
        monkeypatch.setenv("ACCESS_DEFAULT_PASSWORD", "superadmin")
        monkeypatch.setenv("ACCESS_PROMOTE_TO_SUPERADMIN", "true")

        from root.entrypoints.api import create_app

        app = create_app()
        client = app.test_client()
        superadmin_token = _login(client, "superadmin", "superadmin")
        change_response = client.put(
            "/admin/settings/password",
            headers=_auth(superadmin_token),
            data={"old_password": "superadmin", "new_password": "changed-password"},
        )
        assert change_response.status_code == 200

        response = client.get(
            "/admin/settings/database-dump",
            headers=_auth(superadmin_token),
        )

        assert response.status_code == 200
        assert response.data.startswith(b"\x1f\x8b")  # gzip magic
        assert response.headers["Cache-Control"] == "no-store"
        assert "attachment;" in response.headers["Content-Disposition"]
        assert "shop-" in response.headers["Content-Disposition"]
    finally:
        dump_file.unlink(missing_ok=True)


def test_database_dump_returns_clear_error_when_no_dumps_available(monkeypatch, tmp_path):
    """
    Given no dumps in data/dumps/,
    When superadmin requests a database dump,
    Then the endpoint returns 400 with a guidance message,
    instead of returning a stale or fabricated file.
    """
    import os
    import shutil
    from pathlib import Path

    dumps_dir = Path(os.getcwd()) / "data" / "dumps"
    # Snapshot existing dumps, clear the dir, restore at the end.
    backup = tmp_path / "dumps_backup"
    if dumps_dir.exists():
        shutil.move(str(dumps_dir), str(backup))
    dumps_dir.mkdir(parents=True, exist_ok=True)

    try:
        monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
        monkeypatch.setenv("ROOT_APP_ENV", "dev")
        monkeypatch.setenv("ACCESS_DEFAULT_LOGIN", "superadmin")
        monkeypatch.setenv("ACCESS_DEFAULT_PASSWORD", "superadmin")
        monkeypatch.setenv("ACCESS_PROMOTE_TO_SUPERADMIN", "true")

        from root.entrypoints.api import create_app

        app = create_app()
        client = app.test_client()
        superadmin_token = _login(client, "superadmin", "superadmin")
        client.put(
            "/admin/settings/password",
            headers=_auth(superadmin_token),
            data={"old_password": "superadmin", "new_password": "changed-password"},
        )

        response = client.get(
            "/admin/settings/database-dump",
            headers=_auth(superadmin_token),
        )

        assert response.status_code == 400
        assert "scripts/db_dump.py" in response.get_json()["message"]
    finally:
        # Restore prior dumps if any.
        shutil.rmtree(dumps_dir, ignore_errors=True)
        if backup.exists():
            shutil.move(str(backup), str(dumps_dir))


def test_owner_and_unauthenticated_users_cannot_download_sqlite_database_dump(monkeypatch, tmp_path):
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

    from root.entrypoints.api import create_app

    app = create_app()
    client = app.test_client()
    owner_token = _login(client, "admin", "changeme")

    owner_response = client.get(
        "/admin/settings/database-dump",
        headers=_auth(owner_token),
    )
    unauthenticated_response = client.get("/admin/settings/database-dump")

    assert owner_response.status_code == 403
    assert unauthenticated_response.status_code in {302, 401}


def test_owner_account_telegram_update_does_not_change_global_settings(monkeypatch, tmp_path):
    db_path = tmp_path / "shop.db"
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

    from sqlalchemy.orm import Session
    from root.entrypoints.api import create_app

    app = create_app()
    client = app.test_client()
    owner_token = _login(client, "admin", "changeme")

    engine = create_db_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        settings = session.execute(
            select(SettingsModel).where(SettingsModel.id == 1)
        ).scalar_one()
        settings.telegram_chat_id = "legacy-global"
        session.commit()

    response = client.put(
        "/admin/settings/security/telegram-chat",
        headers=_auth(owner_token),
        data={"telegram_chat_id": "owner-chat"},
    )

    with Session(engine) as session:
        owner = session.execute(
            select(UserModel).where(UserModel.login == "admin")
        ).scalar_one()
        settings = session.execute(
            select(SettingsModel).where(SettingsModel.id == 1)
        ).scalar_one()

    assert response.status_code == 200
    assert owner.telegram_chat_id == "owner-chat"
    assert settings.telegram_chat_id == "legacy-global"


# Removed: test_legacy_sqlite_superadmin_non_default_password_is_marked_changed
# It exercised SQLite-as-production schema evolution at app boot. The
# project switched to MySQL + yoyo-migrations; legacy schemas are
# upgraded through migration files now, not by boot-time DDL.
