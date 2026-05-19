"""
E2E auth-gate tests for GET /admin/backups/.

DI wiring for the full facade (with real backup storage / runner) lands
in Stage 5, so the file-creation test is skipped for now.  The auth-gate
tests are self-contained: they stub SystemFacade via Dishka and only
exercise the route-level auth enforcement.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from apiflask import APIFlask
from dishka import make_container, Provider, Scope, provide
from dishka.integrations.flask import setup_dishka

from shared.adapters.driving.error_handlers import init_error_handlers
from shared.adapters.driving.middleware import init_middleware
from shared.helpers.security import create_jwt
from system.adapters.driving.admin import backups_admin_bp
from system.domain.snapshot_vo import SnapshotInfo
from system.ports.driving.facade import SystemFacade
from system.ports.driving.schemas import SnapshotListOut, SnapshotOut

pytestmark = pytest.mark.e2e

_SECRET = "test-secret-at-least-32-bytes-long-here"


def _snapshot_out() -> SnapshotOut:
    return SnapshotOut(
        name="2026-01-01T00-00-00.sql.gz",
        size_bytes=2048,
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        mig_version=2,
        is_pre_restore=False,
        display_name="2026-01-01T00-00-00",
    )


def _make_stub_provider() -> Provider:
    class StubProvider(Provider):
        scope = Scope.APP

        @provide
        def system_facade(self) -> SystemFacade:
            m = MagicMock(spec=SystemFacade)
            m.list_snapshots.return_value = SnapshotListOut(items=[_snapshot_out()])
            m.create_snapshot.return_value = _snapshot_out()
            m.restore_snapshot.return_value = None
            m.delete_snapshot.return_value = None
            return m

    return StubProvider()


def _make_app(provider: "Provider | None" = None) -> APIFlask:
    """Minimal APIFlask with only the backups blueprint, Dishka stub, and middleware."""
    from pathlib import Path
    from jinja2 import ChoiceLoader, FileSystemLoader
    from shared.adapters.driving.middleware import has_permission

    base_dir = Path(__file__).resolve().parents[3]
    app = APIFlask(
        __name__,
        template_folder=str(base_dir / "static" / "templates"),
    )
    app.jinja_loader = ChoiceLoader(
        [
            FileSystemLoader(str(base_dir / "static" / "templates" / "admin")),
            FileSystemLoader(str(base_dir / "src" / "system" / "templates")),
        ]
    )
    # Inject globals required by base.html
    app.jinja_env.globals["has_perm"] = has_permission
    app.jinja_env.globals["app_name"] = "TestShop"
    app.jinja_env.globals["admin_panel_title"] = "Тест"
    app.jinja_env.globals["feature_flags"] = type("FF", (), {"orders_enabled": False})()

    app.register_blueprint(backups_admin_bp)
    init_middleware(app, _SECRET)
    init_error_handlers(app)
    container = make_container(provider or _make_stub_provider())
    setup_dishka(container, app)
    return app


def _superadmin_token() -> str:
    return create_jwt(
        {"sub": 1, "account_type": "admin", "role": "superadmin", "permissions": []},
        _SECRET,
        expires_hours=1,
    )


def _owner_token() -> str:
    """Owner (not superadmin) — should receive 403."""
    return create_jwt(
        {"sub": 2, "account_type": "admin", "role": "owner", "permissions": ["manage_settings"]},
        _SECRET,
        expires_hours=1,
    )


class TestBackupsAdminAuthGates:
    def test_get_backups_without_auth_redirects_to_login(self):
        """
        Given no JWT,
        When GET /admin/backups/ is called,
        Then the error handler redirects to /admin/login (302)
        — the standard admin-page unauthenticated behaviour.
        """
        # Arrange
        app = _make_app()
        client = app.test_client()

        # Act
        response = client.get("/admin/backups/")

        # Assert — admin HTML paths redirect unauthenticated requests
        assert response.status_code == 302
        assert "/admin/login" in response.headers.get("Location", "")

    def test_get_backups_with_owner_jwt_returns_403(self):
        """
        Given an owner-role JWT (not superadmin),
        When GET /admin/backups/ is called,
        Then 403 is returned (backups are superadmin-only).
        """
        # Arrange
        app = _make_app()
        client = app.test_client()
        token = _owner_token()

        # Act
        response = client.get(
            "/admin/backups/",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 403

    def test_get_backups_with_superadmin_jwt_returns_200(self):
        """
        Given a superadmin JWT,
        When GET /admin/backups/ is called,
        Then 200 is returned and the page contains the expected heading.
        """
        # Arrange
        app = _make_app()
        client = app.test_client()
        token = _superadmin_token()

        # Act
        response = client.get(
            "/admin/backups/",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 200
        body = response.data.decode("utf-8")
        assert "Сделать снапшот" in body

    def test_post_snapshot_without_auth_redirects_to_login(self):
        """
        Given no JWT,
        When POST /admin/backups/snapshot is called,
        Then the error handler redirects to /admin/login (302).
        """
        # Arrange
        app = _make_app()
        client = app.test_client()

        # Act
        response = client.post("/admin/backups/snapshot")

        # Assert
        assert response.status_code == 302
        assert "/admin/login" in response.headers.get("Location", "")

    def test_post_snapshot_with_owner_jwt_returns_403(self):
        """
        Given an owner-role JWT,
        When POST /admin/backups/snapshot is called,
        Then 403 is returned.
        """
        # Arrange
        app = _make_app()
        client = app.test_client()
        token = _owner_token()

        # Act
        response = client.post(
            "/admin/backups/snapshot",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 403

    @pytest.mark.skip(
        reason="DI wiring for real backup storage / runner lands in Stage 5. "
        "This test validates file creation and requires a fully-wired container."
    )
    def test_post_snapshot_with_superadmin_creates_file(self):
        """
        Given superadmin JWT and a writable dumps dir,
        When POST /admin/backups/snapshot is called,
        Then 200 is returned and a .sql.gz file appears in the dumps dir.
        """

    def test_delete_nonexistent_snapshot_returns_4xx(self):
        """
        Given superadmin JWT and a facade that raises SnapshotNotFoundError,
        When DELETE /admin/backups/<name> is called,
        Then 422 is returned (DomainError mapped to 422 by error handler).
        """
        # Arrange
        from system.domain.backup_errors import SnapshotNotFoundError

        class FailingProvider(Provider):
            scope = Scope.APP

            @provide
            def system_facade(self) -> SystemFacade:
                m = MagicMock(spec=SystemFacade)
                m.list_snapshots.return_value = SnapshotListOut(items=[])
                m.delete_snapshot.side_effect = SnapshotNotFoundError("ghost.sql.gz")
                return m

        app = _make_app(FailingProvider())
        client = app.test_client()
        token = _superadmin_token()

        # Act
        response = client.delete(
            "/admin/backups/ghost.sql.gz",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert — DomainError → 422 (see shared/adapters/driving/error_handlers.py)
        assert response.status_code == 422

    def test_post_without_csrf_cookie_auth_returns_403(self):
        """
        Given a superadmin JWT sent via cookie (not Bearer),
        When POST /admin/backups/snapshot is called WITHOUT X-CSRF-Token,
        Then 403 is returned because CSRF validation fires for cookie-auth requests.

        The middleware reads request.cookies.get("token"); for cookie-mode
        unsafe requests it then calls _validate_csrf(), which raises
        CSRF_INVALID → 403 when the CSRF header/cookie is absent.
        Flask's test client requires set_cookie() to populate request.cookies;
        a raw Cookie header is not parsed by Werkzeug's test infrastructure.
        """
        # Arrange
        app = _make_app()
        token = _superadmin_token()

        # Act — cookie-auth POST with no CSRF header or csrf_token cookie
        with app.test_client() as client:
            client.set_cookie("token", token, domain="localhost")
            response = client.post("/admin/backups/snapshot")

        # Assert
        assert response.status_code == 403

    def test_delete_with_owner_jwt_returns_403(self):
        """
        Given an owner-role JWT (not superadmin),
        When DELETE /admin/backups/some-name.sql.gz is called,
        Then 403 is returned (backups are superadmin-only).
        """
        # Arrange
        app = _make_app()
        client = app.test_client()
        token = _owner_token()

        # Act
        response = client.delete(
            "/admin/backups/some-name.sql.gz",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 403

    def test_restore_with_owner_jwt_returns_403(self):
        """
        Given an owner-role JWT (not superadmin),
        When POST /admin/backups/some-name.sql.gz/restore is called,
        Then 403 is returned (backups are superadmin-only).
        """
        # Arrange
        app = _make_app()
        client = app.test_client()
        token = _owner_token()

        # Act
        response = client.post(
            "/admin/backups/some-name.sql.gz/restore",
            headers={"Authorization": f"Bearer {token}"},
        )

        # Assert
        assert response.status_code == 403
