"""
Unit tests for account_type gating in shared middleware decorators.

Covers:
- admin_required: allows admin JWT, rejects customer JWT (FORBIDDEN)
- customer_required: allows customer JWT, rejects admin JWT
- permission_required: rejects customer JWT regardless of permission
- superadmin_required: rejects customer JWT
- backward compat: payload without account_type treated as admin
"""
import pytest
from flask import Flask

from shared.adapters.driving.middleware import (
    admin_required,
    current_customer_id,
    customer_required,
    init_middleware,
    permission_required,
    superadmin_required,
)
from shared.generics.errors import DrivingAdapterError
from shared.helpers.security import create_jwt

_SECRET = "test-secret-at-least-32-bytes-long-pad"


def _make_app() -> Flask:
    app = Flask(__name__)
    init_middleware(app, _SECRET)
    return app


def _make_token(account_type: str | None = None, role: str = "owner", **extra) -> str:
    payload: dict = {"sub": 1, "role": role}
    if account_type is not None:
        payload["account_type"] = account_type
    payload.update(extra)
    return create_jwt(payload, _SECRET, expires_hours=1)


def _register_view(app: Flask, decorator, view_name: str = "protected") -> None:
    """Register a minimal protected view on the app."""
    @app.get(f"/{view_name}")
    @decorator
    def protected_view():
        return "ok", 200

    # Avoid duplicate endpoint registration across test functions
    # (each test creates a fresh app, so this is fine)


