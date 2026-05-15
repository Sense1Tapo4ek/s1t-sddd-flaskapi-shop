from datetime import datetime

import pytest

from ordering.domain import (
    InvalidOrderTransitionError,
    Order,
    OrderCreationError,
    OrderStatus,
)


@pytest.mark.unit
class TestOrderCreation:
    def test_order_requires_phone(self):
        """
        Given order data without a phone,
        When creating an order,
        Then the domain rejects the order.
        """
        # Arrange / Act / Assert
        with pytest.raises(OrderCreationError) as exc_info:
            Order.create(id=1, name="Alice", phone="", comment="Call back")

        assert exc_info.value.code == "ORDER_CREATION_FAILED"

    def test_order_starts_in_new_status(self):
        """
        Given valid order data,
        When creating an order,
        Then the order starts as NEW with a creation timestamp.
        """
        # Arrange
        before_create = datetime.now()

        # Act
        order = Order.create(id=1, name="Alice", phone="+375291234567", comment="")

        # Assert
        assert order.status is OrderStatus.NEW
        assert order.created_at >= before_create


@pytest.mark.unit
class TestOrderStatusTransitions:
    @pytest.mark.parametrize(
        ("initial_status", "target_status"),
        [
            (OrderStatus.NEW, OrderStatus.PROCESSING),
            (OrderStatus.NEW, OrderStatus.CANCELED),
            (OrderStatus.PROCESSING, OrderStatus.DONE),
            (OrderStatus.PROCESSING, OrderStatus.CANCELED),
        ],
    )
    def test_allowed_transition_changes_status(self, initial_status, target_status):
        """
        Given an order in a status with an allowed outgoing transition,
        When changing to the allowed target status,
        Then the order status is updated.
        """
        # Arrange
        order = Order.create(id=1, name="Alice", phone="+375291234567", comment="")
        order.status = initial_status

        # Act
        order.change_status(target_status)

        # Assert
        assert order.status is target_status

    @pytest.mark.parametrize(
        ("initial_status", "target_status"),
        [
            (OrderStatus.NEW, OrderStatus.DONE),
            (OrderStatus.PROCESSING, OrderStatus.NEW),
        ],
    )
    def test_illegal_transition_from_non_terminal_is_rejected(
        self, initial_status, target_status
    ):
        """
        Given an order in a non-terminal status (NEW or PROCESSING),
        When changing to a forbidden target that is not allowed by the matrix,
        Then IllegalOrderTransitionError is raised with code "illegal_transition"
        and the order status is not mutated.
        """
        from ordering.domain import IllegalOrderTransitionError

        # Arrange
        order = Order.create(id=1, name="Alice", phone="+375291234567", comment="")
        order.status = initial_status

        # Act
        with pytest.raises(IllegalOrderTransitionError) as exc_info:
            order.change_status(target_status)

        # Assert
        assert exc_info.value.code == "illegal_transition"
        assert order.status is initial_status

    @pytest.mark.parametrize(
        ("initial_status", "target_status"),
        [
            (OrderStatus.DONE, OrderStatus.PROCESSING),
            (OrderStatus.CANCELED, OrderStatus.NEW),
        ],
    )
    def test_transition_from_terminal_is_rejected(
        self, initial_status, target_status
    ):
        """
        Given an order in a terminal status (DONE or CANCELED),
        When attempting any status change,
        Then OrderAlreadyTerminalError is raised with code "order_already_terminal"
        and the order status is not mutated.
        """
        from ordering.domain import OrderAlreadyTerminalError

        # Arrange
        order = Order.create(id=1, name="Alice", phone="+375291234567", comment="")
        order.status = initial_status

        # Act
        with pytest.raises(OrderAlreadyTerminalError) as exc_info:
            order.change_status(target_status)

        # Assert
        assert exc_info.value.code == "order_already_terminal"
        assert order.status is initial_status
