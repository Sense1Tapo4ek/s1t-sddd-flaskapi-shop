from dataclasses import dataclass
from html import escape

from system.config import SystemConfig
from system.app.interfaces.i_notification_channel import INotificationChannel
from shared.adapters.driven.telegram_client import TelegramClient

from ...app import (
    GetSettingsQuery,
    ManageSettingsUseCase,
    TestNotificationUseCase,
    RecoverPasswordUseCase,
    FetchTelegramChatIdUseCase,
)
from .schemas import FetchChatIdIn, SettingsOut, InfoOut, SettingsUpdateIn


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemFacade:
    """
    Public Entry Point for the System Context.
    Used by: Admin Context (Adapters), Public API (Adapters).
    """

    _config: SystemConfig
    _get_query: GetSettingsQuery
    _manage_uc: ManageSettingsUseCase
    _test_notify_uc: TestNotificationUseCase
    _recover_password_uc: RecoverPasswordUseCase
    _fetch_chat_id_uc: FetchTelegramChatIdUseCase
    _notification_channel: INotificationChannel
    _telegram_client: TelegramClient

    def get_config(self) -> SystemConfig:
        return self._config

    def get_settings(self) -> SettingsOut:
        """Full settings for admin panel."""
        settings = self._get_query()
        return SettingsOut.from_domain(settings)

    def get_public_info(self) -> InfoOut:
        """Safe settings for public footer/contacts."""
        settings = self._get_query()
        return InfoOut.from_domain(settings)

    def update_settings(self, schema: SettingsUpdateIn) -> SettingsOut:
        """Update settings from admin panel."""
        cmd = schema.to_command()
        settings = self._manage_uc(cmd)
        return SettingsOut.from_domain(settings)

    def test_telegram(self) -> bool:
        """Trigger a test notification."""
        return self._test_notify_uc()

    def recover_password(self) -> bool:
        """Trigger password recovery via Telegram."""
        return self._recover_password_uc()

    def fetch_telegram_chat_id(self, schema: FetchChatIdIn) -> str:
        return self._fetch_chat_id_uc(bot_token=schema.bot_token)

    def send_notification(self, subject: str, body: str) -> None:
        """Send a notification via the configured channel."""
        self._notification_channel.send(subject=subject, body=body)

    def send_notification_to_chat(
        self,
        *,
        chat_id: str,
        subject: str,
        body: str,
    ) -> bool:
        settings = self._get_query()
        if not settings.telegram_bot_token or not chat_id:
            return False
        return self._telegram_client.send_message(
            token=settings.telegram_bot_token,
            chat_id=chat_id,
            text=f"<b>{escape(subject)}</b>\n{escape(body)}",
        )

    def is_notification_configured(self) -> bool:
        """Check whether the notification channel is configured."""
        return self._notification_channel.is_configured()

    def send_login_code(
        self,
        *,
        chat_id: str,
        login: str,
        code: str,
        title: str = "Login Code",
        ttl_minutes: int = 5,
    ) -> bool:
        settings = self._get_query()
        if not settings.telegram_bot_token:
            return False
        text = (
            f"<b>{escape(title)}</b>\n\n"
            f"Account: <code>{escape(login)}</code>\n"
            f"Code: <code>{escape(code)}</code>\n\n"
            f"Valid for {ttl_minutes} minutes."
        )
        return self._telegram_client.send_message(
            token=settings.telegram_bot_token,
            chat_id=chat_id,
            text=text,
        )
