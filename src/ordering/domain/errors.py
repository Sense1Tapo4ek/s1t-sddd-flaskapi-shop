from shared.generics.errors import DomainError


# ─── Order errors ────────────────────────────────────────────────────────────


class EmptyOrderError(DomainError):
    def __init__(self) -> None:
        super().__init__(message="Заказ не может быть без товаров", code="EMPTY_ORDER")


class OrderRequiresCustomerError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Для создания заказа необходим авторизованный покупатель",
            code="ORDER_REQUIRES_CUSTOMER",
        )


class CourierAddressRequiredError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Адрес доставки обязателен при выборе курьерской доставки",
            code="COURIER_ADDRESS_REQUIRED",
        )


class InvalidOrderTransitionError(DomainError):
    def __init__(self, message: str, code: str = "INVALID_ORDER_TRANSITION") -> None:
        super().__init__(message=message, code=code)

    @classmethod
    def for_transition(cls, current: str, target: str) -> "InvalidOrderTransitionError":
        return cls(f"Невозможно перевести заказ из статуса «{current}» в «{target}»")


class IllegalOrderTransitionError(InvalidOrderTransitionError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            message=f"Недопустимый переход заказа из «{current}» в «{target}»",
            code="ILLEGAL_ORDER_TRANSITION",
        )


class OrderAlreadyTerminalError(InvalidOrderTransitionError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            message=f"Заказ в финальном статусе «{current}»; переход в «{target}» невозможен",
            code="ORDER_ALREADY_TERMINAL",
        )


# ─── Inquiry errors ──────────────────────────────────────────────────────────


class InquiryCreationError(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Невозможно создать обращение: {reason}", code="INQUIRY_CREATION_FAILED"
        )


class InvalidInquiryTransitionError(DomainError):
    def __init__(self, message: str, code: str = "INVALID_TRANSITION") -> None:
        super().__init__(message=message, code=code)

    @classmethod
    def for_transition(cls, current: str, target: str) -> "InvalidInquiryTransitionError":
        return cls(f"Невозможно перевести обращение из статуса «{current}» в «{target}»")


class IllegalInquiryTransitionError(InvalidInquiryTransitionError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            message=f"Недопустимый переход обращения из «{current}» в «{target}»",
            code="illegal_transition",
        )


class InquiryAlreadyTerminalError(InvalidInquiryTransitionError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            message=f"Обращение в финальном статусе «{current}»; переход в «{target}» невозможен",
            code="inquiry_already_terminal",
        )
