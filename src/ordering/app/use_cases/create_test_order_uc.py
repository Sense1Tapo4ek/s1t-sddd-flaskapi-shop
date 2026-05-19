from __future__ import annotations

from dataclasses import dataclass

from ..errors import ProductNotFoundForOrderError
from ..interfaces import IOrderRepo, IProductLookupACL
from ..interfaces.i_product_lookup_acl import ProductSnapshot
from ...domain import DeliveryInfo, DeliveryMethod, Order, OrderItem


_TEST_CUSTOMER_USER_ID = 900001
_SCAN_LIMIT = 400


@dataclass(frozen=True, slots=True, kw_only=True)
class CreateTestOrderUseCase:
    """Admin-only: create ONE order with a randomly picked active product.

    Picks the first active product visible via IProductLookupACL. Used to
    populate the admin requests page for QA / demo. Raises
    ProductNotFoundForOrderError when the catalog has no active products.
    """

    _orders: IOrderRepo
    _product_acl: IProductLookupACL

    def __call__(self) -> int:
        snapshot = self._first_active_product()
        if snapshot is None:
            raise ProductNotFoundForOrderError(0)

        items = [
            OrderItem(
                product_id=snapshot.id,
                title_snapshot=snapshot.title,
                unit_price=snapshot.unit_price,
                quantity=1,
            )
        ]
        delivery = DeliveryInfo(
            method=DeliveryMethod.PICKUP,
            address="",
            comment="Тестовый заказ",
        )
        order = Order.place(
            customer_user_id=_TEST_CUSTOMER_USER_ID,
            items=items,
            delivery=delivery,
            contact_phone="+375 29 000-00-00",
            contact_email="test.customer@example.com",
            comment="Создан через кнопку «Создать тестовый заказ»",
        )
        self._orders.save(order)
        return order.id

    def _first_active_product(self) -> ProductSnapshot | None:
        for product_id in range(1, _SCAN_LIMIT + 1):
            snapshot = self._product_acl.get(product_id)
            if snapshot is not None and snapshot.is_active:
                return snapshot
        return None
