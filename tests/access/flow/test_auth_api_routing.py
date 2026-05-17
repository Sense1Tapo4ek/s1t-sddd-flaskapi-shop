"""
Flow tests for the access API routing layer.

Tests verify that:
- POST /auth/login delegates to AccessFacade and returns 200 + token
- POST /auth/customer/register delegates to CustomerFacade and returns 201 + token
- POST /auth/customer/recover always returns 202 (even on error from UC)
- POST /auth/customer/verify delegates to CustomerFacade and returns 200 + token
- POST /auth/password rejects customer JWT with 403
- POST /auth/login handles AdminInactiveError / CustomerInactiveError -> ACCOUNT_INACTIVE

Facades are stubbed via Dishka stub provider; no DB involved.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from apiflask import APIFlask
from dishka import make_container, Provider, Scope, provide
from dishka.integrations.flask import setup_dishka

from access.adapters.driving.api import access_bp
from access.domain import (
    AdminInactiveError,
    CustomerInactiveError,
    InvalidPasswordError,
)
from access.ports.driving import (
    AccessFacade,
    AdminFacade,
    CustomerFacade,
    LoginOut,
)
from shared.adapters.driving.error_handlers import init_error_handlers
from shared.adapters.driving.middleware import init_middleware
from shared.helpers.security import create_jwt

_SECRET = "test-secret-at-least-32-bytes-long-here"


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_stub_provider(
    login_result=None,
    login_side_effect=None,
    register_result=None,
    send_side_effect=None,
    verify_result=None,
) -> Provider:
    """Build a Dishka Provider with stub facades."""

    class StubProvider(Provider):
        scope = Scope.APP

        @provide
        def access_facade(self) -> AccessFacade:
            m = MagicMock(spec=AccessFacade)
            if login_side_effect is not None:
                m.login.side_effect = login_side_effect
            else:
                m.login.return_value = login_result or LoginOut(token="admin-jwt")
            return m

        @provide
        def customer_facade(self) -> CustomerFacade:
            m = MagicMock(spec=CustomerFacade)
            m.register.return_value = register_result or LoginOut(token="cust-jwt")
            if send_side_effect is not None:
                m.send_recovery_code.side_effect = send_side_effect
            else:
                m.send_recovery_code.return_value = None
            m.verify_and_reset.return_value = verify_result or LoginOut(token="verify-jwt")
            return m

        @provide
        def admin_facade(self) -> AdminFacade:
            m = MagicMock(spec=AdminFacade)
            m.change_password.return_value = None
            return m

    return StubProvider()


def _make_app(provider: Provider) -> APIFlask:
    """Build a minimal APIFlask with the access blueprint and stub DI."""
    app = APIFlask(__name__)
    app.register_blueprint(access_bp)
    init_middleware(app, _SECRET)
    init_error_handlers(app)

    container = make_container(provider)
    setup_dishka(container, app)
    return app


def _make_token(account_type: str = "admin", role: str = "owner") -> str:
    return create_jwt(
        {"sub": 1, "role": role, "account_type": account_type},
        _SECRET,
        expires_hours=1,
    )


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestLoginRoute:
    def test_login_happy_path_returns_200_and_token(self):
        """
        Given a valid login payload and a facade returning a token,
        When POST /auth/login is called,
        Then 200 is returned with a token in the JSON body.
        """
        app = _make_app(_make_stub_provider(login_result=LoginOut(token="tok-admin")))
        with app.test_client() as client:
            resp = client.post(
                "/auth/login",
                json={"login": "admin", "password": "pass"},
                content_type="application/json",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["token"] == "tok-admin"

    def test_login_invalid_password_returns_error_code(self):
        """
        Given a facade that raises InvalidPasswordError,
        When POST /auth/login is called,
        Then the response carries INVALID_CREDENTIALS error code.
        """
        app = _make_app(
            _make_stub_provider(login_side_effect=InvalidPasswordError())
        )
        with app.test_client() as client:
            resp = client.post(
                "/auth/login",
                json={"login": "admin", "password": "wrong"},
                content_type="application/json",
            )
        # DrivingAdapterError(INVALID_CREDENTIALS) maps to 401
        assert resp.status_code == 401
        body = resp.get_json()
        # Error format: {"error": "CODE", "message": "...", "success": False}
        assert body.get("error") == "INVALID_CREDENTIALS"

    def test_login_admin_inactive_returns_account_inactive(self):
        """
        Given a facade that raises AdminInactiveError,
        When POST /auth/login is called,
        Then the response carries ACCOUNT_INACTIVE error code.
        """
        app = _make_app(
            _make_stub_provider(login_side_effect=AdminInactiveError())
        )
        with app.test_client() as client:
            resp = client.post(
                "/auth/login",
                json={"login": "admin", "password": "pass"},
                content_type="application/json",
            )
        body = resp.get_json()
        assert body.get("error") == "ACCOUNT_INACTIVE"

    def test_login_customer_inactive_returns_account_inactive(self):
        """
        Given a facade that raises CustomerInactiveError,
        When POST /auth/login is called,
        Then the response carries ACCOUNT_INACTIVE error code.
        """
        app = _make_app(
            _make_stub_provider(login_side_effect=CustomerInactiveError())
        )
        with app.test_client() as client:
            resp = client.post(
                "/auth/login",
                json={"login": "cust@example.com", "password": "pass"},
                content_type="application/json",
            )
        body = resp.get_json()
        assert body.get("error") == "ACCOUNT_INACTIVE"

    def test_login_missing_fields_returns_validation_error(self):
        """
        Given a payload missing required fields,
        When POST /auth/login is called,
        Then a 4xx validation error is returned.
        """
        app = _make_app(_make_stub_provider())
        with app.test_client() as client:
            resp = client.post(
                "/auth/login",
                json={"login": "admin"},
                content_type="application/json",
            )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# POST /auth/customer/register
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestRegisterCustomerRoute:
    def test_register_returns_201_and_token(self):
        """
        Given a valid customer register payload,
        When POST /auth/customer/register is called,
        Then 201 is returned with a token in the JSON body.
        """
        app = _make_app(
            _make_stub_provider(register_result=LoginOut(token="cust-reg-tok"))
        )
        with app.test_client() as client:
            resp = client.post(
                "/auth/customer/register",
                json={"email": "new@example.com", "password": "password123"},
                content_type="application/json",
            )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["token"] == "cust-reg-tok"

    def test_register_missing_password_returns_validation_error(self):
        """
        Given a payload without password,
        When POST /auth/customer/register is called,
        Then a 4xx error is returned.
        """
        app = _make_app(_make_stub_provider())
        with app.test_client() as client:
            resp = client.post(
                "/auth/customer/register",
                json={"email": "x@example.com"},
                content_type="application/json",
            )
        assert resp.status_code in (400, 422)

    def test_register_invalid_email_returns_validation_error(self):
        """
        Given an invalid email address,
        When POST /auth/customer/register is called,
        Then a 4xx error is returned.
        """
        app = _make_app(_make_stub_provider())
        with app.test_client() as client:
            resp = client.post(
                "/auth/customer/register",
                json={"email": "not-an-email", "password": "password123"},
                content_type="application/json",
            )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# POST /auth/customer/recover
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestRecoverCustomerRoute:
    def test_recover_always_returns_202_on_known_email(self):
        """
        Given a valid email and UC succeeds,
        When POST /auth/customer/recover is called,
        Then 202 is returned regardless.
        """
        app = _make_app(_make_stub_provider())
        with app.test_client() as client:
            resp = client.post(
                "/auth/customer/recover",
                json={"email": "known@example.com"},
                content_type="application/json",
            )
        assert resp.status_code == 202

    def test_recover_always_returns_202_even_on_uc_error(self):
        """
        Given the send_recovery_code UC raises an exception,
        When POST /auth/customer/recover is called,
        Then 202 is still returned (no leak of registration base).
        """
        app = _make_app(
            _make_stub_provider(send_side_effect=Exception("email failed"))
        )
        with app.test_client() as client:
            resp = client.post(
                "/auth/customer/recover",
                json={"email": "ghost@nowhere.com"},
                content_type="application/json",
            )
        assert resp.status_code == 202

    def test_recover_missing_email_returns_validation_error(self):
        """
        Given an empty payload,
        When POST /auth/customer/recover is called,
        Then a 4xx validation error is returned.
        """
        app = _make_app(_make_stub_provider())
        with app.test_client() as client:
            resp = client.post(
                "/auth/customer/recover",
                json={},
                content_type="application/json",
            )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# POST /auth/customer/verify
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestVerifyCustomerRoute:
    def test_verify_returns_200_and_token(self):
        """
        Given a valid verify payload,
        When POST /auth/customer/verify is called,
        Then 200 is returned with a token.
        """
        app = _make_app(
            _make_stub_provider(verify_result=LoginOut(token="reset-tok"))
        )
        with app.test_client() as client:
            resp = client.post(
                "/auth/customer/verify",
                json={
                    "email": "user@example.com",
                    "code": "123456",
                    "new_password": "newpassword1",
                },
                content_type="application/json",
            )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["token"] == "reset-tok"

    def test_verify_missing_code_returns_validation_error(self):
        """
        Given a payload missing the code field,
        When POST /auth/customer/verify is called,
        Then a 4xx error is returned.
        """
        app = _make_app(_make_stub_provider())
        with app.test_client() as client:
            resp = client.post(
                "/auth/customer/verify",
                json={"email": "user@example.com", "new_password": "newpassword1"},
                content_type="application/json",
            )
        assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# POST /auth/password — rejects customer JWT
# ---------------------------------------------------------------------------

@pytest.mark.flow
class TestChangePasswordRoute:
    def test_customer_jwt_rejected_with_403(self):
        """
        Given a valid customer JWT (account_type=customer),
        When POST /auth/password is called,
        Then 403 is returned — customer JWT must not access admin routes.
        """
        app = _make_app(_make_stub_provider())
        token = _make_token(account_type="customer", role="customer")
        with app.test_client() as client:
            resp = client.post(
                "/auth/password",
                json={"new_password": "newpass1234", "old_password": "old"},
                content_type="application/json",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 403
        body = resp.get_json()
        # Error format: {"error": "CODE", "message": "...", "success": False}
        assert body.get("error") == "FORBIDDEN"

    def test_admin_jwt_accepted(self):
        """
        Given a valid admin JWT,
        When POST /auth/password is called,
        Then facade.change_password is invoked and success is returned.
        """
        app = _make_app(_make_stub_provider())
        token = _make_token(account_type="admin", role="owner")
        with app.test_client() as client:
            resp = client.post(
                "/auth/password",
                json={"new_password": "newpass1234", "old_password": "oldpass"},
                content_type="application/json",
                headers={"Authorization": f"Bearer {token}"},
            )
        # The stub AdminFacade returns None; the route returns {"success": True}
        assert resp.status_code == 200
        data = resp.get_json()
        assert data.get("success") is True

    def test_no_token_returns_auth_required(self):
        """
        Given no token,
        When POST /auth/password is called,
        Then AUTH_REQUIRED error is returned.
        """
        app = _make_app(_make_stub_provider())
        with app.test_client() as client:
            resp = client.post(
                "/auth/password",
                json={"new_password": "newpass1234"},
                content_type="application/json",
            )
        body = resp.get_json()
        # Error format: {"error": "CODE", "message": "...", "success": False}
        assert body.get("error") == "AUTH_REQUIRED"
