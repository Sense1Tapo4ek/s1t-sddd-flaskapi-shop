from shared.generics.errors import DomainError, ApplicationError


class AdminNotFoundError(ApplicationError):
    def __init__(self, admin_id: int) -> None:
        super().__init__(message=f"Admin {admin_id} not found", code="ADMIN_NOT_FOUND")


class InvalidPasswordError(DomainError):
    def __init__(self) -> None:
        super().__init__(message="Неверный текущий пароль", code="INVALID_PASSWORD")
