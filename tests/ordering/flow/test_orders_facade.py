"""Flow tests for OrdersFacade.

Round-trips through the facade with mocked use cases and repos.
Verifies the facade correctly delegates to use cases and maps schemas.
"""
from __future__ import annotations

import copy
from decimal import Decimal
from unittest.mock import MagicMock, create_autospec

import pytest

from ordering.app.errors import OrderNotFoundError
from ordering.app.interfaces import IOrderRepo, IProductLookupACL, ProductSnapshot
from ordering.app.use_cases.place_order_uc import PlaceOrderUseCase
from ordering.app.use_cases.change_order_status_uc import ChangeOrderStatusUseCase
from ordering.app.use_cases.archive_order_uc import ArchiveOrderUseCase
from ordering.app.use_cases.create_demo_data_uc import CreateDemoOrderingDataUseCase
from ordering.app.use_cases.create_test_order_uc import CreateTestOrderUseCase
from ordering.app.queries.get_order_by_id_query import GetOrderByIdQuery
from ordering.app.queries.get_orders_query import GetOrdersQuery
from ordering.domain import (
    DeliveryInfo,
    DeliveryMethod,
    Order,
    OrderItem,
    OrderStatus,
)
from ordering.ports.driving.orders_facade import OrdersFacade
from ordering.ports.driving.schemas import (
    OrderIn,
    OrderItemIn,
    OrderOut,
    OrderStatusUpdateIn,
)
from shared.generics.pagination import PaginatedResult

pytestmark = pytest.mark.flow


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_order(order_id: int = 1) -> Order:
    order = Order.place(
        customer_user_id=5,
        items=[
            OrderItem(
                product_id=10,
                title_snapshot="Gadget",
                unit_price=Decimal("25.00"),
                quantity=2,
            )
        ],
        delivery=DeliveryInfo(method=DeliveryMethod.PICKUP),
    )
    order.id = order_id
    return order


def _make_facade(
    place_uc=None,
    change_status_uc=None,
    archive_uc=None,
    get_query=None,
    get_by_id_query=None,
    demo_uc=None,
    test_order_uc=None,
) -> OrdersFacade:
    return OrdersFacade(
        _place_uc=place_uc or MagicMock(spec=PlaceOrderUseCase),
        _change_status_uc=change_status_uc or MagicMock(spec=ChangeOrderStatusUseCase),
        _archive_uc=archive_uc or MagicMock(spec=ArchiveOrderUseCase),
        _get_query=get_query or MagicMock(spec=GetOrdersQuery),
        _get_by_id_query=get_by_id_query or MagicMock(spec=GetOrderByIdQuery),
        _demo_uc=demo_uc or MagicMock(spec=CreateDemoOrderingDataUseCase),
        _test_order_uc=test_order_uc or MagicMock(spec=CreateTestOrderUseCase),
    )


# ─── place_order ──────────────────────────────────────────────────────────────


class TestFacadePlaceOrder:
    def test_delegates_to_place_uc_and_returns_id(self):
        """
        Given a valid OrderIn schema and customer_user_id,
        When facade.place_order() is called,
        Then PlaceOrderUseCase is invoked with a PlaceOrderCommand and the id is returned.
        """
        place_uc = MagicMock(spec=PlaceOrderUseCase)
        place_uc.return_value = 42
        facade = _make_facade(place_uc=place_uc)

        schema = OrderIn(
            items=[OrderItemIn(product_id=1, quantity=3)],
            delivery_method="pickup",
            contact_phone="+375 29 000-00-00",
        )
        result = facade.place_order(schema, customer_user_id=5)

        assert result == 42
        place_uc.assert_called_once()
        cmd = place_uc.call_args[0][0]
        assert cmd.customer_user_id == 5
        assert cmd.items[0].product_id == 1
        assert cmd.items[0].quantity == 3


# ─── get_order ────────────────────────────────────────────────────────────────


