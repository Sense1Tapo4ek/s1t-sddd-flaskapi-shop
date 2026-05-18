"""Unit tests for Order status transitions."""
from decimal import Decimal

import pytest

from ordering.domain import (
    DeliveryInfo,
    DeliveryMethod,
    IllegalOrderTransitionError,
    Order,
    OrderAlreadyTerminalError,
    OrderItem,
    OrderStatus,
)


pytestmark = pytest.mark.unit


def _new_order() -> Order:
    return Order.place(
        customer_user_id=1,
        items=[OrderItem(
            product_id=1,
            title_snapshot="Widget",
            unit_price=Decimal("10.00"),
            quantity=1,
        )],
        delivery=DeliveryInfo(method=DeliveryMethod.PICKUP),
    )


def _order(status: OrderStatus = OrderStatus.NEW) -> Order:
    """Return an Order in the requested status by walking legal transitions."""
    order = _new_order()
    # NEW is the start state; reach others via the allowed transition graph.
    if status is OrderStatus.NEW:
        return order
    if status is OrderStatus.CONFIRMED:
        order.change_status(OrderStatus.CONFIRMED)
        return order
    if status is OrderStatus.COMPLETED:
        order.change_status(OrderStatus.CONFIRMED)
        order.change_status(OrderStatus.COMPLETED)
        return order
    if status is OrderStatus.CANCELED:
        order.change_status(OrderStatus.CANCELED)
        return order
    if status is OrderStatus.ARCHIVED:
        order.change_status(OrderStatus.ARCHIVED)
        return order
    raise ValueError(f"Unknown status: {status}")


class TestOrderStatusTransitions:
    @pytest.mark.parametrize(
        ("initial", "target"),
        [
            (OrderStatus.NEW, OrderStatus.CONFIRMED),
            (OrderStatus.NEW, OrderStatus.CANCELED),
            (OrderStatus.NEW, OrderStatus.ARCHIVED),
            (OrderStatus.CONFIRMED, OrderStatus.COMPLETED),
            (OrderStatus.CONFIRMED, OrderStatus.CANCELED),
            (OrderStatus.CONFIRMED, OrderStatus.ARCHIVED),
            (OrderStatus.COMPLETED, OrderStatus.ARCHIVED),
            (OrderStatus.CANCELED, OrderStatus.ARCHIVED),
        ],
    )
    def test_allowed_transition_updates_status(self, initial, target):
        """
        Given an order in an allowed source status,
        When changing to a valid target status,
        Then the order status is updated.
        """
        order = _order(initial)
        order.change_status(target)
        assert order.status is target

    @pytest.mark.parametrize(
        ("initial", "target"),
        [
            (OrderStatus.CONFIRMED, OrderStatus.NEW),
            (OrderStatus.COMPLETED, OrderStatus.NEW),
            (OrderStatus.COMPLETED, OrderStatus.CONFIRMED),
            (OrderStatus.CANCELED, OrderStatus.NEW),
            (OrderStatus.CANCELED, OrderStatus.CONFIRMED),
        ],
    )
    def test_illegal_transition_raises(self, initial, target):
        """
        Given an order in a status without the target as an allowed transition,
        When change_status is called,
        Then IllegalOrderTransitionError is raised and status is unchanged.
        """
        order = _order(initial)
        with pytest.raises(IllegalOrderTransitionError) as exc_info:
            order.change_status(target)
        assert exc_info.value.code == "ILLEGAL_ORDER_TRANSITION"
        assert order.status is initial

    @pytest.mark.parametrize(
        ("initial", "target"),
        [
            (OrderStatus.ARCHIVED, OrderStatus.NEW),
            (OrderStatus.ARCHIVED, OrderStatus.CONFIRMED),
        ],
    )
    def test_terminal_status_raises(self, initial, target):
        """
        Given an order in ARCHIVED (terminal) status,
        When any status change is attempted,
        Then OrderAlreadyTerminalError is raised and status is unchanged.
        """
        order = _order(initial)
        with pytest.raises(OrderAlreadyTerminalError) as exc_info:
            order.change_status(target)
        assert exc_info.value.code == "ORDER_ALREADY_TERMINAL"
        assert order.status is OrderStatus.ARCHIVED

    def test_archive_method_from_new(self):
        """
        Given an order in NEW,
        When archive() is called,
        Then status becomes ARCHIVED.
        """
        order = _order(OrderStatus.NEW)
        order.archive()
        assert order.status is OrderStatus.ARCHIVED

    def test_archive_method_from_completed(self):
        """
        Given an order in COMPLETED,
        When archive() is called,
        Then status becomes ARCHIVED.
        """
        order = _order(OrderStatus.COMPLETED)
        order.archive()
        assert order.status is OrderStatus.ARCHIVED

    def test_archive_method_on_archived_raises(self):
        """
        Given an order already in ARCHIVED,
        When archive() is called,
        Then OrderAlreadyTerminalError is raised.
        """
        order = _order(OrderStatus.ARCHIVED)
        with pytest.raises(OrderAlreadyTerminalError):
            order.archive()
