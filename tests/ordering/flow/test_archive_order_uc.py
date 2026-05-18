"""Flow tests for ArchiveOrderUseCase."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import create_autospec

import pytest

from ordering.app.commands import ArchiveOrderCommand
from ordering.app.errors import OrderNotFoundError
from ordering.app.interfaces import IOrderRepo
from ordering.app.use_cases.archive_order_uc import ArchiveOrderUseCase
from ordering.domain import (
    DeliveryInfo,
    DeliveryMethod,
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
                unit_price=Decimal("15.00"),
                quantity=1,
            )
        ],
        delivery=DeliveryInfo(method=DeliveryMethod.PICKUP),
    )
    order.id = 7
    order.status = status
    return order


class TestArchiveOrderHappyPath:
    def test_archive_new_order_succeeds(self):
        """
        Given an order in NEW status,
        When ArchiveOrderUseCase is called,
        Then the order status becomes ARCHIVED and its id is returned.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.NEW)
        repo.get_by_id.return_value = order
        uc = ArchiveOrderUseCase(_repo=repo)

        result = uc(ArchiveOrderCommand(order_id=7))

        assert result == 7
        assert order.status is OrderStatus.ARCHIVED
        repo.save.assert_called_once_with(order)

    def test_archive_confirmed_order_succeeds(self):
        """
        Given an order in CONFIRMED status,
        When ArchiveOrderUseCase is called,
        Then the order status becomes ARCHIVED.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.CONFIRMED)
        repo.get_by_id.return_value = order
        uc = ArchiveOrderUseCase(_repo=repo)

        result = uc(ArchiveOrderCommand(order_id=7))

        assert result == 7
        assert order.status is OrderStatus.ARCHIVED

    def test_archive_completed_order_succeeds(self):
        """
        Given an order in COMPLETED status,
        When ArchiveOrderUseCase is called,
        Then the order status becomes ARCHIVED.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.COMPLETED)
        repo.get_by_id.return_value = order
        uc = ArchiveOrderUseCase(_repo=repo)

        uc(ArchiveOrderCommand(order_id=7))

        assert order.status is OrderStatus.ARCHIVED
        repo.save.assert_called_once()

    def test_archive_canceled_order_succeeds(self):
        """
        Given an order in CANCELED status,
        When ArchiveOrderUseCase is called,
        Then the order status becomes ARCHIVED.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.CANCELED)
        repo.get_by_id.return_value = order
        uc = ArchiveOrderUseCase(_repo=repo)

        uc(ArchiveOrderCommand(order_id=7))

        assert order.status is OrderStatus.ARCHIVED


class TestArchiveOrderErrors:
    def test_order_not_found_raises(self):
        """
        Given no order in the repo for the given id,
        When ArchiveOrderUseCase is called,
        Then OrderNotFoundError is raised and save is not called.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.return_value = None
        uc = ArchiveOrderUseCase(_repo=repo)

        with pytest.raises(OrderNotFoundError) as exc_info:
            uc(ArchiveOrderCommand(order_id=99))

        assert exc_info.value.code == "ORDER_NOT_FOUND"
        repo.save.assert_not_called()

    def test_already_archived_raises(self):
        """
        Given an order already in ARCHIVED (terminal) status,
        When ArchiveOrderUseCase is called,
        Then OrderAlreadyTerminalError is raised and save is not called.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        order = _order(OrderStatus.ARCHIVED)
        repo.get_by_id.return_value = order
        uc = ArchiveOrderUseCase(_repo=repo)

        with pytest.raises(OrderAlreadyTerminalError):
            uc(ArchiveOrderCommand(order_id=7))

        repo.save.assert_not_called()
