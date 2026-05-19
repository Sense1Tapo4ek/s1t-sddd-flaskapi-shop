from __future__ import annotations

import json

import pytest


pytestmark = pytest.mark.flow


def _create_app(monkeypatch: pytest.MonkeyPatch, mysql_test_db):
    monkeypatch.setenv("ROOT_APP_ENV", "dev")

    from root.entrypoints.api import create_app

    return create_app()


def test_admin_login_invalid_credentials_show_safe_visible_htmx_error(
    monkeypatch,
    mysql_test_db,
):
    """
    Given the admin login form submits with HTMX,
    When credentials are wrong,
    Then the visible error should describe login failure, not current-password failure.
    """
    # Arrange
    app = _create_app(monkeypatch, mysql_test_db)
    client = app.test_client()

    # Act
    response = client.post(
        "/admin/login",
        data={"login": "admin", "password": "wrong"},
        headers={"HX-Request": "true"},
    )

    # Assert
    assert response.status_code == 401
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"] == {
        "message": "Неверный логин или пароль",
        "type": "error",
    }


def test_auth_login_invalid_credentials_use_unified_error_json(
    monkeypatch,
    mysql_test_db,
):
    """
    Given public JSON login fails,
    When API clients inspect the response,
    Then they receive the shared error envelope with a safe message.
    """
    # Arrange
    app = _create_app(monkeypatch, mysql_test_db)
    client = app.test_client()

    # Act
    response = client.post(
        "/auth/login",
        json={"login": "admin", "password": "wrong"},
    )

    # Assert
    assert response.status_code == 401
    assert response.get_json() == {
        "success": False,
        "error": "INVALID_CREDENTIALS",
        "message": "Неверный логин или пароль",
    }


def test_manual_public_api_errors_use_unified_error_json(monkeypatch, mysql_test_db):
    """
    Given a public endpoint returns an application-level error itself,
    When the recovery token is invalid,
    Then the response still uses the shared error envelope.
    """
    # Arrange
    app = _create_app(monkeypatch, mysql_test_db)
    client = app.test_client()

    # Act
    response = client.post("/system/settings/recover-password/not-the-token")

    # Assert
    assert response.status_code == 404
    assert response.get_json() == {
        "success": False,
        "error": "NOT_FOUND",
        "message": "Неверный путь восстановления",
    }


def test_apiflask_validation_errors_use_unified_error_json(monkeypatch, mysql_test_db):
    """
    Given request schema validation fails before a route handler runs,
    When APIFlask builds the response,
    Then the client still receives the same error envelope and validation detail.
    """
    # Arrange
    app = _create_app(monkeypatch, mysql_test_db)
    client = app.test_client()

    # Act
    response = client.post("/inquiries", json={"name": "", "message": ""})
    body = response.get_json()

    # Assert
    assert response.status_code == 422
    assert body["success"] is False
    assert body["error"] == "VALIDATION_ERROR"
    assert body["message"] == "Проверьте данные запроса"
    assert "detail" in body


def test_infrastructure_errors_hide_internal_details_in_htmx_toast():
    """
    Given an infrastructure failure contains internal adapter details,
    When it happens during an HTMX action,
    Then the toast remains user-facing and does not expose the internal message.
    """
    # Arrange
    from apiflask import APIFlask

    from shared.adapters.driving.error_handlers import init_error_handlers
    from shared.generics.errors import DrivenPortError

    app = APIFlask(__name__)
    init_error_handlers(app)

    @app.get("/broken")
    def broken():
        raise DrivenPortError("create product failed: mysql UNIQUE constraint")

    # Act
    response = app.test_client().get("/broken", headers={"HX-Request": "true"})

    # Assert
    assert response.status_code == 500
    trigger = json.loads(response.headers["HX-Trigger"])
    assert trigger["showToast"] == {
        "message": "Не удалось выполнить операцию. Попробуйте позже.",
        "type": "error",
    }
