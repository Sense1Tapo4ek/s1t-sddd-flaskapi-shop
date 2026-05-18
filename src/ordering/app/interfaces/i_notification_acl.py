from typing import Protocol, runtime_checkable
from ordering.domain.inquiry_agg import Inquiry


@runtime_checkable
class INotificationAcl(Protocol):
    def notify_inquiry_created(self, inquiry: Inquiry) -> None: ...
