from enum import Enum


class OrderStatus(str, Enum):
    NEW = "new"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELED = "canceled"
    ARCHIVED = "archived"
