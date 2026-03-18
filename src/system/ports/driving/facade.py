from dataclasses import dataclass

from system.config import SystemConfig
from system.app.interfaces.i_notification_channel import INotificationChannel

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

    def is_notification_configured(self) -> bool:
        """Check whether the notification channel is configured."""
        return self._notification_channel.is_configured()