# ---------------------------------------------------------------------------
# admin_required
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestAdminRequired:
    def test_allows_admin_jwt(self):
        """
        Given a JWT with account_type=admin,
        When admin_required view is accessed,
        Then 200 is returned.
        """
        app = _make_app()
        _register_view(app, admin_required)
        token = _make_token(account_type="admin")
        with app.test_client() as client:
            resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_rejects_customer_jwt(self):
        """
        Given a JWT with account_type=customer,
        When admin_required view is accessed,
        Then DrivingAdapterError(FORBIDDEN) is raised and 403 is returned.
        """
        app = _make_app()
        _register_view(app, admin_required)

        @app.errorhandler(DrivingAdapterError)
        def _handle(e):
            return {"code": e.code}, 403

        token = _make_token(account_type="customer")
        with app.test_client() as client:
            resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_backward_compat_no_account_type_treated_as_admin(self):
        """
        Given a JWT without account_type field (old admin tokens),
        When admin_required view is accessed,
        Then 200 is returned (backward-compatible default=admin).
        """
        app = _make_app()
        _register_view(app, admin_required)
        token = _make_token(account_type=None)  # no account_type in payload
        with app.test_client() as client:
            resp = client.get("/protected", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_no_token_returns_error(self):
        """
        Given no token,
        When admin_required view is accessed,
        Then DrivingAdapterError(AUTH_REQUIRED) is raised.
        """
        app = _make_app()
        _register_view(app, admin_required)

        @app.errorhandler(DrivingAdapterError)
        def _handle(e):
            return {"code": e.code}, 401

        with app.test_client() as client:
            resp = client.get("/protected")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# customer_required
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCustomerRequired:
    def test_allows_customer_jwt(self):
        """
        Given a JWT with account_type=customer,
        When customer_required view is accessed,
        Then 200 is returned.
        """
        app = _make_app()
        _register_view(app, customer_required, "customer_view")
        token = _make_token(account_type="customer", role="customer")
        with app.test_client() as client:
            resp = client.get(
                "/customer_view", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 200

    def test_rejects_admin_jwt(self):
        """
        Given a JWT with account_type=admin,
        When customer_required view is accessed,
        Then FORBIDDEN is raised.
        """
        app = _make_app()
        _register_view(app, customer_required, "customer_view2")

        @app.errorhandler(DrivingAdapterError)
        def _handle(e):
            return {"code": e.code}, 403

        token = _make_token(account_type="admin")
        with app.test_client() as client:
            resp = client.get(
                "/customer_view2", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 403

    def test_rejects_no_account_type_payload(self):
        """
        Given a JWT without account_type (defaults to admin),
        When customer_required view is accessed,
        Then FORBIDDEN is raised (old tokens are admin, not customer).
        """
        app = _make_app()
        _register_view(app, customer_required, "customer_view3")

        @app.errorhandler(DrivingAdapterError)
        def _handle(e):
            return {"code": e.code}, 403

        token = _make_token(account_type=None)
        with app.test_client() as client:
            resp = client.get(
                "/customer_view3", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# permission_required rejects customer JWT
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestPermissionRequiredRejectsCustomer:
    def test_customer_jwt_is_rejected_regardless_of_permission(self):
        """
        Given a JWT with account_type=customer and a permissions dict that includes
        the required permission,
        When permission_required view is accessed,
        Then FORBIDDEN is raised — customer JWTs are never admin.
        """
        app = _make_app()

        @app.get("/perm_view")
        @permission_required("view_products")
        def perm_view():
            return "ok", 200

        @app.errorhandler(DrivingAdapterError)
        def _handle(e):
            return {"code": e.code}, 403

        token = _make_token(
            account_type="customer",
            permissions={"view_products": True},
        )
        with app.test_client() as client:
            resp = client.get(
                "/perm_view", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 403

    def test_admin_jwt_with_permission_is_allowed(self):
        """
        Given a JWT with account_type=admin and the required permission,
        When permission_required view is accessed,
        Then 200 is returned.
        """
        app = _make_app()

        @app.get("/perm_view2")
        @permission_required("view_products")
        def perm_view2():
            return "ok", 200

        token = _make_token(
            account_type="admin",
            permissions={"view_products": True},
        )
        with app.test_client() as client:
            resp = client.get(
                "/perm_view2", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 200

    def test_superadmin_jwt_is_allowed_through_permission_check(self):
        """
        Given a JWT with account_type=admin and role=superadmin,
        When permission_required view is accessed,
        Then 200 is returned (superadmin bypasses permission check).
        """
        app = _make_app()

        @app.get("/perm_view3")
        @permission_required("any_permission")
        def perm_view3():
            return "ok", 200

        token = _make_token(account_type="admin", role="superadmin")
        with app.test_client() as client:
            resp = client.get(
                "/perm_view3", headers={"Authorization": f"Bearer {token}"}
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# superadmin_required rejects customer JWT
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSuperadminRequiredRejectsCustomer:
    def test_customer_jwt_is_rejected(self):
        """
        Given a JWT with account_type=customer and role=superadmin (malformed),
        When superadmin_required view is accessed,
        Then FORBIDDEN is raised.
        """
        app = _make_app()

        @app.get("/sa_view")
        @superadmin_required
        def sa_view():
            return "ok", 200

        @app.errorhandler(DrivingAdapterError)
        def _handle(e):
            return {"code": e.code}, 403

        token = _make_token(account_type="customer", role="superadmin")
        with app.test_client() as client:
            resp = client.get("/sa_view", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 403

    def test_admin_superadmin_is_allowed(self):
        """
        Given a JWT with account_type=admin and role=superadmin,
        When superadmin_required view is accessed,
        Then 200 is returned.
        """
        app = _make_app()

        @app.get("/sa_view2")
        @superadmin_required
        def sa_view2():
            return "ok", 200

        token = _make_token(account_type="admin", role="superadmin")
        with app.test_client() as client:
            resp = client.get("/sa_view2", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# customer_required: g.customer_user_id wiring
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCustomerRequiredCustomerId:
    def test_sets_customer_user_id_from_sub_claim(self):
        """
        Given a customer JWT with sub=42,
        When customer_required view runs,
        Then current_customer_id() inside the view returns 42.
        """
        app = _make_app()

        @app.get("/cust_id")
        @customer_required
        def cust_id_view():
            return {"id": current_customer_id()}, 200

        token = create_jwt(
            {"sub": 42, "account_type": "customer", "role": "customer"},
            _SECRET,
            expires_hours=1,
        )
        with app.test_client() as client:
            resp = client.get("/cust_id", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.get_json() == {"id": 42}

    def test_current_customer_id_outside_customer_required_raises(self):
        """
        Given no @customer_required decorator on the view,
        When current_customer_id() is called,
        Then RuntimeError is raised (programmer error, not auth failure).
        """
        app = _make_app()

        @app.get("/no_cust")
        def no_cust():
            return {"id": current_customer_id()}, 200

        @app.errorhandler(RuntimeError)
        def _handle(e):
            return {"code": "PROGRAMMER_ERROR"}, 500

        with app.test_client() as client:
            resp = client.get("/no_cust")
        assert resp.status_code == 500
        assert resp.get_json() == {"code": "PROGRAMMER_ERROR"}

    def test_no_token_returns_auth_required(self):
        """
        Given no token,
        When customer_required view is accessed,
        Then DrivingAdapterError(AUTH_REQUIRED) is raised → 401.
        """
        app = _make_app()
        _register_view(app, customer_required, "cust_view_no_token")

        @app.errorhandler(DrivingAdapterError)
        def _handle(e):
            return {"code": e.code}, 401

        with app.test_client() as client:
            resp = client.get("/cust_view_no_token")
        assert resp.status_code == 401
