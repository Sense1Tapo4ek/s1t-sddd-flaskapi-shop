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

        if not settings.telegram_bot_token:
            raise TelegramNotConfiguredError()

        # Cross-context boundary call via ACL
        login, chat_id, code = self._access_acl.request_recovery_code()
        if not chat_id:
            self._access_acl.clear_recovery_code()
            raise TelegramNotConfiguredError()

        text = (
            "<b>Login Code</b>\n\n"
            f"Account: <code>{login}</code>\n"
            "Your one-time code:\n"
            f"<code>{code}</code>\n\n"
            "Valid for 5 minutes."
        )
        sent = self._client.send_message(
            token=settings.telegram_bot_token,
            chat_id=chat_id,
            text=text,
        )
        if not sent:
            self._access_acl.clear_recovery_code()
        return sent
