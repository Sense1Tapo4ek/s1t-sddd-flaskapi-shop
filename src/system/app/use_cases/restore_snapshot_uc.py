from dataclasses import dataclass

from ...domain.backup_errors import SnapshotNotFoundError
from ..interfaces.i_snapshot_storage import ISnapshotStorage
from ..interfaces.i_backup_runner import IBackupRunner
from ..interfaces.i_maintenance import IMaintenanceMode
from .create_snapshot_uc import CreateSnapshotUseCase


@dataclass(frozen=True, slots=True, kw_only=True)
class RestoreSnapshotUseCase:
    _storage: ISnapshotStorage
    _runner: IBackupRunner
    _maintenance: IMaintenanceMode
    _create_uc: CreateSnapshotUseCase

    def __call__(self, *, name: str) -> None:
        target = self._storage.info(name)
        if target is None:
            raise SnapshotNotFoundError(name)

        self._create_uc(prefix="pre-restore-")
        self._maintenance.enter()
        try:
            src = self._storage.path_of(name)
            self._runner.restore(src)
            self._runner.apply_migrations()
            self._runner.dispose_pool()
            self._runner.request_worker_restart()
        finally:
            self._maintenance.exit()
