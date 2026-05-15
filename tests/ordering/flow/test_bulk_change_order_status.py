"""Flow tests for BulkChangeOrderStatusUseCase.

Mocks IOrderRepo. Verifies:
- Each per-id call loads the order, changes status, and saves.
- Missing order becomes BulkFailure with reason "ORDER_NOT_FOUND".
- IllegalOrderTransitionError becomes BulkFailure with reason "illegal_transition".
- OrderAlreadyTerminalError becomes BulkFailure with reason "order_already_terminal".
- Unknown status string (ValueError path) becomes BulkFailure with reason "INVALID_TRANSITION".
- Filter mode iterates pages via cursor until exhausted.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import create_autospec, call

import pytest

from ordering.app.interfaces import IOrderRepo
from ordering.app.use_cases import (
    BulkChangeOrderStatusCommand,
    BulkChangeOrderStatusUseCase,
)
from ordering.app.errors import OrderNotFoundError
from ordering.domain import (
    IllegalOrderTransitionError,
    InvalidOrderTransitionError,
    Order,
    OrderAlreadyTerminalError,
    OrderStatus,
)
from shared.ports.driving.bulk_schemas import BulkTargetFilter, BulkTargetIds

pytestmark = pytest.mark.flow


def _ids(*xs: int) -> BulkTargetIds:
    return BulkTargetIds(ids=list(xs))


def _order(order_id: int, status: OrderStatus = OrderStatus.NEW) -> Order:
    return Order(
        id=order_id,
        name="x",
        phone="+1",
        comment="",
        status=status,
        created_at=datetime.now(),
    )


class TestBulkChangeOrderStatus:
    def test_ids_mode_happy_path_new_to_processing(self):
        """
        Given 3 orders all in NEW status,
        When BulkChangeOrderStatusUseCase runs with target status "processing",
        Then get_by_id is called 3 times, save is called 3 times, and ok=3.
        """
        # Arrange
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [
            _order(1, OrderStatus.NEW),
            _order(2, OrderStatus.NEW),
            _order(3, OrderStatus.NEW),
        ]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        # Act
        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(1, 2, 3),
                status="processing",
            )
        )

        # Assert
        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []
        assert repo.get_by_id.call_count == 3
        assert repo.save.call_count == 3

    def test_partial_failure_when_order_missing(self):
        """
        Given 3 ids where the middle one does not exist in the repo,
        When the UC runs,
        Then failed contains exactly that id with reason "ORDER_NOT_FOUND"
        and the remaining orders are processed normally.
        """
        # Arrange
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [
            _order(1, OrderStatus.NEW),
            None,
            _order(3, OrderStatus.NEW),
        ]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        # Act
        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(1, 2, 3),
                status="processing",
            )
        )

        # Assert
        assert result.total == 3
        assert result.ok == 2
        assert [f.id for f in result.failed] == [2]
        assert result.failed[0].reason == "ORDER_NOT_FOUND"

    def test_partial_failure_when_target_status_illegal(self):
        """
        Given an order in NEW status and target status DONE,
        When the UC runs,
        Then the order fails with reason "illegal_transition"
        because NEW→DONE is forbidden (non-terminal origin, invalid arc).
        """
        # Arrange
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [_order(7, OrderStatus.NEW)]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        # Act
        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(7),
                status="done",
            )
        )

        # Assert
        assert result.total == 1
        assert result.ok == 0
        assert [f.id for f in result.failed] == [7]
        assert result.failed[0].reason == "illegal_transition"
        repo.save.assert_not_called()

    def test_partial_failure_when_current_is_terminal(self):
        """
        Given an order already in DONE status,
        When the UC runs with target status "processing",
        Then the order fails with reason "order_already_terminal"
        because no transition out of a terminal state is possible.
        """
        # Arrange
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [_order(10, OrderStatus.DONE)]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        # Act
        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(10),
                status="processing",
            )
        )

        # Assert
        assert result.total == 1
        assert result.ok == 0
        assert [f.id for f in result.failed] == [10]
        assert result.failed[0].reason == "order_already_terminal"
        repo.save.assert_not_called()

    def test_partial_failure_when_target_status_unknown(self):
        """
        Given orders in NEW status and a completely unknown target status string,
        When the UC runs,
        Then all orders fail with reason "INVALID_TRANSITION" (the ValueError path,
        which wraps via InvalidOrderTransitionError with the old code).
        """
        # Arrange
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.side_effect = [
            _order(1, OrderStatus.NEW),
            _order(2, OrderStatus.NEW),
        ]
        uc = BulkChangeOrderStatusUseCase(_repo=repo)

        # Act
        result = uc(
            BulkChangeOrderStatusCommand(
                target=_ids(1, 2),
                status="bogus",
            )
        )

        # Assert
        assert result.total == 2
        assert result.ok == 0
        assert len(result.failed) == 2
        assert result.failed[0].reason == "INVALID_TRANSITION"
        assert result.failed[1].reason == "INVALID_TRANSITION"
        repo.save.assert_not_called()

    def test_filter_mode_iterates_via_cursor(self):
        """
        Given a filter target and iter_ids_by_filter returning two pages,
        When the UC runs with status "processing",
        Then all 3 ids from both pages are processed and ok=3.
        """
        # Arrange
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

        # Act
        result = uc(
            BulkChangeOrderStatusCommand(
                target=BulkTargetFilter(filter={"status__eq": "new"}),
                status="processing",
            )
        )

        # Assert
        assert result.total == 3
        assert result.ok == 3
        assert result.failed == []
        assert repo.save.call_count == 3
