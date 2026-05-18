from typing import Protocol, runtime_checkable
from ordering.domain.inquiry_agg import Inquiry
from ordering.domain.order_agg import Order


@runtime_checkable
class INotificationAcl(Protocol):
    def notify_inquiry_created(self, inquiry: Inquiry) -> None: ...
    def notify_order_placed(self, order: Order, customer_email: str | None = None) -> None:
        # Stage 7: default no-op so existing SystemNotificationAcl keeps compiling.
        ...
