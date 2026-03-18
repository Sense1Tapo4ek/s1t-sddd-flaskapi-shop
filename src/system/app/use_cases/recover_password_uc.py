from dataclasses import dataclass
from shared.generics.errors import DomainError
from ...domain import SettingsNotFoundError
from ...domain.errors import TelegramTokenInvalidError
from ..interfaces.i_settings_repo import ISettingsRepo
from ..interfaces.i_access_acl import IAccessAcl
from shared.adapters.driven.telegram_client import TelegramClient


class TelegramNotConfiguredError(DomainError):
    def __init__(self) -> None:
        super().__init__(
            message="Cannot recover password: Telegram is not configured",
            code="TELEGRAM_NOT_CONFIGURED",
        )
        self.user_message = "Telegram-бот не настроен. Обратитесь к администратору."


@dataclass(frozen=True, slots=True, kw_only=True)
class RecoverPasswordUseCase:
    """
    Orchestrates password recovery:
    1. Validates Telegram config.
    2. Resets password via Access ACL.
    3. Dispatches new password via Telegram.
    """

    _repo: ISettingsRepo
    _client: TelegramClient
    _access_acl: IAccessAcl

    def __call__(self) -> bool:
        settings = self._repo.get()
        if settings is None:
            raise SettingsNotFoundError()

        if not settings.is_telegram_configured:
            raise TelegramNotConfiguredError()

        # Cross-context boundary call via ACL
        code = self._access_acl.generate_recovery_code()

        text = f"<b>Login Code</b>\n\nYour one-time code:\n<code>{code}</code>\n\nValid for 5 minutes."
        return self._client.send_message(
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            text=text,
        )
