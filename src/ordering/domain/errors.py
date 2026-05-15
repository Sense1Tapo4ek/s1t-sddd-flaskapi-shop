from shared.generics.errors import DomainError


class OrderCreationError(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Невозможно создать заказ: {reason}", code="ORDER_CREATION_FAILED"
        )


class InvalidOrderTransitionError(DomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            message=f"Невозможно перевести заказ из статуса «{current}» в «{target}»",
            code="INVALID_TRANSITION",
        )


class IllegalOrderTransitionError(InvalidOrderTransitionError):
    def __init__(self, current: str, target: str) -> None:
        # Call DomainError directly to avoid re-wrapping the message/code
        DomainError.__init__(
            self,
            message=f"Недопустимый переход заказа из «{current}» в «{target}»",
            code="illegal_transition",
        )


class OrderAlreadyTerminalError(InvalidOrderTransitionError):
    def __init__(self, current: str, target: str) -> None:
        DomainError.__init__(
            self,
            message=f"Заказ в финальном статусе «{current}»; переход в «{target}» невозможен",
            code="order_already_terminal",
        )
