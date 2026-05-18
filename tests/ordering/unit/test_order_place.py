"""Unit tests for Order.place() factory."""
from decimal import Decimal

import pytest

from ordering.domain import (
    DeliveryInfo,
    DeliveryMethod,
    EmptyOrderError,
    Order,
    OrderItem,
    OrderRequiresCustomerError,
    OrderStatus,
)


pytestmark = pytest.mark.unit


def _item(product_id: int = 1, price: str = "10.00", qty: int = 2) -> OrderItem:
    return OrderItem(
        product_id=product_id,
        title_snapshot="Widget",
        unit_price=Decimal(price),
        quantity=qty,
    )


def _pickup_delivery() -> DeliveryInfo:
    return DeliveryInfo(method=DeliveryMethod.PICKUP)


class TestOrderPlaceHappyPath:
    def test_places_order_with_correct_total(self):
        """
        Given two items (10.00 × 2 and 5.00 × 3),
        When Order.place() is called,
        Then total = 35.00 and status = NEW.
        """
        items = [
            _item(1, "10.00", 2),
            _item(2, "5.00", 3),
        ]
        order = Order.place(
            customer_user_id=42,
            items=items,
            delivery=_pickup_delivery(),
        )

        assert order.status is OrderStatus.NEW
        assert order.total == Decimal("35.00")
        assert order.id == 0  # sentinel before persistence
        assert order.customer_user_id == 42
        assert len(order.items) == 2

    def test_created_at_is_set(self):
        """
        Given a valid place() call,
        When the order is created,
        Then created_at is a non-None datetime.
        """
        from datetime import datetime

        before = datetime.now()
        order = Order.place(
            customer_user_id=1,
            items=[_item()],
            delivery=_pickup_delivery(),
        )
        assert order.created_at >= before


class TestOrderPlaceInvariants:
    def test_empty_items_raises(self):
        """
        Given an empty items list,
        When Order.place() is called,
        Then EmptyOrderError is raised.
        """
        with pytest.raises(EmptyOrderError) as exc_info:
            Order.place(
                customer_user_id=1,
                items=[],
                delivery=_pickup_delivery(),
            )
        assert exc_info.value.code == "EMPTY_ORDER"

    def test_zero_customer_id_raises(self):
        """
        Given customer_user_id == 0,
        When Order.place() is called,
        Then OrderRequiresCustomerError is raised.
        """
        with pytest.raises(OrderRequiresCustomerError) as exc_info:
            Order.place(
                customer_user_id=0,
                items=[_item()],
                delivery=_pickup_delivery(),
            )
        assert exc_info.value.code == "ORDER_REQUIRES_CUSTOMER"

    def test_negative_customer_id_raises(self):
        """
        Given customer_user_id < 0,
        When Order.place() is called,
        Then OrderRequiresCustomerError is raised.
        """
        with pytest.raises(OrderRequiresCustomerError):
            Order.place(
                customer_user_id=-5,
                items=[_item()],
                delivery=_pickup_delivery(),
            )

    def test_comment_defaults_to_empty_string(self):
        """
        Given no comment supplied,
        When Order.place() is called,
        Then comment is an empty string.
        """
        order = Order.place(
            customer_user_id=1,
            items=[_item()],
            delivery=_pickup_delivery(),
        )
        assert order.comment == ""
