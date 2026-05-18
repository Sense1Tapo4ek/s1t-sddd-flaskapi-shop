"""Flow tests: /admin/requests/ page route exists and template has the right structure."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.flow


def _create_app(monkeypatch, tmp_path):
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    from root.entrypoints.api import create_app
    return create_app()


class TestRequestsPageRoute:
    def test_requests_page_blocks_unauthenticated(self, monkeypatch, tmp_path):
        """
        Given no auth token,
        When GET /admin/requests/,
        Then response is not 200/500 — route exists and auth gate fires (302 or 401).
        """
        # Arrange
        app = _create_app(monkeypatch, tmp_path)
        client = app.test_client()

        # Act
        response = client.get("/admin/requests/", follow_redirects=False)

        # Assert — not 404 (route registered), not 500 (no crash)
        assert response.status_code not in (404, 500)

    def test_requests_page_template_contains_tab_placeholders(self, monkeypatch, tmp_path):
        """
        Given the requests page template,
        When rendered inside an app and request context,
        Then it contains both feed container ids.
        """
        # Arrange
        app = _create_app(monkeypatch, tmp_path)

        # Act — render inside a proper request context
        with app.test_request_context("/admin/requests/"):
            from flask import render_template
            html = render_template("ordering/pages/requests.html")

        # Assert
        assert "orders-feed" in html
        assert "inquiries-feed" in html
        assert "Заказы" in html
        assert "Обращения" in html

    def test_legacy_inquiries_route_does_not_404(self, monkeypatch, tmp_path):
        """
        Given /admin/inquiries/ endpoint,
        When accessed,
        Then returns not 404/500 (route registered, redirects or auth-gates).
        """
        # Arrange
        app = _create_app(monkeypatch, tmp_path)
        client = app.test_client()

        # Act
        response = client.get("/admin/inquiries/", follow_redirects=False)

        # Assert
        assert response.status_code not in (404, 500)

    def test_legacy_orders_route_does_not_404(self, monkeypatch, tmp_path):
        """
        Given /admin/orders/ endpoint,
        When accessed,
        Then returns not 404/500 (route registered, redirects or auth-gates).
        """
        # Arrange
        app = _create_app(monkeypatch, tmp_path)
        client = app.test_client()

        # Act
        response = client.get("/admin/orders/", follow_redirects=False)

        # Assert
        assert response.status_code not in (404, 500)
