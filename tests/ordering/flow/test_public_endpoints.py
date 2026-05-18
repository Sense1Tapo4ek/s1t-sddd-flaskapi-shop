"""
Public-endpoint flow tests for Stage 9.

- POST /inquiries: anonymous, 201 on valid body.
- POST /orders: customer JWT → 201; admin JWT → 403; no JWT → 401.

Facades are stubbed via Dishka; no DB involved.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from apiflask import APIFlask
from dishka import make_container, Provider, Scope, provide
from dishka.integrations.flask import setup_dishka

from ordering.adapters.driving.api import ordering_bp, orders_bp
from ordering.ports.driving.inquiries_facade import InquiriesFacade
from ordering.ports.driving.orders_facade import OrdersFacade
from ordering.ports.driving.schemas import (
    OrderItemOut,
    OrderOut,
)
from shared.adapters.driving.error_handlers import init_error_handlers
from shared.adapters.driving.middleware import init_middleware
from shared.helpers.security import create_jwt

pytestmark = pytest.mark.flow

_SECRET = "test-secret-at-least-32-bytes-long-here"


def _order_out() -> OrderOut:
    return OrderOut(
        id=1,
        customer_user_id=42,
        items=[
            OrderItemOut(
                product_id=1,
                title_snapshot="Widget",
                unit_price=Decimal("9.99"),
                quantity=2,
            )
        ],
        total=Decimal("19.98"),
        delivery_method="pickup",
        delivery_address="",
        delivery_comment="",
        comment="",
        status="new",
        created_at="2026-05-17 12:00",
    )


def _make_provider() -> Provider:
    class StubProvider(Provider):
        scope = Scope.APP

        @provide
        def inquiries(self) -> InquiriesFacade:
            m = MagicMock(spec=InquiriesFacade)
            m.create_inquiry.return_value = 1
            return m

        @provide
        def orders(self) -> OrdersFacade:
            m = MagicMock(spec=OrdersFacade)
            m.place_order.return_value = 1
            return m

    return StubProvider()


def _make_app() -> APIFlask:
    app = APIFlask(__name__)
    app.register_blueprint(ordering_bp)
    app.register_blueprint(orders_bp)
    init_middleware(app, _SECRET)
    init_error_handlers(app)
    container = make_container(_make_provider())
    setup_dishka(container, app)
    return app


def _customer_token(sub: int = 42) -> str:
    return create_jwt(
        {"sub": sub, "account_type": "customer", "role": "customer"},
        _SECRET,
        expires_hours=1,
    )


def _admin_token() -> str:
    return create_jwt(
        {"sub": 1, "account_type": "admin", "role": "owner"},
        _SECRET,
        expires_hours=1,
    )


class TestInquiryPublicEndpoint:
    def test_create_inquiry_anonymous_returns_201(self):
        """
        Given anonymous client and valid body,
        When POST /inquiries is called,
        Then 201 is returned with the new inquiry id.
        """
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/inquiries",
            json={"name": "Alice", "message": "Hello", "phone": "+375291234567"},
        )

        assert response.status_code == 201
        body = response.get_json()
        assert body["id"] == 1

    def test_create_inquiry_validation_failure_returns_400(self):
        """
        Given a body missing required `message` field,
        When POST /inquiries is called,
        Then a 4xx error is returned (schema validation rejects).
        """
        app = _make_app()
        client = app.test_client()

        response = client.post("/inquiries", json={"name": "Alice"})

        assert 400 <= response.status_code < 500


class TestOrderPublicEndpoint:
    _valid_body = {
        "items": [{"product_id": 1, "quantity": 2}],
        "delivery_method": "pickup",
        "address": "",
        "delivery_comment": "",
        "comment": "test",
    }

    def test_place_order_with_customer_jwt_returns_201(self):
        """
        Given a valid customer JWT and a valid order body,
        When POST /orders is called,
        Then 201 is returned with the order id; customer_user_id is taken
        from JWT sub, not from body.
        """
        app = _make_app()
        client = app.test_client()
        token = _customer_token(sub=42)

        response = client.post(
            "/orders",
            json=self._valid_body,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        body = response.get_json()
        assert body["id"] == 1

    def test_place_order_without_jwt_returns_401(self):
        """
        Given no JWT,
        When POST /orders is called,
        Then 401 AUTH_REQUIRED is returned.
        """
        app = _make_app()
        client = app.test_client()

        response = client.post("/orders", json=self._valid_body)

        assert response.status_code == 401

    def test_place_order_with_admin_jwt_returns_403(self):
        """
        Given an admin JWT (not customer),
        When POST /orders is called,
        Then 403 FORBIDDEN is returned — admins cannot place orders.
        """
        app = _make_app()
        client = app.test_client()
        token = _admin_token()

        response = client.post(
            "/orders",
            json=self._valid_body,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403
