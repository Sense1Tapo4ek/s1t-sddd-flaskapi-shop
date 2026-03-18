from shared.generics.errors import ApplicationError


class OrderNotFoundError(ApplicationError):
    def __init__(self, order_id: int) -> None:
        super().__init__(message=f"Заказ {order_id} не найден", code="ORDER_NOT_FOUND")
