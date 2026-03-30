from shared.generics.errors import ApplicationError, DomainError


class ProductNotFoundError(ApplicationError):
    def __init__(self, product_id: int) -> None:
        super().__init__(
            message=f"Товар {product_id} не найден", code="PRODUCT_NOT_FOUND"
        )


class InvalidProductError(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Некорректные данные товара: {reason}", code="INVALID_PRODUCT"
        )
