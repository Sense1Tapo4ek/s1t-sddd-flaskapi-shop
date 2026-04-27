from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ..interfaces.i_settings_repo import ISettingsRepo
from ...domain.errors import SettingsNotFoundError, TelegramTokenInvalidError, TelegramBotNotStartedError, TelegramStartNotFoundError
from shared.adapters.driven.telegram_client import TelegramClient


@dataclass(frozen=True, slots=True, kw_only=True)
class FetchTelegramChatIdUseCase:
    _repo: ISettingsRepo
    _client: TelegramClient

    def __call__(self, bot_token: str) -> str:
        if not bot_token:
            raise TelegramTokenInvalidError()
        settings = self._repo.get()
        if settings is None:
            raise SettingsNotFoundError()

        updates = self._client.get_updates(bot_token)
        if not updates:
            raise TelegramBotNotStartedError()

        now = datetime.now(timezone.utc)
        for update in reversed(updates):
            msg = update.get("message", {})
            if msg.get("text") == "/start":
                msg_date = datetime.fromtimestamp(msg.get("date", 0), tz=timezone.utc)
                if now - msg_date <= timedelta(minutes=15):
                    return str(msg["chat"]["id"])

        raise TelegramStartNotFoundError()
