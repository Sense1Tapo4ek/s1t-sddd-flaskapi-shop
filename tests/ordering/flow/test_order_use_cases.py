import copy

import pytest

from ordering.app import (
    DeleteOrderCommand,
    DeleteOrderUseCase,
    OrderNotFoundError,
    PlaceOrderCommand,
    PlaceOrderUseCase,
    ProcessOrderCommand,
    ProcessOrderUseCase,
)
from ordering.domain import InvalidOrderTransitionError, Order, OrderStatus


pytestmark = pytest.mark.flow


class InMemoryOrderRepo:
    def __init__(self, *, orders: list[Order] | None = None, next_id: int = 1) -> None:
        self.orders = {order.id: copy.deepcopy(order) for order in orders or []}
        self._next_id = next_id
        self.saved: list[Order] = []
        self.deleted: list[int] = []
        self.events: list[tuple[str, int]] = []

    def next_id(self) -> int:
        order_id = self._next_id
        self._next_id += 1
        return order_id

    def save(self, order: Order) -> None:
        self.events.append(("save", order.id))
        snapshot = copy.deepcopy(order)
        self.saved.append(snapshot)
        self.orders[order.id] = snapshot

    def get_by_id(self, order_id: int) -> Order | None:
        self.events.append(("get_by_id", order_id))
        return self.orders.get(order_id)

    def delete(self, order_id: int) -> None:
        self.events.append(("delete", order_id))
        self.deleted.append(order_id)
        self.orders.pop(order_id, None)


class RecordingNotificationAcl:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.orders: list[Order] = []

    def notify_new_order(self, order: Order) -> None:
        self.orders.append(order)
        if self.fail:
            raise RuntimeError("telegram is unavailable")


def _order(*, order_id: int = 1, status: OrderStatus = OrderStatus.NEW) -> Order:
    order = Order.create(
        id=order_id,
        name="Alice",
        phone="+375291234567",
        comment="Call back",
    )
    order.status = status
    return order


class TestPlaceOrderUseCase:
    def test_saves_created_order_and_notifies(self):
        """
        Given valid order input and working notification ACL,
        When placing the order,
        Then the use case saves the new order and notifies about it.
        """
        # Arrange
        repo = InMemoryOrderRepo(next_id=42)
        notification_acl = RecordingNotificationAcl()
        use_case = PlaceOrderUseCase(_repo=repo, _notification_acl=notification_acl)

        # Act
        order_id = use_case(
            PlaceOrderCommand(
                name="Alice",
                phone="+375291234567",
                comment="Leave near the door",
            )
        )

        # Assert
        assert order_id == 42
        assert len(repo.saved) == 1
        saved_order = repo.saved[0]
        assert saved_order.id == 42
        assert saved_order.name == "Alice"
        assert saved_order.phone == "+375291234567"
        assert saved_order.comment == "Leave near the door"
        assert saved_order.status is OrderStatus.NEW
        assert repo.orders[42] is saved_order
        assert notification_acl.orders[0].id == saved_order.id
        assert notification_acl.orders[0].phone == saved_order.phone

    def test_notification_failure_does_not_break_placement(self):
        """
        Given valid order input and a failing notification ACL,
        When placing the order,
        Then the order is still saved and its id is returned.
        """
        # Arrange
        repo = InMemoryOrderRepo(next_id=7)
        notification_acl = RecordingNotificationAcl(fail=True)
        use_case = PlaceOrderUseCase(_repo=repo, _notification_acl=notification_acl)

        # Act
        order_id = use_case(
            PlaceOrderCommand(name="Bob", phone="+375291111111", comment="")
        )

        # Assert
        assert order_id == 7
        assert len(repo.saved) == 1
        assert repo.saved[0].id == 7
        assert repo.orders[7] is repo.saved[0]
        assert notification_acl.orders[0].id == 7


