from dataclasses import dataclass

from ...domain.backup_errors import SnapshotNotFoundError
from ..interfaces.i_snapshot_storage import ISnapshotStorage


@dataclass(frozen=True, slots=True, kw_only=True)
class DeleteSnapshotUseCase:
    _storage: ISnapshotStorage

    def __call__(self, *, name: str) -> None:
        if self._storage.info(name) is None:
            raise SnapshotNotFoundError(name)
        self._storage.delete(name)
