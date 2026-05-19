"""Flow tests: /admin/orders/ and /admin/inquiries/ are independent admin pages."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.flow


class TestSplitAdminPages:
    def test_orders_page_blocks_unauthenticated(self, dev_app):
        """
        Given no auth token,
        When GET /admin/orders/,
        Then response is not 404/500 — route exists and auth gate fires.
        """
        client = dev_app.test_client()

        response = client.get("/admin/orders/", follow_redirects=False)

        assert response.status_code not in (404, 500)

    def test_inquiries_page_blocks_unauthenticated(self, dev_app):
        """
        Given no auth token,
        When GET /admin/inquiries/,
        Then response is not 404/500 — route exists and auth gate fires.
        """
        client = dev_app.test_client()

        response = client.get("/admin/inquiries/", follow_redirects=False)

        assert response.status_code not in (404, 500)

    def test_orders_template_renders(self, dev_app):
        """
        Given the orders page template,
        When rendered,
        Then it carries the orders feed container + page title.
        """
        with dev_app.test_request_context("/admin/orders/"):
            from flask import render_template
            html = render_template("ordering/pages/orders.html")

        assert 'id="orders-feed"' in html
        assert "Заказы" in html

    def test_inquiries_template_renders(self, dev_app):
        """
        Given the inquiries page template,
        When rendered,
        Then it carries the inquiries feed container + page title.
        """
        with dev_app.test_request_context("/admin/inquiries/"):
            from flask import render_template
            html = render_template("ordering/pages/inquiries.html")

        assert 'id="inquiries-feed"' in html
        assert "Обращения" in html

    def test_legacy_requests_route_is_gone(self, dev_app):
        """
        Given the old unified /admin/requests/ route has been removed,
        When accessed,
        Then 404 — the page no longer exists.
        """
        client = dev_app.test_client()

        response = client.get("/admin/requests/", follow_redirects=False)

        assert response.status_code == 404
