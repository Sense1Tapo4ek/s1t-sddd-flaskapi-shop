"""Flow tests for BulkChangeOrderStatusUseCase and BulkArchiveOrderUseCase.

Mirrors the inquiry bulk pattern. Mocks IOrderRepo. Verifies:
- Each per-id call loads the order, changes status, and saves.
- Missing order becomes BulkFailure with reason "ORDER_NOT_FOUND".
- IllegalOrderTransitionError becomes BulkFailure with reason "ILLEGAL_ORDER_TRANSITION".
- OrderAlreadyTerminalError becomes BulkFailure with reason "ORDER_ALREADY_TERMINAL".
- Unknown status string (ValueError path) becomes BulkFailure with reason "INVALID_TRANSITION".
- Filter mode iterates pages via cursor until exhausted.
- BulkArchiveOrderUseCase archives each order and handles failures.
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import create_autospec

import pytest

from ordering.app.commands import BulkArchiveOrderCommand, BulkChangeOrderStatusCommand
from ordering.app.errors import OrderNotFoundError
from ordering.app.interfaces import IOrderRepo
from ordering.app.use_cases.bulk_change_order_status_uc import (
    BulkArchiveOrderUseCase,
    BulkChangeOrderStatusUseCase,
)
from ordering.domain import (
    DeliveryInfo,
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
)
from shared.ports.driving.bulk_schemas import BulkTargetFilter, BulkTargetIds

pytestmark = pytest.mark.flow


def _ids(*xs: int) -> BulkTargetIds:
    return BulkTargetIds(ids=list(xs))


def _order(order_id: int, status: OrderStatus = OrderStatus.NEW) -> Order:
    order = Order.place(
        customer_user_id=1,
        items=[
            OrderItem(
                product_id=1,
                title_snapshot="Widget",
                unit_price=Decimal("10.00"),
                quantity=1,
            )
        ],
        delivery=DeliveryInfo(method=DeliveryMethod.PICKUP),
    )
    order.id = order_id
    order.status = status
    return order


# ─── BulkChangeOrderStatusUseCase ────────────────────────────────────────────


class TestBulkChangeOrderStatus:
    def test_ids_mode_happy_path_new_to_confirmed(self):
        """
        Given 3 orders all in NEW status,
        When BulkChangeOrderStatusUseCase runs with target status 'confirmed',
        Then get_by_id is called 3 times, save is called 3 times, and ok=3.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [
            _order(1, OrderStatus.NEW),
            _order(2, OrderStatus.NEW),
            _order(3, OrderStatus.NEW),
        ]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(1, 2, 3),
                status="confirmed",
            )
        )

        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []
        assert repo.get_by_id.call_count == 3
        assert repo.save.call_count == 3

    def test_partial_failure_when_order_missing(self):
        """
        Given 3 ids where the middle one does not exist in the repo,
        When the UC runs,
        Then failed contains exactly that id with reason 'ORDER_NOT_FOUND'.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [
            _order(1, OrderStatus.NEW),
            None,
            _order(3, OrderStatus.NEW),
        ]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(1, 2, 3),
                status="confirmed",
            )
        )

        assert result.total == 3
        assert result.ok == 2
        assert [f.id for f in result.failed] == [2]
        assert result.failed[0].reason == "ORDER_NOT_FOUND"

    def test_partial_failure_when_target_status_illegal(self):
        """
        Given an order in CONFIRMED and target status 'new' (backwards),
        When the UC runs,
        Then the order fails with reason 'ILLEGAL_ORDER_TRANSITION'.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [_order(7, OrderStatus.CONFIRMED)]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(7),
                status="new",
            )
        )

        assert result.total == 1
        assert result.ok == 0
        assert [f.id for f in result.failed] == [7]
        assert result.failed[0].reason == "ILLEGAL_ORDER_TRANSITION"
        repo.save.assert_not_called()

    def test_partial_failure_when_current_is_terminal(self):
        """
        Given an order already in ARCHIVED status,
        When the UC runs with target status 'confirmed',
        Then the order fails with reason 'ORDER_ALREADY_TERMINAL'.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [_order(10, OrderStatus.ARCHIVED)]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(10),
                status="confirmed",
            )
        )

        assert result.total == 1
        assert result.ok == 0
        assert [f.id for f in result.failed] == [10]
        assert result.failed[0].reason == "ORDER_ALREADY_TERMINAL"
        repo.save.assert_not_called()

    def test_partial_failure_when_target_status_unknown(self):
        """
        Given orders in NEW status and a completely unknown target status string,
        When the UC runs,
        Then all orders fail with reason 'INVALID_TRANSITION'.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [
            _order(1, OrderStatus.NEW),
            _order(2, OrderStatus.NEW),
        ]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(1, 2),
                status="bogus",
            )
        )

        assert result.total == 2
        assert result.ok == 0
        assert len(result.failed) == 2
        assert result.failed[0].reason == "INVALID_ORDER_TRANSITION"
        assert result.failed[1].reason == "INVALID_ORDER_TRANSITION"
        repo.save.assert_not_called()

    def test_filter_mode_iterates_via_cursor(self):
        """
        Given a filter target and iter_ids_by_filter returning two pages,
        When the UC runs with status 'confirmed',
        Then all 3 ids from both pages are processed and ok=3.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.iter_ids_by_filter.side_effect = [
            ([1, 2], "2"),
            ([3], None),
        ]
        repo.get_by_id.side_effect = [
            _order(1, OrderStatus.NEW),
            _order(2, OrderStatus.NEW),
            _order(3, OrderStatus.NEW),
        ]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        result = uc(
            BulkChangeOrderStatusCommand(
                target=BulkTargetFilter(filter={"status__eq": "new"}),
                status="confirmed",
            )
        )

        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []
        assert repo.save.call_count == 3


# ─── BulkArchiveOrderUseCase ─────────────────────────────────────────────────


class TestBulkArchiveOrders:
    def test_archives_all_ids_successfully(self):
        """
        Given 2 orders in NEW and CONFIRMED status,
        When BulkArchiveOrderUseCase runs,
        Then both are archived and saved, ok=2.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [
            _order(1, OrderStatus.NEW),
            _order(2, OrderStatus.CONFIRMED),
        ]
        uc = BulkArchiveOrderUseCase(_repo=repo)

        result = uc(BulkArchiveOrderCommand(target=_ids(1, 2)))

        assert result.total == 2
        assert result.ok == 2
        assert result.failed == []
        assert repo.save.call_count == 2

    def test_partial_failure_when_order_missing(self):
        """
        Given one id that does not exist,
        When BulkArchiveOrderUseCase runs,
        Then that id fails with reason 'ORDER_NOT_FOUND'.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [None]
        uc = BulkArchiveOrderUseCase(_repo=repo)

        result = uc(BulkArchiveOrderCommand(target=_ids(99)))

        assert result.total == 1
        assert result.ok == 0
        assert result.failed[0].reason == "ORDER_NOT_FOUND"
        repo.save.assert_not_called()

    def test_partial_failure_when_already_archived(self):
        """
        Given an order already in ARCHIVED status,
        When BulkArchiveOrderUseCase runs,
        Then it fails with reason 'ORDER_ALREADY_TERMINAL'.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [_order(5, OrderStatus.ARCHIVED)]
        uc = BulkArchiveOrderUseCase(_repo=repo)

        result = uc(BulkArchiveOrderCommand(target=_ids(5)))

        assert result.total == 1
        assert result.ok == 0
        assert result.failed[0].reason == "ORDER_ALREADY_TERMINAL"
        repo.save.assert_not_called()

    def test_filter_mode_archives_via_cursor(self):
        """
        Given a filter target and iter_ids_by_filter returning two pages,
        When BulkArchiveOrderUseCase runs,
        Then all ids are archived and ok equals total.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.iter_ids_by_filter.side_effect = [
            ([10, 11], "11"),
            ([12], None),
        ]
        repo.get_by_id.side_effect = [
            _order(10, OrderStatus.NEW),
            _order(11, OrderStatus.CONFIRMED),
            _order(12, OrderStatus.CANCELED),
        ]
        uc = BulkArchiveOrderUseCase(_repo=repo)

        result = uc(
            BulkArchiveOrderCommand(
                target=BulkTargetFilter(filter={"status__eq": "new"}),
            )
        )

        assert result.total == 3
        assert result.ok == 3
        assert repo.save.call_count == 3
