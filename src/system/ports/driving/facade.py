from dataclasses import dataclass
from html import escape

from root.config import RootConfig
from system.config import SystemConfig
from system.app.interfaces.i_notification_channel import INotificationChannel
from shared.adapters.driven.telegram_client import TelegramClient

from ...app import (
    CreateSnapshotUseCase,
    DeleteSnapshotUseCase,
    FetchTelegramChatIdUseCase,
    GetSettingsQuery,
    GetStorageSettingsQuery,
    ListSnapshotsQuery,
    ManageSettingsUseCase,
    ManageStorageSettingsUseCase,
    RecoverPasswordUseCase,
    RestoreSnapshotUseCase,
    TestNotificationUseCase,
)
from .schemas import (
    FetchChatIdIn,
    InfoOut,
    SettingsOut,
    SettingsUpdateIn,
    SocialsFlags,
    SnapshotListOut,
    SnapshotOut,
    StorageSettingsOut,
    StorageSettingsUpdateIn,
)


@dataclass(frozen=True, slots=True, kw_only=True)
class SystemFacade:
    """
    Public Entry Point for the System Context.
    Used by: Admin Context (Adapters), Public API (Adapters).
    """

    _config: SystemConfig
    _root_config: RootConfig
    _get_query: GetSettingsQuery
    _get_storage_query: GetStorageSettingsQuery
    _manage_uc: ManageSettingsUseCase
    _manage_storage_uc: ManageStorageSettingsUseCase
    _test_notify_uc: TestNotificationUseCase
    _recover_password_uc: RecoverPasswordUseCase
    _fetch_chat_id_uc: FetchTelegramChatIdUseCase
    _notification_channel: INotificationChannel
    _telegram_client: TelegramClient
    _list_snapshots_query: ListSnapshotsQuery
    _create_snapshot_uc: CreateSnapshotUseCase
    _restore_snapshot_uc: RestoreSnapshotUseCase
    _delete_snapshot_uc: DeleteSnapshotUseCase

    def get_config(self) -> SystemConfig:
        return self._config

    def _socials_flags(self) -> SocialsFlags:
        cfg = self._config
        return SocialsFlags(
            instagram=cfg.socials_instagram_enabled,
            telegram=cfg.socials_telegram_enabled,
            whatsapp=cfg.socials_whatsapp_enabled,
            viber=cfg.socials_viber_enabled,
        )

    def get_settings(self) -> SettingsOut:
        """Full settings for admin panel."""
        settings = self._get_query()
        return SettingsOut.from_domain(settings, self._socials_flags())

    def get_public_info(self) -> InfoOut:
        """Safe settings for public footer/contacts."""
        settings = self._get_query()
        return InfoOut.from_domain(
            settings,
            app_name=self._root_config.app_name,
            socials_flags=self._socials_flags(),
        )

    def update_settings(self, schema: SettingsUpdateIn) -> SettingsOut:
        """Update settings from admin panel."""
        cmd = schema.to_command()
        settings = self._manage_uc(cmd)
        return SettingsOut.from_domain(settings, self._socials_flags())

    def get_storage_settings(self) -> StorageSettingsOut:
        """Storage configuration view for admin (secret is masked)."""
        return StorageSettingsOut.from_domain(self._get_storage_query())

    def update_storage_settings(
        self, schema: StorageSettingsUpdateIn
    ) -> StorageSettingsOut:
        """Update storage configuration. Cache is invalidated inside the use case."""
        settings = self._manage_storage_uc(schema.to_command())
        return StorageSettingsOut.from_domain(settings)

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

    def list_snapshots(self) -> SnapshotListOut:
        """Return all snapshots, newest first."""
        return SnapshotListOut.from_domain(self._list_snapshots_query())

    def create_snapshot(self) -> SnapshotOut:
        """Create a new snapshot with the default (empty) prefix."""
        return SnapshotOut.from_domain(self._create_snapshot_uc(prefix=""))

    def restore_snapshot(self, *, name: str) -> None:
        """Restore the database from snapshot *name*."""
        self._restore_snapshot_uc(name=name)

    def delete_snapshot(self, *, name: str) -> None:
        """Permanently delete snapshot *name*."""
        self._delete_snapshot_uc(name=name)

    def is_notification_configured(self) -> bool:
        """Check whether the notification channel is configured."""
        return self._notification_channel.is_configured()

    def send_login_code(
        self,
        *,
        chat_id: str,
        login: str,
        code: str,
        title: str = "Код для входа",
        ttl_minutes: int = 5,
    ) -> bool:
        settings = self._get_query()
        if not settings.telegram_bot_token:
            return False
        text = (
            f"<b>{escape(title)}</b>\n\n"
            f"Аккаунт: <code>{escape(login)}</code>\n"
            f"Код: <code>{escape(code)}</code>\n\n"
            f"Действителен {ttl_minutes} минут."
        )
        return self._telegram_client.send_message(
            token=settings.telegram_bot_token,
            chat_id=chat_id,
            text=text,
        )
