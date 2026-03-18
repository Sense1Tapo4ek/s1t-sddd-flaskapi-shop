from shared.generics.errors import DomainError, ApplicationError

class SettingsNotFoundError(DomainError):
    def __init__(self) -> None:
        super().__init__(message="Site settings not found", code="SETTINGS_NOT_FOUND")

class TelegramTokenInvalidError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            message="Неверный Bot Token. Проверьте правильность токена от @BotFather.",
            code="INVALID_TELEGRAM_TOKEN"
        )

class TelegramBotNotStartedError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            message="Нет новых событий. Отправьте /start боту и повторите попытку.",
            code="BOT_NOT_STARTED"
        )

class TelegramStartNotFoundError(ApplicationError):
    def __init__(self) -> None:
        super().__init__(
            message="Команда /start не найдена. Пожалуйста, отправьте боту именно /start.",
            code="START_MESSAGE_NOT_FOUND"
        )
