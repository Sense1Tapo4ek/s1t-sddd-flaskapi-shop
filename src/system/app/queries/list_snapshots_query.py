from dataclasses import dataclass

from ...domain.snapshot_vo import SnapshotInfo
from ..interfaces.i_snapshot_storage import ISnapshotStorage


@dataclass(frozen=True, slots=True, kw_only=True)
class ListSnapshotsQuery:
    _storage: ISnapshotStorage

    def __call__(self) -> list[SnapshotInfo]:
        return sorted(self._storage.list(), key=lambda s: s.created_at, reverse=True)
