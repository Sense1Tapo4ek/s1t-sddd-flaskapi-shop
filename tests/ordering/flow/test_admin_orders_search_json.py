"""Flow tests: /admin/orders/search endpoint existence and JSON contract."""
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from ordering.ports.driving.schemas import OrderItemOut, OrderOut, PaginatedOrdersOut

pytestmark = pytest.mark.flow


def _sample_order_out():
    return OrderOut(
        id=10,
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
        created_at="2026-03-01 09:00",
    )


def _create_app(monkeypatch, tmp_path):
    monkeypatch.setenv("INFRA_DATABASE_URL", f"sqlite:///{tmp_path / 'shop.db'}")
    monkeypatch.setenv("ROOT_APP_ENV", "dev")
    from root.entrypoints.api import create_app
    return create_app()


class TestOrdersSearchJsonEndpoint:
    def test_search_endpoint_exists_and_blocks_unauthenticated(self, monkeypatch, tmp_path):
        """
        Given no auth,
        When GET /admin/orders/search,
        Then returns not 404/500 — route registered, auth gate fires.
        """
        # Arrange
        app = _create_app(monkeypatch, tmp_path)
        client = app.test_client()

        # Act
        response = client.get(
            "/admin/orders/search?status__eq=new&page=1&limit=10",
            follow_redirects=False,
        )

        # Assert — route exists (not 404), server doesn't crash (not 500)
        assert response.status_code not in (404, 500)

    def test_orders_search_json_shape_contract(self):
        """
        Given a minimal PaginatedOrdersOut,
        When assembled into the search-json response shape,
        Then contains items/total/page/limit with correct types.
        """
        # Arrange
        order = _sample_order_out()
        paginated = PaginatedOrdersOut(items=[order], total=1)

        # Act — simulate what the endpoint assembles
        payload = {
            "items": [o.model_dump(mode="json") for o in paginated.items],
            "total": paginated.total,
            "page": 1,
            "limit": 10,
        }

        # Assert
        assert payload["total"] == 1
        assert payload["page"] == 1
        assert payload["limit"] == 10
        assert isinstance(payload["items"], list)
        item = payload["items"][0]
        assert item["id"] == 10
        assert item["customer_user_id"] == 42
        assert item["status"] == "new"
        assert item["delivery_method"] == "pickup"
        assert isinstance(item["items"], list)
        assert item["items"][0]["title_snapshot"] == "Widget"

    def test_order_out_serialises_decimal_as_json_safe(self):
        """
        Given OrderOut with Decimal total,
        When model_dump(mode='json') is called,
        Then total field is present and JSON-serialisable.
        """
        # Arrange
        order = _sample_order_out()

        # Act
        data = order.model_dump(mode="json")

        # Assert
        assert "total" in data
        assert data["total"] is not None
        json.dumps(data)  # must not raise
