from dataclasses import dataclass
from decimal import Decimal

from ..commands import PlaceOrderCommand
from ..errors import InactiveProductInOrderError, ProductNotFoundForOrderError
from ..interfaces import INotificationAcl, IOrderRepo
from ..interfaces.i_product_lookup_acl import IProductLookupACL
from ...domain import DeliveryInfo, DeliveryMethod, Order, OrderItem


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderUseCase:
    _repo: IOrderRepo
    _product_acl: IProductLookupACL
    _notification_acl: INotificationAcl

    def __call__(self, cmd: PlaceOrderCommand) -> int:
        # 1. Snapshot each product via ACL
        items: list[OrderItem] = []
        for cmd_item in cmd.items:
            snapshot = self._product_acl.get(cmd_item.product_id)
            if snapshot is None:
                raise ProductNotFoundForOrderError(cmd_item.product_id)
            if not snapshot.is_active:
                raise InactiveProductInOrderError(cmd_item.product_id)
            items.append(
                OrderItem(
                    product_id=snapshot.id,
                    title_snapshot=snapshot.title,
                    unit_price=snapshot.unit_price,
                    quantity=cmd_item.quantity,
                )
            )

        # 2. Build delivery VO (may raise CourierAddressRequiredError)
        delivery = DeliveryInfo(
            method=DeliveryMethod(cmd.delivery_method),
            address=cmd.address,
            comment=cmd.delivery_comment,
        )

        # 3. Create domain aggregate (may raise OrderRequiresCustomerError / EmptyOrderError)
        order = Order.place(
            customer_user_id=cmd.customer_user_id,
            items=items,
            delivery=delivery,
            comment=cmd.comment,
        )

        # 4. Persist
        self._repo.save(order)

        # 5. Notify — Stage 7 will implement the body; failure must not break placement
        # TODO Stage 7: pass customer_email from ACL or cmd; move logging to ACL adapter
        try:
            self._notification_acl.notify_order_placed(order, customer_email=None)
        except Exception:  # noqa: BLE001 — notification failure is non-fatal by design
            pass

        return order.id
