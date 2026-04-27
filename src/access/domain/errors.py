from shared.generics.errors import DomainError, ApplicationError


class AdminNotFoundError(ApplicationError):
    def __init__(self, admin_id: int) -> None:
        super().__init__(message=f"Admin {admin_id} not found", code="ADMIN_NOT_FOUND")


class InvalidPasswordError(DomainError):
    def __init__(self) -> None:
        super().__init__(message="Неверный текущий пароль", code="INVALID_PASSWORD")


class AdminInactiveError(DomainError):
    def __init__(self) -> None:
        super().__init__(message="Аккаунт отключён", code="ADMIN_INACTIVE")


class TelegramLoginUnavailableError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Telegram-вход для этого пользователя не настроен",
            code="TELEGRAM_LOGIN_UNAVAILABLE",
        )


class PasswordConfirmationRequiredError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Введите текущий пароль или подтвердите смену кодом из Telegram",
            code="PASSWORD_CONFIRMATION_REQUIRED",
        )


class WeakPasswordError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Пароль должен быть не короче 5 символов",
            code="WEAK_PASSWORD",
        )


class RecoveryCodeCooldownError(DomainError):
    def __init__(self, seconds_remaining: int) -> None:
        super().__init__(
            message=f"Код уже отправлен. Повторите через {seconds_remaining} сек.",
            code="RECOVERY_CODE_COOLDOWN",
        )


class RecoveryCodeLockedError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Слишком много неверных кодов. Попробуйте позже.",
            code="RECOVERY_CODE_LOCKED",
        )
