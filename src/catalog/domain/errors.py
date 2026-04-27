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


class CategoryNotFoundError(ApplicationError):
    def __init__(self, category_id: int) -> None:
        super().__init__(
            message=f"Категория {category_id} не найдена", code="CATEGORY_NOT_FOUND"
        )


class TagNotFoundError(ApplicationError):
    def __init__(self, tag_id: int) -> None:
        super().__init__(
            message=f"Тег {tag_id} не найден", code="TAG_NOT_FOUND"
        )


class AttributeNotFoundError(ApplicationError):
    def __init__(self, attribute_id: int) -> None:
        super().__init__(
            message=f"Атрибут {attribute_id} не найден", code="ATTRIBUTE_NOT_FOUND"
        )


class InvalidCategoryTreeError(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Некорректное дерево категорий: {reason}",
            code="INVALID_CATEGORY_TREE",
        )


class InvalidAttributeError(DomainError):
    def __init__(self, reason: str) -> None:
        super().__init__(
            message=f"Некорректный атрибут: {reason}", code="INVALID_ATTRIBUTE"
        )
