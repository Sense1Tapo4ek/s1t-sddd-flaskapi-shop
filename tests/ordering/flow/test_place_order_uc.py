"""Flow tests for PlaceOrderUseCase."""
from __future__ import annotations

import copy
from decimal import Decimal
from unittest.mock import create_autospec

import pytest

from ordering.app.commands import PlaceOrderCommand, PlaceOrderItem
from ordering.app.errors import InactiveProductInOrderError, ProductNotFoundForOrderError
from ordering.app.interfaces import INotificationAcl, IOrderRepo
from ordering.app.interfaces.i_product_lookup_acl import IProductLookupACL, ProductSnapshot
from ordering.app.use_cases.place_order_uc import PlaceOrderUseCase
from ordering.domain import (
    CourierAddressRequiredError,
    Order,
    OrderStatus,
)

pytestmark = pytest.mark.flow


def _snapshot(product_id: int = 1, price: str = "10.00", active: bool = True) -> ProductSnapshot:
    return ProductSnapshot(
        id=product_id,
        title=f"Product {product_id}",
        unit_price=Decimal(price),
        is_active=active,
    )


class InMemoryOrderRepo:
    def __init__(self) -> None:
        self.saved: list[Order] = []
        self._next_id = 1

    def next_id(self) -> int:
        return 0

    def save(self, order: Order) -> None:
        if order.id == 0:
            order.id = self._next_id
            self._next_id += 1
        self.saved.append(copy.deepcopy(order))

    def get_by_id(self, order_id: int) -> Order | None:
        for o in self.saved:
            if o.id == order_id:
                return o
        return None

    def get_paginated(self, params):
        raise NotImplementedError

    def iter_ids_by_filter(self, filter_payload, *, cursor, limit):
        raise NotImplementedError


class RecordingNotificationAcl:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.order_notifications: list[tuple] = []

    def notify_inquiry_created(self, inquiry) -> None:
        pass

    def notify_order_placed(self, order, customer_email=None) -> None:
        self.order_notifications.append((order, customer_email))
        if self.fail:
            raise RuntimeError("telegram unavailable")


class InMemoryProductACL:
    def __init__(self, snapshots: dict[int, ProductSnapshot] | None = None) -> None:
        self._data: dict[int, ProductSnapshot] = snapshots or {}

    def get(self, product_id: int) -> ProductSnapshot | None:
        return self._data.get(product_id)


def _cmd(
    customer_user_id: int = 1,
    items: list[tuple[int, int]] | None = None,
    delivery_method: str = "pickup",
    address: str = "",
) -> PlaceOrderCommand:
    if items is None:
        items = [(1, 2)]
    return PlaceOrderCommand(
        customer_user_id=customer_user_id,
        items=[PlaceOrderItem(product_id=p, quantity=q) for p, q in items],
        delivery_method=delivery_method,
        address=address,
        contact_phone="+375 29 000-00-00",
        contact_email="cust@example.com",
    )


class TestPlaceOrderHappyPath:
    def test_places_order_and_assigns_id(self):
        """
        Given a valid command and active products,
        When PlaceOrderUseCase runs,
        Then the order is saved with a non-zero id and status NEW.
        """
        acl = InMemoryProductACL({1: _snapshot(1, "20.00")})
        repo = InMemoryOrderRepo()
        notif = RecordingNotificationAcl()
        uc = PlaceOrderUseCase(_repo=repo, _product_acl=acl, _notification_acl=notif)

        order_id = uc(_cmd(customer_user_id=5, items=[(1, 3)]))

        assert order_id == 1
        assert len(repo.saved) == 1
        saved = repo.saved[0]
        assert saved.customer_user_id == 5
        assert saved.status is OrderStatus.NEW
        assert saved.total == Decimal("60.00")
        assert len(saved.items) == 1
        assert saved.items[0].title_snapshot == "Product 1"
        assert notif.order_notifications[0][0].id == order_id

    def test_notification_failure_does_not_break_placement(self):
        """
        Given a failing notification ACL,
        When placing an order,
        Then the order is still saved and its id returned.
        """
        acl = InMemoryProductACL({1: _snapshot(1)})
        repo = InMemoryOrderRepo()
        notif = RecordingNotificationAcl(fail=True)
        uc = PlaceOrderUseCase(_repo=repo, _product_acl=acl, _notification_acl=notif)

        order_id = uc(_cmd())

        assert order_id == 1
        assert len(repo.saved) == 1


class TestPlaceOrderErrors:
    def test_missing_product_raises(self):
        """
        Given a product_id not in the catalog ACL,
        When placing an order,
        Then ProductNotFoundForOrderError is raised.
        """
        acl = InMemoryProductACL({})
        repo = InMemoryOrderRepo()
        notif = RecordingNotificationAcl()
        uc = PlaceOrderUseCase(_repo=repo, _product_acl=acl, _notification_acl=notif)

        with pytest.raises(ProductNotFoundForOrderError) as exc_info:
            uc(_cmd(items=[(99, 1)]))

        assert exc_info.value.code == "PRODUCT_NOT_FOUND_FOR_ORDER"
        assert repo.saved == []

    def test_inactive_product_raises(self):
        """
        Given a product marked is_active=False in the catalog ACL,
        When placing an order,
        Then InactiveProductInOrderError is raised.
        """
        acl = InMemoryProductACL({1: _snapshot(1, active=False)})
        repo = InMemoryOrderRepo()
        notif = RecordingNotificationAcl()
        uc = PlaceOrderUseCase(_repo=repo, _product_acl=acl, _notification_acl=notif)

        with pytest.raises(InactiveProductInOrderError) as exc_info:
            uc(_cmd(items=[(1, 1)]))

        assert exc_info.value.code == "INACTIVE_PRODUCT_IN_ORDER"
        assert repo.saved == []

    def test_courier_without_address_raises(self):
        """
        Given delivery_method=courier with no address,
        When placing an order,
        Then CourierAddressRequiredError is raised.
        """
        acl = InMemoryProductACL({1: _snapshot(1)})
        repo = InMemoryOrderRepo()
        notif = RecordingNotificationAcl()
        uc = PlaceOrderUseCase(_repo=repo, _product_acl=acl, _notification_acl=notif)

        with pytest.raises(CourierAddressRequiredError):
            uc(_cmd(delivery_method="courier", address=""))

        assert repo.saved == []
