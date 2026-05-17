from enum import Enum


class AccountType(str, Enum):
    ADMIN = "admin"
    CUSTOMER = "customer"
