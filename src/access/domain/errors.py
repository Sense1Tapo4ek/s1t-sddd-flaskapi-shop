from shared.generics.errors import ApplicationError, DomainError, DrivenPortError


class AdminNotFoundError(ApplicationError):
    def __init__(self, admin_id: int) -> None:
        super().__init__(message=f"Администратор {admin_id} не найден", code="ADMIN_NOT_FOUND")


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
    def __init__(self, min_length: int = 5) -> None:
        self.min_length = min_length
        super().__init__(
            message=f"Пароль должен быть не короче {min_length} символов",
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


class CustomerInactiveError(DomainError):
    def __init__(self) -> None:
        super().__init__(message="Аккаунт клиента отключён", code="CUSTOMER_INACTIVE")


class EmailAlreadyRegisteredError(DomainError):
    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(
            message=f"Email {email} уже зарегистрирован",
            code="EMAIL_ALREADY_REGISTERED",
        )


class CustomerNotFoundError(ApplicationError):
    def __init__(self, customer_id: int) -> None:
        self.customer_id = customer_id
        super().__init__(
            message=f"Клиент {customer_id} не найден",
            code="CUSTOMER_NOT_FOUND",
        )


class InvalidRecoveryCodeError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Неверный или просроченный код",
            code="INVALID_RECOVERY_CODE",
        )


class EmailRecoveryFailedError(DrivenPortError):
    def __init__(self) -> None:
        super().__init__(
            message="Не удалось отправить письмо. Попробуйте позже.",
            code="EMAIL_DELIVERY_FAILED",
        )
