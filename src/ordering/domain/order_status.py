from enum import Enum


class OrderStatus(str, Enum):
    NEW = "new"
    PROCESSING = "processing"
    DONE = "done"
    CANCELED = "canceled"
