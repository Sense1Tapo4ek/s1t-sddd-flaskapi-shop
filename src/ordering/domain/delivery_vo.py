from dataclasses import dataclass
from enum import Enum

from .errors import CourierAddressRequiredError


class DeliveryMethod(str, Enum):
    PICKUP = "pickup"
    COURIER = "courier"


@dataclass(frozen=True, slots=True, kw_only=True)
class DeliveryInfo:
    """
    Value Object: delivery configuration for an Order.
    Invariant: courier delivery requires a non-empty address.
    """

    method: DeliveryMethod
    address: str = ""
    comment: str = ""

    def __post_init__(self) -> None:
        if self.method == DeliveryMethod.COURIER and not self.address.strip():
            raise CourierAddressRequiredError()
