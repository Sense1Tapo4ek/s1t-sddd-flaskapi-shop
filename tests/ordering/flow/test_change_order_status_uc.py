"""Flow tests for ChangeOrderStatusUseCase."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from unittest.mock import create_autospec

import pytest

from ordering.app.commands import ChangeOrderStatusCommand
from ordering.app.errors import OrderNotFoundError
from ordering.app.interfaces import IOrderRepo
from ordering.app.use_cases.change_order_status_uc import ChangeOrderStatusUseCase
from ordering.domain import (
    DeliveryInfo,
    DeliveryMethod,
    IllegalOrderTransitionError,
    InvalidOrderTransitionError,
    Order,
    OrderAlreadyTerminalError,
    OrderItem,
    OrderStatus,
)

pytestmark = pytest.mark.flow


def _order(status: OrderStatus = OrderStatus.NEW) -> Order:
    order = Order.place(
        customer_user_id=1,
        items=[
            OrderItem(
                product_id=1,
                title_snapshot="Widget",
                unit_price=Decimal("10.00"),
                quantity=2,
            )
        ],
        delivery=DeliveryInfo(method=DeliveryMethod.PICKUP),
    )
    order.id = 42
    order.status = status
    return order


class TestChangeOrderStatusHappyPath:
    def test_status_changes_and_id_returned(self):
        """
        Given an order in NEW status,
        When ChangeOrderStatusUseCase is called with status 'confirmed',
        Then the order's status is updated and its id is returned.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.NEW)
        repo.get_by_id.return_value = order
        uc = ChangeOrderStatusUseCase(_repo=repo)

        result = uc(ChangeOrderStatusCommand(order_id=42, new_status="confirmed"))

        assert result == 42
        assert order.status is OrderStatus.CONFIRMED
        repo.save.assert_called_once_with(order)

    def test_confirmed_to_completed(self):
        """
        Given an order in CONFIRMED status,
        When changing to 'completed',
        Then status updates and save is called.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.CONFIRMED)
        repo.get_by_id.return_value = order
        uc = ChangeOrderStatusUseCase(_repo=repo)

        result = uc(ChangeOrderStatusCommand(order_id=42, new_status="completed"))

        assert result == 42
        assert order.status is OrderStatus.COMPLETED
        repo.save.assert_called_once()

    def test_new_to_canceled(self):
        """
        Given an order in NEW status,
        When changing to 'canceled',
        Then status updates to CANCELED.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.NEW)
        repo.get_by_id.return_value = order
        uc = ChangeOrderStatusUseCase(_repo=repo)

        result = uc(ChangeOrderStatusCommand(order_id=42, new_status="canceled"))

        assert result == 42
        assert order.status is OrderStatus.CANCELED


class TestChangeOrderStatusErrors:
    def test_order_not_found_raises(self):
        """
        Given no order in the repo for the given id,
        When ChangeOrderStatusUseCase is called,
        Then OrderNotFoundError is raised.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.return_value = None
        uc = ChangeOrderStatusUseCase(_repo=repo)

        with pytest.raises(OrderNotFoundError) as exc_info:
            uc(ChangeOrderStatusCommand(order_id=99, new_status="confirmed"))

        assert exc_info.value.code == "ORDER_NOT_FOUND"
        repo.save.assert_not_called()

    def test_illegal_transition_raises(self):
        """
        Given an order in CONFIRMED status,
        When attempting to change to 'new' (a backwards transition),
        Then IllegalOrderTransitionError is raised and save is not called.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.CONFIRMED)
        repo.get_by_id.return_value = order
        uc = ChangeOrderStatusUseCase(_repo=repo)

        with pytest.raises(IllegalOrderTransitionError):
            uc(ChangeOrderStatusCommand(order_id=42, new_status="new"))

        repo.save.assert_not_called()

    def test_terminal_status_raises(self):
        """
        Given an order in ARCHIVED (terminal) status,
        When attempting any status change,
        Then OrderAlreadyTerminalError is raised and save is not called.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.ARCHIVED)
        repo.get_by_id.return_value = order
        uc = ChangeOrderStatusUseCase(_repo=repo)

        with pytest.raises(OrderAlreadyTerminalError):
            uc(ChangeOrderStatusCommand(order_id=42, new_status="confirmed"))

        repo.save.assert_not_called()

    def test_unknown_status_string_raises(self):
        """
        Given a completely unknown status string,
        When ChangeOrderStatusUseCase is called,
        Then InvalidOrderTransitionError is raised and save is not called.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.NEW)
        repo.get_by_id.return_value = order
        uc = ChangeOrderStatusUseCase(_repo=repo)

        with pytest.raises(InvalidOrderTransitionError):
            uc(ChangeOrderStatusCommand(order_id=42, new_status="bogus_status"))

        repo.save.assert_not_called()
