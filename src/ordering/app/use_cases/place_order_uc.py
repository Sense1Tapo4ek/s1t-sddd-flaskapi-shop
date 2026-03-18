import logging
from dataclasses import dataclass

from ..interfaces import IOrderRepo, INotificationAcl
from ..commands import PlaceOrderCommand
from ...domain import Order

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class PlaceOrderUseCase:
    _repo: IOrderRepo
    _notification_acl: INotificationAcl

    def __call__(self, cmd: PlaceOrderCommand) -> int:
        # 1. Identity generation (Workaround for non-UUID systems using int IDs)
        # In a real UUID system, we'd generate uuid4() here.
        new_id = self._repo.next_id()

        # 2. Create Aggregate
        order = Order.create(
            id=new_id, name=cmd.name, phone=cmd.phone, comment=cmd.comment
        )

        # 3. Persist
        self._repo.save(order)

        # 4. Notify (Side Effect)
        # Notification failure must not break order placement.
        try:
            self._notification_acl.notify_new_order(order)
        except Exception:
            logger.exception("Notification failed for order %s", order.id)

        return order.id
