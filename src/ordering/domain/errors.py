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
