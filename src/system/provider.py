from dishka import Provider, Scope, provide

from shared.adapters.driven import SecretCipher, TelegramClient
from system.adapters.driven import S3HealthChecker
from system.app import (
    FetchTelegramChatIdUseCase,
    GetSettingsQuery,
    GetStorageSettingsQuery,
    ManageSettingsUseCase,
    ManageStorageSettingsUseCase,
    RecoverPasswordUseCase,
    TestNotificationUseCase,
)
from system.app.interfaces import (
    IAccessAcl,
    INotificationChannel,
    IS3HealthChecker,
    ISettingsRepo,
    IStorageSettingsRepo,
)
from system.config import SystemConfig
from system.ports.driven import (
    AccessAcl,
    SettingsRepo,
    SqlStorageSettingsRepo,
    TelegramNotificationChannel,
)
from system.ports.driving import SystemFacade


class SystemProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> SystemConfig:
        return SystemConfig()

    @provide
    def cipher(self, config: SystemConfig) -> SecretCipher:
        return SecretCipher(_key=config.storage_secrets_key)

    # Shared infra
    telegram_client = provide(TelegramClient)

    # Driven Ports
    repo = provide(SettingsRepo, provides=ISettingsRepo)
    storage_settings_repo = provide(
        SqlStorageSettingsRepo, provides=IStorageSettingsRepo
    )
    notification_channel = provide(
        TelegramNotificationChannel, provides=INotificationChannel
    )
    acl = provide(AccessAcl, provides=IAccessAcl)
    s3_health_checker = provide(S3HealthChecker, provides=IS3HealthChecker)

    # App (Use Cases & Queries)
    get_q = provide(GetSettingsQuery)
    get_storage_q = provide(GetStorageSettingsQuery)
    manage_uc = provide(ManageSettingsUseCase)
    manage_storage_uc = provide(ManageStorageSettingsUseCase)
    test_uc = provide(TestNotificationUseCase)
    recover_uc = provide(RecoverPasswordUseCase)
    fetch_chat_id_uc = provide(FetchTelegramChatIdUseCase)

    # Driving Port (Facade)
    facade = provide(SystemFacade)
