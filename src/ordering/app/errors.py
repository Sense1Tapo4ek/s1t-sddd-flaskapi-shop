from shared.generics.errors import ApplicationError


class InquiryNotFoundError(ApplicationError):
    def __init__(self, inquiry_id: int) -> None:
        super().__init__(message=f"Обращение {inquiry_id} не найдено", code="INQUIRY_NOT_FOUND")


class OrderNotFoundError(ApplicationError):
    def __init__(self, order_id: int) -> None:
        super().__init__(message=f"Заказ {order_id} не найден", code="ORDER_NOT_FOUND")


class ProductNotFoundForOrderError(ApplicationError):
    def __init__(self, product_id: int) -> None:
        super().__init__(
            message=f"Товар {product_id} не найден",
            code="PRODUCT_NOT_FOUND_FOR_ORDER",
        )


class InactiveProductInOrderError(ApplicationError):
    def __init__(self, product_id: int) -> None:
        super().__init__(
            message=f"Товар {product_id} недоступен для заказа",
            code="INACTIVE_PRODUCT_IN_ORDER",
        )
