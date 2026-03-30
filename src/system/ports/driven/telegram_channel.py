from dataclasses import dataclass
from system.app.interfaces.i_notification_channel import INotificationChannel
from system.app.interfaces.i_settings_repo import ISettingsRepo
from shared.adapters.driven.telegram_client import TelegramClient


@dataclass(frozen=True, slots=True)
class TelegramNotificationChannel(INotificationChannel):
    _repo: ISettingsRepo
    _client: TelegramClient

    def is_configured(self) -> bool:
        settings = self._repo.get()
        return settings is not None and settings.is_telegram_configured

    def send(self, subject: str, body: str) -> None:
        settings = self._repo.get()
        if settings is None or not settings.is_telegram_configured:
            return
        self._client.send_message(
            token=settings.telegram_bot_token,
            chat_id=settings.telegram_chat_id,
            text=f"<b>{subject}</b>\n{body}",
        )