class TestProcessOrderUseCase:
    def test_saves_valid_status_transition(self):
        """
        Given an existing order in a status with an allowed transition,
        When processing the order to the target status,
        Then the use case saves the changed order.
        """
        # Arrange
        order = _order(order_id=5, status=OrderStatus.NEW)
        repo = InMemoryOrderRepo(orders=[order])
        use_case = ProcessOrderUseCase(_repo=repo)

        # Act
        result = use_case(
            ProcessOrderCommand(order_id=5, new_status=OrderStatus.PROCESSING.value)
        )

        # Assert
        assert result == 5
        assert order.status is OrderStatus.NEW
        assert len(repo.saved) == 1
        assert repo.saved[0].status is OrderStatus.PROCESSING
        assert repo.events == [("get_by_id", 5), ("save", 5)]

    def test_missing_order_raises_not_found(self):
        """
        Given no order with the requested id,
        When processing that order,
        Then the use case raises OrderNotFoundError and does not save anything.
        """
        # Arrange
        repo = InMemoryOrderRepo()
        use_case = ProcessOrderUseCase(_repo=repo)

        # Act
        with pytest.raises(OrderNotFoundError) as exc_info:
            use_case(ProcessOrderCommand(order_id=404, new_status="processing"))

        # Assert
        assert exc_info.value.code == "ORDER_NOT_FOUND"
        assert repo.saved == []
        assert repo.events == [("get_by_id", 404)]

    def test_invalid_transition_propagates_and_does_not_save(self):
        """
        Given an existing order and a forbidden target status,
        When processing the order,
        Then the domain error propagates and the order is not saved.
        """
        # Arrange
        order = _order(order_id=9, status=OrderStatus.NEW)
        repo = InMemoryOrderRepo(orders=[order])
        use_case = ProcessOrderUseCase(_repo=repo)

        # Act
        with pytest.raises(InvalidOrderTransitionError) as exc_info:
            use_case(ProcessOrderCommand(order_id=9, new_status=OrderStatus.DONE.value))

        # Assert
        assert exc_info.value.code == "INVALID_TRANSITION"
        assert order.status is OrderStatus.NEW
        assert repo.saved == []
        assert repo.events == [("get_by_id", 9)]

    def test_unknown_status_string_raises_transition_error_and_does_not_save(self):
        """
        Given an existing order and a malformed status string,
        When processing the order,
        Then the use case raises a domain transition error and the order is not saved.
        """
        # Arrange
        order = _order(order_id=13, status=OrderStatus.NEW)
        repo = InMemoryOrderRepo(orders=[order])
        use_case = ProcessOrderUseCase(_repo=repo)

        # Act
        with pytest.raises(InvalidOrderTransitionError) as exc_info:
            use_case(ProcessOrderCommand(order_id=13, new_status="shipped"))

        # Assert
        assert exc_info.value.code == "INVALID_TRANSITION"
        assert repo.saved == []
        assert repo.events == [("get_by_id", 13)]


class TestDeleteOrderUseCase:
    def test_checks_existence_before_delete(self):
        """
        Given an existing order,
        When deleting the order,
        Then the use case checks existence before deleting it.
        """
        # Arrange
        order = _order(order_id=11)
        repo = InMemoryOrderRepo(orders=[order])
        use_case = DeleteOrderUseCase(_repo=repo)

        # Act
        use_case(DeleteOrderCommand(order_id=11))

        # Assert
        assert repo.deleted == [11]
        assert 11 not in repo.orders
        assert repo.events == [("get_by_id", 11), ("delete", 11)]

    def test_missing_order_raises_not_found_without_delete(self):
        """
        Given no order with the requested id,
        When deleting that order,
        Then the use case raises OrderNotFoundError and does not delete anything.
        """
        # Arrange
        repo = InMemoryOrderRepo()
        use_case = DeleteOrderUseCase(_repo=repo)

        # Act
        with pytest.raises(OrderNotFoundError) as exc_info:
            use_case(DeleteOrderCommand(order_id=404))

        # Assert
        assert exc_info.value.code == "ORDER_NOT_FOUND"
        assert repo.deleted == []
        assert repo.events == [("get_by_id", 404)]
