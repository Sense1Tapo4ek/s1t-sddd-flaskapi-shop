from dishka import Provider, Scope, provide

from system.config import SystemConfig
from system.app.interfaces.i_settings_repo import ISettingsRepo
from system.app.interfaces.i_access_acl import IAccessAcl
from system.app.interfaces.i_notification_channel import INotificationChannel
from system.app.use_cases.manage_settings_uc import ManageSettingsUseCase
from system.app.use_cases.test_notification_uc import TestNotificationUseCase
from system.app.queries.get_settings_query import GetSettingsQuery
from system.app.use_cases.recover_password_uc import RecoverPasswordUseCase
from system.app.use_cases.fetch_telegram_chat_id_uc import FetchTelegramChatIdUseCase
from system.ports.driven.settings_repo import SettingsRepo
from system.ports.driven.telegram_channel import TelegramNotificationChannel
from system.ports.driven.access_acl import AccessAcl
from system.ports.driving.facade import SystemFacade
from shared.adapters.driven.telegram_client import TelegramClient


class SystemProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> SystemConfig:
        return SystemConfig()

    # Shared infra
    telegram_client = provide(TelegramClient)

    # Driven Ports
    repo = provide(SettingsRepo, provides=ISettingsRepo)
    notification_channel = provide(TelegramNotificationChannel, provides=INotificationChannel)
    acl = provide(AccessAcl, provides=IAccessAcl)

    # App (Use Cases & Queries)
    get_q = provide(GetSettingsQuery)
    manage_uc = provide(ManageSettingsUseCase)
    test_uc = provide(TestNotificationUseCase)
    recover_uc = provide(RecoverPasswordUseCase)
    fetch_chat_id_uc = provide(FetchTelegramChatIdUseCase)

    # Driving Port (Facade)
    facade = provide(SystemFacade)
