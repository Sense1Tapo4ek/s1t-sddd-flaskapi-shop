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
    """
    # Arrange
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    monkeypatch.setenv("ACCESS_OWNER_CAN_VIEW_CATEGORY_TREE", "false")
    monkeypatch.setenv("ACCESS_OWNER_CAN_VIEW_PRODUCTS", "false")
    monkeypatch.setenv("ACCESS_OWNER_CAN_EDIT_PRODUCTS", "false")

    from root.entrypoints.api import create_app

    app = create_app()
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

    from root.entrypoints.api import create_app

    app = create_app()
    client = app.test_client()
    superadmin_token = _login(client, "superadmin", "superadmin")

    response = client.get(
        "/admin/settings/database-dump",
        headers=_auth(superadmin_token),
    )

    assert response.status_code == 403


def test_superadmin_can_download_sqlite_database_dump_after_password_change(monkeypatch, tmp_path):
    """
    Given superadmin changed the bootstrap password,
    When superadmin requests a database dump,
    Then the current database file is returned as a no-store downloadable attachment.
    """
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

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
    assert response.data.startswith(b"SQLite format 3")
    assert response.headers["Cache-Control"] == "no-store"
    assert "attachment;" in response.headers["Content-Disposition"]
    assert "shop-" in response.headers["Content-Disposition"]
    assert ".sqlite" in response.headers["Content-Disposition"]


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


def test_legacy_sqlite_superadmin_non_default_password_is_marked_changed(monkeypatch, tmp_path):
    db_path = tmp_path / "legacy.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                login VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                recovery_code_hash VARCHAR(255),
                recovery_code_expires DATETIME
            )
            """
        )
        conn.execute(
            "INSERT INTO admins (login, password_hash) VALUES (?, ?)",
            ("superadmin", hash_password("already-changed")),
        )
        conn.commit()

    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

    from sqlalchemy.orm import Session
    from root.entrypoints.api import create_app

    create_app()

    engine = create_db_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        superadmin = session.execute(
            select(UserModel).where(UserModel.login == "superadmin")
        ).scalar_one()

    assert superadmin.password_changed_at is not None