class TestFacadeGetOrder:
    def test_returns_order_out_for_existing_order(self):
        """
        Given an order in the repo,
        When facade.get_order(id) is called,
        Then an OrderOut is returned with correct fields.
        """
        order = _make_order(7)
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.return_value = order
        get_by_id_query = GetOrderByIdQuery(_repo=repo)
        facade = _make_facade(get_by_id_query=get_by_id_query)

        result = facade.get_order(7)

        assert isinstance(result, OrderOut)
        assert result.id == 7
        assert result.customer_user_id == 5
        assert result.total == Decimal("50.00")
        assert result.status == "new"
        assert len(result.items) == 1
        assert result.items[0].title_snapshot == "Gadget"

    def test_raises_order_not_found_for_missing_order(self):
        """
        Given no order in the repo for the given id,
        When facade.get_order(id) is called,
        Then OrderNotFoundError is raised.
        """
        repo = create_autospec(IOrderRepo, instance=True)
        repo.get_by_id.return_value = None
        get_by_id_query = GetOrderByIdQuery(_repo=repo)
        facade = _make_facade(get_by_id_query=get_by_id_query)

        with pytest.raises(OrderNotFoundError) as exc_info:
            facade.get_order(99)

        assert exc_info.value.code == "ORDER_NOT_FOUND"


# ─── change_order_status ──────────────────────────────────────────────────────


class TestFacadeChangeOrderStatus:
    def test_delegates_to_change_status_uc(self):
        """
        Given an OrderStatusUpdateIn schema,
        When facade.change_order_status() is called,
        Then ChangeOrderStatusUseCase is invoked with the correct command.
        """
        change_uc = MagicMock(spec=ChangeOrderStatusUseCase)
        change_uc.return_value = 3
        facade = _make_facade(change_status_uc=change_uc)

        schema = OrderStatusUpdateIn(status="confirmed")
        result = facade.change_order_status(order_id=3, schema=schema)

        assert result == 3
        change_uc.assert_called_once()
        cmd = change_uc.call_args[0][0]
        assert cmd.order_id == 3
        assert cmd.new_status == "confirmed"


# ─── archive_order ────────────────────────────────────────────────────────────


class TestFacadeArchiveOrder:
    def test_delegates_to_archive_uc(self):
        """
        Given a valid order id,
        When facade.archive_order() is called,
        Then ArchiveOrderUseCase is invoked with an ArchiveOrderCommand.
        """
        archive_uc = MagicMock(spec=ArchiveOrderUseCase)
        archive_uc.return_value = 5
        facade = _make_facade(archive_uc=archive_uc)

        result = facade.archive_order(order_id=5)

        assert result == 5
        archive_uc.assert_called_once()
        cmd = archive_uc.call_args[0][0]
        assert cmd.order_id == 5


# ─── list_orders ──────────────────────────────────────────────────────────────


class TestFacadeListOrders:
    def test_delegates_to_get_query_and_maps_result(self):
        """
        Given a paginated result from the repo,
        When facade.list_orders() is called,
        Then PaginatedOrdersOut is returned with correct item count and total.
        """
        order = _make_order(1)
        paginated = PaginatedResult(items=[order], total=1, page=1, limit=20)
        get_query = MagicMock(spec=GetOrdersQuery)
        get_query.return_value = paginated
        facade = _make_facade(get_query=get_query)

        result = facade.list_orders(page=1, limit=20)

        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == 1
        get_query.assert_called_once()

    def test_list_orders_passes_filters_to_query(self):
        """
        Given filter parameters,
        When facade.list_orders() is called with filters,
        Then GetOrdersQuery is called with those filter values.
        """
        paginated = PaginatedResult(items=[], total=0, page=1, limit=20)
        get_query = MagicMock(spec=GetOrdersQuery)
        get_query.return_value = paginated
        facade = _make_facade(get_query=get_query)

        facade.list_orders(
            page=2,
            limit=10,
            sort_by="created_at",
            sort_dir="asc",
            filters={"status": "new"},
        )

        call_kwargs = get_query.call_args[1]
        assert call_kwargs["page"] == 2
        assert call_kwargs["limit"] == 10
        assert call_kwargs["sort_by"] == "created_at"
        assert call_kwargs["sort_dir"] == "asc"
        assert call_kwargs["filters"] == {"status": "new"}
