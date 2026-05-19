from pathlib import Path

from dishka import Provider, Scope, provide
from sqlalchemy.engine import Engine

from root.config import RootConfig
from shared.adapters.driven import SecretCipher, TelegramClient
from shared.config import InfraConfig
from system.adapters.driven import S3HealthChecker
from system.app import (
    CreateSnapshotUseCase,
    DeleteSnapshotUseCase,
    FetchTelegramChatIdUseCase,
    GetSettingsQuery,
    GetStorageSettingsQuery,
    IBackupRunner,
    IMaintenanceMode,
    ISnapshotStorage,
    ListSnapshotsQuery,
    ManageSettingsUseCase,
    ManageStorageSettingsUseCase,
    RecoverPasswordUseCase,
    RestoreSnapshotUseCase,
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
    FsMaintenanceMode,
    FsSnapshotStorage,
    MysqldumpRunner,
    SettingsRepo,
    SqlStorageSettingsRepo,
    TelegramNotificationChannel,
)
from system.ports.driving import SystemFacade

# Project root: src/system/provider.py → parents[2].
# parents[0] = src/system, parents[1] = src, parents[2] = project root.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DUMPS_DIR = _PROJECT_ROOT / "data" / "dumps"


class SystemProvider(Provider):
    scope = Scope.APP

    @provide
    def config(self) -> SystemConfig:
        return SystemConfig()

    @provide
    def root_config(self) -> RootConfig:
        return RootConfig()

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

    # Backup infra
    @provide
    def snapshot_storage(self) -> ISnapshotStorage:
        _DUMPS_DIR.mkdir(parents=True, exist_ok=True)
        return FsSnapshotStorage(_dumps_dir=_DUMPS_DIR)

    @provide
    def backup_runner(self, engine: Engine, infra_config: InfraConfig) -> IBackupRunner:
        return MysqldumpRunner(_db_url=infra_config.database_url, _engine=engine)

    @provide
    def maintenance_mode(self) -> IMaintenanceMode:
        return FsMaintenanceMode(_flag_path=_PROJECT_ROOT / "data" / ".maintenance")

    # App (Use Cases & Queries)
    get_q = provide(GetSettingsQuery)
    get_storage_q = provide(GetStorageSettingsQuery)
    manage_uc = provide(ManageSettingsUseCase)
    manage_storage_uc = provide(ManageStorageSettingsUseCase)
    test_uc = provide(TestNotificationUseCase)
    recover_uc = provide(RecoverPasswordUseCase)
    fetch_chat_id_uc = provide(FetchTelegramChatIdUseCase)
    list_snapshots_q = provide(ListSnapshotsQuery)
    create_snapshot_uc = provide(CreateSnapshotUseCase)
    restore_snapshot_uc = provide(RestoreSnapshotUseCase)
    delete_snapshot_uc = provide(DeleteSnapshotUseCase)

    # Driving Port (Facade)
    facade = provide(SystemFacade)
